# -*- coding: utf-8 -*-
"""Missing-pair discovery + ReplaySim --batch + cache write-back."""
from __future__ import annotations

import json
import math
import os
import subprocess
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from . import ASSEMBLER_VERSION
from .assembler import make_cross_input, pair_key, shell_hash
from .cache import StrengthCache
from .config import ITERATIONS, MAX_DURATION_MS, PANEL_GAMES
from .panel import Panel, build_panel, needed_pairs, needed_pairs_for_game
from .pool import Board, bucket_boards
from ._paths import DEFAULT_BB_MAP, DEFAULT_EXE, expand


def load_bb_map(path: Path | None = None) -> dict[str, str]:
    path = path or DEFAULT_BB_MAP
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    out: dict[str, str] = {}
    for k, v in raw.items():
        ver = k.split(":", 1)[0]
        expanded = expand(v)
        if ver not in out:
            out[ver] = expanded
    return out


@dataclass
class PairJob:
    pair_key: str
    job_id: str
    row: Board
    col: Board
    assembled: dict
    deficit: int  # how many more sims needed


def assemble_pair(row: Board, col: Board) -> dict:
    return make_cross_input(
        row.input,
        col.input,
        player_side=row.side,
        opp_side=col.side,
    )


def sims_sufficient(have: int, target: int) -> bool:
    """BB may return slightly fewer than requested (e.g. 498/500); treat as done."""
    if have >= target:
        return True
    if target <= 0:
        return True
    # Allow 2% shortfall or 2 abs sims (whichever larger) before re-running.
    slack = max(2, int(target * 0.02))
    return have + slack >= target


def make_pair_job(
    row: Board,
    col: Board,
    *,
    bb_version: str,
    cache: StrengthCache,
    target_sims: int,
) -> PairJob | None:
    assembled = assemble_pair(row, col)
    pk = pair_key(bb_version, assembled, ASSEMBLER_VERSION)
    have = cache.pair_sims(pk)
    if sims_sufficient(have, target_sims):
        return None
    return PairJob(
        pair_key=pk,
        job_id=f"{row.board_id}||{col.board_id}",
        row=row,
        col=col,
        assembled=assembled,
        deficit=max(1, target_sims - have),
    )


def plan_jobs(
    boards: list[Board],
    panel: Panel,
    cache: StrengthCache,
    *,
    target_sims: int,
    game_id: str | None = None,
) -> list[PairJob]:
    pairs = (
        needed_pairs_for_game(boards, panel, game_id)
        if game_id
        else needed_pairs(boards, panel)
    )
    jobs: list[PairJob] = []
    seen: set[str] = set()
    for row, col in pairs:
        j = make_pair_job(row, col, bb_version=panel.bb_version, cache=cache, target_sims=target_sims)
        if j is None or j.pair_key in seen:
            continue
        seen.add(j.pair_key)
        jobs.append(j)
    return jobs


def binomial_se(p: float, n: int) -> float:
    if n <= 0:
        return 1.0
    p = min(max(p, 0.0), 1.0)
    return math.sqrt(p * (1.0 - p) / n)


def rates_within_3sigma(rec: dict, sim: dict) -> bool:
    n1 = int(rec.get("simulationCount") or rec.get("sims") or 0)
    n2 = int(sim.get("simulationCount") or sim.get("sims") or 0)
    for key in ("winRate", "tieRate", "lossRate"):
        p1 = float(rec.get(key) or 0.0)
        p2 = float(sim.get(key) or 0.0)
        se = math.sqrt(binomial_se(p1, n1) ** 2 + binomial_se(p2, n2) ** 2)
        floor = 3.0 * math.sqrt(0.5 * (1.0 / max(n1, 1) + 1.0 / max(n2, 1)))
        limit = max(3.0 * se, floor) if se > 0 else max(1e-6, floor)
        if abs(p1 - p2) > limit + 1e-12:
            return False
    return True


