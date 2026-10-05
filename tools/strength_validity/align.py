# -*- coding: utf-8 -*-
"""Align strength.jsonl × turns.jsonl × optional diag Player.Health."""
from __future__ import annotations

import json
import os
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Optional

_TOOLS = Path(__file__).resolve().parents[1]
_REPO = _TOOLS.parent
if str(_TOOLS) not in sys.path:
    sys.path.insert(0, str(_TOOLS))

from standard_layer.combat import discover_games, iter_game_combats, load_meta  # noqa: E402


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


def hdt_score(win: Any, tie: Any) -> Optional[float]:
    if win is None and tie is None:
        return None
    w = float(win or 0.0)
    t = float(tie or 0.0)
    return w + 0.5 * t


def _hdt_from_strength_or_turn(srow: dict, trow: Optional[dict]) -> Optional[float]:
    hdt = srow.get("hdt")
    if isinstance(hdt, dict):
        sc = hdt_score(hdt.get("winRate"), hdt.get("tieRate"))
        if sc is not None:
            return sc
    if trow:
        out = trow.get("output") or {}
        if isinstance(out, dict):
            return hdt_score(out.get("winRate"), out.get("tieRate"))
    return None


def index_turns(rows: Iterable[dict], *, bb_version: str | None = None) -> dict[tuple[str, int], dict]:
    by: dict[tuple[str, int], dict] = {}
    for r in rows:
        if bb_version is not None:
            bb = (r.get("meta") or {}).get("bbVersion")
            if str(bb) != bb_version:
                continue
        t = r.get("turn")
        gid = r.get("gameId")
        if t is None or not gid:
            continue
        by[(str(gid), int(t))] = r
    return by


def load_player_health_from_diag(
    roots: list[str],
    bb_version: str,
) -> dict[tuple[str, int], int]:
    """(gameId, turn) -> Player.Health from combat Input (pre-combat snapshot)."""
    out: dict[tuple[str, int], int] = {}
    games = discover_games(roots)
    for gid, gdir in games.items():
        meta = load_meta(gdir)
        bb = (meta.get("bobsBuddy") or {}).get("fileVersion") or (meta.get("bobsBuddy") or {}).get(
            "version"
        )
        if str(bb) != bb_version:
            continue
        try:
            _, _, combats = iter_game_combats(gdir)
        except Exception:  # noqa: BLE001
            continue
        for c in combats:
            turn = c.get("turn")
            inp = c.get("input") or {}
            pl = inp.get("Player") or {}
            hp = pl.get("Health")
            if turn is None or hp is None:
                continue
            try:
                out[(gid, int(turn))] = int(hp)
            except (TypeError, ValueError):
                continue
    return out


def default_diag_roots() -> list[str]:
    return [
        str(_REPO / "data" / "BgHelperDiag"),
        os.path.expandvars(r"%APPDATA%\HearthstoneDeckTracker\BgHelperDiag"),
    ]


@dataclass
class TurnPair:
    game_id: str
    turn: int
    percentile: float
    hdt: Optional[float]
    next_health: Optional[int]
    health_source: Optional[str]  # input | friendlyHealth | None
    flags: list[str] = field(default_factory=list)
    level: Optional[str] = None
    width_pts: Optional[float] = None
    placement: Optional[int] = None
    result: Optional[str] = None  # appendix only


@dataclass
class GameAgg:
    game_id: str
    placement: Optional[int]
    mean_percentile: Optional[float]
    mean_hdt: Optional[float]
    n_turns: int
    mean_next_health: Optional[float]
    last_known_health: Optional[int]
    n_wide: int = 0
    n_insufficient: int = 0


def align_turns(
    strength_rows: list[dict],
    turns_by: dict[tuple[str, int], dict],
    health_by: dict[tuple[str, int], int],
    *,
    max_turn: int | None = 12,
    side: str = "Player",
) -> list[TurnPair]:
    """One row per strength Player turn with percentile; attach next-turn health."""
    # Pre-index friendlyHealth from turns for fallback / next turn lookup
    fh: dict[tuple[str, int], int] = {}
    for (gid, t), row in turns_by.items():
        out = row.get("output") or {}
        if isinstance(out, dict) and out.get("friendlyHealth") is not None:
            try:
                fh[(gid, t)] = int(out["friendlyHealth"])
            except (TypeError, ValueError):
                pass

    pairs: list[TurnPair] = []
    for s in strength_rows:
        if str(s.get("side") or "") != side:
            continue
        if s.get("percentile") is None:
            continue
        turn = s.get("turn")
        gid = s.get("gameId")
        if turn is None or not gid:
            continue
        t = int(turn)
        if max_turn is not None and t > max_turn:
            continue
        gid = str(gid)
        trow = turns_by.get((gid, t))
        # next health: prefer Input at t+1, else friendlyHealth at t+1
        nxt_key = (gid, t + 1)
        next_hp: Optional[int] = None
        src: Optional[str] = None
        if nxt_key in health_by:
            next_hp = health_by[nxt_key]
            src = "input"
        elif nxt_key in fh:
            next_hp = fh[nxt_key]
            src = "friendlyHealth"

        flags = list(s.get("flags") or [])
        pairs.append(
            TurnPair(
                game_id=gid,
                turn=t,
                percentile=float(s["percentile"]),
                hdt=_hdt_from_strength_or_turn(s, trow),
                next_health=next_hp,
                health_source=src,
                flags=flags,
                level=s.get("level"),
                width_pts=s.get("widthPts"),
                placement=(trow or {}).get("placement") if trow else s.get("placement"),
                result=(trow or {}).get("result") if trow else None,
            )
        )
    pairs.sort(key=lambda p: (p.game_id, p.turn))
    return pairs


def aggregate_games(pairs: list[TurnPair]) -> list[GameAgg]:
    by: dict[str, list[TurnPair]] = defaultdict(list)
    for p in pairs:
        by[p.game_id].append(p)
    out: list[GameAgg] = []
    for gid, rows in sorted(by.items()):
        pcts = [r.percentile for r in rows]
        hdts = [r.hdt for r in rows if r.hdt is not None]
        nhs = [r.next_health for r in rows if r.next_health is not None]
        placement = None
        for r in rows:
            if r.placement is not None:
                placement = int(r.placement)
                break
        # last known health: max turn with next_health, else none; also track terminal
        last_hp = None
        if nhs:
            # health at highest turn+1 among rows that have next_health
            best_t = -1
            for r in rows:
                if r.next_health is not None and r.turn > best_t:
                    best_t = r.turn
                    last_hp = r.next_health
        out.append(
            GameAgg(
                game_id=gid,
                placement=placement,
                mean_percentile=float(np_mean(pcts)) if pcts else None,
                mean_hdt=float(np_mean(hdts)) if hdts else None,
                n_turns=len(rows),
                mean_next_health=float(np_mean(nhs)) if nhs else None,
                last_known_health=last_hp,
                n_wide=sum(1 for r in rows if "wide" in (r.flags or [])),
                n_insufficient=sum(1 for r in rows if "insufficient" in (r.flags or [])),
            )
        )
    return out


def np_mean(xs: list[float]) -> float:
    return sum(xs) / len(xs)


def result_code(result: Optional[str]) -> Optional[float]:
    if result == "win":
        return 1.0
    if result == "tie":
        return 0.5
    if result == "loss":
        return 0.0
    return None
