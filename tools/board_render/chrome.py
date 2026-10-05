# -*- coding: utf-8 -*-
"""Border / keyword chrome: --chrome-dir → installed HDT Resources/Minion → drawn fallback.

HDT packs Minion PNGs as WPF resources (App.xaml:47–59, baseline 509bb0b9). Installed
Squirrel app-* trees usually do NOT expose loose Resources/Minion files; probing still
checks common paths. Source checkouts may have the PNGs on disk — usable via --chrome-dir
for personal non-commercial local use only (ADR-0006 / ADR-0012). Never copy into git.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from PIL import Image, ImageDraw

# Filenames aligned with HDT App.xaml StaticResource paths under Resources/Minion/.
CHROME_FILES = {
    "border": "border.png",
    "border_premium": "border_premium.png",
    "taunt": "taunt.png",
    "taunt_premium": "taunt_premium.png",
    "divine_shield": "divine-shield.png",
    "deathrattle": "deathrattle.png",
    "reborn": "reborn.png",
    "poisonous": "poisonous.png",
    "venomous": "venomous.png",
    "stats": "stats.png",
    "stats_premium": "stats_premium.png",
    "legendary": "legendary.png",
    "legendary_premium": "legendary_premium.png",
}


def _candidate_hdt_minion_dirs() -> list[Path]:
    """Probe order for loose Minion PNGs next to an HDT install."""
    out: list[Path] = []
    local = Path(os.environ.get("LOCALAPPDATA", "")) / "HearthstoneDeckTracker"
    if local.is_dir():
        # Newest Squirrel app-* first.
        apps = sorted(
            [p for p in local.glob("app-*") if p.is_dir()],
            key=lambda p: p.name,
            reverse=True,
        )
        for app in apps:
            out.append(app / "Resources" / "Minion")
        out.append(local / "Resources" / "Minion")

    # Legacy 团子 / Program Files layout (local-environment.md).
    for prog in (
        Path(r"C:\Program Files\HDT"),
        Path(r"C:\Program Files (x86)\HDT"),
    ):
        out.append(prog / "Resources" / "Minion")
        out.append(prog)

    # Developer source checkout (AGENTS.md); only if Resources/Minion actually exists.
    src = (
        Path(r"C:\projects\github\Hearthstone-Deck-Tracker")
        / "Hearthstone Deck Tracker"
        / "Resources"
        / "Minion"
    )
    out.append(src)
    return out


def find_chrome_dir(explicit: str | Path | None = None) -> Optional[Path]:
    if explicit:
        p = Path(explicit)
        if (p / CHROME_FILES["border"]).is_file() or (p / "border.png").is_file():
            return p
        nested = p / "Resources" / "Minion"
        if (nested / "border.png").is_file():
            return nested
        return None
    for cand in _candidate_hdt_minion_dirs():
        if (cand / "border.png").is_file():
            return cand
    return None


@dataclass
class ChromeStore:
    """Load HDT chrome PNGs when available; otherwise draw simple substitutes."""

    chrome_dir: Optional[Path] = None
    source: str = "drawn"  # "hdt" | "drawn"
    images: dict[str, Image.Image] = field(default_factory=dict, repr=False)

    @classmethod
    def open(cls, chrome_dir: str | Path | None = None) -> "ChromeStore":
        found = find_chrome_dir(chrome_dir)
        store = cls(chrome_dir=found, source="hdt" if found else "drawn")
        if found:
            store._load(found)
        return store

    def _load(self, directory: Path) -> None:
        for key, name in CHROME_FILES.items():
            path = directory / name
            if path.is_file():
                try:
                    self.images[key] = Image.open(path).convert("RGBA")
                except OSError:
                    continue

    def get(self, key: str) -> Optional[Image.Image]:
        img = self.images.get(key)
        return img.copy() if img is not None else None

    def has_hdt(self) -> bool:
        return self.source == "hdt" and bool(self.images)

    def drawn_border(self, size: tuple[int, int], *, golden: bool) -> Image.Image:
        w, h = size
        img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        color = (218, 165, 32, 230) if golden else (160, 160, 160, 220)
        width = 5 if golden else 3
        # Ellipse inset so stroke stays inside the box.
        draw.ellipse([2, 2, w - 3, h - 3], outline=color, width=width)
        return img

    def drawn_badge(self, text: str, *, fill: tuple[int, int, int, int]) -> Image.Image:
        """Small pill used when keyword PNG is missing (e.g. windfury / stealth)."""
        # Size is approximate; render.py may rescale.
        w, h = 36, 18
        img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        draw.rounded_rectangle([0, 0, w - 1, h - 1], radius=4, fill=fill)
        try:
            from PIL import ImageFont

            font = ImageFont.truetype("msyh.ttc", 11)
        except OSError:
            font = ImageFont.load_default()
        # Center-ish text.
        tw, th = draw.textbbox((0, 0), text, font=font)[2:]
        draw.text(((w - tw) / 2, (h - th) / 2 - 1), text, fill=(255, 255, 255, 255), font=font)
        return img
