# -*- coding: utf-8 -*-
"""Minion portrait lookup: local cache → HDT CardPortraits (read-only) → HSJSON download."""
from __future__ import annotations

import os
import shutil
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from tools.standard_layer._paths import REPO

HSJSON_PORTRAIT = "https://art.hearthstonejson.com/v1/256x/{card_id}.jpg"


def default_cache_dir() -> Path:
    return REPO / "data" / "art_cache" / "portraits"


def default_hdt_portraits_dir() -> Path:
    appdata = os.environ.get("APPDATA", "")
    return Path(appdata) / "HearthstoneDeckTracker" / "Images" / "CardPortraits"


@dataclass
class ArtStore:
    """Resolve portrait images for card ids. Never commits network files into git (data/ is ignored)."""

    cache_dir: Path = field(default_factory=default_cache_dir)
    hdt_portraits_dir: Path = field(default_factory=default_hdt_portraits_dir)
    offline: bool = False
    missing_ids: list[str] = field(default_factory=list)
    _resolved: dict[str, Optional[Path]] = field(default_factory=dict, repr=False)

    def __post_init__(self) -> None:
        self.cache_dir = Path(self.cache_dir)
        self.hdt_portraits_dir = Path(self.hdt_portraits_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def path_for(self, card_id: str) -> Optional[Path]:
        if not card_id:
            return None
        if card_id in self._resolved:
            return self._resolved[card_id]

        cached = self.cache_dir / f"{card_id}.jpg"
        if cached.is_file() and cached.stat().st_size > 0:
            self._resolved[card_id] = cached
            return cached

        hdt = self.hdt_portraits_dir / f"{card_id}.jpg"
        if hdt.is_file() and hdt.stat().st_size > 0:
            try:
                shutil.copy2(hdt, cached)
                self._resolved[card_id] = cached
                return cached
            except OSError:
                self._resolved[card_id] = hdt
                return hdt

        if not self.offline:
            if self._download(card_id, cached):
                self._resolved[card_id] = cached
                return cached

        if card_id not in self.missing_ids:
            self.missing_ids.append(card_id)
        self._resolved[card_id] = None
        return None

    def _download(self, card_id: str, dest: Path) -> bool:
        url = HSJSON_PORTRAIT.format(card_id=card_id)
        tmp = dest.with_suffix(".jpg.part")
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "hdt-bg-helper-board-render/0.1"})
            with urllib.request.urlopen(req, timeout=30) as resp:
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
