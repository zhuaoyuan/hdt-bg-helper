# -*- coding: utf-8 -*-
"""Synthetic-table unit tests for align + metrics (no live games)."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_TOOLS = _HERE.parent
_REPO = _TOOLS.parent
for p in (_REPO, _TOOLS, _HERE):
    s = str(p)
    if s not in sys.path:
        sys.path.insert(0, s)

from tools.strength_validity.align import (  # noqa: E402
    TurnPair,
    aggregate_games,
    align_turns,
    hdt_score,
)
from tools.strength_validity.metrics import associate, partial_spearman, spearman  # noqa: E402
from tools.strength_validity.report import (  # noqa: E402
    MIN_N_GAMES,
    build_report,
    eval_placement,
    exit3_verdict,
)


class TestMetrics(unittest.TestCase):
    def test_perfect_monotone_positive(self):
        x = list(range(20))
        y = list(range(20))
        a = associate(x, y, n_boot=500, n_perm=500, seed=0)
        self.assertEqual(a["n"], 20)
        self.assertAlmostEqual(a["rho"], 1.0, places=6)
        self.assertTrue(a["significant"])
        self.assertGreater(a["ci95"][0], 0)

    def test_uncorrelated_not_significant(self):
        # deterministic alternating pattern → near zero rho
        x = list(range(40))
        y = [1 if i % 2 == 0 else 0 for i in x]
        a = associate(x, y, n_boot=800, n_perm=800, seed=1)
        self.assertIsNotNone(a["rho"])
        self.assertLess(abs(a["rho"]), 0.25)
        self.assertFalse(a["significant"])

    def test_partial_removes_confounder(self):
        # y driven by z; x = z + noise unrelated to y beyond z
        import numpy as np

        rng = np.random.default_rng(0)
        z = rng.normal(size=80)
        y = z + rng.normal(scale=0.05, size=80)
        x = z + rng.normal(scale=0.05, size=80)
        raw = spearman(x, y)
        part = partial_spearman(x, y, z, n_boot=400, n_perm=400, seed=0)
        self.assertGreater(abs(raw["rho"]), 0.8)
        self.assertLess(abs(part["rho"]), 0.35)


class TestAlign(unittest.TestCase):
    def test_align_next_health_prefers_input(self):
        strength = [
            {
                "gameId": "g1",
                "turn": 1,
                "side": "Player",
                "bbVersion": "1.85.0.0",
                "percentile": 0.8,
                "flags": [],
                "hdt": {"winRate": 0.6, "tieRate": 0.2, "lossRate": 0.2},
            },
            {
                "gameId": "g1",
                "turn": 2,
                "side": "Player",
                "bbVersion": "1.85.0.0",
                "percentile": 0.7,
                "flags": ["wide"],
                "hdt": {"winRate": 0.5, "tieRate": 0.0, "lossRate": 0.5},
            },
        ]
        turns = {
            ("g1", 1): {
                "gameId": "g1",
                "turn": 1,
                "placement": 2,
                "result": "win",
                "output": {"friendlyHealth": 40, "winRate": 0.6, "tieRate": 0.2},
            },
            ("g1", 2): {
                "gameId": "g1",
                "turn": 2,
                "placement": 2,
                "result": "loss",
                "output": {"friendlyHealth": 35, "winRate": 0.5, "tieRate": 0.0},
            },
            ("g1", 3): {
                "gameId": "g1",
                "turn": 3,
                "placement": 2,
                "output": {"friendlyHealth": 30},
            },
        }
        health = {("g1", 2): 36, ("g1", 3): 31}
        pairs = align_turns(strength, turns, health, max_turn=12)
        self.assertEqual(len(pairs), 2)
        self.assertEqual(pairs[0].next_health, 36)
        self.assertEqual(pairs[0].health_source, "input")
        self.assertEqual(pairs[1].next_health, 31)
        games = aggregate_games(pairs)
        self.assertEqual(len(games), 1)
        self.assertEqual(games[0].placement, 2)
        self.assertAlmostEqual(games[0].mean_percentile, 0.75)
        self.assertAlmostEqual(games[0].mean_next_health, (36 + 31) / 2)

    def test_hdt_score(self):
        self.assertAlmostEqual(hdt_score(0.4, 0.2), 0.5)

    def test_skip_non_player_and_missing_pct(self):
        strength = [
            {"gameId": "g", "turn": 1, "side": "Opponent", "percentile": 0.9},
            {"gameId": "g", "turn": 1, "side": "Player", "percentile": None},
            {"gameId": "g", "turn": 2, "side": "Player", "percentile": 0.1},
        ]
        pairs = align_turns(strength, {}, {}, max_turn=12)
        self.assertEqual(len(pairs), 1)
        self.assertEqual(pairs[0].turn, 2)


class TestReport(unittest.TestCase):
    def test_exit3_sample_insufficient(self):
        # build < MIN_N_GAMES placed games with monotone signal
        pairs: list[TurnPair] = []
        for i in range(6):
            gid = f"g{i}"
            place = i + 1
            pct = 1.0 - i * 0.1  # higher pct → better place
            pairs.append(
                TurnPair(
                    game_id=gid,
                    turn=1,
                    percentile=pct,
                    hdt=pct,
                    next_health=40 + int(10 * pct),
                    health_source="input",
                    placement=place,
                )
            )
        report = build_report(
            pairs,
            bb_version="test",
            strength_path="x",
            max_turn=12,
            n_boot=200,
            n_perm=200,
            seed=0,
        )
        self.assertLess(report["placement"]["n_games"], MIN_N_GAMES)
        self.assertEqual(report["exit3"]["exit3"], "sample_insufficient")
        self.assertEqual(report["exit3"]["adr0003"], "evidence_insufficient")
        self.assertTrue(report["recommend_more_paired_games"])

    def test_exit3_pass_synthetic(self):
        pairs: list[TurnPair] = []
        for i in range(16):
            gid = f"g{i}"
            place = (i % 8) + 1
            pct = 1.0 - (place - 1) * 0.12 + (i * 0.001)
            hp = 50 - place * 3
            pairs.append(
                TurnPair(
                    game_id=gid,
                    turn=1,
                    percentile=pct,
                    hdt=0.5,  # weak HDT so partial can still show pct
                    next_health=hp,
                    health_source="input",
                    placement=place,
                )
            )
        report = build_report(
            pairs,
            bb_version="test",
            strength_path="x",
            max_turn=12,
            n_boot=800,
            n_perm=800,
            seed=0,
        )
        self.assertEqual(report["placement"]["verdict"], "significant_ok")
        self.assertEqual(report["next_health"]["game_level"]["verdict"], "significant_ok")
        self.assertEqual(report["exit3"]["exit3"], "pass")
        self.assertEqual(report["exit3"]["adr0003"], "no_trigger")


if __name__ == "__main__":
    unittest.main()
