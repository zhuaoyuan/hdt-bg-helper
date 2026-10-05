# -*- coding: utf-8 -*-
"""Detect P1 checklist gap positives that should downgrade ready -> partial."""
from __future__ import annotations

from typing import Any, Optional

from .combat import get_player_obj, list_items


def _side_unknown_hand(side: Optional[dict]) -> int:
    if not side:
        return 0
    n = 0
    for h in list_items(side.get("Hand")):
        if not isinstance(h, dict):
            continue
        cid = h.get("CardId") or h.get("CardID") or h.get("cardId")
        if cid in (None, "", "Unknown", "UNKNOWN"):
            n += 1
    return n


def _side_secrets(side: Optional[dict]) -> int:
    if not side:
        return 0
    return len([x for x in list_items(side.get("Secrets")) if isinstance(x, dict)])


def detect_gaps(inp: Optional[dict], entities: list[dict] | None = None) -> list[str]:
    """Return observational gap flags (quality report + optional partial triggers).

    Most flags are informational: HDT's Input already encodes fog-of-war (Unknown hand)
    and systemic blinds (opponent ResourcesSpent / 2717). Status classification only
    treats ``no_input``, ``anon_player_key``, and ``duos_input_present`` as downgrades.
    """
    flags: list[str] = []
    if not inp:
        return ["no_input"]

    if "DuosInputPlayer" in inp or "DuosInputPlayerTeammate" in inp:
        flags.append("duos_input_present")

    for k in inp:
        if isinstance(k, str) and k.startswith("player_") and len(k) == 15:
            flags.append("anon_player_key")
            break

    opponent = get_player_obj(inp, "Opponent")
    uh = _side_unknown_hand(opponent)
    if uh:
        flags.append(f"opp_unknown_hand:{uh}")
    sec = _side_secrets(opponent)
    if sec:
        flags.append(f"opp_secrets:{sec}")

    if entities and opponent is not None:
        opp_counter = opponent.get("FriendlyMinionsDeadLastCombatCounter")
        if opp_counter in (0, None):
            for e in entities:
                tags = e.get("tags") or {}
                v = tags.get("2717") or tags.get(2717)
                if v not in (None, 0, "0"):
                    ctype = tags.get("CARDTYPE")
                    if ctype in (2, "2", "HERO") or tags.get("PLAYER_LEADERBOARD_PLACE") is not None:
                        flags.append("gap_2717_entity_nonzero_input_zero")
                        break

    return flags


def gap_inventory(rows: list[dict]) -> dict[str, int]:
    from collections import Counter

    c: Counter = Counter()
    for r in rows:
        for g in r.get("gapFlags") or []:
            key = g.split(":")[0]
            c[key] += 1
    return dict(sorted(c.items()))
