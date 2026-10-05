# -*- coding: utf-8 -*-
"""Deterministic reference panel: earliest K games per bucket."""
from __future__ import annotations

from dataclasses import dataclass

from .config import PANEL_GAMES
from .pool import Board, game_time_key


@dataclass(frozen=True)
class Panel:
    bb_version: str
    turn: int
    game_ids: tuple[str, ...]  # ordered earliest→latest, len ≤ K
    board_ids: tuple[str, ...]

    @property
    def k(self) -> int:
        return len(self.game_ids)


def select_panel_games(boards: list[Board], k: int = PANEL_GAMES) -> list[str]:
    """Earliest k distinct gameIds (lexicographic = chronological for our id format)."""
    games = sorted({b.game_id for b in boards}, key=game_time_key)
    return games[:k]


def build_panel(
    boards: list[Board],
    *,
    bb_version: str,
    turn: int,
    k: int = PANEL_GAMES,
) -> Panel:
    game_ids = select_panel_games(boards, k=k)
    gset = set(game_ids)
    board_ids = tuple(sorted(b.board_id for b in boards if b.game_id in gset))
    return Panel(
        bb_version=bb_version,
        turn=turn,
        game_ids=tuple(game_ids),
        board_ids=board_ids,
    )


def panel_boards(boards: list[Board], panel: Panel) -> list[Board]:
    gset = set(panel.game_ids)
    return [b for b in boards if b.game_id in gset]


def needed_pairs(
    boards: list[Board],
    panel: Panel,
) -> list[tuple[Board, Board]]:
    """All (row, col) where col in panel, different game (leave-one-game).

    Directional: each direction is a separate pair (no antisymmetry).
    """
    by_id = {b.board_id: b for b in boards}
    cols = [by_id[bid] for bid in panel.board_ids if bid in by_id]
    out: list[tuple[Board, Board]] = []
    for row in boards:
        for col in cols:
            if row.game_id == col.game_id:
                continue
            out.append((row, col))
    return out


def needed_pairs_for_game(
    boards: list[Board],
    panel: Panel,
    game_id: str,
) -> list[tuple[Board, Board]]:
    """Incremental: pairs involving game_id as row, or as new panel column.

    - Always: each board in game_id vs each panel board (other games).
    - If game_id is on the panel: every other board in the bucket vs each
      board of game_id (so peers can fight the new panel columns).
    """
    by_id = {b.board_id: b for b in boards}
    cols = [by_id[bid] for bid in panel.board_ids if bid in by_id]
    game_boards = [b for b in boards if b.game_id == game_id]
    on_panel = game_id in set(panel.game_ids)
    out: list[tuple[Board, Board]] = []
    seen: set[tuple[str, str]] = set()

    def add(row: Board, col: Board) -> None:
        if row.game_id == col.game_id:
            return
        key = (row.board_id, col.board_id)
        if key in seen:
            return
        seen.add(key)
        out.append((row, col))

    for row in game_boards:
        for col in cols:
            add(row, col)

    if on_panel:
        new_cols = game_boards
        for row in boards:
            if row.game_id == game_id:
                continue
            for col in new_cols:
                add(row, col)

    return out
