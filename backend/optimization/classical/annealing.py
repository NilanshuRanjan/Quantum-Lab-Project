from __future__ import annotations

import math
import random
import time
from typing import Dict, List, Sequence

from backend.energy.energy_model import EnergyModel
from backend.optimization.classical import ClassicalOptimizationResult


def solve_simulated_annealing(
    model: EnergyModel,
    iterations: int = 4000,
    initial_temperature: float = 8.0,
    cooling_rate: float = 0.995,
    seed: int = 0,
    alpha: float = 1.0,
    beta: float = 1.5,
    gamma: float = 0.8,
) -> ClassicalOptimizationResult:
    """Stochastic local search that preserves appliance duration counts while swapping active hours within their feasible windows."""
    start = time.perf_counter()
    rng = random.Random(seed)
    schedule = {appliance.name: appliance.generate_feasible_schedule() for appliance in model.appliances}
    current_score = model.objective(schedule, alpha=alpha, beta=beta, gamma=gamma)
    temperature = initial_temperature

    for _ in range(iterations):
        candidate_schedule = {name: hours[:] for name, hours in schedule.items()}
        appliance = rng.choice(model.appliances)
        active_hours = [hour for hour, value in enumerate(candidate_schedule[appliance.name]) if value]
        if len(active_hours) == 0:
            continue
        allowed_hours = appliance.allowed_hours()
        inactive_hours = [hour for hour in allowed_hours if hour not in active_hours]
        if not inactive_hours:
            continue
        src = rng.choice(active_hours)
        dst = rng.choice(inactive_hours)
        candidate_schedule[appliance.name][src] = 0
        candidate_schedule[appliance.name][dst] = 1

        valid, _ = model.validate_schedule(candidate_schedule)
        if not valid:
            continue

        candidate_score = model.objective(candidate_schedule, alpha=alpha, beta=beta, gamma=gamma)
        delta = candidate_score - current_score
        if delta <= 0 or rng.random() < math.exp(-(delta / max(temperature, 1e-9))):
            schedule = candidate_schedule
            current_score = candidate_score
        temperature *= cooling_rate

    valid, issues = model.validate_schedule(schedule)
    objective_value = model.objective(schedule, alpha=alpha, beta=beta, gamma=gamma)
    electricity_cost = sum(model.tariff_schedule.tariffs[hour] * value for hour, value in enumerate(model.grid_import_and_battery(schedule)[0]))
    peak_demand = max(model.hourly_total_demand(schedule))
    discomfort_cost = model.discomfort_cost(schedule)
    runtime = time.perf_counter() - start

    return ClassicalOptimizationResult(
        method="SimulatedAnnealing",
        schedule=schedule,
        objective_value=objective_value,
        electricity_cost=electricity_cost,
        peak_demand=peak_demand,
        discomfort_cost=discomfort_cost,
        feasible=valid,
        runtime_seconds=runtime,
        details={
            "iterations": iterations,
            "seed": seed,
            "issues": issues,
            "temperature": temperature,
        },
    )
