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


class PercentileSyntheticTests(unittest.TestCase):
    """Known ranking + interval shape on a synthetic score matrix (P3-T3)."""

    def _strength_boards(self, n_games: int = 8, turn: int = 4):
        from tools.strength.percentile import PairStat, ScoreMap, choose_level, clustered_bootstrap_ci, opponent_set, panel_ids_for_slack, round_robin

        boards = []
        # Game i Player has latent strength i/(n-1); Opponent is weaker shadow.
        for i in range(n_games):
            gid = f"2026100{i+1}_100000_g{i}"
            strength = i / max(n_games - 1, 1)
            inp = _mini_input(f"P{i}", f"O{i}", turn=turn)
            pb = _board(gid, turn, "Player", inp)
            ob = _board(gid, turn, "Opponent", inp)
            pb.label = {"strength": strength}
            ob.label = {"strength": strength * 0.5}
            boards.append(pb)
            boards.append(ob)

        def s_ab(a: Board, b: Board) -> float:
            # Higher latent → higher score; deterministic, no MC noise needed for rank test.
            return 0.5 + 0.5 * (float(a.label["strength"]) - float(b.label["strength"]))

        scores: ScoreMap = {}
        for row in boards:
            scores[row.board_id] = {}
            for col in boards:
                if row.game_id == col.game_id:
                    continue
                s = min(1.0, max(0.0, s_ab(row, col)))
                scores[row.board_id][col.board_id] = PairStat(s=s, sims=500, se2=0.0)

        by_turn = {turn: boards}
        panel_ids = {b.board_id for b in boards}
        return boards, scores, by_turn, panel_ids

    def test_round_robin_ranks_strongest_highest(self):
        from tools.strength.percentile import choose_level, opponent_set, panel_ids_for_slack, round_robin

        boards, scores, by_turn, panel_ids = self._strength_boards(8)
        players = [b for b in boards if b.side == "Player"]
        qs = []
        for cand in players:
            level, R, slack = choose_level(cand, by_turn, g_min=6, l1_enabled=False)
            self.assertEqual(level, "L0")
            O = opponent_set(R, panel_ids_for_slack(cand.turn, slack, {cand.turn: panel_ids}), scores, cand.board_id)
            row = round_robin(cand, R=R, O=O, scores=scores)
            self.assertIsNotNone(row)
            self.assertIsNotNone(row["percentile"])
            qs.append((float(cand.label["strength"]), row["percentile"], row["S"]))
        qs.sort()
        # Monotone: stronger latent → higher Q and S
        for i in range(1, len(qs)):
            self.assertGreaterEqual(qs[i][1], qs[i - 1][1] - 1e-9)
            self.assertGreaterEqual(qs[i][2], qs[i - 1][2] - 1e-9)
        self.assertGreater(qs[-1][1], qs[0][1])

    def test_bootstrap_ci_contains_point_and_has_width(self):
        from tools.strength.percentile import choose_level, clustered_bootstrap_ci, opponent_set, panel_ids_for_slack, round_robin

        boards, scores, by_turn, panel_ids = self._strength_boards(10)
        cand = max((b for b in boards if b.side == "Player"), key=lambda b: b.label["strength"])
        level, R, slack = choose_level(cand, by_turn, g_min=6, l1_enabled=False)
        pids = panel_ids_for_slack(cand.turn, slack, {cand.turn: panel_ids})
        O = opponent_set(R, pids, scores, cand.board_id)
        row = round_robin(cand, R=R, O=O, scores=scores)
        ci, width = clustered_bootstrap_ci(
            cand,
            R=R,
            panel_board_ids=pids,
            scores=scores,
            B=200,
            seed=1,
            mc_noise=False,
        )
        self.assertIsNotNone(ci)
        self.assertIsNotNone(width)
        self.assertGreaterEqual(width, 0.0)
        self.assertLessEqual(ci[0], row["percentile"] + 1e-9)
        self.assertGreaterEqual(ci[1], row["percentile"] - 1e-9)
        # With game resampling only, width should be positive for finite peer sets
        self.assertGreater(width, 0.0)

    def test_insufficient_when_below_g_min(self):
        from tools.strength.percentile import choose_level

        boards, scores, by_turn, panel_ids = self._strength_boards(4)
        cand = boards[0]
        level, R, slack = choose_level(cand, by_turn, g_min=6, l1_enabled=False)
        self.assertEqual(level, "insufficient")
        self.assertEqual(slack, 0)

    def test_l1_label_when_same_turn_thin(self):
        from tools.strength.percentile import PairStat, choose_level

        # 4 games at t5 (< G_min=6), 8 games at t4/t6 to allow L1
        boards = []
        for turn, n in ((4, 8), (5, 4), (6, 8)):
            for i in range(n):
                gid = f"2026101{turn}_10000{i}_x{i}"
                inp = _mini_input("P", "O", turn=turn)
                boards.append(_board(gid, turn, "Player", inp))
        by_turn = {}
        for b in boards:
            by_turn.setdefault(b.turn, []).append(b)
        cand = by_turn[5][0]
        level, R, slack = choose_level(cand, by_turn, g_min=6, l1_enabled=True)
        self.assertEqual(level, "L1:turn±1")
        self.assertEqual(slack, 1)
        self.assertGreaterEqual(len({b.game_id for b in R}), 6)


if __name__ == "__main__":
    unittest.main()
