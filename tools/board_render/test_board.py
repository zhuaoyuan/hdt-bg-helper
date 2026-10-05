# -*- coding: utf-8 -*-
"""Unit tests for board extraction (no real game data required)."""
from __future__ import annotations

import unittest

from tools.board_render.board import (
    art_card_id,
    base_card_id,
    check_tuple,
    compare_sides,
    minion_from_bb_item,
    minion_from_entity,
    side_from_combat,
    side_from_entities,
    side_from_input,
)


def _ent(
    eid: int,
    card_id: str,
    *,
    pos: int,
    atk: int,
    health: int,
    damage: int = 0,
    premium: int = 0,
    taunt: int = 0,
    ds: int = 0,
    dr: int = 0,
    reborn: int = 0,
    poisonous: int = 0,
    venomous: int = 0,
    windfury: int = 0,
    stealth: int = 0,
    cardtype: int = 4,
    zone: int = 1,
    latest: str | None = None,
) -> dict:
    tags = {
        "CARDTYPE": cardtype,
        "ZONE": zone,
        "ZONE_POSITION": pos,
        "ATK": atk,
        "HEALTH": health,
    }
    if damage:
        tags["DAMAGE"] = damage
    if premium:
        tags["PREMIUM"] = premium
    if taunt:
        tags["TAUNT"] = taunt
    if ds:
        tags["DIVINE_SHIELD"] = ds
    if dr:
        tags["DEATH_RATTLE"] = dr
    if reborn:
        tags["REBORN"] = reborn
    if poisonous:
        tags["POISONOUS"] = poisonous
    if venomous:
        tags["VENOMOUS"] = venomous
    if windfury:
        tags["WINDFURY"] = windfury
    if stealth:
        tags["STEALTH"] = stealth
    return {
        "id": eid,
        "cardId": card_id,
        "tags": tags,
        "info": {"LatestCardId": latest if latest is not None else card_id},
    }


def _bb(
    card_id: str,
    *,
    atk: int,
    health: int,
    golden: bool = False,
    taunt: bool = False,
    div: int = 0,
    reborn: bool = False,
    poisonous: bool = False,
    venomous: bool = False,
    windfury: bool = False,
    stealth: bool = False,
) -> dict:
    return {
        "CardID": card_id,
        "_data": {
            "MaxAttack": atk,
            "MaxHealth": health,
            "BaseAttack": atk,
            "BaseHealth": health,
            "Golden": golden,
            "Taunt": taunt,
            "Div": div,
            "Reborn": reborn,
            "Poisonous": poisonous,
            "Venomous": venomous,
            "Windfury": windfury,
            "Stealth": stealth,
        },
    }


class BaseIdTests(unittest.TestCase):
    def test_strip_golden_suffix(self):
        self.assertEqual(base_card_id("BG36_200_G"), "BG36_200")
        self.assertEqual(base_card_id("BG36_200"), "BG36_200")
        self.assertEqual(art_card_id("BG36_200", True), "BG36_200_G")
        self.assertEqual(art_card_id("BG36_200_G", True), "BG36_200_G")


