# -*- coding: utf-8 -*-
"""Feature extraction for positioning permutations (enumerate spike)."""
from __future__ import annotations

from typing import Any

from .reorder import (
    card_id,
    is_cleave,
    is_reborn_or_dr,
    is_taunt,
    max_attack,
    max_health,
)


def _spearman_vs_rank(order_values: list[float]) -> float | None:
    """Spearman correlation between position index and value (higher value → prefer left = low index).

    We correlate position i with (-value) so that 'stronger left' → positive rho.
    """
    n = len(order_values)
    if n < 2:
        return None
    # ranks of -value (descending strength → low rank number)
    indexed = sorted(range(n), key=lambda i: (-order_values[i], i))
    strength_rank = [0] * n
    for r, i in enumerate(indexed):
        strength_rank[i] = r
    # position rank is just 0..n-1
    pos_rank = list(range(n))
    return _pearson(pos_rank, strength_rank)


def _pearson(xs: list[float], ys: list[float]) -> float | None:
    n = len(xs)
    if n < 2:
        return None
    mx = sum(xs) / n
    my = sum(ys) / n
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    dx = sum((x - mx) ** 2 for x in xs) ** 0.5
    dy = sum((y - my) ** 2 for y in ys) ** 0.5
    if dx == 0 or dy == 0:
        return None
    return num / (dx * dy)


def kendall_tau(a: list[int], b: list[int]) -> float | None:
    """Kendall τ between two permutations of the same multiset of indices (as sequences of orig indices)."""
    n = len(a)
    if n < 2 or len(b) != n:
        return None
    # map value -> position in b (first occurrence for ties via enumerate of pairs)
    # Treat as rankings of positions 0..n-1 labeled by a[i]
    pos_b = {v: i for i, v in enumerate(b)}
    # If duplicate values in permutation of indices, a and b are permutations of 0..n-1
    concord = 0
    discord = 0
    for i in range(n):
        for j in range(i + 1, n):
            ai, aj = a[i], a[j]
            bi, bj = pos_b[ai], pos_b[aj]
            if bi < bj:
                concord += 1
            else:
                discord += 1
    tot = concord + discord
    if tot == 0:
        return None
    return (concord - discord) / tot


def adj_swap_distance(order: list[int]) -> int:
    """Bubble-sort swap count to restore identity (0,1,...,n-1) from `order` of orig indices."""
    arr = list(order)
    n = len(arr)
    swaps = 0
    for i in range(n):
        for j in range(n - 1):
            if arr[j] > arr[j + 1]:
                arr[j], arr[j + 1] = arr[j + 1], arr[j]
                swaps += 1
    return swaps


def extract_perm_features(items_orig: list[dict], order: list[int]) -> dict[str, Any]:
    """Features for one permutation; `order` is indices into `items_orig`."""
    items = [items_orig[i] for i in order]
    n = len(items)
    atks = [max_attack(m) for m in items]
    hps = [max_health(m) for m in items]
    taunt_idx = [i for i, m in enumerate(items) if is_taunt(m)]
    reborn_idx = [i for i, m in enumerate(items) if is_reborn_or_dr(m)]
    cleave_idx = [i for i, m in enumerate(items) if is_cleave(m)]

    strongest_atk_i = max(range(n), key=lambda i: (atks[i], -i)) if n else None
    strongest_hp_i = max(range(n), key=lambda i: (hps[i], -i)) if n else None

    cleave_adj_tank = None
    if cleave_idx:
        hits = 0
        checks = 0
        for ci in cleave_idx:
            for ni in (ci - 1, ci + 1):
                if 0 <= ni < n and ni not in cleave_idx:
                    checks += 1
                    if hps[ni] >= sorted(hps, reverse=True)[min(1, n - 1)]:
                        hits += 1
        cleave_adj_tank = (hits / checks) if checks else None

    identity = list(range(n))
    return {
        "n": n,
        "tauntLeftmost": 1.0 if taunt_idx and taunt_idx[0] == 0 else (0.0 if taunt_idx else None),
        "tauntMeanIndex": (sum(taunt_idx) / len(taunt_idx)) if taunt_idx else None,
        "tauntAny": 1.0 if taunt_idx else 0.0,
        "rebornMeanIndex": (sum(reborn_idx) / len(reborn_idx)) if reborn_idx else None,
        "rebornAny": 1.0 if reborn_idx else 0.0,
        "cleaveAdjTankRate": cleave_adj_tank,
        "cleaveAny": 1.0 if cleave_idx else 0.0,
        "spearmanAtkLeft": _spearman_vs_rank(atks),
        "spearmanHpLeft": _spearman_vs_rank(hps),
        "strongestAtkLeftHalf": (
            1.0 if strongest_atk_i is not None and strongest_atk_i < max(1, (n + 1) // 2) else 0.0
        )
        if n
        else None,
        "strongestHpLeftHalf": (
            1.0 if strongest_hp_i is not None and strongest_hp_i < max(1, (n + 1) // 2) else 0.0
        )
        if n
        else None,
        "kendallVsOrig": kendall_tau(order, identity),
        "adjSwapFromOrig": float(adj_swap_distance(order)),
        "cardIds": [card_id(m) for m in items],
    }


def mean_features(rows: list[dict[str, Any]], keys: list[str]) -> dict[str, float | None]:
    out: dict[str, float | None] = {}
    for k in keys:
        vals = [float(r[k]) for r in rows if r.get(k) is not None]
        out[k] = (sum(vals) / len(vals)) if vals else None
    return out


FEATURE_KEYS = [
    "tauntLeftmost",
    "tauntMeanIndex",
    "rebornMeanIndex",
    "cleaveAdjTankRate",
    "spearmanAtkLeft",
    "spearmanHpLeft",
    "strongestAtkLeftHalf",
    "strongestHpLeftHalf",
    "kendallVsOrig",
    "adjSwapFromOrig",
]


def compare_groups(
    top: list[dict[str, Any]],
    all_rows: list[dict[str, Any]],
    bottom: list[dict[str, Any]],
) -> dict[str, Any]:
    mt = mean_features(top, FEATURE_KEYS)
    ma = mean_features(all_rows, FEATURE_KEYS)
    mb = mean_features(bottom, FEATURE_KEYS)
    diff_all = {
        k: (mt[k] - ma[k]) if mt[k] is not None and ma[k] is not None else None for k in FEATURE_KEYS
    }
    diff_bot = {
        k: (mt[k] - mb[k]) if mt[k] is not None and mb[k] is not None else None for k in FEATURE_KEYS
    }
    return {
        "meanTop": mt,
        "meanAll": ma,
        "meanBottom": mb,
        "topMinusAll": diff_all,
        "topMinusBottom": diff_bot,
        "nTop": len(top),
        "nAll": len(all_rows),
        "nBottom": len(bottom),
    }
