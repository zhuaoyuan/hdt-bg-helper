# -*- coding: utf-8 -*-
"""Backfill rules/versions metadata into an existing strength.jsonl.

The engine emits these fields on a fresh run (``engine.evaluate_candidate``).
Existing percentile files predate that change; this migration adds only metadata
and verifies that S/percentile/CI/etc. are byte-for-byte unchanged.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path

from ._paths import REPO

_METADATA_KEYS = ("rules", "versions", "rulesSource")


def _identity(row: dict) -> str:
    payload = {k: v for k, v in row.items() if k not in _METADATA_KEYS}
    return hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _load_jsonl(path: Path) -> list[dict]:
    out: list[dict] = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out


def annotate(rows: list[dict], turns_by: dict[tuple[str, int], dict]) -> dict:
    hit = 0
    missing = 0
    for row in rows:
        gid = str(row.get("gameId") or "")
        turn = row.get("turn")
        if turn is None:
            missing += 1
            continue
        trow = turns_by.get((gid, int(turn)))
        if not trow:
            missing += 1
            row["rules"] = None
            row["versions"] = None
            row["rulesSource"] = "missing_turn_row"
            continue
        meta = trow.get("meta") or {}
        row["rules"] = trow.get("rules")
        row["versions"] = {
            "bbVersion": row.get("bbVersion"),
            "hdtVersion": meta.get("hdtVersion"),
            "hearthDbVersion": meta.get("hearthDbVersion"),
            "hearthstoneBuild": meta.get("hearthstoneBuild"),
        }
        row["rulesSource"] = "standard_layer"
        hit += 1
    return {"annotated": hit, "missingTurnRow": missing, "rows": len(rows)}


def write_rows(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Backfill rules/versions in strength.jsonl")
    ap.add_argument("--strength", default=str(REPO / "data" / "strength" / "1.85.0.0" / "strength.jsonl"))
    ap.add_argument("--turns", default=str(REPO / "data" / "standard" / "turns.jsonl"))
    ap.add_argument("--out", default=None, help="output path (default: in-place after backup)")
    ap.add_argument("--backup", default=None, help="backup path (default: <strength>.bak_before_rules)")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)

    src = Path(args.strength)
    rows = _load_jsonl(src)
    before = [_identity(r) for r in rows]
    turns = _load_jsonl(Path(args.turns))
    turns_by = {(str(r["gameId"]), int(r["turn"])): r for r in turns if r.get("gameId") and r.get("turn") is not None}
    report = annotate(rows, turns_by)
    after = [_identity(r) for r in rows]
    if before != after:
        print("refusing: identity fields changed during annotation", flush=True)
        return 2
    print(json.dumps(report, ensure_ascii=False, indent=2), flush=True)
    if args.dry_run:
        return 0

    out = Path(args.out) if args.out else src
    if out == src:
        backup = Path(args.backup) if args.backup else src.with_name(src.name + ".bak_before_rules")
        if not backup.is_file():
            shutil.copy2(src, backup)
        print(f"backup: {backup}", flush=True)
    write_rows(out, rows)
    print(f"wrote {out}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
