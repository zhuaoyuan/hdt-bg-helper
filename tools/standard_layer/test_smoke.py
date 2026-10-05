# -*- coding: utf-8 -*-
"""Smoke tests for standard_layer (no real game data required)."""
from __future__ import annotations

import unittest

from tools.standard_layer.crosscheck import board_match, crosscheck_turn
from tools.standard_layer.status import classify_status
from tools.standard_layer.tuanzi import parse_minions_zh, parse_tuanzi_file
import os
import tempfile


class StatusTests(unittest.TestCase):
    def test_ready_solo_with_output(self):
        combat = {
            "hasOutput": True,
            "hasInput": True,
            "inputRef": {"lineSeq": 1},
            "pickMeta": {"usedAfter2022": True},
        }
        st, reasons = classify_status(
            meta={"isBattlegroundsDuosMatch": False, "disabled": False, "probeInitError": None},
            session_reason="game_start",
            combat=combat,
            tuanzi_turn={"kind": "actual"},
            gap_flags=["opp_unknown_hand:2"],
        )
        self.assertEqual(st, "ready")
        self.assertEqual(reasons, [])

    def test_missing_direct_dc(self):
        combat = {"hasOutput": False, "hasInput": False, "inputRef": {}, "pickMeta": {}}
        st, _ = classify_status(
            meta={},
            session_reason="game_start",
            combat=combat,
            tuanzi_turn={"kind": "direct_dc"},
            gap_flags=["no_input"],
        )
        self.assertEqual(st, "missing")

    def test_partial_mid_game(self):
        combat = {
            "hasOutput": True,
            "hasInput": True,
            "inputRef": {"lineSeq": 1},
            "pickMeta": {"usedAfter2022": True},
        }
        st, reasons = classify_status(
            meta={},
            session_reason="enabled_mid_game",
            combat=combat,
            tuanzi_turn=None,
            gap_flags=[],
        )
        self.assertEqual(st, "partial")
        self.assertIn("enabled_mid_game", reasons)


class CrosscheckTests(unittest.TestCase):
    def test_base_health_matches_tuanzi(self):
        diag = [{"atk": 10, "health": 12, "baseAtk": 10, "baseHealth": 10, "golden": False}]
        tz = [{"atk": 10, "health": 10, "golden": False}]
        self.assertTrue(board_match(diag, tz))

    def test_sim_ok(self):
        combat = {
            "playerMinions": [{"atk": 1, "health": 1, "golden": False}],
            "oppMinions": [],
            "outputSummary": {
                "winRate": 1.0,
                "tieRate": 0.0,
                "lossRate": 0.0,
                "myDeathRate": 0.0,
                "theirDeathRate": 0.0,
                "simulationCount": 19998,
            },
        }
        tz = {
            "kind": "actual",
            "mine": [{"atk": 1, "health": 1, "golden": False}],
            "opp": [],
            "sim": {
                "count": 19998,
                "win": 100.0,
                "tie": 0.0,
                "loss": 0.0,
                "myLethal": 0.0,
                "theirLethal": 0.0,
            },
        }
        cross = crosscheck_turn(combat, tz)
        self.assertTrue(cross["strictPass"])


class TuanziParseTests(unittest.TestCase):
    def test_parse_minions(self):
        ms = parse_minions_zh("小随从（1-2）；大金（金）（3-4）")
        self.assertEqual(len(ms), 2)
        self.assertEqual(ms[0]["atk"], 1)
        self.assertTrue(ms[1]["golden"])

    def test_parse_file(self):
        text = "\n".join([
            "第1回合，英雄甲 VS 英雄乙",
            "我方随从：兵（1-1）；",
            "对方随从：",
            "模拟结果（模拟19998次）：0%抬走对面，100%赢，0%平，0%输，0%被抬走",
            "实际结果：赢，打对面2点伤害~",
            "游戏结束，战绩：第3名",
        ])
        with tempfile.TemporaryDirectory() as td:
            p = os.path.join(td, "2026年10月05日.txt")
            with open(p, "w", encoding="utf-8") as f:
                f.write(text)
            games = parse_tuanzi_file(p)
        self.assertEqual(len(games), 1)
        self.assertEqual(games[0]["place"], 3)
        self.assertEqual(games[0]["turns"][1]["actualRes"], "win")
        self.assertEqual(games[0]["turns"][1]["actualDmg"], 2)


if __name__ == "__main__":
    unittest.main()
