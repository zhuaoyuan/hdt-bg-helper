# -*- coding: utf-8 -*-
"""Turn probe win/tie/loss curves into an absolute stat and score the ladder."""
from __future__ import annotations

import json
import math
import os
import sys
from collections import defaultdict
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO / "tools"))

OUT = Path(__file__).resolve().parent / "out"
TURNS_PATH = _REPO / "data" / "standard" / "turns.jsonl"
STRENGTH_PATH = _REPO / "data" / "strength" / "1.85.0.0" / "strength.jsonl"


def combat_score(win: float, tie: float) -> float:
    return float(win) + 0.5 * float(tie)


def x50_log(levels: list[int], scores: list[float]) -> tuple[float | None, str]:
    """Stat where score crosses 0.5, interpolated in log2(level)."""
    if not levels:
        return None, "empty"
    if scores[0] < 0.5:
        return None, "below"
    if scores[-1] >= 0.5:
        return None, "above"
    for i in range(len(levels) - 1):
        left, right = scores[i], scores[i + 1]
        if left >= 0.5 > right:
            span = left - right
            if span < 1e-9:
                return float(levels[i]), "flat"
            t = (left - 0.5) / span
            log_v = math.log2(levels[i]) + t * (math.log2(levels[i + 1]) - math.log2(levels[i]))
            return 2.0 ** log_v, "interior"
    return None, "no-cross"


def logistic_x50(levels: list[int], scores: list[float]) -> tuple[float | None, float]:
    """Least-squares logistic in log2(level). Returns (x50, sse)."""
    if len(levels) < 3:
        return None, math.inf
    best_sse = math.inf
    best_log = None
    lo = math.log2(levels[0]) - 1
    hi = math.log2(levels[-1]) + 1
    steps = 80
    scales = (0.15, 0.3, 0.5, 0.8, 1.2, 2.0, 3.5)
    for step in range(steps + 1):
        log_a = lo + (hi - lo) * step / steps
        for scale in scales:
            sse = 0.0
            for level, score in zip(levels, scores):
                z = (math.log2(level) - log_a) / scale
                if z > 40:
                    pred = 0.0
                elif z < -40:
                    pred = 1.0
                else:
                    pred = 1.0 / (1.0 + math.exp(z))
                sse += (pred - score) ** 2
            if sse < best_sse:
                best_sse = sse
                best_log = log_a
    if best_log is None:
        return None, best_sse
    return 2.0 ** best_log, best_sse


def monotone(scores: list[float], tol: float = 0.05) -> bool:
    return all(b <= a + tol for a, b in zip(scores, scores[1:]))


def ranks(values: list[float]) -> list[float]:
    order = sorted(range(len(values)), key=lambda i: values[i])
    out = [0.0] * len(values)
    i = 0
    while i < len(values):
        j = i
        while j + 1 < len(values) and values[order[j + 1]] == values[order[i]]:
            j += 1
        avg = (i + j) / 2.0 + 1.0
        for k in range(i, j + 1):
            out[order[k]] = avg
        i = j + 1
    return out


def pearson(xs: list[float], ys: list[float]) -> float | None:
    n = len(xs)
    if n < 3:
        return None
    mx = sum(xs) / n
    my = sum(ys) / n
    num = sum((a - mx) * (b - my) for a, b in zip(xs, ys))
    dx = math.sqrt(sum((a - mx) ** 2 for a in xs))
    dy = math.sqrt(sum((b - my) ** 2 for b in ys))
    if dx == 0 or dy == 0:
        return None
    return num / (dx * dy)


def spearman(xs: list[float], ys: list[float]) -> float | None:
    if len(xs) < 3:
        return None
    return pearson(ranks(xs), ranks(ys))


