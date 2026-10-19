# -*- coding: utf-8 -*-
"""Cluster bootstrap (by game) for the X50-vs-mainline outcome comparison.

Metrics (all on the same board set as score_model_outcomes.py):

  * AUC of the turn-adjusted log2(X50) for decisive combats (win vs loss);
  * Spearman with the actual combat score (win=1, tie=0.5, loss=0);
  * the same for the mainline percentile;
  * paired differences on boards that have both X50 and a percentile.

Confidence intervals are percentile intervals from a **cluster bootstrap by
gameId** (boards in one game are correlated; resampling boards independently
would be too optimistic). The turn adjustment is recomputed in every replicate
from the resampled boards, with a fallback to the full-sample median when a
turn is missing.

Usage:
    python spikes/dummy-ladder/bootstrap_outcomes.py --bootstrap 5000
"""
from __future__ import annotations

import argparse
import json
import math
import random
import sys
from collections import defaultdict
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_REPO = _HERE.parents[1]
sys.path.insert(0, str(_HERE))

from model_estimate import median, spearman  # noqa: E402

TURNS = _REPO / "data" / "standard" / "turns.jsonl"
STRENGTH = _REPO / "data" / "strength" / "1.85.0.0" / "strength.jsonl"


def load_jsonl(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def auc(scores, labels):
    pos = [s for s, y in zip(scores, labels) if y == 1]
    neg = [s for s, y in zip(scores, labels) if y == 0]
    if not pos or not neg:
        return None
    wins = 0.0
    for p in pos:
        for q in neg:
            if p > q:
                wins += 1.0
            elif p == q:
                wins += 0.5
    return wins / (len(pos) * len(neg))


def label_of(row: dict):
    result = row.get("result")
    return 1.0 if result == "win" else 0.0 if result == "loss" else 0.5 if result == "tie" else None


def centre_from_values(values: dict[str, float], turn_of: dict[str, int]) -> dict[int, float]:
    by_turn: dict[int, list[float]] = defaultdict(list)
    for bid, value in values.items():
        turn = turn_of.get(bid)
        if turn is not None:
            by_turn[turn].append(value)
    return {turn: median(vs) for turn, vs in by_turn.items() if vs}


def _shifted(records: list[dict], key: str, centre: dict[int, float]):
    out = []
    for r in records:
        value, label = r.get(key), r.get("label")
        if value is None or label is None:
            continue
        base = centre.get(r["turn"])
        if base is None:
            continue
        out.append((value - base, label))
    return out


def _auc_rho(pairs):
    dec = [(v, y) for v, y in pairs if y in (0.0, 1.0)]
    a = auc([v for v, _ in dec], [y for _, y in dec]) if dec else None
    rho = spearman([v for v, _ in pairs], [y for _, y in pairs]) if len(pairs) >= 3 else None
    return a, rho


def metrics(records: list[dict], model_centre: dict[int, float],
            interp_centre: dict[int, float], v1_centre: dict[int, float]) -> dict:
    """One replicate; records may contain duplicated clusters, on purpose."""
    model_a = _shifted(records, "model", model_centre)
    interp_a = _shifted(records, "interp", interp_centre)
    v1_a = _shifted(records, "v1", v1_centre)
    q_pairs = [(r["q"], r["label"]) for r in records
               if r.get("q") is not None and r.get("label") is not None]

    auc_model, rho_model = _auc_rho(model_a)
    auc_interp, rho_interp = _auc_rho(interp_a)
    auc_v1, rho_v1 = _auc_rho(v1_a)
    auc_q, rho_q = _auc_rho(q_pairs)

    both = []
    for r in records:
        if r.get("model") is None or r.get("q") is None or r.get("label") is None:
            continue
        base = model_centre.get(r["turn"])
        if base is None:
            continue
        both.append((r["model"] - base, r["q"], r["label"]))
    dec_both = [(m, q, y) for m, q, y in both if y in (0.0, 1.0)]
    auc_model_ov = (auc([m for m, _, _ in dec_both], [y for _, _, y in dec_both])
                    if dec_both else None)
    auc_q_ov = (auc([q for _, q, _ in dec_both], [y for _, _, y in dec_both])
                if dec_both else None)
    rho_model_ov = (spearman([m for m, _, _ in both], [y for _, _, y in both])
                    if len(both) >= 3 else None)
    rho_q_ov = (spearman([q for _, q, _ in both], [y for _, _, y in both])
                if len(both) >= 3 else None)

    both_v1 = []
    for r in records:
        if r.get("model") is None or r.get("v1") is None or r.get("label") is None:
            continue
        cm = model_centre.get(r["turn"])
        cv = v1_centre.get(r["turn"])
        if cm is None or cv is None:
            continue
        both_v1.append((r["model"] - cm, r["v1"] - cv, r["label"]))
    dec_v1 = [(m, v, y) for m, v, y in both_v1 if y in (0.0, 1.0)]
    auc_v1_ov = (auc([v for _, v, _ in dec_v1], [y for _, _, y in dec_v1])
                 if dec_v1 else None)

    return {
        "aucModel": auc_model,
        "aucInterp": auc_interp,
        "aucV1": auc_v1,
        "aucPercentile": auc_q,
        "rhoModel": rho_model,
        "rhoInterp": rho_interp,
        "rhoV1": rho_v1,
        "rhoPercentile": rho_q,
        "deltaAucModelVsPercentile": (None if auc_model_ov is None or auc_q_ov is None
                                     else auc_model_ov - auc_q_ov),
        "deltaRhoModelVsPercentile": (None if rho_model_ov is None or rho_q_ov is None
                                     else rho_model_ov - rho_q_ov),
        "deltaAucModelVsV1": (None if auc_model_ov is None or auc_v1_ov is None
                              else auc_model_ov - auc_v1_ov),
        "nDecisive": len(dec_both),
    }


def interval(values, lo=2.5, hi=97.5):
    xs = sorted(v for v in values if v is not None)
    if not xs:
        return None
    def pct(p):
        k = (len(xs) - 1) * p / 100.0
        f = int(math.floor(k))
        c = min(f + 1, len(xs) - 1)
        return xs[f] + (xs[c] - xs[f]) * (k - f)
    return (pct(lo), pct(hi))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--curves", type=Path, default=_HERE / "out-adaptive" / "curves.json")
    ap.add_argument("--v1", type=Path, default=_HERE / "out-wide" / "curves.json")
    ap.add_argument("--bootstrap", type=int, default=5000)
    ap.add_argument("--seed", type=int, default=20261019)
    args = ap.parse_args()

    if not args.curves.is_file():
        print(f"missing {args.curves}; run run_adaptive.py first")
        return 2
    rows = json.loads(args.curves.read_text(encoding="utf-8"))
    turns = {(r.get("gameId"), r.get("turn")): r for r in load_jsonl(TURNS)}
    strength = {r["boardId"]: r for r in load_jsonl(STRENGTH)}
    v1_rows = json.loads(args.v1.read_text(encoding="utf-8")) if args.v1.is_file() else []
    v1 = {r["boardId"]: math.log2(r["x50"]) for r in v1_rows if r.get("x50")}
    v1_turn = {r["boardId"]: int(r["turn"]) for r in v1_rows if r.get("turn") is not None}

    # Turn centres are estimated on *all* boards (not only labelled ones), so the
    # point estimates match score_model_outcomes.py; the bootstrap keeps them
    # fixed and only resamples games/labels.
    turn_of_all = {r["boardId"]: int(r["turn"]) for r in rows if r.get("boardId")}
    all_model = {r["boardId"]: math.log2(r["x50"]) for r in rows
                 if r.get("x50") and not r.get("censored")}
    all_interp = {r["boardId"]: math.log2(r["x50Interp"]) for r in rows if r.get("x50Interp")}
    model_centre = centre_from_values(all_model, turn_of_all)
    interp_centre = centre_from_values(all_interp, turn_of_all)
    v1_centre = centre_from_values(v1, v1_turn)

    records = []
    for row in rows:
        bid = row.get("boardId")
        tr = turns.get((row.get("gameId"), row.get("turn")))
        if not bid or tr is None:
            continue
        label = label_of(tr)
        if label is None:
            continue
        records.append({
            "boardId": bid,
            "gameId": row["gameId"],
            "turn": int(row["turn"]),
            "label": label,
            "model": (math.log2(row["x50"])
                      if row.get("x50") and not row.get("censored") else None),
            "interp": math.log2(row["x50Interp"]) if row.get("x50Interp") else None,
            "v1": v1.get(bid),
            "q": (float(strength[bid]["percentile"])
                  if bid in strength and strength[bid].get("percentile") is not None else None),
        })
    # Deduplicate the point-estimate sample by boardId (bootstrap adds duplicates).
    unique = list({r["boardId"]: r for r in records}.values())
    point = metrics(unique, model_centre, interp_centre, v1_centre)

    games = sorted({r["gameId"] for r in unique})
    by_game = defaultdict(list)
    for r in unique:
        by_game[r["gameId"]].append(r)
    rng = random.Random(args.seed)
    boot = defaultdict(list)
    for _ in range(args.bootstrap):
        sample = []
        for _ in range(len(games)):
            sample.extend(by_game[rng.choice(games)])
        m = metrics(sample, model_centre, interp_centre, v1_centre)
        for key, value in m.items():
            boot[key].append(value)

    print(f"boards={len(unique)} games={len(games)} "
          f"decisive={sum(1 for r in unique if r['label'] in (0.0, 1.0))} "
          f"bootstrap={args.bootstrap}")
    summary = {}
    for key in ("aucModel", "aucInterp", "aucV1", "aucPercentile",
                "rhoModel", "rhoInterp", "rhoV1", "rhoPercentile",
                "deltaAucModelVsPercentile", "deltaRhoModelVsPercentile", "deltaAucModelVsV1"):
        lo_hi = interval(boot[key])
        summary[key] = {
            "point": None if point[key] is None else round(point[key], 4),
            "lo": None if lo_hi is None else round(lo_hi[0], 4),
            "hi": None if lo_hi is None else round(lo_hi[1], 4),
        }
        print(f"{key:>28}: {summary[key]['point']} "
              f"[{summary[key]['lo']}, {summary[key]['hi']}]")
    neg = sum(1 for v in boot["deltaAucModelVsPercentile"] if v is not None and v < 0)
    total = sum(1 for v in boot["deltaAucModelVsPercentile"] if v is not None)
    print(f"P(deltaAUC(model - percentile) < 0) = {neg}/{total} = {neg / total:.3f}")
    summary["pDeltaAucLt0"] = neg / total if total else None
    out_path = args.curves.with_name("bootstrap.json")
    out_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
