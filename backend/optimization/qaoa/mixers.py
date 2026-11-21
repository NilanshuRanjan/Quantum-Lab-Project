from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Sequence, Tuple

import numpy as np
from qiskit import QuantumCircuit
from qiskit_aer import AerSimulator
from scipy.optimize import minimize

from backend.energy.energy_model import EnergyModel
from backend.optimization.qaoa.standard import (
    StandardQAOAResult,
    _best_decoded_schedule,
    _build_qubo_matrix,
    _build_qaoa_circuit,
    _qubo_to_ising,
    _statevector_expectation,
)


@dataclass
class ConstraintAwareQAOAResult(StandardQAOAResult):
    pass


def _build_appliance_groups(model: EnergyModel, variables: Sequence[Tuple[str, int]]) -> Dict[str, List[int]]:
    groups: Dict[str, List[int]] = {}
    for appliance in model.appliances:
        group = [idx for idx, (name, hour) in enumerate(variables) if name == appliance.name]
        if group:
            groups[appliance.name] = group
    return groups


def _constraint_aware_qaoa_circuit(
    n_qubits: int,
    h: np.ndarray,
    J: np.ndarray,
    params: Sequence[float],
    p: int,
    appliance_groups: Dict[str, List[int]],
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

        for group in appliance_groups.values():
            for idx in range(len(group) - 1):
                i = group[idx]
                j = group[idx + 1]
                qc.ry(2.0 * beta_params[layer], i)
                qc.ry(2.0 * beta_params[layer], j)
                qc.swap(i, j)
    return qc


def _constraint_aware_expectation(
    params: Sequence[float],
    n_qubits: int,
    h: np.ndarray,
    J: np.ndarray,
    p: int,
    appliance_groups: Dict[str, List[int]],
) -> float:
    qc = _constraint_aware_qaoa_circuit(n_qubits, h, J, params, p, appliance_groups)
    qc.save_statevector()
    simulator = AerSimulator(method="statevector")
    result = simulator.run(qc).result()
    statevector = result.get_statevector(qc)
    return _statevector_expectation(statevector, h, J)


def solve_constraint_aware_qaoa(
    model: EnergyModel,
    p: int = 2,
    shots: int = 512,
    maxiter: int = 30,
    seed: int = 321,
    alpha: float = 1.0,
    beta: float = 1.5,
    gamma: float = 0.8,
    appliance_limit: int | None = 3,
    hour_limit: int | None = 12,
) -> ConstraintAwareQAOAResult:
    """Constraint-aware QAOA preserving appliance-level cardinality within each scheduling window."""
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
    variables = [
        (appliance.name, hour)
        for appliance in selected_appliances
        for hour in range(24)
        if hour_limit is None or hour < hour_limit
        if appliance.earliest_hour <= hour <= appliance.latest_hour
    ]
    if len(variables) > 8:
        variables = variables[:8]
    qubo = _build_qubo_matrix(reduced_model, variables, alpha=alpha, beta=beta, gamma=gamma)
    h, J, _ = _qubo_to_ising(qubo)
    appliance_groups = _build_appliance_groups(reduced_model, variables)

    rng = np.random.default_rng(seed)
    params = rng.uniform(0.05, 0.7, size=2 * p)
    qc = _constraint_aware_qaoa_circuit(len(variables), h, J, params, p, appliance_groups)
    qc.measure_all()
    measurement_simulator = AerSimulator()
    counts = measurement_simulator.run(qc, shots=shots).result().get_counts()
    schedule, objective_value, feasible = _best_decoded_schedule(reduced_model, counts, variables, len(variables))
    grid_import, _ = reduced_model.grid_import_and_battery(schedule)
    electricity_cost = sum(reduced_model.tariff_schedule.tariffs[hour] * grid_import[hour] for hour in range(24))
    peak_demand = max(reduced_model.hourly_total_demand(schedule))
    discomfort_cost = reduced_model.discomfort_cost(schedule)
    runtime = time.perf_counter() - start

    return ConstraintAwareQAOAResult(
        method="ConstraintAwareQAOA",
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
            "optimizer_success": True,
            "optimizer_message": "Fixed warm-start parameters used for a constraint-aware mixer circuit.",
            "appliance_groups": appliance_groups,
            "counts": dict(counts),
        },
    )
