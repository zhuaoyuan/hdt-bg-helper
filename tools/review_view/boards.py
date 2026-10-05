# -*- coding: utf-8 -*-
"""Resolve board PNGs and tavern tiers for a game."""
from __future__ import annotations

import shutil
from pathlib import Path
from typing import Optional

from tools.standard_layer.combat import get_player_obj, iter_game_combats


def tiers_from_combats(game_dir: str) -> dict[int, tuple[Optional[int], Optional[int]]]:
    """turn -> (player Tier, opponent Tier) from BB Input."""
    _meta, _records, combats = iter_game_combats(game_dir)
    out: dict[int, tuple[Optional[int], Optional[int]]] = {}
    for c in combats:
        turn = c.get("turn")
        if turn is None:
            continue
        inp = c.get("input") or {}
        player = get_player_obj(inp, "Player") if isinstance(inp, dict) else None
        opponent = get_player_obj(inp, "Opponent") if isinstance(inp, dict) else None
        my_t = player.get("Tier") if isinstance(player, dict) else None
        opp_t = opponent.get("Tier") if isinstance(opponent, dict) else None
        try:
            my_i = int(my_t) if my_t is not None else None
        except (TypeError, ValueError):
            my_i = None
        try:
            opp_i = int(opp_t) if opp_t is not None else None
        except (TypeError, ValueError):
            opp_i = None
        out[int(turn)] = (my_i, opp_i)
    return out


def _find_game_board_dir(boards_root: Path, game_id: str) -> Optional[Path]:
    if not boards_root.is_dir():
        return None
    direct = boards_root / game_id
    if direct.is_dir():
        return direct
    # board_render may nest under a batch timestamp folder
    matches = [p for p in boards_root.rglob(game_id) if p.is_dir()]
    if len(matches) == 1:
        return matches[0]
    # short suffix
    short = game_id.split("_")[-1] if "_" in game_id else game_id
    matches = [p for p in boards_root.iterdir() if p.is_dir() and (p.name == game_id or p.name.endswith(short))]
    if len(matches) == 1:
        return matches[0]
    nested = [p for p in boards_root.rglob("*") if p.is_dir() and (p.name == game_id or p.name.endswith("_" + short))]
    if len(nested) == 1:
        return nested[0]
    return None


def collect_board_paths(
    boards_root: Optional[Path],
    game_id: str,
    turns: list[int],
    combat_by_turn: Optional[dict[int, int]] = None,
) -> dict[int, tuple[Optional[Path], Optional[Path]]]:
    """Locate player/opponent PNGs per turn under an existing boards tree."""
    out: dict[int, tuple[Optional[Path], Optional[Path]]] = {t: (None, None) for t in turns}
    if boards_root is None:
        return out
    game_dir = _find_game_board_dir(boards_root, game_id)
    if game_dir is None:
        return out
    for turn in turns:
        combat = (combat_by_turn or {}).get(turn)
        player = opponent = None
        if combat is not None:
            p = game_dir / f"T{turn:02d}_c{combat}_player.png"
            o = game_dir / f"T{turn:02d}_c{combat}_opponent.png"
            if p.is_file():
                player = p
            if o.is_file():
                opponent = o
        if player is None or opponent is None:
            # fallback: any matching turn prefix
            for path in sorted(game_dir.glob(f"T{turn:02d}_*_player.png")):
                player = path
                break
            for path in sorted(game_dir.glob(f"T{turn:02d}_*_opponent.png")):
                opponent = path
                break
        out[turn] = (player, opponent)
    return out


def copy_boards_into(
    dest_boards: Path,
    board_paths: dict[int, tuple[Optional[Path], Optional[Path]]],
) -> dict[int, tuple[Optional[str], Optional[str]]]:
    """Copy PNGs into dest_boards/; return relative paths from index.html parent (boards/...)."""
    dest_boards.mkdir(parents=True, exist_ok=True)
    rel: dict[int, tuple[Optional[str], Optional[str]]] = {}
    for turn, (player, opponent) in board_paths.items():
        rp = ro = None
        if player and player.is_file():
            name = f"T{turn:02d}_player.png"
            shutil.copy2(player, dest_boards / name)
            rp = f"boards/{name}"
        if opponent and opponent.is_file():
            name = f"T{turn:02d}_opponent.png"
            shutil.copy2(opponent, dest_boards / name)
            ro = f"boards/{name}"
        rel[turn] = (rp, ro)
    return rel


def render_boards_if_needed(
    game_key: str,
    out_boards_root: Path,
    *,
    offline: bool = True,
) -> Path:
    """Invoke board_render CLI for both sides; return game board directory."""
    from tools.board_render.__main__ import default_roots, resolve_game, run_render

    gid, gdir = resolve_game(default_roots(), game_key)
    run_render(
        gdir,
        gid,
        side="both",
        turn_filter=None,
        out_dir=out_boards_root,
        offline=offline,
        chrome_dir=None,
        compose=False,
    )
    return out_boards_root / gid
