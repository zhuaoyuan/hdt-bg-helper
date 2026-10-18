# -*- coding: utf-8 -*-
"""Pick a stratified player-board sample and fight a fixed vanilla ladder.

Outputs stay under spikes/dummy-ladder/out/ (gitignored).
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO / "tools"))

from standard_layer.combat import (  # noqa: E402
    board_from_input,
    discover_games,
    iter_game_combats,
    load_meta,
)
from strength.sim_pools import member_versions  # noqa: E402

OUT = Path(__file__).resolve().parent / "out"
EXE = Path(__file__).resolve().parent / "DummySim" / "bin" / "run" / "DummySim.exe"
BB_DIR = r"C:\Program Files\HDT"
POOL = "1.85.0.0"
TURNS = range(3, 15)
PER_TURN = 3
LEVELS = [1, 2, 4, 8, 16, 32, 64, 128, 256, 512, 1024, 2048]
COUNT = 7
ITERATIONS = 500


def collect_index() -> dict[int, list[tuple[str, str, int]]]:
    roots = [
        str(_REPO / "data" / "BgHelperDiag"),
        os.path.expandvars(r"%APPDATA%\HearthstoneDeckTracker\BgHelperDiag"),
    ]
    allowed = set(member_versions(POOL))
    by_turn: dict[int, list[tuple[str, str, int]]] = defaultdict(list)
    for gid, gdir in sorted(discover_games(roots).items()):
        meta = load_meta(gdir)
        bb = (meta.get("bobsBuddy") or {}).get("fileVersion") or (meta.get("bobsBuddy") or {}).get("version")
        if str(bb or "") not in allowed or meta.get("isBattlegroundsDuosMatch"):
            continue
        _meta, _records, combats = iter_game_combats(gdir)
        for index, combat in enumerate(combats):
            turn = combat.get("turn")
            if not isinstance(turn, int) or turn not in TURNS:
                continue
            if not isinstance(combat.get("input"), dict):
                continue
            player_board, _opp = board_from_input(combat["input"])
            if not player_board:
                continue
            by_turn[turn].append((gid, gdir, index))
    return by_turn


def choose(by_turn: dict[int, list[tuple[str, str, int]]]) -> list[tuple[str, str, int, int]]:
    picked: list[tuple[str, str, int, int]] = []
    for turn in TURNS:
        rows = sorted(by_turn.get(turn, []), key=lambda r: r[0])
        if not rows:
            continue
        if len(rows) <= PER_TURN:
            idxs = range(len(rows))
        else:
            idxs = sorted({0, len(rows) // 2, len(rows) - 1})
        for i in idxs:
            gid, gdir, combat_index = rows[i]
            picked.append((gid, gdir, combat_index, turn))
    return picked


def write_inputs(picked: list[tuple[str, str, int, int]]) -> list[dict]:
    inputs = OUT / "inputs"
    inputs.mkdir(parents=True, exist_ok=True)
    needed: dict[str, set[int]] = defaultdict(set)
    for gid, gdir, combat_index, turn in picked:
        needed[gdir].add(combat_index)
    written: list[dict] = []
    for gdir, indexes in needed.items():
        _meta, _records, combats = iter_game_combats(gdir)
        for combat_index in indexes:
            combat = combats[combat_index]
            gid = next(p[0] for p in picked if p[1] == gdir and p[2] == combat_index)
            turn = combat["turn"]
            path = inputs / f"{gid}_t{turn}.json"
            path.write_text(json.dumps(combat["input"], ensure_ascii=False), encoding="utf-8")
            written.append({
                "boardId": f"{gid}|t{turn}|player",
                "gameId": gid,
                "turn": turn,
                "inputPath": str(path),
            })
    return written


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    print("indexing", flush=True)
    picked = choose(collect_index())
    print(f"boards={len(picked)}", flush=True)
    boards = write_inputs(picked)
    jobs_path = OUT / "jobs.jsonl"
    with jobs_path.open("w", encoding="utf-8") as f:
        for board in boards:
            for level in LEVELS:
                job = {
                    "id": f"{board['gameId']}|t{board['turn']}|L{level}",
                    "inputPath": board["inputPath"],
                    "attack": level,
                    "health": level,
                    "count": COUNT,
                }
                f.write(json.dumps(job, ensure_ascii=False) + "\n")
    (OUT / "boards.json").write_text(json.dumps(boards, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"jobs={len(boards) * len(LEVELS)}", flush=True)
    log_path = OUT / "results.jsonl"
    with log_path.open("w", encoding="utf-8") as log:
        proc = subprocess.Popen(
            [
                str(EXE),
                "--bb-dir",
                BB_DIR,
                "--batch",
                str(jobs_path),
                "--iterations",
                str(ITERATIONS),
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
        )
        assert proc.stdout is not None
        done = 0
        for line in proc.stdout:
            line = line.rstrip()
            if not line:
                continue
            log.write(line + "\n")
            log.flush()
            done += 1
            if done % 20 == 0 or '"ok":false' in line.replace(" ", ""):
                print(f"{done} {line[:180]}", flush=True)
        code = proc.wait()
    print(f"exit={code} lines={done}", flush=True)
    if code != 0:
        raise SystemExit(code)


if __name__ == "__main__":
    main()
