# -*- coding: utf-8 -*-
"""Integrity status: ready / partial / unsupported / invalid / missing."""
from __future__ import annotations

from typing import Optional


def classify_status(
    *,
    meta: dict,
    session_reason: Optional[str],
    combat: dict,
    tuanzi_turn: Optional[dict],
    gap_flags: list[str],
) -> tuple[str, list[str]]:
    """Return (status, reasons).

    Rules aligned with design/P2-data-capture.md §3.3 and P2 rescope:

      ready   : solo, has Combat Input+Output, plugin from game_start (not mid-game)
      partial : duos; mid-game enable with output; unrepaired anon key (dump usable but dirty)
      missing : no Combat Output/Input (incl. direct disconnect without dump)
      unsupported : probe failed and no output
      invalid : session disabled / no input ref despite output

    Systemic P1 checklist blinds baked into HDT's own Input (unknown hand, 2717 always 0
    in Input, ResourcesSpent always 0) are recorded on the row as ``gapFlags`` for the
    quality report, but do **not** alone downgrade ``ready`` — otherwise ready would stay
    well below the 90% exit bar while the dump still matches what HDT simulated.
    """
    reasons: list[str] = []
    duos = bool(meta.get("isBattlegroundsDuosMatch"))
    mid = session_reason == "enabled_mid_game"
    probe_err = meta.get("probeInitError")
    disabled = bool(meta.get("disabled"))

    # Hard capture failures — preferred over soft gap flags
    status_gaps = [g for g in gap_flags if g in ("no_input", "anon_player_key", "duos_input_present")]

    if tuanzi_turn and tuanzi_turn.get("kind") == "direct_dc":
        reasons.append("tuanzi_direct_dc")
        if not combat.get("hasOutput"):
            return "missing", reasons

    if disabled:
        reasons.append("session_disabled")
        return "invalid", reasons

    if probe_err and not combat.get("hasOutput"):
        reasons.append(f"probe_init_error:{probe_err}")
        return "unsupported", reasons

    if not combat.get("hasOutput") or not combat.get("hasInput"):
        reasons.append("no_combat_output" if not combat.get("hasOutput") else "no_combat_input")
        if mid:
            reasons.append("enabled_mid_game")
        return "missing", reasons

    if not combat.get("pickMeta", {}).get("usedAfter2022", True):
        reasons.append("bb_before_2022_fallback")

    if mid:
        reasons.append("enabled_mid_game")
        return "partial", reasons + status_gaps

    if duos or "duos_input_present" in gap_flags:
        reasons.append("duos")
        return "partial", reasons + status_gaps

    if "anon_player_key" in gap_flags:
        reasons.append("anon_player_key")
        return "partial", reasons

    if combat.get("inputRef", {}).get("lineSeq") is None:
        reasons.append("no_input_ref")
        return "invalid", reasons

    return "ready", reasons
