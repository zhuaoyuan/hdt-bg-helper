# -*- coding: utf-8 -*-
"""Join standard-layer turns with strength.jsonl into GameReview."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable, Optional

from .model import GameReview, TurnReview, strength_state_for


def load_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def _game_matches(row_gid: str, game_id: str) -> bool:
    if row_gid == game_id:
        return True
    return row_gid.endswith("_" + game_id) or row_gid.endswith(game_id)


def filter_turns(rows: Iterable[dict], game_id: str) -> list[dict]:
    matched = [r for r in rows if _game_matches(str(r.get("gameId") or ""), game_id)]
    matched.sort(key=lambda r: (int(r.get("turn") or 0), int(r.get("combat") or 0)))
    return matched


def index_player_strength(rows: Iterable[dict], game_id: str) -> dict[int, dict]:
    """Map turn -> first Player-side strength row for the game."""
    out: dict[int, dict] = {}
    for r in rows:
        if not _game_matches(str(r.get("gameId") or ""), game_id):
            continue
        side = str(r.get("side") or "")
        if side not in ("Player", "player"):
            continue
        turn = r.get("turn")
        if turn is None:
            continue
        t = int(turn)
        if t not in out:
            out[t] = r
    return out


def _hdt_from_sources(turn_row: dict, strength_row: Optional[dict]) -> tuple[Optional[float], Optional[float], Optional[float]]:
    hdt = (strength_row or {}).get("hdt") if strength_row else None
    if isinstance(hdt, dict) and hdt.get("winRate") is not None:
        return hdt.get("winRate"), hdt.get("tieRate"), hdt.get("lossRate")
    out = turn_row.get("output") or {}
    if isinstance(out, dict):
        return out.get("winRate"), out.get("tieRate"), out.get("lossRate")
    return None, None, None


def _ci95(row: Optional[dict]) -> Optional[tuple[float, float]]:
    if not row:
        return None
    ci = row.get("ci95")
    if isinstance(ci, (list, tuple)) and len(ci) >= 2:
        return float(ci[0]), float(ci[1])
    return None


def build_game_review(
    *,
    game_id: str,
    turn_rows: list[dict],
    strength_by_turn: dict[int, dict],
    tiers_by_turn: Optional[dict[int, tuple[Optional[int], Optional[int]]]] = None,
    boards_by_turn: Optional[dict[int, tuple[Optional[str], Optional[str]]]] = None,
    notes: Optional[dict[str, Any]] = None,
    allow_missing_strength: bool = False,
) -> GameReview:
    if not turn_rows:
        raise ValueError(f"no standard-layer turns for game {game_id!r}")

    canonical = str(turn_rows[0].get("gameId") or game_id)
    my_hero = turn_rows[0].get("myHero")
    placement = turn_rows[0].get("placement")
    bb = (turn_rows[0].get("meta") or {}).get("bbVersion")
    engine = None

    turns: list[TurnReview] = []
    for row in turn_rows:
        turn = int(row["turn"])
        srow = strength_by_turn.get(turn)
        if srow is None and not allow_missing_strength:
            # still emit row as missing; CLI may refuse later for ready turns
            pass
        if srow and engine is None:
            engine = srow.get("engineVersion")
        if srow and bb is None:
            bb = srow.get("bbVersion")
        hdt_w, hdt_t, hdt_l = _hdt_from_sources(row, srow)
        status = str(row.get("status") or "unknown")
        state = strength_state_for(status=status, strength_row=srow)
        my_tier = opp_tier = None
        if tiers_by_turn and turn in tiers_by_turn:
            my_tier, opp_tier = tiers_by_turn[turn]
        bp = bo = None
        if boards_by_turn and turn in boards_by_turn:
            bp, bo = boards_by_turn[turn]
        flags = list((srow or {}).get("flags") or [])
        turns.append(
            TurnReview(
                turn=turn,
                status=status,
                opp_hero=row.get("oppHero"),
                result=row.get("result"),
                damage=row.get("damage"),
                result_source=row.get("resultSource"),
                hdt_win=hdt_w,
                hdt_tie=hdt_t,
                hdt_loss=hdt_l,
                S=(srow or {}).get("S"),
                percentile=(srow or {}).get("percentile"),
                ci95=_ci95(srow),
                width_pts=(srow or {}).get("widthPts"),
                level=(srow or {}).get("level"),
                flags=flags,
                strength_state=state,
                my_tavern_tier=my_tier,
                opp_tavern_tier=opp_tier,
                board_player=bp,
                board_opponent=bo,
                combat=row.get("combat"),
            )
        )

    return GameReview(
        game_id=canonical,
        my_hero=my_hero,
        placement=placement,
        bb_version=bb,
        engine_version=engine,
        turns=turns,
        notes=notes,
    )


def load_notes(path: Path) -> Optional[dict[str, Any]]:
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))
