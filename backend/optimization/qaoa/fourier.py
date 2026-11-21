from __future__ import annotations

import numpy as np

from backend.energy.energy_model import EnergyModel
from backend.optimization.qaoa.standard import StandardQAOAResult, solve_standard_qaoa


def _fourier_interp(base_params: Sequence[float], target_depth: int) -> np.ndarray:
    base = np.asarray(base_params, dtype=float)
    if base.size == 0:
        return np.zeros(2 * target_depth, dtype=float)
    if target_depth <= base.size:
        return np.asarray(base[:target_depth], dtype=float)

    k = np.arange(target_depth, dtype=float)
    x = np.linspace(0.0, 1.0, base.size)
    y = base
    interp = np.interp(k / max(target_depth - 1, 1), x, y)
    return interp


def fourier_parameter_init(low_depth: int, high_depth: int, base_params: Sequence[float]) -> tuple[np.ndarray, np.ndarray]:
    """Generate a Fourier-style warm start from a lower-depth QAOA optimization."""
    gamma = _fourier_interp(np.asarray(base_params[:low_depth], dtype=float), high_depth)
    beta = _fourier_interp(np.asarray(base_params[low_depth:], dtype=float), high_depth)
    return gamma, beta


def solve_fourier_qaoa(
    model: EnergyModel,
    p: int = 3,
    p0: int = 2,
    shots: int = 512,
    maxiter: int = 30,
    seed: int = 456,
    alpha: float = 1.0,
    beta: float = 1.5,
    gamma: float = 0.8,
    appliance_limit: int | None = 3,
    hour_limit: int | None = 12,
) -> StandardQAOAResult:
    """Optimize a shallow QAOA circuit, then transfer its parameters to a deeper depth using a Fourier-style warm start."""
    low_result = solve_standard_qaoa(
        model,
        p=p0,
        shots=max(32, shots // 4),
        maxiter=max(3, min(maxiter, 6)),
        seed=seed,
        alpha=alpha,
        beta=beta,
        gamma=gamma,
        appliance_limit=appliance_limit,
        hour_limit=hour_limit,
    )
    base_params = np.concatenate([
        np.asarray(low_result.parameters["gamma"], dtype=float),
        np.asarray(low_result.parameters["beta"], dtype=float),
    ])
    gamma_init, beta_init = fourier_parameter_init(p0, p, base_params)
    warm_start = np.concatenate([gamma_init, beta_init])
    return solve_standard_qaoa(
        model,
        p=p,
        shots=max(32, shots // 2),
        maxiter=max(3, min(maxiter, 6)),
        seed=seed,
        alpha=alpha,
        beta=beta,
        gamma=gamma,
        appliance_limit=appliance_limit,
        hour_limit=hour_limit,
        initial_params=warm_start,
    )
