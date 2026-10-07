# -*- coding: utf-8 -*-
"""Reorder Side.items by simple stat / keyword rules (stable sort)."""
from __future__ import annotations

import copy
from typing import Any, Callable

from .cleave_ids import CLEAVE_CARD_IDS

# Body-stat strategies (Q-017); kept for CLI / regression.
DEFAULT_STRATEGIES = (
    "atk_desc",
    "hp_desc",
    "atk1_hp1",
    "atk1_hp2",
    "atk2_hp1",
    "rev_orig",
    "taunt_left_atk",
)

# Keyword / adjacency (Q-018); local_swap handled in run/local_search.
KEYWORD_RULE_STRATEGIES = (
    "taunt_pin_hp",
    "cleave_adj_tank",
    "reborn_dr_right",
)

KEYWORD_STRATEGIES = KEYWORD_RULE_STRATEGIES + ("local_swap_b6",)

SEARCH_STRATEGIES = frozenset({"local_swap_b6"})

ALL_STRATEGIES = ("orig",) + DEFAULT_STRATEGIES + KEYWORD_STRATEGIES


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


def is_reborn(m: dict) -> bool:
    return bool(minion_data(m).get("Reborn"))


def has_extra_deathrattle(m: dict) -> bool:
    adr = minion_data(m).get("AdditionalDeathrattles")
    if isinstance(adr, list):
        return len(adr) > 0
    if isinstance(adr, dict):
        items = adr.get("items")
        if isinstance(items, list):
            return len(items) > 0
        return len(adr) > 0
    return bool(adr)


def is_reborn_or_dr(m: dict) -> bool:
    return is_reborn(m) or has_extra_deathrattle(m)


def card_id(m: dict) -> str:
    return str(m.get("CardID") or m.get("CardId") or "")


def is_cleave(m: dict) -> bool:
    d = minion_data(m)
    if "Cleave" in d:
        return bool(d.get("Cleave"))
    return card_id(m) in CLEAVE_CARD_IDS


def card_ids(items: list[dict]) -> list[str]:
    return [card_id(m) for m in items]


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


def _taunt_pin_hp(items: list[dict]) -> list[dict]:
    """Taunts left (hp desc); non-taunts keep relative order. No-op if no taunt."""
    if not any(is_taunt(m) for m in items):
        return list(items)
    taunts = [m for m in items if is_taunt(m)]
    others = [m for m in items if not is_taunt(m)]
    taunts = _stable_sort_desc(taunts, lambda m: (max_health(m),))
    return taunts + others


def _cleave_adj_tank(items: list[dict]) -> list[dict]:
    """Place highest-hp non-cleave neighbors beside each cleave; preserve relative order otherwise."""
    n = len(items)
    if n == 0 or not any(is_cleave(m) for m in items):
        return list(items)

    # Work on indices; greedily assign unused tanks to empty slots adjacent to cleaves.
    result: list[dict | None] = [None] * n
    cleave_idx = [i for i, m in enumerate(items) if is_cleave(m)]
    for i in cleave_idx:
        result[i] = items[i]

    tanks = sorted(
        ((i, m) for i, m in enumerate(items) if not is_cleave(m)),
        key=lambda im: (-max_health(im[1]), im[0]),
    )
    used: set[int] = set()

    # Prefer slots that are immediate neighbors of a cleave, left then right, scanning cleaves L→R.
    neighbor_slots: list[int] = []
    seen_slot: set[int] = set()
    for ci in cleave_idx:
        for s in (ci - 1, ci + 1):
            if 0 <= s < n and result[s] is None and s not in seen_slot:
                neighbor_slots.append(s)
                seen_slot.add(s)

    for slot, (ti, tm) in zip(neighbor_slots, tanks):
        result[slot] = tm
        used.add(ti)

    # Fill remaining empties with unused minions in original order.
    rest = [m for i, m in enumerate(items) if i not in used and not is_cleave(m)]
    ri = 0
    for i in range(n):
        if result[i] is None:
            result[i] = rest[ri]
            ri += 1
    return [m for m in result if m is not None]


def _reborn_dr_right(items: list[dict]) -> list[dict]:
    """Reborn / extra-deathrattle minions to the right; both groups keep relative order."""
    left = [m for m in items if not is_reborn_or_dr(m)]
    right = [m for m in items if is_reborn_or_dr(m)]
    if not right:
        return list(items)
    return left + right


def reorder_items(items: list[dict], strategy: str) -> list[dict]:
    """Return a new list (shallow-copied minion refs) in strategy order."""
    if strategy == "orig":
        return list(items)
    if strategy == "rev_orig":
        return list(reversed(items))
    if strategy == "local_swap_b6":
        raise ValueError("local_swap_b6 requires search; use local_search module")

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
    if strategy == "taunt_pin_hp":
        return _taunt_pin_hp(items)
    if strategy == "cleave_adj_tank":
        return _cleave_adj_tank(items)
    if strategy == "reborn_dr_right":
        return _reborn_dr_right(items)
    raise ValueError(f"unknown strategy: {strategy}")


def extract_side_items(inp: dict, side: str) -> list[dict]:
    unit = inp.get(side) or {}
    side_list = unit.get("Side") or {}
    items = side_list.get("items")
    if not isinstance(items, list):
        return []
    return items


def set_side_items(inp: dict, side: str, items: list[dict]) -> dict:
    """Deep-copy input and replace side's Side.items."""
    out = copy.deepcopy(inp)
    unit = out.get(side)
    if not isinstance(unit, dict):
        return out
    side_list = unit.get("Side")
    if not isinstance(side_list, dict):
        return out
    side_list["items"] = list(items)
    return out


def apply_strategy_to_input(inp: dict, side: str, strategy: str) -> dict:
    """Deep-copy input and reorder `side`'s Side.items. Other fields unchanged."""
    items = extract_side_items(inp, side)
    return set_side_items(inp, side, reorder_items(items, strategy))


def apply_order_to_input(inp: dict, side: str, order: list[int]) -> dict:
    """Deep-copy input; place Side.items in the given original-index order."""
    items = extract_side_items(inp, side)
    if len(order) != len(items):
        raise ValueError(f"order length {len(order)} != items {len(items)}")
    reordered = [items[i] for i in order]
    return set_side_items(inp, side, reordered)


def multiset_equal(a: list[str], b: list[str]) -> bool:
    return sorted(a) == sorted(b)


def adjacent_swaps(items: list[dict]) -> list[list[dict]]:
    """All boards after one adjacent swap (n-1 variants)."""
    out: list[list[dict]] = []
    n = len(items)
    for i in range(n - 1):
        nxt = list(items)
        nxt[i], nxt[i + 1] = nxt[i + 1], nxt[i]
        out.append(nxt)
    return out
