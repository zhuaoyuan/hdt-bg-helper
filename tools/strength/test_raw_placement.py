# -*- coding: utf-8 -*-
"""game_end leaderboard place for the local hero."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tools.strength.raw_placement import final_local_place, final_local_place_from_lines


def _entities(reason: str, hero: int | None, place: int | None, hero_on_entity: int = 7) -> str:
    player = {"hero": hero} if hero is not None else {}
    tags = {}
    if place is not None:
        tags["PLAYER_LEADERBOARD_PLACE"] = place
    row = {
        "type": "entities",
        "reason": reason,
        "context": {"player": player},
        "entities": [{"id": hero_on_entity, "tags": tags}, {"id": 8, "tags": {"PLAYER_LEADERBOARD_PLACE": 1}}],
    }
    return json.dumps(row)


class RawPlacementTests(unittest.TestCase):
    def test_uses_game_end_not_an_earlier_place(self) -> None:
        lines = [
            _entities("combat_start", 7, 5),
            _entities("game_end", None, 2),
        ]
        self.assertEqual(final_local_place_from_lines(iter(lines)), 2)

    def test_ignores_a_game_with_no_ending(self) -> None:
        lines = [_entities("combat_start", 7, 4)]
        self.assertIsNone(final_local_place_from_lines(iter(lines)))

    def test_reads_a_records_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "records.jsonl"
            path.write_text(_entities("game_end", 7, 6) + "\n", encoding="utf-8")
            self.assertEqual(final_local_place(tmp), 6)


if __name__ == "__main__":
    unittest.main()
