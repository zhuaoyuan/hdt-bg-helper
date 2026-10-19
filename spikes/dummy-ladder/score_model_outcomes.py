# -*- coding: utf-8 -*-
"""Score X50 variants against the recorded combat outcomes.

Reads the adaptive curve file (model estimate), the v1 curve file
(interpolation) and, when available, `strength.jsonl` (mainline percentile);
joins to `turns.jsonl`; and reports:

  * AUC of the turn-adjusted log2(X50) for decisive combats (win vs loss);
  * Spearman of the turn-adjusted log2(X50) with the actual combat score
    (win=1, tie=0.5, loss=0);
  * the same on the overlap with the mainline percentile, so the comparison is
    on one sample.

This is a descriptive check, not a significance test: no cluster bootstrap yet.
Requires `data/standard/turns.jsonl`; boards from games newer than the standard
layer are silently dropped (they have no outcome label), which is reported as
the n difference.

Usage:
    python spikes/dummy-ladder/score_model_outcomes.py
    python spikes/dummy-ladder/score_model_outcomes.py --curves out-adaptive/curves.json
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_REPO = _HERE.parents[1]
sys.path.insert(0, str(_HERE))

from model_estimate import median, spearman  # noqa: E402

TURNS = _REPO / "data" / "standard" / "turns.jsonl"
STRENGTH = _REPO / "data" / "strength" / "1.85.0.0" / "strength.jsonl"


def load_jsonl(path: Path) -> list[dict]:
    rows = []
    if not path.is_file():
        return rows
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def auc(scores, labels) -> float | None:
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


def label_of(row: dict) -> float | None:
    result = row.get("result")
    if result == "win":
        return 1.0
    if result == "loss":
        return 0.0
    if result == "tie":
        return 0.5
    return None


def summarise(name: str, values: dict[str, float], labels: dict[str, float],
              turns_by_board: dict[str, int]) -> dict:
    """values: boardId -> log2 estimate (already turn-adjusted)."""
    decisive = [(values[b], labels[b]) for b in values if labels.get(b) in (0.0, 1.0)]
    scored = [(values[b], labels[b]) for b in values if labels.get(b) is not None]
    a = auc([s for s, _ in decisive], [y for _, y in decisive]) if decisive else None
    rho = spearman([s for s, _ in scored], [y for _, y in scored]) if scored else None
    out = {
        "metric": name,
        "nDecisive": len(decisive),
        "auc": None if a is None else round(a, 4),
        "nScored": len(scored),
        "spearman": None if rho is None else round(rho, 4),
    }
    print(f"{name:>22}: n_dec={out['nDecisive']:3d} AUC={out['auc']} "
          f"n_all={out['nScored']:3d} rho={out['spearman']}")
    return out


def turn_adjust(values: dict[str, float], turns_by_board: dict[str, int]) -> dict[str, float]:
    by_turn: dict[int, list[float]] = {}
    for b, v in values.items():
        by_turn.setdefault(turns_by_board[b], []).append(v)
    centre = {t: median(vs) for t, vs in by_turn.items() if vs}
    return {b: v - centre[turns_by_board[b]] for b, v in values.items()}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--curves", type=Path, default=_HERE / "out-adaptive" / "curves.json")
    ap.add_argument("--v1", type=Path, default=_HERE / "out-wide" / "curves.json")
    args = ap.parse_args()

    if not args.curves.is_file():
        print(f"missing {args.curves}; run run_adaptive.py first")
        return 2
    rows = json.loads(args.curves.read_text(encoding="utf-8"))
    turns_rows = load_jsonl(TURNS)
    if not turns_rows:
        print(f"missing {TURNS}")
        return 2
    turns = {(r.get("gameId"), r.get("turn")): r for r in turns_rows}
    strength = {r["boardId"]: r for r in load_jsonl(STRENGTH)}

    boards = {r["boardId"]: r for r in rows if r.get("boardId")}
    labels: dict[str, float] = {}
    for bid, row in boards.items():
        tr = turns.get((row.get("gameId"), row.get("turn")))
        if tr is not None:
            lab = label_of(tr)
            if lab is not None:
                labels[bid] = lab
    turn_of = {bid: int(row["turn"]) for bid, row in boards.items()}

    model = {b: math.log2(r["x50"]) for b, r in boards.items()
             if r.get("x50") and not r.get("censored")}
    interp = {b: math.log2(r["x50Interp"]) for b, r in boards.items() if r.get("x50Interp")}

    v1: dict[str, float] = {}
    if args.v1.is_file():
        for r in json.loads(args.v1.read_text(encoding="utf-8")):
            if r.get("x50"):
                v1[r["boardId"]] = math.log2(r["x50"])

    q = {b: float(r["percentile"]) for b, r in strength.items()
         if r.get("percentile") is not None}

    print(f"boards={len(boards)} labelled={len(labels)} v1={len(v1)} percentile={len(q)}")
    model_adj = turn_adjust(model, turn_of)
    interp_adj = turn_adjust(interp, turn_of)
    v1_adj = turn_adjust(v1, {b: turn_of[b] for b in v1 if b in turn_of})

    summary = [summarise("model (adaptive)", model_adj, labels, turn_of)]
    if interp_adj:
        summary.append(summarise("interp (adaptive rungs)", interp_adj, labels, turn_of))
    if v1_adj:
        summary.append(summarise("interp (v1 rungs)", v1_adj, labels, turn_of))
    if q:
        summary.append(summarise("mainline percentile", {b: q[b] for b in q}, labels, turn_of))

    # Same-sample comparison on the model / percentile overlap.
    both = [b for b in model_adj if b in q and labels.get(b) in (0.0, 1.0)]
    if both:
        a_model = auc([model_adj[b] for b in both], [labels[b] for b in both])
        a_q = auc([q[b] for b in both], [labels[b] for b in both])
        print(f"overlap model vs percentile: n={len(both)} "
              f"AUC(model)={None if a_model is None else round(a_model, 4)} "
              f"AUC(percentile)={None if a_q is None else round(a_q, 4)}")

    # Per-turn view: within one turn a constant shift does not change AUC/rho,
    # so raw log2 values are used here.
    print("by turn: boards dec AUC_model AUC_q rho_model rho_q")
    per_turn = []
    for turn in sorted({int(r["turn"]) for r in boards.values()}):
        bds = [b for b, r in boards.items() if int(r["turn"]) == turn]
        mv = {b: model[b] for b in bds if b in model}
        qv = {b: q[b] for b in bds if b in q}

        def stats(vals):
            dec = [(vals[b], labels[b]) for b in vals if b in labels and labels[b] in (0.0, 1.0)]
            sc = [(vals[b], labels[b]) for b in vals if b in labels]
            a = auc([x for x, _ in dec], [y for _, y in dec]) if dec else None
            r = spearman([x for x, _ in sc], [y for _, y in sc]) if len(sc) >= 3 else None
            return a, r, len(dec)

        am, rm, nm = stats(mv)
        aq, rq, nq = stats(qv)
        row = {
            "turn": turn, "boards": len(bds), "decisiveModel": nm, "decisivePercentile": nq,
            "aucModel": None if am is None else round(am, 4),
            "aucPercentile": None if aq is None else round(aq, 4),
            "rhoModel": None if rm is None else round(rm, 4),
            "rhoPercentile": None if rq is None else round(rq, 4),
        }
        per_turn.append(row)
        print(f"  t{turn:02d} n={len(bds):3d} dec={nm:3d} "
              f"AUC_model={row['aucModel']} AUC_q={row['aucPercentile']} "
              f"rho_model={row['rhoModel']} rho_q={row['rhoPercentile']}")

    out_path = args.curves.with_name("outcomes.json")
    out_path.write_text(json.dumps({"summary": summary, "perTurn": per_turn},
                                   ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
