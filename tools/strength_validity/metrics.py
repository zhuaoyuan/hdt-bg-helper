# -*- coding: utf-8 -*-
"""Spearman / bootstrap CI / permutation / partial Spearman."""
from __future__ import annotations

from typing import Any, Sequence

import numpy as np
from scipy import stats


def _as_float_arrays(
    x: Sequence[float], y: Sequence[float]
) -> tuple[np.ndarray, np.ndarray]:
    xa = np.asarray(x, dtype=float)
    ya = np.asarray(y, dtype=float)
    mask = np.isfinite(xa) & np.isfinite(ya)
    return xa[mask], ya[mask]


def spearman(x: Sequence[float], y: Sequence[float]) -> dict[str, Any]:
    xa, ya = _as_float_arrays(x, y)
    n = int(xa.size)
    if n < 3:
        return {"n": n, "rho": None, "pvalue": None}
    if np.std(xa) < 1e-15 or np.std(ya) < 1e-15:
        return {"n": n, "rho": None, "pvalue": None}
    rho, p = stats.spearmanr(xa, ya)
    if not np.isfinite(rho):
        return {"n": n, "rho": None, "pvalue": None}
    return {"n": n, "rho": float(rho), "pvalue": float(p)}


def bootstrap_spearman_ci(
    x: Sequence[float],
    y: Sequence[float],
    *,
    n_boot: int = 5000,
    seed: int = 0,
    alpha: float = 0.05,
) -> dict[str, Any]:
    xa, ya = _as_float_arrays(x, y)
    n = int(xa.size)
    point = spearman(xa, ya)
    if n < 3 or point["rho"] is None:
        return {**point, "ci95": None, "n_boot": 0}
    rng = np.random.default_rng(seed)
    rhos: list[float] = []
    for _ in range(n_boot):
        idx = rng.integers(0, n, size=n)
        r = spearman(xa[idx], ya[idx])["rho"]
        if r is not None:
            rhos.append(r)
    if len(rhos) < max(100, n_boot // 10):
        return {**point, "ci95": None, "n_boot": len(rhos)}
    lo = float(np.quantile(rhos, alpha / 2))
    hi = float(np.quantile(rhos, 1 - alpha / 2))
    return {**point, "ci95": [lo, hi], "n_boot": len(rhos)}


def permutation_spearman_p(
    x: Sequence[float],
    y: Sequence[float],
    *,
    n_perm: int = 5000,
    seed: int = 1,
) -> dict[str, Any]:
    xa, ya = _as_float_arrays(x, y)
    n = int(xa.size)
    point = spearman(xa, ya)
    if n < 3 or point["rho"] is None:
        return {**point, "perm_p": None, "n_perm": 0}
    rng = np.random.default_rng(seed)
    obs = abs(float(point["rho"]))
    extreme = 0
    for _ in range(n_perm):
        yp = rng.permutation(ya)
        r = spearman(xa, yp)["rho"]
        if r is not None and abs(r) >= obs - 1e-15:
            extreme += 1
    # add-one smoothing
    p = (extreme + 1) / (n_perm + 1)
    return {**point, "perm_p": float(p), "n_perm": n_perm}


def associate(
    x: Sequence[float],
    y: Sequence[float],
    *,
    n_boot: int = 5000,
    n_perm: int = 5000,
    seed: int = 0,
) -> dict[str, Any]:
    """Full association package: rho + bootstrap CI + permutation p."""
    boot = bootstrap_spearman_ci(x, y, n_boot=n_boot, seed=seed)
    perm = permutation_spearman_p(x, y, n_perm=n_perm, seed=seed + 1)
    ci = boot.get("ci95")
    rho = boot.get("rho")
    perm_p = perm.get("perm_p")
    significant = False
    if rho is not None and ci is not None and perm_p is not None:
        significant = (ci[0] > 0 or ci[1] < 0) and perm_p < 0.05
    return {
        "n": boot.get("n"),
        "rho": rho,
        "scipy_p": boot.get("pvalue"),
        "ci95": ci,
        "perm_p": perm_p,
        "significant": significant,
        "n_boot": boot.get("n_boot"),
        "n_perm": perm.get("n_perm"),
    }


def rankdata(a: np.ndarray) -> np.ndarray:
    return stats.rankdata(a, method="average")


def partial_spearman(
    x: Sequence[float],
    y: Sequence[float],
    z: Sequence[float],
    *,
    n_boot: int = 5000,
    n_perm: int = 5000,
    seed: int = 2,
) -> dict[str, Any]:
    """Spearman(x,y | z) via residual ranks after linear regression on ranks of z."""
    xa, ya = _as_float_arrays(x, y)
    za = np.asarray(z, dtype=float)
    # realign z with the same finite mask as x,y — recompute jointly
    xa = np.asarray(x, dtype=float)
    ya = np.asarray(y, dtype=float)
    za = np.asarray(z, dtype=float)
    mask = np.isfinite(xa) & np.isfinite(ya) & np.isfinite(za)
    xa, ya, za = xa[mask], ya[mask], za[mask]
    n = int(xa.size)
    if n < 4:
        return {"n": n, "rho": None, "ci95": None, "perm_p": None, "significant": False}

    def residual_corr(xx: np.ndarray, yy: np.ndarray, zz: np.ndarray) -> float | None:
        rx, ry, rz = rankdata(xx), rankdata(yy), rankdata(zz)
        # residualize against rz (with intercept)
        A = np.column_stack([np.ones(len(rz)), rz])
        bx, *_ = np.linalg.lstsq(A, rx, rcond=None)
        by, *_ = np.linalg.lstsq(A, ry, rcond=None)
        ex = rx - A @ bx
        ey = ry - A @ by
        if np.std(ex) < 1e-12 or np.std(ey) < 1e-12:
            return None
        r = spearman(ex, ey)["rho"]
        return r

    rho0 = residual_corr(xa, ya, za)
    if rho0 is None:
        return {"n": n, "rho": None, "ci95": None, "perm_p": None, "significant": False}

    rng = np.random.default_rng(seed)
    rhos: list[float] = []
    for _ in range(n_boot):
        idx = rng.integers(0, n, size=n)
        r = residual_corr(xa[idx], ya[idx], za[idx])
        if r is not None:
            rhos.append(r)
    ci = None
    if len(rhos) >= max(100, n_boot // 10):
        ci = [float(np.quantile(rhos, 0.025)), float(np.quantile(rhos, 0.975))]

    extreme = 0
    for _ in range(n_perm):
        yp = rng.permutation(ya)
        r = residual_corr(xa, yp, za)
        if r is not None and abs(r) >= abs(rho0) - 1e-15:
            extreme += 1
    perm_p = (extreme + 1) / (n_perm + 1)
    significant = False
    if ci is not None:
        significant = (ci[0] > 0 or ci[1] < 0) and perm_p < 0.05
    return {
        "n": n,
        "rho": float(rho0),
        "ci95": ci,
        "perm_p": float(perm_p),
        "significant": significant,
        "n_boot": len(rhos),
        "n_perm": n_perm,
    }


def leave_one_out_rhos(x: Sequence[float], y: Sequence[float]) -> list[float | None]:
    xa, ya = _as_float_arrays(x, y)
    n = int(xa.size)
    out: list[float | None] = []
    if n < 4:
        return out
    for i in range(n):
        mask = np.ones(n, dtype=bool)
        mask[i] = False
        out.append(spearman(xa[mask], ya[mask])["rho"])
    return out
