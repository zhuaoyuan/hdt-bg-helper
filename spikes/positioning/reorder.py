# -*- coding: utf-8 -*-
"""Reorder Side.items by simple stat rules (stable sort)."""
from __future__ import annotations

import copy
from typing import Any, Callable

# Default strategy set (excl. orig which is identity).
DEFAULT_STRATEGIES = (
    "atk_desc",
    "hp_desc",
    "atk1_hp1",
    "atk1_hp2",
    "atk2_hp1",
    "rev_orig",
    "taunt_left_atk",
)

ALL_STRATEGIES = ("orig",) + DEFAULT_STRATEGIES


def minion_data(m: dict) -> dict:
    d = m.get("_data")
    return d if isinstance(d, dict) else {}


def max_attack(m: dict) -> float:
    d = minion_data(m)
    v = d.get("MaxAttack")
    if v is None:
        v = d.get("BaseAttack")
    return float(v or 0)


def max_health(m: dict) -> float:
    d = minion_data(m)
    v = d.get("MaxHealth")
    if v is None:
        v = d.get("BaseHealth")
    return float(v or 0)


def is_taunt(m: dict) -> bool:
    return bool(minion_data(m).get("Taunt"))


def card_ids(items: list[dict]) -> list[str]:
    return [str(m.get("CardID") or m.get("CardId") or "") for m in items]


def _stable_sort_desc(items: list[dict], key_fn: Callable[[dict], tuple]) -> list[dict]:
    """Sort by key descending; ties keep original relative order."""
    indexed = list(enumerate(items))

    def sort_key(ih: tuple[int, dict]) -> tuple:
        i, m = ih
        k = key_fn(m)
        neg = tuple(-float(x) for x in k)
        return (*neg, i)

    indexed.sort(key=sort_key)
    return [m for _, m in indexed]


def reorder_items(items: list[dict], strategy: str) -> list[dict]:
    """Return a new list (shallow-copied minion refs) in strategy order."""
    if strategy == "orig":
        return list(items)
    if strategy == "rev_orig":
        return list(reversed(items))

    items = list(items)
    if strategy == "atk_desc":
        return _stable_sort_desc(items, lambda m: (max_attack(m),))
    if strategy == "hp_desc":
        return _stable_sort_desc(items, lambda m: (max_health(m),))
    if strategy == "atk1_hp1":
        return _stable_sort_desc(items, lambda m: (max_attack(m) + max_health(m),))
    if strategy == "atk1_hp2":
        return _stable_sort_desc(items, lambda m: (max_attack(m) + 2 * max_health(m),))
    if strategy == "atk2_hp1":
        return _stable_sort_desc(items, lambda m: (2 * max_attack(m) + max_health(m),))
    if strategy == "taunt_left_atk":
        taunts = [m for m in items if is_taunt(m)]
        others = [m for m in items if not is_taunt(m)]
        taunts = _stable_sort_desc(taunts, lambda m: (max_attack(m),))
        others = _stable_sort_desc(others, lambda m: (max_attack(m),))
        return taunts + others
    raise ValueError(f"unknown strategy: {strategy}")


def extract_side_items(inp: dict, side: str) -> list[dict]:
    unit = inp.get(side) or {}
    side_list = unit.get("Side") or {}
    items = side_list.get("items")
    if not isinstance(items, list):
        return []
    return items


def apply_strategy_to_input(inp: dict, side: str, strategy: str) -> dict:
    """Deep-copy input and reorder `side`'s Side.items. Other fields unchanged."""
    out = copy.deepcopy(inp)
    unit = out.get(side)
    if not isinstance(unit, dict):
        return out
    side_list = unit.get("Side")
    if not isinstance(side_list, dict):
        return out
    items = side_list.get("items")
    if not isinstance(items, list):
        return out
    side_list["items"] = reorder_items(items, strategy)
    return out


def multiset_equal(a: list[str], b: list[str]) -> bool:
    return sorted(a) == sorted(b)
