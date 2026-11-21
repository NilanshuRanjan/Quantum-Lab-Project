from __future__ import annotations

import time
from dataclasses import dataclass, field
from itertools import combinations
from typing import Any, Dict, Iterable, List, Sequence, Tuple

import numpy as np
from qiskit import QuantumCircuit
from qiskit_aer import AerSimulator
from scipy.optimize import minimize

from backend.energy.energy_model import EnergyModel


@dataclass
class StandardQAOAResult:
    method: str
    schedule: Dict[str, list[int]]
    objective_value: float
    electricity_cost: float
    peak_demand: float
    discomfort_cost: float
    feasible: bool
    runtime_seconds: float
    parameters: Dict[str, list[float]]
    circuit_depth: int
    qubits: int
    shots: int
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "method": self.method,
            "schedule": self.schedule,
            "objective_value": self.objective_value,
            "electricity_cost": self.electricity_cost,
            "peak_demand": self.peak_demand,
            "discomfort_cost": self.discomfort_cost,
            "feasible": self.feasible,
            "runtime_seconds": self.runtime_seconds,
            "parameters": self.parameters,
            "circuit_depth": self.circuit_depth,
            "qubits": self.qubits,
            "shots": self.shots,
            "details": self.details,
        }


def _build_variable_index(model: EnergyModel, appliance_limit: int | None = None, hour_limit: int | None = None) -> List[Tuple[str, int]]:
    appliances = model.appliances[: appliance_limit] if appliance_limit is not None else model.appliances
    variables: List[Tuple[str, int]] = []
    for appliance in appliances:
        for hour in range(24):
            if hour_limit is not None and hour >= hour_limit:
                continue
            if appliance.earliest_hour <= hour <= appliance.latest_hour:
                variables.append((appliance.name, hour))
    return variables


def _build_qubo_matrix(
    model: EnergyModel,
    variables: Sequence[Tuple[str, int]],
    alpha: float = 1.0,
    beta: float = 1.5,
    gamma: float = 0.8,
    duration_penalty: float = 10.0,
) -> np.ndarray:
    n = len(variables)
    qubo = np.zeros((n, n), dtype=float)
    index_by_var = {var: idx for idx, var in enumerate(variables)}

    for appliance in model.appliances:
        if appliance.name not in {name for name, _ in variables}:
            continue
        allowed_hours = [hour for hour in range(24) if appliance.earliest_hour <= hour <= appliance.latest_hour]
        if not allowed_hours:
            continue
        selected_hours = [hour for name, hour in variables if name == appliance.name]
        for hour in selected_hours:
            idx = index_by_var[(appliance.name, hour)]
            cost = alpha * model.tariff_schedule.tariffs[hour] * appliance.power_kw
            qubo[idx, idx] += cost
            if hour not in appliance.preferred_set():
                qubo[idx, idx] += gamma * appliance.discomfort_weight * 1.5

        d = appliance.duration_hours
        for hour in selected_hours:
            idx = index_by_var[(appliance.name, hour)]
            qubo[idx, idx] += duration_penalty * (1.0 - 2.0 * d)
        for h1, h2 in combinations(selected_hours, 2):
            i = index_by_var[(appliance.name, h1)]
            j = index_by_var[(appliance.name, h2)]
            qubo[i, j] += 2.0 * duration_penalty
            qubo[j, i] += 2.0 * duration_penalty

    for hour in range(24):
        hour_vars = [(name, h) for name, h in variables if h == hour]
        for i in range(len(hour_vars)):
            for j in range(i + 1, len(hour_vars)):
                n1, _ = hour_vars[i]
                n2, _ = hour_vars[j]
                ap1 = next(a for a in model.appliances if a.name == n1)
                ap2 = next(a for a in model.appliances if a.name == n2)
                q_val = beta * ap1.power_kw * ap2.power_kw
                idx1 = index_by_var[hour_vars[i]]
                idx2 = index_by_var[hour_vars[j]]
                qubo[idx1, idx2] += q_val
                qubo[idx2, idx1] += q_val

    return qubo