class EntityExtractTests(unittest.TestCase):
    def test_sort_by_zone_position(self):
        entities = [
            _ent(3, "C", pos=3, atk=1, health=1),
            _ent(1, "A", pos=1, atk=2, health=2),
            _ent(2, "B", pos=2, atk=3, health=3),
            _ent(9, "HERO", pos=0, atk=0, health=30, cardtype=3),  # not minion
        ]
        ctx = {"opponent": {"board": [9, 3, 1, 2]}}
        side = side_from_entities(entities, ctx, "opponent")
        self.assertEqual(side.source, "entities")
        self.assertEqual([m.base_card_id for m in side.minions], ["A", "B", "C"])
        self.assertEqual([m.position for m in side.minions], [1, 2, 3])

    def test_golden_and_keywords(self):
        e = _ent(
            1,
            "BG36_200_G",
            pos=1,
            atk=2,
            health=8,
            premium=1,
            taunt=1,
            ds=1,
            dr=1,
            reborn=1,
            poisonous=1,
            venomous=1,
            windfury=1,
            stealth=1,
        )
        m = minion_from_entity(e)
        assert m is not None
        self.assertTrue(m.golden)
        self.assertEqual(m.card_id, "BG36_200_G")
        self.assertEqual(m.base_card_id, "BG36_200")
        self.assertTrue(m.taunt)
        self.assertTrue(m.divine_shield)
        self.assertTrue(m.deathrattle)
        self.assertTrue(m.reborn)
        self.assertTrue(m.poisonous)
        self.assertTrue(m.venomous)
        self.assertTrue(m.windfury)
        self.assertTrue(m.stealth)

    def test_damage_reduces_health(self):
        e = _ent(1, "X", pos=1, atk=5, health=10, damage=3)
        m = minion_from_entity(e)
        assert m is not None
        self.assertEqual(m.health, 7)

    def test_latest_card_id_preferred(self):
        e = _ent(1, "OLD", pos=1, atk=1, health=1, latest="NEW_G")
        e["tags"]["PREMIUM"] = 1
        m = minion_from_entity(e)
        assert m is not None
        self.assertEqual(m.card_id, "NEW_G")
        self.assertEqual(m.base_card_id, "NEW")

    def test_numeric_tag_keys(self):
        e = {
            "id": 1,
            "cardId": "N",
            "tags": {"4": 4, "49": 1, "263": 1, "47": 4, "45": 5, "190": 1},
            "info": {},
        }
        m = minion_from_entity(e)
        assert m is not None
        self.assertEqual(m.attack, 4)
        self.assertEqual(m.health, 5)
        self.assertTrue(m.taunt)


class BbExtractTests(unittest.TestCase):
    def test_golden_art_suffix(self):
        m = minion_from_bb_item(_bb("BG36_200", atk=2, health=8, golden=True), 1)
        self.assertTrue(m.golden)
        self.assertEqual(m.card_id, "BG36_200_G")
        self.assertEqual(m.base_card_id, "BG36_200")
        self.assertFalse(m.deathrattle)  # BB has no reliable deathrattle bool

    def test_div_as_divine_shield(self):
        m = minion_from_bb_item(_bb("A", atk=1, health=1, div=1), 1)
        self.assertTrue(m.divine_shield)

    def test_side_from_input_order(self):
        inp = {
            "Opponent": {
                "Side": {
                    "items": [
                        _bb("A", atk=1, health=1, taunt=True),
                        _bb("B", atk=2, health=2, golden=True),
                    ]
                }
            }
        }
        side = side_from_input(inp, "opponent")
        self.assertEqual(side.source, "input")
        self.assertEqual([m.base_card_id for m in side.minions], ["A", "B"])
        self.assertEqual(check_tuple(side.minions[0]), ("A", 1, 1, False, True, False))
        self.assertEqual(check_tuple(side.minions[1]), ("B", 2, 2, True, False, False))


class CombatPreferTests(unittest.TestCase):
    def test_prefers_entities_when_present(self):
        combat = {
            "entities": [_ent(1, "E", pos=1, atk=1, health=1, dr=1)],
            "context": {"player": {"board": [1]}},
            "input": {"Player": {"Side": {"items": [_bb("E", atk=1, health=1)]}}},
            "hasStartSnap": True,
        }
        side = side_from_combat(combat, "player")
        self.assertEqual(side.source, "entities")
        self.assertTrue(side.minions[0].deathrattle)

    def test_falls_back_to_input(self):
        combat = {
            "entities": [],
            "context": {},
            "input": {"Opponent": {"Side": {"items": [_bb("X", atk=3, health=3, taunt=True)]}}},
            "hasStartSnap": False,
        }
        side = side_from_combat(combat, "opponent")
        self.assertEqual(side.source, "input")
        self.assertEqual(side.minions[0].base_card_id, "X")

    def test_compare_sides_match(self):
        a = side_from_entities(
            [_ent(1, "A_G", pos=1, atk=2, health=8, premium=1, taunt=0, ds=1)],
            {"player": {"board": [1]}},
            "player",
        )
        b = side_from_input(
            {"Player": {"Side": {"items": [_bb("A", atk=2, health=8, golden=True, div=1)]}}},
            "player",
        )
        self.assertEqual(compare_sides(a, b), [])
        self.assertEqual(check_tuple(a.minions[0]), check_tuple(b.minions[0]))


if __name__ == "__main__":
    unittest.main()
