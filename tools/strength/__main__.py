# -*- coding: utf-8 -*-
"""CLI: strength pool / panel / cache / incremental batch.

Examples:
  python -m tools.strength backfill --bb-version 1.85.0.0 --turns 1 --dry-run
  python -m tools.strength backfill --bb-version 1.85.0.0 --turns 1
  python -m tools.strength increment --bb-version 1.85.0.0 --game-id 20261002_112126_685dd2
  python -m tools.strength verify-p3t0 --limit 80
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

# Ensure `standard_layer` import path (same pattern as spikes/strength-cross).
_REPO = Path(__file__).resolve().parents[2]
_TOOLS = _REPO / "tools"
if str(_TOOLS) not in sys.path:
    sys.path.insert(0, str(_TOOLS))

from . import ASSEMBLER_VERSION  # noqa: E402
from .assembler import pair_key  # noqa: E402
from .batch import (  # noqa: E402
    backfill_version,
    increment_game,
    load_bb_map,
    rates_within_3sigma,
    run_replay_batch,
)
from .cache import StrengthCache  # noqa: E402
from .config import BOOTSTRAP_B, ITERATIONS, MAX_DURATION_MS, PANEL_GAMES  # noqa: E402
from .engine import (  # noqa: E402
    ensure_pairs,
    exit_width_stats,
    load_strength_jsonl,
    run_percentile,
    strength_out_path,
)
from .pool import collect_boards, load_turns  # noqa: E402
from .sim_pools import (  # noqa: E402
    judge_cross_replay,
    latest_installed_member,
    load_table,
    member_versions,
    pool_join,
    sim_pool_of,
)
from ._paths import (  # noqa: E402
    DEFAULT_CACHE,
    DEFAULT_EXE,
    DEFAULT_TURNS,
    default_diag_roots,
)


def _parse_turns(s: str | None) -> list[int] | None:
    if not s:
        return None
    out: list[int] = []
    for part in s.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            a, b = part.split("-", 1)
            out.extend(range(int(a), int(b) + 1))
        else:
            out.append(int(part))
    return out


def _resolve_pool(args: argparse.Namespace) -> str:
    if getattr(args, "sim_pool", None):
        return str(args.sim_pool)
    if getattr(args, "bb_version", None):
        return sim_pool_of(args.bb_version)
    print("pass --sim-pool or --bb-version", file=sys.stderr)
    raise SystemExit(2)


def _collect_pool(args: argparse.Namespace, turns_by: dict, *, max_turn: int | None = None):
    pool = _resolve_pool(args)
    boards = collect_boards(
        args.roots or default_diag_roots(),
        pool,
        turns_by,
        versions=member_versions(pool),
        max_turn=max_turn,
        include_opponent=not args.player_only,
    )
    return pool, boards


def _print_budget(missing: int, seconds: float, max_hours: float) -> bool:
    print(
        f"pairsMissing={missing} roughSec={seconds:.0f} "
        f"(single-thread median elapsedMs; cap {max_hours:g}h)",
        flush=True,
    )
    if seconds > max_hours * 3600:
        print(
            "rough estimate exceeds the cap; not starting simulations. "
            "Re-run with a higher --max-hours after the owner agrees.",
            flush=True,
        )
        return False
    return True


def cmd_backfill(args: argparse.Namespace) -> int:
    turns_by = load_turns(Path(args.turns_jsonl))
    want = _parse_turns(args.turns)
    pool, boards = _collect_pool(
        args,
        turns_by,
        max_turn=max(want or [99]),
    )
    if want:
        boards = [b for b in boards if b.turn in set(want)]
    print(
        f"pooled {len(boards)} boards for simPool {pool} "
        f"members={','.join(member_versions(pool))} "
        f"(opponent={'off' if args.player_only else 'on'})",
        flush=True,
    )
    with StrengthCache(args.cache) as cache:
        if not args.dry_run:
            probe = backfill_version(
                boards,
                cache,
                bb_version=pool,
                exe=Path(args.exe),
                bb_map=load_bb_map(Path(args.bb_map)) if args.bb_map else None,
                turns=want,
                k=args.panel_games,
                target_sims=args.iterations,
                iterations=args.iterations,
                max_duration=args.max_duration,
                threads=args.threads,
                dry_run=True,
            )
            med = cache.median_elapsed_ms() or 50.0
            seconds = probe["pairsMissing"] * med / 1000.0
            if not _print_budget(probe["pairsMissing"], seconds, args.max_hours):
                print(json.dumps(probe, ensure_ascii=False, indent=2))
                return 3
        report = backfill_version(
            boards,
            cache,
            bb_version=pool,
            exe=Path(args.exe),
            bb_map=load_bb_map(Path(args.bb_map)) if args.bb_map else None,
            turns=want,
            k=args.panel_games,
            target_sims=args.iterations,
            iterations=args.iterations,
            max_duration=args.max_duration,
            threads=args.threads,
            dry_run=args.dry_run,
        )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if args.out:
        Path(args.out).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


def cmd_increment(args: argparse.Namespace) -> int:
    turns_by = load_turns(Path(args.turns_jsonl))
    pool, boards = _collect_pool(args, turns_by)
    with StrengthCache(args.cache) as cache:
        report = increment_game(
            boards,
            cache,
            bb_version=pool,
            game_id=args.game_id,
            exe=Path(args.exe),
            bb_map=load_bb_map(Path(args.bb_map)) if args.bb_map else None,
            k=args.panel_games,
            target_sims=args.iterations,
            iterations=args.iterations,
            max_duration=args.max_duration,
            threads=args.threads,
            dry_run=args.dry_run,
        )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


def cmd_percentile(args: argparse.Namespace) -> int:
    pool = _resolve_pool(args)
    turns = _parse_turns(args.turns)
    if not args.no_fill:
        turns_by = load_turns(Path(args.turns_jsonl))
        max_turn = max(turns) if turns else 99
        _pool, boards = _collect_pool(args, turns_by, max_turn=max_turn)
        if turns:
            keep = set()
            for t in turns:
                keep.update((t - 1, t, t + 1))
            boards = [b for b in boards if b.turn in keep]
        bb_map = load_bb_map(Path(args.bb_map)) if args.bb_map else None
        bb_map = bb_map or load_bb_map()
        dll_ver = latest_installed_member(pool, bb_map)
        bb_dir = bb_map.get(dll_ver) if dll_ver else None
        if not bb_dir:
            print(f"no DLL for simPool {pool}", file=sys.stderr)
            return 2
        with StrengthCache(args.cache) as cache:
            probe = ensure_pairs(
                boards,
                cache,
                bb_version=pool,
                exe=Path(args.exe),
                bb_dir=bb_dir,
                k=args.panel_games,
                target_sims=args.iterations,
                iterations=args.iterations,
                max_duration=args.max_duration,
                threads=args.threads,
                dry_run=True,
            )
            missing = int(probe["l0"]["pairsMissing"]) + sum(
                int(r["pairsMissing"]) for r in probe["l1"]
            )
            med = cache.median_elapsed_ms() or 50.0
            seconds = missing * med / 1000.0
        if not _print_budget(missing, seconds, args.max_hours):
            print(json.dumps({"simPool": pool, "dllVersion": dll_ver, "pairsMissing": missing}, ensure_ascii=False, indent=2))
            return 3
        if args.dry_run:
            print(json.dumps({"simPool": pool, "dllVersion": dll_ver, "pairsMissing": missing, "dryRun": True}, ensure_ascii=False, indent=2))
            return 0
    if args.dry_run:
        print(json.dumps({"simPool": pool, "dryRun": True, "fill": "skipped"}, ensure_ascii=False))
        return 0
    bb_map = load_bb_map(Path(args.bb_map)) if args.bb_map else None
    report = run_percentile(
        bb_version=pool,
        roots=args.roots,
        turns_jsonl=Path(args.turns_jsonl),
        cache_path=Path(args.cache),
        exe=Path(args.exe),
        bb_map=bb_map,
        turns=turns,
        k=args.panel_games,
        target_sims=args.iterations,
        iterations=args.iterations,
        max_duration=args.max_duration,
        threads=args.threads,
        bootstrap_b=args.bootstrap,
        player_only=args.player_only,
        fill_missing=not args.no_fill,
        dry_run_fill=args.dry_run,
        out_path=Path(args.out) if args.out else None,
    )
    print(json.dumps({k: report[k] for k in report if k != "fill"}, ensure_ascii=False, indent=2))
    if args.stats_out:
        rows = load_strength_jsonl(Path(report["out"]))
        stats = exit_width_stats(rows, max_turn=args.max_turn)
        Path(args.stats_out).write_text(json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(stats, ensure_ascii=False, indent=2))
    return 0


def cmd_exit_width(args: argparse.Namespace) -> int:
    path = Path(args.jsonl) if args.jsonl else strength_out_path(args.bb_version)
    rows = load_strength_jsonl(path)
    stats = exit_width_stats(rows, max_turn=args.max_turn)
    print(json.dumps(stats, ensure_ascii=False, indent=2))
    if args.out:
        Path(args.out).write_text(json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0 if stats.get("ok") else 1


def cmd_verify_p3t0(args: argparse.Namespace) -> int:
    """Re-sim a sample of out_both pairs; require ≥99% within 3σ of historical."""
    baseline = Path(args.baseline)
    jobs_path = baseline / "cross_results.jobs.jsonl"
    results_path = baseline / "cross_results.results.jsonl"
    if not jobs_path.is_file() or not results_path.is_file():
        print(f"missing baseline files under {baseline}", file=sys.stderr)
        return 2

    hist = {}
    with results_path.open(encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            if r.get("ok") and r.get("id"):
                hist[r["id"]] = r

    jobs = []
    with jobs_path.open(encoding="utf-8") as f:
        for i, line in enumerate(f):
            if args.limit and len(jobs) >= args.limit:
                break
            if args.stride > 1 and (i % args.stride) != 0:
                continue
            j = json.loads(line)
            if j.get("id") in hist:
                jobs.append(j)

    bb_map = load_bb_map(Path(args.bb_map))
    bb_dir = bb_map.get(args.bb_version)
    if not bb_dir:
        print("no bb dir", file=sys.stderr)
        return 2

    # Optionally also write through cache to exercise merge path.
    # Never write placeholder hashes into the production strength cache — that
    # poisons (rowBoardHash,colBoardHash,shellHash) index lookups used by P3-T3.
    cache_path = Path(args.cache) if args.cache else None
    if cache_path and cache_path.resolve() == DEFAULT_CACHE.resolve() and not args.allow_cache_write:
        print(
            "verify-p3t0: refusing to write placeholder hashes into default cache; "
            "pass a temp --cache or --allow-cache-write",
            flush=True,
        )
        cache_path = None
    cache = StrengthCache(cache_path) if cache_path else None

    results, summary = run_replay_batch(
        Path(args.exe),
        bb_dir,
        [{"id": j["id"], "input": j["input"]} for j in jobs],
        iterations=args.iterations,
        max_duration=args.max_duration,
        threads=args.threads,
    )
    by_id = {r.get("id"): r for r in results}
    passed = 0
    checked = 0
    details = []
    for j in jobs:
        sim = by_id.get(j["id"]) or {}
        rec = hist[j["id"]]
        if not sim.get("ok"):
            details.append({"id": j["id"], "ok": False, "error": sim.get("error")})
            checked += 1
            continue
        ok = rates_within_3sigma(rec, sim)
        passed += int(ok)
        checked += 1
        if cache is not None:
            pk = pair_key(args.bb_version, j["input"], ASSEMBLER_VERSION)
            cache.merge_from_sim_result(
                pair_key=pk,
                bb_version=args.bb_version,
                row_board_hash="verify",
                col_board_hash="verify",
                shell_hash="verify",
                result=sim,
            )
        if not ok or args.verbose:
            details.append(
                {
                    "id": j["id"],
                    "ok": ok,
                    "rec": {k: rec.get(k) for k in ("winRate", "tieRate", "lossRate", "simulationCount")},
                    "sim": {k: sim.get(k) for k in ("winRate", "tieRate", "lossRate", "simulationCount")},
                }
            )

    if cache is not None:
        cache.close()

    rate = passed / checked if checked else 0.0
    report = {
        "checked": checked,
        "passed": passed,
        "passRate": rate,
        "threshold": 0.99,
        "ok": rate >= 0.99,
        "iterations": args.iterations,
        "summary": summary,
        "failures": [d for d in details if not d.get("ok")],
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if args.out:
        Path(args.out).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0 if report["ok"] else 1


def _add_common(sp: argparse.ArgumentParser) -> None:
    sp.add_argument("--cache", default=str(DEFAULT_CACHE))
    sp.add_argument("--exe", default=str(DEFAULT_EXE))
    sp.add_argument("--bb-map", default=str(_REPO / "tools" / "ReplaySim" / "bb-dirs.json"))
    sp.add_argument("--turns-jsonl", default=str(DEFAULT_TURNS))
    sp.add_argument("--root", dest="roots", action="append", default=None, help="diag root (repeatable)")
    sp.add_argument("--iterations", type=int, default=ITERATIONS)
    sp.add_argument("--max-duration", type=int, default=MAX_DURATION_MS)
    sp.add_argument("--panel-games", type=int, default=PANEL_GAMES)
    sp.add_argument("--threads", type=int, default=None)
    sp.add_argument("--player-only", action="store_true", help="exclude opponent boards from pool")
    sp.add_argument("--dry-run", action="store_true")
    sp.add_argument("--max-hours", type=float, default=2.0, help="stop before sim if rough single-thread time exceeds this")


def _add_pool_selector(sp: argparse.ArgumentParser) -> None:
    sp.add_argument("--bb-version", default=None, help="file version or pool id; resolved through sim_pools.json")
    sp.add_argument("--sim-pool", default=None, help="sim pool id (earliest member file version)")


def cmd_score_policy(args: argparse.Namespace) -> int:
    from .score_search import run_score_policy_search

    pool = _resolve_pool(args)
    run_score_policy_search(
        sim_pool=pool,
        roots=args.roots,
        turns_jsonl=Path(args.turns_jsonl),
        cache_path=Path(args.cache),
        out_dir=Path(args.out) if args.out else None,
        n_boot=args.bootstrap,
    )
    return 0


def cmd_pools(_args: argparse.Namespace) -> int:
    for row in load_table(refresh=True):
        print(f"{row['bbVersion']}\t{row['simPool']}\t{row.get('joinedAt', '')}\t{row.get('evidence', '')}")
    return 0


def cmd_pool_check(args: argparse.Namespace) -> int:
    import importlib.util

    path = _REPO / "spikes" / "replay-harness" / "tools" / "roundtrip.py"
    spec = importlib.util.spec_from_file_location("bb_roundtrip", path)
    if spec is None or spec.loader is None:
        print(f"cannot load {path}", file=sys.stderr)
        return 2
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    bb_map = load_bb_map(Path(args.bb_map))
    pool = args.sim_pool
    baseline = latest_installed_member(pool, bb_map)
    candidate = args.candidate
    if not baseline:
        print(f"no installed DLL in simPool {pool}", file=sys.stderr)
        return 2
    if candidate == baseline:
        print(f"candidate {candidate} is already the latest installed member", file=sys.stderr)
        return 2

    def attempt(versions: list[str], alt: str):
        ns = argparse.Namespace(
            roots=args.roots or default_diag_roots(),
            root=None,
            versions=versions,
            alt_version=alt,
            limit=args.limit,
            max_duration=args.max_duration,
            verbose=args.verbose,
            json_out="",
        )
        return mod.mode_q011(ns, bb_map, Path(args.exe))

    sample = candidate
    alt = baseline
    _rows, stats = attempt([candidate], baseline)
    if int(stats.get("attempted") or 0) == 0:
        sample = baseline
        alt = candidate
        _rows, stats = attempt([baseline], candidate)
    passed = judge_cross_replay(stats)
    report = {
        "candidate": candidate,
        "simPool": pool,
        "baseline": baseline,
        "sampleVersion": sample,
        "altVersion": alt,
        "passed": passed,
        "stats": {k: int(v) for k, v in stats.items()},
    }
    out = Path(args.out) if args.out else (
        _REPO / "data" / "strength" / "pool-checks" / f"{candidate}-vs-{pool}.json"
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"wrote {out}", flush=True)
    return 0 if passed else 1


def cmd_pool_join(args: argparse.Namespace) -> int:
    ok = pool_join(
        candidate=args.candidate,
        sim_pool=args.sim_pool,
        evidence=Path(args.evidence),
        check_path=Path(args.check),
        joined_at=args.joined_at,
    )
    if not ok:
        print("pool-join refused: check did not pass, or evidence is missing", flush=True)
        return 1
    print(f"joined {args.candidate} -> {args.sim_pool}", flush=True)
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="tools.strength", description="P3 strength engine (batch + percentile)")
    sub = p.add_subparsers(dest="cmd", required=True)

    b = sub.add_parser("backfill", help="fill missing pairs for a sim pool")
    _add_common(b)
    _add_pool_selector(b)
    b.add_argument("--turns", default=None, help="e.g. 1 or 1-3 or 1,2,5")
    b.add_argument("--out", default=None)
    b.set_defaults(func=cmd_backfill)

    i = sub.add_parser("increment", help="incremental pairs for one game")
    _add_common(i)
    _add_pool_selector(i)
    i.add_argument("--game-id", required=True)
    i.set_defaults(func=cmd_increment)

    pct = sub.add_parser("percentile", help="round-robin S/Q + bootstrap → strength.jsonl")
    _add_common(pct)
    _add_pool_selector(pct)
    pct.add_argument("--turns", default="1-12", help="candidate turns (L1 may load ±1)")
    pct.add_argument("--bootstrap", type=int, default=BOOTSTRAP_B)
    pct.add_argument("--out", default=None, help="strength.jsonl path")
    pct.add_argument("--no-fill", action="store_true", help="do not run missing-pair batch")
    pct.add_argument("--stats-out", default=None, help="write exit-width stats JSON")
    pct.add_argument("--max-turn", type=int, default=12, help="for --stats-out scope")
    pct.set_defaults(func=cmd_percentile)

    ew = sub.add_parser("exit-width", help="P3 exit criterion #1 on strength.jsonl")
    ew.add_argument("--bb-version", default="1.85.0.0")
    ew.add_argument("--jsonl", default=None, help="default data/strength/<bb>/strength.jsonl")
    ew.add_argument("--max-turn", type=int, default=12)
    ew.add_argument("--out", default=None)
    ew.set_defaults(func=cmd_exit_width)

    v = sub.add_parser("verify-p3t0", help="re-sim out_both sample vs historical 3σ")
    _add_common(v)
    v.add_argument("--bb-version", default="1.85.0.0")
    v.add_argument("--baseline", default=str(_REPO / "spikes" / "strength-cross" / "out_both"))
    v.add_argument("--limit", type=int, default=100)
    v.add_argument("--stride", type=int, default=50, help="take every Nth job before limit")
    v.add_argument("--out", default=None)
    v.add_argument("--verbose", action="store_true")
    v.add_argument(
        "--allow-cache-write",
        action="store_true",
        help="allow writing verify placeholder hashes into --cache (avoid default cache)",
    )
    v.set_defaults(func=cmd_verify_p3t0)

    pools = sub.add_parser("pools", help="list file version → sim pool")
    pools.set_defaults(func=cmd_pools)

    chk = sub.add_parser("pool-check", help="same-input cross-DLL check before joining a pool")
    _add_common(chk)
    chk.add_argument("--candidate", required=True, help="new file version")
    chk.add_argument("--sim-pool", required=True)
    chk.add_argument("--limit", type=int, default=100)
    chk.add_argument("--out", default=None)
    chk.add_argument("--verbose", action="store_true")
    chk.set_defaults(func=cmd_pool_check)

    join = sub.add_parser("pool-join", help="record a passed check in sim_pools.json")
    join.add_argument("--candidate", required=True)
    join.add_argument("--sim-pool", required=True)
    join.add_argument("--evidence", required=True, help="facts file that mentions the candidate")
    join.add_argument("--check", required=True, help="pool-check JSON with passed=true")
    join.add_argument("--joined-at", default="2026-10-11")
    join.set_defaults(func=cmd_pool_join)

    sp = sub.add_parser(
        "score-policy",
        help="tie-weight search into score-policy/ (does not write strength.jsonl)",
    )
    _add_common(sp)
    _add_pool_selector(sp)
    sp.add_argument("--out", default=None, help="sidecar directory (default data/strength/<pool>/score-policy)")
    sp.add_argument("--bootstrap", type=int, default=2000)
    sp.set_defaults(func=cmd_score_policy)

    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
