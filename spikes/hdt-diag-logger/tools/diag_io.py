"""Shared helpers for reading BgHelperDiag game directories (jsonl and gzip)."""
from __future__ import annotations

import gzip
import json
import os
from typing import Iterator, Optional


def open_text(path: str):
    if path.endswith(".gz"):
        return gzip.open(path, "rt", encoding="utf-8", errors="replace")
    return open(path, "r", encoding="utf-8", errors="replace")


def records_path(game_dir: str) -> Optional[str]:
    for name in ("records.jsonl.gz", "records.jsonl"):
        p = os.path.join(game_dir, name)
        if os.path.exists(p):
            return p
    return None


def power_path(game_dir: str) -> Optional[str]:
    for name in ("power.log.gz", "power.log"):
        p = os.path.join(game_dir, name)
        if os.path.exists(p):
            return p
    return None


def read_records(game_dir: str) -> list:
    p = records_path(game_dir)
    if not p:
        return []
    out = []
    with open_text(p) as f:
        for i, row in enumerate(f, 1):
            try:
                out.append(json.loads(row))
            except json.JSONDecodeError as e:
                out.append({"type": "_bad_json", "line": i, "error": str(e)})
    return out


def iter_record_lines(game_dir: str) -> Iterator[str]:
    p = records_path(game_dir)
    if not p:
        return
    with open_text(p) as f:
        for row in f:
            yield row
