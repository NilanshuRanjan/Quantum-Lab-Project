import unittest

from backend.app.services.comparison_service import ComparisonService


class TestComparisonService(unittest.TestCase):
    def test_benchmark_produces_summary_rows(self) -> None:
        results = ComparisonService.run_benchmark(seeds=(0, 7), include_qaoa=True)
        self.assertGreaterEqual(len(results), 3)
        self.assertTrue(all(item.samples > 0 for item in results))
        self.assertTrue(all(item.feasible_rate >= 0.0 for item in results))
        self.assertTrue(all(item.objective_mean >= 0.0 for item in results))

    def test_benchmark_without_qaoa_still_outputs_classical_rows(self) -> None:
        results = ComparisonService.run_benchmark(seeds=(0,), include_qaoa=False)
        self.assertEqual(len(results), 3)
        self.assertSetEqual({item.method for item in results}, {"MILP", "Greedy", "SimulatedAnnealing"})


if __name__ == "__main__":
    unittest.main()
