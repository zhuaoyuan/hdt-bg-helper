# -*- coding: utf-8 -*-
import unittest

from cross_input import make_cross_input, score_of


class CrossInputTests(unittest.TestCase):
    def test_score(self):
        self.assertEqual(score_of(1.0, 0.0), 1.0)
        self.assertEqual(score_of(0.0, 1.0), 0.5)
        self.assertEqual(score_of(0.4, 0.2), 0.5)

    def test_graft_controlled(self):
        src = {
            "$id": 1,
            "$type": "BobsBuddy.Simulation.Input, BobsBuddy",
            "DamageCap": 5,
            "turn": 3,
            "Anomaly": None,
            "availableRaces": None,
            "Player": {
                "$id": 2,
                "Side": {
                    "$id": 3,
                    "items": [{"$id": 4, "CardID": "X", "ControlledByPlayer": True}],
                },
            },
            "Opponent": {
                "$id": 5,
                "Side": {
                    "$id": 6,
                    "items": [{"$id": 7, "CardID": "Y", "ControlledByPlayer": False}],
                },
            },
        }
        other = {
            "$id": 10,
            "DamageCap": 5,
            "turn": 3,
            "Player": {
                "$id": 11,
                "Side": {
                    "$id": 12,
                    "items": [{"$id": 13, "CardID": "Z", "ControlledByPlayer": True}],
                },
            },
            "Opponent": src["Opponent"],
        }
        out = make_cross_input(src, other, player_side="Player", opp_side="Player")
        self.assertFalse(out["isDuos"])
        self.assertEqual(out["DamageCap"], 5)
        p_items = out["Player"]["Side"]["items"]
        o_items = out["Opponent"]["Side"]["items"]
        self.assertTrue(p_items[0]["ControlledByPlayer"])
        self.assertFalse(o_items[0]["ControlledByPlayer"])
        self.assertEqual(o_items[0]["CardID"], "Z")
        ids = {out["$id"], out["Player"]["$id"], out["Opponent"]["$id"]}
        self.assertEqual(len(ids), 3)


if __name__ == "__main__":
    unittest.main()
