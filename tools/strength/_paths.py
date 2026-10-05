"""Repo / default data paths for tools.strength."""
from __future__ import annotations

import os
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
DEFAULT_CACHE = REPO / "data" / "strength" / "cache.sqlite"
DEFAULT_TURNS = REPO / "data" / "standard" / "turns.jsonl"
DEFAULT_BB_MAP = REPO / "tools" / "ReplaySim" / "bb-dirs.json"
DEFAULT_EXE = REPO / "tools" / "ReplaySim" / "bin" / "run" / "ReplaySim.exe"


def expand(p: str) -> str:
    return os.path.expandvars(os.path.expanduser(p))


def default_diag_roots() -> list[str]:
    return [
        str(REPO / "data" / "BgHelperDiag"),
        expand(r"%APPDATA%\HearthstoneDeckTracker\BgHelperDiag"),
    ]
