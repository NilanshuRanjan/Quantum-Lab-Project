from __future__ import annotations

from backend.energy.energy_model import EnergyModel


if __name__ == "__main__":
    model = EnergyModel.generate_default_scenario()
    schedule = model.generate_feasible_schedule()
    valid, issues = model.validate_schedule(schedule)

    print("SmartGrid-QAOA Phase 1 Demo")
    print("=" * 32)
    print(f"Feasible schedule: {valid}")
    if issues:
        print("Issues:")
        for issue in issues:
            print(f"- {issue}")

    total_demand = model.hourly_total_demand(schedule)
    grid_import, final_soc = model.grid_import_and_battery(schedule)
    print("\nHourly demand (kW):")
    print([round(value, 2) for value in total_demand])
    print("\nGrid import (kW):")
    print([round(value, 2) for value in grid_import])
    print(f"\nFinal battery SOC: {final_soc:.2f} kWh")
    print(f"Objective value: {model.objective(schedule):.4f}")
    print("\nAppliance schedules:")
    print(model.describe_schedule(schedule))
