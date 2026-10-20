# -*- coding: utf-8 -*-
"""Validate the opponent-side X50 (``run_adaptive.py --side opponent``).

A. Player-side regression
   Re-measure 6 existing t6 boards with ``measureSide: "player"`` on a fixed
   ladder and compare with the v2 result in ``out-adaptive-all/curves.json``.
   Checks |log2 ratio|, CI overlap and status.

B. Side-symmetry ground truth
   Take the same 6 Inputs, swap the top-level ``Player`` / ``Opponent`` objects,
   and measure with ``measureSide: "opponent"``. The dummy now faces the
   *original Player board P*, so the estimate should reproduce P's player-side
   X50 (P is just parked on the Opponent side). Two flag variants:
     (i)  keep the dumped flags (moved minions still say ControlledByPlayer=true)
     (ii) recursively set ControlledByPlayer=false on everything moved into the
          Opponent slot (minions, Hand/HeroPowers items, _enchantments, ...),
          which is what a real opponent-side dump looks like.
   The fixed ladder is deliberately dense at the low end (t6 boards sit at
   X50 ~3..16) and reaches 8192; every configuration uses the same rungs, so the
   comparison is design-controlled. The goal is agreement within ~5-10%, not a
   replica of the adaptive collection.

C. Scale sanity
   Opponent vs player per-turn medians (same 81 games), and Spearman of log2 X50
   against the raw board stats (sum of atk+hp, minion count).

Usage:
    python spikes/dummy-ladder/verify_side_opp.py                 # run + write
    python spikes/dummy-ladder/verify_side_opp.py --reuse         # re-analyse only
"""
from __future__ import annotations

import argparse
import copy
import datetime
import json
import math
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_REPO = _HERE.parents[1]
sys.path.insert(0, str(_HERE))
sys.path.insert(0, str(_REPO / "tools"))

from model_estimate import Point, estimate, median, spearman  # noqa: E402

from standard_layer.combat import board_from_input  # noqa: E402

import run_adaptive as ra  # noqa: E402

GT_CURVES = _HERE / "out-adaptive-all" / "curves.json"
GT_INPUTS = _HERE / "out-adaptive-all" / "inputs"

# Dense at the low end (t6 X50 is ~3..16), geometric tail up to 8192.
LADDER = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 12, 14, 16, 20, 24, 32, 40, 48,
          64, 96, 128, 256, 512, 1024, 2048, 4096, 8192]

CONFIGS = ("player_orig", "swap_keep", "swap_false")
PAIR_MODE = {"player_orig": "player", "swap_keep": "opponent", "swap_false": "opponent"}


# ---------------------------------------------------------------------------
# inputs


def load_gt() -> list[dict]:
    rows = json.loads(GT_CURVES.read_text(encoding="utf-8"))
    return [r for r in rows if r.get("boardId", "").endswith("|Player")]


def pick_boards(gt: list[dict], games: set[str], n: int) -> list[dict]:
    """Quantile-spread pick across t6 interior boards of the 1.88.6.0 games."""
    cand = [r for r in gt
            if r["turn"] == 6 and r["status"] == "interior" and r.get("x50")
            and r["gameId"] in games
            and (GT_INPUTS / f"{r['gameId']}_t6.json").is_file()]
    cand.sort(key=lambda r: (r["x50"], r["boardId"]))
    if not cand:
        raise SystemExit("no candidate t6 boards with a saved Input")
    picks: list[dict] = []
    for i in range(n):
        idx = round(i * (len(cand) - 1) / max(1, n - 1))
        board = cand[idx]
        if board["boardId"] not in {p["boardId"] for p in picks}:
            picks.append(board)
    return picks


def swap_sides(inp: dict) -> dict:
    """Swap the top-level Player/Opponent objects, leave everything else alone."""
    out = copy.deepcopy(inp)
    out["Player"], out["Opponent"] = out["Opponent"], out["Player"]
    return out


def strip_controlled_by_player(node, count: list[int]) -> None:
    """Recursively force ControlledByPlayer=false inside one side's subtree."""
    if isinstance(node, dict):
        if node.get("ControlledByPlayer") is True:
            node["ControlledByPlayer"] = False
            count[0] += 1
        for value in node.values():
            strip_controlled_by_player(value, count)
    elif isinstance(node, list):
        for value in node:
            strip_controlled_by_player(value, count)


# ---------------------------------------------------------------------------
# batch


