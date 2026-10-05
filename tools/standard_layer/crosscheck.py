# -*- coding: utf-8 -*-
"""Cross-check standard-layer turn against Tuanzi board + five rates."""
from __future__ import annotations

from typing import Optional


def pct100(x) -> float | None:
    if x is None:
        return None
    v = float(x)
    if 0 <= v <= 1.0000001:
        return round(v * 100.0, 3)
    return round(v, 3)


def approx_eq(a, b, tol: float = 0.6) -> bool:
    if a is None or b is None:
        return False
    return abs(float(a) - float(b)) <= tol


def board_sig(ms: list[dict], *, prefer: str = "max") -> list[tuple]:
    """Multiset of (atk, health, golden). prefer=max|base selects which fields when both exist."""
    out = []
    for m in ms:
        if prefer == "base":
            atk = m.get("baseAtk")
            if atk is None:
                atk = m.get("atk")
            hp = m.get("baseHealth")
            if hp is None:
                hp = m.get("health")
        else:
            atk = m.get("atk")
            hp = m.get("health")
        if atk is None or hp is None:
            continue
        out.append((int(atk), int(hp), bool(m.get("golden"))))
    return sorted(out)


def board_match(diag: list[dict], tuanzi: list[dict]) -> bool:
    """True if max-stat or base-stat multiset matches tuanzi (UI often prints Base*)."""
    tz = board_sig(tuanzi, prefer="max")  # tuanzi rows only have atk/health
    return board_sig(diag, prefer="max") == tz or board_sig(diag, prefer="base") == tz


def crosscheck_turn(combat: dict, tuanzi_turn: Optional[dict]) -> Optional[dict]:
    if not tuanzi_turn:
        return None
    kind = tuanzi_turn.get("kind")
    if kind == "direct_dc":
        return {"kind": kind, "applicable": False, "reason": "direct_dc"}

    out = combat.get("outputSummary") or {}
    sim = tuanzi_turn.get("sim") or {}
    has_board = "mine" in tuanzi_turn or "opp" in tuanzi_turn
    bb_ok = None
    if has_board:
        bb_ok = board_match(combat.get("playerMinions") or [], tuanzi_turn.get("mine") or []) and board_match(
            combat.get("oppMinions") or [], tuanzi_turn.get("opp") or []
        )

    sim_ok = None
    if sim and out.get("winRate") is not None:
        sim_ok = (
            approx_eq(pct100(out.get("winRate")), sim.get("win"))
            and approx_eq(pct100(out.get("tieRate")), sim.get("tie"))
            and approx_eq(pct100(out.get("lossRate")), sim.get("loss"))
            and approx_eq(pct100(out.get("myDeathRate")), sim.get("myLethal"))
            and approx_eq(pct100(out.get("theirDeathRate")), sim.get("theirLethal"))
            and (
                out.get("simulationCount") == sim.get("count")
                or abs((out.get("simulationCount") or 0) - (sim.get("count") or -1)) <= 2
            )
        )

    applicable = bool(has_board or sim)
    # Exit criteria: ready turns must match board + five rates + sim count when Tuanzi has them.
    strict = None
    if applicable:
        strict = (bb_ok is True if has_board else True) and (sim_ok is True if sim else True)
    return {
        "kind": kind,
        "applicable": applicable,
        "boardOk": bb_ok,
        "simOk": sim_ok,
        "strictPass": strict,
    }
