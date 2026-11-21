from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence, Tuple


@dataclass(frozen=True)
class Appliance:
    """A dispatchable residential appliance with a fixed duration and time window."""

    name: str
    power_kw: float
    duration_hours: int
    earliest_hour: int
    latest_hour: int
    preferred_hours: Tuple[int, ...] = ()
    discomfort_weight: float = 1.0

    def __post_init__(self) -> None:
        if not 0 <= self.earliest_hour <= self.latest_hour < 24:
            raise ValueError("Appliance time window must be within 0..23.")
        if self.duration_hours <= 0:
            raise ValueError("Appliance duration must be positive.")
        if self.duration_hours > (self.latest_hour - self.earliest_hour + 1):
            raise ValueError("Appliance duration exceeds the allowed time window.")
        if self.power_kw <= 0:
            raise ValueError("Appliance power must be positive.")

    def allowed_hours(self) -> Tuple[int, ...]:
        return tuple(range(self.earliest_hour, self.latest_hour + 1))

    def preferred_set(self) -> set[int]:
        return set(self.preferred_hours)

    def generate_feasible_schedule(self) -> list[int]:
        hours = list(self.allowed_hours())
        if self.preferred_hours:
            preferred = [h for h in self.preferred_hours if h in hours]
        else:
            preferred = []

        selected: list[int] = []
        for hour in preferred:
            if len(selected) >= self.duration_hours:
                break
            if hour not in selected:
                selected.append(hour)

        for hour in hours:
            if len(selected) >= self.duration_hours:
                break
            if hour not in selected:
                selected.append(hour)

        if len(selected) != self.duration_hours:
            raise ValueError(f"Unable to construct a feasible schedule for {self.name}.")

        schedule = [0] * 24
        for hour in selected:
            schedule[hour] = 1
        return schedule

    def validate_schedule(self, schedule: Sequence[int]) -> bool:
        if len(schedule) != 24:
            return False
        active_hours = sum(int(value) for value in schedule)
        if active_hours != self.duration_hours:
            return False
        for hour, value in enumerate(schedule):
            if value == 1 and not (self.earliest_hour <= hour <= self.latest_hour):
                return False
        return True
