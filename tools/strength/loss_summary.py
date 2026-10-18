# -*- coding: utf-8 -*-
"""Loss-damage summary for the blood percentile.

Negative damageResults are losses. Expected taken damage is the mean of the
raw sample values: a negative sample contributes its own magnitude, including
when that magnitude equals DamageCap. Wins and ties contribute 0. Capped
losses stay in the sample.
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
    taken = 0
    for raw in samples:
        sample_count += 1
        v = int(raw)
        if v >= 0:
            continue
        loss_count += 1
        got = -v
        taken += got
        if cap > 0 and got == cap:
            capped += 1
        else:
            uncapped.append(got)
    if sample_count == 0:
        return None
    median = _median(uncapped) if uncapped else None
    return {
        "lossCount": loss_count,
        "cappedLossCount": capped,
        "uncappedLossMedian": median,
        "lossSampleCount": sample_count,
        "takenSum": taken,
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
    taken_sum: float | None = None,
) -> float | None:
    """Mean of raw taken damage. Each negative sample counts as its own value.

    ``taken_sum`` is required. Capped losses are included at the value written
    in damageResults, not dropped and not replaced by a separate cap rule.
    """
    del loss_count, capped_loss_count, uncapped_median, damage_cap
    n = int(sample_count)
    if n <= 0 or taken_sum is None:
        return None
    return float(taken_sum) / float(n)


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
