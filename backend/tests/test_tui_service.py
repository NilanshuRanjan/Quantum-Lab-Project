import unittest

from backend.app.services.optimizer_service import OptimizerService


class TestOptimizerService(unittest.TestCase):
    def test_default_summary_is_coherent(self) -> None:
        summary = OptimizerService.scenario_summary()
        self.assertEqual(summary.appliance_count, 6)
        self.assertGreater(summary.battery_capacity_kwh, 0.0)
        self.assertGreater(summary.max_grid_kw, 0.0)
        self.assertTrue(summary.default_schedule_valid)

    def test_classical_suite_returns_feasible_results(self) -> None:
        results = OptimizerService.run_classical_suite()
        self.assertEqual(len(results), 3)
        self.assertTrue(all(result.feasible for result in results))
        self.assertIn("MILP", {result.method for result in results})


if __name__ == "__main__":
    unittest.main()