def _qubo_to_ising(qubo: np.ndarray) -> Tuple[np.ndarray, np.ndarray, float]:
    n = qubo.shape[0]
    h = np.zeros(n, dtype=float)
    J = np.zeros((n, n), dtype=float)
    for i in range(n):
        h[i] = -0.5 * qubo[i, i] - 0.25 * (np.sum(qubo[i, :]) - qubo[i, i])
    for i in range(n):
        for j in range(i + 1, n):
            J[i, j] = 0.25 * qubo[i, j]
            J[j, i] = J[i, j]
    offset = 0.5 * np.sum(np.diag(qubo)) + 0.25 * np.sum(qubo - np.diag(np.diag(qubo)))
    return h, J, offset


def _build_qaoa_circuit(
    n_qubits: int,
    h: np.ndarray,
    J: np.ndarray,
    params: Sequence[float],
    p: int,
) -> QuantumCircuit:
    if len(params) != 2 * p:
        raise ValueError(f"Expected {2 * p} parameters, got {len(params)}.")
    qc = QuantumCircuit(n_qubits)
    for q in range(n_qubits):
        qc.h(q)

    gamma_params = params[:p]
    beta_params = params[p:]
    for layer in range(p):
        for q in range(n_qubits):
            qc.rz(2.0 * gamma_params[layer] * h[q], q)
        for i in range(n_qubits):
            for j in range(i + 1, n_qubits):
                if abs(J[i, j]) > 1e-12:
                    qc.rzz(2.0 * gamma_params[layer] * J[i, j], i, j)
        for q in range(n_qubits):
            qc.rx(2.0 * beta_params[layer], q)
    return qc


def _statevector_expectation(statevector: np.ndarray, h: np.ndarray, J: np.ndarray) -> float:
    probs = np.abs(statevector) ** 2
    n = h.shape[0]
    energy = 0.0
    for basis in range(1 << n):
        prob = probs[basis]
        z_values = [1.0 if ((basis >> qubit) & 1) == 0 else -1.0 for qubit in range(n)]
        local_energy = 0.0
        for i in range(n):
            local_energy += h[i] * z_values[i]
        for i in range(n):
            for j in range(i + 1, n):
                local_energy += J[i, j] * z_values[i] * z_values[j]
        energy += prob * local_energy
    return float(energy)


def _circuit_expectation(params: Sequence[float], n_qubits: int, h: np.ndarray, J: np.ndarray, p: int) -> float:
    qc = _build_qaoa_circuit(n_qubits, h, J, params, p)
    qc.save_statevector()
    simulator = AerSimulator(method="statevector")
    result = simulator.run(qc).result()
    statevector = result.get_statevector(qc)
    return _statevector_expectation(statevector, h, J)


def _decode_bitstring(bitstring: str, variables: Sequence[Tuple[str, int]], n_qubits: int) -> Dict[str, list[int]]:
    schedule = {name: [0] * 24 for name in sorted({name for name, _ in variables})}
    for idx, (name, hour) in enumerate(variables):
        bit = int(bitstring[-(idx + 1)]) if idx < len(bitstring) else 0
        schedule[name][hour] = bit
    return schedule


def _best_decoded_schedule(
    model: EnergyModel,
    counts: Dict[str, int],
    variables: Sequence[Tuple[str, int]],
    n_qubits: int,
) -> Tuple[Dict[str, list[int]], float, bool]:
    best_schedule: Dict[str, list[int]] | None = None
    best_objective = float("inf")
    best_feasible = False

    for bitstring, count in counts.items():
        if len(bitstring) < n_qubits:
            bitstring = bitstring.rjust(n_qubits, "0")
        schedule = _decode_bitstring(bitstring, variables, n_qubits)
        valid, _ = model.validate_schedule(schedule)
        if not valid:
            continue
        objective = model.objective(schedule)
        if objective < best_objective:
            best_objective = objective
            best_schedule = schedule
            best_feasible = True
    if best_schedule is None:
        fallback_schedule = model.generate_feasible_schedule()
        valid, _ = model.validate_schedule(fallback_schedule)
        best_schedule = fallback_schedule
        best_objective = model.objective(best_schedule)
        best_feasible = valid
    return best_schedule, best_objective, best_feasible


