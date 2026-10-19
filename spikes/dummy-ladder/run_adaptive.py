# -*- coding: utf-8 -*-
"""Two-stage / adaptive collection for the dummy ladder + model estimate.

Round 0 (coarse)   : a fixed geometric ladder spanning the observed range.
Round 1 (stage 1)  : per board, two points inside the 50% bracket + two
                     logistic targets (p=0.25, 0.75) from the round-0 fit.
Round 2 (stage 2)  : two logistic targets (p=0.4, 0.6) from the round-1 fit.

The final X50 is the weighted-logistic 0.5 point over all sampled rungs, with
an asymptotic 95% interval (see model_estimate.py). The design is fixed after
the coarse round (no early stopping by default), so the interval is conditional
on the realized rung design rather than on an optional-stopping rule.

Compared with v1 (coarse 14 rungs + 7 fixed bracket points + two-rung
interpolation, ~21 sims/board), the default here is coarse 8 rungs (ratio 4)
+ 4 + 2 + extension, ~14 sims/board.

Usage:
    python spikes/dummy-ladder/run_adaptive.py --selftest       # estimator checks, no BB
    python spikes/dummy-ladder/run_adaptive.py --coarse ratio4 --turns 6,8,10
    python spikes/dummy-ladder/run_adaptive.py --limit 20 --out spikes/dummy-ladder/out-adaptive-smoke

The DummySim.exe must be built first (see spikes/dummy-ladder/README.md).
Outputs stay under the chosen --out directory (gitignored).
"""
from __future__ import annotations

import argparse
import json
import math
import os
import subprocess
import sys
import time
from collections import defaultdict
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_REPO = _HERE.parents[1]
sys.path.insert(0, str(_HERE))
sys.path.insert(0, str(_REPO / "tools"))

from model_estimate import (  # noqa: E402
    Point,
    choose_levels,
    estimate,
    median,
    selftest as estimator_selftest,
)

from standard_layer.combat import (  # noqa: E402
    board_from_input,
    discover_games,
    iter_game_combats,
    load_meta,
)
from strength.sim_pools import member_versions  # noqa: E402

EXE = _HERE / "DummySim" / "bin" / "run" / "DummySim.exe"
BB_DIR = r"C:\Program Files\HDT"
CAP_LEVEL = 1 << 20
MAX_RUNGS = 26


def coarse_levels(mode: str) -> list[int]:
    if mode == "ratio2":
        return [2 ** i for i in range(0, 14)]      # 1 .. 8192
    if mode == "ratio4":
        return [4 ** i for i in range(0, 8)]       # 1 .. 16384
    raise ValueError(f"unknown coarse mode: {mode}")


def parse_turns(text: str) -> set[int]:
    out: set[int] = set()
    for part in str(text).split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            lo, hi = part.split("-", 1)
            out.update(range(int(lo), int(hi) + 1))
        else:
            out.add(int(part))
    return out


def collect_boards(pool: str, turns: set[int]) -> list[dict]:
    roots = [
        str(_REPO / "data" / "BgHelperDiag"),
        os.path.expandvars(r"%APPDATA%\HearthstoneDeckTracker\BgHelperDiag"),
    ]
    allowed = set(member_versions(pool))
    by_id: dict[str, dict] = {}
    games = discover_games(roots)
    print(f"indexing {len(games)} game dirs (pool {pool}, turns {sorted(turns)})", flush=True)
    for gid, gdir in sorted(games.items()):
        try:
            meta = load_meta(gdir)
        except Exception as ex:  # noqa: BLE001
            print(f"[skip] {gid}: meta {ex}", flush=True)
            continue
        info = meta.get("bobsBuddy") if isinstance(meta, dict) else None
        if not isinstance(info, dict):
            info = {}
        bb = info.get("fileVersion") or info.get("version")
        if str(bb or "") not in allowed or (isinstance(meta, dict) and meta.get("isBattlegroundsDuosMatch")):
            continue
        try:
            _meta, _records, combats = iter_game_combats(gdir)
        except Exception as ex:  # noqa: BLE001
            print(f"[skip] {gid}: {ex}", flush=True)
            continue
        for combat in combats:
            turn = combat.get("turn")
            if not isinstance(turn, int) or turn not in turns:
                continue
            if not isinstance(combat.get("input"), dict):
                continue
            player_board, _opp = board_from_input(combat["input"])
            if not player_board:
                continue
            bid = f"{gid}|t{turn}|Player"
            by_id[bid] = {
                "boardId": bid,
                "gameId": gid,
                "turn": turn,
                "input": combat["input"],
            }
    return [by_id[k] for k in sorted(by_id)]


