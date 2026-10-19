# -*- coding: utf-8 -*-
"""Cross-DLL stability of X50 on the same boards and the same rungs.

Runs the *same* inputs and the *same* sampled ladder levels under two
BobsBuddy.dll build directories (default 1.85.0.0 and 1.88.6.0), estimates X50
with the same IRLS estimator, and reports:

  * rank agreement (Spearman) between the two X50 sets;
  * median signed / absolute log2 ratio and the multiplicative equivalent;
  * cluster bootstrap (by game) 95% intervals for the median ratio and
    Spearman;
  * per-turn medians and CI widths;
  * per-DLL errors/warnings.

The paired design (same rungs, same inputs, only the DLL changes) is the clean
"is the absolute scale stable across simulator versions?" test.

Usage:
    python spikes/dummy-ladder/cross_dll.py
    python spikes/dummy-ladder/cross_dll.py --limit 100 --bootstrap 1000

Requires out-adaptive/curves.json and out-adaptive/inputs/ (from
run_adaptive.py) and the two BobsBuddy directories on disk.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import random
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_REPO = _HERE.parents[1]
sys.path.insert(0, str(_HERE))

from model_estimate import Point, estimate, median, spearman  # noqa: E402

EXE = _HERE / "DummySim" / "bin" / "run" / "DummySim.exe"
SRC = _HERE / "out-adaptive"
OUT = _HERE / "cross-dll"
DEFAULT_A = ("1.85.0.0", os.path.expandvars(r"%LOCALAPPDATA%\HearthstoneDeckTracker\app-1.58.6"))
DEFAULT_B = ("1.88.6.0", r"C:\Program Files\HDT")


def run_dll(label: str, bb_dir: str, boards: list[dict], iterations: int,
            out_dir: Path, threads: int | None = None) -> tuple[dict[str, dict[int, Point]], list[dict]]:
    dll = os.path.join(bb_dir, "BobsBuddy.dll")
    if not os.path.isfile(dll):
        raise FileNotFoundError(f"no BobsBuddy.dll for {label}: {dll}")
    jobs_path = out_dir / f"jobs-{label}.jsonl"
    log_path = out_dir / f"results-{label}.jsonl"
    jobs = []
    for board in boards:
        for level in board["levels"]:
            jobs.append({"id": f"{board['boardId']}|L{level}", "inputPath": board["inputPath"],
                         "attack": level, "health": level, "count": 7})
    with jobs_path.open("w", encoding="utf-8") as handle:
        for job in jobs:
            handle.write(json.dumps(job, ensure_ascii=False) + "\n")
    cmd = [str(EXE), "--bb-dir", bb_dir, "--batch", str(jobs_path), "--iterations", str(iterations)]
    if threads:
        cmd += ["--threads", str(threads)]
    points: dict[str, dict[int, Point]] = defaultdict(dict)
    errors: list[dict] = []
    warnings = 0
    with log_path.open("w", encoding="utf-8") as log:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                text=True, encoding="utf-8", errors="replace")
        if proc.stdout is None:
            raise RuntimeError("no stdout from DummySim")
        for line in proc.stdout:
            line = line.rstrip()
            if not line:
                continue
            log.write(line + "\n")
            log.flush()
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not row.get("ok"):
                errors.append(row)
                continue
            warnings += int(row.get("warnings") or 0)
            bid = str(row["id"]).rsplit("|L", 1)[0]
            n = float(row.get("simulationCount") or iterations)
            points[bid][int(row["attack"])] = Point(
                int(row["attack"]), float(row["winRate"]) * n,
                float(row["tieRate"]) * n, float(row["lossRate"]) * n,
            )
        code = proc.wait()
    print(f"{label}: jobs={len(jobs)} ok={sum(len(v) for v in points.values())} "
          f"errors={len(errors)} warnings={warnings} exit={code}", flush=True)
    if code != 0:
        raise SystemExit(f"{label} exe exited {code}")
    return points, errors


def pct_interval(values: list[float], lo: float = 2.5, hi: float = 97.5):
    xs = sorted(v for v in values if v is not None)
    if not xs:
        return None
    def pct(p: float) -> float:
        k = (len(xs) - 1) * p / 100.0
        f = int(math.floor(k))
        c = min(f + 1, len(xs) - 1)
        return xs[f] + (xs[c] - xs[f]) * (k - f)
    return (pct(lo), pct(hi))


def cluster_bootstrap(rows: list[dict], b: int = 2000, seed: int = 20261019):
    by_game: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        by_game[row["gameId"]].append(row)
    games = sorted(by_game)
    if not games:
        return {}
    rng = random.Random(seed)
    med_abs, med_signed, rhos = [], [], []
    for _ in range(b):
        sample: list[dict] = []
        for _ in range(len(games)):
            sample.extend(by_game[rng.choice(games)])
        xs = [r["log2A"] for r in sample]
        ys = [r["log2B"] for r in sample]
        med_abs.append(median([abs(x - y) for x, y in zip(xs, ys)]))
        med_signed.append(median([x - y for x, y in zip(xs, ys)]))
        rho = spearman(xs, ys)
        if rho is not None:
            rhos.append(rho)
    return {
        "medianAbsLog2": med_abs,
        "medianSignedLog2": med_signed,
        "spearman": rhos,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--curves", type=Path, default=SRC / "curves.json")
    ap.add_argument("--a-version", default=DEFAULT_A[0])
    ap.add_argument("--a-dir", default=DEFAULT_A[1])
    ap.add_argument("--b-version", default=DEFAULT_B[0])
    ap.add_argument("--b-dir", default=DEFAULT_B[1])
    ap.add_argument("--iterations", type=int, default=500)
    ap.add_argument("--bootstrap", type=int, default=2000)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--threads", type=int, default=None)
    args = ap.parse_args()

    if not EXE.is_file():
        print(f"missing {EXE}; build DummySim first")
        return 2
    if not args.curves.is_file():
        print(f"missing {args.curves}; run run_adaptive.py first")
        return 2
    rows = json.loads(args.curves.read_text(encoding="utf-8"))
    boards = []
    for row in rows:
        ip = SRC / "inputs" / f"{row['gameId']}_t{row['turn']}.json"
        if not ip.is_file():
            continue
        if not row.get("levels"):
            continue
        boards.append({"boardId": row["boardId"], "gameId": row["gameId"],
                       "turn": row["turn"], "levels": row["levels"], "inputPath": str(ip)})
    if args.limit:
        boards = boards[: args.limit]
    if not boards:
        print("no boards with input files; run run_adaptive.py first")
        return 1
    OUT.mkdir(parents=True, exist_ok=True)
    print(f"boards={len(boards)} rungs={sum(len(b['levels']) for b in boards)}")

    pts_a, err_a = run_dll(args.a_version, args.a_dir, boards, args.iterations, OUT, args.threads)
    pts_b, err_b = run_dll(args.b_version, args.b_dir, boards, args.iterations, OUT, args.threads)

    paired = []
    per_turn: dict[int, list[dict]] = defaultdict(list)
    for board in boards:
        bid = board["boardId"]
        ea = estimate(list(pts_a.get(bid, {}).values()))
        eb = estimate(list(pts_b.get(bid, {}).values()))
        if not ea.get("x50") or not eb.get("x50"):
            continue
        row = {
            "boardId": bid, "gameId": board["gameId"], "turn": board["turn"],
            "x50A": ea["x50"], "ciA": ea["ci"], "x50B": eb["x50"], "ciB": eb["ci"],
            "log2A": math.log2(ea["x50"]), "log2B": math.log2(eb["x50"]),
        }
        paired.append(row)
        per_turn[board["turn"]].append(row)
    if len(paired) < 3:
        print(f"only {len(paired)} paired boards")
        return 1

    xs = [r["log2A"] for r in paired]
    ys = [r["log2B"] for r in paired]
    rho = spearman(xs, ys)
    signed = [x - y for x, y in zip(xs, ys)]
    ratios = [abs(v) for v in signed]
    med_signed = median(signed)
    med_abs = median(ratios)

    widths_a, widths_b = [], []
    for r in paired:
        for key, target in (("ciA", widths_a), ("ciB", widths_b)):
            ci = r.get(key)
            if ci and ci[0] > 0 and ci[1] > 0:
                target.append(math.log2(ci[1] / ci[0]))

    def show(name: str, value, digits: int = 4):
        print(f"{name}={None if value is None else round(value, digits)}")

    print(f"paired={len(paired)}")
    show("spearman(A, B)", rho)
    show("median signed log2(A/B)", med_signed)
    print(f"  signed ratio={None if med_signed is None else round(2 ** med_signed, 3)}")
    show("median |log2(A/B)|", med_abs)
    print(f"  abs ratio={None if med_abs is None else round(2 ** med_abs, 3)}"
          f" max={round(max(ratios), 4)} >10%={sum(1 for v in ratios if v > math.log2(1.1))}")
    show("median CI width A", median(widths_a))
    show("median CI width B", median(widths_b))
    print("by turn: n rho medA medB med_abs_log2")
    for turn in sorted(per_turn):
        group = per_turn[turn]
        gx = [r["log2A"] for r in group]
        gy = [r["log2B"] for r in group]
        print(f"  t{turn:02d} n={len(group):3d} rho={spearman(gx, gy)} "
              f"medA={round(2 ** median(gx), 2)} medB={round(2 ** median(gy), 2)} "
              f"med_abs={round(median([abs(x - y) for x, y in zip(gx, gy)]), 4)}")

    boot = cluster_bootstrap(paired, b=args.bootstrap)
    summary = {
        "boards": len(boards),
        "paired": len(paired),
        "aVersion": args.a_version, "bVersion": args.b_version,
        "spearman": rho,
        "medianSignedLog2": med_signed,
        "medianAbsLog2": med_abs,
        "maxAbsLog2": max(ratios) if ratios else None,
        "gt10pct": sum(1 for v in ratios if v > math.log2(1.1)),
        "medianCiWidthA": median(widths_a),
        "medianCiWidthB": median(widths_b),
        "errorsA": len(err_a), "errorsB": len(err_b),
        "bootstrap": {},
    }
    for key, values in boot.items():
        interval = pct_interval(values)
        summary["bootstrap"][key] = {
            "lo": None if interval is None else round(interval[0], 4),
            "hi": None if interval is None else round(interval[1], 4),
        }
        print(f"bootstrap {key}: "
              f"{None if interval is None else (round(interval[0], 4), round(interval[1], 4))}")

    payload = {"summary": summary, "perTurn": {
        str(t): {"n": len(g), "spearman": spearman([r["log2A"] for r in g], [r["log2B"] for r in g])}
        for t, g in per_turn.items()
    }, "pairs": paired}
    (OUT / "compare.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2),
                                      encoding="utf-8")
    print(f"wrote {OUT / 'compare.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
