# -*- coding: utf-8 -*-
"""Final placement from the game_end entity snapshot.

``PLAYER_LEADERBOARD_PLACE`` is only final for players already eliminated when the
local player's game ends. This helper reads the local player's hero only; it does
not claim to reconstruct the full lobby ranking.
"""
from __future__ import annotations

from typing import Optional


def _local_hero_id(records: list[dict]) -> Optional[int]:
    hero_id: Optional[int] = None
    for r in records:
        if r.get("type") != "entities":
            continue
        player = (r.get("context") or {}).get("player") or {}
        hero = player.get("hero")
        if hero is not None:
            try:
                hero_id = int(hero)
            except (TypeError, ValueError):
                pass
    return hero_id


def final_local_place(records: list[dict]) -> Optional[int]:
    """Return the local player's final placement, or None when unavailable.

    Only the local player is considered. A place of 0 (not yet final) is treated
    as unknown rather than as "第 0 名".
    """
    game_end: Optional[dict] = None
    hero_id = _local_hero_id(records)
    for r in records:
        if r.get("type") == "entities" and r.get("reason") == "game_end":
            game_end = r
    if game_end is None:
        return None
    end_hero = ((game_end.get("context") or {}).get("player") or {}).get("hero")
    if end_hero is not None:
        try:
            hero_id = int(end_hero)
        except (TypeError, ValueError):
            pass
    if hero_id is None:
        return None
    for ent in game_end.get("entities") or []:
        if ent.get("id") != hero_id:
            continue
        raw = (ent.get("tags") or {}).get("PLAYER_LEADERBOARD_PLACE")
        if raw is None:
            return None
        try:
            place = int(raw)
        except (TypeError, ValueError):
            return None
        return place if place > 0 else None
    return None
