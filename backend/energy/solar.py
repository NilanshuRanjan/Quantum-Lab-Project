from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SolarProfile:
    """Hourly solar generation profile in kW over a 24-hour day."""

    profile: tuple[float, ...]

    def __post_init__(self) -> None:
        if len(self.profile) != 24:
            raise ValueError("Solar profile must include exactly 24 hourly values.")

    @classmethod
    def default_profile(cls) -> "SolarProfile":
        values = [
            0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
            0.05, 0.10, 0.22, 0.45, 0.70, 0.95,
            1.20, 1.35, 1.45, 1.30, 1.00, 0.72,
            0.42, 0.18, 0.06, 0.0, 0.0, 0.0,
        ]
        return cls(tuple(values))
