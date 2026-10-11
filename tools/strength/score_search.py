# -*- coding: utf-8 -*-
"""Search the tie-weight curve without touching strength.jsonl.

Q-020: damage is capped, so alpha = beta = 0 and there is no blood label B.
Selection falls back to the mean percentile of each ranked game's last 3
combats versus -placement (ADR-0017 / ADR-0018).
"""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Callable

from .cache import StrengthCache
from .config import G_MIN, ITERATIONS, L1_ENABLED, PANEL_GAMES, W_RELAX
from .engine import build_score_map
from .panel import build_panel
from .percentile import choose_level, opponent_set, panel_ids_for_slack, round_robin
from .pool import Board, bucket_boards, collect_boards, load_turns
from .score_policy import T1_GRID, W_FLOOR, baseline_score, curve_score
from .sim_pools import member_versions, sim_pool_of
from ._paths import DEFAULT_CACHE, DEFAULT_TURNS, REPO, default_diag_roots

MIN_PLACED_GAMES = 12
LAST_COMBATS = 3


def last_combat_values(turns_and_q: list[tuple[int, float | None]], k: int = LAST_COMBATS) -> list[float]:
    """Percentiles on the last k combats of one game. Missing percentiles are skipped."""
    ordered = sorted(turns_and_q, key=lambda item: item[0])
    tail = ordered[-k:]
    return [float(q) for _, q in tail if q is not None]


def mean_or_none(vals: list[float]) -> float | None:
    if not vals:
        return None
    return sum(vals) / float(len(vals))


def placement_of(board: Board) -> int | None:
    raw = (board.label or {}).get("placement")
    if raw is None:
        return None
    return int(raw)


def ranked_game_points(
    boards: list[Board],
    percentile_by_id: dict[str, float | None],
) -> list[dict[str, Any]]:
    """One row per game that has a placement and at least one last-3 percentile."""
    by_game: dict[str, list[Board]] = defaultdict(list)
    for b in boards:
        if b.side == "Player":
            by_game[b.game_id].append(b)
    rows: list[dict[str, Any]] = []
    for gid, group in by_game.items():
        ordered = sorted(group, key=lambda b: b.turn)
        place = None
        for b in reversed(ordered):
            place = placement_of(b)
            if place is not None:
                break
        if place is None:
            continue
        qs = last_combat_values([(b.turn, percentile_by_id.get(b.board_id)) for b in ordered])
        q_bar = mean_or_none(qs)
        if q_bar is None:
            continue
        rows.append({
            "gameId": gid,
            "placement": place,
            "negPlacement": -float(place),
            "meanQ": q_bar,
            "nLast": len(qs),
        })
    rows.sort(key=lambda r: r["gameId"])
    return rows


def judge_fallback(rho: float | None, baseline_rho: float | None, n_games: int) -> dict[str, Any]:
    """ADR-0018 without B: rho > 0, rho above the baseline, and at least 12 ranked games."""
    higher = (
        rho is not None and baseline_rho is not None and float(rho) > float(baseline_rho)
    )
    positive = rho is not None and float(rho) > 0.0
    enough = int(n_games) >= MIN_PLACED_GAMES
    return {
        "valid": bool(higher and positive and enough),
        "higherThanBaseline": higher,
        "positive": positive,
        "enoughGames": enough,
        "nGames": int(n_games),
        "minGames": MIN_PLACED_GAMES,
    }


def player_percentiles(
    candidates: list[Board],
    by_turn: dict[int, list[Board]],
    panels: dict[int, set[str]],
    scores,
) -> dict[str, float | None]:
    out: dict[str, float | None] = {}
    for cand in candidates:
        level, R, slack = choose_level(
            cand,
            by_turn,
            g_min=G_MIN,
            l1_enabled=L1_ENABLED,
            l2_enabled=False,
            player_only=False,
        )
        if level == "insufficient":
            out[cand.board_id] = None
            continue
        panel_ids = panel_ids_for_slack(cand.turn, slack, panels)
        O = opponent_set(R, panel_ids, scores, cand.board_id)
        core = round_robin(cand, R=R, O=O, scores=scores, w_relax=W_RELAX)
        if core is None or core.get("percentile") is None:
            out[cand.board_id] = None
        else:
            out[cand.board_id] = float(core["percentile"])
    return out


def _point_record(
    *,
    kind: str,
    t1: int | None,
    rho_pack: dict[str, Any],
    n_boards: int,
    n_player: int,
) -> dict[str, Any]:
    return {
        "kind": kind,
        "t1": t1,
        "wFloor": None if kind == "baseline" else W_FLOOR,
        "tieWeight": 0.5 if kind == "baseline" else "curve",
        "alpha": 0.0,
        "beta": 0.0,
        "td": None,
        "L": None,
        "rhoOut": None,
        "rhoOver": None,
        "J": None,
        "nOut": None,
        "nOver": None,
        "rhoLast3": rho_pack.get("rho"),
        "ci95": rho_pack.get("ci95"),
        "nGames": rho_pack.get("n"),
        "nBoardsInLast3": n_boards,
        "nPlayer": n_player,
        "reason": "Q-020: no usable damage distribution; selection is last-3 mean Q vs -placement",
    }


