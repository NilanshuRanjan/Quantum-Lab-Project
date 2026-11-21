from __future__ import annotations

from fastapi import APIRouter, HTTPException

from backend.app.api.schemas import OptimizationRequest
from backend.app.services.comparison_service import ComparisonService
from backend.app.services.optimizer_service import OptimizerService
from backend.energy.energy_model import EnergyModel
from backend.optimization.classical.annealing import solve_simulated_annealing
from backend.optimization.classical.greedy import solve_greedy
from backend.optimization.classical.milp import solve_milp

try:
    from backend.optimization.qaoa.standard import solve_standard_qaoa
except Exception:  # pragma: no cover - optional quantum dependency path
    solve_standard_qaoa = None  # type: ignore[assignment]

router = APIRouter(prefix="/api")


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/summary")
def summarize() -> dict[str, object]:
    summary = OptimizerService.scenario_summary()
    return {
        "appliance_count": summary.appliance_count,
        "battery_capacity_kwh": summary.battery_capacity_kwh,
        "max_grid_kw": summary.max_grid_kw,
        "solar_peak_kw": summary.solar_peak_kw,
        "average_tariff_per_kwh": summary.average_tariff_per_kwh,
        "default_schedule_valid": summary.default_schedule_valid,
        "default_objective": summary.default_objective,
    }


@router.get("/default-schedule")
def default_schedule() -> dict[str, object]:
    model = OptimizerService.default_model()
    schedule = model.generate_feasible_schedule()
    valid, issues = model.validate_schedule(schedule)
    return {
        "valid": valid,
        "issues": issues,
        "schedule": schedule,
        "objective": model.objective(schedule),
    }


@router.post("/optimize")
def optimize(request: OptimizationRequest | None = None) -> dict[str, object]:
    request = request or OptimizationRequest()
    model = OptimizerService.default_model()

    if request.method == "milp":
        result = solve_milp(model)
        return {"results": [result.to_dict()]}
    if request.method == "greedy":
        result = solve_greedy(model)
        return {"results": [result.to_dict()]}
    if request.method == "annealing":
        result = solve_simulated_annealing(model, iterations=request.iterations, seed=request.seed)
        return {"results": [result.to_dict()]}
    if request.method == "qaoa":
        if solve_standard_qaoa is None:
            raise HTTPException(status_code=503, detail="QAOA backend is unavailable in this environment.")
        result = solve_standard_qaoa(
            model,
            p=request.p,
            shots=request.shots,
            maxiter=8,
            seed=request.seed,
            appliance_limit=request.appliance_limit,
            hour_limit=request.hour_limit,
        )
        return {"results": [result.to_dict()]}

    results = [
        solve_milp(model),
        solve_greedy(model),
        solve_simulated_annealing(model, iterations=request.iterations, seed=request.seed),
    ]
    return {"results": [result.to_dict() for result in results]}


@router.post("/benchmark")
def benchmark() -> dict[str, object]:
    entries = ComparisonService.run_benchmark()
    return {"benchmarks": [entry.to_dict() for entry in entries]}


@router.post("/validate")
def validate_schedule(schedule: dict[str, list[int]]) -> dict[str, object]:
    model = EnergyModel.generate_default_scenario()
    valid, issues = model.validate_schedule(schedule)
    return {"valid": valid, "issues": issues, "schedule": schedule}
