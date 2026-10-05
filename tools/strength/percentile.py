# -*- coding: utf-8 -*-
"""Leave-one-game round-robin S/Q + clustered bootstrap (ADR-0011 / design §3.2–3.3, §3.7)."""
from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Iterable

import numpy as np

from .config import BOOTSTRAP_B, G_MIN, L1_ENABLED, L2_ENABLED, W_RELAX
from .pool import Board


@dataclass(frozen=True)
class PairStat:
    s: float
    sims: int
    se2: float  # variance of s estimate ≈ s(1-s)/n
    my_death_rate: float | None = None
    av_damage: float | None = None


ScoreMap = dict[str, dict[str, PairStat]]  # rowBoardId -> colBoardId -> PairStat


def weighted_mean(vals: list[float], weights: list[float]) -> float | None:
    if not vals:
        return None
    sw = sum(weights)
    if sw <= 0:
        return None
    return sum(v * w for v, w in zip(vals, weights)) / sw


def empirical_cdf_percentile(S: float, peer_S: list[float], peer_w: list[float]) -> float | None:
    if not peer_S:
        return None
    den = sum(peer_w)
    if den <= 0:
        return None
    num = 0.0
    for sp, w in zip(peer_S, peer_w):
        if sp < S:
            num += w
        elif sp == S:
            num += 0.5 * w
    return num / den


def se2_of_s(s: float, sims: int) -> float:
    if sims <= 0:
        return 0.0
    s = min(max(s, 0.0), 1.0)
    return s * (1.0 - s) / float(sims)


def choose_level(
    cand: Board,
    by_turn: dict[int, list[Board]],
    *,
    g_min: int = G_MIN,
    l1_enabled: bool = L1_ENABLED,
    l2_enabled: bool = L2_ENABLED,
    player_only: bool = False,
) -> tuple[str, list[Board], int]:
    """Return (level, R, turn_slack). level is L0 / L1:turn±1 / insufficient (L2 unused)."""
    del l2_enabled  # reserved; default off

    def pool(slack: int) -> list[Board]:
        turns = range(cand.turn - slack, cand.turn + slack + 1)
        out: list[Board] = []
        for tt in turns:
            for b in by_turn.get(tt, []):
                if b.game_id == cand.game_id:
                    continue
                if player_only and b.side != "Player":
                    continue
                out.append(b)
        return out

    r0 = pool(0)
    g0 = len({b.game_id for b in r0})
    if g0 >= g_min:
        return "L0", r0, 0

    if l1_enabled:
        r1 = pool(1)
        g1 = len({b.game_id for b in r1})
        if g1 >= g_min:
            return "L1:turn±1", r1, 1
        return "insufficient", r1, 1

    return "insufficient", r0, 0


def opponent_set(
    R: list[Board],
    panel_board_ids: set[str],
    scores: ScoreMap,
    cand_id: str,
) -> list[Board]:
    """O = R ∩ panel, and cand must have a score vs that board."""
    sm = scores.get(cand_id) or {}
    return [b for b in R if b.board_id in panel_board_ids and b.board_id in sm]


def board_base_weight(b: Board, cand_turn: int, w_relax: float) -> float:
    return 1.0 if b.turn == cand_turn else w_relax


