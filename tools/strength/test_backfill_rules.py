# -*- coding: utf-8 -*-
"""Tests for the strength metadata backfill."""
from __future__ import annotations

import unittest

from tools.strength.backfill_rules import annotate


class BackfillRulesTests(unittest.TestCase):
    def test_annotates_and_preserves_identity(self):
        rows = [
            {"gameId": "g1", "turn": 3, "bbVersion": "1.85.0.0", "S": 0.5, "percentile": 0.4}
        ]
        turns = {
            ("g1", 3): {
                "rules": {"availableRaces": ["BEAST"]},
                "meta": {"hdtVersion": "1.58.6.0", "hearthDbVersion": "36.6.0", "hearthstoneBuild": 123},
            }
        }
        report = annotate(rows, turns)
        self.assertEqual(report["annotated"], 1)
        self.assertEqual(rows[0]["rules"], {"availableRaces": ["BEAST"]})
        self.assertEqual(rows[0]["versions"]["hdtVersion"], "1.58.6.0")
        self.assertEqual(rows[0]["S"], 0.5)

    def test_missing_turn_marks_source(self):
        rows = [{"gameId": "g1", "turn": 3, "S": 0.5}]
        report = annotate(rows, {})
        self.assertEqual(report["missingTurnRow"], 1)
        self.assertEqual(rows[0]["rulesSource"], "missing_turn_row")
        self.assertEqual(rows[0]["S"], 0.5)


if __name__ == "__main__":
    unittest.main()
