# -*- coding: utf-8 -*-
"""Tests for the canonical dataset manifest."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tools.standard_layer.__main__ import write_dataset_manifest


class DatasetManifestTests(unittest.TestCase):
    def test_writes_hash_and_counts(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td)
            turns = out / "turns.jsonl"
            quality = out / "quality_report.json"
            quality_txt = out / "quality_report.txt"
            turns.write_text('{"gameId": "g1", "turn": 1}\n', encoding="utf-8")
            quality.write_text("{}", encoding="utf-8")
            quality_txt.write_text("report\n", encoding="utf-8")
            report = {
                "gamesCount": 1,
                "turnCount": 1,
                "statusCounts": {"ready": 1},
                "placement": {"rowsWithPlacement": 1},
                "versions": {"bobsBuddy": {"1.85.0.0": 1}},
            }
            path = write_dataset_manifest(
                out,
                roots=["root-a"],
                turns_path=turns,
                report_path=quality,
                report_txt=quality_txt,
                report=report,
            )
            data = json.loads(path.read_text(encoding="utf-8"))
            self.assertTrue(data["canonical"])
            self.assertEqual(data["counts"]["games"], 1)
            self.assertEqual(data["roots"], ["root-a"])
            self.assertEqual(len(data["files"]["turns"]["sha256"]), 64)
            self.assertEqual(data["placement"]["rowsWithPlacement"], 1)


if __name__ == "__main__":
    unittest.main()
