# -*- coding: utf-8 -*-
"""Sample boards by S_orig tertile; full-permute; summarize top-20% commonalities."""
from __future__ import annotations

import hashlib
import itertools
import json
import math
import random
import sys
from dataclasses import replace
from pathlib import Path
from typing import Any, Callable

_REPO = Path(__file__).resolve().parents[2]
_TOOLS = _REPO / "tools"
if str(_TOOLS) not in sys.path:
    sys.path.insert(0, str(_TOOLS))

from strength import ASSEMBLER_VERSION  # noqa: E402
from strength.assembler import board_hash, shell_hash  # noqa: E402
from strength.batch import load_bb_map  # noqa: E402
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

from .features import (  # noqa: E402
    FEATURE_KEYS,
    compare_groups,
    extract_perm_features,
)
from .reorder import apply_order_to_input, card_id, extract_side_items  # noqa: E402
from .run import make_job, run_jobs_chunked, score_board_against_pool  # noqa: E402

DEFAULT_SEED = "enumerate-2026-10-07"
DEFAULT_PER_STRATUM = 2
DEFAULT_MIN_N = 2
DEFAULT_MAX_N = 5
DEFAULT_TOP_FRAC = 0.20
DEFAULT_PAIR_CAP = 150_000


def side_items(board: Board) -> list[dict]:
    return extract_side_items(board.input, board.side)


def n_minions(board: Board) -> int:
    return len(side_items(board))


def with_order(board: Board, order: list[int]) -> Board:
    new_inp = apply_order_to_input(board.input, board.side, order)
    return replace(
        board,
        input=new_inp,
        board_hash=board_hash(new_inp, board.side),
        shell_hash=shell_hash(new_inp),
    )


def tertile_label(rank0: int, n: int) -> str:
    """rank0 in 0..n-1 ascending by S; low / mid / high."""
    if n <= 0:
        return "mid"
    if n == 1:
        return "mid"
    # boundaries at n/3 and 2n/3
    lo = n // 3
    hi = (2 * n) // 3
    if rank0 < lo:
        return "low"
    if rank0 < hi:
        return "mid"
    return "high"