def correlate_last3(points: list[dict[str, Any]], *, n_boot: int, seed: int) -> dict[str, Any]:
    from tools.strength_validity.metrics import bootstrap_spearman_ci

    if len(points) < 3:
        return {"n": len(points), "rho": None, "ci95": None, "n_boot": 0}
    pack = bootstrap_spearman_ci(
        [p["meanQ"] for p in points],
        [p["negPlacement"] for p in points],
        n_boot=n_boot,
        seed=seed,
    )
    return {"n": pack.get("n"), "rho": pack.get("rho"), "ci95": pack.get("ci95"), "n_boot": pack.get("n_boot")}


def run_score_policy_search(
    *,
    sim_pool: str = "1.85.0.0",
    roots: list[str] | None = None,
    turns_jsonl: Path | None = None,
    cache_path: Path | None = None,
    out_dir: Path | None = None,
    n_boot: int = 2000,
    progress: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    """Write a sidecar grid. Does not read or write strength.jsonl."""
    log = progress or (lambda m: print(m, flush=True))
    pool = sim_pool_of(sim_pool)
    turns_by = load_turns(turns_jsonl or DEFAULT_TURNS)
    boards = collect_boards(
        roots or default_diag_roots(),
        pool,
        turns_by,
        versions=member_versions(pool),
        max_turn=None,
        include_opponent=True,
    )
    cache_path = cache_path or DEFAULT_CACHE
    out_dir = out_dir or (REPO / "data" / "strength" / pool / "score-policy")
    if out_dir.name != "score-policy":
        raise ValueError(f"refusing to write outside a score-policy directory: {out_dir}")

    with StrengthCache(cache_path) as cache:
        buckets = bucket_boards(boards)
        by_turn: dict[int, list[Board]] = {
            t: bl for (v, t), bl in buckets.items() if v == pool
        }
        panels: dict[int, set[str]] = {}
        for t, bl in by_turn.items():
            panels[t] = set(build_panel(bl, bb_version=pool, turn=t, k=PANEL_GAMES).board_ids)
        thin_turns = {
            t
            for t, bl in by_turn.items()
            if len({b.game_id for b in bl}) - 1 < G_MIN
        }
        slack = 1 if (thin_turns and L1_ENABLED) else 0
        candidates = [
            b
            for t in sorted(by_turn)
            for b in by_turn.get(t, [])
            if b.side == "Player"
        ]
        log(f"players={len(candidates)} turns={len(by_turn)} thin={sorted(thin_turns) if slack else []}")

        specs: list[tuple[str, int | None, Callable]] = [("baseline", None, baseline_score)]
        for t1 in T1_GRID:
            specs.append((f"t1={t1}", t1, curve_score(t1)))

        records: list[dict[str, Any]] = []
        for name, t1, fn in specs:
            log(f"scoring {name}…")
            scores, missing = build_score_map(
                boards,
                panels,
                cache,
                bb_version=pool,
                target_sims=ITERATIONS,
                turn_slack=slack,
                slack_turns=thin_turns if slack else set(),
                score_fn=fn,
            )
            log(f"  pairs missing={len(missing)}; percentiles…")
            pct = player_percentiles(candidates, by_turn, panels, scores)
            points = ranked_game_points(candidates, pct)
            rho_pack = correlate_last3(points, n_boot=n_boot, seed=17 if t1 is None else 17 + int(t1))
            n_boards = sum(p["nLast"] for p in points)
            mean_of_mean = mean_or_none([float(p["meanQ"]) for p in points])
            rec = _point_record(
                kind="baseline" if t1 is None else "curve",
                t1=t1,
                rho_pack=rho_pack,
                n_boards=n_boards,
                n_player=len(candidates),
            )
            rec["name"] = name
            rec["missingPairs"] = len(missing)
            rec["meanOfMeanQ"] = mean_of_mean
            records.append(rec)
            log(f"  nGames={rec['nGames']} rhoLast3={rec['rhoLast3']} ci95={rec['ci95']}")

    baseline = next(r for r in records if r["kind"] == "baseline")
    curves = [r for r in records if r["kind"] == "curve" and r["rhoLast3"] is not None]
    if not curves:
        adopted = None
        judgment = judge_fallback(None, baseline.get("rhoLast3"), int(baseline.get("nGames") or 0))
    else:
        best = max(float(r["rhoLast3"]) for r in curves)
        tied = [r for r in curves if abs(float(r["rhoLast3"]) - best) <= 1e-12]
        tied.sort(key=lambda r: int(r["t1"]))
        adopted = tied[0]
        judgment = judge_fallback(
            adopted.get("rhoLast3"),
            baseline.get("rhoLast3"),
            int(adopted.get("nGames") or 0),
        )
        judgment["tiedT1"] = [r["t1"] for r in tied]

    summary = {
        "simPool": pool,
        "damage": "dropped",
        "alpha": 0.0,
        "beta": 0.0,
        "selection": "last3-mean-Q vs -placement",
        "adopted": None if adopted is None else {"t1": adopted["t1"], "rhoLast3": adopted["rhoLast3"]},
        "baselineRho": baseline.get("rhoLast3"),
        "judgment": judgment,
        "strengthJsonl": "unchanged",
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    grid_path = out_dir / "grid.jsonl"
    with grid_path.open("w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    summary_path = out_dir / "summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    log(json.dumps(summary, ensure_ascii=False))
    summary["grid"] = str(grid_path)
    summary["summaryPath"] = str(summary_path)
    return summary
