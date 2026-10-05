# -*- coding: utf-8 -*-
"""Tests for art / chrome / cards asset helpers (no network required)."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from PIL import Image

from tools.board_render.art import ArtStore
from tools.board_render.cards import CardStore
from tools.board_render.chrome import ChromeStore, find_chrome_dir


class ArtStoreTests(unittest.TestCase):
    def test_cache_hit(self):
        with tempfile.TemporaryDirectory() as td:
            cache = Path(td) / "portraits"
            cache.mkdir()
            img = cache / "X.jpg"
            img.write_bytes(b"fake-jpg")
            store = ArtStore(cache_dir=cache, hdt_portraits_dir=Path(td) / "missing", offline=True)
            self.assertEqual(store.path_for("X"), img)
            self.assertEqual(store.missing_ids, [])

    def test_hdt_copy_into_cache(self):
        with tempfile.TemporaryDirectory() as td:
            cache = Path(td) / "portraits"
            hdt = Path(td) / "CardPortraits"
            hdt.mkdir()
            src = hdt / "Y.jpg"
            src.write_bytes(b"from-hdt")
            store = ArtStore(cache_dir=cache, hdt_portraits_dir=hdt, offline=True)
            got = store.path_for("Y")
            self.assertIsNotNone(got)
            assert got is not None
            self.assertTrue(got.is_file())
            self.assertEqual(got.read_bytes(), b"from-hdt")
            self.assertTrue((cache / "Y.jpg").is_file())

    def test_offline_miss_recorded(self):
        with tempfile.TemporaryDirectory() as td:
            store = ArtStore(
                cache_dir=Path(td) / "portraits",
                hdt_portraits_dir=Path(td) / "missing",
                offline=True,
            )
            self.assertIsNone(store.path_for("NOPE"))
            self.assertIn("NOPE", store.missing_ids)


class ChromeStoreTests(unittest.TestCase):
    def test_drawn_fallback_when_missing(self):
        store = ChromeStore.open(chrome_dir=Path(tempfile.gettempdir()) / "no-such-chrome-dir-xyz")
        self.assertEqual(store.source, "drawn")
        border = store.drawn_border((100, 100), golden=False)
        self.assertEqual(border.size, (100, 100))
        self.assertEqual(border.mode, "RGBA")
        badge = store.drawn_badge("风", fill=(80, 80, 180, 220))
        self.assertEqual(badge.mode, "RGBA")

    def test_load_from_dir(self):
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            Image.new("RGBA", (10, 10), (255, 0, 0, 255)).save(d / "border.png")
            Image.new("RGBA", (10, 10), (0, 255, 0, 255)).save(d / "taunt.png")
            store = ChromeStore.open(chrome_dir=d)
            self.assertEqual(store.source, "hdt")
            self.assertIsNotNone(store.get("border"))
            self.assertIsNotNone(store.get("taunt"))
            self.assertIsNone(store.get("venomous"))

    def test_find_explicit_nested(self):
        with tempfile.TemporaryDirectory() as td:
            nested = Path(td) / "Resources" / "Minion"
            nested.mkdir(parents=True)
            Image.new("RGBA", (4, 4)).save(nested / "border.png")
            found = find_chrome_dir(td)
            self.assertEqual(found, nested)


class CardStoreTests(unittest.TestCase):
    def test_load_json_cache(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "cards.zhCN.json"
            path.write_text(
                json.dumps(
                    [
                        {"id": "A", "attack": 2, "health": 3},
                        {"id": "B", "attack": 1, "health": 1},
                    ]
                ),
                encoding="utf-8",
            )
            store = CardStore.open(offline=True, path=path)
            self.assertEqual(store.source, "cache")
            self.assertEqual(store.get("A").attack, 2)
            self.assertEqual(store.get("A_G").health, 3)  # golden shares base

    def test_offline_none_when_missing(self):
        with tempfile.TemporaryDirectory() as td:
            with mock.patch("tools.board_render.cards.default_carddefs_candidates", return_value=[]):
                store = CardStore.open(offline=True, path=Path(td) / "missing.json")
            self.assertEqual(store.source, "none")
            self.assertIsNone(store.get("X"))


if __name__ == "__main__":
    unittest.main()
