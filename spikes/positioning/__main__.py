# -*- coding: utf-8 -*-
"""CLI for positioning strength spike.

Examples:
  python -m spikes.positioning run --bb-version 1.85.0.0 --turns 5 --strategies orig,atk_desc --limit-boards 8
  python -m spikes.positioning run --bb-version 1.85.0.0 --turns 3-7
  python -m spikes.positioning report --summary data/positioning/1.85.0.0/summary.json
  python -m spikes.positioning enumerate --bb-version 1.85.0.0 --turns 3,4
  python -m spikes.positioning enumerate --dry-run
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from spikes.positioning.enumerate_run import run_enumerate  # noqa: E402
from spikes.positioning.reorder import (  # noqa: E402
    ALL_STRATEGIES,
    DEFAULT_STRATEGIES,
    KEYWORD_STRATEGIES,
)
from spikes.positioning.run import load_summary, run_analysis  # noqa: E402


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


def _parse_strats(s: str | None) -> list[str] | None:
    if not s:
        return None
    return [x.strip() for x in s.split(",") if x.strip()]


def cmd_run(args: argparse.Namespace) -> int:
    if args.keyword:
        strats = _parse_strats(args.strategies) or list(KEYWORD_STRATEGIES)
    else:
        strats = _parse_strats(args.strategies) or list(DEFAULT_STRATEGIES)
    summary = run_analysis(
        bb_version=args.bb_version,
        turns=_parse_turns(args.turns) or list(range(3, 8)),
        strategies=strats,
        cache_path=Path(args.cache) if args.cache else None,
        exe=Path(args.exe) if args.exe else None,
        bb_map_path=Path(args.bb_map) if args.bb_map else None,
        out_dir=Path(args.out) if args.out else None,
        iterations=args.iterations,
        max_duration=args.max_duration,
        threads=args.threads,
        limit_boards=args.limit_boards,
        dry_run=args.dry_run,
        chunk_size=args.chunk_size,
        n_boot=args.n_boot,
        swap_budget=args.swap_budget,
        pair_cap=args.pair_cap,
    )
    print(json.dumps({"cells": summary.get("cells"), "runInfo": summary.get("runInfo")}, ensure_ascii=False, indent=2))
    return 0


def cmd_enumerate(args: argparse.Namespace) -> int:
    summary = run_enumerate(
        bb_version=args.bb_version,
        turns=_parse_turns(args.turns) or [3, 4],
        per_stratum=args.per_stratum,
        min_n=args.min_n,
        max_n=args.max_n,
        top_frac=args.top_frac,
        seed=args.seed,
        pair_cap=args.pair_cap,
        cache_path=Path(args.cache) if args.cache else None,
        exe=Path(args.exe) if args.exe else None,
        bb_map_path=Path(args.bb_map) if args.bb_map else None,
        out_dir=Path(args.out) if args.out else None,
        iterations=args.iterations,
        max_duration=args.max_duration,
        threads=args.threads,
        chunk_size=args.chunk_size,
        dry_run=args.dry_run,
    )
    hints = summary.get("conclusionHints") or (summary.get("aggregate") or {}).get("conclusionHints")
    print(
        json.dumps(
            {
                "nSampled": summary.get("nSampled"),
                "nPermRows": summary.get("nPermRows"),
                "pairsEstimatedTotal": summary.get("pairsEstimatedTotal"),
                "truncatedBoards": summary.get("truncatedBoards"),
                "conclusionHints": hints,
                "boardSummaries": summary.get("boardSummaries"),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def cmd_report(args: argparse.Namespace) -> int:
    path = Path(args.summary)
    summary = load_summary(path)
    cells = summary.get("cells") or []
    print(f"strategies={summary.get('strategies')} turns={summary.get('turns')}")
    print(f"origMeanAbsMax={summary.get('origMeanAbsMax')}")
    print(
        f"{'strategy':16} {'turn':>4} {'n':>4} {'meanΔS':>10} {'ci95':>22} {'frac+':>6} {'wil_p':>8} {'FDR':>5} {'CI+':>4}"
    )
    for c in cells:
        if c.get("strategy") == "orig" and not args.include_orig:
            continue
        ci = (c.get("bootstrap") or {}).get("ci95")
        ci_s = f"[{ci[0]:+.4f},{ci[1]:+.4f}]" if ci else "—"
        mean = c.get("mean")
        mean_s = f"{mean:+.5f}" if mean is not None else "—"
        frac = c.get("fracPositive")
        frac_s = f"{frac:.2f}" if frac is not None else "—"
        wp = (c.get("wilcoxon") or {}).get("pvalue")
        wp_s = f"{wp:.3g}" if wp is not None else "—"
        print(
            f"{c['strategy']:16} {c['turn']:4d} {c.get('n') or 0:4d} {mean_s:>10} {ci_s:>22} "
            f"{frac_s:>6} {wp_s:>8} {str(bool(c.get('fdrReject05'))):>5} {str(bool(c.get('ciLowerPositive'))):>4}"
        )
    sig = [c for c in cells if c.get("ciLowerPositive") and c.get("strategy") != "orig"]
    print(f"\nCI-lower>0 cells: {len(sig)}")
    for c in sig:
        print(f"  {c['strategy']} t{c['turn']}: mean={c['mean']:+.5f}")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m spikes.positioning")
    sub = p.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("run", help="simulate + score + summary")
    r.add_argument("--bb-version", default="1.85.0.0")
    r.add_argument("--turns", default="3-7", help="e.g. 5 or 3-7 or 3,5,7")
    r.add_argument(
        "--strategies",
        default=None,
        help=f"comma list; default body={','.join(DEFAULT_STRATEGIES)}; "
        f"with --keyword default={','.join(KEYWORD_STRATEGIES)}; known={','.join(ALL_STRATEGIES)}",
    )
    r.add_argument(
        "--keyword",
        action="store_true",
        help="Q-018 keyword/adjacency set; default out under .../keyword/",
    )
    r.add_argument("--cache", default=None)
    r.add_argument("--exe", default=None)
    r.add_argument("--bb-map", default=None)
    r.add_argument("--out", default=None)
    r.add_argument("--iterations", type=int, default=500)
    r.add_argument("--max-duration", type=int, default=500)
    r.add_argument("--threads", type=int, default=None)
    r.add_argument("--limit-boards", type=int, default=None, help="per-turn pool cap (smoke)")
    r.add_argument("--dry-run", action="store_true")
    r.add_argument("--chunk-size", type=int, default=1500)
    r.add_argument("--n-boot", type=int, default=2000)
    r.add_argument("--swap-budget", type=int, default=6)
    r.add_argument("--pair-cap", type=int, default=250_000, help="global local_swap pair hard cap")
    r.set_defaults(func=cmd_run)

    rep = sub.add_parser("report", help="pretty-print summary.json")
    rep.add_argument(
        "--summary",
        default=str(_REPO / "data" / "positioning" / "1.85.0.0" / "summary.json"),
    )
    rep.add_argument("--include-orig", action="store_true")
    rep.set_defaults(func=cmd_report)

    en = sub.add_parser("enumerate", help="tertile sample + full permute + top20% features")
    en.add_argument("--bb-version", default="1.85.0.0")
    en.add_argument("--turns", default="3,4")
    en.add_argument("--per-stratum", type=int, default=2)
    en.add_argument("--min-n", type=int, default=2)
    en.add_argument("--max-n", type=int, default=5)
    en.add_argument("--top-frac", type=float, default=0.20)
    en.add_argument("--seed", default="enumerate-2026-10-07")
    en.add_argument("--pair-cap", type=int, default=150_000)
    en.add_argument("--cache", default=None)
    en.add_argument("--exe", default=None)
    en.add_argument("--bb-map", default=None)
    en.add_argument("--out", default=None)
    en.add_argument("--iterations", type=int, default=500)
    en.add_argument("--max-duration", type=int, default=500)
    en.add_argument("--threads", type=int, default=None)
    en.add_argument("--chunk-size", type=int, default=1500)
    en.add_argument("--dry-run", action="store_true")
    en.set_defaults(func=cmd_enumerate)

    args = p.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
