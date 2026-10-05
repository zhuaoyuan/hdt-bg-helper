# -*- coding: utf-8 -*-
"""Render a single-side minion strip to a PNG (ADR-0012: no hero / rates / result)."""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from PIL import Image, ImageDraw, ImageFont

from .art import ArtStore
from .board import MinionView, SideBoard
from .cards import CardStore
from .chrome import ChromeStore

# Layout constants (v1 board strip).
BG_COLOR = (0x20, 0x24, 0x27, 255)
SLOT_W = 150
SLOT_H = 210
PAD_X = 16
PAD_Y = 8
MAX_MINIONS = 7
PORTRAIT_BOX = (256, 256)  # HDT BattlegroundsMinion.xaml canvas size
# EllipseGeometry RadiusX=87 RadiusY=120 Center=128,128
ELLIPSE_RX = 87
ELLIPSE_RY = 120
# Chrome Image Canvas.Left/Top offsets from xaml
CHROME_OFFSET = (-24, -36)
CHROME_SIZE = (300, 350)
DIVINE_OFFSET = (-36, -24)
DIVINE_SIZE = (325, 311)
# Attack/Health text boxes in 256 canvas coords
ATK_BOX = (29, 170, 75, 75)
HP_BOX = (151, 170, 75, 75)

STAT_WHITE = (255, 255, 255, 255)
STAT_GREEN = (0x1E, 0xE1, 0x64, 255)
STAT_OUTLINE = (0, 0, 0, 255)


def _font(size: int) -> ImageFont.ImageFont:
    for name in ("msyhbd.ttc", "msyh.ttc", "arialbd.ttf", "arial.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _ellipse_mask(size: tuple[int, int], rx: int, ry: int) -> Image.Image:
    w, h = size
    mask = Image.new("L", (w, h), 0)
    draw = ImageDraw.Draw(mask)
    cx, cy = w // 2, h // 2
    draw.ellipse([cx - rx, cy - ry, cx + rx, cy + ry], fill=255)
    return mask


def _fit_cover(img: Image.Image, size: tuple[int, int]) -> Image.Image:
    tw, th = size
    iw, ih = img.size
    scale = max(tw / iw, th / ih)
    nw, nh = max(1, int(iw * scale)), max(1, int(ih * scale))
    resized = img.resize((nw, nh), Image.Resampling.LANCZOS)
    left = (nw - tw) // 2
    top = (nh - th) // 2
    return resized.crop((left, top, left + tw, top + th))


def _paste(base: Image.Image, overlay: Image.Image, xy: tuple[int, int]) -> None:
    if overlay.mode != "RGBA":
        overlay = overlay.convert("RGBA")
    base.alpha_composite(overlay, dest=xy)


def _placeholder_portrait(card_id: str) -> Image.Image:
    img = Image.new("RGBA", PORTRAIT_BOX, (70, 74, 80, 255))
    draw = ImageDraw.Draw(img)
    draw.ellipse([128 - ELLIPSE_RX, 128 - ELLIPSE_RY, 128 + ELLIPSE_RX, 128 + ELLIPSE_RY], fill=(55, 58, 64, 255))
    font = _font(18)
    label = card_id or "?"
    # Wrap long ids roughly.
    if len(label) > 12:
        label = label[:12] + "…"
    bbox = draw.textbbox((0, 0), label, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.text(((256 - tw) / 2, (256 - th) / 2), label, fill=(200, 200, 200, 255), font=font)
    return img


def _load_portrait(art: ArtStore, card_id: str) -> tuple[Image.Image, bool]:
    path = art.path_for(card_id)
    if path is None:
        return _placeholder_portrait(card_id), False
    try:
        img = Image.open(path).convert("RGBA")
        return _fit_cover(img, PORTRAIT_BOX), True
    except OSError:
        return _placeholder_portrait(card_id), False


def _stat_color(value: int, base: Optional[int]) -> tuple[int, int, int, int]:
    if base is not None and value > base:
        return STAT_GREEN
    return STAT_WHITE


def _draw_outlined_text(
    canvas: Image.Image,
    text: str,
    box: tuple[int, int, int, int],
    fill: tuple[int, int, int, int],
    font: ImageFont.ImageFont,
) -> None:
    draw = ImageDraw.Draw(canvas)
    x, y, w, h = box
    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    tx = x + (w - tw) / 2 - bbox[0]
    ty = y + (h - th) / 2 - bbox[1]
    for dx, dy in ((-2, 0), (2, 0), (0, -2), (0, 2), (-1, -1), (1, -1), (-1, 1), (1, 1)):
        draw.text((tx + dx, ty + dy), text, font=font, fill=STAT_OUTLINE)
    draw.text((tx, ty), text, font=font, fill=fill)


def render_minion(
    minion: MinionView,
    *,
    art: ArtStore,
    chrome: ChromeStore,
    cards: CardStore | None = None,
) -> Image.Image:
    """Render one minion at HDT 256-canvas resolution, then caller scales into a slot."""
    canvas_w = CHROME_SIZE[0]  # 300 — enough for chrome overhang
    canvas_h = CHROME_SIZE[1]  # 350
    # Origin of the 256 portrait canvas inside the larger chrome canvas.
    origin_x, origin_y = -CHROME_OFFSET[0], -CHROME_OFFSET[1]  # 24, 36

    out = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))

    # Taunt behind portrait (HDT order).
    if minion.taunt:
        key = "taunt_premium" if minion.golden else "taunt"
        layer = chrome.get(key)
        if layer is not None:
            _paste(out, layer.resize(CHROME_SIZE, Image.Resampling.LANCZOS), (0, 0))

    portrait, _ok = _load_portrait(art, minion.card_id)
    mask = _ellipse_mask(PORTRAIT_BOX, ELLIPSE_RX, ELLIPSE_RY)
    clipped = Image.new("RGBA", PORTRAIT_BOX, (0, 0, 0, 0))
    clipped.paste(portrait, (0, 0))
    clipped.putalpha(mask)
    _paste(out, clipped, (origin_x, origin_y))

    def overlay_key(key: str, size: tuple[int, int] = CHROME_SIZE, offset: tuple[int, int] = (0, 0)) -> None:
        layer = chrome.get(key)
        if layer is None:
            return
        _paste(out, layer.resize(size, Image.Resampling.LANCZOS), offset)

    border_key = "border_premium" if minion.golden else "border"
    if chrome.get(border_key) is not None:
        overlay_key(border_key)
    else:
        # Drawn fallback relative to portrait ellipse inside chrome canvas.
        bw, bh = int(ELLIPSE_RX * 2.35), int(ELLIPSE_RY * 2.15)
        border = chrome.drawn_border((bw, bh), golden=minion.golden)
        bx = origin_x + 128 - bw // 2
        by = origin_y + 128 - bh // 2
        _paste(out, border, (bx, by))

    if minion.reborn:
        overlay_key("reborn")
    if minion.deathrattle:
        overlay_key("deathrattle")
    if minion.poisonous:
        overlay_key("poisonous")
    if minion.venomous:
        overlay_key("venomous")

    stats_key = "stats_premium" if minion.golden else "stats"
    overlay_key(stats_key)

    if minion.divine_shield:
        if chrome.get("divine_shield") is not None:
            # Portrait at (24,36); divine at Canvas(-36,-24) → sheet (-12,12).
            overlay_key("divine_shield", size=DIVINE_SIZE, offset=(-12, 12))
        else:
            # Soft ring.
            ring = Image.new("RGBA", PORTRAIT_BOX, (0, 0, 0, 0))
            d = ImageDraw.Draw(ring)
            d.ellipse(
                [128 - ELLIPSE_RX - 4, 128 - ELLIPSE_RY - 4, 128 + ELLIPSE_RX + 4, 128 + ELLIPSE_RY + 4],
                outline=(255, 230, 120, 220),
                width=4,
            )
            _paste(out, ring, (origin_x, origin_y))

    # Windfury / stealth: HDT control does not draw these; use badges.
    badge_y = origin_y + 8
    badge_x = origin_x + 8
    if minion.windfury:
        badge = chrome.drawn_badge("风怒", fill=(40, 90, 180, 230))
        _paste(out, badge, (badge_x, badge_y))
        badge_y += badge.height + 2
    if minion.stealth:
        badge = chrome.drawn_badge("潜行", fill=(80, 80, 100, 230))
        _paste(out, badge, (badge_x, badge_y))

    base = cards.get(minion.base_card_id) if cards else None
    atk_fill = _stat_color(minion.attack, base.attack if base else None)
    hp_fill = _stat_color(minion.health, base.health if base else None)
    font = _font(42)
    atk_box = (origin_x + ATK_BOX[0], origin_y + ATK_BOX[1], ATK_BOX[2], ATK_BOX[3])
    hp_box = (origin_x + HP_BOX[0], origin_y + HP_BOX[1], HP_BOX[2], HP_BOX[3])
    _draw_outlined_text(out, str(minion.attack), atk_box, atk_fill, font)
    _draw_outlined_text(out, str(minion.health), hp_box, hp_fill, font)
    return out


