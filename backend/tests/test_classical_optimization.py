import unittest

from backend.energy.energy_model import EnergyModel
from backend.optimization.classical.annealing import solve_simulated_annealing
from backend.optimization.classical.greedy import solve_greedy
from backend.optimization.classical.milp import solve_milp


class TestClassicalOptimization(unittest.TestCase):
    def setUp(self) -> None:
        self.model = EnergyModel.generate_default_scenario()

    def test_milp_returns_feasible_schedule(self) -> None:
        result = solve_milp(self.model)
        self.assertTrue(result.feasible, msg=result.details.get("issues"))
        self.assertIn("washing_machine", result.schedule)

    def test_greedy_returns_feasible_schedule(self) -> None:
        result = solve_greedy(self.model)
        self.assertTrue(result.feasible, msg=result.details.get("issues"))

    def test_annealing_returns_feasible_schedule(self) -> None:
        result = solve_simulated_annealing(self.model, iterations=1000, seed=7)
        self.assertTrue(result.feasible, msg=result.details.get("issues"))


if __name__ == "__main__":
    unittest.main()
