from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Battery:
    """A simple battery model for the microgrid energy balance."""

    capacity_kwh: float
    max_charge_kw: float
    max_discharge_kw: float
    initial_soc_kwh: float = 0.0
    efficiency: float = 0.92
    soc_kwh: float = field(init=False)

    def __post_init__(self) -> None:
        if self.capacity_kwh <= 0:
            raise ValueError("Battery capacity must be positive.")
        if self.max_charge_kw <= 0 or self.max_discharge_kw <= 0:
            raise ValueError("Battery charge/discharge limits must be positive.")
        self.soc_kwh = max(0.0, min(self.capacity_kwh, self.initial_soc_kwh))

    def state_of_charge_fraction(self) -> float:
        return self.soc_kwh / self.capacity_kwh

    def charge(self, power_kw: float) -> float:
        charge_allowed = min(power_kw, self.max_charge_kw, self.capacity_kwh - self.soc_kwh)
        self.soc_kwh += charge_allowed * self.efficiency
        return charge_allowed

    def discharge(self, power_kw: float) -> float:
        discharge_allowed = min(power_kw, self.max_discharge_kw, self.soc_kwh)
        self.soc_kwh -= discharge_allowed
        return discharge_allowed

    def reset(self) -> None:
        self.soc_kwh = max(0.0, min(self.capacity_kwh, self.initial_soc_kwh))
