from __future__ import annotations

import time
from itertools import combinations
from typing import Dict, Iterable, List, Sequence

import pulp

from backend.energy.energy_model import EnergyModel
from backend.optimization.classical import ClassicalOptimizationResult


def solve_milp(model: EnergyModel, alpha: float = 1.0, beta: float = 1.5, gamma: float = 0.8) -> ClassicalOptimizationResult:
    """Solve the appliance-scheduling baseline as a compact MILP with linearized peak-demand proxy."""
    start = time.perf_counter()
    variables: Dict[tuple[str, int], pulp.LpVariable] = {}
    problem = pulp.LpProblem("smartgrid_qaoa_milp", pulp.LpMinimize)

    for appliance in model.appliances:
        for hour in range(24):
            if appliance.earliest_hour <= hour <= appliance.latest_hour:
                variables[(appliance.name, hour)] = pulp.LpVariable(
                    f"x_{appliance.name}_{hour}",
                    lowBound=0,
                    upBound=1,
                    cat=pulp.LpBinary,
                )

    peak_demand = pulp.LpVariable("peak_demand", lowBound=0)
    grid_import = {
        hour: pulp.LpVariable(f"grid_import_{hour}", lowBound=0)
        for hour in range(24)
    }

    for appliance in model.appliances:
        allowed_hours = [hour for hour in range(24) if appliance.earliest_hour <= hour <= appliance.latest_hour]
        problem += pulp.lpSum(variables[(appliance.name, hour)] for hour in allowed_hours) == appliance.duration_hours

    for hour in range(24):
        fixed_load = model.fixed_loads[hour]
        solar = model.solar_profile.profile[hour]
        demand_expr = fixed_load + pulp.lpSum(
            appliance.power_kw * variables[(appliance.name, hour)]
            for appliance in model.appliances
            if (appliance.name, hour) in variables
        )
        problem += grid_import[hour] >= demand_expr - solar
        problem += peak_demand >= demand_expr

    discomfort = 0.0
    for appliance in model.appliances:
        for hour in range(24):
            if (appliance.name, hour) not in variables:
                continue
            if hour not in appliance.preferred_set():
                discomfort += appliance.discomfort_weight * variables[(appliance.name, hour)]

    tariff_cost = pulp.lpSum(model.tariff_schedule.tariffs[hour] * grid_import[hour] for hour in range(24))
    objective = alpha * tariff_cost + beta * peak_demand + gamma * discomfort
    problem += objective

    status = problem.solve(pulp.PULP_CBC_CMD(msg=False))
    if pulp.LpStatus[status] != "Optimal":
        raise RuntimeError(f"MILP solve did not reach optimality: {pulp.LpStatus[status]}")

    schedule = {appliance.name: [0 for _ in range(24)] for appliance in model.appliances}
    for appliance in model.appliances:
        for hour in range(24):
            var = variables.get((appliance.name, hour))
            if var is not None:
                schedule[appliance.name][hour] = int(pulp.value(var))

    valid, issues = model.validate_schedule(schedule)
    grid_import_values = [pulp.value(grid_import[hour]) or 0.0 for hour in range(24)]
    demand_values = model.hourly_total_demand(schedule)
    electricity_cost = sum(model.tariff_schedule.tariffs[hour] * grid_import_values[hour] for hour in range(24))
    discomfort_cost = model.discomfort_cost(schedule)
    peak_value = max(demand_values)
    objective_value = model.objective(schedule, alpha=alpha, beta=beta, gamma=gamma)
    runtime = time.perf_counter() - start

    return ClassicalOptimizationResult(
        method="MILP",
        schedule=schedule,
        objective_value=objective_value,
        electricity_cost=electricity_cost,
        peak_demand=peak_value,
        discomfort_cost=discomfort_cost,
        feasible=valid,
        runtime_seconds=runtime,
        details={
            "status": pulp.LpStatus[status],
            "issues": issues,
            "peak_variable": pulp.value(peak_demand) or 0.0,
            "grid_import": grid_import_values,
            "demand": demand_values,
        },
    )
