# -*- coding: utf-8 -*-
"""Collect ready boards into (bbVersion, turn) buckets; drop ghosts / duos."""
from __future__ import annotations

import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

_TOOLS = Path(__file__).resolve().parents[1]
if str(_TOOLS) not in sys.path:
    sys.path.insert(0, str(_TOOLS))

from standard_layer.combat import discover_games, iter_game_combats, load_meta  # noqa: E402

from .assembler import board_hash, shell_hash  # noqa: E402
from ._paths import default_diag_roots  # noqa: E402


def board_id(game_id: str, turn: int, side: str) -> str:
    return f"{game_id}|t{turn}|{side}"


def is_ghost_opponent(inp: dict, *, opp_hero_card: str | None = None) -> bool:
    """Opponent side is a Kel'Thuzad ghost replay of an eliminated player."""
    if opp_hero_card and "KelThuzad" in opp_hero_card:
        return True
    hero = (inp.get("Opponent") or {}).get("Hero") or {}
    cid = str(hero.get("CardID") or hero.get("CardId") or "")
    return "KelThuzad" in cid


def load_turns(path) -> dict[tuple[str, int], dict]:
    import json
    import os

    by: dict[tuple[str, int], dict] = {}
    p = str(path)
    if not os.path.isfile(p):
        return by
    with open(p, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            t = row.get("turn")
            if t is None:
                continue
            by[(row["gameId"], int(t))] = row
    return by


@dataclass
class Board:
    board_id: str
    game_id: str
    turn: int
    side: str
    bb_version: str
    input: dict
    board_hash: str
    shell_hash: str
    is_ghost: bool
    status: str
    game_dir: str
    label: dict = field(default_factory=dict)

    def to_row(self) -> dict[str, Any]:
        return {
            "boardId": self.board_id,
            "gameId": self.game_id,
            "turn": self.turn,
            "side": self.side,
            "bbVersion": self.bb_version,
            "boardHash": self.board_hash,
            "shellHash": self.shell_hash,
            "status": self.status,
            "isGhost": int(self.is_ghost),
        }


def collect_boards(
    roots: list[str] | None,
    bb_version: str,
    turns_by: dict[tuple[str, int], dict] | None = None,
    *,
    max_turn: int | None = None,
    include_opponent: bool = True,
    require_ready: bool = True,
) -> list[Board]:
    """Pool units: ready solo turns with _input; Opponent excludes ghosts."""
    roots = roots if roots is not None else default_diag_roots()
    turns_by = turns_by or {}
    games = discover_games(roots)
    boards: list[Board] = []

    for gid, gdir in sorted(games.items()):
        meta = load_meta(gdir)
        bb = (meta.get("bobsBuddy") or {}).get("fileVersion") or (meta.get("bobsBuddy") or {}).get(
            "version"
        )
        if str(bb) != bb_version:
            continue
        if meta.get("isBattlegroundsDuosMatch"):
            continue
        try:
            _, _, combats = iter_game_combats(gdir)
        except Exception as ex:  # noqa: BLE001
            print(f"[skip] {gid}: {ex}", flush=True)
            continue

        for c in combats:
            inp = c.get("input")
            turn = c.get("turn")
            if not inp or turn is None:
                continue
            if max_turn is not None and int(turn) > max_turn:
                continue
            row = turns_by.get((gid, int(turn)))
            status = (row or {}).get("status")
            if require_ready:
                if row is None:
                    # fallback: accept combat with both input+output (P3-T0 compat)
                    if not (c.get("hasInput") and c.get("hasOutput")):
                        continue
                    status = "ready"
                elif status != "ready":
                    continue
            elif status is None:
                status = "unknown"

            ghost = is_ghost_opponent(
                inp, opp_hero_card=(row or {}).get("oppHeroCard") or c.get("oppHeroCard")
            )
            out_sum = c.get("outputSummary") or {}
            label = {
                "result": (row or {}).get("result"),
                "damage": (row or {}).get("damage"),
                "resultSource": (row or {}).get("resultSource"),
                "hdtWin": (out_sum.get("winRate") if out_sum else None)
                or ((row or {}).get("output") or {}).get("winRate"),
                "hdtTie": (out_sum.get("tieRate") if out_sum else None)
                or ((row or {}).get("output") or {}).get("tieRate"),
                "hdtLoss": (out_sum.get("lossRate") if out_sum else None)
                or ((row or {}).get("output") or {}).get("lossRate"),
                "placement": (row or {}).get("placement"),
            }

            sides = ("Player", "Opponent") if include_opponent else ("Player",)
            for side in sides:
                if not isinstance(inp.get(side), dict):
                    continue
                is_ghost = bool(side == "Opponent" and ghost)
                if is_ghost:
                    continue  # 不入池
                bid = board_id(gid, int(turn), side)
                boards.append(
                    Board(
                        board_id=bid,
                        game_id=gid,
                        turn=int(turn),
                        side=side,
                        bb_version=bb_version,
                        input=inp,
                        board_hash=board_hash(inp, side),
                        shell_hash=shell_hash(inp),
                        is_ghost=False,
                        status=status or "ready",
                        game_dir=gdir,
                        label=label,
                    )
                )
    return boards


def bucket_boards(boards: list[Board]) -> dict[tuple[str, int], list[Board]]:
    """Key = (bbVersion, turn)."""
    out: dict[tuple[str, int], list[Board]] = defaultdict(list)
    for b in boards:
        out[(b.bb_version, b.turn)].append(b)
    return dict(out)


def game_time_key(game_id: str) -> str:
    """gameId like 20261002_112126_xxx sorts chronologically."""
    return game_id
