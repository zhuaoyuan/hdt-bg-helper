# -*- coding: utf-8 -*-
"""Loss-damage summary for ADR-0019 labels.

Mirrors ReplaySim.TrySummarizeLosses: negative damageResults are losses,
a positive DamageCap censors at that value, and the median is taken damage
among losses that are not on the cap. Win/tie samples (>= 0) contribute 0
to expected taken damage.
"""
from __future__ import annotations

from typing import Any, Sequence


def summarize_loss_samples(samples: Sequence[int], damage_cap: int) -> dict[str, Any] | None:
    """Return lossCount, cappedLossCount, uncappedLossMedian, lossSampleCount."""
    cap = int(damage_cap or 0)
    uncapped: list[int] = []
    loss_count = 0
    capped = 0
    sample_count = 0
    for raw in samples:
        sample_count += 1
        v = int(raw)
        if v >= 0:
            continue
        loss_count += 1
        taken = -v
        if cap > 0 and taken == cap:
            capped += 1
        else:
            uncapped.append(taken)
    if sample_count == 0:
        return None
    median = _median(uncapped) if uncapped else None
    return {
        "lossCount": loss_count,
        "cappedLossCount": capped,
        "uncappedLossMedian": median,
        "lossSampleCount": sample_count,
        "damageCap": cap,
    }


def _median(vals: list[int]) -> float:
    ordered = sorted(vals)
    n = len(ordered)
    if n % 2 == 1:
        return float(ordered[n // 2])
    return (ordered[n // 2 - 1] + ordered[n // 2]) / 2.0


def expected_taken(
    *,
    loss_count: int,
    capped_loss_count: int,
    uncapped_median: float | None,
    sample_count: int,
    damage_cap: int,
) -> float | None:
    """Mean taken damage over the sample. Wins and ties are 0.

    Uncapped losses use their median; capped losses use the cap. That is the
    average that can be rebuilt from the stored columns.
    """
    n = int(sample_count)
    if n <= 0:
        return None
    losses = int(loss_count)
    capped = int(capped_loss_count)
    if capped < 0 or capped > losses or losses > n:
        return None
    uncapped_n = losses - capped
    if uncapped_n > 0 and uncapped_median is None:
        return None
    med = 0.0 if uncapped_n == 0 else float(uncapped_median)
    cap = float(damage_cap) if int(damage_cap) > 0 else 0.0
    return (uncapped_n * med + capped * cap) / float(n)


def z_take(
    *,
    loss_count: int,
    capped_loss_count: int,
    uncapped_median: float | None,
    turn_median: float | None,
) -> float:
    """Phase-2 taken-damage scale. Half-or-more capped, or no uncapped loss, is 1."""
    losses = int(loss_count)
    capped = int(capped_loss_count)
    if losses <= 0 or capped * 2 >= losses or uncapped_median is None:
        return 1.0
    if turn_median is None or float(turn_median) <= 0:
        return 1.0
    return float(uncapped_median) / float(turn_median)
