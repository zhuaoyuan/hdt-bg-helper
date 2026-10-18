# -*- coding: utf-8 -*-
"""All player boards on turns 6, 8 and 10: coarse ladder, then bracket fill.

Validity sample. Probe growth curve stays in out/. This writes out-wide/.
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

OUT = Path(__file__).resolve().parent / "out-wide"
EXE = Path(__file__).resolve().parent / "DummySim" / "bin" / "run" / "DummySim.exe"
BB_DIR = r"C:\Program Files\HDT"
POOL = "1.85.0.0"
TURNS = (6, 8, 10)
LEVELS = [1, 2, 4, 8, 16, 32, 64, 128, 256, 512, 1024, 2048, 4096, 8192]
SLICES = 8
ITERATIONS = 500


def run_exe(jobs_path: Path, log_path: Path) -> None:
    with log_path.open("w", encoding="utf-8") as log:
        proc = subprocess.Popen(
            [str(EXE), "--bb-dir", BB_DIR, "--batch", str(jobs_path), "--iterations", str(ITERATIONS)],
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
            if done % 200 == 0 or '"ok":false' in line.replace(" ", ""):
                print(f"{log_path.name} {done} {line[:140]}", flush=True)
        code = proc.wait()
    print(f"{log_path.name} exit={code} lines={done}", flush=True)
    if code != 0:
        raise SystemExit(code)


def main() -> None:
    roots = [
        str(_REPO / "data" / "BgHelperDiag"),
        os.path.expandvars(r"%APPDATA%\HearthstoneDeckTracker\BgHelperDiag"),
    ]
    allowed = set(member_versions(POOL))
    picked: list[tuple[str, str, int, int]] = []
    print("indexing", flush=True)
    for gid, gdir in sorted(discover_games(roots).items()):
        meta = load_meta(gdir)
        bb = (meta.get("bobsBuddy") or {}).get("fileVersion") or (meta.get("bobsBuddy") or {}).get("version")
        if str(bb or "") not in allowed or meta.get("isBattlegroundsDuosMatch"):
            continue
        _meta, _records, combats = iter_game_combats(gdir)
        for index, combat in enumerate(combats):
            turn = combat.get("turn")
            if turn not in TURNS or not isinstance(combat.get("input"), dict):
                continue
            player_board, _opp = board_from_input(combat["input"])
            if not player_board:
                continue
            picked.append((gid, gdir, index, int(turn)))
    print(f"boards={len(picked)}", flush=True)

    OUT.mkdir(parents=True, exist_ok=True)
    inputs = OUT / "inputs"
    inputs.mkdir(parents=True, exist_ok=True)
    needed: dict[str, set[int]] = defaultdict(set)
    for _gid, gdir, index, _turn in picked:
        needed[gdir].add(index)
    boards = []
    for gdir, indexes in needed.items():
        _meta, _records, combats = iter_game_combats(gdir)
        for index in indexes:
            combat = combats[index]
            gid = combat and next(p[0] for p in picked if p[1] == gdir and p[2] == index)
            turn = int(combat["turn"])
            path = inputs / f"{gid}_t{turn}.json"
            path.write_text(json.dumps(combat["input"], ensure_ascii=False), encoding="utf-8")
            boards.append({
                "boardId": f"{gid}|t{turn}|Player",
                "gameId": gid,
                "turn": turn,
                "inputPath": str(path),
            })
    (OUT / "boards.json").write_text(json.dumps(boards, ensure_ascii=False), encoding="utf-8")

    jobs_path = OUT / "jobs.jsonl"
    with jobs_path.open("w", encoding="utf-8") as handle:
        for board in boards:
            for level in LEVELS:
                handle.write(json.dumps({
                    "id": f"{board['gameId']}|t{board['turn']}|L{level}",
                    "inputPath": board["inputPath"],
                    "attack": level,
                    "health": level,
                    "count": 7,
                }) + "\n")
    print(f"coarse_jobs={len(boards) * len(LEVELS)}", flush=True)
    run_exe(jobs_path, OUT / "results.jsonl")

    by_board: dict[str, list[dict]] = defaultdict(list)
    with (OUT / "results.jsonl").open(encoding="utf-8") as handle:
        for line in handle:
            row = json.loads(line)
            if row.get("ok"):
                by_board[row["id"].rsplit("|", 1)[0]].append(row)

    refine_jobs = []
    path_by = {(b["gameId"], b["turn"]): b["inputPath"] for b in boards}
    for key, rows in by_board.items():
        rows.sort(key=lambda r: r["attack"])
        game, turn_token = key.split("|")
        turn = int(turn_token[1:])
        path = path_by[(game, turn)]
        scores = [(int(r["attack"]), float(r["winRate"]) + 0.5 * float(r["tieRate"])) for r in rows]
        bracket = None
        for i in range(len(scores) - 1):
            if scores[i][1] >= 0.5 > scores[i + 1][1]:
                bracket = (scores[i][0], scores[i + 1][0])
                break
        if bracket is None:
            continue
        lo, hi = bracket
        extra = []
        for k in range(1, SLICES):
            extra.append(max(lo + 1, round(lo * (2 ** (k / SLICES)))))
        for level in sorted(set(extra) - {s[0] for s in scores}):
            refine_jobs.append({
                "id": f"{game}|t{turn}|L{level}",
                "inputPath": path,
                "attack": level,
                "health": level,
                "count": 7,
            })
    refine_path = OUT / "refine-jobs.jsonl"
    with refine_path.open("w", encoding="utf-8") as handle:
        for job in refine_jobs:
            handle.write(json.dumps(job) + "\n")
    print(f"refine_jobs={len(refine_jobs)}", flush=True)
    if refine_jobs:
        run_exe(refine_path, OUT / "refine.jsonl")
    print("wide done", flush=True)


if __name__ == "__main__":
    main()
