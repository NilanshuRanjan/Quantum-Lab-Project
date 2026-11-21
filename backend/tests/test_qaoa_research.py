import unittest

from backend.energy.appliances import Appliance
from backend.energy.battery import Battery
from backend.energy.energy_model import EnergyModel
from backend.energy.solar import SolarProfile
from backend.energy.tariff import TariffSchedule
from backend.optimization.qaoa.enhanced import solve_enhanced_qaoa
from backend.optimization.qaoa.fourier import solve_fourier_qaoa
from backend.optimization.qaoa.mixers import solve_constraint_aware_qaoa


class TestResearchQAOA(unittest.TestCase):
    def setUp(self) -> None:
        self.model = EnergyModel(
            appliances=[
                Appliance("heater", 1.5, 1, 0, 3, preferred_hours=(1, 2), discomfort_weight=1.0),
                Appliance("washer", 1.2, 1, 1, 4, preferred_hours=(2, 3), discomfort_weight=1.0),
                Appliance("dryer", 2.0, 1, 2, 5, preferred_hours=(3, 4), discomfort_weight=1.0),
            ],
            solar_profile=SolarProfile((0.0,) * 24),
            tariff_schedule=TariffSchedule((0.20,) * 24),
            battery=Battery(capacity_kwh=5.0, max_charge_kw=2.0, max_discharge_kw=2.0, initial_soc_kwh=2.5),
            fixed_loads=(0.3,) * 24,
            max_grid_kw=5.0,
        )

    def test_constraint_aware_qaoa(self) -> None:
        result = solve_constraint_aware_qaoa(self.model, p=1, shots=32, maxiter=2, appliance_limit=3, hour_limit=6)
        self.assertTrue(result.feasible, msg=result.details.get("counts"))

    def test_fourier_initialized_qaoa(self) -> None:
        result = solve_fourier_qaoa(self.model, p=1, p0=1, shots=32, maxiter=2, appliance_limit=3, hour_limit=6)
        self.assertTrue(result.feasible, msg=result)

    def test_enhanced_qaoa(self) -> None:
        result = solve_enhanced_qaoa(self.model, p=1, shots=32, maxiter=2, appliance_limit=3, hour_limit=6)
        self.assertTrue(result.feasible, msg=result.details.get("refinement_issues"))


if __name__ == "__main__":
    unittest.main()
