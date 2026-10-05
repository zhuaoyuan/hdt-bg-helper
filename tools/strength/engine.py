# -*- coding: utf-8 -*-
"""Orchestrate cache → score matrix → strength.jsonl (+ exit-width stats)."""
from __future__ import annotations

import json
import math
import os
from collections import defaultdict
from pathlib import Path
from typing import Any, Callable

from . import ASSEMBLER_VERSION, __version__ as ENGINE_VERSION
from .assembler import make_cross_input, pair_key, shell_hash as shell_hash_of
from .batch import (
    PairJob,
    backfill_version,
    execute_jobs,
    load_bb_map,
    make_pair_job,
    sims_sufficient,
)
from .cache import StrengthCache
from .config import (
    BOOTSTRAP_B,
    EXIT_WIDTH_FRAC,
    EXIT_WIDTH_MEDIAN_LE,
    EXIT_WIDTH_P80_LE,
    G_MIN,
    INCLUDE_OPPONENT_BOARDS,
    ITERATIONS,
    L1_ENABLED,
    L2_ENABLED,
    MAX_DURATION_MS,
    PANEL_GAMES,
    W_RELAX,
    WIDE_FLAG_GT,
)
from .panel import build_panel
from .percentile import (
    PairStat,
    ScoreMap,
    choose_level,
    clustered_bootstrap_ci,
    opponent_set,
    panel_ids_for_slack,
    round_robin,
    se2_of_s,
)
from .pool import Board, bucket_boards, collect_boards, load_turns
from ._paths import DEFAULT_CACHE, DEFAULT_EXE, DEFAULT_TURNS, REPO, default_diag_roots


def strength_out_path(bb_version: str, root: Path | None = None) -> Path:
    base = root or (REPO / "data" / "strength")
    return base / bb_version / "strength.jsonl"


def cross_shell_hash(row_input: dict) -> str:
    """Shell hash as stored on cache pairs (matches make_cross_input + shell_hash)."""
    return shell_hash_of(
        {
            "DamageCap": row_input.get("DamageCap"),
            "turn": row_input.get("turn"),
            "availableRaces": row_input.get("availableRaces"),
            "Anomaly": row_input.get("Anomaly"),
            "isDuos": False,
        }
    )


def build_score_map(
    boards: list[Board],
    panel_by_turn: dict[int, set[str]],
    cache: StrengthCache,
    *,
    bb_version: str,
    target_sims: int = ITERATIONS,
    turn_slack: int = 1,
) -> tuple[ScoreMap, list[tuple[Board, Board]]]:
    """Load s(row,col) from cache for leave-one-game pairs within turn±slack.

    Uses hash index (no re-assembly) for speed. Returns (scores, missing_pairs).
    """
    by_id = {b.board_id: b for b in boards}
    by_turn: dict[int, list[Board]] = defaultdict(list)
    for b in boards:
        by_turn[b.turn].append(b)

    index = cache.load_pair_index(bb_version)
    scores: ScoreMap = defaultdict(dict)
    missing: list[tuple[Board, Board]] = []
    missing_seen: set[tuple[str, str]] = set()

    turns = sorted(by_turn)
    for t in turns:
        col_ids: set[str] = set()
        for tt in range(t - turn_slack, t + turn_slack + 1):
            col_ids |= set(panel_by_turn.get(tt, set()))
        cols = [by_id[i] for i in sorted(col_ids) if i in by_id]
        for row in by_turn[t]:
            sh = cross_shell_hash(row.input)
            for col in cols:
                if row.game_id == col.game_id:
                    continue
                key = (row.board_hash, col.board_hash, sh)
                p = index.get(key)
                if p is None:
                    # Fallback: assemble pair_key (handles verify-polluted hash metadata).
                    assembled = make_cross_input(
                        row.input,
                        col.input,
                        player_side=row.side,
                        opp_side=col.side,
                    )
                    pk = pair_key(bb_version, assembled, ASSEMBLER_VERSION)
                    p = cache.get_pair(pk)
                    if p is not None and str(p.get("rowBoardHash")) in ("verify", ""):
                        # Repair metadata so later index hits work.
                        cache.merge_pair(
                            pair_key=pk,
                            bb_version=bb_version,
                            row_board_hash=row.board_hash,
                            col_board_hash=col.board_hash,
                            shell_hash=sh,
                            assembler_version=ASSEMBLER_VERSION,
                            sims=0,
                            wins=0.0,
                            ties=0.0,
                            losses=0.0,
                            my_death_rate=None,
                            their_death_rate=None,
                            av_damage=None,
                            elapsed_ms=None,
                        )
                        p = cache.get_pair(pk)
                if p is None or not sims_sufficient(int(p["sims"]), target_sims):
                    mk = (row.board_id, col.board_id)
                    if mk not in missing_seen:
                        missing_seen.add(mk)
                        missing.append((row, col))
                    continue
                n = int(p["sims"])
                win = float(p["wins"]) / n
                tie = float(p["ties"]) / n
                s = win + 0.5 * tie
                scores[row.board_id][col.board_id] = PairStat(
                    s=s,
                    sims=n,
                    se2=se2_of_s(s, n),
                    my_death_rate=p.get("myDeathRate"),
                    av_damage=p.get("avDamage"),
                )
    return dict(scores), missing