def build_inputs(boards: list[dict], verify_dir: Path) -> dict[str, dict[str, str]]:
    """Write the swapped variants; return {gid: {config: inputPath}}."""
    inputs = verify_dir / "inputs"
    inputs.mkdir(parents=True, exist_ok=True)
    paths: dict[str, dict[str, str]] = {}
    for board in boards:
        gid = board["gameId"]
        src = GT_INPUTS / f"{gid}_t6.json"
        orig = json.loads(src.read_text(encoding="utf-8"))
        entry = {"player_orig": str(src), "original": str(src)}

        keep = swap_sides(orig)
        p_keep = inputs / f"{gid}_t6_swap_keep.json"
        p_keep.write_text(json.dumps(keep, ensure_ascii=False), encoding="utf-8")
        entry["swap_keep"] = str(p_keep)

        false = copy.deepcopy(keep)
        flips = [0]
        strip_controlled_by_player(false["Opponent"], flips)
        p_false = inputs / f"{gid}_t6_swap_false.json"
        p_false.write_text(json.dumps(false, ensure_ascii=False), encoding="utf-8")
        entry["swap_false"] = str(p_false)
        entry["flagFlips"] = flips[0]
        paths[gid] = entry
    return paths


def run_verify(paths: dict[str, dict[str, str]], verify_dir: Path,
               iterations: int, reuse: bool) -> list[dict]:
    log = verify_dir / "verify.jsonl"
    if reuse and log.is_file():
        print(f"reuse {log}", flush=True)
        rows = []
        for line in log.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                rows.append(json.loads(line))
        return rows
    jobs = []
    for gid, entry in sorted(paths.items()):
        for cfg in CONFIGS:
            for level in LADDER:
                jobs.append({
                    "id": f"{cfg}|{gid}|t6|L{level}",
                    "inputPath": entry[cfg],
                    "attack": level,
                    "health": level,
                    "count": 7,
                    "measureSide": PAIR_MODE[cfg],
                })
    return ra.run_jobs(jobs, verify_dir, "verify", iterations)


def points_by_config(rows: list[dict], iterations: int) -> dict[str, dict[str, dict]]:
    """{(cfg, gid): {level: Point}}, flipping win/loss for opponent mode."""
    out: dict[str, dict[str, dict]] = {}
    for row in rows:
        if not row.get("ok"):
            continue
        cfg, gid, turn_part, level_part = str(row["id"]).split("|")
        n = float(row.get("simulationCount") or iterations)
        wins = float(row["winRate"]) * n
        ties = float(row["tieRate"]) * n
        losses = float(row["lossRate"]) * n
        if PAIR_MODE[cfg] == "opponent":
            # DummySim reports the dummy side (Input.Player); flip to the real
            # board's perspective so score decreases in the dummy level.
            wins, losses = losses, wins
        out.setdefault(cfg, {}).setdefault(gid, {})[int(level_part[1:])] = Point(
            int(level_part[1:]), wins, ties, losses)
    return out


def compare(est: dict, ref: dict) -> dict:
    """Agreement between one estimate and a reference estimate/curve row."""
    res: dict = {"x50": est.get("x50"), "ci": est.get("ci")}
    x50, rx = est.get("x50"), ref.get("x50")
    if x50 and rx:
        lr = math.log2(x50 / rx)
        res["log2Ratio"] = round(lr, 4)
        res["pctDiff"] = round((2.0 ** abs(lr) - 1.0) * 100.0, 2)
    ci, rci = est.get("ci"), ref.get("ci")
    if ci and rci:
        res["ciOverlap"] = bool(ci[0] <= rci[1] and rci[0] <= ci[1])
    return res


# ---------------------------------------------------------------------------
# C. scale sanity


def board_stats(inp: dict, side_index: int) -> tuple[int, int]:
    board = board_from_input(inp)[side_index]
    total = 0
    for m in board:
        total += int(m.get("atk") or 0) + int(m.get("health") or 0)
    return len(board), total


