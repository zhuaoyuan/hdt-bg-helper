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


def index_strength(
    rows: Iterable[dict],
    game_id: str,
    *,
    side: str,
) -> dict[int, dict]:
    """Map turn -> first strength row for game+side (Player or Opponent)."""
    want = {side, side.lower(), side.capitalize()}
    out: dict[int, dict] = {}
    for r in rows:
        if not _game_matches(str(r.get("gameId") or ""), game_id):
            continue
        if str(r.get("side") or "") not in want:
            continue
        turn = r.get("turn")
        if turn is None:
            continue
        t = int(turn)
        if t not in out:
            out[t] = r
    return out


def index_player_strength(rows: Iterable[dict], game_id: str) -> dict[int, dict]:
    return index_strength(rows, game_id, side="Player")


def index_opponent_strength(rows: Iterable[dict], game_id: str) -> dict[int, dict]:
    return index_strength(rows, game_id, side="Opponent")


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


def _apply_strength(row: Optional[dict]) -> dict[str, Any]:
    if not row:
        return {
            "S": None,
            "percentile": None,
            "ci95": None,
            "width_pts": None,
            "level": None,
            "flags": [],
        }
    return {
        "S": row.get("S"),
        "percentile": row.get("percentile"),
        "ci95": _ci95(row),
        "width_pts": row.get("widthPts"),
        "level": row.get("level"),
        "flags": list(row.get("flags") or []),
    }


def build_game_review(
    *,
    game_id: str,
    turn_rows: list[dict],
    strength_by_turn: dict[int, dict],
    opp_strength_by_turn: Optional[dict[int, dict]] = None,
    tiers_by_turn: Optional[dict[int, tuple[Optional[int], Optional[int]]]] = None,
    boards_by_turn: Optional[dict[int, tuple[Optional[str], Optional[str]]]] = None,
    notes: Optional[dict[str, Any]] = None,
    allow_missing_strength: bool = False,
) -> GameReview:
    del allow_missing_strength
    if not turn_rows:
        raise ValueError(f"no standard-layer turns for game {game_id!r}")

    canonical = str(turn_rows[0].get("gameId") or game_id)
    my_hero = turn_rows[0].get("myHero")
    placement = turn_rows[0].get("placement")
    bb = (turn_rows[0].get("meta") or {}).get("bbVersion")
    engine = None
    opp_map = opp_strength_by_turn or {}

    turns: list[TurnReview] = []
    prev_my_tier: Optional[int] = None
    prev_opp_tier: Optional[int] = None
    for row in turn_rows:
        turn = int(row["turn"])
        srow = strength_by_turn.get(turn)
        orow = opp_map.get(turn)
        if srow and engine is None:
            engine = srow.get("engineVersion")
        if srow and bb is None:
            bb = srow.get("bbVersion")
        if orow and engine is None:
            engine = orow.get("engineVersion")
        hdt_w, hdt_t, hdt_l = _hdt_from_sources(row, srow)
        status = str(row.get("status") or "unknown")
        state = strength_state_for(status=status, strength_row=srow)
        opp_state = strength_state_for(status=status, strength_row=orow)
        my_tier = opp_tier = None
        if tiers_by_turn and turn in tiers_by_turn:
            my_tier, opp_tier = tiers_by_turn[turn]
        my_up = prev_my_tier is not None and my_tier is not None and my_tier > prev_my_tier
        opp_up = prev_opp_tier is not None and opp_tier is not None and opp_tier > prev_opp_tier
        if my_tier is not None:
            prev_my_tier = my_tier
        if opp_tier is not None:
            prev_opp_tier = opp_tier
        bp = bo = None
        if boards_by_turn and turn in boards_by_turn:
            bp, bo = boards_by_turn[turn]
        ps = _apply_strength(srow)
        os_ = _apply_strength(orow)
        out = row.get("output") if isinstance(row.get("output"), dict) else {}
        my_hp = out.get("friendlyHealth")
        try:
            my_hp_i = int(my_hp) if my_hp is not None else None
        except (TypeError, ValueError):
            my_hp_i = None
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
                S=ps["S"],
                percentile=ps["percentile"],
                ci95=ps["ci95"],
                width_pts=ps["width_pts"],
                level=ps["level"],
                flags=ps["flags"],
                strength_state=state,
                opp_S=os_["S"],
                opp_percentile=os_["percentile"],
                opp_ci95=os_["ci95"],
                opp_width_pts=os_["width_pts"],
                opp_level=os_["level"],
                opp_flags=os_["flags"],
                opp_strength_state=opp_state,
                my_tavern_tier=my_tier,
                opp_tavern_tier=opp_tier,
                my_tavern_up=my_up,
                opp_tavern_up=opp_up,
                my_health=my_hp_i,
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