def needed_pairs_across(
    boards: list[Board],
    panel_board_ids: set[str],
) -> list[tuple[Board, Board]]:
    by_id = {b.board_id: b for b in boards}
    cols = [by_id[i] for i in sorted(panel_board_ids) if i in by_id]
    out: list[tuple[Board, Board]] = []
    for row in boards:
        for col in cols:
            if row.game_id == col.game_id:
                continue
            out.append((row, col))
    return out


def ensure_pairs(
    boards: list[Board],
    cache: StrengthCache,
    *,
    bb_version: str,
    exe: Path,
    bb_dir: str,
    k: int = PANEL_GAMES,
    target_sims: int = ITERATIONS,
    iterations: int = ITERATIONS,
    max_duration: int = MAX_DURATION_MS,
    threads: int | None = None,
    dry_run: bool = False,
    fill_l1: bool = True,
    progress: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    """Backfill per-turn L0 matrices; optionally L1 cross-turn unions."""
    log = progress or (lambda m: print(m, flush=True))
    buckets = bucket_boards(boards)
    # L0
    l0 = backfill_version(
        boards,
        cache,
        bb_version=bb_version,
        exe=exe,
        bb_map={bb_version: bb_dir},
        k=k,
        target_sims=target_sims,
        iterations=iterations,
        max_duration=max_duration,
        threads=threads,
        dry_run=dry_run,
        progress=log,
    )
    l1_reports: list[dict[str, Any]] = []
    if fill_l1 and L1_ENABLED:
        turns = sorted({t for (v, t) in buckets if v == bb_version})
        panels: dict[int, set[str]] = {}
        for t in turns:
            bl = buckets[(bb_version, t)]
            panels[t] = set(build_panel(bl, bb_version=bb_version, turn=t, k=k).board_ids)

        # Only fill L1 cross-turn pairs for turns where some leave-one-game
        # candidate would fall below G_min at L0 (design §3.3). Turns 1–12
        # with ≥20 games almost never need this; avoid O(N²) union blow-up.
        thin_turns: list[int] = []
        for t in turns:
            bl = buckets[(bb_version, t)]
            games = {b.game_id for b in bl}
            # worst-case leave-one-game G = |games|-1
            if len(games) - 1 < G_MIN:
                thin_turns.append(t)

        if not thin_turns:
            log("L1 fill skipped: all turns have leave-one-game G ≥ G_min")
        for t in thin_turns:
            nearby = []
            panel_ids: set[str] = set()
            for tt in (t - 1, t, t + 1):
                if (bb_version, tt) not in buckets:
                    continue
                nearby.extend(buckets[(bb_version, tt)])
                panel_ids |= panels.get(tt, set())
            if not nearby or not panel_ids:
                continue
            by_id = {b.board_id: b for b in nearby}
            uniq = list(by_id.values())
            pairs = needed_pairs_across(uniq, panel_ids)
            jobs: list[PairJob] = []
            seen: set[str] = set()
            for row, col in pairs:
                j = make_pair_job(
                    row, col, bb_version=bb_version, cache=cache, target_sims=target_sims
                )
                if j is None or j.pair_key in seen:
                    continue
                seen.add(j.pair_key)
                jobs.append(j)
            info = {
                "turn": t,
                "pairsNeeded": len(pairs),
                "pairsMissing": len(jobs),
                "cacheHits": len(pairs) - len(jobs),
                "reason": "thin_L0",
            }
            if dry_run or not jobs:
                info["ran"] = 0
                info["wallSec"] = 0.0
            else:
                log(f"L1 union around t{t} (thin L0): missing {len(jobs)} / {len(pairs)}")
                run = execute_jobs(
                    jobs,
                    cache,
                    exe=exe,
                    bb_dir=bb_dir,
                    bb_version=bb_version,
                    iterations=iterations,
                    max_duration=max_duration,
                    threads=threads,
                    progress=log,
                )
                info["ran"] = run["ran"]
                info["wallSec"] = run["wallSec"]
                info["ok"] = run["ok"]
            l1_reports.append(info)
    return {"l0": l0, "l1": l1_reports}


def _hdt_block(board: Board) -> dict[str, Any]:
    lab = board.label or {}
    out: dict[str, Any] = {}
    for key, src in (
        ("winRate", "hdtWin"),
        ("tieRate", "hdtTie"),
        ("lossRate", "hdtLoss"),
    ):
        v = lab.get(src)
        if v is not None:
            out[key] = v
    return out


def evaluate_candidate(
    cand: Board,
    *,
    by_turn: dict[int, list[Board]],
    panels: dict[int, set[str]],
    scores: ScoreMap,
    g_min: int = G_MIN,
    l1_enabled: bool = L1_ENABLED,
    w_relax: float = W_RELAX,
    bootstrap_b: int = BOOTSTRAP_B,
    bootstrap_seed: int = 0,
    player_only: bool = False,
    panel_games_k: int = PANEL_GAMES,
    iterations: int = ITERATIONS,
) -> dict[str, Any]:
    level, R, slack = choose_level(
        cand,
        by_turn,
        g_min=g_min,
        l1_enabled=l1_enabled,
        l2_enabled=L2_ENABLED,
        player_only=player_only,
    )
    panel_ids = panel_ids_for_slack(cand.turn, slack, panels)
    O = opponent_set(R, panel_ids, scores, cand.board_id)
    core = round_robin(cand, R=R, O=O, scores=scores, w_relax=w_relax)
    flags: list[str] = []
    row: dict[str, Any] = {
        "boardId": cand.board_id,
        "gameId": cand.game_id,
        "turn": cand.turn,
        "side": cand.side,
        "bbVersion": cand.bb_version,
        "S": None if core is None else core["S"],
        "percentile": None if core is None else core["percentile"],
        "ci95": None,
        "widthPts": None,
        "level": level,
        "flags": flags,
        "nGames": 0 if core is None else core["nGames"],
        "nOppBoards": 0 if core is None else core["nOppBoards"],
        "nPeers": 0 if core is None else core["nPeers"],
        "panelGames": panel_games_k,
        "iterations": iterations,
        "mcSeS": None if core is None else core["mcSeS"],
        "aux": {} if core is None else core.get("aux") or {},
        "hdt": _hdt_block(cand),
        "engineVersion": ENGINE_VERSION,
    }
    if level == "insufficient":
        row["percentile"] = None
        row["ci95"] = None
        row["widthPts"] = None
        return row

    if core is None or core.get("percentile") is None:
        row["level"] = "insufficient"
        row["percentile"] = None
        return row

    import zlib

    seed = bootstrap_seed ^ (zlib.adler32(cand.board_id.encode("utf-8")) & 0xFFFFFFFF)
    ci, width = clustered_bootstrap_ci(
        cand,
        R=R,
        panel_board_ids=panel_ids,
        scores=scores,
        B=bootstrap_b,
        seed=seed,
        w_relax=w_relax,
        mc_noise=True,
    )
    row["ci95"] = ci
    row["widthPts"] = width
    if width is not None and width > WIDE_FLAG_GT:
        row["flags"] = list(row["flags"]) + ["wide"]
    return row


def run_percentile(
    *,
    bb_version: str,
    roots: list[str] | None = None,
    turns_jsonl: Path | None = None,
    cache_path: Path | None = None,
    exe: Path | None = None,
    bb_map: dict[str, str] | None = None,
    turns: list[int] | None = None,
    k: int = PANEL_GAMES,
    target_sims: int = ITERATIONS,
    iterations: int = ITERATIONS,
    max_duration: int = MAX_DURATION_MS,
    threads: int | None = None,
    bootstrap_b: int = BOOTSTRAP_B,
    player_only: bool = False,
    fill_missing: bool = True,
    dry_run_fill: bool = False,
    out_path: Path | None = None,
    progress: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    log = progress or (lambda m: print(m, flush=True))
    turns_by = load_turns(turns_jsonl or DEFAULT_TURNS)
    max_turn = max(turns) if turns else 99
    boards = collect_boards(
        roots or default_diag_roots(),
        bb_version,
        turns_by,
        max_turn=max_turn,
        include_opponent=INCLUDE_OPPONENT_BOARDS and not player_only,
    )
    if turns is not None:
        want = set(turns)
        # Keep adjacent turns for L1 even if candidate filter is narrower.
        if L1_ENABLED:
            expand = set()
            for t in want:
                expand.update((t - 1, t, t + 1))
            boards = [b for b in boards if b.turn in expand]
        else:
            boards = [b for b in boards if b.turn in want]

    cache_path = cache_path or DEFAULT_CACHE
    exe = exe or DEFAULT_EXE
    bb_map = bb_map or load_bb_map()
    bb_dir = bb_map.get(bb_version)
    if not bb_dir or not os.path.isfile(os.path.join(bb_dir, "BobsBuddy.dll")):
        raise FileNotFoundError(f"no BobsBuddy.dll for {bb_version}: {bb_dir}")

    fill_report: dict[str, Any] | None = None
    with StrengthCache(cache_path) as cache:
        if fill_missing:
            log("ensuring pair cache (L0 + L1 unions)…")
            fill_report = ensure_pairs(
                boards,
                cache,
                bb_version=bb_version,
                exe=Path(exe),
                bb_dir=bb_dir,
                k=k,
                target_sims=target_sims,
                iterations=iterations,
                max_duration=max_duration,
                threads=threads,
                dry_run=dry_run_fill,
                fill_l1=L1_ENABLED,
                progress=log,
            )

        buckets = bucket_boards(boards)
        by_turn: dict[int, list[Board]] = {
            t: bl for (v, t), bl in buckets.items() if v == bb_version
        }
        panels: dict[int, set[str]] = {}
        for t, bl in by_turn.items():
            panels[t] = set(build_panel(bl, bb_version=bb_version, turn=t, k=k).board_ids)

        # Score map: same-turn only unless some turn is below G_min (needs L1).
        thin = any(len({b.game_id for b in bl}) - 1 < G_MIN for bl in by_turn.values())
        slack = 1 if (thin and L1_ENABLED) else 0
        log(f"loading score matrix from cache (turn_slack={slack})…")
        scores, missing = build_score_map(
            boards,
            panels,
            cache,
            bb_version=bb_version,
            target_sims=target_sims,
            turn_slack=slack,
        )
        if missing and fill_missing and not dry_run_fill:
            log(f"score map still missing {len(missing)} pairs; running top-up batch")
            jobs: list[PairJob] = []
            seen: set[str] = set()
            for row, col in missing:
                j = make_pair_job(
                    row, col, bb_version=bb_version, cache=cache, target_sims=target_sims
                )
                if j is None or j.pair_key in seen:
                    continue
                seen.add(j.pair_key)
                jobs.append(j)
            if jobs:
                execute_jobs(
                    jobs,
                    cache,
                    exe=Path(exe),
                    bb_dir=bb_dir,
                    bb_version=bb_version,
                    iterations=iterations,
                    max_duration=max_duration,
                    threads=threads,
                    progress=log,
                )
                scores, missing = build_score_map(
                    boards,
                    panels,
                    cache,
                    bb_version=bb_version,
                    target_sims=target_sims,
                    turn_slack=slack,
                )

        cand_turns = set(turns) if turns is not None else set(by_turn)
        candidates = [
            b
            for t in sorted(cand_turns)
            for b in by_turn.get(t, [])
            if b.side == "Player"
        ]
        log(f"evaluating {len(candidates)} Player candidates (B={bootstrap_b})…")
        rows: list[dict[str, Any]] = []
        for i, cand in enumerate(candidates):
            if (i + 1) % 25 == 0 or i == 0:
                log(f"  candidate {i + 1}/{len(candidates)} turn={cand.turn}")
            rows.append(
                evaluate_candidate(
                    cand,
                    by_turn=by_turn,
                    panels=panels,
                    scores=scores,
                    g_min=G_MIN,
                    l1_enabled=L1_ENABLED,
                    w_relax=W_RELAX,
                    bootstrap_b=bootstrap_b,
                    player_only=player_only,
                    panel_games_k=k,
                    iterations=iterations,
                )
            )

    out_path = out_path or strength_out_path(bb_version)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    summary = {
        "bbVersion": bb_version,
        "nCandidates": len(rows),
        "out": str(out_path),
        "missingAfter": len(missing),
        "levels": _count_by(rows, "level"),
        "nWide": sum(1 for r in rows if "wide" in (r.get("flags") or [])),
        "nL1": sum(1 for r in rows if str(r.get("level", "")).startswith("L1")),
        "fill": fill_report,
    }
    log(json.dumps({k: summary[k] for k in summary if k != "fill"}, ensure_ascii=False))
    return summary


def _count_by(rows: list[dict], key: str) -> dict[str, int]:
    out: dict[str, int] = defaultdict(int)
    for r in rows:
        out[str(r.get(key))] += 1
    return dict(out)


def exit_width_stats(
    rows: list[dict[str, Any]] | None = None,
    *,
    jsonl_path: Path | None = None,
    max_turn: int = 12,
    min_games_queue: int = 20,
    median_le: float = EXIT_WIDTH_MEDIAN_LE,
    p80_le: float = EXIT_WIDTH_P80_LE,
    frac: float = EXIT_WIDTH_FRAC,
) -> dict[str, Any]:
    """P3 exit criterion #1 (ADR-0014): median ≤25 and ≥80% ≤30 (Player, turn≤max_turn)."""
    if rows is None:
        if jsonl_path is None:
            raise ValueError("rows or jsonl_path required")
        rows = []
        with Path(jsonl_path).open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    rows.append(json.loads(line))

    scoped = [
        r
        for r in rows
        if r.get("side") == "Player"
        and isinstance(r.get("turn"), int)
        and int(r["turn"]) <= max_turn
        and r.get("percentile") is not None
        and r.get("widthPts") is not None
    ]
    widths = [float(r["widthPts"]) for r in scoped]
    n_games = len({r["gameId"] for r in scoped})
    if not widths:
        return {
            "n": 0,
            "nGames": n_games,
            "ok": False,
            "reason": "no rows with percentile+width",
        }
    widths_sorted = sorted(widths)
    mid = len(widths_sorted) // 2
    if len(widths_sorted) % 2:
        median = widths_sorted[mid]
    else:
        median = 0.5 * (widths_sorted[mid - 1] + widths_sorted[mid])
    frac_le_p80 = sum(1 for w in widths if w <= p80_le) / len(widths)
    frac_le20 = sum(1 for w in widths if w <= 20.0) / len(widths)
    ok = (
        n_games >= min_games_queue
        and median <= median_le
        and frac_le_p80 >= frac
    )
    return {
        "n": len(widths),
        "nGames": n_games,
        "maxTurn": max_turn,
        "medianWidthPts": median,
        "fracWidthLeP80Cap": frac_le_p80,
        "fracWidthLe20": frac_le20,
        "p80WidthPts": widths_sorted[max(0, int(math.ceil(0.80 * len(widths_sorted)) - 1))],
        "p95WidthPts": widths_sorted[max(0, int(math.ceil(0.95 * len(widths_sorted)) - 1))],
        "thresholds": {
            "medianLe": median_le,
            "p80Le": p80_le,
            "frac": frac,
            "minGames": min_games_queue,
        },
        "ok": ok,
        "levels": _count_by(scoped, "level"),
        "nWide": sum(1 for r in scoped if "wide" in (r.get("flags") or [])),
    }


def load_strength_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with Path(path).open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows
