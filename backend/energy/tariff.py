from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence


@dataclass(frozen=True)
class TariffSchedule:
    """Hourly time-of-use electricity tariff in currency per kWh."""

    tariffs: tuple[float, ...]

    def __post_init__(self) -> None:
        if len(self.tariffs) != 24:
            raise ValueError("Tariff schedule must include exactly 24 hourly values.")

    @classmethod
    def default_tariff_schedule(cls) -> "TariffSchedule":
        # Typical residential TOU profile: evening and early morning demand is more expensive.
        values = [
            0.18, 0.17, 0.16, 0.15, 0.15, 0.16,
            0.17, 0.18, 0.19, 0.20, 0.21, 0.22,
            0.23, 0.23, 0.22, 0.21, 0.20, 0.21,
            0.23, 0.25, 0.26, 0.24, 0.22, 0.20,
        ]
        return cls(tuple(values))
