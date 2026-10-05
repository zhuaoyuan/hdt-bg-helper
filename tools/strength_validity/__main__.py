# -*- coding: utf-8 -*-
"""CLI: P3-T4 strength validity evaluation.

Examples:
  python -m tools.strength_validity run --bb-version 1.85.0.0
  python -m tools.strength_validity run --bb-version 1.85.0.0 --player-only-strength data/strength/1.85.0.0/strength_player_only.jsonl
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_TOOLS = _HERE.parent
_REPO = _TOOLS.parent
for p in (_REPO, _TOOLS):
    s = str(p)
    if s not in sys.path:
        sys.path.insert(0, s)

from tools.strength._paths import DEFAULT_TURNS  # noqa: E402
from tools.strength.engine import strength_out_path  # noqa: E402

from .align import (  # noqa: E402
    align_turns,
    default_diag_roots,
    index_turns,
    load_jsonl,
    load_player_health_from_diag,
)
from .report import build_report, report_to_markdown  # noqa: E402


def _parse_turns(s: str | None) -> int | None:
    if not s:
        return 12
    if s.lower() in ("all", "*", "none"):
        return None
    if "-" in s:
        # "1-12" → max 12
        return int(s.split("-", 1)[1])
    return int(s)


def cmd_run(args: argparse.Namespace) -> int:
    strength_path = Path(args.strength) if args.strength else strength_out_path(args.bb_version)
    turns_path = Path(args.turns_jsonl)
    max_turn = _parse_turns(args.turns)

    strength_rows = load_jsonl(strength_path)
    turn_rows = load_jsonl(turns_path)
    turns_by = index_turns(turn_rows, bb_version=None)  # match by gameId; bb filter via strength

    roots = args.roots or default_diag_roots()
    health_by: dict = {}
    if not args.no_diag_health:
        print(f"loading Player.Health from diag ({len(roots)} roots)…", flush=True)
        health_by = load_player_health_from_diag(roots, args.bb_version)
        print(f"  health snapshots: {len(health_by)}", flush=True)

    # Filter strength to bb
    strength_rows = [r for r in strength_rows if str(r.get("bbVersion") or args.bb_version) == args.bb_version]

    pairs = align_turns(
        strength_rows,
        turns_by,
        health_by,
        max_turn=max_turn,
        side="Player",
    )
    report = build_report(
        pairs,
        bb_version=args.bb_version,
        strength_path=str(strength_path),
        max_turn=max_turn,
        n_boot=args.bootstrap,
        n_perm=args.permutation,
        seed=args.seed,
    )
    report["healthSnapshots"] = len(health_by)

    # Full-turn control if main was capped
    if max_turn is not None and args.also_all_turns:
        pairs_all = align_turns(strength_rows, turns_by, health_by, max_turn=None, side="Player")
        report["all_turns_control"] = build_report(
            pairs_all,
            bb_version=args.bb_version,
            strength_path=str(strength_path),
            max_turn=None,
            n_boot=min(args.bootstrap, 2000),
            n_perm=min(args.permutation, 2000),
            seed=args.seed + 999,
            include_result_appendix=False,
        )

    text = json.dumps(report, ensure_ascii=False, indent=2)
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(text, encoding="utf-8")
        print(f"wrote {args.out}", flush=True)
    else:
        # Windows consoles may be GBK; avoid hard-crash on unicode in JSON notes.
        try:
            print(text)
        except UnicodeEncodeError:
            sys.stdout.buffer.write((text + "\n").encode("utf-8", errors="replace"))
    if args.md:
        md = report_to_markdown(report)
        Path(args.md).parent.mkdir(parents=True, exist_ok=True)
        Path(args.md).write_text(md, encoding="utf-8")
        print(f"wrote {args.md}", flush=True)

    # Optional second pass for player-only file
    if args.player_only_strength:
        po = Path(args.player_only_strength)
        if po.is_file():
            po_rows = [r for r in load_jsonl(po) if str(r.get("bbVersion") or args.bb_version) == args.bb_version]
            po_pairs = align_turns(po_rows, turns_by, health_by, max_turn=max_turn, side="Player")
            po_report = build_report(
                po_pairs,
                bb_version=args.bb_version,
                strength_path=str(po),
                max_turn=max_turn,
                n_boot=args.bootstrap,
                n_perm=args.permutation,
                seed=args.seed + 7,
            )
            if args.player_only_out:
                Path(args.player_only_out).write_text(
                    json.dumps(po_report, ensure_ascii=False, indent=2), encoding="utf-8"
                )
            report["player_only"] = {
                "strengthPath": str(po),
                "exit3": po_report["exit3"],
                "placement": po_report["placement"]["percentile_vs_neg_placement"],
                "next_health_game": po_report["next_health"]["game_level"],
            }
            if args.out:
                Path(args.out).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        else:
            print(f"[warn] player-only strength missing: {po}", flush=True)

    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="tools.strength_validity", description="P3-T4 validity eval")
    sub = p.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("run", help="align + Spearman tables")
    r.add_argument("--bb-version", default="1.85.0.0")
    r.add_argument("--strength", default=None, help="default data/strength/<bb>/strength.jsonl")
    r.add_argument("--turns-jsonl", default=str(DEFAULT_TURNS))
    r.add_argument("--turns", default="1-12", help="max turn like 1-12, or 'all'")
    r.add_argument("--root", dest="roots", action="append", default=None)
    r.add_argument("--no-diag-health", action="store_true", help="skip Input.Health; use friendlyHealth only")
    r.add_argument("--bootstrap", type=int, default=5000)
    r.add_argument("--permutation", type=int, default=5000)
    r.add_argument("--seed", type=int, default=0)
    r.add_argument("--out", default=None)
    r.add_argument("--md", default=None)
    r.add_argument("--also-all-turns", action="store_true")
    r.add_argument("--player-only-strength", default=None)
    r.add_argument("--player-only-out", default=None)
    r.set_defaults(func=cmd_run)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
