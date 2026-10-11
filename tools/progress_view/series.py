# -*- coding: utf-8 -*-
"""Chronological strength series for one sim pool."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Optional

from tools.strength.sim_pools import member_versions
from tools.strength_validity.metrics import spearman


def load_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
    if not path.is_file():
        return rows
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def _pct(row: dict) -> Optional[float]:
    v = row.get("percentile")
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _mean(xs: list[float]) -> Optional[float]:
    if not xs:
        return None
    return sum(xs) / len(xs)


@dataclass
class GamePoint:
    seq: int
    game_id: str
    bb_version: str
    survival_turns: Optional[int]
    survival_source: str
    placement: Optional[int]
    player_by_turn: dict[int, float] = field(default_factory=dict)
    opp_by_turn: dict[int, float] = field(default_factory=dict)
    player_mean: Optional[float] = None
    opp_mean: Optional[float] = None
    player_n: int = 0
    opp_n: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "seq": self.seq,
            "gameId": self.game_id,
            "bbVersion": self.bb_version,
            "survivalTurns": self.survival_turns,
            "survivalSource": self.survival_source,
            "placement": self.placement,
            "playerByTurn": {str(k): v for k, v in sorted(self.player_by_turn.items())},
            "oppByTurn": {str(k): v for k, v in sorted(self.opp_by_turn.items())},
            "playerMean": self.player_mean,
            "oppMean": self.opp_mean,
            "playerN": self.player_n,
            "oppN": self.opp_n,
        }


def rolling_mean(values: list[Optional[float]], window: int) -> list[Optional[float]]:
    """Trailing mean over the last `window` non-null observations, aligned to index."""
    if window < 1:
        raise ValueError("window must be >= 1")
    out: list[Optional[float]] = []
    buf: list[float] = []
    for v in values:
        if v is None:
            out.append(_mean(buf[-window:]) if buf else None)
            continue
        buf.append(v)
        out.append(_mean(buf[-window:]))
    return out


def _index_side(rows: Iterable[dict], side: str) -> dict[str, dict[int, float]]:
    by: dict[str, dict[int, float]] = {}
    for r in rows:
        if str(r.get("side") or "") != side:
            continue
        gid = r.get("gameId")
        turn = r.get("turn")
        pct = _pct(r)
        if not gid or turn is None or pct is None:
            continue
        by.setdefault(str(gid), {})[int(turn)] = pct
    return by


def _bb_by_game(rows: Iterable[dict]) -> dict[str, str]:
    out: dict[str, str] = {}
    for r in rows:
        gid = r.get("gameId")
        bb = r.get("bbVersion")
        if gid and bb and str(gid) not in out:
            out[str(gid)] = str(bb)
    return out


def _turns_facts(
    turns: Iterable[dict],
    members: set[str],
) -> dict[str, dict[str, Any]]:
    """gameId -> survival, placement, bbVersion from the standard layer."""
    acc: dict[str, dict[str, Any]] = {}
    for r in turns:
        meta = r.get("meta") or {}
        bb = str(meta.get("bbVersion") or "")
        gid = r.get("gameId")
        turn = r.get("turn")
        if not gid or turn is None:
            continue
        if bb not in members:
            continue
        slot = acc.setdefault(
            str(gid),
            {"bb": bb, "maxTurn": 0, "placement": None},
        )
        t = int(turn)
        if t > int(slot["maxTurn"]):
            slot["maxTurn"] = t
        if r.get("placement") is not None:
            slot["placement"] = int(r["placement"])
        if bb:
            slot["bb"] = bb
    return acc


def _strength_max_turn(rows: Iterable[dict]) -> dict[str, int]:
    out: dict[str, int] = {}
    for r in rows:
        gid = r.get("gameId")
        turn = r.get("turn")
        if not gid or turn is None:
            continue
        t = int(turn)
        prev = out.get(str(gid), 0)
        if t > prev:
            out[str(gid)] = t
    return out


def build_series(
    strength_rows: list[dict],
    turns_rows: list[dict],
    opp_rows: list[dict] | None = None,
    *,
    sim_pool: str = "1.85.0.0",
    window: int = 8,
) -> dict[str, Any]:
    """Games in `sim_pool`, ordered by gameId. Percentiles stay on 0–1."""
    members = set(member_versions(sim_pool))
    player = _index_side(strength_rows, "Player")
    opp = _index_side(opp_rows or [], "Opponent")
    bb_of = _bb_by_game(strength_rows)
    facts = _turns_facts(turns_rows, members)
    max_from_strength = _strength_max_turn(strength_rows)

    game_ids = set(player) | set(facts)
    # Drop games whose file version is outside the pool when we know it.
    kept: list[str] = []
    for gid in game_ids:
        bb = str(bb_of.get(gid) or (facts.get(gid) or {}).get("bb") or "")
        if bb and bb not in members:
            continue
        kept.append(gid)
    kept.sort()

    points: list[GamePoint] = []
    for i, gid in enumerate(kept, start=1):
        fact = facts.get(gid) or {}
        if fact.get("maxTurn"):
            survival = int(fact["maxTurn"])
            source = "turns"
        elif gid in max_from_strength:
            survival = max_from_strength[gid]
            source = "strength"
        else:
            survival = None
            source = "none"
        pmap = dict(player.get(gid) or {})
        omap = dict(opp.get(gid) or {})
        pvals = list(pmap.values())
        ovals = list(omap.values())
        points.append(
            GamePoint(
                seq=i,
                game_id=gid,
                bb_version=str(bb_of.get(gid) or fact.get("bb") or ""),
                survival_turns=survival,
                survival_source=source,
                placement=fact.get("placement"),
                player_by_turn=pmap,
                opp_by_turn=omap,
                player_mean=_mean(pvals),
                opp_mean=_mean(ovals),
                player_n=len(pvals),
                opp_n=len(ovals),
            )
        )

    def col(fn) -> list[Optional[float]]:
        return [fn(p) for p in points]

    seqs = [float(p.seq) for p in points]
    player_means = col(lambda p: p.player_mean)
    opp_means = col(lambda p: p.opp_mean)
    survivals = col(lambda p: float(p.survival_turns) if p.survival_turns is not None else None)

    def trend(ys: list[Optional[float]]) -> dict[str, Any]:
        xs = [s for s, y in zip(seqs, ys) if y is not None]
        yy = [y for y in ys if y is not None]
        return spearman(xs, yy)

    turns_seen = sorted({t for p in points for t in p.player_by_turn})
    return {
        "simPool": sim_pool,
        "members": sorted(members),
        "window": window,
        "nGames": len(points),
        "games": [p.to_dict() for p in points],
        "playerMeanRoll": rolling_mean(player_means, window),
        "oppMeanRoll": rolling_mean(opp_means, window),
        "survivalRoll": rolling_mean(survivals, window),
        "trend": {
            "playerMean": trend(player_means),
            "oppMean": trend(opp_means),
            "survival": trend(survivals),
        },
        "turns": turns_seen,
    }
