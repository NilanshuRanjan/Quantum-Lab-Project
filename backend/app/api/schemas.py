from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class OptimizationRequest(BaseModel):
    method: Literal["all", "milp", "greedy", "annealing", "qaoa"] = "all"
    iterations: int = Field(default=2500, ge=10, le=20000)
    shots: int = Field(default=256, ge=32, le=4096)
    seed: int = Field(default=7, ge=0, le=10_000)
    p: int = Field(default=2, ge=1, le=6)
    appliance_limit: int | None = Field(default=3, ge=1, le=6)
    hour_limit: int | None = Field(default=12, ge=1, le=24)


class ScheduleValidationResponse(BaseModel):
    valid: bool
    issues: list[str]
    schedule: dict[str, list[int]]
