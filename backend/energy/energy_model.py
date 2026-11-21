from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Sequence

from backend.energy.appliances import Appliance
from backend.energy.battery import Battery
from backend.energy.solar import SolarProfile
from backend.energy.tariff import TariffSchedule


@dataclass
class EnergyModel:
    appliances: list[Appliance]
    solar_profile: SolarProfile
    tariff_schedule: TariffSchedule
    battery: Battery
    fixed_loads: tuple[float, ...] = (0.6,) * 24
    max_grid_kw: float = 10.0
    peak_penalty_weight: float = 1.5
    discomfort_weight: float = 0.75

    def __post_init__(self) -> None:
        if len(self.fixed_loads) != 24:
            raise ValueError("Fixed loads must include exactly 24 hourly values.")

    @classmethod
    def generate_default_scenario(cls) -> "EnergyModel":
        appliances = [
            Appliance("washing_machine", 1.7, 2, 8, 18, preferred_hours=(10, 11, 12, 13), discomfort_weight=1.2),
            Appliance("dishwasher", 1.4, 3, 11, 20, preferred_hours=(13, 14, 15), discomfort_weight=1.1),
            Appliance("dryer", 2.2, 2, 12, 21, preferred_hours=(16, 17, 18), discomfort_weight=1.3),
            Appliance("water_heater", 1.8, 3, 0, 7, preferred_hours=(2, 3, 4), discomfort_weight=1.0),
            Appliance("ev_charger", 3.3, 2, 20, 23, preferred_hours=(21, 22, 23), discomfort_weight=1.5),
            Appliance("heat_pump", 1.2, 4, 5, 12, preferred_hours=(6, 7, 8), discomfort_weight=0.9),
        ]
        return cls(
            appliances=appliances,
            solar_profile=SolarProfile.default_profile(),
            tariff_schedule=TariffSchedule.default_tariff_schedule(),
            battery=Battery(capacity_kwh=12.0, max_charge_kw=4.0, max_discharge_kw=4.0, initial_soc_kwh=5.0),
            fixed_loads=(0.5, 0.5, 0.5, 0.5, 0.6, 0.7, 0.8, 0.8, 0.9, 1.0, 1.1, 1.2, 1.1, 1.0, 0.9, 0.9, 0.9, 1.0, 1.3, 1.5, 1.4, 1.2, 1.0, 0.8),
            max_grid_kw=10.0,
        )

    def hourly_total_demand(self, schedule: Dict[str, Sequence[int]]) -> list[float]:
        hourly = [0.0 for _ in range(24)]
        for appliance in self.appliances:
            appliance_schedule = schedule.get(appliance.name, [0] * 24)
            for hour, value in enumerate(appliance_schedule):
                hourly[hour] += appliance.power_kw * int(value)
        for hour, fixed_load in enumerate(self.fixed_loads):
            hourly[hour] += fixed_load
        return hourly

    def grid_import_and_battery(self, schedule: Dict[str, Sequence[int]]) -> tuple[list[float], float]:
        demand = self.hourly_total_demand(schedule)
        solar = list(self.solar_profile.profile)
        battery = Battery(
            capacity_kwh=self.battery.capacity_kwh,
            max_charge_kw=self.battery.max_charge_kw,
            max_discharge_kw=self.battery.max_discharge_kw,
            initial_soc_kwh=self.battery.initial_soc_kwh,
            efficiency=self.battery.efficiency,
        )

        hourly_grid = [0.0 for _ in range(24)]
        for hour in range(24):
            net_load = demand[hour] - solar[hour]
            if net_load <= 0:
                charge = min(-net_load, battery.max_charge_kw, battery.capacity_kwh - battery.soc_kwh)
                battery.soc_kwh += charge * battery.efficiency
            else:
                discharge = min(net_load, battery.max_discharge_kw, battery.soc_kwh)
                battery.soc_kwh -= discharge
                net_load -= discharge
                hourly_grid[hour] = max(0.0, net_load)
        return hourly_grid, battery.soc_kwh

    def validate_schedule(self, schedule: Dict[str, Sequence[int]]) -> tuple[bool, list[str]]:
        issues: list[str] = []
        for appliance in self.appliances:
            appliance_schedule = schedule.get(appliance.name, [0] * 24)
            if not appliance.validate_schedule(appliance_schedule):
                issues.append(f"{appliance.name} violates duration/window constraints.")
        if not issues:
            hourly_demand = self.hourly_total_demand(schedule)
            grid_import, _ = self.grid_import_and_battery(schedule)
            for hour, import_value in enumerate(grid_import):
                if import_value > self.max_grid_kw + 1e-9:
                    issues.append(f"Grid import exceeds limit at hour {hour}: {import_value:.2f} kW.")
            peak = max(hourly_demand)
            if peak > self.max_grid_kw + self.battery.max_discharge_kw + 1e-9:
                issues.append(f"Peak demand exceeds feasible dispatch envelope: {peak:.2f} kW.")
        return (len(issues) == 0), issues

    def discomfort_cost(self, schedule: Dict[str, Sequence[int]]) -> float:
        total = 0.0
        for appliance in self.appliances:
            appliance_schedule = schedule.get(appliance.name, [0] * 24)
            for hour, active in enumerate(appliance_schedule):
                if active:
                    if hour not in appliance.preferred_set():
                        total += appliance.discomfort_weight * 1.5
        return total

    def objective(self, schedule: Dict[str, Sequence[int]], alpha: float = 1.0, beta: float = 1.5, gamma: float = 0.8) -> float:
        grid_import, _ = self.grid_import_and_battery(schedule)
        tariff_cost = sum(self.tariff_schedule.tariffs[hour] * grid_import[hour] for hour in range(24))
        demand = self.hourly_total_demand(schedule)
        peak_penalty = max(0.0, max(demand) - self.max_grid_kw) ** 2
        discomfort = self.discomfort_cost(schedule)
        return alpha * tariff_cost + beta * peak_penalty * self.peak_penalty_weight + gamma * discomfort * self.discomfort_weight

    def generate_feasible_schedule(self) -> Dict[str, list[int]]:
        schedule: Dict[str, list[int]] = {}
        for appliance in self.appliances:
            schedule[appliance.name] = appliance.generate_feasible_schedule()
        return schedule

    def describe_schedule(self, schedule: Dict[str, Sequence[int]]) -> str:
        lines: list[str] = []
        for appliance in self.appliances:
            values = list(schedule.get(appliance.name, [0] * 24))
            active_hours = [hour for hour, value in enumerate(values) if value]
            lines.append(f"{appliance.name}: {active_hours}")
        return "\n".join(lines)
