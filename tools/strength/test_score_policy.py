# -*- coding: utf-8 -*-
"""Locks for the turn-dependent matchup score (design §5)."""
from __future__ import annotations

import unittest

from tools.strength.score_policy import (
    T1_GRID,
    W_FLOOR,
    baseline_score,
    damage_lambda,
    matchup_score,
    step_weight,
    ten_curves,
    tie_weight,
    two_segment_weight,
)


class TieWeightTests(unittest.TestCase):
    def test_locked_before_turn_6_and_floor_after_t1(self) -> None:
        for t1 in T1_GRID:
            for turn in (1, 5):
                self.assertEqual(tie_weight(turn, t1), 1.0)
            for turn in (t1, t1 + 3, 20):
                self.assertEqual(tie_weight(turn, t1), W_FLOOR)

    def test_linear_midpoint(self) -> None:
        # t_lock=5, t1=9 → turn 7 is halfway from 1 to 0.6.
        self.assertAlmostEqual(tie_weight(7, 9), 0.8)


class OrderingTests(unittest.TestCase):
    def test_high_tie_beats_high_win_on_every_turn(self) -> None:
        for t1 in T1_GRID:
            for turn in (1, 5, 6, 8, 9, 12, 15, 18):
                high_tie = matchup_score(0.2, 0.8, turn, t1=t1)
                high_win = matchup_score(0.6, 0.1, turn, t1=t1)
                self.assertGreater(high_tie, high_win, msg=f"t1={t1} turn={turn}")


class DamageTermTests(unittest.TestCase):
    def test_no_win_zeros_deal_term(self) -> None:
        plain = matchup_score(0.0, 0.2, 12, t1=9, td=5, length=3, alpha=0.1, beta=0.0, z_deal=4.0)
        self.assertAlmostEqual(plain, matchup_score(0.0, 0.2, 12, t1=9))

    def test_no_loss_zeros_take_term(self) -> None:
        plain = matchup_score(0.4, 0.6, 12, t1=9, td=5, length=3, alpha=0.0, beta=0.1, z_take=3.0)
        self.assertAlmostEqual(plain, matchup_score(0.4, 0.6, 12, t1=9))

    def test_lambda_and_hand_score(self) -> None:
        self.assertEqual(damage_lambda(5, 5, 3), 0.0)
        self.assertAlmostEqual(damage_lambda(8, 5, 3), 1.0)
        self.assertAlmostEqual(damage_lambda(6, 5, 3), 1.0 / 3.0)
        # turn 12 ≥ t1=9 so w=0.6; td=5, L=3 so λ=1; win and loss both present.
        s = matchup_score(
            0.5, 0.2, 12, t1=9, td=5, length=3, alpha=0.1, beta=0.05, z_deal=2.0, z_take=4.0
        )
        self.assertAlmostEqual(s, 0.5 + 0.6 * 0.2 + 1.0 * (0.1 * 2.0 - 0.05 * 4.0))

    def test_q020_search_path_has_no_damage(self) -> None:
        s = matchup_score(0.5, 0.2, 12, t1=12, alpha=0.0, beta=0.0, z_deal=9.0, z_take=9.0)
        self.assertAlmostEqual(s, 0.5 + tie_weight(12, 12) * 0.2)


class ShapeV2Tests(unittest.TestCase):
    """Design R-score-policy-search-v2 §5: ten curves, bounds, lock, monotone, ordering."""

    def test_exactly_ten_closed_shapes(self) -> None:
        curves = ten_curves()
        self.assertEqual(len(curves), 10)
        families = [c.family for c in curves]
        self.assertEqual(families.count("linear"), 3)
        self.assertEqual(families.count("step"), 3)
        self.assertEqual(families.count("two"), 4)
        names = [c.name for c in curves]
        self.assertEqual(len(names), len(set(names)))

    def test_bounds_lock_and_monotone(self) -> None:
        turns = list(range(1, 25))
        for curve in ten_curves():
            weights = [curve.weight(t) for t in turns]
            for turn, w in zip(turns, weights):
                self.assertGreaterEqual(w, W_FLOOR, msg=curve.name)
                self.assertLessEqual(w, 1.0, msg=curve.name)
                if turn <= 5:
                    self.assertEqual(w, 1.0, msg=f"{curve.name} t={turn}")
            for prev, nxt in zip(weights, weights[1:]):
                self.assertLessEqual(nxt, prev + 1e-12, msg=curve.name)

    def test_known_nodes(self) -> None:
        self.assertEqual(step_weight(8, 9), 1.0)
        self.assertEqual(step_weight(9, 9), W_FLOOR)
        # t_lock=5 → ta=9 is 4 turns; turn 7 is halfway from 1 to 0.8.
        self.assertAlmostEqual(two_segment_weight(7, 9, 15, 0.8), 0.9)
        self.assertAlmostEqual(two_segment_weight(9, 9, 15, 0.8), 0.8)
        # ta=9 → tb=15 is 6 turns; turn 12 is halfway from 0.8 to 0.6.
        self.assertAlmostEqual(two_segment_weight(12, 9, 15, 0.8), 0.7)
        self.assertAlmostEqual(two_segment_weight(15, 9, 15, 0.8), W_FLOOR)
        self.assertAlmostEqual(two_segment_weight(18, 12, 18, 0.9), W_FLOOR)

    def test_high_tie_beats_high_win(self) -> None:
        turns = (1, 5, 6, 8, 9, 12, 15, 18)
        for curve in ten_curves():
            for turn in turns:
                high_tie = curve.score(0.2, 0.8, turn)
                high_win = curve.score(0.6, 0.1, turn)
                self.assertGreater(high_tie, high_win, msg=f"{curve.name} t={turn}")


class BaselineTests(unittest.TestCase):
    def test_old_formula(self) -> None:
        self.assertAlmostEqual(baseline_score(0.2, 0.8, 3), 0.6)
        self.assertAlmostEqual(baseline_score(0.6, 0.1, 14), 0.65)


if __name__ == "__main__":
    unittest.main()