def turn_table(rows: list[dict]) -> dict[int, dict]:
    table: dict[int, dict] = {}
    for turn in sorted({r["turn"] for r in rows}):
        group = [r for r in rows if r["turn"] == turn]
        interior = [r["x50"] for r in group
                    if r["status"] == "interior" and r.get("x50")]
        table[turn] = {"n": len(group), "interior": len(interior),
                       "medianX50": None if not interior else round(median(interior), 2)}
    return table


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", type=Path, default=_HERE / "out-opp-188")
    ap.add_argument("--verify-dir", type=Path, default=None)
    ap.add_argument("--boards", type=int, default=6)
    ap.add_argument("--iterations", type=int, default=500)
    ap.add_argument("--reuse", action="store_true", help="reuse verify/verify.jsonl")
    args = ap.parse_args()

    out_dir: Path = args.out.resolve()
    verify_dir: Path = (args.verify_dir or (out_dir / "verify")).resolve()
    verify_dir.mkdir(parents=True, exist_ok=True)

    run_boards = json.loads((out_dir / "boards.json").read_text(encoding="utf-8"))
    games = {b["gameId"] for b in run_boards}
    opp_curves = json.loads((out_dir / "curves.json").read_text(encoding="utf-8"))
    gt = load_gt()
    boards = pick_boards(gt, games, args.boards)
    print("validation boards:")
    for board in boards:
        print(f"  {board['boardId']} x50={board['x50']} ci={board['ci']}")

    # ---- run the fixed-ladder batch
    paths = build_inputs(boards, verify_dir)
    rows = run_verify(paths, verify_dir, args.iterations, args.reuse)
    pts = points_by_config(rows, args.iterations)
    errors = [r for r in rows if not r.get("ok")]
    warnings = sum(int(r.get("warnings") or 0) for r in rows if r.get("ok"))
    print(f"rows={len(rows)} errors={len(errors)} hydration_warnings={warnings}")

    # ---- A + B
    per_board = []
    a_stats, b_stats = [], {cfg: [] for cfg in ("swap_keep", "swap_false")}
    for board in boards:
        gid = board["gameId"]
        row: dict = {
            "boardId": board["boardId"],
            "gameId": gid,
            "groundTruth": {"x50": board["x50"], "ci": board["ci"],
                            "status": board["status"], "levels": board["levels"]},
            "flagFlips": paths[gid]["flagFlips"],
        }
        estimates: dict[str, dict] = {}
        for cfg in CONFIGS:
            have = pts.get(cfg, {}).get(gid, {})
            est = estimate(list(have.values())) if have else {}
            status = ra.status_of(have) if have else "fit_failed"
            estimates[cfg] = est
            row[cfg] = {
                "status": status,
                "x50": est.get("x50"),
                "ci": est.get("ci"),
                "seLog2": est.get("seLog2"),
                "nPoints": est.get("nPoints"),
                "monotone": est.get("monotone"),
                "levels": est.get("levels"),
                "scores": est.get("scores"),
            }
        # A: player-side re-measure vs the adaptive v2 ground truth
        a = compare(estimates["player_orig"], board)
        a["statusMatch"] = row["player_orig"]["status"] == board["status"]
        row["A"] = a
        a_stats.append(a)
        # B: swapped board measured on the Opponent side vs the same board
        # measured on the Player side (fixed ladder = design-controlled), and
        # vs the adaptive v2 ground truth.
        for cfg in ("swap_keep", "swap_false"):
            b = compare(estimates[cfg], estimates["player_orig"])
            b["vsGroundTruth"] = compare(estimates[cfg], board)
            b["statusMatch"] = row[cfg]["status"] == row["player_orig"]["status"]
            row[{"swap_keep": "B_keep", "swap_false": "B_false"}[cfg]] = b
            b_stats[cfg].append(b)
        per_board.append(row)

    def agg(items: list[dict]) -> dict:
        ratios = [abs(i["log2Ratio"]) for i in items if "log2Ratio" in i]
        overlaps = [i["ciOverlap"] for i in items if "ciOverlap" in i]
        return {
            "n": len(items),
            "medianLog2Ratio": None if not ratios else round(median(ratios), 4),
            "medianPctDiff": None if not ratios else round((2.0 ** median(ratios) - 1) * 100, 2),
            "maxLog2Ratio": None if not ratios else round(max(ratios), 4),
            "maxPctDiff": None if not ratios else round((2.0 ** max(ratios) - 1) * 100, 2),
            "within5Pct": sum(1 for r in ratios if r <= math.log2(1.05)),
            "within10Pct": sum(1 for r in ratios if r <= math.log2(1.10)),
            "ciOverlap": f"{sum(overlaps)}/{len(overlaps)}",
            "statusMatch": sum(1 for i in items if i.get("statusMatch")),
        }

    a_summary = agg(a_stats)
    b_summary = {cfg: agg(items) for cfg, items in b_stats.items()}

    # ---- C. scale sanity
    own_rows = [r for r in gt if r["gameId"] in games]
    turn_opp = turn_table(opp_curves)
    turn_own = turn_table(own_rows)

    xs_opp, sum_opp, cnt_opp = [], [], []
    xs_own, sum_own, cnt_own = [], [], []
    for row in opp_curves:
        if row["status"] != "interior" or not row.get("x50"):
            continue
        path = out_dir / "inputs" / f"{row['gameId']}_t{row['turn']}.json"
        if not path.is_file():
            continue
        inp = json.loads(path.read_text(encoding="utf-8"))
        n_min, total = board_stats(inp, 1)
        xs_opp.append(math.log2(row["x50"]))
        sum_opp.append(total)
        cnt_opp.append(n_min)
    for row in own_rows:
        if row["status"] != "interior" or not row.get("x50"):
            continue
        path = GT_INPUTS / f"{row['gameId']}_t{row['turn']}.json"
        if not path.is_file():
            continue
        inp = json.loads(path.read_text(encoding="utf-8"))
        n_min, total = board_stats(inp, 0)
        xs_own.append(math.log2(row["x50"]))
        sum_own.append(total)
        cnt_own.append(n_min)

    per_turn = {}
    for turn in sorted(set(turn_opp) | set(turn_own)):
        o = turn_opp.get(turn, {})
        w = turn_own.get(turn, {})
        mo, mw = o.get("medianX50"), w.get("medianX50")
        per_turn[turn] = {
            "opponent": o,
            "player": w,
            "medianRatio": None if not (mo and mw) else round(mo / mw, 3),
            "medianLog2Ratio": None if not (mo and mw) else round(math.log2(mo / mw), 3),
        }

    c_summary = {
        "opponent": {
            "nInterior": len(xs_opp),
            "spearmanLog2X50VsSumStats": round(spearman(xs_opp, sum_opp), 4),
            "spearmanLog2X50VsMinionCount": round(spearman(xs_opp, cnt_opp), 4),
        },
        "player": {
            "nInterior": len(xs_own),
            "spearmanLog2X50VsSumStats": round(spearman(xs_own, sum_own), 4),
            "spearmanLog2X50VsMinionCount": round(spearman(xs_own, cnt_own), 4),
        },
        "perTurn": per_turn,
    }

    # ---- write
    result = {
        "generated": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
        "outDir": str(out_dir),
        "ladder": LADDER,
        "iterations": args.iterations,
        "testBoards": [b["boardId"] for b in boards],
        "batch": {"rows": len(rows), "errors": len(errors),
                  "hydrationWarnings": warnings},
        "A_playerRegression": {"summary": a_summary, "perBoard": a_stats},
        "B_sideSymmetry": {"summary": b_summary,
                           "note": "swap_keep/swap_false vs player_orig (same fixed ladder); "
                                   "vsGroundTruth is the adaptive v2 value",
                           "perBoard": {row["boardId"]: {
                               "swap_keep": row["B_keep"],
                               "swap_false": row["B_false"],
                               "player_orig_x50": row["player_orig"]["x50"],
                               "groundTruth_x50": row["groundTruth"]["x50"],
                               "flagFlips": row["flagFlips"],
                           } for row in per_board}},
        "C_scale": c_summary,
        "boards": per_board,
        "errorRows": errors[:20],
    }
    target = out_dir / "validation.json"
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    print("\nA. player-side regression (fixed ladder vs out-adaptive-all curves.json)")
    print(f"   {a_summary}")
    print("B. side symmetry (swapped board on Opponent side vs Player side)")
    for cfg, summary in b_summary.items():
        print(f"   {cfg:11s} {summary}")
    print("C. scale: opponent vs player median X50 by turn")
    print("   turn  n_opp interior median_opp | n_own interior median_own | ratio")
    for turn, row in per_turn.items():
        o, w = row["opponent"], row["player"]
        print(f"   t{turn:02d}  {o.get('n', 0):5d} {o.get('interior', 0):8d} "
              f"{o.get('medianX50')!s:>10s} | {w.get('n', 0):5d} {w.get('interior', 0):8d} "
              f"{w.get('medianX50')!s:>10s} | {row.get('medianRatio')}")
    print(f"   spearman(opp): {c_summary['opponent']}")
    print(f"   spearman(own): {c_summary['player']}")
    print(f"wrote {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