def sample_boards(
    pool: list[Board],
    s_orig: dict[str, float],
    *,
    per_stratum: int = DEFAULT_PER_STRATUM,
    min_n: int = DEFAULT_MIN_N,
    max_n: int = DEFAULT_MAX_N,
    seed: str = DEFAULT_SEED,
    turn: int = 0,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Return sample meta rows + shortfall info."""
    eligible = [b for b in pool if min_n <= n_minions(b) <= max_n and b.board_id in s_orig]
    ranked = sorted(eligible, key=lambda b: (s_orig[b.board_id], b.board_id))
    n = len(ranked)
    buckets: dict[str, list[Board]] = {"low": [], "mid": [], "high": []}
    for i, b in enumerate(ranked):
        buckets[tertile_label(i, n)].append(b)

    rng = random.Random(hashlib.sha256(f"{seed}|t{turn}".encode()).hexdigest())
    picked: list[dict[str, Any]] = []
    shortfall: dict[str, int] = {}
    for stratum in ("low", "mid", "high"):
        cand = list(buckets[stratum])
        need = per_stratum
        if len(cand) < need:
            shortfall[stratum] = need - len(cand)
        rng.shuffle(cand)
        for b in cand[:need]:
            picked.append(
                {
                    "boardId": b.board_id,
                    "gameId": b.game_id,
                    "turn": b.turn,
                    "side": b.side,
                    "stratum": stratum,
                    "n": n_minions(b),
                    "S_orig": s_orig[b.board_id],
                    "cardIdsOrig": [card_id(m) for m in side_items(b)],
                    "nFactorial": math.factorial(n_minions(b)),
                }
            )
    meta = {
        "nEligible": n,
        "nPool": len(pool),
        "stratumCounts": {k: len(v) for k, v in buckets.items()},
        "shortfall": shortfall,
        "nSampled": len(picked),
    }
    return picked, meta


def top_k_count(n_perms: int, frac: float = DEFAULT_TOP_FRAC) -> int:
    return max(1, int(math.ceil(frac * n_perms)))


def select_top_bottom(
    rows: list[dict[str, Any]], frac: float = DEFAULT_TOP_FRAC
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], int]:
    """rows must have S; expand ties at boundary. Returns top, bottom, topExpanded flag count extra."""
    ranked = sorted(rows, key=lambda r: (-float(r["S"]), r["permId"]))
    k = top_k_count(len(ranked), frac)
    if not ranked:
        return [], [], 0
    # expand top: include all with S >= S of k-th
    threshold_top = float(ranked[k - 1]["S"])
    top = [r for r in ranked if float(r["S"]) >= threshold_top - 1e-15]
    # bottom: lowest k, expand ties
    ranked_asc = list(reversed(ranked))
    threshold_bot = float(ranked_asc[k - 1]["S"])
    bottom = [r for r in ranked_asc if float(r["S"]) <= threshold_bot + 1e-15]
    expanded = max(0, len(top) - k)
    return top, bottom, expanded


def estimate_pairs(samples: list[dict[str, Any]], pool_size: int) -> int:
    opp = max(0, pool_size - 1)
    return sum(int(s["nFactorial"]) * opp for s in samples)


def run_enumerate(
    *,
    bb_version: str = "1.85.0.0",
    turns: list[int] | None = None,
    per_stratum: int = DEFAULT_PER_STRATUM,
    min_n: int = DEFAULT_MIN_N,
    max_n: int = DEFAULT_MAX_N,
    top_frac: float = DEFAULT_TOP_FRAC,
    seed: str = DEFAULT_SEED,
    pair_cap: int = DEFAULT_PAIR_CAP,
    roots: list[str] | None = None,
    turns_jsonl: Path | None = None,
    cache_path: Path | None = None,
    exe: Path | None = None,
    bb_map_path: Path | None = None,
    out_dir: Path | None = None,
    iterations: int = ITERATIONS,
    max_duration: int = MAX_DURATION_MS,
    threads: int | None = None,
    chunk_size: int = 1500,
    dry_run: bool = False,
    progress: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    log = progress or (lambda m: print(m, flush=True))
    turns = turns or [3, 4]
    roots = roots if roots is not None else default_diag_roots()
    turns_by = load_turns(turns_jsonl or DEFAULT_TURNS)
    cache_path = cache_path or DEFAULT_CACHE
    exe = exe or DEFAULT_EXE
    if out_dir is None:
        out_dir = _REPO / "data" / "positioning" / bb_version / "enumerate"
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
    buckets = bucket_boards(boards)
    bb_map = load_bb_map(bb_map_path or DEFAULT_BB_MAP)
    bb_dir = bb_map.get(bb_version)
    if not bb_dir:
        raise SystemExit(f"no bb-dir for {bb_version}")

    sample_all: list[dict[str, Any]] = []
    sample_meta: dict[str, Any] = {}
    perms_all: list[dict[str, Any]] = []
    top_all: list[dict[str, Any]] = []
    run_info: list[dict[str, Any]] = []
    board_summaries: list[dict[str, Any]] = []
    pairs_remaining = pair_cap
    truncated_boards: list[str] = []

    with StrengthCache(cache_path) as cache:
        # Phase 1: S_orig for full pools + sample
        for t in turns:
            pool = buckets.get((bb_version, t), [])
            if len(pool) < 2:
                log(f"turn {t}: skip pool={len(pool)}")
                continue
            # ensure orig pairs present
            jobs = []
            seen: set[str] = set()
            for row in pool:
                for col in pool:
                    if col.board_id == row.board_id:
                        continue
                    j = make_job(
                        row, col, bb_version=bb_version, cache=cache, target_sims=iterations
                    )
                    if j is None or j.pair_key in seen:
                        continue
                    seen.add(j.pair_key)
                    jobs.append(j)
            info: dict[str, Any] = {
                "turn": t,
                "nPool": len(pool),
                "origMissing": len(jobs),
                "dryRun": dry_run,
            }
            log(f"turn {t}: pool={len(pool)} orig_missing={len(jobs)}")
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
                info["origRun"] = run

            s_orig: dict[str, float] = {}
            for b in pool:
                s, n_ok, miss = score_board_against_pool(
                    b, pool, bb_version=bb_version, cache=cache
                )
                if s is not None:
                    s_orig[b.board_id] = s

            picked, meta = sample_boards(
                pool,
                s_orig,
                per_stratum=per_stratum,
                min_n=min_n,
                max_n=max_n,
                seed=seed,
                turn=t,
            )
            sample_meta[str(t)] = meta
            sample_all.extend(picked)
            est = estimate_pairs(picked, len(pool))
            info["sample"] = meta
            info["pairsEstimated"] = est
            log(
                f"turn {t}: sampled={meta['nSampled']} shortfall={meta['shortfall']} "
                f"pairsEst={est}"
            )
            run_info.append(info)

        if dry_run:
            summary = {
                "mode": "enumerate",
                "dryRun": True,
                "bbVersion": bb_version,
                "turns": turns,
                "seed": seed,
                "perStratum": per_stratum,
                "minN": min_n,
                "maxN": max_n,
                "topFrac": top_frac,
                "pairCap": pair_cap,
                "sample": sample_all,
                "sampleMeta": sample_meta,
                "runInfo": run_info,
                "pairsEstimatedTotal": sum(int(i.get("pairsEstimated") or 0) for i in run_info),
            }
            (out_dir / "sample.json").write_text(
                json.dumps({"sample": sample_all, "meta": sample_meta}, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            (out_dir / "summary.json").write_text(
                json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            log(f"dry-run wrote {out_dir}")
            return summary

        # Phase 2: permute each sample
        by_id = {b.board_id: b for b in boards}
        for t in turns:
            pool = buckets.get((bb_version, t), [])
            if len(pool) < 2:
                continue
            turn_samples = [s for s in sample_all if s["turn"] == t]
            for sm in turn_samples:
                bid = sm["boardId"]
                b0 = by_id[bid]
                items = side_items(b0)
                n = len(items)
                orders = list(itertools.permutations(range(n)))
                # Plan jobs under remaining cap (only commit a perm if all its misses fit)
                jobs = []
                seen: set[str] = set()
                variants: list[tuple[list[int], Board]] = []
                stopped = False
                for order in orders:
                    order_l = list(order)
                    cand = with_order(b0, order_l)
                    need: list = []
                    for col in pool:
                        if col.board_id == bid:
                            continue
                        j = make_job(
                            cand,
                            col,
                            bb_version=bb_version,
                            cache=cache,
                            target_sims=iterations,
                        )
                        if j is None or j.pair_key in seen:
                            continue
                        need.append(j)
                    if len(need) > pairs_remaining:
                        stopped = True
                        break
                    for j in need:
                        seen.add(j.pair_key)
                        jobs.append(j)
                    pairs_remaining -= len(need)
                    variants.append((order_l, cand))

                info = {
                    "turn": t,
                    "boardId": bid,
                    "nPerms": len(orders),
                    "pairsPlanned": len(jobs),
                    "truncated": stopped,
                }
                log(
                    f"board {bid} t{t} n={n}: perms={len(orders)} missing_pairs={len(jobs)} "
                    f"capLeft={pairs_remaining}"
                )
                if stopped:
                    truncated_boards.append(bid)
                if jobs:
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
                    info["run"] = run
                run_info.append(info)

                if stopped and not variants:
                    continue

                # Score all completed variants (even if truncated mid-board, score what we built)
                board_perm_rows: list[dict[str, Any]] = []
                s_orig_b = float(sm["S_orig"])
                for pi, (order_l, cand) in enumerate(variants):
                    s, n_ok, miss = score_board_against_pool(
                        cand, pool, bb_version=bb_version, cache=cache
                    )
                    if s is None:
                        continue
                    feats = extract_perm_features(items, order_l)
                    row = {
                        "boardId": bid,
                        "gameId": sm["gameId"],
                        "turn": t,
                        "side": sm["side"],
                        "stratum": sm["stratum"],
                        "permId": pi,
                        "order": order_l,
                        "S": s,
                        "S_orig": s_orig_b,
                        "deltaS": s - s_orig_b,
                        "nOpp": n_ok,
                        "nMissing": miss,
                        "isOrig": order_l == list(range(n)),
                        **{k: feats[k] for k in FEATURE_KEYS},
                        "cardIds": feats["cardIds"],
                    }
                    board_perm_rows.append(row)
                    perms_all.append(row)

                if not board_perm_rows:
                    continue

                # ranks
                ranked = sorted(board_perm_rows, key=lambda r: (-r["S"], r["permId"]))
                s_best = float(ranked[0]["S"])
                for rank, r in enumerate(ranked, start=1):
                    r["rank"] = rank
                    r["percentile"] = (rank - 1) / max(1, len(ranked) - 1) if len(ranked) > 1 else 0.0
                    r["gapToBest"] = s_best - float(r["S"])

                top, bottom, expanded = select_top_bottom(board_perm_rows, top_frac)
                for r in top:
                    r["inTop"] = True
                    top_all.append(r)

                orig_row = next((r for r in board_perm_rows if r["isOrig"]), None)
                cmp = compare_groups(
                    [{k: r[k] for k in FEATURE_KEYS} for r in top],
                    [{k: r[k] for k in FEATURE_KEYS} for r in board_perm_rows],
                    [{k: r[k] for k in FEATURE_KEYS} for r in bottom],
                )
                board_summaries.append(
                    {
                        "boardId": bid,
                        "turn": t,
                        "stratum": sm["stratum"],
                        "n": n,
                        "nPermsScored": len(board_perm_rows),
                        "S_orig": s_orig_b,
                        "S_best": s_best,
                        "deltaBest": s_best - s_orig_b,
                        "origRank": orig_row["rank"] if orig_row else None,
                        "origPercentile": orig_row["percentile"] if orig_row else None,
                        "topExpandedExtra": expanded,
                        "orderOrig": list(range(n)),
                        "orderBest": ranked[0]["order"],
                        "cardIdsOrig": sm["cardIdsOrig"],
                        "cardIdsBest": ranked[0]["cardIds"],
                        "features": cmp,
                        "truncated": bid in truncated_boards,
                    }
                )

    # Cross-board feature agreement
    features_summary = _aggregate_commonality(board_summaries)

    # Persist
    (out_dir / "sample.json").write_text(
        json.dumps({"sample": sample_all, "meta": sample_meta}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    with (out_dir / "perms.jsonl").open("w", encoding="utf-8") as f:
        for r in perms_all:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    with (out_dir / "top.jsonl").open("w", encoding="utf-8") as f:
        for r in top_all:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    (out_dir / "features.json").write_text(
        json.dumps(
            {"boards": board_summaries, "aggregate": features_summary},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    summary = {
        "mode": "enumerate",
        "dryRun": False,
        "bbVersion": bb_version,
        "turns": turns,
        "seed": seed,
        "perStratum": per_stratum,
        "minN": min_n,
        "maxN": max_n,
        "topFrac": top_frac,
        "pairCap": pair_cap,
        "pairsRemaining": pairs_remaining,
        "truncatedBoards": truncated_boards,
        "nSampled": len(sample_all),
        "nPermRows": len(perms_all),
        "nTopRows": len(top_all),
        "runInfo": run_info,
        "sampleMeta": sample_meta,
        "boardSummaries": [
            {
                k: bs[k]
                for k in (
                    "boardId",
                    "turn",
                    "stratum",
                    "n",
                    "S_orig",
                    "S_best",
                    "deltaBest",
                    "origRank",
                    "origPercentile",
                    "cardIdsOrig",
                    "cardIdsBest",
                    "truncated",
                )
            }
            for bs in board_summaries
        ],
        "aggregate": features_summary,
        "conclusionHints": features_summary.get("conclusionHints"),
    }
    (out_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    log(f"wrote {out_dir} (perms={len(perms_all)} top={len(top_all)})")
    return summary


def _aggregate_commonality(board_summaries: list[dict[str, Any]]) -> dict[str, Any]:
    """Across boards: how often topMinusBottom feature agrees in sign; mean effect."""
    if not board_summaries:
        return {"nBoards": 0}

    # per feature: list of topMinusBottom across boards (skip None)
    per_key: dict[str, list[float]] = {k: [] for k in FEATURE_KEYS}
    for bs in board_summaries:
        diff = (bs.get("features") or {}).get("topMinusBottom") or {}
        for k in FEATURE_KEYS:
            v = diff.get(k)
            if v is not None:
                per_key[k].append(float(v))

    table: dict[str, Any] = {}
    agreeing: list[str] = []
    for k, vals in per_key.items():
        if not vals:
            table[k] = {"n": 0}
            continue
        mean = sum(vals) / len(vals)
        pos = sum(1 for v in vals if v > 1e-9)
        neg = sum(1 for v in vals if v < -1e-9)
        # "agree" = same sign in >= 2/3 of boards with data
        n = len(vals)
        agree_pos = pos >= math.ceil(2 * n / 3) and mean > 0
        agree_neg = neg >= math.ceil(2 * n / 3) and mean < 0
        table[k] = {
            "n": n,
            "meanTopMinusBottom": mean,
            "nPos": pos,
            "nNeg": neg,
            "agreePos": agree_pos,
            "agreeNeg": agree_neg,
        }
        if agree_pos or agree_neg:
            agreeing.append(k)

    # orig percentile stats
    orig_pcts = [
        float(bs["origPercentile"])
        for bs in board_summaries
        if bs.get("origPercentile") is not None
    ]
    deltas = [float(bs["deltaBest"]) for bs in board_summaries if bs.get("deltaBest") is not None]

    hints = {
        "agreeingFeatures": agreeing,
        "nAgreeing": len(agreeing),
        "readable": (
            f"{len(agreeing)} feature(s) agree on top-vs-bottom across ≥2/3 boards: {agreeing}"
            if agreeing
            else "no stable feature commonality (top vs bottom) across ≥2/3 boards"
        ),
        "meanDeltaBest": (sum(deltas) / len(deltas)) if deltas else None,
        "meanOrigPercentile": (sum(orig_pcts) / len(orig_pcts)) if orig_pcts else None,
    }
    return {
        "nBoards": len(board_summaries),
        "byFeature": table,
        "conclusionHints": hints,
        "byTurn": _by_turn_slice(board_summaries),
    }


def _by_turn_slice(board_summaries: list[dict[str, Any]]) -> dict[str, Any]:
    turns = sorted({int(bs["turn"]) for bs in board_summaries})
    out: dict[str, Any] = {}
    for t in turns:
        subset = [bs for bs in board_summaries if int(bs["turn"]) == t]
        out[str(t)] = {
            "nBoards": len(subset),
            "meanDeltaBest": sum(float(bs["deltaBest"]) for bs in subset) / len(subset),
            "meanOrigPercentile": sum(float(bs["origPercentile"]) for bs in subset) / len(subset),
        }
    return out
