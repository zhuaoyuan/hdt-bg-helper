# -*- coding: utf-8 -*-
"""Final placement from a diagnostic game's game_end entity snapshot.

The standard layer copies placement from the 团子 text. The raw record already
stores PLAYER_LEADERBOARD_PLACE on each hero. This reader uses only that tag
on the local player's hero at game_end.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Iterator

_TOOLS = Path(__file__).resolve().parents[1]
if str(_TOOLS) not in sys.path:
    sys.path.insert(0, str(_TOOLS))

from standard_layer._paths import ensure_spike_paths  # noqa: E402

ensure_spike_paths()
from diag_io import iter_record_lines, records_path  # noqa: E402


def _place_on(snapshot: dict, hero_id: int) -> int | None:
    for ent in snapshot.get("entities") or []:
        if ent.get("id") != hero_id:
            continue
        raw = (ent.get("tags") or {}).get("PLAYER_LEADERBOARD_PLACE")
        if raw is None:
            return None
        return int(raw)
    return None


def final_local_place_from_lines(lines: Iterator[str]) -> int | None:
    """Local hero's leaderboard place on the game_end entity snapshot.

    Hero id is taken from that snapshot when present, otherwise from the last
    earlier snapshot that named context.player.hero. In-progress places are
    not used when the record has no game_end.
    """
    hero_id = None
    game_end: dict | None = None
    for line in lines:
        if "entities" not in line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if row.get("type") != "entities":
            continue
        player = (row.get("context") or {}).get("player") or {}
        hero = player.get("hero")
        if hero is not None:
            hero_id = int(hero)
        if row.get("reason") == "game_end":
            game_end = row
    if game_end is None or hero_id is None:
        return None
    end_hero = ((game_end.get("context") or {}).get("player") or {}).get("hero")
    if end_hero is not None:
        hero_id = int(end_hero)
    return _place_on(game_end, hero_id)


def final_local_place(game_dir: str) -> int | None:
    if not records_path(game_dir):
        return None
    return final_local_place_from_lines(iter_record_lines(game_dir))


def load_final_places(roots: list[str]) -> dict[str, int]:
    """gameId -> final place, for every diag dir under roots that has game_end."""
    out: dict[str, int] = {}
    for root in roots:
        if not root or not os.path.isdir(root):
            continue
        for name in sorted(os.listdir(root)):
            path = os.path.join(root, name)
            if not os.path.isdir(path):
                continue
            place = final_local_place(path)
            if place is not None:
                out[name] = place
    return out