def solve_standard_qaoa(
    model: EnergyModel,
    p: int = 2,
    shots: int = 1024,
    maxiter: int = 30,
    seed: int = 123,
    alpha: float = 1.0,
    beta: float = 1.5,
    gamma: float = 0.8,
    appliance_limit: int | None = 3,
    hour_limit: int | None = 12,
    initial_params: Sequence[float] | None = None,
) -> StandardQAOAResult:
    """Construct and execute a standard QAOA circuit for a compact appliance-scheduling instance."""
    start = time.perf_counter()
    selected_appliances = model.appliances[:appliance_limit] if appliance_limit is not None else model.appliances
    reduced_model = EnergyModel(
        appliances=selected_appliances,
        solar_profile=model.solar_profile,
        tariff_schedule=model.tariff_schedule,
        battery=model.battery,
        fixed_loads=model.fixed_loads,
        max_grid_kw=model.max_grid_kw,
        peak_penalty_weight=model.peak_penalty_weight,
        discomfort_weight=model.discomfort_weight,
    )
    variables = _build_variable_index(reduced_model, appliance_limit=None, hour_limit=hour_limit)
    if len(variables) > 8:
        variables = variables[:8]
    if not variables:
        raise ValueError("No usable scheduling variables were produced for the requested QAOA instance.")
    qubo = _build_qubo_matrix(reduced_model, variables, alpha=alpha, beta=beta, gamma=gamma)
    h, J, _ = _qubo_to_ising(qubo)

    rng = np.random.default_rng(seed)
    x0 = np.asarray(initial_params, dtype=float) if initial_params is not None else rng.uniform(0.0, np.pi, size=2 * p)
    if x0.size != 2 * p:
        if x0.size < 2 * p:
            x0 = np.pad(x0, (0, 2 * p - x0.size), mode="constant")
        else:
            x0 = x0[: 2 * p]
    optimizer = minimize(
        lambda params: _circuit_expectation(params, len(variables), h, J, p),
        x0,
        method="L-BFGS-B",
        options={"maxiter": maxiter},
    )
    params = optimizer.x
    qc = _build_qaoa_circuit(len(variables), h, J, params, p)
    qc.save_statevector()
    simulator = AerSimulator(method="statevector")
    state_result = simulator.run(qc).result()
    statevector = state_result.get_statevector(qc)
    final_value = _statevector_expectation(statevector, h, J)

    measurement_simulator = AerSimulator()
    measurement_result = measurement_simulator.run(qc, shots=shots).result().get_counts()
    schedule, objective_value, feasible = _best_decoded_schedule(reduced_model, measurement_result, variables, len(variables))
    grid_import, _ = reduced_model.grid_import_and_battery(schedule)
    electricity_cost = sum(reduced_model.tariff_schedule.tariffs[hour] * grid_import[hour] for hour in range(24))
    peak_demand = max(reduced_model.hourly_total_demand(schedule))
    discomfort_cost = reduced_model.discomfort_cost(schedule)
    runtime = time.perf_counter() - start

    return StandardQAOAResult(
        method="StandardQAOA",
        schedule=schedule,
        objective_value=objective_value,
        electricity_cost=electricity_cost,
        peak_demand=peak_demand,
        discomfort_cost=discomfort_cost,
        feasible=feasible,
        runtime_seconds=runtime,
        parameters={"gamma": params[:p].tolist(), "beta": params[p:].tolist()},
        circuit_depth=p,
        qubits=len(variables),
        shots=shots,
        details={
            "optimizer_success": optimizer.success,
            "optimizer_message": optimizer.message,
            "final_ising_objective": float(final_value),
            "variables": variables,
            "qubo_shape": qubo.shape,
            "counts": dict(measurement_result),
            "selected_appliances": [a.name for a in selected_appliances],
        },
    )
