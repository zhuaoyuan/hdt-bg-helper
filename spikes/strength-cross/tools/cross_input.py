# -*- coding: utf-8 -*-
"""Assemble a BB Input JSON: Player from board A, Opponent from board B."""
from __future__ import annotations

import copy
from typing import Any


def _walk(obj: Any, fn):
    fn(obj)
    if isinstance(obj, dict):
        for v in obj.values():
            _walk(v, fn)
    elif isinstance(obj, list):
        for v in obj:
            _walk(v, fn)


def remap_ids(obj: Any, start: int = 1) -> Any:
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
                    # dangling ref outside grafted subtree — drop to avoid wrong binding
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
    """Player._input often $ref-cycles to Input; Hydrator ignores it, but keep clean."""
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
