# -*- coding: utf-8 -*-
"""Unit tests for enumerate sampling / top-k / features."""
from __future__ import annotations

import unittest
from types import SimpleNamespace

from spikes.positioning.enumerate_run import (
    sample_boards,
    select_top_bottom,
    tertile_label,
    top_k_count,
)
from spikes.positioning.features import (
    adj_swap_distance,
    extract_perm_features,
    kendall_tau,
)
from spikes.positioning.reorder import apply_order_to_input


def _minion(**kw):
    d = {
        "CardID": kw.get("CardID", "X"),
        "_data": {
            "MaxAttack": kw.get("atk", 1),
            "MaxHealth": kw.get("hp", 1),
            "Taunt": kw.get("taunt", False),
            "Reborn": kw.get("reborn", False),
        },
    }
    return d


def _board(bid: str, turn: int, items: list, s: float = 0.5):
    inp = {"Player": {"Side": {"items": items}}, "Opponent": {"Side": {"items": []}}}
    return SimpleNamespace(
        board_id=bid,
        game_id="g1",
        turn=turn,
        side="Player",
        input=inp,
    )


class TestTertile(unittest.TestCase):
    def test_labels(self):
        # n=6 → lo=2, hi=4 → ranks 0,1 low; 2,3 mid; 4,5 high
        self.assertEqual([tertile_label(i, 6) for i in range(6)], ["low", "low", "mid", "mid", "high", "high"])

    def test_top_k(self):
        self.assertEqual(top_k_count(6, 0.2), 2)  # ceil(1.2)=2
        self.assertEqual(top_k_count(5, 0.2), 1)  # ceil(1.0)=1
        self.assertEqual(top_k_count(24, 0.2), 5)


class TestSample(unittest.TestCase):
    def test_per_stratum(self):
        items = [_minion(CardID="A"), _minion(CardID="B"), _minion(CardID="C")]
        pool = [_board(f"b{i}", 3, items) for i in range(9)]
        s_orig = {f"b{i}": float(i) / 10 for i in range(9)}
        picked, meta = sample_boards(pool, s_orig, per_stratum=2, seed="t", turn=3)
        self.assertEqual(len(picked), 6)
        by = {}
        for p in picked:
            by.setdefault(p["stratum"], 0)
            by[p["stratum"]] += 1
        self.assertEqual(by, {"low": 2, "mid": 2, "high": 2})
        self.assertEqual(meta["shortfall"], {})


class TestTopBottom(unittest.TestCase):
    def test_expand_ties(self):
        rows = [
            {"permId": 0, "S": 0.9},
            {"permId": 1, "S": 0.8},
            {"permId": 2, "S": 0.8},
            {"permId": 3, "S": 0.1},
            {"permId": 4, "S": 0.05},
        ]
        # n=5, top 20% → k=1; threshold 0.9 → only 1
        top, bottom, extra = select_top_bottom(rows, 0.2)
        self.assertEqual(len(top), 1)
        self.assertEqual(extra, 0)
        # if two share best
        rows2 = [
            {"permId": 0, "S": 0.9},
            {"permId": 1, "S": 0.9},
            {"permId": 2, "S": 0.5},
            {"permId": 3, "S": 0.1},
            {"permId": 4, "S": 0.05},
        ]
        top2, _, extra2 = select_top_bottom(rows2, 0.2)
        self.assertEqual(len(top2), 2)
        self.assertEqual(extra2, 1)


class TestFeatures(unittest.TestCase):
    def test_taunt_left(self):
        items = [
            _minion(CardID="T", taunt=True, atk=1, hp=5),
            _minion(CardID="A", atk=5, hp=1),
            _minion(CardID="B", atk=2, hp=2),
        ]
        f0 = extract_perm_features(items, [0, 1, 2])
        self.assertEqual(f0["tauntLeftmost"], 1.0)
        f1 = extract_perm_features(items, [1, 0, 2])
        self.assertEqual(f1["tauntLeftmost"], 0.0)

    def test_kendall_identity(self):
        self.assertAlmostEqual(kendall_tau([0, 1, 2], [0, 1, 2]), 1.0)
        self.assertAlmostEqual(kendall_tau([2, 1, 0], [0, 1, 2]), -1.0)

    def test_adj_swap(self):
        self.assertEqual(adj_swap_distance([0, 1, 2]), 0)
        self.assertEqual(adj_swap_distance([1, 0, 2]), 1)

    def test_apply_order(self):
        items = [_minion(CardID="A"), _minion(CardID="B"), _minion(CardID="C")]
        inp = {"Player": {"Side": {"items": items}}}
        out = apply_order_to_input(inp, "Player", [2, 0, 1])
        ids = [m["CardID"] for m in out["Player"]["Side"]["items"]]
        self.assertEqual(ids, ["C", "A", "B"])


if __name__ == "__main__":
    unittest.main()
