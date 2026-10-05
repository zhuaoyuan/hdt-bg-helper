# -*- coding: utf-8 -*-
"""Minimal Power.log tag replayer for BgHelperDiag power.log.gz files.

Only tracks entity tags (FULL_ENTITY / SHOW_ENTITY / CHANGE_ENTITY / TAG_CHANGE,
plus GameEntity / Player blocks inside CREATE_GAME). Enough to read hero
HEALTH / DAMAGE / ARMOR / PLAYER_LEADERBOARD_PLACE at any line.
"""
from __future__ import annotations

import gzip
import os
import re
from typing import Iterator

LINE_RE = re.compile(r"^(\d+)\t\d+\t\S+ \S+ PowerTaskList\.DebugPrintPower\(\) - (\s*)(.*)$")
ENT_BRACKET_RE = re.compile(r"\[entityName=.*? id=(\d+) .*?cardId=(\S*) player=(\d+)\]")
CREATE_RE = re.compile(r"^FULL_ENTITY - Creating ID=(\d+) CardID=(\S*)")
UPDATE_RE = re.compile(r"^(FULL_ENTITY|SHOW_ENTITY|CHANGE_ENTITY) - Updating (?:Entity=)?(.+?) CardID=(\S*)$")
TAG_RE = re.compile(r"^tag=(\S+) value=(\S+)$")
TAG_CHANGE_RE = re.compile(r"^TAG_CHANGE Entity=(.+?) tag=(\S+) value=(\S+)(?: DEF CHANGE)?$")
GAME_ENTITY_RE = re.compile(r"^GameEntity EntityID=(\d+)")
PLAYER_RE = re.compile(r"^Player EntityID=(\d+) PlayerID=(\d+)")


def read_power(game_dir: str) -> list[tuple[int, str]]:
    """Return [(lineSeq, payload)] where payload is the text after 'DebugPrintPower() - ' (stripped)."""
    from diag_io import open_text, power_path

    path = power_path(game_dir)
    if not path:
        path = os.path.join(game_dir, "power.log.gz")
        if not os.path.exists(path):
            return []
    out = []
    with open_text(path) as f:
        for raw in f:
            m = LINE_RE.match(raw.rstrip("\r\n"))
            if m:
                out.append((int(m.group(1)), m.group(3)))
    return out


def _to_int(v: str):
    try:
        return int(v)
    except ValueError:
        return v


class TagState:
    def __init__(self) -> None:
        self.tags: dict[int, dict[str, object]] = {}
        self.card: dict[int, str] = {}
        self.game_entity: int | None = None
        self.player_ids: dict[int, int] = {}  # entity id -> PlayerID
        self.name_to_id: dict[str, int] = {}
        self._cur: int | None = None
        self.create_game_lines: list[int] = []

    def resolve(self, ref: str) -> int | None:
        m = ENT_BRACKET_RE.search(ref)
        if m:
            eid = int(m.group(1))
            if m.group(2):
                self.card.setdefault(eid, m.group(2))
            return eid
        if ref == "GameEntity":
            return self.game_entity
        if ref.isdigit():
            return int(ref)
        return self.name_to_id.get(ref)

    def feed(self, seq: int, payload: str) -> tuple[int, str, object] | None:
        """Apply one line. Returns (entity, tag, value) for TAG_CHANGE / block tags, else None."""
        m = TAG_RE.match(payload)
        if m:
            if self._cur is not None:
                v = _to_int(m.group(2))
                self.tags.setdefault(self._cur, {})[m.group(1)] = v
                return (self._cur, m.group(1), v)
            return None
        self._cur = None
        if payload == "CREATE_GAME":
            self.create_game_lines.append(seq)
            return None
        m = GAME_ENTITY_RE.match(payload)
        if m:
            self.game_entity = int(m.group(1))
            self._cur = self.game_entity
            return None
        m = PLAYER_RE.match(payload)
        if m:
            eid = int(m.group(1))
            self.player_ids[eid] = int(m.group(2))
            self._cur = eid
            return None
        m = CREATE_RE.match(payload)
        if m:
            eid = int(m.group(1))
            if m.group(2):
                self.card[eid] = m.group(2)
            self._cur = eid
            return None
        m = UPDATE_RE.match(payload)
        if m:
            eid = self.resolve(m.group(2))
            if eid is not None and m.group(3):
                self.card[eid] = m.group(3)
            self._cur = eid
            return None
        m = TAG_CHANGE_RE.match(payload)
        if m:
            ref = m.group(1)
            eid = self.resolve(ref)
            if eid is None:
                return None
            v = _to_int(m.group(3))
            self.tags.setdefault(eid, {})[m.group(2)] = v
            return (eid, m.group(2), v)
        return None

    def get(self, eid: int | None, tag: str, default=0):
        if eid is None:
            return default
        return self.tags.get(eid, {}).get(tag, default)

    def leaderboard_heroes(self) -> dict[int, dict]:
        out = {}
        for eid, t in self.tags.items():
            if "PLAYER_LEADERBOARD_PLACE" in t and t.get("CARDTYPE") == "HERO":
                out[eid] = {
                    "id": eid,
                    "card": self.card.get(eid),
                    "controller": t.get("CONTROLLER"),
                    "place": t.get("PLAYER_LEADERBOARD_PLACE"),
                    "health": t.get("HEALTH", 0),
                    "damage": t.get("DAMAGE", 0),
                    "armor": t.get("ARMOR", 0),
                    "zone": t.get("ZONE"),
                }
        return out


def iter_replay(lines: list[tuple[int, str]]) -> Iterator[tuple[int, str, TagState, tuple | None]]:
    st = TagState()
    for seq, payload in lines:
        ev = st.feed(seq, payload)
        yield seq, payload, st, ev
