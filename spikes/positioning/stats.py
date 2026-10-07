# -*- coding: utf-8 -*-
"""Aggregate ΔS: game-clustered bootstrap CI, Wilcoxon, BH-FDR."""
from __future__ import annotations

from collections import defaultdict
from typing import Any, Sequence

import numpy as np
from scipy import stats


def mean_delta(deltas: Sequence[float]) -> float | None:
    a = np.asarray(deltas, dtype=float)
    a = a[np.isfinite(a)]
    if a.size == 0:
        return None
    return float(np.mean(a))


def summarize_deltas(deltas: Sequence[float]) -> dict[str, Any]:
    a = np.asarray(deltas, dtype=float)
    a = a[np.isfinite(a)]
    n = int(a.size)
    if n == 0:
        return {
            "n": 0,
            "mean": None,
            "median": None,
            "p10": None,
            "p90": None,
            "fracPositive": None,
        }
    return {
        "n": n,
        "mean": float(np.mean(a)),
        "median": float(np.median(a)),
        "p10": float(np.quantile(a, 0.10)),
        "p90": float(np.quantile(a, 0.90)),
        "fracPositive": float(np.mean(a > 0)),
    }


def wilcoxon_vs_zero(deltas: Sequence[float]) -> dict[str, Any]:
    a = np.asarray(deltas, dtype=float)
    a = a[np.isfinite(a)]
    n = int(a.size)
    if n < 3:
        return {"n": n, "stat": None, "pvalue": None}
    # Drop exact zeros (Wilcoxon requirement)
    nz = a[np.abs(a) > 1e-15]
    if nz.size < 3:
        return {"n": n, "stat": None, "pvalue": None, "nNonZero": int(nz.size)}
    try:
        res = stats.wilcoxon(nz, alternative="two-sided", zero_method="wilcox")
        return {
            "n": n,
            "nNonZero": int(nz.size),
            "stat": float(res.statistic),
            "pvalue": float(res.pvalue),
        }
    except ValueError:
        return {"n": n, "nNonZero": int(nz.size), "stat": None, "pvalue": None}


def clustered_bootstrap_mean_ci(
    board_rows: Sequence[dict[str, Any]],
    *,
    delta_key: str = "deltaS",
    game_key: str = "gameId",
    n_boot: int = 2000,
    seed: int = 0,
    alpha: float = 0.05,
) -> dict[str, Any]:
    """Resample games with replacement; within-game keep all boards."""
    by_game: dict[str, list[float]] = defaultdict(list)
    for r in board_rows:
        d = r.get(delta_key)
        if d is None or not np.isfinite(float(d)):
            continue
        by_game[str(r[game_key])].append(float(d))
    games = list(by_game.keys())
    g = len(games)
    point = mean_delta([d for gs in by_game.values() for d in gs])
    if g < 2 or point is None:
        return {"nGames": g, "mean": point, "ci95": None, "n_boot": 0}

    rng = np.random.default_rng(seed)
    means: list[float] = []
    for _ in range(n_boot):
        pick = rng.integers(0, g, size=g)
        sample: list[float] = []
        for i in pick:
            sample.extend(by_game[games[i]])
        if sample:
            means.append(float(np.mean(sample)))
    if len(means) < max(50, n_boot // 10):
        return {"nGames": g, "mean": point, "ci95": None, "n_boot": len(means)}
    lo = float(np.quantile(means, alpha / 2))
    hi = float(np.quantile(means, 1 - alpha / 2))
    return {
        "nGames": g,
        "mean": point,
        "ci95": [lo, hi],
        "n_boot": len(means),
        "significantPositive": lo > 0,
        "significantNegative": hi < 0,
    }


def bh_fdr(pvalues: Sequence[float | None], *, q: float = 0.05) -> list[bool]:
    """Benjamini–Hochberg: return reject flags aligned with input (None → False)."""
    indexed: list[tuple[int, float]] = []
    for i, p in enumerate(pvalues):
        if p is not None and np.isfinite(p):
            indexed.append((i, float(p)))
    out = [False] * len(pvalues)
    m = len(indexed)
    if m == 0:
        return out
    indexed.sort(key=lambda t: t[1])
    # largest i with p_(i) <= (i/m)*q
    max_k = -1
    for k, (_i, p) in enumerate(indexed, start=1):
        if p <= (k / m) * q:
            max_k = k
    for k in range(max_k):
        out[indexed[k][0]] = True
    return out


def cell_report(board_rows: Sequence[dict[str, Any]], *, n_boot: int = 2000, seed: int = 0) -> dict[str, Any]:
    deltas = [float(r["deltaS"]) for r in board_rows if r.get("deltaS") is not None]
    summ = summarize_deltas(deltas)
    boot = clustered_bootstrap_mean_ci(board_rows, n_boot=n_boot, seed=seed)
    wil = wilcoxon_vs_zero(deltas)
    return {
        **summ,
        "bootstrap": boot,
        "wilcoxon": wil,
        "ciLowerPositive": bool(boot.get("significantPositive")),
    }
