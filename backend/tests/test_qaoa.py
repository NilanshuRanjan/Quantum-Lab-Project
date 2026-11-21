import unittest

from backend.energy.appliances import Appliance
from backend.energy.battery import Battery
from backend.energy.energy_model import EnergyModel
from backend.energy.solar import SolarProfile
from backend.energy.tariff import TariffSchedule
from backend.optimization.qaoa.standard import solve_standard_qaoa


class TestStandardQAOA(unittest.TestCase):
    def test_standard_qaoa_returns_feasible_schedule(self) -> None:
        appliances = [
            Appliance("heater", 1.5, 1, 0, 5, preferred_hours=(1, 2), discomfort_weight=1.0),
            Appliance("washer", 1.2, 1, 1, 6, preferred_hours=(2, 3), discomfort_weight=1.0),
            Appliance("dryer", 2.0, 1, 4, 7, preferred_hours=(5, 6), discomfort_weight=1.0),
        ]
        model = EnergyModel(
            appliances=appliances,
            solar_profile=SolarProfile((0.0,) * 24),
            tariff_schedule=TariffSchedule((0.20,) * 24),
            battery=Battery(capacity_kwh=5.0, max_charge_kw=2.0, max_discharge_kw=2.0, initial_soc_kwh=2.5),
            fixed_loads=(0.3,) * 24,
            max_grid_kw=5.0,
        )

        result = solve_standard_qaoa(model, p=1, shots=256, maxiter=8, appliance_limit=3, hour_limit=8)
        self.assertTrue(result.feasible)
        self.assertGreater(result.qubits, 0)
        self.assertTrue(result.schedule["heater"])  # at least one hour assigned by the reduced schedule


if __name__ == "__main__":
    unittest.main()
