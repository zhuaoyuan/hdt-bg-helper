# -*- coding: utf-8 -*-
"""Loss-damage summary columns do not replace win/tie/loss counts."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tools.strength.cache import StrengthCache
from tools.strength.loss_summary import expected_taken, summarize_loss_samples, z_take


class SummaryMathTests(unittest.TestCase):
    def test_ignores_wins_and_ties_and_marks_the_cap(self) -> None:
        # +4 win, 0 tie, -3 uncapped loss, -10 on the cap, -10 on the cap.
        got = summarize_loss_samples([4, 0, -3, -10, -10], 10)
        self.assertEqual(got["lossCount"], 3)
        self.assertEqual(got["cappedLossCount"], 2)
        self.assertEqual(got["uncappedLossMedian"], 3.0)
        self.assertEqual(got["lossSampleCount"], 5)

    def test_cap_zero_does_not_censor(self) -> None:
        got = summarize_loss_samples([-32, -8], 0)
        self.assertEqual(got["cappedLossCount"], 0)
        self.assertEqual(got["uncappedLossMedian"], 20.0)

    def test_even_median(self) -> None:
        got = summarize_loss_samples([-2, -4], 15)
        self.assertEqual(got["uncappedLossMedian"], 3.0)

    def test_expected_taken_uses_median_and_cap(self) -> None:
        # 1 uncapped at median 3, 2 capped at 10, 2 non-losses → (3+20)/5.
        self.assertAlmostEqual(
            expected_taken(
                loss_count=3,
                capped_loss_count=2,
                uncapped_median=3.0,
                sample_count=5,
                damage_cap=10,
            ),
            23.0 / 5.0,
        )

    def test_z_take_saturates_when_half_the_losses_are_capped(self) -> None:
        self.assertEqual(
            z_take(loss_count=4, capped_loss_count=2, uncapped_median=3.0, turn_median=3.0),
            1.0,
        )
        self.assertAlmostEqual(
            z_take(loss_count=4, capped_loss_count=1, uncapped_median=6.0, turn_median=3.0),
            2.0,
        )


class CacheWriteTests(unittest.TestCase):
    def test_summary_write_keeps_win_tie_loss(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with StrengthCache(Path(tmp) / "c.sqlite") as cache:
                cache.merge_pair(
                    pair_key="pk",
                    bb_version="1.85.0.0",
                    row_board_hash="r",
                    col_board_hash="c",
                    shell_hash="s",
                    assembler_version="v",
                    sims=10,
                    wins=4.0,
                    ties=3.0,
                    losses=3.0,
                    my_death_rate=0.1,
                    their_death_rate=0.2,
                    av_damage=-1.0,
                    elapsed_ms=11.0,
                )
                cache.write_loss_summary(
                    "pk",
                    loss_count=3,
                    capped_loss_count=1,
                    uncapped_median=4.0,
                    sample_count=10,
                )
                row = cache.get_pair("pk")
            self.assertEqual(row["wins"], 4.0)
            self.assertEqual(row["ties"], 3.0)
            self.assertEqual(row["losses"], 3.0)
            self.assertEqual(row["sims"], 10)
            self.assertEqual(row["lossCount"], 3)
            self.assertEqual(row["cappedLossCount"], 1)
            self.assertEqual(row["uncappedLossMedian"], 4.0)
            self.assertEqual(row["lossSampleCount"], 10)


if __name__ == "__main__":
    unittest.main()
