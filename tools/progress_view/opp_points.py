# -*- coding: utf-8 -*-
"""Point-estimate Opponent percentiles from the existing pair cache.

Does not call the simulator and does not run bootstrap. Rows already present
in strength_opp.jsonl are kept.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from tools.review_view.opp_strength import load_opp_cache, opp_cache_path, save_opp_cache
from tools.strength.cache import StrengthCache
from tools.strength.config import G_MIN, ITERATIONS, L1_ENABLED, PANEL_GAMES, W_RELAX
from tools.strength.engine import build_score_map
from tools.strength.panel import build_panel
from tools.strength.percentile import choose_level, opponent_set, panel_ids_for_slack, round_robin
from tools.strength.pool import bucket_boards, collect_boards, load_turns
from tools.strength.sim_pools import member_versions
from tools.strength._paths import DEFAULT_CACHE, DEFAULT_TURNS, default_diag_roots


def opponent_point_percentiles(
    sim_pool: str,
    *,
    roots: list[str] | None = None,
    turns_jsonl: Path | None = None,
    cache_path: Path | None = None,
    progress: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    log = progress or (lambda m: print(m, flush=True))
    opp_path = opp_cache_path(sim_pool)
    cached = load_opp_cache(opp_path)
    turns_by = load_turns(turns_jsonl or DEFAULT_TURNS)
    log(f"collecting boards for simPool {sim_pool}…")
    boards = collect_boards(
        roots or default_diag_roots(),
        sim_pool,
        turns_by,
        versions=member_versions(sim_pool),
        include_opponent=True,
    )
    boards = [b for b in boards if b.sim_pool == sim_pool]
    buckets = bucket_boards(boards)
    by_turn = {t: bl for (v, t), bl in buckets.items() if v == sim_pool}
    panels: dict[int, set[str]] = {}
    for t, bl in by_turn.items():
        panels[t] = set(build_panel(bl, bb_version=sim_pool, turn=t, k=PANEL_GAMES).board_ids)

    thin_turns = {
        t
        for t, bl in by_turn.items()
        if len({b.game_id for b in bl}) - 1 < G_MIN
    }
    slack = 1 if (thin_turns and L1_ENABLED) else 0
    log(f"loading scores (turn_slack={slack}, thin={sorted(thin_turns) if slack else []})…")
    with StrengthCache(cache_path or DEFAULT_CACHE) as cache:
        scores, missing = build_score_map(
            boards,
            panels,
            cache,
            bb_version=sim_pool,
            target_sims=ITERATIONS,
            turn_slack=slack,
            slack_turns=thin_turns if slack else set(),
        )

    candidates = [
        b
        for t in sorted(by_turn)
        for b in by_turn[t]
        if b.side == "Opponent" and b.board_id not in cached
    ]
    log(f"point-estimating {len(candidates)} Opponent boards (cache hit {len(cached)})…")
    n_ok = 0
    for i, cand in enumerate(candidates):
        if (i + 1) % 50 == 0 or i == 0:
            log(f"  opponent {i + 1}/{len(candidates)} turn={cand.turn}")
        level, R, used_slack = choose_level(
            cand,
            by_turn,
            g_min=G_MIN,
            l1_enabled=L1_ENABLED,
            player_only=False,
        )
        panel_ids = panel_ids_for_slack(cand.turn, used_slack, panels)
        O = opponent_set(R, panel_ids, scores, cand.board_id)
        core = None if level == "insufficient" else round_robin(
            cand, R=R, O=O, scores=scores, w_relax=W_RELAX
        )
        pct = None if core is None else core.get("percentile")
        flags = ["point-only"]
        if pct is None:
            flags.append("insufficient" if level == "insufficient" or core is None else "missing-score")
            level_out = "insufficient" if pct is None else level
        else:
            level_out = level
            n_ok += 1
        cached[cand.board_id] = {
            "boardId": cand.board_id,
            "gameId": cand.game_id,
            "turn": cand.turn,
            "side": "Opponent",
            "bbVersion": cand.bb_version,
            "simPool": cand.sim_pool,
            "S": None if core is None else core.get("S"),
            "percentile": pct,
            "ci95": None,
            "widthPts": None,
            "level": level_out,
            "flags": flags,
            "nGames": 0 if core is None else core.get("nGames"),
            "nOppBoards": 0 if core is None else core.get("nOppBoards"),
            "nPeers": 0 if core is None else core.get("nPeers"),
            "iterations": ITERATIONS,
            "engineVersion": "point-only",
        }

    save_opp_cache(opp_path, cached)
    summary = {
        "simPool": sim_pool,
        "out": str(opp_path),
        "nCached": len(cached),
        "nComputed": len(candidates),
        "nWithPercentile": n_ok,
        "nMissingPairs": len(missing),
    }
    log(json.dumps(summary, ensure_ascii=False))
    return summary
