# -*- coding: utf-8 -*-
"""P3-T5: offline static HTML post-game review view."""

from .model import GameReview, TurnReview, strength_state_for, turn_detail_text

__all__ = [
    "GameReview",
    "TurnReview",
    "strength_state_for",
    "turn_detail_text",
]