def run_replay_batch(
    exe: Path,
    bb_dir: str,
    jobs: list[dict],
    *,
    iterations: int,
    max_duration: int,
    threads: int | None = None,
) -> tuple[list[dict], dict[str, Any]]:
    if not jobs:
        return [], {"wallSec": 0.0, "jobs": 0, "results": 0, "ok": 0, "exitCode": 0}

    with tempfile.TemporaryDirectory(prefix="strength-batch-") as tmp:
        jobs_path = Path(tmp) / "jobs.jsonl"
        with jobs_path.open("w", encoding="utf-8") as f:
            for j in jobs:
                f.write(json.dumps(j, ensure_ascii=False) + "\n")

        cmd = [
            str(exe),
            "--bb-dir",
            bb_dir,
            "--batch",
            str(jobs_path),
            "--iterations",
            str(iterations),
            "--max-duration",
            str(max_duration),
        ]
        if threads is not None:
            cmd.extend(["--threads", str(threads)])

        t0 = time.perf_counter()
        proc = subprocess.run(
            cmd, capture_output=True, text=True, encoding="utf-8", errors="replace"
        )
        wall = time.perf_counter() - t0

    results: list[dict] = []
    for line in (proc.stdout or "").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            results.append(json.loads(line))
        except json.JSONDecodeError:
            results.append({"ok": False, "error": "bad_json", "detail": line[:200]})

    summary = {
        "wallSec": wall,
        "exitCode": proc.returncode,
        "jobs": len(jobs),
        "results": len(results),
        "ok": sum(1 for r in results if r.get("ok")),
        "stderrTail": (proc.stderr or "")[-1000:],
    }
    return results, summary


