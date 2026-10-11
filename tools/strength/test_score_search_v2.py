# -*- coding: utf-8 -*-
"""Fit/confirm gate for the ten tie-weight curves (design §3.4)."""
from __future__ import annotations

import unittest

from tools.strength.score_search_v2 import (
    blood_percentiles,
    choose_on_fit,
    judge_confirm,
    split_halves,
)


class SplitTests(unittest.TestCase):
    def test_earlier_ids_fit_and_odd_game_stays_in_confirm(self) -> None:
        fit, confirm = split_halves(["g3", "g1", "g2", "g2"])
        self.assertEqual(fit, ["g1"])
        self.assertEqual(confirm, ["g2", "g3"])


class BloodTests(unittest.TestCase):
    def test_lower_damage_has_higher_percentile(self) -> None:
        u = blood_percentiles([("a", 1.0), ("b", 5.0), ("c", 9.0)])
        self.assertGreater(u["a"], u["b"])
        self.assertGreater(u["b"], u["c"])
        self.assertAlmostEqual(u["a"], 1.0)
        self.assertAlmostEqual(u["c"], 0.0)


class GateTests(unittest.TestCase):
    def test_fit_drops_weaker_end_then_takes_higher_mid(self) -> None:
        rows = [
            {"name": "low-end", "family": "linear", "params": {}, "rhoMid": 0.9, "rhoEnd": 0.1},
            {"name": "best", "family": "step", "params": {"t1": 9}, "rhoMid": 0.4, "rhoEnd": 0.3},
            {"name": "worse-mid", "family": "two", "params": {}, "rhoMid": 0.2, "rhoEnd": 0.5},
        ]
        chosen = choose_on_fit(rows, 0.2)
        self.assertEqual(chosen["name"], "best")
        self.assertFalse(rows[0]["kept"])

    def test_tie_keeps_closed_list_order(self) -> None:
        rows = [
            {"name": "first", "family": "linear", "params": {}, "rhoMid": 0.4, "rhoEnd": 0.2},
            {"name": "second", "family": "step", "params": {}, "rhoMid": 0.4, "rhoEnd": 0.2},
        ]
        chosen = choose_on_fit(rows, 0.2)
        self.assertEqual(chosen["name"], "first")
        self.assertEqual(chosen["tiedNames"], ["first", "second"])

    def test_confirm_needs_five_hundredths_and_end_not_below(self) -> None:
        self.assertTrue(judge_confirm(0.25, 0.20, 0.30, 0.30)["passed"])
        self.assertFalse(judge_confirm(0.249, 0.20, 0.30, 0.30)["passed"])
        self.assertFalse(judge_confirm(0.40, 0.20, 0.29, 0.30)["passed"])
        self.assertFalse(judge_confirm(None, 0.20, 0.30, 0.30)["passed"])


if __name__ == "__main__":
    unittest.main()
