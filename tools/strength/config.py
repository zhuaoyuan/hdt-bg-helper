"""Frozen defaults from facts/strength-calibration.md (do not retune in P3-T2)."""
from __future__ import annotations

ITERATIONS = 500
MAX_DURATION_MS = 500
PANEL_GAMES = 30
G_MIN = 6
W_RELAX = 0.25
L1_ENABLED = True
L2_ENABLED = False  # placeholder; P3-T3 uses this
INCLUDE_OPPONENT_BOARDS = True
BOOTSTRAP_B = 1000
