from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict


@dataclass
class ClassicalOptimizationResult:
    """Common result structure for all classical optimization baselines."""

    method: str
    schedule: Dict[str, list[int]]
    objective_value: float
    electricity_cost: float
    peak_demand: float
    discomfort_cost: float
    feasible: bool
    runtime_seconds: float
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
            "details": self.details,
        }
