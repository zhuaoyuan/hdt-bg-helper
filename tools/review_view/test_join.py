# -*- coding: utf-8 -*-
"""Unit tests for join + strength_state (fixture only)."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tools.review_view.page import render_html, write_review
from tools.review_view.join import build_game_review, filter_turns, index_player_strength
from tools.review_view.model import strength_state_for, turn_detail_text


class StrengthStateTests(unittest.TestCase):
    def test_non_ready(self):
        self.assertEqual(
            strength_state_for(status="partial", strength_row={"percentile": 0.5, "level": "L0"}),
            "non_ready",
        )

    def test_missing(self):
        self.assertEqual(strength_state_for(status="ready", strength_row=None), "missing")

    def test_insufficient(self):
        self.assertEqual(
            strength_state_for(status="ready", strength_row={"level": "insufficient", "S": 0.4}),
            "insufficient",
        )

    def test_relaxed_l1(self):
        self.assertEqual(
            strength_state_for(
                status="ready",
                strength_row={"level": "L1", "percentile": 0.4, "flags": []},
            ),
            "relaxed",
        )

    def test_wide_flag(self):
        self.assertEqual(
            strength_state_for(
                status="ready",
                strength_row={"level": "L0", "percentile": 0.5, "flags": ["wide"], "widthPts": 18},
            ),
            "wide",
        )

    def test_wide_by_width(self):
        self.assertEqual(
            strength_state_for(
                status="ready",
                strength_row={"level": "L0", "percentile": 0.5, "flags": [], "widthPts": 22},
            ),
            "wide",
        )

    def test_ok(self):
        self.assertEqual(
            strength_state_for(
                status="ready",
                strength_row={"level": "L0", "percentile": 0.7, "flags": [], "widthPts": 10},
            ),
            "ok",
        )


class JoinTests(unittest.TestCase):
    def setUp(self):
        self.turns = [
            {
                "gameId": "g1",
                "turn": 1,
                "combat": 1,
                "myHero": "HeroA",
                "oppHero": "Opp1",
                "result": "win",
                "damage": 2,
                "resultSource": "tuanzi",
                "status": "ready",
                "placement": 3,
                "output": {"winRate": 0.6, "tieRate": 0.1, "lossRate": 0.3},
                "meta": {"bbVersion": "1.85.0.0"},
            },
            {
                "gameId": "g1",
                "turn": 2,
                "combat": 2,
                "myHero": "HeroA",
                "oppHero": "Opp2",
                "result": "loss",
                "damage": 5,
                "resultSource": "tuanzi",
                "status": "ready",
                "placement": 3,
                "output": {"winRate": 0.2, "tieRate": 0.0, "lossRate": 0.8},
                "meta": {"bbVersion": "1.85.0.0"},
            },
            {
                "gameId": "g1",
                "turn": 3,
                "combat": 3,
                "myHero": "HeroA",
                "oppHero": "Opp3",
                "result": None,
                "damage": None,
                "status": "partial",
                "placement": 3,
                "meta": {"bbVersion": "1.85.0.0"},
            },
        ]
        self.strength = [
            {
                "gameId": "g1",
                "turn": 1,
                "side": "Player",
                "S": 0.55,
                "percentile": 0.6,
                "ci95": [0.5, 0.7],
                "widthPts": 20,
                "level": "L0",
                "flags": [],
                "hdt": {"winRate": 0.6, "tieRate": 0.1, "lossRate": 0.3},
                "engineVersion": "0.1.0",
                "bbVersion": "1.85.0.0",
            },
            {
                "gameId": "g1",
                "turn": 2,
                "side": "Player",
                "S": 0.3,
                "percentile": 0.2,
                "ci95": [0.05, 0.4],
                "widthPts": 35,
                "level": "L0",
                "flags": ["wide"],
                "engineVersion": "0.1.0",
            },
        ]

    def test_filter_and_index(self):
        rows = filter_turns(self.turns, "g1")
        self.assertEqual(len(rows), 3)
        idx = index_player_strength(self.strength, "g1")
        self.assertEqual(set(idx), {1, 2})

    def test_build_states(self):
        game = build_game_review(
            game_id="g1",
            turn_rows=self.turns,
            strength_by_turn=index_player_strength(self.strength, "g1"),
            tiers_by_turn={1: (2, 3), 2: (3, 3)},
            boards_by_turn={1: ("boards/T01_player.png", "boards/T01_opponent.png")},
        )
        self.assertEqual(game.placement, 3)
        self.assertEqual(game.turns[0].strength_state, "ok")
        self.assertEqual(game.turns[1].strength_state, "wide")
        self.assertEqual(game.turns[2].strength_state, "non_ready")
        self.assertIn("区间偏宽", turn_detail_text(game.turns[1]))
        self.assertEqual(game.turns[0].my_tavern_tier, 2)
        self.assertEqual(game.turns[0].opp_tavern_tier, 3)
        self.assertEqual(game.turns[2].strength_state, "non_ready")

    def test_missing_strength_row(self):
        game = build_game_review(
            game_id="g1",
            turn_rows=self.turns[:1],
            strength_by_turn={},
        )
        self.assertEqual(game.turns[0].strength_state, "missing")
        self.assertIn("尚无 strength", turn_detail_text(game.turns[0]))


class HtmlTests(unittest.TestCase):
    def test_render_contains_fields(self):
        game = build_game_review(
            game_id="g1",
            turn_rows=[
                {
                    "gameId": "g1",
                    "turn": 1,
                    "myHero": "HeroA",
                    "oppHero": "Opp1",
                    "result": "win",
                    "damage": 2,
                    "status": "ready",
                    "placement": 4,
                    "output": {"winRate": 0.5, "tieRate": 0.0, "lossRate": 0.5},
                    "meta": {"bbVersion": "1.85.0.0"},
                }
            ],
            strength_by_turn={
                1: {
                    "side": "Player",
                    "S": 0.5,
                    "percentile": 0.55,
                    "ci95": [0.4, 0.7],
                    "widthPts": 12,
                    "level": "L0",
                    "flags": [],
                    "hdt": {"winRate": 0.5, "tieRate": 0.0, "lossRate": 0.5},
                    "engineVersion": "0.1.0",
                }
            },
            tiers_by_turn={1: (4, 3)},
            boards_by_turn={1: ("boards/T01_player.png", None)},
        )
        html = render_html(game)
        self.assertIn("g1", html)
        self.assertIn("当场模拟", html)
        self.assertIn("my_tavern_tier", html)
        self.assertIn("strength_state", html)
        with tempfile.TemporaryDirectory() as td:
            path = write_review(game, Path(td))
            self.assertTrue(path.is_file())
            self.assertTrue((Path(td) / "model.json").is_file())


if __name__ == "__main__":
    unittest.main()
