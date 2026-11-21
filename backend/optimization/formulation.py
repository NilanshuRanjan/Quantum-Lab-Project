from __future__ import annotations

"""Placeholder optimization formulation module for the shared backend architecture.

The full QUBO and QAOA formulations are intentionally deferred until Phase 3.
This file provides the skeleton for the optimization layer used by later phases.
"""

from dataclasses import dataclass


@dataclass
class EnergyFormulation:
    """Skeleton for the discrete optimization problem that will later be encoded as QUBO."""

    n_appliances: int
    horizon_hours: int = 24

    def describe(self) -> str:
        return f"Energy formulation for {self.n_appliances} appliances over {self.horizon_hours} hours."
