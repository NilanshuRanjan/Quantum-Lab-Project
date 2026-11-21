from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, Sequence

from backend.energy.energy_model import EnergyModel
from backend.optimization.classical import ClassicalOptimizationResult
from backend.optimization.classical.annealing import solve_simulated_annealing
from backend.optimization.classical.greedy import solve_greedy
from backend.optimization.classical.milp import solve_milp

try:
    from backend.optimization.qaoa.standard import StandardQAOAResult, solve_standard_qaoa
except Exception:  # pragma: no cover - optional quantum dependency path
    StandardQAOAResult = None  # type: ignore[assignment]
    solve_standard_qaoa = None  # type: ignore[assignment]


@dataclass
class DashboardSummary:
    appliance_count: int
    battery_capacity_kwh: float
    max_grid_kw: float
    solar_peak_kw: float
    average_tariff_per_kwh: float
    default_schedule_valid: bool
    default_objective: float


class OptimizerService:
    """Shared service layer used by both the terminal UI and future API/web clients."""

    @staticmethod
    def default_model() -> EnergyModel:
        return EnergyModel.generate_default_scenario()

    @staticmethod
    def default_schedule(model: EnergyModel | None = None) -> Dict[str, list[int]]:
        active_model = model or OptimizerService.default_model()
        return active_model.generate_feasible_schedule()

    @staticmethod
    def scenario_summary(model: EnergyModel | None = None) -> DashboardSummary:
        active_model = model or OptimizerService.default_model()
        default_schedule = active_model.generate_feasible_schedule()
        valid, _ = active_model.validate_schedule(default_schedule)
        objective = active_model.objective(default_schedule)
        average_tariff = sum(active_model.tariff_schedule.tariffs) / len(active_model.tariff_schedule.tariffs)
        return DashboardSummary(
            appliance_count=len(active_model.appliances),
            battery_capacity_kwh=active_model.battery.capacity_kwh,
            max_grid_kw=active_model.max_grid_kw,
            solar_peak_kw=max(active_model.solar_profile.profile),
            average_tariff_per_kwh=average_tariff,
            default_schedule_valid=valid,
            default_objective=objective,
        )

    @staticmethod
    def run_classical_suite(model: EnergyModel | None = None) -> list[ClassicalOptimizationResult]:
        active_model = model or OptimizerService.default_model()
        return [
            solve_milp(active_model),
            solve_greedy(active_model),
            solve_simulated_annealing(active_model, iterations=2500, seed=7),
        ]

    @staticmethod
    def run_qaoa_preview(model: EnergyModel | None = None) -> StandardQAOAResult | None:
        if solve_standard_qaoa is None:
            return None
        active_model = model or OptimizerService.default_model()
        return solve_standard_qaoa(
            active_model,
            p=2,
            shots=256,
            maxiter=8,
            seed=42,
            appliance_limit=3,
            hour_limit=12,
        )

    @staticmethod
    def queue_rows(items: Iterable[ClassicalOptimizationResult | StandardQAOAResult]) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for result in items:
            rows.append(
                {
                    "method": result.method,
                    "feasible": bool(result.feasible),
                    "objective_value": float(result.objective_value),
                    "electricity_cost": float(result.electricity_cost),
                    "peak_demand": float(result.peak_demand),
                    "runtime_seconds": float(result.runtime_seconds),
                }
            )
        return rows
