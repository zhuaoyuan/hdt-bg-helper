# -*- coding: utf-8 -*-
"""Second-round tie-weight search (ADR-0019).

Does not write strength.jsonl. A curve is adopted only when the confirmation
half clears the gate in design R-score-policy-search-v2 §3.4.
"""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Callable, Sequence

import numpy as np

from .cache import StrengthCache
from .config import G_MIN, ITERATIONS, L1_ENABLED, PANEL_GAMES
from .engine import build_score_map
from .loss_summary import expected_taken
from .panel import build_panel
from .percentile import empirical_cdf_percentile
from .pool import Board, bucket_boards, collect_boards, load_turns
from .raw_placement import load_final_places
from .score_policy import baseline_score, ten_curves
from .score_search import player_percentiles, ranked_game_points
from .sim_pools import member_versions, sim_pool_of
from ._paths import DEFAULT_CACHE, DEFAULT_TURNS, REPO, default_diag_roots

MID_LO = 6
MID_HI = 14
CONFIRM_DELTA = 0.05


def split_halves(game_ids: Sequence[str]) -> tuple[list[str], list[str]]:
    """Earlier game ids are the fit half. An odd count leaves the extra game in confirm."""
    ordered = sorted(set(game_ids))
    cut = len(ordered) // 2
    return ordered[:cut], ordered[cut:]


def blood_percentiles(turn_values: list[tuple[str, float]]) -> dict[str, float]:
    """Higher u means lower taken damage. Peers are the other boards on that turn."""
    if len(turn_values) < 2:
        return {}
    out: dict[str, float] = {}
    for board_id, taken in turn_values:
        peers = [-other for other_id, other in turn_values if other_id != board_id]
        weights = [1.0] * len(peers)
        u = empirical_cdf_percentile(-float(taken), peers, weights)
        if u is not None:
            out[board_id] = float(u)
    return out


def judge_confirm(
    rho_mid: float | None,
    baseline_mid: float | None,
    rho_end: float | None,
    baseline_end: float | None,
    *,
    delta: float = CONFIRM_DELTA,
) -> dict[str, Any]:
    """Confirmation gate: mid-game lift at least `delta`, end-game rho not below baseline."""
    mid_ok = (
        rho_mid is not None
        and baseline_mid is not None
        and float(rho_mid) - float(baseline_mid) >= float(delta) - 1e-12
    )
    end_ok = (
        rho_end is not None
        and baseline_end is not None
        and float(rho_end) >= float(baseline_end) - 1e-12
    )
    lift = None
    if rho_mid is not None and baseline_mid is not None:
        lift = float(rho_mid) - float(baseline_mid)
    return {
        "passed": bool(mid_ok and end_ok),
        "deltaMid": lift,
        "deltaRequired": float(delta),
        "midOk": bool(mid_ok),
        "endOk": bool(end_ok),
    }


def choose_on_fit(curves: list[dict[str, Any]], baseline_end: float | None) -> dict[str, Any] | None:
    """Drop curves whose fit-half end rho is below the baseline, then take the highest mid rho.

    Ties keep the earlier curve in the closed list (the list order is the tie break).
    """
    kept: list[dict[str, Any]] = []
    for row in curves:
        end = row.get("rhoEnd")
        mid = row.get("rhoMid")
        below = (
            end is None
            or baseline_end is None
            or float(end) < float(baseline_end) - 1e-12
            or mid is None
        )
        row["kept"] = not below
        if not below:
            kept.append(row)
    if not kept:
        return None
    best = max(float(r["rhoMid"]) for r in kept)
    tied = [r for r in kept if abs(float(r["rhoMid"]) - best) <= 1e-12]
    chosen = tied[0]
    chosen["tiedNames"] = [r["name"] for r in tied]
    return chosen