def auc(scores: list[float], labels: list[int]) -> float | None:
    """Mann-Whitney AUC. labels are 1 (positive) or 0."""
    pos = [s for s, y in zip(scores, labels) if y == 1]
    neg = [s for s, y in zip(scores, labels) if y == 0]
    if not pos or not neg:
        return None
    wins = 0.0
    for p in pos:
        for q in neg:
            if p > q:
                wins += 1
            elif p == q:
                wins += 0.5
    return wins / (len(pos) * len(neg))


def load_jsonl(path: Path) -> list[dict]:
    rows = []
    if not path.is_file():
        return rows
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def median(values: list[float]) -> float | None:
    if not values:
        return None
    xs = sorted(values)
    mid = len(xs) // 2
    if len(xs) % 2:
        return xs[mid]
    return 0.5 * (xs[mid - 1] + xs[mid])


def main() -> None:
    global OUT
    if len(sys.argv) > 1:
        OUT = Path(sys.argv[1])
    raw = [r for r in load_jsonl(OUT / "results.jsonl") if r.get("ok")]
    raw += [r for r in load_jsonl(OUT / "refine.jsonl") if r.get("ok")]
    by_board: dict[str, list[dict]] = defaultdict(list)
    for row in raw:
        game, turn_token, _level = row["id"].split("|")
        turn = int(turn_token[1:])
        key = f"{game}|t{turn}|Player"
        by_board[key].append(row)

    curves = []
    for board_id, rows in sorted(by_board.items()):
        rows.sort(key=lambda r: r["attack"])
        levels = [int(r["attack"]) for r in rows]
        scores = [combat_score(r["winRate"], r["tieRate"]) for r in rows]
        x50, status = x50_log(levels, scores)
        fit, sse = logistic_x50(levels, scores)
        game, turn_token, _side = board_id.split("|")
        # strength.jsonl uses side "Player", matching tools/strength/pool.py.
        curves.append({
            "boardId": board_id,
            "gameId": game,
            "turn": int(turn_token[1:]),
            "levels": levels,
            "scores": [round(s, 4) for s in scores],
            "monotone": monotone(scores),
            "x50": None if x50 is None else round(x50, 2),
            "x50Status": status,
            "fitX50": None if fit is None else round(fit, 2),
            "fitSse": round(sse, 4),
        })

    (OUT / "curves.json").write_text(json.dumps(curves, ensure_ascii=False, indent=2), encoding="utf-8")

    widths = []
    for curve in curves:
        soft = [level for level, score in zip(curve["levels"], curve["scores"]) if 0.05 < score < 0.95]
        widths.append(len(soft))
    print(f"boards={len(curves)} sims={len(raw)}")
    print(f"transition rungs in (0.05,0.95): median={median(widths)} max={max(widths) if widths else None}")
    print(f"monotone={sum(1 for c in curves if c['monotone'])}/{len(curves)}")
    status_counts: dict[str, int] = defaultdict(int)
    for curve in curves:
        status_counts[curve["x50Status"]] += 1
    print("status", dict(status_counts))

    print("by turn: n interior median_x50")
    for turn in sorted({c["turn"] for c in curves}):
        group = [c for c in curves if c["turn"] == turn]
        interior = [c["x50"] for c in group if c["x50Status"] == "interior"]
        print(f"  t{turn:02d} n={len(group)} interior={len(interior)} median={median(interior)}")

    both = [
        (c["x50"], c["fitX50"])
        for c in curves
        if c["x50Status"] == "interior" and c["fitX50"] is not None
    ]
    if both:
        rho = spearman([a for a, _b in both], [b for _a, b in both])
        print(f"spearman(interp, logistic)={None if rho is None else round(rho, 3)} n={len(both)}")

    strength = {row["boardId"]: row for row in load_jsonl(STRENGTH_PATH)}
    paired = []
    for curve in curves:
        peer = strength.get(curve["boardId"])
        if not peer or peer.get("percentile") is None or curve["x50"] is None:
            continue
        paired.append((curve["turn"], curve["x50"], float(peer["percentile"]), curve["boardId"]))
    print(f"paired_with_percentile={len(paired)}")
    if len(paired) >= 3:
        raw_rho = spearman([math.log2(x) for _t, x, _q, _b in paired], [q for _t, _x, q, _b in paired])
        print(f"spearman(log2 x50, percentile) pooled={None if raw_rho is None else round(raw_rho, 3)}")
        by_turn_med: dict[int, float] = {}
        for turn in {t for t, _x, _q, _b in paired}:
            by_turn_med[turn] = median([math.log2(x) for t, x, _q, _b in paired if t == turn]) or 0.0
        adj = spearman(
            [math.log2(x) - by_turn_med[t] for t, x, _q, _b in paired],
            [q for _t, _x, q, _b in paired],
        )
        print(f"spearman(turn-adjusted log2 x50, percentile)={None if adj is None else round(adj, 3)}")
    by_turn_rho = []
    for turn in sorted({t for t, _x, _q, _b in paired}):
        group = [(x, q) for t, x, q, _b in paired if t == turn]
        rho = spearman([math.log2(x) for x, _q in group], [q for _x, q in group])
        if rho is not None:
            by_turn_rho.append(rho)
            print(f"  t{turn:02d} spearman(log x50, Q)={rho:.3f} n={len(group)}")
    if by_turn_rho:
        print(f"median within-turn spearman={median(by_turn_rho):.3f}")

    turns = {}
    for row in load_jsonl(TURNS_PATH):
        turns[(row.get("gameId"), row.get("turn"))] = row
    outcome_x = []
    outcome_y = []
    outcome_q = []
    for curve in curves:
        row = turns.get((curve["gameId"], curve["turn"]))
        if not row or curve["x50"] is None:
            continue
        result = row.get("result")
        if result == "win":
            label = 1
        elif result == "loss":
            label = 0
        else:
            continue
        outcome_x.append(math.log2(curve["x50"]))
        outcome_y.append(label)
        peer = strength.get(curve["boardId"])
        if peer and peer.get("percentile") is not None:
            outcome_q.append((float(peer["percentile"]), label, curve["turn"], math.log2(curve["x50"])))
    print(f"decisive combats with x50={len(outcome_y)}")
    turn_med_all: dict[int, float] = {}
    for turn in {c["turn"] for c in curves}:
        vals = [math.log2(c["x50"]) for c in curves if c["turn"] == turn and c["x50"]]
        if vals:
            turn_med_all[turn] = median(vals) or 0.0
    resid_scores = []
    resid_labels = []
    for curve in curves:
        row = turns.get((curve["gameId"], curve["turn"]))
        if not row or not curve["x50"] or curve["turn"] not in turn_med_all:
            continue
        result = row.get("result")
        if result == "win":
            label = 1
        elif result == "loss":
            label = 0
        else:
            continue
        resid_scores.append(math.log2(curve["x50"]) - turn_med_all[curve["turn"]])
        resid_labels.append(label)
    resid_auc = auc(resid_scores, resid_labels)
    if resid_auc is not None:
        print(f"AUC(turn-adjusted log x50 -> win vs loss)={resid_auc:.3f} n={len(resid_labels)}")
    if outcome_q:
        q_auc = auc([q for q, _y, _t, _x in outcome_q], [y for _q, y, _t, _x in outcome_q])
        resid_on_q = []
        labels_on_q = []
        for q, label, turn, log_x in outcome_q:
            if turn not in turn_med_all:
                continue
            resid_on_q.append(log_x - turn_med_all[turn])
            labels_on_q.append(label)
        x_auc = auc(resid_on_q, labels_on_q)
        print(
            f"on Q-overlap n={len(outcome_q)} AUC(Q)={None if q_auc is None else round(q_auc, 3)} "
            f"AUC(turn-adjusted x50)={None if x_auc is None else round(x_auc, 3)}"
        )


if __name__ == "__main__":
    main()
