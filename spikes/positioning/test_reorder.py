# -*- coding: utf-8 -*-
import unittest

from spikes.positioning.reorder import (
    adjacent_swaps,
    card_ids,
    max_attack,
    max_health,
    multiset_equal,
    reorder_items,
    apply_strategy_to_input,
)


def _m(
    card: str,
    atk: int,
    hp: int,
    *,
    taunt: bool = False,
    reborn: bool = False,
    cleave: bool = False,
    adr: list | None = None,
) -> dict:
    data = {
        "MaxAttack": atk,
        "MaxHealth": hp,
        "BaseAttack": atk,
        "BaseHealth": hp,
        "Taunt": taunt,
        "Reborn": reborn,
        "Cleave": cleave,
    }
    if adr is not None:
        data["AdditionalDeathrattles"] = adr
    return {"CardID": card, "_data": data}


class ReorderTests(unittest.TestCase):
    def test_atk_desc_stable(self):
        items = [_m("A", 1, 5), _m("B", 3, 1), _m("C", 3, 9), _m("D", 2, 2)]
        out = reorder_items(items, "atk_desc")
        self.assertEqual(card_ids(out), ["B", "C", "D", "A"])  # B before C (stable)
        self.assertTrue(multiset_equal(card_ids(items), card_ids(out)))

    def test_hp_desc(self):
        items = [_m("A", 9, 1), _m("B", 1, 5), _m("C", 2, 5)]
        out = reorder_items(items, "hp_desc")
        self.assertEqual(card_ids(out), ["B", "C", "A"])

    def test_weights(self):
        items = [_m("A", 4, 1), _m("B", 1, 4)]  # A:5/6/9 vs B:5/9/6 for 1+1 / 1+2 / 2+1
        self.assertEqual(card_ids(reorder_items(items, "atk1_hp1")), ["A", "B"])  # tie → stable
        self.assertEqual(card_ids(reorder_items(items, "atk1_hp2")), ["B", "A"])
        self.assertEqual(card_ids(reorder_items(items, "atk2_hp1")), ["A", "B"])

    def test_rev_and_orig(self):
        items = [_m("A", 1, 1), _m("B", 2, 2), _m("C", 3, 3)]
        self.assertEqual(card_ids(reorder_items(items, "orig")), ["A", "B", "C"])
        self.assertEqual(card_ids(reorder_items(items, "rev_orig")), ["C", "B", "A"])

    def test_taunt_left(self):
        items = [_m("A", 5, 1), _m("B", 1, 1, taunt=True), _m("C", 9, 1, taunt=True)]
        out = reorder_items(items, "taunt_left_atk")
        self.assertEqual(card_ids(out), ["C", "B", "A"])

    def test_apply_preserves_other_side(self):
        inp = {
            "Player": {"Side": {"items": [_m("A", 1, 1), _m("B", 3, 3)]}, "Hero": {"CardID": "H1"}},
            "Opponent": {"Side": {"items": [_m("X", 2, 2)]}, "Hero": {"CardID": "H2"}},
            "turn": 5,
        }
        out = apply_strategy_to_input(inp, "Player", "atk_desc")
        self.assertEqual(card_ids(out["Player"]["Side"]["items"]), ["B", "A"])
        self.assertEqual(card_ids(out["Opponent"]["Side"]["items"]), ["X"])
        self.assertEqual(out["Opponent"]["Hero"]["CardID"], "H2")
        # original untouched
        self.assertEqual(card_ids(inp["Player"]["Side"]["items"]), ["A", "B"])

    def test_max_helpers(self):
        m = _m("Z", 7, 4)
        self.assertEqual(max_attack(m), 7)
        self.assertEqual(max_health(m), 4)

    def test_taunt_pin_hp_noop_without_taunt(self):
        items = [_m("A", 1, 1), _m("B", 9, 9)]
        self.assertEqual(card_ids(reorder_items(items, "taunt_pin_hp")), ["A", "B"])

    def test_taunt_pin_hp(self):
        items = [_m("A", 5, 1), _m("B", 1, 3, taunt=True), _m("C", 1, 9, taunt=True), _m("D", 2, 2)]
        out = reorder_items(items, "taunt_pin_hp")
        self.assertEqual(card_ids(out), ["C", "B", "A", "D"])  # taunts by hp; others keep order

    def test_cleave_adj_tank(self):
        items = [
            _m("T1", 1, 10),
            _m("CL", 5, 1, cleave=True),
            _m("T2", 1, 8),
            _m("W", 1, 1),
        ]
        out = reorder_items(items, "cleave_adj_tank")
        self.assertTrue(multiset_equal(card_ids(items), card_ids(out)))
        # cleave stays; highest tanks fill neighbors
        self.assertEqual(out[1]["CardID"], "CL")
        neighbors = {out[0]["CardID"], out[2]["CardID"]}
        self.assertEqual(neighbors, {"T1", "T2"})

    def test_reborn_dr_right(self):
        items = [
            _m("A", 1, 1),
            _m("R", 1, 1, reborn=True),
            _m("B", 1, 1),
            _m("D", 1, 1, adr=["x"]),
        ]
        out = reorder_items(items, "reborn_dr_right")
        self.assertEqual(card_ids(out), ["A", "B", "R", "D"])

    def test_adjacent_swaps(self):
        items = [_m("A", 1, 1), _m("B", 1, 1), _m("C", 1, 1)]
        swaps = adjacent_swaps(items)
        self.assertEqual(len(swaps), 2)
        self.assertEqual(card_ids(swaps[0]), ["B", "A", "C"])
        self.assertEqual(card_ids(swaps[1]), ["A", "C", "B"])


class StatsTests(unittest.TestCase):
    def test_bh_fdr(self):
        from spikes.positioning.stats import bh_fdr

        # classic: 0.01, 0.04, 0.03, 0.5 with q=0.05, m=4 → reject first three? 
        # p_(1)=0.01 <= 0.0125; p_(2)=0.03 <= 0.025; p_(3)=0.04 <= 0.0375? no 0.04>0.0375
        # wait sorted: 0.01, 0.03, 0.04, 0.5
        # k=1: 0.01 <= 0.0125 yes
        # k=2: 0.03 <= 0.025? no
        # so only first
        flags = bh_fdr([0.01, 0.04, 0.03, 0.5], q=0.05)
        self.assertEqual(flags, [True, False, False, False])

    def test_orig_delta_summary(self):
        from spikes.positioning.stats import summarize_deltas

        s = summarize_deltas([0.0, 0.0, 0.0])
        self.assertEqual(s["mean"], 0.0)
        self.assertEqual(s["fracPositive"], 0.0)


if __name__ == "__main__":
    unittest.main()
