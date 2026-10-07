# -*- coding: utf-8 -*-
"""Budgeted adjacent-swap hill climb for local_swap_b6."""
from __future__ import annotations

from dataclasses import replace
from typing import Any, Callable

from strength.assembler import board_hash, shell_hash
from strength.batch import PairJob
from strength.cache import StrengthCache
from strength.pool import Board

from .reorder import adjacent_swaps, extract_side_items, set_side_items

MakeJobFn = Callable[..., PairJob | None]
ScoreFn = Callable[..., tuple[float | None, int, int]]
RunJobsFn = Callable[..., dict[str, Any]]


def board_with_items(board: Board, items: list[dict]) -> Board:
    new_inp = set_side_items(board.input, board.side, items)
    return replace(
        board,
        input=new_inp,
        board_hash=board_hash(new_inp, board.side),
        shell_hash=shell_hash(new_inp),
    )


def plan_candidate_jobs(
    candidates: list[Board],
    pool: list[Board],
    *,
    bb_version: str,
    cache: StrengthCache,
    target_sims: int,
    seen: set[str],
    remaining_cap: int | None,
    make_job: MakeJobFn,
) -> list[PairJob]:
    jobs: list[PairJob] = []
    for row in candidates:
        for col in pool:
            if col.board_id == row.board_id:
                continue
            j = make_job(row, col, bb_version=bb_version, cache=cache, target_sims=target_sims)
            if j is None or j.pair_key in seen:
                continue
            if remaining_cap is not None and len(jobs) >= remaining_cap:
                return jobs
            seen.add(j.pair_key)
            jobs.append(j)
    return jobs


def hill_climb_turn(
    pool: list[Board],
    *,
    bb_version: str,
    cache: StrengthCache,
    exe,
    bb_dir: str,
    iterations: int,
    max_duration: int,
    threads: int | None,
    chunk_size: int,
    make_job: MakeJobFn,
    score_board_against_pool: ScoreFn,
    run_jobs_chunked: RunJobsFn,
    swap_budget: int = 6,
    pair_cap: int = 250_000,
    dry_run: bool = False,
    progress: Callable[[str], None] | None = None,
) -> tuple[dict[str, Board], dict[str, Any]]:
    """
    From orig, up to `swap_budget` improving adjacent swaps per board.
    Returns final Board per board_id and run meta.
    """
    log = progress or (lambda _m: None)
    current: dict[str, Board] = {b.board_id: b for b in pool}
    stopped: set[str] = set()
    truncated: set[str] = set()
    steps_done: dict[str, int] = {b.board_id: 0 for b in pool}
    seen: set[str] = set()
    pairs_planned = 0
    pairs_ran = 0
    pairs_ok = 0
    wall = 0.0

    base_jobs = plan_candidate_jobs(
        list(pool),
        pool,
        bb_version=bb_version,
        cache=cache,
        target_sims=iterations,
        seen=seen,
        remaining_cap=pair_cap,
        make_job=make_job,
    )
    pairs_planned += len(base_jobs)
    if not dry_run and base_jobs:
        info = run_jobs_chunked(
            base_jobs,
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
        pairs_ran += int(info.get("ran") or 0)
        pairs_ok += int(info.get("ok") or 0)
        wall += float(info.get("wallSec") or 0.0)

    for step in range(1, swap_budget + 1):
        active = [b for b in pool if b.board_id not in stopped]
        if not active:
            break
        remaining = max(0, pair_cap - pairs_planned)
        if remaining == 0:
            for b in active:
                truncated.add(b.board_id)
                stopped.add(b.board_id)
            log(f"local_swap: pair_cap reached before step {step}")
            break

        cand_by_board: dict[str, list[Board]] = {}
        flat: list[Board] = []
        for b0 in active:
            cur = current[b0.board_id]
            items = extract_side_items(cur.input, cur.side)
            neighbors = [board_with_items(b0, nxt) for nxt in adjacent_swaps(items)]
            cands = [cur] + neighbors
            cand_by_board[b0.board_id] = cands
            flat.extend(cands)

        jobs = plan_candidate_jobs(
            flat,
            pool,
            bb_version=bb_version,
            cache=cache,
            target_sims=iterations,
            seen=seen,
            remaining_cap=remaining,
            make_job=make_job,
        )
        pairs_planned += len(jobs)
        if len(jobs) >= remaining:
            for b0 in active:
                truncated.add(b0.board_id)

        if not dry_run and jobs:
            log(
                f"local_swap step {step}: boards={len(active)} "
                f"new_jobs={len(jobs)} planned_total={pairs_planned}"
            )
            info = run_jobs_chunked(
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
            pairs_ran += int(info.get("ran") or 0)
            pairs_ok += int(info.get("ok") or 0)
            wall += float(info.get("wallSec") or 0.0)

        for b0 in active:
            bid = b0.board_id
            cands = cand_by_board[bid]
            scored: list[tuple[float, Board]] = []
            incomplete = False
            for c in cands:
                s, _n, miss = score_board_against_pool(
                    c, pool, bb_version=bb_version, cache=cache
                )
                if s is None or miss > 0:
                    incomplete = True
                    continue
                scored.append((s, c))
            if incomplete and bid in truncated:
                stopped.add(bid)
                continue
            if not scored:
                stopped.add(bid)
                truncated.add(bid)
                continue
            scored.sort(key=lambda t: (-t[0], t[1].board_hash))
            best_s, best_b = scored[0]
            cur = current[bid]
            cur_s, _, cur_miss = score_board_against_pool(
                cur, pool, bb_version=bb_version, cache=cache
            )
            if cur_s is None or cur_miss > 0:
                stopped.add(bid)
                truncated.add(bid)
                continue
            if best_s > cur_s + 1e-15 and best_b.board_hash != cur.board_hash:
                current[bid] = best_b
                steps_done[bid] = step
            else:
                stopped.add(bid)
            if bid in truncated:
                stopped.add(bid)

    meta = {
        "strategy": "local_swap_b6",
        "swapBudget": swap_budget,
        "pairCap": pair_cap,
        "pairsPlanned": pairs_planned,
        "pairsRan": pairs_ran,
        "pairsOk": pairs_ok,
        "wallSec": wall,
        "nTruncated": len(truncated),
        "truncatedBoardIds": sorted(truncated),
        "stepsDoneMean": (
            float(sum(steps_done.values()) / len(steps_done)) if steps_done else 0.0
        ),
        "nImproved": sum(1 for b in pool if current[b.board_id].board_hash != b.board_hash),
    }
    return current, meta
