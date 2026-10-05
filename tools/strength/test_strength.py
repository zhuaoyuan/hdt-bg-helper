# -*- coding: utf-8 -*-
"""Unit tests: key stability, merge, leave-one-game, ghost filter, panel determinism."""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

# unittest discover -s tools/strength → this dir on path; also need tools/ + package root.
_HERE = Path(__file__).resolve().parent
_TOOLS = _HERE.parent
_REPO = _TOOLS.parent
for p in (_REPO, _TOOLS, _HERE):
    s = str(p)
    if s not in sys.path:
        sys.path.insert(0, s)

from tools.strength import ASSEMBLER_VERSION  # noqa: E402
from tools.strength.assembler import make_cross_input, pair_key, score_of  # noqa: E402
from tools.strength.cache import StrengthCache  # noqa: E402
from tools.strength.panel import (  # noqa: E402
    build_panel,
    needed_pairs,
    needed_pairs_for_game,
    select_panel_games,
)
from tools.strength.pool import Board, is_ghost_opponent  # noqa: E402


def _mini_input(card_p: str, card_o: str, *, damage_cap: int = 5, turn: int = 3, opp_hero: str = "X") -> dict:
    return {
        "$id": 1,
        "$type": "BobsBuddy.Simulation.Input, BobsBuddy",
        "DamageCap": damage_cap,
        "turn": turn,
        "Anomaly": None,
        "availableRaces": ["BEAST"],
        "Player": {
            "$id": 2,
            "Hero": {"$id": 20, "CardID": "ME"},
            "Side": {
                "$id": 3,
                "items": [{"$id": 4, "CardID": card_p, "ControlledByPlayer": True}],
            },
        },
        "Opponent": {
            "$id": 5,
            "Hero": {"$id": 21, "CardID": opp_hero},
            "Side": {
                "$id": 6,
                "items": [{"$id": 7, "CardID": card_o, "ControlledByPlayer": False}],
            },
        },
    }


def _board(gid: str, turn: int, side: str, inp: dict, bb: str = "1.85.0.0") -> Board:
    from tools.strength.assembler import board_hash, shell_hash

    return Board(
        board_id=f"{gid}|t{turn}|{side}",
        game_id=gid,
        turn=turn,
        side=side,
        bb_version=bb,
        input=inp,
        board_hash=board_hash(inp, side),
        shell_hash=shell_hash(inp),
        is_ghost=False,
        status="ready",
        game_dir="/tmp",
    )


class AssemblerTests(unittest.TestCase):
    def test_score(self):
        self.assertEqual(score_of(1.0, 0.0), 1.0)
        self.assertEqual(score_of(0.0, 1.0), 0.5)
        self.assertEqual(score_of(0.4, 0.2), 0.5)

    def test_pair_key_stable(self):
        a = _mini_input("A", "B")
        b = _mini_input("C", "D")
        c1 = make_cross_input(a, b, player_side="Player", opp_side="Player")
        c2 = make_cross_input(a, b, player_side="Player", opp_side="Player")
        k1 = pair_key("1.85.0.0", c1)
        k2 = pair_key("1.85.0.0", c2)
        self.assertEqual(k1, k2)
        # key order in source dict must not matter after canonicalize
        c2_reordered = {k: c2[k] for k in reversed(list(c2.keys()))}
        self.assertEqual(k1, pair_key("1.85.0.0", c2_reordered))

    def test_pair_key_changes_with_bb_or_assembler(self):
        a = _mini_input("A", "B")
        b = _mini_input("C", "D")
        cross = make_cross_input(a, b)
        k = pair_key("1.85.0.0", cross)
        self.assertNotEqual(k, pair_key("1.81.2.0", cross))
        self.assertNotEqual(k, pair_key("1.85.0.0", cross, assembler_version="999"))

    def test_graft_controlled(self):
        src = _mini_input("X", "Y")
        other = _mini_input("Z", "Y")
        out = make_cross_input(src, other, player_side="Player", opp_side="Player")
        self.assertFalse(out["isDuos"])
        self.assertEqual(out["DamageCap"], 5)
        self.assertTrue(out["Player"]["Side"]["items"][0]["ControlledByPlayer"])
        self.assertFalse(out["Opponent"]["Side"]["items"][0]["ControlledByPlayer"])
        self.assertEqual(out["Opponent"]["Side"]["items"][0]["CardID"], "Z")


class SimsSufficientTests(unittest.TestCase):
    def test_slack(self):
        from tools.strength.batch import sims_sufficient

        self.assertTrue(sims_sufficient(500, 500))
        self.assertTrue(sims_sufficient(498, 500))
        self.assertTrue(sims_sufficient(490, 500))  # 2% of 500 = 10
        self.assertFalse(sims_sufficient(480, 500))
        self.assertFalse(sims_sufficient(0, 500))


