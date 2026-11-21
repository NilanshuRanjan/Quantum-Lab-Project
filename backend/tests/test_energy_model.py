import unittest

from backend.energy.energy_model import EnergyModel


class TestEnergyModel(unittest.TestCase):
    def setUp(self) -> None:
        self.model = EnergyModel.generate_default_scenario()

    def test_default_scenario_has_24_hours(self) -> None:
        self.assertEqual(len(self.model.fixed_loads), 24)
        self.assertEqual(len(self.model.solar_profile.profile), 24)
        self.assertEqual(len(self.model.tariff_schedule.tariffs), 24)

    def test_generate_feasible_schedule_is_valid(self) -> None:
        schedule = self.model.generate_feasible_schedule()
        valid, issues = self.model.validate_schedule(schedule)
        self.assertTrue(valid, msg="; ".join(issues))

    def test_objective_is_lower_for_better_schedule(self) -> None:
        good = self.model.generate_feasible_schedule()
        bad = {name: [0] * 24 for name in [a.name for a in self.model.appliances]}
        for appliance in self.model.appliances:
            hours = appliance.allowed_hours()[: appliance.duration_hours]
            for hour in hours:
                bad[appliance.name][hour] = 1

        good_obj = self.model.objective(good)
        bad_obj = self.model.objective(bad)
        self.assertLess(good_obj, bad_obj)

    def test_appliance_validation_detects_invalid_window(self) -> None:
        schedule = self.model.generate_feasible_schedule()
        schedule["water_heater"][0] = 1
        valid, issues = self.model.validate_schedule(schedule)
        self.assertFalse(valid)
        self.assertTrue(any("water_heater" in issue for issue in issues))


if __name__ == "__main__":
    unittest.main()