def round_robin(
    cand: Board,
    *,
    R: list[Board],
    O: list[Board],
    scores: ScoreMap,
    w_relax: float = W_RELAX,
    game_mult: dict[str, float] | None = None,
    mc_noise: bool = False,
    rng: np.random.Generator | None = None,
) -> dict[str, Any] | None:
    """Compute S and Q for one candidate against fixed R/O (design §3.2)."""
    cand_id = cand.board_id
    if cand_id not in scores or not O:
        return None

    def w_board(b: Board) -> float:
        m = 1.0 if game_mult is None else float(game_mult.get(b.game_id, 0.0))
        if m <= 0:
            return 0.0
        return m * board_base_weight(b, cand.turn, w_relax)

    def s_val(row_id: str, col_id: str) -> float | None:
        sm = scores.get(row_id)
        if not sm or col_id not in sm:
            return None
        st = sm[col_id]
        s = st.s
        if mc_noise and rng is not None and st.se2 > 0:
            s = float(np.clip(s + rng.normal(0.0, math.sqrt(st.se2)), 0.0, 1.0))
        return s

    s_vals: list[float] = []
    s_ws: list[float] = []
    death_acc = 0.0
    dmg_acc = 0.0
    aux_w = 0.0
    for b in O:
        sv = s_val(cand_id, b.board_id)
        if sv is None:
            continue
        ww = w_board(b)
        if ww <= 0:
            continue
        s_vals.append(sv)
        s_ws.append(ww)
        st = scores[cand_id][b.board_id]
        if st.my_death_rate is not None:
            death_acc += float(st.my_death_rate) * ww
            aux_w += ww
        if st.av_damage is not None:
            dmg_acc += float(st.av_damage) * ww

    S = weighted_mean(s_vals, s_ws)
    if S is None:
        return None

    # Peers = all of R (Player + Opponent); each must have scores vs O\{own game}.
    peer_S: list[float] = []
    peer_w: list[float] = []
    for p in R:
        if p.board_id == cand_id:
            continue
        if p.board_id not in scores:
            continue
        vals: list[float] = []
        ws: list[float] = []
        for b in O:
            if b.game_id == p.game_id:
                continue
            sv = s_val(p.board_id, b.board_id)
            if sv is None:
                continue
            ww = w_board(b)
            if ww <= 0:
                continue
            vals.append(sv)
            ws.append(ww)
        sp = weighted_mean(vals, ws)
        if sp is None:
            continue
        pw = w_board(p)
        if pw <= 0:
            continue
        peer_S.append(sp)
        peer_w.append(pw)

    Q = empirical_cdf_percentile(S, peer_S, peer_w)

    # Monte Carlo SE of S: propagate pair variances with the same weights.
    num_var = 0.0
    den_w = sum(s_ws)
    if den_w > 0:
        for b in O:
            st = (scores.get(cand_id) or {}).get(b.board_id)
            ww = w_board(b)
            if st is None or ww <= 0:
                continue
            num_var += (ww / den_w) ** 2 * st.se2
    mc_se = math.sqrt(num_var) if num_var > 0 else 0.0

    aux: dict[str, float] = {}
    if aux_w > 0:
        aux["myDeathRate"] = death_acc / aux_w
    dmg_w = 0.0
    dmg_sum = 0.0
    for b in O:
        st = (scores.get(cand_id) or {}).get(b.board_id)
        ww = w_board(b)
        if st is None or ww <= 0 or st.av_damage is None:
            continue
        dmg_sum += float(st.av_damage) * ww
        dmg_w += ww
    if dmg_w > 0:
        aux["avDamage"] = dmg_sum / dmg_w

    return {
        "S": S,
        "percentile": Q,
        "nGames": len({b.game_id for b in R}),
        "nOppBoards": len(O),
        "nPeers": len(peer_S),
        "mcSeS": mc_se,
        "aux": aux,
    }


