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
    tie_weight,
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


class BaselineTests(unittest.TestCase):
    def test_old_formula(self) -> None:
        self.assertAlmostEqual(baseline_score(0.2, 0.8, 3), 0.6)
        self.assertAlmostEqual(baseline_score(0.6, 0.1, 14), 0.65)


if __name__ == "__main__":
    unittest.main()
