# -*- coding: utf-8 -*-
"""Plan/run leave-one-board cross sims for original + repositioned boards."""
from __future__ import annotations

import json
import sys
from dataclasses import replace
from pathlib import Path
from typing import Any, Callable

_REPO = Path(__file__).resolve().parents[2]
_TOOLS = _REPO / "tools"
if str(_TOOLS) not in sys.path:
    sys.path.insert(0, str(_TOOLS))

from strength import ASSEMBLER_VERSION  # noqa: E402
from strength.assembler import board_hash, make_cross_input, pair_key, shell_hash  # noqa: E402
from strength.batch import (  # noqa: E402
    PairJob,
    execute_jobs,
    load_bb_map,
    sims_sufficient,
)
from strength.cache import StrengthCache  # noqa: E402
from strength.config import ITERATIONS, MAX_DURATION_MS  # noqa: E402
from strength.pool import Board, bucket_boards, collect_boards, load_turns  # noqa: E402
from strength._paths import (  # noqa: E402
    DEFAULT_BB_MAP,
    DEFAULT_CACHE,
    DEFAULT_EXE,
    DEFAULT_TURNS,
    default_diag_roots,
)

from .reorder import DEFAULT_STRATEGIES, apply_strategy_to_input  # noqa: E402
from .stats import bh_fdr, cell_report  # noqa: E402


def _stable_seed(st: str, t: int) -> int:
    return 1000 + t * 17 + sum(ord(c) for c in st) % 97


def with_strategy(board: Board, strategy: str) -> Board:
    """New Board with reordered candidate side; board_id kept for leave-one identity."""
    if strategy == "orig":
        return board
    new_inp = apply_strategy_to_input(board.input, board.side, strategy)
    return replace(
        board,
        input=new_inp,
        board_hash=board_hash(new_inp, board.side),
        shell_hash=shell_hash(new_inp),
    )


def make_job(
    row: Board,
    col: Board,
    *,
    bb_version: str,
    cache: StrengthCache,
    target_sims: int,
) -> PairJob | None:
    assembled = make_cross_input(
        row.input,
        col.input,
        player_side=row.side,
        opp_side=col.side,
    )
    pk = pair_key(bb_version, assembled, ASSEMBLER_VERSION)
    have = cache.pair_sims(pk)
    if sims_sufficient(have, target_sims):
        return None
    return PairJob(
        pair_key=pk,
        job_id=f"{row.board_id}||{col.board_id}||{row.board_hash[:8]}",
        row=row,
        col=col,
        assembled=assembled,
        deficit=max(1, target_sims - have),
    )


def pair_score(
    row: Board,
    col: Board,
    *,
    bb_version: str,
    cache: StrengthCache,
) -> float | None:
    assembled = make_cross_input(
        row.input,
        col.input,
        player_side=row.side,
        opp_side=col.side,
    )
    pk = pair_key(bb_version, assembled, ASSEMBLER_VERSION)
    rates = cache.pair_rates(pk)
    if rates is None:
        return None
    return float(rates["s"])


def plan_turn_jobs(
    pool: list[Board],
    strategies: list[str],
    *,
    bb_version: str,
    cache: StrengthCache,
    target_sims: int,
) -> list[PairJob]:
    """All leave-one pairs for orig + each strategy (row=candidate, col=opponent)."""
    jobs: list[PairJob] = []
    seen: set[str] = set()
    # Cache reordered boards per (board_id, strategy)
    variants: dict[tuple[str, str], Board] = {}
    for b in pool:
        variants[(b.board_id, "orig")] = b
        for st in strategies:
            if st == "orig":
                continue
            variants[(b.board_id, st)] = with_strategy(b, st)

    need_strats = ["orig"] + [s for s in strategies if s != "orig"]
    for st in need_strats:
        for row0 in pool:
            row = variants[(row0.board_id, st)]
            for col in pool:
                if col.board_id == row0.board_id:
                    continue
                j = make_job(row, col, bb_version=bb_version, cache=cache, target_sims=target_sims)
                if j is None or j.pair_key in seen:
                    continue
                seen.add(j.pair_key)
                jobs.append(j)
    return jobs


