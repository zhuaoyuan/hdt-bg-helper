# -*- coding: utf-8 -*-
"""Independent-ish recomputation of the X50 trend numbers.

Reads only out/boards.csv + out/analysis.json, recomputes the primary slopes with a
different numerical path (within-turn demeaning = Frisch-Waugh instead of a dummy
design matrix), a fresh bootstrap seed, and the per-turn Spearman values. Prints a
diff report; exits non-zero if any check exceeds tolerance.

    python spikes/x50-trend/verify.py
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "spikes/x50-trend/out"


def load_boards(out: Path) -> dict[str, list[dict]]:
    by_side: dict[str, list[dict]] = {"me": [], "opp": []}
    with (out / "boards.csv").open(encoding="utf-8") as f:
        header = f.readline().rstrip("\n").split(",")
        for line in f:
            p = line.rstrip("\n").split(",")
            r = dict(zip(header, p))
            side = r["side"]
            if side not in by_side:
                continue
            try:
                turn = int(r["turn"])
                lx = float(r["log2x50"])
            except ValueError:
                continue
            if int(r["interior"]) != 1 or not (5 <= turn <= 12):
                continue
            by_side[side].append({"gameId": r["gameId"], "seq": float(r["seq"]),
                                  "turn": turn, "y": lx})
    return by_side


def demean_slope(rows: list[dict]) -> float:
    """Within-turn demeaning then OLS through the origin: beta = sum(x~y~)/sum(x~^2)."""
    turns = sorted({r["turn"] for r in rows})
    y = np.array([r["y"] for r in rows])
    x = np.array([r["seq"] for r in rows])
    yres = np.empty_like(y)
    xres = np.empty_like(x)
    for t in turns:
        m = np.array([r["turn"] == t for r in rows])
        yres[m] = y[m] - y[m].mean()
        xres[m] = x[m] - x[m].mean()
    return float((xres * yres).sum() / (xres * xres).sum())


def pct(beta: float) -> float:
    return (2 ** (10 * beta) - 1) * 100


def bootstrap(rows: list[dict], B: int = 2000, seed: int = 20261020) -> np.ndarray:
    rng = np.random.default_rng(seed)
    by_game: dict[str, list[dict]] = {}
    for r in rows:
        by_game.setdefault(r["gameId"], []).append(r)
    games = sorted(by_game)
    out = np.empty(B)
    for b in range(B):
        pick = rng.choice(len(games), size=len(games), replace=True)
        sample: list[dict] = []
        for i in pick:
            sample.extend(by_game[games[i]])
        out[b] = demean_slope(sample)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", type=Path, default=OUT)
    args = ap.parse_args()
    analysis = json.loads((args.out / "analysis.json").read_text(encoding="utf-8"))
    boards = load_boards(args.out)
    from scipy.stats import spearmanr

    problems: list[str] = []

    print("== game counts ==")
    all_games = {r["gameId"] for rows in boards.values() for r in rows}
    n_manifest = analysis["sample"]["games"]
    print(f"games in boards.csv={len(all_games)} analysis.json={n_manifest}")
    if len(all_games) != n_manifest:
        problems.append("game count mismatch")

    for side in ("me", "opp"):
        rows = boards[side]
        if not rows:
            print(f"[{side}] no boards (opponent-side data missing)")
            continue
        claimed = analysis["trends"].get(side)
        if not claimed:
            problems.append(f"{side}: no trend in analysis.json")
            continue
        b = demean_slope(rows)
        dist = bootstrap(rows)
        lo, hi = np.percentile(dist, [2.5, 97.5])
        p = float(min(1.0, 2 * min((dist >= 0).mean(), (dist <= 0).mean())))
        print(f"\n== {side} ==")
        print(f"n={len(rows)} games={len({r['gameId'] for r in rows})}")
        print(f"slope  verify={pct(b):+.3f}%/10局  analysis={claimed['pctPer10Games']:+.3f}%")
        print(f"CI     verify=[{pct(lo):+.3f}, {pct(hi):+.3f}]  "
              f"analysis=[{claimed['ci95PctPer10Games'][0]:+.3f}, "
              f"{claimed['ci95PctPer10Games'][1]:+.3f}]")
        print(f"p      verify={p:.4f}  analysis={claimed['pBootstrap']:.4f}")
        if abs(pct(b) - claimed["pctPer10Games"]) > 0.05:
            problems.append(f"{side}: slope differs by >0.05pp/10games")
        # CI endpoints should agree up to Monte-Carlo noise from the other seed;
        # the MC standard error of a 2.5% quantile is ~0.15pp here.
        ci_lo, ci_hi = claimed["ci95PctPer10Games"]
        if abs(pct(lo) - ci_lo) > 0.5:
            problems.append(f"{side}: low CI endpoint differs by >0.5pp")
        if abs(pct(hi) - ci_hi) > 0.5:
            problems.append(f"{side}: high CI endpoint differs by >0.5pp")

        # per-turn rho spot check
        for t in (5, 8, 12):
            sub = sorted([r for r in rows if r["turn"] == t], key=lambda r: r["seq"])
            if len(sub) < 10:
                continue
            rho, _ = spearmanr([r["seq"] for r in sub], [r["y"] for r in sub])
            claimed_t = next((x for x in analysis["perTurn"][side] if x["turn"] == t), None)
            if claimed_t is None:
                continue
            print(f"  t{t}: rho verify={rho:+.4f} analysis={claimed_t['rho']:+.4f}")
            if abs(rho - claimed_t["rho"]) > 1e-6:
                problems.append(f"{side} t{t} rho mismatch")

    # MA spot check: last point of me t8 series
    t8 = analysis["series"].get("me", {}).get("8")
    if t8:
        rows = sorted([r for r in boards["me"] if r["turn"] == 8], key=lambda r: r["seq"])
        last10 = [r["y"] for r in rows[-10:]]
        ma = sum(last10) / len(last10)
        print(f"\n== MA check: me t8 last point ==")
        print(f"verify={ma:.6f} analysis={t8['ma10'][-1]:.6f}")
        if abs(ma - t8["ma10"][-1]) > 1e-9:
            problems.append("MA10 mismatch")

    print("\n== diffs ==")
    print(json.dumps({"problems": problems}, ensure_ascii=False))
    return 0 if not problems else 1


if __name__ == "__main__":
    raise SystemExit(main())