def _bootstrap_by_game(
    rows: list[dict[str, Any]],
    x_key: str,
    y_key: str,
    *,
    n_boot: int,
    seed: int,
) -> dict[str, Any]:
    from tools.strength_validity.metrics import spearman

    if len(rows) < 3:
        return {"n": len(rows), "nGames": len({r["gameId"] for r in rows}), "rho": None, "ci95": None, "n_boot": 0}
    xs = [float(r[x_key]) for r in rows]
    ys = [float(r[y_key]) for r in rows]
    point = spearman(xs, ys)
    games = sorted({r["gameId"] for r in rows})
    by_game: dict[str, list[int]] = defaultdict(list)
    for i, r in enumerate(rows):
        by_game[r["gameId"]].append(i)
    if point["rho"] is None or len(games) < 3:
        return {
            "n": point["n"],
            "nGames": len(games),
            "rho": point["rho"],
            "ci95": None,
            "n_boot": 0,
        }
    rng = np.random.default_rng(seed)
    rhos: list[float] = []
    gindex = np.arange(len(games))
    for _ in range(n_boot):
        pick = rng.choice(gindex, size=len(games), replace=True)
        idx: list[int] = []
        for g in pick:
            idx.extend(by_game[games[int(g)]])
        got = spearman([xs[i] for i in idx], [ys[i] for i in idx])["rho"]
        if got is not None:
            rhos.append(float(got))
    ci = None
    if len(rhos) >= max(100, n_boot // 10):
        ci = [float(np.quantile(rhos, 0.025)), float(np.quantile(rhos, 0.975))]
    return {
        "n": point["n"],
        "nGames": len(games),
        "rho": point["rho"],
        "ci95": ci,
        "n_boot": len(rhos),
    }


def _pair_taken(row: Board, col: Board, pair: dict[str, Any]) -> float | None:
    if not pair.get("lossSampleCount"):
        return None
    cap = int((row.input or {}).get("DamageCap") or 0)
    return expected_taken(
        loss_count=int(pair["lossCount"] or 0),
        capped_loss_count=int(pair["cappedLossCount"] or 0),
        uncapped_median=pair.get("uncappedLossMedian"),
        sample_count=int(pair["lossSampleCount"]),
        damage_cap=cap,
        taken_sum=pair.get("takenSum"),
    )


def board_taken_damage(
    boards: list[Board],
    panels: dict[int, set[str]],
    index: dict[tuple[str, str, str], dict[str, Any]],
) -> tuple[dict[str, float], dict[str, Any]]:
    """Mean taken damage of each turn 6–14 player board vs the same-turn panel."""
    from .assembler import cross_shell_hash

    by_id = {b.board_id: b for b in boards}
    taken: dict[str, float] = {}
    loss_n = 0
    capped_n = 0
    pairs_used = 0
    boards_with = 0
    for row in boards:
        if row.side != "Player" or row.turn < MID_LO or row.turn > MID_HI:
            continue
        shell = cross_shell_hash(row.input)
        vals: list[float] = []
        for col_id in panels.get(row.turn, set()):
            col = by_id.get(col_id)
            if col is None or col.game_id == row.game_id:
                continue
            pair = index.get((row.board_hash, col.board_hash, shell))
            if pair is None:
                continue
            et = _pair_taken(row, col, pair)
            if et is None:
                continue
            vals.append(et)
            pairs_used += 1
            loss_n += int(pair.get("lossCount") or 0)
            capped_n += int(pair.get("cappedLossCount") or 0)
        if not vals:
            continue
        taken[row.board_id] = sum(vals) / float(len(vals))
        boards_with += 1
    frac = (capped_n / loss_n) if loss_n else None
    stats = {
        "nPairs": pairs_used,
        "nBoards": boards_with,
        "lossCount": loss_n,
        "cappedLossCount": capped_n,
        "cappedFraction": frac,
    }
    return taken, stats


def _half_pack(
    boards: list[Board],
    percentiles: dict[str, float | None],
    blood_u: dict[str, float],
    places: dict[str, int],
    game_ids: set[str],
    *,
    n_boot: int,
    seed: int,
) -> dict[str, Any]:
    mid_rows = []
    for b in boards:
        if b.side != "Player" or b.game_id not in game_ids:
            continue
        if b.turn < MID_LO or b.turn > MID_HI:
            continue
        q = percentiles.get(b.board_id)
        u = blood_u.get(b.board_id)
        if q is None or u is None:
            continue
        mid_rows.append({"gameId": b.game_id, "boardId": b.board_id, "turn": b.turn, "Q": float(q), "u": float(u)})
    end_points = ranked_game_points(
        [b for b in boards if b.side == "Player" and b.game_id in game_ids],
        percentiles,
        placement_by_game=places,
    )
    mid = _bootstrap_by_game(mid_rows, "Q", "u", n_boot=n_boot, seed=seed)
    end = _bootstrap_by_game(
        [{"gameId": p["gameId"], "Q": p["meanQ"], "u": p["negPlacement"]} for p in end_points],
        "Q",
        "u",
        n_boot=n_boot,
        seed=seed + 1,
    )
    return {
        "rhoMid": mid["rho"],
        "ci95Mid": mid["ci95"],
        "nBoards": mid["n"],
        "nGamesMid": mid["nGames"],
        "rhoEnd": end["rho"],
        "ci95End": end["ci95"],
        "nGames": end["n"],
        "nBoardsInLast3": sum(int(p["nLast"]) for p in end_points),
    }


def _curve_row(name: str, family: str, params: dict[str, Any], fit: dict, confirm: dict) -> dict[str, Any]:
    return {
        "name": name,
        "family": family,
        "params": params,
        "fit": {k: fit[k] for k in ("rhoMid", "ci95Mid", "nBoards", "nGamesMid", "rhoEnd", "ci95End", "nGames", "nBoardsInLast3")},
        "confirm": {k: confirm[k] for k in ("rhoMid", "ci95Mid", "nBoards", "nGamesMid", "rhoEnd", "ci95End", "nGames", "nBoardsInLast3")},
    }


def run_score_policy_v2(
    *,
    sim_pool: str = "1.85.0.0",
    roots: list[str] | None = None,
    turns_jsonl: Path | None = None,
    cache_path: Path | None = None,
    out_dir: Path | None = None,
    n_boot: int = 2000,
    progress: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    """Write the v2 sidecar. Never reads or writes strength.jsonl."""
    log = progress or (lambda m: print(m, flush=True))
    pool = sim_pool_of(sim_pool)
    strength_path = REPO / "data" / "strength" / pool / "strength.jsonl"
    mtime_before = strength_path.stat().st_mtime if strength_path.is_file() else None
    turns_by = load_turns(turns_jsonl or DEFAULT_TURNS)
    root_list = roots or default_diag_roots()
    boards = collect_boards(
        root_list,
        pool,
        turns_by,
        versions=member_versions(pool),
        max_turn=None,
        include_opponent=True,
    )
    out_dir = out_dir or (REPO / "data" / "strength" / pool / "score-policy-v2")
    if out_dir.name != "score-policy-v2":
        raise ValueError(f"refusing to write outside a score-policy-v2 directory: {out_dir}")

    with StrengthCache(cache_path or DEFAULT_CACHE) as cache:
        buckets = bucket_boards(boards)
        by_turn = {t: bl for (v, t), bl in buckets.items() if v == pool}
        panels = {
            t: set(build_panel(bl, bb_version=pool, turn=t, k=PANEL_GAMES).board_ids)
            for t, bl in by_turn.items()
        }
        thin_turns = {t for t, bl in by_turn.items() if len({b.game_id for b in bl}) - 1 < G_MIN}
        slack = 1 if (thin_turns and L1_ENABLED) else 0
        candidates = [b for t in sorted(by_turn) for b in by_turn.get(t, []) if b.side == "Player"]
        places = load_final_places(root_list)
        game_ids = sorted({b.game_id for b in candidates})
        fit_ids, confirm_ids = split_halves(game_ids)
        fit_set, confirm_set = set(fit_ids), set(confirm_ids)
        index = cache.load_pair_index(pool)
        taken, cap_stats = board_taken_damage(boards, panels, index)
        by_turn_taken: dict[int, list[tuple[str, float]]] = defaultdict(list)
        for b in candidates:
            if b.board_id in taken and MID_LO <= b.turn <= MID_HI:
                by_turn_taken[b.turn].append((b.board_id, taken[b.board_id]))
        blood_u: dict[str, float] = {}
        for _turn, vals in by_turn_taken.items():
            blood_u.update(blood_percentiles(vals))
        log(
            f"games={len(game_ids)} fit={len(fit_ids)} confirm={len(confirm_ids)} "
            f"bloodBoards={len(blood_u)} cappedFraction={cap_stats.get('cappedFraction')}"
        )
        if cap_stats["nBoards"] == 0:
            raise RuntimeError("loss summaries are missing; not selecting a curve")

        specs: list[tuple[str, str, dict[str, Any], Callable]] = [
            ("baseline", "baseline", {}, baseline_score),
        ]
        for curve in ten_curves():
            specs.append((curve.name, curve.family, curve.params, curve.as_score_fn()))

        records: list[dict[str, Any]] = []
        for i, (name, family, params, fn) in enumerate(specs):
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
            pct = player_percentiles(candidates, by_turn, panels, scores)
            fit = _half_pack(candidates, pct, blood_u, places, fit_set, n_boot=n_boot, seed=100 + i)
            confirm = _half_pack(candidates, pct, blood_u, places, confirm_set, n_boot=n_boot, seed=200 + i)
            rec = _curve_row(name, family, params, fit, confirm)
            rec["missingPairs"] = len(missing)
            records.append(rec)
            log(
                f"  fit mid={fit['rhoMid']} end={fit['rhoEnd']} "
                f"confirm mid={confirm['rhoMid']} end={confirm['rhoEnd']}"
            )

    baseline = next(r for r in records if r["family"] == "baseline")
    fit_view = []
    for r in records:
        if r["family"] == "baseline":
            continue
        fit_view.append({
            "name": r["name"],
            "family": r["family"],
            "params": r["params"],
            "rhoMid": r["fit"]["rhoMid"],
            "rhoEnd": r["fit"]["rhoEnd"],
        })
    chosen = choose_on_fit(fit_view, baseline["fit"]["rhoEnd"])
    adopted = None
    judgment = None
    if chosen is not None:
        full = next(r for r in records if r["name"] == chosen["name"])
        judgment = judge_confirm(
            full["confirm"]["rhoMid"],
            baseline["confirm"]["rhoMid"],
            full["confirm"]["rhoEnd"],
            baseline["confirm"]["rhoEnd"],
        )
        judgment["name"] = chosen["name"]
        judgment["params"] = chosen["params"]
        judgment["tiedNames"] = chosen.get("tiedNames")
        if judgment["passed"]:
            adopted = {
                "name": chosen["name"],
                "family": chosen["family"],
                "params": chosen["params"],
                "deltaMid": judgment["deltaMid"],
            }

    mtime_after = strength_path.stat().st_mtime if strength_path.is_file() else None
    summary = {
        "simPool": pool,
        "phase": 1,
        "damageTerm": "none",
        "beta": 0.0,
        "selection": "turn 6-14 Q vs blood percentile; last-3 Q vs -placement is a constraint",
        "placementSource": "diag game_end PLAYER_LEADERBOARD_PLACE",
        "halves": {
            "fitGames": fit_ids,
            "confirmGames": confirm_ids,
            "nFit": len(fit_ids),
            "nConfirm": len(confirm_ids),
        },
        "cap": cap_stats,
        "candidate": None if chosen is None else {
            "name": chosen["name"],
            "params": chosen["params"],
            "tiedNames": chosen.get("tiedNames"),
        },
        "confirmation": judgment,
        "adopted": adopted,
        "strengthJsonl": "unchanged",
        "strengthMtimeUnchanged": mtime_before == mtime_after,
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    grid_path = out_dir / "grid.jsonl"
    with grid_path.open("w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    summary_path = out_dir / "summary.json"
    # Game id lists make the summary large but they are the split record.
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    log(json.dumps({"adopted": adopted, "confirmation": judgment, "strengthMtimeUnchanged": summary["strengthMtimeUnchanged"]}, ensure_ascii=False))
    summary["grid"] = str(grid_path)
    summary["summaryPath"] = str(summary_path)
    return summary


def evaluate_blood_as_strength(
    *,
    sim_pool: str = "1.85.0.0",
    roots: list[str] | None = None,
    turns_jsonl: Path | None = None,
    cache_path: Path | None = None,
    n_boot: int = 2000,
    progress: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    """Use the blood percentile itself as the strength percentile.

    The score is Spearman of the mean blood percentile on the last 3 combats
    versus -placement. Turns outside 6–14 have no blood percentile and are skipped.
    Does not write strength.jsonl.
    """
    log = progress or (lambda m: print(m, flush=True))
    pool = sim_pool_of(sim_pool)
    root_list = roots or default_diag_roots()
    turns_by = load_turns(turns_jsonl or DEFAULT_TURNS)
    boards = collect_boards(
        root_list,
        pool,
        turns_by,
        versions=member_versions(pool),
        max_turn=None,
        include_opponent=True,
    )
    with StrengthCache(cache_path or DEFAULT_CACHE) as cache:
        buckets = bucket_boards(boards)
        by_turn = {t: bl for (v, t), bl in buckets.items() if v == pool}
        panels = {
            t: set(build_panel(bl, bb_version=pool, turn=t, k=PANEL_GAMES).board_ids)
            for t, bl in by_turn.items()
        }
        candidates = [b for t in sorted(by_turn) for b in by_turn.get(t, []) if b.side == "Player"]
        places = load_final_places(root_list)
        index = cache.load_pair_index(pool)
        taken, cap_stats = board_taken_damage(boards, panels, index)
    by_turn_taken: dict[int, list[tuple[str, float]]] = defaultdict(list)
    for b in candidates:
        if b.board_id in taken and MID_LO <= b.turn <= MID_HI:
            by_turn_taken[b.turn].append((b.board_id, taken[b.board_id]))
    blood_u: dict[str, float] = {}
    for vals in by_turn_taken.values():
        blood_u.update(blood_percentiles(vals))
    game_ids = sorted({b.game_id for b in candidates})
    fit_ids, confirm_ids = split_halves(game_ids)

    def points(gids: set[str]) -> tuple[list[dict[str, Any]], int, int]:
        rows: list[dict[str, Any]] = []
        slots = 0
        with_u = 0
        for gid in gids:
            group = sorted((b for b in candidates if b.game_id == gid), key=lambda b: b.turn)
            tail = group[-3:]
            slots += len(tail)
            vals = []
            for b in tail:
                if b.board_id in blood_u:
                    vals.append(blood_u[b.board_id])
                    with_u += 1
            if gid not in places or not vals:
                continue
            rows.append({
                "gameId": gid,
                "Q": sum(vals) / float(len(vals)),
                "u": -float(places[gid]),
                "n": len(vals),
            })
        return rows, slots, with_u

    halves = {}
    for name, ids in (("fit", set(fit_ids)), ("confirm", set(confirm_ids)), ("all", set(game_ids))):
        rows, slots, with_u = points(ids)
        pack = _bootstrap_by_game(rows, "Q", "u", n_boot=n_boot, seed=11)
        halves[name] = {
            "rho": pack["rho"],
            "ci95": pack["ci95"],
            "nGames": pack["n"],
            "slots": slots,
            "slotsWithBlood": with_u,
        }
        log(f"{name} rho={pack['rho']} n={pack['n']} ci={pack['ci95']}")
    report = {
        "simPool": pool,
        "label": "blood percentile used as strength; last 3 combats vs -placement",
        "taken": "mean of raw damageResults; negative samples keep their own magnitude",
        "cap": cap_stats,
        "nBloodBoards": len(blood_u),
        "halves": halves,
        "strengthJsonl": "unchanged",
    }
    out = REPO / "data" / "strength" / pool / "score-policy-v2" / "blood-as-strength.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report["path"] = str(out)
    return report
