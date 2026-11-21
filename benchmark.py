from __future__ import annotations

from backend.app.services.comparison_service import ComparisonService


if __name__ == "__main__":
    entries = ComparisonService.run_benchmark()
    print("SmartGrid-QAOA benchmark summary")
    print("=" * 80)
    for item in entries:
        print(
            f"{item.method:20} | samples={item.samples:>2} | feasible={item.feasible_rate:.2f} | "
            f"objective_mean={item.objective_mean:.2f} | objective_best={item.objective_best:.2f} | "
            f"runtime_mean={item.runtime_mean:.4f}s"
        )