def write_inputs(boards: list[dict], out_dir: Path) -> None:
    inputs = out_dir / "inputs"
    inputs.mkdir(parents=True, exist_ok=True)
    for board in boards:
        path = inputs / f"{board['gameId']}_t{board['turn']}.json"
        path.write_text(json.dumps(board["input"], ensure_ascii=False), encoding="utf-8")
        board["inputPath"] = str(path)


def run_jobs(jobs: list[dict], out_dir: Path, tag: str, iterations: int,
             threads: int | None = None, max_duration: int | None = None) -> list[dict]:
    if not EXE.is_file():
        raise FileNotFoundError(
            f"{EXE} not found. Build DummySim first (README.md), then rerun."
        )
    jobs_path = out_dir / f"{tag}-jobs.jsonl"
    log_path = out_dir / f"{tag}.jsonl"
    with jobs_path.open("w", encoding="utf-8") as handle:
        for job in jobs:
            handle.write(json.dumps(job, ensure_ascii=False) + "\n")
    cmd = [str(EXE), "--bb-dir", BB_DIR, "--batch", str(jobs_path), "--iterations", str(iterations)]
    if threads:
        cmd += ["--threads", str(threads)]
    if max_duration:
        cmd += ["--max-duration", str(max_duration)]
    rows: list[dict] = []
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
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        code = proc.wait()
    print(f"{tag}: jobs={len(jobs)} rows={len(rows)} exit={code}", flush=True)
    if code != 0:
        raise SystemExit(f"{tag} exe exited {code}")
    return rows


def merge_rows(rows: list[dict], points: dict[str, dict[int, Point]],
               iterations: int, errors: list[dict]) -> None:
    for row in rows:
        if not row.get("ok"):
            errors.append(row)
            continue
        bid = str(row["id"]).rsplit("|L", 1)[0]
        level = int(row["attack"])
        n = float(row.get("simulationCount") or iterations)
        points.setdefault(bid, {})[level] = Point(
            level,
            float(row["winRate"]) * n,
            float(row["tieRate"]) * n,
            float(row["lossRate"]) * n,
        )


def status_of(points: dict[int, Point]) -> str:
    if len(points) < 3:
        return "fit_failed"
    pts = [points[lv] for lv in sorted(points)]
    for i in range(len(pts) - 1):
        if pts[i].score >= 0.5 > pts[i + 1].score:
            return "interior"
    if pts[-1].score >= 0.5:
        return "above"
    if pts[0].score < 0.5:
        return "below"
    return "interior"