class CacheMergeTests(unittest.TestCase):
    def test_merge_adds_counts(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "c.sqlite"
            with StrengthCache(db) as cache:
                cache.merge_pair(
                    pair_key="k1",
                    bb_version="1.85.0.0",
                    row_board_hash="r",
                    col_board_hash="c",
                    shell_hash="s",
                    assembler_version=ASSEMBLER_VERSION,
                    sims=100,
                    wins=40,
                    ties=10,
                    losses=50,
                    my_death_rate=0.1,
                    their_death_rate=0.2,
                    av_damage=1.0,
                    elapsed_ms=10.0,
                )
                cache.merge_pair(
                    pair_key="k1",
                    bb_version="1.85.0.0",
                    row_board_hash="r",
                    col_board_hash="c",
                    shell_hash="s",
                    assembler_version=ASSEMBLER_VERSION,
                    sims=100,
                    wins=60,
                    ties=0,
                    losses=40,
                    my_death_rate=0.3,
                    their_death_rate=0.0,
                    av_damage=3.0,
                    elapsed_ms=20.0,
                )
                rates = cache.pair_rates("k1")
                self.assertIsNotNone(rates)
                assert rates is not None
                self.assertEqual(rates["sims"], 200)
                self.assertAlmostEqual(rates["winRate"], 0.5)
                self.assertAlmostEqual(rates["tieRate"], 0.05)
                # blended death: (0.1*100 + 0.3*100)/200 = 0.2
                p = cache.get_pair("k1")
                assert p is not None
                self.assertAlmostEqual(float(p["myDeathRate"]), 0.2)


class GhostAndLeaveOneTests(unittest.TestCase):
    def test_ghost_detection(self):
        g = _mini_input("A", "B", opp_hero="TB_BaconShop_HERO_KelThuzad")
        self.assertTrue(is_ghost_opponent(g))
        self.assertTrue(is_ghost_opponent(g, opp_hero_card="TB_BaconShop_HERO_KelThuzad"))
        n = _mini_input("A", "B", opp_hero="HERO_OK")
        self.assertFalse(is_ghost_opponent(n))

    def test_leave_one_game_excludes_same_game(self):
        boards = []
        for gid, card in [("20261001_100000_aaa", "A"), ("20261001_110000_bbb", "B"), ("20261001_120000_ccc", "C")]:
            inp = _mini_input(card, "O", turn=4)
            boards.append(_board(gid, 4, "Player", inp))
            boards.append(_board(gid, 4, "Opponent", inp))
        panel = build_panel(boards, bb_version="1.85.0.0", turn=4, k=30)
        pairs = needed_pairs(boards, panel)
        for row, col in pairs:
            self.assertNotEqual(row.game_id, col.game_id)
        # each of 6 boards vs 4 boards from other 2 games = 6*4 = 24
        self.assertEqual(len(pairs), 24)


class PanelTests(unittest.TestCase):
    def test_panel_deterministic_earliest_k(self):
        boards = []
        gids = [
            "20261005_120000_zzz",
            "20261001_100000_aaa",
            "20261003_110000_bbb",
            "20261002_090000_ccc",
        ]
        for gid in gids:
            inp = _mini_input("P", "O", turn=2)
            boards.append(_board(gid, 2, "Player", inp))
        # shuffle list order — panel must still pick earliest by gameId
        boards = [boards[i] for i in (2, 0, 3, 1)]
        selected = select_panel_games(boards, k=2)
        self.assertEqual(selected, ["20261001_100000_aaa", "20261002_090000_ccc"])
        p1 = build_panel(boards, bb_version="1.85.0.0", turn=2, k=2)
        p2 = build_panel(list(reversed(boards)), bb_version="1.85.0.0", turn=2, k=2)
        self.assertEqual(p1.game_ids, p2.game_ids)
        self.assertEqual(p1.board_ids, p2.board_ids)

    def test_increment_when_on_panel_adds_peer_rows(self):
        boards = []
        for gid, card in [("20261001_100000_aaa", "A"), ("20261001_110000_bbb", "B")]:
            inp = _mini_input(card, "O", turn=5)
            boards.append(_board(gid, 5, "Player", inp))
        panel = build_panel(boards, bb_version="1.85.0.0", turn=5, k=30)
        # both on panel; increment for bbb should include aaa→bbb
        pairs = needed_pairs_for_game(boards, panel, "20261001_110000_bbb")
        ids = {(r.board_id, c.board_id) for r, c in pairs}
        self.assertIn(
            ("20261001_100000_aaa|t5|Player", "20261001_110000_bbb|t5|Player"),
            ids,
        )
        self.assertIn(
            ("20261001_110000_bbb|t5|Player", "20261001_100000_aaa|t5|Player"),
            ids,
        )


if __name__ == "__main__":
    unittest.main()
