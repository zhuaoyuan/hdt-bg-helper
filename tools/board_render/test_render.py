# -*- coding: utf-8 -*-
"""Smoke tests for render_side (no network / no real captures)."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from PIL import Image

from tools.board_render.art import ArtStore
from tools.board_render.board import MinionView, SideBoard
from tools.board_render.chrome import ChromeStore
from tools.board_render.render import compose_sides, render_side, save_png


def _minion(**kwargs) -> MinionView:
    base = dict(
        card_id="TEST",
        base_card_id="TEST",
        attack=1,
        health=1,
        golden=False,
        taunt=False,
        divine_shield=False,
        deathrattle=False,
        reborn=False,
        poisonous=False,
        venomous=False,
        windfury=False,
        stealth=False,
        position=1,
    )
    base.update(kwargs)
    return MinionView(**base)


class RenderSmokeTests(unittest.TestCase):
    def test_render_empty_and_keywords_offline(self):
        with tempfile.TemporaryDirectory() as td:
            art = ArtStore(cache_dir=Path(td) / "p", hdt_portraits_dir=Path(td) / "h", offline=True)
            chrome = ChromeStore.open(chrome_dir=Path(td) / "nochrome")
            empty = render_side(SideBoard([], "entities"), art=art, chrome=chrome)
            self.assertEqual(empty.mode, "RGB")
            self.assertGreater(empty.width, 0)

            side = SideBoard(
                [
                    _minion(card_id="A", attack=2, health=3, taunt=True, divine_shield=True),
                    _minion(
                        card_id="B_G",
                        base_card_id="B",
                        attack=5,
                        health=5,
                        golden=True,
                        deathrattle=True,
                        windfury=True,
                        stealth=True,
                        position=2,
                    ),
                ],
                "entities",
            )
            img = render_side(side, art=art, chrome=chrome)
            self.assertEqual(img.mode, "RGB")
            self.assertEqual(img.height, 8 * 2 + 210)
            path = Path(td) / "out.png"
            save_png(img, path)
            self.assertTrue(path.is_file())
            self.assertIn("A", art.missing_ids)

    def test_compose_stacks(self):
        a = Image.new("RGB", (100, 50), (10, 10, 10))
        b = Image.new("RGB", (80, 40), (20, 20, 20))
        stacked = compose_sides(a, b, gap=4)
        self.assertEqual(stacked.height, 40 + 4 + 50)
        self.assertEqual(stacked.width, 100)


if __name__ == "__main__":
    unittest.main()
