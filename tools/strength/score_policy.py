# -*- coding: utf-8 -*-
"""Turn-dependent matchup score (ADR-0016 / design R-score-policy-search §3.1).

Damage coefficients stay available for the formula tests. Q-020 found that
positive DamageCap truncates damageResults, so the live search fixes alpha=beta=0.
"""
from __future__ import annotations

from typing import Callable

# T5 and earlier stay at tie weight 1. Floor is not searched.
T_LOCK = 5
W_FLOOR = 0.6
T1_GRID = (9, 12, 15)


def tie_weight(turn: int, t1: int, *, w_floor: float = W_FLOOR, t_lock: int = T_LOCK) -> float:
    """1 through t_lock, then linear down to w_floor at t1, then flat."""
    t = int(turn)
    if t <= t_lock:
        return 1.0
    if t1 <= t_lock:
        return float(w_floor)
    if t >= t1:
        return float(w_floor)
    return 1.0 + (float(w_floor) - 1.0) * (t - t_lock) / float(t1 - t_lock)


def damage_lambda(turn: int, td: int, length: int) -> float:
    """0 at and before td; rises linearly to 1 over `length` turns after td."""
    t = int(turn)
    if t <= int(td):
        return 0.0
    span = int(length)
    if span <= 0:
        return 1.0
    return min(1.0, (t - int(td)) / float(span))


def matchup_score(
    win: float,
    tie: float,
    turn: int,
    *,
    t1: int,
    td: int = 5,
    length: int = 3,
    alpha: float = 0.0,
    beta: float = 0.0,
    z_deal: float = 0.0,
    z_take: float = 0.0,
    w_floor: float = W_FLOOR,
) -> float:
    """s = Pw + w(t) Pt + λ(t) (α z_deal − β z_take).

    Missing wins zero the deal term. Missing losses zero the take term.
    """
    pw = float(win)
    pt = float(tie)
    loss = 1.0 - pw - pt
    w = tie_weight(turn, t1, w_floor=w_floor)
    lam = damage_lambda(turn, td, length)
    deal = 0.0 if pw <= 0.0 else float(alpha) * float(z_deal)
    take = 0.0 if loss <= 1e-12 else float(beta) * float(z_take)
    return pw + w * pt + lam * (deal - take)


def curve_score(t1: int) -> Callable[[float, float, int], float]:
    """Win/tie/turn scorer with damage coefficients fixed at 0."""

    def fn(win: float, tie: float, turn: int) -> float:
        return matchup_score(win, tie, turn, t1=t1, alpha=0.0, beta=0.0)

    return fn


def baseline_score(win: float, tie: float, turn: int) -> float:
    """Old formula: tie weight 0.5, no damage. Turn is ignored."""
    del turn
    return float(win) + 0.5 * float(tie)