def run_jobs_chunked(
    jobs: list[PairJob],
    cache: StrengthCache,
    *,
    exe: Path,
    bb_dir: str,
    bb_version: str,
    iterations: int,
    max_duration: int,
    threads: int | None,
    chunk_size: int = 1500,
    progress: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    log = progress or (lambda _m: None)
    if not jobs:
        return {"planned": 0, "ran": 0, "ok": 0, "wallSec": 0.0, "chunks": 0}
    total_ok = 0
    total_wall = 0.0
    total_ran = 0
    chunks = 0
    for i in range(0, len(jobs), chunk_size):
        chunk = jobs[i : i + chunk_size]
        chunks += 1
        log(f"chunk {chunks}: {len(chunk)} jobs ({i + 1}-{i + len(chunk)}/{len(jobs)})")
        info = execute_jobs(
            chunk,
            cache,
            exe=exe,
            bb_dir=bb_dir,
            bb_version=bb_version,
            iterations=iterations,
            max_duration=max_duration,
            threads=threads,
            progress=log,
        )
        total_ok += int(info.get("ok") or 0)
        total_wall += float(info.get("wallSec") or 0.0)
        total_ran += int(info.get("ran") or 0)
    return {
        "planned": len(jobs),
        "ran": total_ran,
        "ok": total_ok,
        "wallSec": total_wall,
        "chunks": chunks,
    }


def score_board_against_pool(
    candidate: Board,
    pool: list[Board],
    *,
    bb_version: str,
    cache: StrengthCache,
) -> tuple[float | None, int, int]:
    """Return (S, n_ok, n_missing). Exclude same board_id."""
    vals: list[float] = []
    missing = 0
    for col in pool:
        if col.board_id == candidate.board_id:
            continue
        # For strategy variants board_id matches original; compare via identity.
        # candidate may be reordered clone with same board_id.
        s = pair_score(candidate, col, bb_version=bb_version, cache=cache)
        if s is None:
            missing += 1
            continue
        vals.append(s)
    if not vals:
        return None, 0, missing
    return float(sum(vals) / len(vals)), len(vals), missing


def evaluate_turn(
    pool: list[Board],
    strategies: list[str],
    *,
    bb_version: str,
    cache: StrengthCache,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for b in pool:
        s_orig, n_ok0, miss0 = score_board_against_pool(
            b, pool, bb_version=bb_version, cache=cache
        )
        for st in strategies:
            cand = b if st == "orig" else with_strategy(b, st)
            if st == "orig":
                s_st, n_ok, miss = s_orig, n_ok0, miss0
                delta = 0.0 if s_orig is not None else None
            else:
                s_st, n_ok, miss = score_board_against_pool(
                    cand, pool, bb_version=bb_version, cache=cache
                )
                delta = (
                    float(s_st - s_orig)
                    if s_st is not None and s_orig is not None
                    else None
                )
            rows.append(
                {
                    "boardId": b.board_id,
                    "gameId": b.game_id,
                    "turn": b.turn,
                    "side": b.side,
                    "strategy": st,
                    "S_orig": s_orig,
                    "S": s_st,
                    "deltaS": delta,
                    "nOpp": n_ok,
                    "nMissing": miss,
                    "boardHash": cand.board_hash,
                }
            )
    return rows


def run_analysis(
    *,
    bb_version: str = "1.85.0.0",
    turns: list[int] | None = None,
    strategies: list[str] | None = None,
    roots: list[str] | None = None,
    turns_jsonl: Path | None = None,
    cache_path: Path | None = None,
    exe: Path | None = None,
    bb_map_path: Path | None = None,
    out_dir: Path | None = None,
    iterations: int = ITERATIONS,
    max_duration: int = MAX_DURATION_MS,
    threads: int | None = None,
    limit_boards: int | None = None,
    dry_run: bool = False,
    chunk_size: int = 1500,
    n_boot: int = 2000,
    progress: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    log = progress or (lambda m: print(m, flush=True))
    turns = turns or list(range(3, 8))
    strategies = strategies or list(DEFAULT_STRATEGIES)
    # Always include orig in evaluation for smoke; not in DEFAULT_STRATEGIES
    eval_strats = ["orig"] + [s for s in strategies if s != "orig"]
    roots = roots if roots is not None else default_diag_roots()
    turns_by = load_turns(turns_jsonl or DEFAULT_TURNS)
    cache_path = cache_path or DEFAULT_CACHE
    exe = exe or DEFAULT_EXE
    out_dir = out_dir or (_REPO / "data" / "positioning" / bb_version)
    out_dir.mkdir(parents=True, exist_ok=True)

    boards = collect_boards(
        roots,
        bb_version,
        turns_by,
        max_turn=max(turns),
        include_opponent=True,
        require_ready=True,
    )
    boards = [b for b in boards if b.turn in set(turns)]
    if limit_boards is not None:
        # Keep full turn pools for leave-one semantics: limit by taking first N games' boards
        game_order: list[str] = []
        for b in boards:
            if b.game_id not in game_order:
                game_order.append(b.game_id)
        keep_games = set(game_order[: max(1, limit_boards // max(1, len(turns) * 2))])
        # If still too many, truncate pool per turn later
        boards = [b for b in boards if b.game_id in keep_games]
        buckets = bucket_boards(boards)
        trimmed: list[Board] = []
        for t in turns:
            bl = buckets.get((bb_version, t), [])
            if limit_boards and len(bl) > limit_boards:
                bl = bl[:limit_boards]
            trimmed.extend(bl)
        boards = trimmed

    buckets = bucket_boards(boards)
    bb_map = load_bb_map(bb_map_path or DEFAULT_BB_MAP)
    bb_dir = bb_map.get(bb_version)
    if not bb_dir:
        raise SystemExit(f"no bb-dir for {bb_version} in {bb_map_path or DEFAULT_BB_MAP}")

    log(
        f"boards={len(boards)} turns={turns} strategies={eval_strats} "
        f"cache={cache_path} dry_run={dry_run}"
    )

    all_rows: list[dict[str, Any]] = []
    run_info: list[dict[str, Any]] = []

    with StrengthCache(cache_path) as cache:
        for t in turns:
            pool = buckets.get((bb_version, t), [])
            if len(pool) < 2:
                log(f"turn {t}: skip (pool={len(pool)})")
                continue
            jobs = plan_turn_jobs(
                pool,
                eval_strats,
                bb_version=bb_version,
                cache=cache,
                target_sims=iterations,
            )
            info = {
                "turn": t,
                "nPool": len(pool),
                "pairsMissing": len(jobs),
                "dryRun": dry_run,
            }
            log(f"turn {t}: pool={len(pool)} missing_pairs={len(jobs)}")
            if not dry_run and jobs:
                run = run_jobs_chunked(
                    jobs,
                    cache,
                    exe=exe,
                    bb_dir=bb_dir,
                    bb_version=bb_version,
                    iterations=iterations,
                    max_duration=max_duration,
                    threads=threads,
                    chunk_size=chunk_size,
                    progress=log,
                )
                info.update(run)
            run_info.append(info)
            rows = evaluate_turn(pool, eval_strats, bb_version=bb_version, cache=cache)
            all_rows.extend(rows)

    # Persist board-level scores
    scores_path = out_dir / "scores.jsonl"
    with scores_path.open("w", encoding="utf-8") as f:
        for r in all_rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    summary = build_summary(all_rows, run_info, strategies=eval_strats, turns=turns, n_boot=n_boot)
    summary_path = out_dir / "summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    log(f"wrote {scores_path} and {summary_path}")
    return summary


def build_summary(
    all_rows: list[dict[str, Any]],
    run_info: list[dict[str, Any]],
    *,
    strategies: list[str],
    turns: list[int],
    n_boot: int = 2000,
) -> dict[str, Any]:
    cells: list[dict[str, Any]] = []
    pvals: list[float | None] = []
    cell_index: list[int] = []  # indices into cells that enter FDR (non-orig)

    for st in strategies:
        for t in turns:
            subset = [r for r in all_rows if r["strategy"] == st and r["turn"] == t]
            if not subset:
                continue
            rep = cell_report(subset, n_boot=n_boot, seed=_stable_seed(st, t))
            cell = {
                "strategy": st,
                "turn": t,
                **{k: rep[k] for k in ("n", "mean", "median", "p10", "p90", "fracPositive")},
                "bootstrap": rep["bootstrap"],
                "wilcoxon": rep["wilcoxon"],
                "ciLowerPositive": rep["ciLowerPositive"],
            }
            cells.append(cell)
            if st != "orig":
                cell_index.append(len(cells) - 1)
                pvals.append((rep["wilcoxon"] or {}).get("pvalue"))

    rejects = bh_fdr(pvals, q=0.05)
    for i, rej in zip(cell_index, rejects):
        cells[i]["fdrReject05"] = bool(rej)
    for i, c in enumerate(cells):
        if c["strategy"] == "orig":
            c["fdrReject05"] = False

    # Sanity: orig mean |ΔS| ~ 0
    orig_means = [c["mean"] for c in cells if c["strategy"] == "orig" and c["mean"] is not None]
    return {
        "strategies": strategies,
        "turns": turns,
        "runInfo": run_info,
        "cells": cells,
        "origMeanAbsMax": max((abs(x) for x in orig_means), default=None),
        "nBoardRows": len(all_rows),
    }


def load_summary(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))
