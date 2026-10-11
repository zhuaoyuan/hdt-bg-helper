# -*- coding: utf-8 -*-
"""Map Bob's Buddy file versions onto strength sim pools.

Pool id is the earliest ``bbVersion`` in the pool. Unknown versions stay
alone (pool id = themselves) until ``pool-join`` records evidence.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

_HERE = Path(__file__).resolve().parent
TABLE_PATH = _HERE / "sim_pools.json"
_CACHE: list[dict[str, Any]] | None = None


def version_tuple(version: str) -> tuple[int, ...]:
    parts: list[int] = []
    for piece in str(version).split("."):
        if not piece.isdigit():
            break
        parts.append(int(piece))
    return tuple(parts)


def load_table(path: Path | None = None, *, refresh: bool = False) -> list[dict[str, Any]]:
    global _CACHE
    path = Path(path) if path is not None else TABLE_PATH
    if path == TABLE_PATH and _CACHE is not None and not refresh:
        return _CACHE
    raw = json.loads(path.read_text(encoding="utf-8"))
    rows = list(raw.get("versions") or [])
    if path == TABLE_PATH:
        _CACHE = rows
    return rows


def save_table(rows: list[dict[str, Any]], path: Path | None = None) -> None:
    global _CACHE
    path = Path(path) if path is not None else TABLE_PATH
    payload = {"versions": rows}
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if path == TABLE_PATH:
        _CACHE = rows


def sim_pool_of(bb_version: str, table: list[dict[str, Any]] | None = None) -> str:
    """Pool id for a file version. Missing rows stay in a pool of their own."""
    ver = str(bb_version)
    rows = table if table is not None else load_table()
    for row in rows:
        if str(row.get("bbVersion")) == ver:
            return str(row.get("simPool") or ver)
    return ver


def member_versions(sim_pool: str, table: list[dict[str, Any]] | None = None) -> list[str]:
    pool = str(sim_pool)
    rows = table if table is not None else load_table()
    members = [str(r["bbVersion"]) for r in rows if str(r.get("simPool")) == pool]
    return members or [pool]


def latest_installed_member(sim_pool: str, bb_map: dict[str, str]) -> str | None:
    """Highest file version in the pool that has BobsBuddy.dll on disk."""
    found: list[str] = []
    for ver in member_versions(sim_pool):
        directory = bb_map.get(ver)
        if directory and os.path.isfile(os.path.join(directory, "BobsBuddy.dll")):
            found.append(ver)
    if not found:
        return None
    return max(found, key=version_tuple)


def judge_cross_replay(stats: dict[str, Any]) -> bool:
    """Q-011 pass: every attempted combat within 3σ, no sim failures.

    Same predicate as ``facts/replay-roundtrip.md`` §3 / ``roundtrip.py``:
    win/tie/loss inside 3σ (with the harness floor). A single ``diff`` is the
    1.78→1.85 style rejection.
    """
    attempted = int(stats.get("attempted") or 0)
    fail = int(stats.get("fail") or 0)
    diff = int(stats.get("diff") or 0)
    same = int(stats.get("same") or 0)
    return attempted > 0 and fail == 0 and diff == 0 and same == attempted


def pool_join(
    *,
    candidate: str,
    sim_pool: str,
    evidence: Path,
    check_path: Path,
    table_path: Path | None = None,
    joined_at: str = "2026-10-11",
) -> bool:
    """Add ``candidate`` to ``sim_pool`` only after a passed check and a facts file.

    Returns False without writing when the check did not pass or evidence is missing.
    """
    evidence = Path(evidence)
    check_path = Path(check_path)
    if not evidence.is_file() or not check_path.is_file():
        return False
    if "facts" not in evidence.parts:
        return False
    check = json.loads(check_path.read_text(encoding="utf-8"))
    if not check.get("passed"):
        return False
    if str(check.get("candidate")) != str(candidate) or str(check.get("simPool")) != str(sim_pool):
        return False
    text = evidence.read_text(encoding="utf-8")
    if str(candidate) not in text:
        return False

    path = Path(table_path) if table_path is not None else TABLE_PATH
    rows = load_table(path, refresh=True)
    evidence_rel = evidence.as_posix()
    updated = False
    for row in rows:
        if str(row.get("bbVersion")) == str(candidate):
            row["simPool"] = str(sim_pool)
            row["joinedAt"] = joined_at
            row["evidence"] = evidence_rel
            updated = True
            break
    if not updated:
        rows.append(
            {
                "bbVersion": str(candidate),
                "simPool": str(sim_pool),
                "joinedAt": joined_at,
                "evidence": evidence_rel,
            }
        )
    save_table(rows, path)
    return True
