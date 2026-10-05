# -*- coding: utf-8 -*-
"""Assemble BB Input for s(a,b); normalize + hash for cache keys.

Migrated from spikes/strength-cross/tools/cross_input.py (logic copy; no spike import).
"""
from __future__ import annotations

import copy
import hashlib
import json
from typing import Any

from . import ASSEMBLER_VERSION


def _walk(obj: Any, fn) -> None:
    fn(obj)
    if isinstance(obj, dict):
        for v in obj.values():
            _walk(v, fn)
    elif isinstance(obj, list):
        for v in obj:
            _walk(v, fn)


def remap_ids(obj: Any, start: int = 1) -> tuple[Any, int]:
    """Deep-copy and assign fresh unique $id; remap in-tree $ref."""
    obj = copy.deepcopy(obj)
    old_to_new: dict[int, int] = {}
    next_id = start

    def collect(node: Any) -> None:
        nonlocal next_id
        if not isinstance(node, dict):
            return
        if "$id" in node:
            try:
                old = int(node["$id"])
            except (TypeError, ValueError):
                return
            if old not in old_to_new:
                old_to_new[old] = next_id
                next_id += 1

    _walk(obj, collect)

    def apply(node: Any) -> None:
        if not isinstance(node, dict):
            return
        if "$id" in node:
            try:
                old = int(node["$id"])
                if old in old_to_new:
                    node["$id"] = old_to_new[old]
            except (TypeError, ValueError):
                pass
        if "$ref" in node:
            try:
                old = int(node["$ref"])
                if old in old_to_new:
                    node["$ref"] = old_to_new[old]
                else:
                    node.pop("$ref", None)
            except (TypeError, ValueError):
                node.pop("$ref", None)

    _walk(obj, apply)
    return obj, next_id


def set_controlled(side: Any, controlled: bool) -> None:
    def fn(node: Any) -> None:
        if isinstance(node, dict) and "ControlledByPlayer" in node:
            node["ControlledByPlayer"] = controlled

    _walk(side, fn)


def clear_side_input_refs(side: dict) -> None:
    if isinstance(side, dict) and "_input" in side:
        side["_input"] = None


def make_cross_input(
    player_src: dict,
    opp_src: dict,
    *,
    player_side: str = "Player",
    opp_side: str = "Player",
) -> dict:
    """Build Input with rules from player_src, Player←player_side, Opponent←opp_side."""
    if player_side not in ("Player", "Opponent"):
        raise ValueError(player_side)
    if opp_side not in ("Player", "Opponent"):
        raise ValueError(opp_side)

    out: dict[str, Any] = {
        "$type": player_src.get("$type") or "BobsBuddy.Simulation.Input, BobsBuddy",
        "Anomaly": copy.deepcopy(player_src.get("Anomaly")),
        "isDuos": False,
        "DamageCap": player_src.get("DamageCap"),
        "turn": player_src.get("turn"),
        "availableRaces": copy.deepcopy(player_src.get("availableRaces")),
        "PlayerTeammate": None,
        "OpponentTeammate": None,
    }

    p_side = copy.deepcopy(player_src[player_side])
    o_side = copy.deepcopy(opp_src[opp_side])
    set_controlled(p_side, True)
    set_controlled(o_side, False)
    clear_side_input_refs(p_side)
    clear_side_input_refs(o_side)

    p_side, next_id = remap_ids(p_side, start=2)
    o_side, next_id = remap_ids(o_side, start=next_id)
    out["$id"] = 1
    out["Player"] = p_side
    out["Opponent"] = o_side
    return out


def score_of(win: float | None, tie: float | None) -> float:
    return float(win or 0.0) + 0.5 * float(tie or 0.0)


def canonicalize(obj: Any) -> Any:
    """Sort dict keys recursively for stable JSON."""
    if isinstance(obj, dict):
        return {k: canonicalize(obj[k]) for k in sorted(obj.keys())}
    if isinstance(obj, list):
        return [canonicalize(x) for x in obj]
    return obj


def stable_json(obj: Any) -> str:
    return json.dumps(canonicalize(obj), ensure_ascii=False, separators=(",", ":"))


def sha256_hex(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def shell_payload(inp: dict) -> dict:
    return {
        "DamageCap": inp.get("DamageCap"),
        "turn": inp.get("turn"),
        "availableRaces": inp.get("availableRaces"),
        "Anomaly": inp.get("Anomaly"),
        "isDuos": inp.get("isDuos"),
    }


def board_side_payload(inp: dict, side: str) -> dict:
    return {"side": side, "unit": inp.get(side)}


def board_hash(inp: dict, side: str) -> str:
    return sha256_hex(stable_json(board_side_payload(inp, side)))


def shell_hash(inp: dict) -> str:
    return sha256_hex(stable_json(shell_payload(inp)))


def pair_key(bb_version: str, assembled: dict, assembler_version: str = ASSEMBLER_VERSION) -> str:
    """sha256(bbVersion | assemblerVersion | normalized assembled Input)."""
    payload = f"{bb_version}|{assembler_version}|{stable_json(assembled)}"
    return sha256_hex(payload)


def rates_to_counts(
    sims: int,
    win_rate: float | None,
    tie_rate: float | None,
    loss_rate: float | None,
    my_death_rate: float | None = None,
    their_death_rate: float | None = None,
    av_damage: float | None = None,
) -> dict[str, float | int]:
    """Convert ReplaySim rates to additive counts (wins/ties/losses are float counts)."""
    n = int(sims or 0)
    w = float(win_rate or 0.0) * n
    t = float(tie_rate or 0.0) * n
    l = float(loss_rate or 0.0) * n
    return {
        "sims": n,
        "wins": w,
        "ties": t,
        "losses": l,
        "myDeathRateSum": float(my_death_rate or 0.0) * n,
        "theirDeathRateSum": float(their_death_rate or 0.0) * n,
        "avDamageSum": float(av_damage or 0.0) * n,
    }
