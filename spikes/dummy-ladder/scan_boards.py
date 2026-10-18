# -*- coding: utf-8 -*-
"""Stat scan of player boards in one sim pool. No simulation."""
from __future__ import annotations

import os
import statistics
import sys
from collections import defaultdict
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO / "tools"))

from standard_layer.combat import (  # noqa: E402
    board_from_input,
    discover_games,
    get_player_obj,
    iter_game_combats,
    list_items,
    load_meta,
)
from strength.sim_pools import member_versions  # noqa: E402


def main() -> None:
    roots = [
        str(_REPO / "data" / "BgHelperDiag"),
        os.path.expandvars(r"%APPDATA%\HearthstoneDeckTracker\BgHelperDiag"),
    ]
    allowed = set(member_versions("1.85.0.0"))
    by_turn: dict[int, list[tuple]] = defaultdict(list)
    printed = False
    games = 0
    for gid, gdir in sorted(discover_games(roots).items()):
        meta = load_meta(gdir)
        bb = (meta.get("bobsBuddy") or {}).get("fileVersion") or (meta.get("bobsBuddy") or {}).get("version")
        if str(bb or "") not in allowed or meta.get("isBattlegroundsDuosMatch"):
            continue
        games += 1
        _meta, _records, combats = iter_game_combats(gdir)
        for combat in combats:
            inp = combat.get("input")
            if not isinstance(inp, dict):
                continue
            turn = combat.get("turn")
            if not isinstance(turn, int):
                continue
            player_board, _opp = board_from_input(inp)
            if not player_board:
                continue
            atks = [int(m.get("atk") or 0) for m in player_board]
            hps = [int(m.get("health") or 0) for m in player_board]
            by_turn[turn].append((len(player_board), sum(atks), sum(hps), max(atks), max(hps), gid))
            if not printed:
                player = get_player_obj(inp, "Player")
                side = list_items((player or {}).get("Side"))
                m0 = side[0]
                print("card", m0.get("CardID") or m0.get("CardId"))
                print("minion_keys", ",".join(sorted(m0.keys())))
                data = m0.get("_data") if isinstance(m0.get("_data"), dict) else {}
                print("data_keys", ",".join(sorted(data.keys())))
                printed = True

    print(f"games={games} boards={sum(len(v) for v in by_turn.values())}")
    for turn in sorted(by_turn):
        rows = by_turn[turn]
        if turn > 16:
            continue
        atk = sorted(r[1] for r in rows)
        cnt = sorted(r[0] for r in rows)
        mx = sorted(r[3] for r in rows)

        def pct(xs: list[int], p: float) -> int:
            return xs[min(len(xs) - 1, int(p * (len(xs) - 1)))]

        print(
            f"t{turn:02d} n={len(rows):3d} "
            f"nmin_p50={pct(cnt, 0.5):2d} "
            f"sumAtk_p10={pct(atk, 0.1):4d} p50={pct(atk, 0.5):4d} p90={pct(atk, 0.9):5d} "
            f"maxAtk_p50={pct(mx, 0.5):4d} p90={pct(mx, 0.9):4d}"
        )


if __name__ == "__main__":
    main()
