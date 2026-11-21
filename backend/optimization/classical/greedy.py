from __future__ import annotations

import itertools
import math
import time
from typing import Dict, Iterable, List, Sequence

from backend.energy.energy_model import EnergyModel
from backend.optimization.classical import ClassicalOptimizationResult


def _candidate_combination_score(model: EnergyModel, schedule: Dict[str, list[int]], appliance_name: str, candidate_hours: Sequence[int]) -> float:
    score = 0.0
    for hour in candidate_hours:
        power = next(a.power_kw for a in model.appliances if a.name == appliance_name)
        tariff_cost = model.tariff_schedule.tariffs[hour] * power
        discomfort_cost = 0.0
        appliance = next(a for a in model.appliances if a.name == appliance_name)
        if hour not in appliance.preferred_set():
            discomfort_cost = appliance.discomfort_weight * 1.5
        score += tariff_cost + discomfort_cost

    demand_after = model.hourly_total_demand(schedule)
    for hour in candidate_hours:
        demand_after[hour] += next(a.power_kw for a in model.appliances if a.name == appliance_name)
    peak_after = max(demand_after)
    score += 0.25 * peak_after
    return score


def solve_greedy(model: EnergyModel, alpha: float = 1.0, beta: float = 1.5, gamma: float = 0.8) -> ClassicalOptimizationResult:
    """Greedy heuristic that schedules each appliance in the cheapest preferred slots while respecting active-hour windows."""
    start = time.perf_counter()
    schedule: Dict[str, list[int]] = {appliance.name: [0] * 24 for appliance in model.appliances}
    sorted_appliances = sorted(
        model.appliances,
        key=lambda a: (-(a.power_kw * a.duration_hours), a.latest_hour, len(a.allowed_hours())),
    )

    for appliance in sorted_appliances:
        best_hours: Sequence[int] | None = None
        best_score = math.inf
        allowed = list(appliance.allowed_hours())
        for candidate in itertools.combinations(allowed, appliance.duration_hours):
            trial = {name: hour_list[:] for name, hour_list in schedule.items()}
            trial[appliance.name] = [0] * 24
            for hour in candidate:
                trial[appliance.name][hour] = 1
            valid, _ = model.validate_schedule(trial)
            if not valid:
                continue
            score = _candidate_combination_score(model, schedule, appliance.name, candidate)
            if score < best_score:
                best_score = score
                best_hours = candidate
        if best_hours is None:
            fallback_hours = sorted(allowed)[:appliance.duration_hours]
            best_hours = tuple(fallback_hours)
        for hour in best_hours:
            schedule[appliance.name][hour] = 1

    valid, issues = model.validate_schedule(schedule)
    objective_value = model.objective(schedule, alpha=alpha, beta=beta, gamma=gamma)
    electricity_cost = sum(model.tariff_schedule.tariffs[hour] * value for hour, value in enumerate(model.grid_import_and_battery(schedule)[0]))
    peak_demand = max(model.hourly_total_demand(schedule))
    discomfort_cost = model.discomfort_cost(schedule)
    runtime = time.perf_counter() - start

    return ClassicalOptimizationResult(
        method="Greedy",
        schedule=schedule,
        objective_value=objective_value,
        electricity_cost=electricity_cost,
        peak_demand=peak_demand,
        discomfort_cost=discomfort_cost,
        feasible=valid,
        runtime_seconds=runtime,
        details={
            "issues": issues,
            "peak_after_grid": peak_demand,
        },
    )
