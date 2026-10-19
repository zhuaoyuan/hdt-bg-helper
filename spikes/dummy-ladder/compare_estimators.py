# -*- coding: utf-8 -*-
"""Compare the model-based estimator (with adaptive sampling) against v1.

Reads the v1 curve file (two-rung interpolation over the fixed ladder) and the
new adaptive curve file (logistic location + CI), joins them by boardId, and
reports:

  * rank agreement between the two X50 estimates (Spearman);
  * median |log2 ratio| and its multiplicative equivalent;
  * median 95% CI width of the model estimate (in log2 and as a ratio);
  * simulation cost per board (adaptive vs v1 levels * iterations);
  * per-turn medians, so a turn-specific regression would be visible.

Usage:
    python spikes/dummy-ladder/compare_estimators.py \
        --adaptive spikes/dummy-ladder/out-adaptive/curves.json \
        --wide spikes/dummy-ladder/out-wide/curves.json

If ``out-wide/curves-model.json`` exists (from
``model_estimate.py --curves out-wide/curves.json``), an estimator-only
comparison (same rungs, model vs interpolation) is printed too.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from collections import defaultdict
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))

from model_estimate import median, spearman  # noqa: E402


def load(path: Path) -> dict[str, dict]:
    rows = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(rows, list):
        raise SystemExit(f"{path}: expected a JSON array of rows")
    return {row["boardId"]: row for row in rows if isinstance(row, dict) and row.get("boardId")}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--adaptive", type=Path, default=_HERE / "out-adaptive" / "curves.json")
    ap.add_argument("--wide", type=Path, default=_HERE / "out-wide" / "curves.json")
    ap.add_argument("--rescored", type=Path, default=_HERE / "out-wide" / "curves-model.json",
                    help="model_estimate.py --curves output (estimator-only comparison)")
    ap.add_argument("--iterations", type=int, default=500)
    ap.add_argument("--out", type=Path, default=_HERE / "out-adaptive" / "compare.json")
    args = ap.parse_args()

    for path in (args.adaptive, args.wide):
        if not path.is_file():
            print(f"missing {path}; run run_adaptive.py / score_curves.py first")
            return 2

    new = load(args.adaptive)
    old = load(args.wide)
    common = sorted(set(new) & set(old))
    pairs = []
    for bid in common:
        a, b = new[bid], old[bid]
        if not a.get("x50") or not b.get("x50"):
            continue
        pairs.append((bid, a, b))
    if len(pairs) < 3:
        print(f"only {len(pairs)} comparable boards")
        return 1

    xs = [math.log2(a["x50"]) for _bid, a, _b in pairs]
    ys = [math.log2(b["x50"]) for _bid, _a, b in pairs]
    rho = spearman(xs, ys)
    ratios = [abs(x - y) for x, y in zip(xs, ys)]
    widths = []
    for _bid, a, _b in pairs:
        ci = a.get("ci")
        if ci and ci[0] > 0 and ci[1] > 0:
            widths.append(math.log2(ci[1] / ci[0]))
    new_sims = [a.get("sims") or (len(a.get("levels") or []) * args.iterations) for _b, a, _o in pairs]
    old_sims = [len(o.get("levels") or []) * args.iterations for _b, _a, o in pairs]

    print(f"boards={len(pairs)}")
    print(f"spearman(model, interp)={None if rho is None else round(rho, 4)}")
    med_ratio = median(ratios)
    print(f"median |log2 ratio|={None if med_ratio is None else round(med_ratio, 4)}"
          f" (x{None if med_ratio is None else round(2 ** med_ratio, 3)})")
    med_width = median(widths)
    print(f"median CI width={None if med_width is None else round(med_width, 4)} log2"
          f" (x{None if med_width is None else round(2 ** med_width, 3)})")
    print(f"median sims/board: new={median(new_sims)} old={median(old_sims)}")
    if median(new_sims) and median(old_sims):
        print(f"cost ratio old/new={median(old_sims) / median(new_sims):.2f}x")

    per_turn = defaultdict(list)
    for _bid, a, b in pairs:
        per_turn[a["turn"]].append((math.log2(a["x50"]), math.log2(b["x50"])))
    print("by turn: n spearman med_model med_interp")
    for turn in sorted(per_turn):
        group = per_turn[turn]
        r = spearman([x for x, _ in group], [y for _, y in group])
        print(f"  t{turn:02d} n={len(group):3d} rho={None if r is None else round(r, 4)} "
              f"med_model={round(2 ** median([x for x, _ in group]), 2)} "
              f"med_interp={round(2 ** median([y for _, y in group]), 2)}")

    payload = {
        "boards": len(pairs),
        "spearmanModelVsInterp": rho,
        "medianAbsLog2Ratio": med_ratio,
        "medianCiWidthLog2": med_width,
        "medianNewSims": median(new_sims),
        "medianOldSims": median(old_sims),
        "perTurn": {
            str(turn): {
                "n": len(group),
                "spearman": spearman([x for x, _ in group], [y for _, y in group]),
            }
            for turn, group in per_turn.items()
        },
    }

    # Estimator-only comparison: same v1 rungs, model vs interpolation.
    if args.rescored.is_file():
        resc = load(args.rescored)
        rows = [resc[bid] for bid in sorted(set(resc) & set(old))
                if (resc[bid].get("model") or {}).get("x50") and resc[bid].get("x50")]
        if len(rows) >= 3:
            rx = [math.log2(r["model"]["x50"]) for r in rows]
            ry = [math.log2(r["x50"]) for r in rows]
            rho2 = spearman(rx, ry)
            med2 = median([abs(a - b) for a, b in zip(rx, ry)])
            widths2 = []
            for r in rows:
                ci = (r["model"] or {}).get("ci")
                if ci and ci[0] > 0 and ci[1] > 0:
                    widths2.append(math.log2(ci[1] / ci[0]))
            print(f"estimator-only (same v1 rungs): n={len(rows)} "
                  f"spearman(model, interp)={None if rho2 is None else round(rho2, 4)} "
                  f"median |log2 ratio|={None if med2 is None else round(med2, 4)} "
                  f"median CI width={None if median(widths2) is None else round(median(widths2), 4)}")
            payload["rescored"] = {
                "n": len(rows),
                "spearmanModelVsInterp": rho2,
                "medianAbsLog2Ratio": med2,
                "medianCiWidthLog2": median(widths2),
            }
        else:
            print(f"rescored file has only {len(rows)} comparable rows; skipped estimator-only check")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