def clustered_bootstrap_ci(
    cand: Board,
    *,
    R: list[Board],
    panel_board_ids: set[str],
    scores: ScoreMap,
    B: int = BOOTSTRAP_B,
    seed: int = 0,
    w_relax: float = W_RELAX,
    mc_noise: bool = True,
) -> tuple[list[float] | None, float | None]:
    """Return (ci95 [lo,hi], widthPts) for Q; None if too few resamples succeed.

    Fast path: pre-extract opponent/peer score vectors and resample game multiplicities
    with numpy (design §3.7).
    """
    games = sorted({b.game_id for b in R})
    if len(games) < 3:
        return None, None
    game_index = {g: i for i, g in enumerate(games)}
    n_g = len(games)

    cand_id = cand.board_id
    cand_sm = scores.get(cand_id) or {}
    # Opponents = panel ∩ R with scores from cand
    opp_boards = [b for b in R if b.board_id in panel_board_ids and b.board_id in cand_sm]
    if not opp_boards:
        return None, None

    opp_game = np.array([game_index[b.game_id] for b in opp_boards], dtype=np.int32)
    opp_base_w = np.array(
        [board_base_weight(b, cand.turn, w_relax) for b in opp_boards], dtype=np.float64
    )
    opp_s = np.array([cand_sm[b.board_id].s for b in opp_boards], dtype=np.float64)
    opp_se = np.array(
        [math.sqrt(cand_sm[b.board_id].se2) for b in opp_boards], dtype=np.float64
    )

    # Peers with full score rows vs opponents (leave peer's game out later)
    peer_boards: list[Board] = []
    peer_s_rows: list[np.ndarray] = []
    peer_se_rows: list[np.ndarray] = []
    for p in R:
        if p.board_id == cand_id or p.board_id not in scores:
            continue
        psm = scores[p.board_id]
        row_s = np.empty(len(opp_boards), dtype=np.float64)
        row_se = np.empty(len(opp_boards), dtype=np.float64)
        ok = True
        for j, ob in enumerate(opp_boards):
            st = psm.get(ob.board_id)
            if st is None:
                row_s[j] = np.nan
                row_se[j] = 0.0
            else:
                row_s[j] = st.s
                row_se[j] = math.sqrt(st.se2)
        # Keep peer if it has at least one usable opp outside its game (checked in loop)
        if np.all(np.isnan(row_s)):
            ok = False
        if not ok:
            continue
        peer_boards.append(p)
        peer_s_rows.append(row_s)
        peer_se_rows.append(row_se)

    if not peer_boards:
        return None, None

    peer_game = np.array([game_index[p.game_id] for p in peer_boards], dtype=np.int32)
    peer_base_w = np.array(
        [board_base_weight(p, cand.turn, w_relax) for p in peer_boards], dtype=np.float64
    )
    peer_S_mat = np.vstack(peer_s_rows)  # P x O
    peer_se_mat = np.vstack(peer_se_rows)

    rng = np.random.default_rng(seed)
    boot_q: list[float] = []
    for _ in range(B):
        # multiplicity per game
        sampled = rng.integers(0, n_g, size=n_g)
        mult = np.bincount(sampled, minlength=n_g).astype(np.float64)
        opp_w = opp_base_w * mult[opp_game]
        if opp_w.sum() <= 0:
            continue
        s_opp = opp_s.copy()
        if mc_noise:
            noise = rng.normal(0.0, 1.0, size=s_opp.shape) * opp_se
            s_opp = np.clip(s_opp + noise, 0.0, 1.0)
        # mask zero-weight opps
        mask = opp_w > 0
        if not np.any(mask):
            continue
        S = float(np.sum(s_opp[mask] * opp_w[mask]) / np.sum(opp_w[mask]))

        # peer scores
        pS = peer_S_mat.copy()
        if mc_noise:
            pS = np.clip(pS + rng.normal(0.0, 1.0, size=pS.shape) * peer_se_mat, 0.0, 1.0)
        peer_w = peer_base_w * mult[peer_game]
        qs_peer: list[float] = []
        qw: list[float] = []
        for i in range(len(peer_boards)):
            if peer_w[i] <= 0:
                continue
            # exclude opponent boards from peer's own game
            omit = opp_game == peer_game[i]
            use = mask & (~omit) & np.isfinite(pS[i])
            if not np.any(use):
                continue
            ww = opp_w[use]
            sp = float(np.sum(pS[i, use] * ww) / np.sum(ww))
            qs_peer.append(sp)
            qw.append(float(peer_w[i]))
        if not qs_peer:
            continue
        den = sum(qw)
        num = 0.0
        for sp, w in zip(qs_peer, qw):
            if sp < S:
                num += w
            elif sp == S:
                num += 0.5 * w
        boot_q.append(num / den)

    if len(boot_q) < 20:
        return None, None
    qs = np.sort(np.asarray(boot_q, dtype=float))
    lo = float(qs[max(0, int(0.025 * len(qs)))])
    hi = float(qs[min(len(qs) - 1, int(0.975 * len(qs)))])
    return [lo, hi], (hi - lo) * 100.0


def panel_ids_for_slack(
    cand_turn: int,
    slack: int,
    panels: dict[int, Iterable[str]],
) -> set[str]:
    ids: set[str] = set()
    for tt in range(cand_turn - slack, cand_turn + slack + 1):
        for bid in panels.get(tt, []):
            ids.add(bid)
    return ids


def score_lookup_pair(
    scores: ScoreMap,
    row_id: str,
    col_id: str,
) -> PairStat | None:
    return (scores.get(row_id) or {}).get(col_id)
