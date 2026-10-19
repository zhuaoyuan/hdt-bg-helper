# -*- coding: utf-8 -*-
"""Tests for local final placement and the per-game rules block."""
from __future__ import annotations

import unittest

from tools.standard_layer.combat import rules_block
from tools.standard_layer.placement import final_local_place


def _entities(reason: str, hero: int | None, place=None) -> dict:
    tags = {}
    if place is not None:
        tags["PLAYER_LEADERBOARD_PLACE"] = place
    return {
        "type": "entities",
        "reason": reason,
        "context": {"player": {"hero": hero}},
        "entities": [{"id": hero, "tags": tags}] if hero is not None else [],
    }


class PlacementTests(unittest.TestCase):
    def test_reads_local_final_place(self):
        records = [
            _entities("combat_start", 5),
            _entities("game_end", 5, 3),
        ]
        self.assertEqual(final_local_place(records), 3)

    def test_zero_place_is_unknown(self):
        records = [_entities("game_end", 5, 0)]
        self.assertIsNone(final_local_place(records))

    def test_missing_game_end(self):
        records = [_entities("combat_start", 5)]
        self.assertIsNone(final_local_place(records))

    def test_falls_back_to_earlier_hero_id(self):
        records = [
            _entities("combat_start", 7),
            {
                "type": "entities",
                "reason": "game_end",
                "context": {"player": {}},
                "entities": [{"id": 7, "tags": {"PLAYER_LEADERBOARD_PLACE": 2}}],
            },
        ]
        self.assertEqual(final_local_place(records), 2)


class RulesBlockTests(unittest.TestCase):
    def test_input_preferred(self):
        combat = {
            "input": {"availableRaces": ["BEAST", "MECHANICAL"], "DamageCap": 15},
            "context": {"availableRaces": ["BEAST"], "anomalyDbfId": None},
        }
        rules = rules_block(combat, {"isBattlegroundsDuosMatch": False})
        self.assertEqual(rules["availableRaces"], ["BEAST", "MECHANICAL"])
        self.assertEqual(rules["damageCap"], 15)
        self.assertIsNone(rules["anomalyDbfId"])
        self.assertFalse(rules["duos"])

    def test_context_fallback(self):
        combat = {
            "input": {},
            "context": {"availableRaces": ["DEMON"], "anomalyDbfId": 123},
        }
        rules = rules_block(combat, {"isBattlegroundsDuosMatch": True})
        self.assertEqual(rules["availableRaces"], ["DEMON"])
        self.assertEqual(rules["anomalyDbfId"], 123)
        self.assertTrue(rules["duos"])

    def test_input_serialized_race_list(self):
        combat = {
            "input": {
                "availableRaces": {
                    "$type": "System.Collections.Generic.List<HearthDb.Enums.Race>",
                    "items": ["BEAST", "MECHANICAL"],
                }
            },
            "context": {"availableRaces": ["BEAST"]},
        }
        rules = rules_block(combat, {})
        self.assertEqual(rules["availableRaces"], ["BEAST", "MECHANICAL"])

    def test_missing_is_none(self):
        rules = rules_block({}, {})
        self.assertIsNone(rules["availableRaces"])
        self.assertIsNone(rules["anomalyDbfId"])
        self.assertIsNone(rules["damageCap"])


if __name__ == "__main__":
    unittest.main()
