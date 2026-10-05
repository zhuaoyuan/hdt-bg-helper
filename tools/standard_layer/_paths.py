"""Shared path bootstrap for spike helpers (diag_io, power_replay, roundtrip)."""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
DIAG_TOOLS = REPO / "spikes" / "hdt-diag-logger" / "tools"
REPLAY_TOOLS = REPO / "spikes" / "replay-harness" / "tools"
REPLAY_HARNESS = REPO / "spikes" / "replay-harness"


def ensure_spike_paths() -> None:
    for p in (DIAG_TOOLS, REPLAY_TOOLS):
        s = str(p)
        if s not in sys.path:
            sys.path.insert(0, s)
