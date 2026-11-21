from __future__ import annotations

from dataclasses import dataclass, field
from statistics import mean
from typing import Any, Iterable, Sequence

from backend.app.services.optimizer_service import OptimizerService
from backend.energy.energy_model import EnergyModel
from backend.optimization.classical.annealing import solve_simulated_annealing
from backend.optimization.classical.greedy import solve_greedy
from backend.optimization.classical.milp import solve_milp

try:
    from backend.optimization.qaoa.standard import solve_standard_qaoa
except Exception:  # pragma: no cover - optional quantum dependency path
    solve_standard_qaoa = None  # type: ignore[assignment]


@dataclass
class BenchmarkEntry:
    method: str
    samples: int
    feasible_rate: float
    objective_mean: float
    objective_best: float
    runtime_mean: float
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "method": self.method,
            "samples": self.samples,
            "feasible_rate": self.feasible_rate,
            "objective_mean": self.objective_mean,
            "objective_best": self.objective_best,
            "runtime_mean": self.runtime_mean,
            "details": self.details,
        }


class ComparisonService:
    """Benchmark suite comparing classical baselines to the compact QAOA preview."""

    @staticmethod
    def run_benchmark(
        model: EnergyModel | None = None,
        seeds: Sequence[int] = (0, 7, 42),
        include_qaoa: bool = True,
    ) -> list[BenchmarkEntry]:
        active_model = model or OptimizerService.default_model()
        entries: list[BenchmarkEntry] = []

        for method_name, runner in (
            ("MILP", lambda seed: solve_milp(active_model)),
            ("Greedy", lambda seed: solve_greedy(active_model)),
            ("SimulatedAnnealing", lambda seed: solve_simulated_annealing(active_model, iterations=2500, seed=seed)),
        ):
            results = [runner(seed) for seed in seeds[:3]]
            feasible = [1 if result.feasible else 0 for result in results]
            objectives = [float(result.objective_value) for result in results]
            runtimes = [float(result.runtime_seconds) for result in results]
            entries.append(
                BenchmarkEntry(
                    method=method_name,
                    samples=len(results),
                    feasible_rate=sum(feasible) / max(len(feasible), 1),
                    objective_mean=sum(objectives) / max(len(objectives), 1),
                    objective_best=min(objectives) if objectives else float("inf"),
                    runtime_mean=sum(runtimes) / max(len(runtimes), 1),
                    details={
                        "objective_values": objectives,
                        "runtime_seconds": runtimes,
                        "feasible": feasible,
                    },
                )
            )

        if include_qaoa and solve_standard_qaoa is not None:
            qaoa_results = [
                solve_standard_qaoa(
                    active_model,
                    p=2,
                    shots=256,
                    maxiter=8,
                    seed=seed,
                    appliance_limit=3,
                    hour_limit=12,
                )
                for seed in seeds[:3]
            ]
            feasible = [1 if result.feasible else 0 for result in qaoa_results]
            objectives = [float(result.objective_value) for result in qaoa_results]
            runtimes = [float(result.runtime_seconds) for result in qaoa_results]
            entries.append(
                BenchmarkEntry(
                    method="StandardQAOA",
                    samples=len(qaoa_results),
                    feasible_rate=sum(feasible) / max(len(feasible), 1),
                    objective_mean=sum(objectives) / max(len(objectives), 1),
                    objective_best=min(objectives) if objectives else float("inf"),
                    runtime_mean=sum(runtimes) / max(len(runtimes), 1),
                    details={
                        "objective_values": objectives,
                        "runtime_seconds": runtimes,
                        "feasible": feasible,
                        "qubits": [getattr(result, "qubits", None) for result in qaoa_results],
                    },
                )
            )

        return entries
