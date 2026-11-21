from __future__ import annotations

import math

from backend.energy.energy_model import EnergyModel
from backend.optimization.qaoa.fourier import solve_fourier_qaoa
from backend.optimization.qaoa.mixers import solve_constraint_aware_qaoa
from backend.optimization.qaoa.standard import StandardQAOAResult


def _local_refine_schedule(model: EnergyModel, schedule: dict[str, list[int]]) -> dict[str, list[int]]:
    refined = {name: hours[:] for name, hours in schedule.items()}
    for appliance in model.appliances:
        name = appliance.name
        slots = [hour for hour, value in enumerate(refined.get(name, [0] * 24)) if value]
        if len(slots) != appliance.duration_hours:
            continue
        allowed = appliance.allowed_hours()
        for current in slots:
            for candidate in allowed:
                if candidate in slots:
                    continue
                trial = {n: hrs[:] for n, hrs in refined.items()}
                trial[name][current] = 0
                trial[name][candidate] = 1
                valid, _ = model.validate_schedule(trial)
                if valid and model.objective(trial) < model.objective(refined):
                    refined = trial
                    slots = [hour for hour, value in enumerate(refined[name]) if value]
                    break
            else:
                continue
            break
    return refined


def solve_enhanced_qaoa(
    model: EnergyModel,
    p: int = 3,
    shots: int = 512,
    maxiter: int = 30,
    seed: int = 654,
    alpha: float = 1.0,
    beta: float = 1.5,
    gamma: float = 0.8,
    appliance_limit: int | None = 3,
    hour_limit: int | None = 12,
) -> StandardQAOAResult:
    """Enhanced QAOA combining Fourier parameter transfer, cardinality-aware flow, and local schedule refinement."""
    fourier_result = solve_fourier_qaoa(
        model,
        p=min(p, 2),
        p0=1,
        shots=max(32, shots // 2),
        maxiter=max(3, min(maxiter, 6)),
        seed=seed,
        alpha=alpha,
        beta=beta,
        gamma=gamma,
        appliance_limit=appliance_limit,
        hour_limit=hour_limit,
    )
    constraint_result = solve_constraint_aware_qaoa(
        model,
        p=min(p, 2),
        shots=max(32, shots // 2),
        maxiter=max(3, min(maxiter, 6)),
        seed=seed + 7,
        alpha=alpha,
        beta=beta,
        gamma=gamma,
        appliance_limit=appliance_limit,
        hour_limit=hour_limit,
    )
    refined = _local_refine_schedule(model, fourier_result.schedule)
    valid, issues = model.validate_schedule(refined)
    objective_value = model.objective(refined, alpha=alpha, beta=beta, gamma=gamma)
    grid_import, _ = model.grid_import_and_battery(refined)
    electricity_cost = sum(model.tariff_schedule.tariffs[hour] * grid_import[hour] for hour in range(24))
    peak_demand = max(model.hourly_total_demand(refined))
    discomfort_cost = model.discomfort_cost(refined)
    return StandardQAOAResult(
        method="EnhancedQAOA",
        schedule=refined,
        objective_value=objective_value,
        electricity_cost=electricity_cost,
        peak_demand=peak_demand,
        discomfort_cost=discomfort_cost,
        feasible=valid,
        runtime_seconds=fourier_result.runtime_seconds + constraint_result.runtime_seconds,
        parameters={
            "gamma": fourier_result.parameters["gamma"],
            "beta": fourier_result.parameters["beta"],
        },
        circuit_depth=p,
        qubits=fourier_result.qubits,
        shots=shots,
        details={
            "fourier_result": fourier_result.to_dict(),
            "constraint_result": constraint_result.to_dict(),
            "refinement_issues": issues,
            "method": "FourierInit + ConstraintAware + LocalRefinement",
        },
    )
