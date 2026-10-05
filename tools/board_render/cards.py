# -*- coding: utf-8 -*-
"""Optional base attack/health for green-stat highlighting.

Lookup order: data/art_cache/cards.zhCN.json → HDT CardDefs (if present) → HSJSON download.
Failure is non-fatal: callers treat missing bases as white stats.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from tools.standard_layer._paths import REPO

HSJSON_CARDS = "https://api.hearthstonejson.com/v1/latest/zhCN/cards.json"


def default_cards_json() -> Path:
    return REPO / "data" / "art_cache" / "cards.zhCN.json"


def default_carddefs_candidates() -> list[Path]:
    appdata = Path(os.environ.get("APPDATA", "")) / "HearthstoneDeckTracker"
    return [
        appdata / "CardDefs" / "CardDefs.xml",
        appdata / "Files" / "CardDefs.xml",
        appdata / "CardDefs.xml",
    ]


@dataclass
class CardBaseStats:
    attack: int
    health: int


@dataclass
class CardStore:
    path: Optional[Path] = None
    offline: bool = False
    by_id: dict[str, CardBaseStats] = field(default_factory=dict)
    source: str = "none"  # "cache" | "carddefs" | "hsjson" | "none"

    @classmethod
    def open(cls, *, offline: bool = False, path: str | Path | None = None) -> "CardStore":
        store = cls(offline=offline)
        cache = Path(path) if path else default_cards_json()
        if cache.is_file():
            if store._load_json(cache):
                store.path = cache
                store.source = "cache"
                return store
        for cand in default_carddefs_candidates():
            if cand.is_file() and store._load_carddefs(cand):
                store.path = cand
                store.source = "carddefs"
                return store
        if not offline:
            cache.parent.mkdir(parents=True, exist_ok=True)
            if store._download_json(cache) and store._load_json(cache):
                store.path = cache
                store.source = "hsjson"
                return store
        store.source = "none"
        return store

    def get(self, card_id: str) -> Optional[CardBaseStats]:
        if not card_id:
            return None
        if card_id in self.by_id:
            return self.by_id[card_id]
        # Golden art ids share base stats with the non-_G card.
        if card_id.endswith("_G"):
            return self.by_id.get(card_id[:-2])
        return None

    def _load_json(self, path: Path) -> bool:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            return False
        if not isinstance(data, list):
            return False
        count = 0
        for row in data:
            if not isinstance(row, dict):
                continue
            cid = row.get("id")
            if not isinstance(cid, str) or not cid:
                continue
            atk = row.get("attack")
            hp = row.get("health")
            if atk is None and hp is None:
                continue
            self.by_id[cid] = CardBaseStats(
                attack=int(atk) if atk is not None else 0,
                health=int(hp) if hp is not None else 0,
            )
            count += 1
        return count > 0

    def _load_carddefs(self, path: Path) -> bool:
        """Minimal CardDefs.xml parse: Entity CardID + ATK/HEALTH tags."""
        try:
            tree = ET.parse(path)
        except (OSError, ET.ParseError):
            return False
        count = 0
        for ent in tree.getroot().iter("Entity"):
            cid = ent.get("CardID")
            if not cid:
                continue
            atk = None
            hp = None
            for tag in ent.findall("Tag"):
                enum = tag.get("enumID") or tag.get("name")
                val = tag.get("value")
                if val is None:
                    continue
                if enum in ("47", "ATK"):
                    atk = int(val)
                elif enum in ("45", "HEALTH"):
                    hp = int(val)
            if atk is None and hp is None:
                continue
            self.by_id[cid] = CardBaseStats(attack=atk or 0, health=hp or 0)
            count += 1
        return count > 0

    def _download_json(self, dest: Path) -> bool:
        tmp = dest.with_suffix(dest.suffix + ".part")
        try:
            req = urllib.request.Request(
                HSJSON_CARDS,
                headers={"User-Agent": "hdt-bg-helper-board-render/0.1"},
            )
            with urllib.request.urlopen(req, timeout=120) as resp:
                data = resp.read()
            if not data:
                return False
            tmp.write_bytes(data)
            tmp.replace(dest)
            return True
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError):
            if tmp.exists():
                try:
                    tmp.unlink()
                except OSError:
                    pass
            return False
