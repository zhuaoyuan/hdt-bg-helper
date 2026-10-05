# -*- coding: utf-8 -*-
"""Extract a single-side minion row from combat_start entities (preferred) or BB Input."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Optional

from tools.standard_layer.combat import get_player_obj, list_items

SideName = Literal["player", "opponent"]

# GAME_TAG names used in entities dumps (HDT Entity tags; baseline 509bb0b9).
# Numeric fallbacks match HearthDb GameTag enum values.
_TAG_ALIASES: dict[str, tuple[Any, ...]] = {
    "CARDTYPE": ("CARDTYPE", 4),
    "ZONE": ("ZONE", 49),
    "ZONE_POSITION": ("ZONE_POSITION", 263),
    "ATK": ("ATK", 47),
    "HEALTH": ("HEALTH", 45),
    "DAMAGE": ("DAMAGE", 44),
    "PREMIUM": ("PREMIUM", 12),
    "TAUNT": ("TAUNT", 190),
    "DIVINE_SHIELD": ("DIVINE_SHIELD", 194),
    "DEATH_RATTLE": ("DEATH_RATTLE", 217),
    "REBORN": ("REBORN", 1085),
    "POISONOUS": ("POISONOUS", 363),
    "VENOMOUS": ("VENOMOUS", 2853),
    "WINDFURY": ("WINDFURY", 189),
    "STEALTH": ("STEALTH", 191),
}

CARDTYPE_MINION = 4
ZONE_PLAY = 1


@dataclass
class MinionView:
    card_id: str
    base_card_id: str
    attack: int
    health: int
    golden: bool
    taunt: bool
    divine_shield: bool
    deathrattle: bool
    reborn: bool
    poisonous: bool
    venomous: bool
    windfury: bool
    stealth: bool
    position: int


@dataclass
class SideBoard:
    """Stateless single-side board; no player/opponent semantics in render_side."""

    minions: list[MinionView]
    source: str  # "entities" | "input"
    label: str | None = None


def base_card_id(card_id: str | None) -> str:
    if not card_id:
        return ""
    return card_id[:-2] if card_id.endswith("_G") else card_id


def art_card_id(card_id: str | None, golden: bool) -> str:
    """Portrait id: prefer *_G when golden (entities often already have it; BB usually does not)."""
    cid = card_id or ""
    if golden and cid and not cid.endswith("_G"):
        return cid + "_G"
    return cid


def check_tuple(m: MinionView) -> tuple[str, int, int, bool, bool, bool]:
    """Identity used by --check: (base id, atk, health, golden, taunt, divine_shield)."""
    return (m.base_card_id, m.attack, m.health, m.golden, m.taunt, m.divine_shield)


def _tag(entity: dict, name: str) -> Any:
    tags = entity.get("tags") or {}
    for key in _TAG_ALIASES.get(name, (name,)):
        if key in tags:
            return tags[key]
        sk = str(key)
        if sk in tags:
            return tags[sk]
    return None


def _tag_int(entity: dict, name: str, default: int = 0) -> int:
    v = _tag(entity, name)
    if v is None or v == "":
        return default
    try:
        return int(v)
    except (TypeError, ValueError):
        return default


def _tag_bool(entity: dict, name: str) -> bool:
    v = _tag(entity, name)
    if v is None or v == "" or v is False:
        return False
    try:
        return int(v) != 0
    except (TypeError, ValueError):
        return bool(v)


def _entity_card_id(entity: dict) -> str:
    info = entity.get("info") if isinstance(entity.get("info"), dict) else {}
    cid = info.get("LatestCardId") or entity.get("cardId") or ""
    return cid if isinstance(cid, str) else str(cid or "")


def minion_from_entity(entity: dict) -> MinionView | None:
    """Build MinionView from a PLAY-zone minion entity, or None if not a board minion."""
    if _tag_int(entity, "CARDTYPE") != CARDTYPE_MINION:
        return None
    if _tag_int(entity, "ZONE") != ZONE_PLAY:
        return None
    cid = _entity_card_id(entity)
    golden = _tag_bool(entity, "PREMIUM")
    health = _tag_int(entity, "HEALTH") - _tag_int(entity, "DAMAGE")
    return MinionView(
        card_id=art_card_id(cid, golden),
        base_card_id=base_card_id(cid),
        attack=_tag_int(entity, "ATK"),
        health=health,
        golden=golden,
        taunt=_tag_bool(entity, "TAUNT"),
        divine_shield=_tag_bool(entity, "DIVINE_SHIELD"),
        deathrattle=_tag_bool(entity, "DEATH_RATTLE"),
        reborn=_tag_bool(entity, "REBORN"),
        poisonous=_tag_bool(entity, "POISONOUS"),
        venomous=_tag_bool(entity, "VENOMOUS"),
        windfury=_tag_bool(entity, "WINDFURY"),
        stealth=_tag_bool(entity, "STEALTH"),
        position=_tag_int(entity, "ZONE_POSITION"),
    )


def side_from_entities(
    entities: list[dict],
    context: dict,
    side: SideName,
    *,
    label: str | None = None,
) -> SideBoard:
    """Preferred path: entities@combat_start + context.<side>.board (ZONE=PLAY minions)."""
    by_id: dict[int, dict] = {}
    for e in entities or []:
        eid = e.get("id")
        if eid is not None:
            by_id[int(eid)] = e

    board_ids = ((context or {}).get(side) or {}).get("board") or []
    rows: list[tuple[int, MinionView]] = []
    for eid in board_ids:
        ent = by_id.get(int(eid))
        if not ent:
            continue
        mv = minion_from_entity(ent)
        if mv is None:
            continue
        rows.append((mv.position, mv))
    rows.sort(key=lambda x: x[0])
    # Normalize positions to 1..n in board order (ZONE_POSITION can have gaps).
    minions = []
    for i, (_, m) in enumerate(rows, start=1):
        minions.append(
            MinionView(
                card_id=m.card_id,
                base_card_id=m.base_card_id,
                attack=m.attack,
                health=m.health,
                golden=m.golden,
                taunt=m.taunt,
                divine_shield=m.divine_shield,
                deathrattle=m.deathrattle,
                reborn=m.reborn,
                poisonous=m.poisonous,
                venomous=m.venomous,
                windfury=m.windfury,
                stealth=m.stealth,
                position=i,
            )
        )
    return SideBoard(minions=minions, source="entities", label=label or side)


def _bb_bool(data: dict, *keys: str) -> bool:
    for k in keys:
        v = data.get(k)
        if v is None:
            continue
        if isinstance(v, bool):
            return v
        try:
            return int(v) != 0
        except (TypeError, ValueError):
            return bool(v)
    return False


def minion_from_bb_item(item: dict, position: int) -> MinionView:
    """BB Side.items[] → MinionView. Deathrattle not available as a reliable bool → False."""
    data = item.get("_data") if isinstance(item.get("_data"), dict) else {}
    cid = item.get("CardID") or item.get("CardId") or ""
    if not isinstance(cid, str):
        cid = str(cid or "")
    golden = _bb_bool(data, "Golden")
    atk = data.get("MaxAttack")
    if atk is None:
        atk = data.get("BaseAttack") or 0
    hp = data.get("MaxHealth")
    if hp is None:
        hp = data.get("BaseHealth") or 0
    return MinionView(
        card_id=art_card_id(cid, golden),
        base_card_id=base_card_id(cid),
        attack=int(atk),
        health=int(hp),
        golden=golden,
        taunt=_bb_bool(data, "Taunt"),
        divine_shield=_bb_bool(data, "Div", "DivineShield"),
        deathrattle=False,
        reborn=_bb_bool(data, "Reborn"),
        poisonous=_bb_bool(data, "Poisonous"),
        venomous=_bb_bool(data, "Venomous"),
        windfury=_bb_bool(data, "Windfury"),
        stealth=_bb_bool(data, "Stealth"),
        position=position,
    )


def side_from_input(
    inp: Optional[dict],
    side: SideName,
    *,
    label: str | None = None,
) -> SideBoard:
    """Fallback: Bob's Buddy Input Player/Opponent Side.items."""
    which = "Player" if side == "player" else "Opponent"
    player = get_player_obj(inp, which) if inp else None
    items = list_items((player or {}).get("Side"))
    minions = [
        minion_from_bb_item(m, i)
        for i, m in enumerate(items, start=1)
        if isinstance(m, dict)
    ]
    return SideBoard(minions=minions, source="input", label=label or side)


def side_from_combat(
    combat: dict,
    side: SideName,
    *,
    label: str | None = None,
) -> SideBoard:
    """Prefer entities@combat_start; fall back to BB Input when that side has no minions."""
    entities = combat.get("entities") or []
    context = combat.get("context") or {}
    preferred = side_from_entities(entities, context, side, label=label)
    if preferred.minions:
        return preferred
    inp = combat.get("input")
    fallback = side_from_input(inp, side, label=label)
    if fallback.minions:
        return fallback
    # Keep entities source even if empty (snapshot present but board empty).
    if combat.get("hasStartSnap") or context:
        return preferred
    return fallback


def compare_sides(a: SideBoard, b: SideBoard) -> list[dict]:
    """Return mismatch rows for check_tuple lists (empty = match)."""
    ta = [check_tuple(m) for m in a.minions]
    tb = [check_tuple(m) for m in b.minions]
    if ta == tb:
        return []
    return [
        {
            "entities": ta,
            "input": tb,
            "lenEntities": len(ta),
            "lenInput": len(tb),
        }
    ]