def extension_levels(points: dict[int, Point]) -> list[int]:
    """If even the top rung wins >=50%, extend by x2 and x4 (up to CAP)."""
    top = max(points)
    if points[top].score < 0.5 or top >= CAP_LEVEL:
        return []
    out = []
    for factor in (2, 4):
        level = min(top * factor, CAP_LEVEL)
        if level > top and level not in out:
            out.append(level)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--pool", default="1.85.0.0")
    ap.add_argument("--turns", default="6,8,10")
    ap.add_argument("--out", type=Path, default=_HERE / "out-adaptive")
    ap.add_argument("--coarse", choices=("ratio2", "ratio4"), default="ratio4")
    ap.add_argument("--iterations", type=int, default=500)
    ap.add_argument("--extra-rounds", type=int, default=2,
                    help="adaptive rounds after the coarse round (default 2)")
    ap.add_argument("--limit", type=int, default=0, help="only the first N boards (smoke)")
    ap.add_argument("--threads", type=int, default=None)
    ap.add_argument("--max-duration", type=int, default=None)
    ap.add_argument("--selftest", action="store_true", help="run estimator self-tests and exit")
    args = ap.parse_args()

    if args.selftest:
        return estimator_selftest()

    out_dir: Path = args.out.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    t0 = time.time()

    boards = collect_boards(args.pool, parse_turns(args.turns))
    if args.limit:
        boards = boards[: args.limit]
    if not boards:
        print("no boards found; check --pool/--turns and the diag roots")
        return 1
    write_inputs(boards, out_dir)
    (out_dir / "boards.json").write_text(
        json.dumps([{k: b[k] for k in ("boardId", "gameId", "turn")} for b in boards],
                   ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"boards={len(boards)}", flush=True)

    points: dict[str, dict[int, Point]] = defaultdict(dict)
    rounds: dict[str, int] = {b["boardId"]: 0 for b in boards}
    errors: list[dict] = []

    # ---- round 0: coarse ladder
    coarse = coarse_levels(args.coarse)
    jobs = []
    for board in boards:
        for level in coarse:
            jobs.append({"id": f"{board['boardId']}|L{level}", "inputPath": board["inputPath"],
                         "attack": level, "health": level, "count": 7})
    rows = run_jobs(jobs, out_dir, "round0", args.iterations, args.threads, args.max_duration)
    merge_rows(rows, points, args.iterations, errors)
    if not any(points.get(bid) for bid in rounds):
        raise SystemExit("round 0 produced no ok rows; check DummySim.exe and --bb-dir")
    for bid in rounds:
        rounds[bid] = 1 if points.get(bid) else 0

    # ---- adaptive rounds
    for r in range(args.extra_rounds):
        stage = 1 if r == 0 else 2
        jobs = []
        touched: set[str] = set()
        for board in boards:
            bid = board["boardId"]
            have = points.get(bid, {})
            if len(have) >= MAX_RUNGS:
                continue
            pts = [have[lv] for lv in sorted(have)]
            if not pts:
                continue
            status = status_of(have)
            if status == "above":
                new = extension_levels(have)
            elif status == "interior":
                existing = set(have)
                new = choose_levels(pts, n=4 if stage == 1 else 2, stage=stage,
                                    existing=existing, lo=1, hi=CAP_LEVEL)
            else:
                continue
            for level in new:
                if level in have or level < 1 or level > CAP_LEVEL:
                    continue
                jobs.append({"id": f"{bid}|L{level}", "inputPath": board["inputPath"],
                             "attack": level, "health": level, "count": 7})
                touched.add(bid)
        if not jobs:
            break
        rows = run_jobs(jobs, out_dir, f"round{r + 1}", args.iterations,
                        args.threads, args.max_duration)
        merge_rows(rows, points, args.iterations, errors)
        for bid in touched:
            rounds[bid] += 1

    # ---- final estimates
    curves = []
    for board in boards:
        bid = board["boardId"]
        have = points.get(bid, {})
        est = estimate(list(have.values()))
        status = status_of(have) if have else "fit_failed"
        entry = {
            "boardId": bid,
            "gameId": board["gameId"],
            "turn": board["turn"],
            "status": status,
            "censored": status != "interior",
            "rounds": rounds.get(bid, 0),
            **est,
        }
        curves.append(entry)
    (out_dir / "curves.json").write_text(json.dumps(curves, ensure_ascii=False, indent=2),
                                         encoding="utf-8")

    # ---- summary
    wall = time.time() - t0
    by_status = defaultdict(int)
    for row in curves:
        by_status[row["status"]] += 1
    ci_widths = []
    for row in curves:
        ci = row.get("ci")
        if ci and ci[0] > 0 and ci[1] > 0:
            ci_widths.append(math.log2(ci[1] / ci[0]))
    sims = [row["sims"] for row in curves if row["sims"]]
    rungs = [row["nPoints"] for row in curves if row["nPoints"]]
    print(f"boards={len(curves)} status={dict(by_status)}")
    print(f"median rungs/board={median(rungs)} median sims/board={median(sims)} "
          f"total sims={sum(sims)} wall={wall:.1f}s")
    med_ci = median(ci_widths)
    if med_ci is None:
        print("median CI width=n/a")
    else:
        print(f"median CI width={med_ci:.3f} log2 (x{2 ** med_ci:.3f})")
    print("by turn: n interior median_x50 median_ci_width")
    for turn in sorted({row["turn"] for row in curves}):
        group = [row for row in curves if row["turn"] == turn]
        interior = [row["x50"] for row in group if row["status"] == "interior" and row["x50"]]
        widths = []
        for row in group:
            ci = row.get("ci")
            if row["status"] == "interior" and ci and ci[0] > 0:
                widths.append(math.log2(ci[1] / ci[0]))
        med = median(interior)
        medw = median(widths)
        print(f"  t{turn:02d} n={len(group):3d} interior={len(interior):3d} "
              f"median={None if med is None else round(med, 2)} "
              f"ci_width={None if medw is None else round(medw, 3)}")
    if errors:
        print(f"errors={len(errors)} (first: {errors[0]})")

    summary = {
        "pool": args.pool,
        "turns": sorted(parse_turns(args.turns)),
        "coarse": args.coarse,
        "coarse_levels": coarse,
        "iterations": args.iterations,
        "extraRounds": args.extra_rounds,
        "boards": len(curves),
        "status": dict(by_status),
        "medianRungs": median(rungs),
        "medianSims": median(sims),
        "totalSims": sum(sims),
        "medianCiWidthLog2": median(ci_widths),
        "wallSec": round(wall, 1),
        "errors": len(errors),
    }
    (out_dir / "run.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2),
                                      encoding="utf-8")
    print(f"wrote {out_dir / 'curves.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
