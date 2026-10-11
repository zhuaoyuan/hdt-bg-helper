# -*- coding: utf-8 -*-
"""Synthetic series tests (no live games, no simulator)."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from tools.progress_view.page import render_html  # noqa: E402
from tools.progress_view.series import build_series, rolling_mean  # noqa: E402


def _player(gid: str, turn: int, pct: float, bb: str = "1.85.0.0") -> dict:
    return {
        "gameId": gid,
        "turn": turn,
        "side": "Player",
        "percentile": pct,
        "bbVersion": bb,
        "simPool": "1.85.0.0",
    }


def _turn(gid: str, turn: int, bb: str = "1.85.0.0", placement=None) -> dict:
    return {
        "gameId": gid,
        "turn": turn,
        "placement": placement,
        "meta": {"bbVersion": bb},
    }


class SeriesTests(unittest.TestCase):
    def test_order_mean_and_survival_source(self) -> None:
        strength = [
            _player("20261002_120000_bbbbbb", 1, 0.2),
            _player("20261002_120000_bbbbbb", 2, 0.4),
            _player("20261001_120000_aaaaaa", 3, 0.2),
            _player("20261003_120000_cccccc", 1, 0.7),
            _player("20261004_120000_dddddd", 4, 0.8, bb="1.88.6.0"),
            {
                "gameId": "20261004_120000_dddddd",
                "turn": 8,
                "side": "Player",
                "percentile": None,
                "bbVersion": "1.88.6.0",
            },
        ]
        turns = [
            _turn("20261002_120000_bbbbbb", 1),
            _turn("20261002_120000_bbbbbb", 6, placement=2),
            _turn("20261001_120000_aaaaaa", 4, placement=1),
            _turn("20261003_120000_cccccc", 2),
            _turn("20260901_120000_oldold", 9, bb="1.78.1.0"),
        ]
        opp = [
            {
                "gameId": "20261001_120000_aaaaaa",
                "turn": 3,
                "side": "Opponent",
                "percentile": 0.25,
                "bbVersion": "1.85.0.0",
            }
        ]
        model = build_series(strength, turns, opp, sim_pool="1.85.0.0", window=2)
        ids = [g["gameId"] for g in model["games"]]
        self.assertEqual(
            ids,
            [
                "20261001_120000_aaaaaa",
                "20261002_120000_bbbbbb",
                "20261003_120000_cccccc",
                "20261004_120000_dddddd",
            ],
        )
        self.assertNotIn("20260901_120000_oldold", ids)
        by = {g["gameId"]: g for g in model["games"]}
        self.assertAlmostEqual(by["20261002_120000_bbbbbb"]["playerMean"], 0.3)
        self.assertEqual(by["20261002_120000_bbbbbb"]["survivalTurns"], 6)
        self.assertEqual(by["20261002_120000_bbbbbb"]["survivalSource"], "turns")
        self.assertEqual(by["20261002_120000_bbbbbb"]["placement"], 2)
        self.assertEqual(by["20261004_120000_dddddd"]["survivalTurns"], 8)
        self.assertEqual(by["20261004_120000_dddddd"]["survivalSource"], "strength")
        self.assertEqual(by["20261004_120000_dddddd"]["playerN"], 1)
        self.assertAlmostEqual(by["20261001_120000_aaaaaa"]["oppMean"], 0.25)
        self.assertGreater(model["trend"]["playerMean"]["rho"], 0)

    def test_rolling_skips_null_in_window_buffer(self) -> None:
        got = rolling_mean([0.1, None, 0.3], 2)
        self.assertAlmostEqual(got[0], 0.1)
        self.assertAlmostEqual(got[1], 0.1)
        self.assertAlmostEqual(got[2], 0.2)

    def test_html_has_both_sides(self) -> None:
        model = build_series(
            [_player("20261001_120000_aaaaaa", 1, 0.4), _player("20261002_120000_bbbbbb", 1, 0.6)],
            [_turn("20261001_120000_aaaaaa", 5), _turn("20261002_120000_bbbbbb", 7)],
            [],
            window=2,
        )
        html = render_html(model)
        self.assertIn("己方", html)
        self.assertIn("对手", html)
        self.assertIn("生存回合", html)
        self.assertIn("20261001_120000_aaaaaa", html)


if __name__ == "__main__":
    unittest.main()