def render_side(
    side: SideBoard,
    *,
    art: ArtStore,
    chrome: ChromeStore,
    cards: CardStore | None = None,
) -> Image.Image:
    """Core API: one SideBoard → one PNG strip (minions only)."""
    minions = list(side.minions)[:MAX_MINIONS]
    n = max(1, len(minions))  # empty board still gets a minimal strip
    width = PAD_X * 2 + SLOT_W * n
    height = PAD_Y * 2 + SLOT_H
    canvas = Image.new("RGBA", (width, height), BG_COLOR)

    if not minions:
        return canvas.convert("RGB")

    for i, m in enumerate(minions):
        tile = render_minion(m, art=art, chrome=chrome, cards=cards)
        # Fit chrome canvas into slot while keeping aspect.
        tw, th = tile.size
        scale = min(SLOT_W / tw, SLOT_H / th)
        nw, nh = max(1, int(tw * scale)), max(1, int(th * scale))
        scaled = tile.resize((nw, nh), Image.Resampling.LANCZOS)
        x = PAD_X + i * SLOT_W + (SLOT_W - nw) // 2
        y = PAD_Y + (SLOT_H - nh) // 2
        canvas.alpha_composite(scaled, dest=(x, y))

    return canvas.convert("RGB")


def compose_sides(player: Image.Image, opponent: Image.Image, *, gap: int = 8) -> Image.Image:
    """Optional convenience: stack opponent above player (not part of render_side)."""
    width = max(player.width, opponent.width)
    height = opponent.height + gap + player.height
    out = Image.new("RGB", (width, height), BG_COLOR[:3])
    out.paste(opponent, ((width - opponent.width) // 2, 0))
    out.paste(player, ((width - player.width) // 2, opponent.height + gap))
    return out


def save_png(img: Image.Image, path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path, format="PNG")
