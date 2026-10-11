# -*- coding: utf-8 -*-
"""Last-3 selection and the no-damage validity gate."""
from __future__ import annotations

import unittest

from tools.strength.pool import Board
from tools.strength.score_search import (
    judge_fallback,
    last_combat_values,
    mean_or_none,
    ranked_game_points,
)


def _board(game: str, turn: int, place) -> Board:
    return Board(
        board_id=f"{game}|t{turn}|Player",
        game_id=game,
        turn=turn,
        side="Player",
        bb_version="1.85.0.0",
        input={},
        board_hash="h",
        shell_hash="s",
        is_ghost=False,
        status="ready",
        game_dir="",
        label={"placement": place},
    )


class LastCombatTests(unittest.TestCase):
    def test_uses_final_three_not_the_highest(self) -> None:
        vals = last_combat_values([(1, 0.9), (2, 0.2), (10, 0.4), (11, None), (12, 0.5)])
        self.assertEqual(vals, [0.4, 0.5])
        self.assertAlmostEqual(mean_or_none(vals), 0.45)

    def test_ranked_points_skip_games_without_placement(self) -> None:
        a = _board("g1", 8, 1)
        b = _board("g1", 9, 1)
        c = _board("g1", 10, 1)
        d = _board("g2", 4, None)
        pct = {a.board_id: 0.2, b.board_id: 0.4, c.board_id: 0.6, d.board_id: 0.9}
        rows = ranked_game_points([a, b, c, d], pct)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["gameId"], "g1")
        self.assertAlmostEqual(rows[0]["meanQ"], 0.4)
        self.assertEqual(rows[0]["negPlacement"], -1.0)

    def test_raw_placement_overrides_turn_label(self) -> None:
        a = _board("g1", 10, 8)
        b = _board("g2", 10, None)
        pct = {a.board_id: 0.2, b.board_id: 0.9}
        rows = ranked_game_points([a, b], pct, placement_by_game={"g2": 3})
        self.assertEqual([r["gameId"] for r in rows], ["g2"])
        self.assertEqual(rows[0]["placement"], 3)


class JudgmentTests(unittest.TestCase):
    def test_needs_all_three(self) -> None:
        self.assertTrue(judge_fallback(0.4, 0.2, 12)["valid"])
        self.assertFalse(judge_fallback(0.4, 0.2, 11)["valid"])
        self.assertFalse(judge_fallback(0.2, 0.4, 20)["valid"])
        self.assertFalse(judge_fallback(-0.1, -0.2, 20)["valid"])
        self.assertFalse(judge_fallback(0.2, 0.2, 20)["valid"])


if __name__ == "__main__":
    unittest.main()
