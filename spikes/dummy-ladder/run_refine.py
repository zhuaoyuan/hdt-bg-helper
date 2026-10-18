# -*- coding: utf-8 -*-
"""Fill geometric steps inside each probe board's 50% bracket."""
from __future__ import annotations

import json
import math
import subprocess
from pathlib import Path

OUT = Path(__file__).resolve().parent / "out"
EXE = Path(__file__).resolve().parent / "DummySim" / "bin" / "run" / "DummySim.exe"
BB_DIR = r"C:\Program Files\HDT"
ITERATIONS = 500
# 7 interior points between a doubling (ratio 2^(1/8)).
SLICES = 8
EXTRA_TOP = [4096, 8192, 16384, 32768]


def combat_score(row: dict) -> float:
    return float(row["winRate"]) + 0.5 * float(row["tieRate"])


def main() -> None:
    curves = json.loads((OUT / "curves.json").read_text(encoding="utf-8"))
    path_by = {}
    for row in json.loads((OUT / "boards.json").read_text(encoding="utf-8")):
        path_by[(row["gameId"], row["turn"])] = row["inputPath"]

    jobs = []
    for curve in curves:
        path = path_by[(curve["gameId"], curve["turn"])]
        levels = curve["levels"]
        scores = curve["scores"]
        if curve["x50Status"] == "above":
            extra = EXTRA_TOP
        else:
            bracket = None
            for i in range(len(levels) - 1):
                if scores[i] >= 0.5 > scores[i + 1]:
                    bracket = (levels[i], levels[i + 1])
                    break
            if bracket is None:
                continue
            lo, hi = bracket
            extra = []
            for k in range(1, SLICES):
                extra.append(max(lo + 1, round(lo * (2 ** (k / SLICES)))))
            extra = sorted(set(extra) - set(levels))
        for level in extra:
            jobs.append({
                "id": f"{curve['gameId']}|t{curve['turn']}|L{level}",
                "inputPath": path,
                "attack": level,
                "health": level,
                "count": 7,
            })

    jobs_path = OUT / "refine-jobs.jsonl"
    with jobs_path.open("w", encoding="utf-8") as handle:
        for job in jobs:
            handle.write(json.dumps(job) + "\n")
    print(f"refine_jobs={len(jobs)}", flush=True)
    log_path = OUT / "refine.jsonl"
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
            if done % 40 == 0 or '"ok": false' in line or '"ok":false' in line:
                print(f"{done} {line[:160]}", flush=True)
        code = proc.wait()
    print(f"exit={code} lines={done}", flush=True)
    if code != 0:
        raise SystemExit(code)


if __name__ == "__main__":
    main()
