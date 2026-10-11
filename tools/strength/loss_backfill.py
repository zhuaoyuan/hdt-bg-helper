# -*- coding: utf-8 -*-
"""Replay cached turn 6–14 pairs to store loss-damage summaries.

Does not change wins, ties, or losses. Stops before any simulation when the
single-thread elapsedMs estimate exceeds the backfill cap (default 2 hours).
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from .assembler import cross_shell_hash
from .batch import assemble_pair, load_bb_map, resolve_bb_dir, run_replay_batch
from .cache import StrengthCache
from .config import ITERATIONS, MAX_DURATION_MS, PANEL_GAMES
from .panel import build_panel
from .pool import Board, bucket_boards, collect_boards, load_turns
from .sim_pools import member_versions
from ._paths import DEFAULT_BB_MAP, DEFAULT_CACHE, DEFAULT_EXE, DEFAULT_TURNS, REPO, default_diag_roots

MID_TURN_LO = 6
MID_TURN_HI = 14
MAX_HOURS = 2.0


def rough_seconds(n_pairs: int, median_elapsed_ms: float | None) -> float:
    med = 50.0 if median_elapsed_ms is None else float(median_elapsed_ms)
    return int(n_pairs) * med / 1000.0


def plan_midgame_pairs(
    boards: list[Board],
    index: dict[tuple[str, str, str], dict[str, Any]],
    *,
    pool: str,
    panel_games: int = PANEL_GAMES,
    resume: bool = True,
) -> dict[str, Any]:
    """Unique cached pairs: player boards on turns 6–14 vs the same-turn panel."""
    buckets = bucket_boards(boards)
    by_turn: dict[int, list[Board]] = {t: bl for (v, t), bl in buckets.items() if v == pool}
    by_id = {b.board_id: b for b in boards}
    panels = {
        t: set(build_panel(bl, bb_version=pool, turn=t, k=panel_games).board_ids)
        for t, bl in by_turn.items()
    }
    chosen: dict[str, dict[str, Any]] = {}
    missing = 0
    already = 0
    for turn in range(MID_TURN_LO, MID_TURN_HI + 1):
        cols = [by_id[i] for i in panels.get(turn, set()) if i in by_id]
        for row in by_turn.get(turn, []):
            if row.side != "Player":
                continue
            shell = cross_shell_hash(row.input)
            for col in cols:
                if row.game_id == col.game_id:
                    continue
                key = (row.board_hash, col.board_hash, shell)
                found = index.get(key)
                if found is None:
                    missing += 1
                    continue
                pk = str(found["pairKey"])
                if pk in chosen:
                    continue
                if resume and found.get("lossSampleCount"):
                    already += 1
                    continue
                chosen[pk] = {"pair": found, "row": row, "col": col}
    return {
        "jobs": list(chosen.values()),
        "uniqueToRun": len(chosen),
        "alreadySummarized": already,
        "missingRates": missing,
    }


def run_loss_summary_backfill(
    *,
    sim_pool: str = "1.85.0.0",
    roots: list[str] | None = None,
    turns_jsonl: Path | None = None,
    cache_path: Path | None = None,
    exe: Path | None = None,
    bb_map_path: Path | None = None,
    max_hours: float = MAX_HOURS,
    chunk: int = 400,
    dry_run: bool = False,
    progress: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    log = progress or (lambda m: print(m, flush=True))
    turns_by = load_turns(turns_jsonl or DEFAULT_TURNS)
    boards = collect_boards(
        roots or default_diag_roots(),
        sim_pool,
        turns_by,
        versions=member_versions(sim_pool),
        max_turn=None,
        include_opponent=True,
    )
    cache_path = cache_path or DEFAULT_CACHE
    exe = exe or DEFAULT_EXE
    report: dict[str, Any] = {
        "simPool": sim_pool,
        "turns": [MID_TURN_LO, MID_TURN_HI],
        "started": False,
        "winsUntouched": True,
    }
    with StrengthCache(cache_path) as cache:
        index = cache.load_pair_index(sim_pool)
        plan = plan_midgame_pairs(boards, index, pool=sim_pool)
        med = cache.median_elapsed_ms()
        seconds = rough_seconds(plan["uniqueToRun"], med)
        report.update(
            {
                "pairsToRun": plan["uniqueToRun"],
                "alreadySummarized": plan["alreadySummarized"],
                "missingRates": plan["missingRates"],
                "medianElapsedMs": med,
                "roughSec": seconds,
                "maxHours": max_hours,
            }
        )
        log(
            f"pairsToRun={plan['uniqueToRun']} already={plan['alreadySummarized']} "
            f"missingRates={plan['missingRates']} roughSec={seconds:.0f} "
            f"(single-thread median elapsedMs; cap {max_hours:g}h)"
        )
        if seconds > max_hours * 3600.0:
            report["stopped"] = "over-budget"
            log("rough estimate exceeds the cap; not starting simulations.")
            return report
        if dry_run or plan["uniqueToRun"] == 0:
            report["dryRun"] = dry_run
            return report
        if not Path(exe).is_file():
            raise FileNotFoundError(f"ReplaySim exe missing: {exe}")
        bb_map = load_bb_map(bb_map_path or DEFAULT_BB_MAP)
        _pool, dll_ver, bb_dir = resolve_bb_dir(sim_pool, bb_map)
        report["dll"] = dll_ver
        report["started"] = True
        jobs = plan["jobs"]
        written = 0
        failed = 0
        checked = 0
        for start in range(0, len(jobs), chunk):
            batch = jobs[start : start + chunk]
            file_jobs = []
            by_id = {}
            for item in batch:
                row: Board = item["row"]
                col: Board = item["col"]
                jid = item["pair"]["pairKey"]
                file_jobs.append({"id": jid, "input": assemble_pair(row, col)})
                by_id[jid] = item
            log(f"loss summary {start + 1}-{start + len(batch)} / {len(jobs)}")
            results, summary = run_replay_batch(
                Path(exe),
                bb_dir,
                file_jobs,
                iterations=ITERATIONS,
                max_duration=MAX_DURATION_MS,
                threads=None,
            )
            payload = []
            for r in results:
                if not r.get("ok") or r.get("lossCount") is None or r.get("lossSampleCount") is None:
                    failed += 1
                    continue
                pk = str(r.get("id"))
                item = by_id.get(pk)
                if item is None:
                    failed += 1
                    continue
                before = item["pair"]
                payload.append(
                    (
                        int(r["lossCount"]),
                        int(r["cappedLossCount"]),
                        None if r.get("uncappedLossMedian") is None else float(r["uncappedLossMedian"]),
                        int(r["lossSampleCount"]),
                        pk,
                    )
                )
                after = cache.get_pair(pk)
                # Written after the batch commit; snapshot the rates we must keep.
                item["_keep"] = (
                    before.get("sims"),
                    before.get("wins"),
                    before.get("ties"),
                    before.get("losses"),
                )
                del after
            cache.write_loss_summaries(payload)
            for row_payload in payload:
                pk = row_payload[-1]
                after = cache.get_pair(pk)
                keep = by_id[pk]["_keep"]
                if after is None or (
                    after.get("sims"),
                    after.get("wins"),
                    after.get("ties"),
                    after.get("losses"),
                ) != keep:
                    report["winsUntouched"] = False
                checked += 1
            written += len(payload)
            log(
                f"  wrote={len(payload)} failed_so_far={failed} "
                f"wallSec={summary.get('wallSec')}"
            )
            if summary.get("exitCode") not in (0, None) and not payload:
                report["stopped"] = "replay-failed"
                report["stderrTail"] = summary.get("stderrTail")
                break
        report["written"] = written
        report["failed"] = failed
        report["checked"] = checked
    out = REPO / "data" / "strength" / sim_pool / "score-policy-v2"
    out.mkdir(parents=True, exist_ok=True)
    path = out / "loss-summary-backfill.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report["reportPath"] = str(path)
    log(json.dumps({k: report[k] for k in report if k != "stderrTail"}, ensure_ascii=False))
    return report