def execute_jobs(
    pair_jobs: list[PairJob],
    cache: StrengthCache,
    *,
    exe: Path,
    bb_dir: str,
    bb_version: str,
    iterations: int = ITERATIONS,
    max_duration: int = MAX_DURATION_MS,
    threads: int | None = None,
    progress: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    """Run ReplaySim for deficits; merge into cache.

    Request max(deficit, iterations) capped at `iterations` for first fill;
    small top-ups use the deficit count (and a proportional maxDuration floor).
    """
    log = progress or (lambda _m: None)
    if not pair_jobs:
        return {
            "planned": 0,
            "ran": 0,
            "ok": 0,
            "cacheHits": 0,
            "wallSec": 0.0,
            "hitRate": 1.0,
        }

    # Use a single batch iterations = max deficit clamped to [1, iterations].
    req_iters = min(iterations, max(j.deficit for j in pair_jobs))
    req_iters = max(1, req_iters)
    # Keep duration budget at least matching requested iters (ms≈iters for our defaults).
    req_max = max(max_duration, req_iters) if req_iters >= iterations else max(50, req_iters)

    file_jobs = [{"id": j.job_id, "input": j.assembled} for j in pair_jobs]
    by_id = {j.job_id: j for j in pair_jobs}

    log(f"running {len(file_jobs)} pairs via ReplaySim (iterations={req_iters})")
    results, summary = run_replay_batch(
        exe,
        bb_dir,
        file_jobs,
        iterations=req_iters,
        max_duration=req_max,
        threads=threads,
    )
    ok_n = 0
    for r in results:
        if not r.get("ok"):
            continue
        jid = r.get("id")
        pj = by_id.get(jid)
        if pj is None:
            continue
        cache.merge_from_sim_result(
            pair_key=pj.pair_key,
            bb_version=bb_version,
            row_board_hash=pj.row.board_hash,
            col_board_hash=pj.col.board_hash,
            shell_hash=shell_hash(pj.assembled),
            result=r,
        )
        ok_n += 1

    return {
        "planned": len(pair_jobs),
        "ran": len(file_jobs),
        "ok": ok_n,
        "cacheHits": 0,
        "wallSec": summary["wallSec"],
        "hitRate": 0.0,
        "summary": summary,
    }


def backfill_bucket(
    boards: list[Board],
    cache: StrengthCache,
    *,
    bb_version: str,
    turn: int,
    exe: Path,
    bb_dir: str,
    k: int = PANEL_GAMES,
    target_sims: int = ITERATIONS,
    iterations: int = ITERATIONS,
    max_duration: int = MAX_DURATION_MS,
    threads: int | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    panel = build_panel(boards, bb_version=bb_version, turn=turn, k=k)
    cache.upsert_boards(b.to_row() for b in boards)
    jobs = plan_jobs(boards, panel, cache, target_sims=target_sims)
    total_needed = len(needed_pairs(boards, panel))
    hits = total_needed - len(jobs)
    hit_rate = (hits / total_needed) if total_needed else 1.0
    info = {
        "bbVersion": bb_version,
        "turn": turn,
        "nBoards": len(boards),
        "panelGames": panel.k,
        "panelBoardIds": len(panel.board_ids),
        "pairsNeeded": total_needed,
        "pairsMissing": len(jobs),
        "cacheHits": hits,
        "hitRate": hit_rate,
        "dryRun": dry_run,
    }
    if dry_run or not jobs:
        info["ran"] = 0
        info["ok"] = 0
        info["wallSec"] = 0.0
        return info
    run = execute_jobs(
        jobs,
        cache,
        exe=exe,
        bb_dir=bb_dir,
        bb_version=bb_version,
        iterations=iterations,
        max_duration=max_duration,
        threads=threads,
    )
    info.update({k: run[k] for k in ("ran", "ok", "wallSec") if k in run})
    return info


def backfill_version(
    boards: list[Board],
    cache: StrengthCache,
    *,
    bb_version: str,
    exe: Path | None = None,
    bb_map: dict[str, str] | None = None,
    turns: list[int] | None = None,
    k: int = PANEL_GAMES,
    target_sims: int = ITERATIONS,
    iterations: int = ITERATIONS,
    max_duration: int = MAX_DURATION_MS,
    threads: int | None = None,
    dry_run: bool = False,
    progress: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    log = progress or (lambda m: print(m, flush=True))
    exe = exe or DEFAULT_EXE
    bb_map = bb_map or load_bb_map()
    bb_dir = bb_map.get(bb_version)
    if not bb_dir or not os.path.isfile(os.path.join(bb_dir, "BobsBuddy.dll")):
        raise FileNotFoundError(f"no BobsBuddy.dll for {bb_version}: {bb_dir}")
    if not Path(exe).is_file():
        raise FileNotFoundError(f"ReplaySim exe missing: {exe}")

    buckets = bucket_boards(boards)
    reports = []
    for (ver, turn), b_list in sorted(buckets.items()):
        if ver != bb_version:
            continue
        if turns is not None and turn not in turns:
            continue
        log(f"bucket {ver} t{turn}: {len(b_list)} boards")
        reports.append(
            backfill_bucket(
                b_list,
                cache,
                bb_version=ver,
                turn=turn,
                exe=Path(exe),
                bb_dir=bb_dir,
                k=k,
                target_sims=target_sims,
                iterations=iterations,
                max_duration=max_duration,
                threads=threads,
                dry_run=dry_run,
            )
        )
    return {
        "bbVersion": bb_version,
        "buckets": reports,
        "pairsMissing": sum(r["pairsMissing"] for r in reports),
        "pairsNeeded": sum(r["pairsNeeded"] for r in reports),
        "cacheHits": sum(r["cacheHits"] for r in reports),
        "hitRate": (
            sum(r["cacheHits"] for r in reports) / sum(r["pairsNeeded"] for r in reports)
            if sum(r["pairsNeeded"] for r in reports)
            else 1.0
        ),
        "wallSec": sum(r.get("wallSec") or 0.0 for r in reports),
    }


def increment_game(
    boards: list[Board],
    cache: StrengthCache,
    *,
    bb_version: str,
    game_id: str,
    exe: Path | None = None,
    bb_map: dict[str, str] | None = None,
    k: int = PANEL_GAMES,
    target_sims: int = ITERATIONS,
    iterations: int = ITERATIONS,
    max_duration: int = MAX_DURATION_MS,
    threads: int | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    exe = exe or DEFAULT_EXE
    bb_map = bb_map or load_bb_map()
    bb_dir = bb_map.get(bb_version)
    if not bb_dir or not os.path.isfile(os.path.join(bb_dir, "BobsBuddy.dll")):
        raise FileNotFoundError(f"no BobsBuddy.dll for {bb_version}: {bb_dir}")

    buckets = bucket_boards([b for b in boards if b.bb_version == bb_version])
    reports = []
    for (ver, turn), b_list in sorted(buckets.items()):
        if not any(b.game_id == game_id for b in b_list):
            continue
        panel = build_panel(b_list, bb_version=ver, turn=turn, k=k)
        cache.upsert_boards(b.to_row() for b in b_list)
        jobs = plan_jobs(b_list, panel, cache, target_sims=target_sims, game_id=game_id)
        needed = len(needed_pairs_for_game(b_list, panel, game_id))
        hits = needed - len(jobs)
        info = {
            "turn": turn,
            "pairsNeeded": needed,
            "pairsMissing": len(jobs),
            "cacheHits": hits,
            "hitRate": (hits / needed) if needed else 1.0,
            "panelGames": panel.k,
        }
        if not dry_run and jobs:
            run = execute_jobs(
                jobs,
                cache,
                exe=Path(exe),
                bb_dir=bb_dir,
                bb_version=ver,
                iterations=iterations,
                max_duration=max_duration,
                threads=threads,
            )
            info["wallSec"] = run["wallSec"]
            info["ok"] = run["ok"]
        else:
            info["wallSec"] = 0.0
            info["ok"] = 0
        reports.append(info)
    return {"bbVersion": bb_version, "gameId": game_id, "buckets": reports}
