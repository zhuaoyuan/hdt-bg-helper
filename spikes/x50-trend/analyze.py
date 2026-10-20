# -*- coding: utf-8 -*-
"""X50 time-series analysis for one BB version: per-turn 10-game moving average,
trend tests with game-clustered bootstrap, robustness checks, figures.

Run after build_dataset.py:
    python spikes/x50-trend/analyze.py

Outputs (gitignored):
    spikes/x50-trend/out/analysis.json
    spikes/x50-trend/out/figs/*.png
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "spikes/x50-trend/out"
TURNS_MAIN = tuple(range(5, 13))          # 5-12 main window
TURNS_DESC = tuple(range(5, 16))          # descriptive profile (sparse after 12)


def load_csv(path: Path, numeric: tuple[str, ...]) -> list[dict]:
    rows: list[dict] = []
    with path.open(encoding="utf-8") as f:
        header = f.readline().rstrip("\n").split(",")
        for line in f:
            line = line.rstrip("\n")
            if not line:
                continue
            parts = line.split(",")
            rec: dict = {}
            for k, v in zip(header, parts):
                if k in numeric:
                    rec[k] = float(v) if v not in ("", "None") else None
                elif k in ("seq", "turn", "interior", "placement", "maxTurn", "nMe", "nOpp"):
                    rec[k] = int(float(v)) if v not in ("", "None") else None
                else:
                    rec[k] = v if v not in ("", "None") else None
            rows.append(rec)
    return rows


def mean(xs):
    xs = [x for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else None


def median(xs):
    xs = sorted(x for x in xs if x is not None)
    if not xs:
        return None
    n = len(xs)
    return xs[n // 2] if n % 2 else 0.5 * (xs[n // 2 - 1] + xs[n // 2])


def quantile(xs, q):
    xs = sorted(x for x in xs if x is not None)
    if not xs:
        return None
    pos = q * (len(xs) - 1)
    lo, hi = int(math.floor(pos)), int(math.ceil(pos))
    return xs[lo] + (xs[hi] - xs[lo]) * (pos - lo)


def rolling_mean(values: list[float], window: int) -> list[float | None]:
    """Trailing mean over the last `window` available observations."""
    out: list[float | None] = []
    buf: list[float] = []
    for v in values:
        if v is not None:
            buf.append(v)
        out.append(sum(buf[-window:]) / len(buf[-window:]) if buf else None)
    return out


def rolling_mean_full(values: list[float], window: int) -> list[float | None]:
    """Trailing mean, but only emitted once a full window is available.

    A 10-game moving average over 1-9 games is dominated by the first few games;
    drawing it from the first observation would fake a trend. Raw points stay
    visible from the start.
    """
    ma = rolling_mean(values, window)
    seen = 0
    out: list[float | None] = []
    for v, m in zip(values, ma):
        if v is not None:
            seen += 1
        out.append(m if seen >= window else None)
    return out


def bh_q(values: list[float]) -> list[float]:
    """Benjamini-Hochberg q values, same order as input."""
    m = len(values)
    order = sorted(range(m), key=lambda i: values[i])
    q = [0.0] * m
    prev = 1.0
    for rank in range(m - 1, -1, -1):
        i = order[rank]
        prev = min(prev, values[i] * m / (rank + 1))
        q[i] = prev
    return q


def design_matrix(rows: list[dict], turn_fe: bool) -> np.ndarray:
    seqs = np.array([r["seq"] for r in rows], dtype=float)
    x = (seqs - seqs.mean()).reshape(-1, 1)
    cols = [np.ones((len(rows), 1)), x]
    if turn_fe:
        turns = sorted({r["turn"] for r in rows})
        for t in turns[1:]:
            cols.append(np.array([[1.0 if r["turn"] == t else 0.0] for r in rows]))
    return np.hstack(cols)


def fit_slope(rows: list[dict], turn_fe: bool = True) -> float:
    X = design_matrix(rows, turn_fe)
    y = np.array([r["y"] for r in rows], dtype=float)
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    return float(beta[1])


def cluster_bootstrap(rows: list[dict], B: int, seed: int, turn_fe: bool = True) -> np.ndarray:
    rng = np.random.default_rng(seed)
    games = sorted({r["gameId"] for r in rows})
    by_game: dict[str, list[dict]] = {}
    for r in rows:
        by_game.setdefault(r["gameId"], []).append(r)
    out = np.empty(B)
    for b in range(B):
        pick = rng.choice(len(games), size=len(games), replace=True)
        sample: list[dict] = []
        for i in pick:
            sample.extend(by_game[games[i]])
        out[b] = fit_slope(sample, turn_fe)
    return out


def summarize_slope(rows: list[dict], label: str, B: int, seed: int) -> dict:
    b = fit_slope(rows)
    dist = cluster_bootstrap(rows, B, seed)
    lo, hi = np.percentile(dist, [2.5, 97.5])
    p = 2 * min((dist >= 0).mean(), (dist <= 0).mean())
    p = min(1.0, float(p))
    # per-10-games percent change; log2 slope -> ratio 2^(10 b)
    def pct(beta):
        return (2 ** (10 * beta) - 1) * 100

    n_games = len({r["gameId"] for r in rows})
    span = max(1, n_games - 1)

    def total(beta):
        return (2 ** (span * beta) - 1) * 100

    return {
        "label": label,
        "n": len(rows),
        "nGames": n_games,
        "slopeLog2PerGame": b,
        "pctPer10Games": pct(b),
        "ci95PctPer10Games": [pct(lo), pct(hi)],
        "totalDriftPct": total(b),
        "ci95TotalDriftPct": [total(lo), total(hi)],
        "pBootstrap": p,
        "bootSd": float(dist.std(ddof=1)),
        "mde80PctPer10Games": pct((1.96 + 0.84) * float(dist.std(ddof=1))),
    }


def per_turn_trend(rows: list[dict], side: str) -> list[dict]:
    from scipy.stats import spearmanr

    out = []
    for t in TURNS_MAIN:
        sub = sorted([r for r in rows if r["turn"] == t and r["side"] == side],
                     key=lambda r: r["seq"])
        if len(sub) < 20:
            continue
        x = np.array([r["seq"] for r in sub], dtype=float)
        y = np.array([r["y"] for r in sub], dtype=float)
        X = np.column_stack([np.ones_like(x), x - x.mean()])
        beta, *_ = np.linalg.lstsq(X, y, rcond=None)
        resid = y - X @ beta
        sigma2 = float(resid @ resid) / (len(y) - 2)
        se = math.sqrt(sigma2 / float(((x - x.mean()) ** 2).sum()))
        rho, p = spearmanr(x, y)
        out.append(
            {
                "turn": t,
                "n": len(sub),
                "slopeLog2PerGame": float(beta[1]),
                "seLog2PerGame": se,
                "pctPer10Games": (2 ** (10 * beta[1]) - 1) * 100,
                "rho": float(rho),
                "p": float(p),
            }
        )
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", type=Path, default=OUT)
    ap.add_argument("--bootstrap", type=int, default=2000)
    ap.add_argument("--window", type=int, default=10)
    ap.add_argument("--no-figs", action="store_true")
    args = ap.parse_args()

    boards = load_csv(args.out / "boards.csv",
                      ("x50", "log2x50", "ciLow", "ciHigh", "seLog2"))
    games = load_csv(args.out / "games.csv",
                     ("meMeanLog2", "oppMeanLog2", "intensityMeanLog2"))
    has_opp = any(r["side"] == "opp" for r in boards)

    # --- main sample: interior, turns 5-12
    main_rows = [r for r in boards if r["interior"] and r["turn"] in TURNS_MAIN]
    for r in main_rows:
        r["y"] = r["log2x50"]

    result: dict = {
        "window": args.window,
        "turnsMain": list(TURNS_MAIN),
        "hasOpponent": has_opp,
        "sample": {
            "games": len({r["gameId"] for r in boards}),
            "boardsTotal": len(boards),
            "boardsMain": {s: sum(1 for r in main_rows if r["side"] == s) for s in ("me", "opp")},
            "turnsMainN": {
                str(t): {s: sum(1 for r in main_rows if r["side"] == s and r["turn"] == t)
                         for s in ("me", "opp")}
                for t in TURNS_MAIN
            },
        },
        "series": {},
        "trends": {},
        "perTurn": {},
        "robustness": {},
        "intensity": {},
    }

    # --- per-turn chronological series + trailing MA (log2 space)
    for side in ("me", "opp"):
        if side == "opp" and not has_opp:
            continue
        side_series: dict[str, dict] = {}
        for t in TURNS_DESC:
            sub = sorted([r for r in main_rows if r["turn"] == t and r["side"] == side
                          and r["interior"]], key=lambda r: r["seq"])
            if not sub:
                continue
            vals = [r["y"] for r in sub]
            ma = rolling_mean_full(vals, args.window)
            side_series[str(t)] = {
                "seq": [r["seq"] for r in sub],
                "x50": [r["x50"] for r in sub],
                "log2x50": vals,
                "ma10": ma,
            }
        result["series"][side] = side_series

    # --- primary trends: pooled, turn FE, game-clustered bootstrap
    for side, yfn in (
        ("me", lambda r: r["log2x50"]),
        ("opp", lambda r: r["log2x50"]),
    ):
        if side == "opp" and not has_opp:
            continue
        rows = [dict(r, y=yfn(r)) for r in main_rows if r["side"] == side and r["log2x50"] is not None]
        result["trends"][side] = summarize_slope(rows, side, args.bootstrap, seed=11)
        result["perTurn"][side] = per_turn_trend(main_rows, side)

    # intensity = geometric mean of both sides on the same combat
    pairs: dict[tuple[str, int], dict[str, dict]] = {}
    for r in main_rows:
        if r["log2x50"] is None:
            continue
        pairs.setdefault((r["gameId"], r["turn"]), {})[r["side"]] = r
    intensity_rows = []
    for (gid, t), d in pairs.items():
        if "me" in d and "opp" in d:
            intensity_rows.append({"gameId": gid, "seq": d["me"]["seq"], "turn": t,
                                   "y": 0.5 * (d["me"]["log2x50"] + d["opp"]["log2x50"])})
    if has_opp and intensity_rows:
        result["intensity"]["trend"] = summarize_slope(intensity_rows, "intensity",
                                                       args.bootstrap, seed=23)
        ratio_rows = []
        for (gid, t), d in pairs.items():
            if "me" in d and "opp" in d:
                ratio_rows.append({"gameId": gid, "seq": d["me"]["seq"], "turn": t,
                                   "y": d["me"]["log2x50"] - d["opp"]["log2x50"]})
        result["intensity"]["trendRatioMeOverOpp"] = summarize_slope(
            ratio_rows, "log2(me/opp)", args.bootstrap, seed=29)
        result["intensity"]["medianRatioByTurn"] = {
            str(t): float(np.median([r["y"] for r in ratio_rows if r["turn"] == t]))
            for t in sorted({r["turn"] for r in ratio_rows})
        }

    # --- BH across the three primary tests (me / opp / intensity)
    prim = []
    for key in ("me", "opp"):
        if key in result["trends"]:
            prim.append(result["trends"][key])
    if "trend" in result["intensity"]:
        prim.append(result["intensity"]["trend"])
        prim.append(result["intensity"]["trendRatioMeOverOpp"])
    qs = bh_q([p["pBootstrap"] for p in prim])
    for p, q in zip(prim, qs):
        p["qBH"] = q

    # BH across per-turn tests per side
    for side in ("me", "opp"):
        if side in result["perTurn"]:
            qs = bh_q([r["p"] for r in result["perTurn"][side]])
            for r, q in zip(result["perTurn"][side], qs):
                r["qBH"] = q

    # --- turn-adjusted index: removes turn-mix/survival composition from the
    # per-game level, so games that die early stay comparable. index = grand mean +
    # mean over the game's boards of (board value - per-turn median).
    index: dict[str, list[dict]] = {}
    date_of_seq = {g["seq"]: g.get("date") for g in games}
    for side in ("me", "opp"):
        if side == "opp" and not has_opp:
            continue
        rows = [r for r in main_rows if r["side"] == side and r["log2x50"] is not None]
        turn_med = {t: median([r["y"] for r in rows if r["turn"] == t])
                    for t in sorted({r["turn"] for r in rows})}
        grand = mean([r["y"] for r in rows])
        acc: dict[tuple[str, int], list[float]] = {}
        for r in rows:
            acc.setdefault((r["gameId"], r["seq"]), []).append(r["y"] - turn_med[r["turn"]])
        index[side] = [
            {"gameId": gid, "seq": sq, "date": date_of_seq.get(sq), "n": len(v),
             "index": grand + mean(v)}
            for (gid, sq), v in sorted(acc.items(), key=lambda kv: kv[0][1])
        ]
    if has_opp and intensity_rows:
        turn_med = {t: median([r["y"] for r in intensity_rows if r["turn"] == t])
                    for t in sorted({r["turn"] for r in intensity_rows})}
        grand = mean([r["y"] for r in intensity_rows])
        acc = {}
        for r in intensity_rows:
            acc.setdefault((r["gameId"], r["seq"]), []).append(r["y"] - turn_med[r["turn"]])
        index["intensity"] = [
            {"gameId": gid, "seq": sq, "date": date_of_seq.get(sq), "n": len(v),
             "index": grand + mean(v)}
            for (gid, sq), v in sorted(acc.items(), key=lambda kv: kv[0][1])
        ]
    result["index"] = index
    idx_by_seq: dict[int, dict] = {}
    for side, rows in index.items():
        for r in rows:
            idx_by_seq.setdefault(r["seq"], {})[side] = r["index"]
    with (args.out / "index.csv").open("w", encoding="utf-8", newline="") as f:
        f.write("seq,date,meIndex,oppIndex,intensityIndex\n")
        for sq in sorted(idx_by_seq):
            d = idx_by_seq[sq]
            def fnum(v):
                return "" if v is None else f"{v:.6f}"
            f.write(f"{sq},{d.get('date', '')},{fnum(d.get('me'))},"
                    f"{fnum(d.get('opp'))},{fnum(d.get('intensity'))}\n")

    # --- robustness
    rob = result["robustness"]
    # (a) first 40 vs last 41 games, pooled over turns 5-12
    for side in ("me", "opp"):
        if side == "opp" and not has_opp:
            continue
        rows = [r for r in main_rows if r["side"] == side]
        early = [r["y"] for r in rows if r["seq"] <= 40]
        late = [r["y"] for r in rows if r["seq"] > 40]
        rob[f"halves_{side}"] = {
            "earlyMedianLog2": median(early),
            "lateMedianLog2": median(late),
            "deltaLog2": (median(late) - median(early)) if early and late else None,
            "earlyX50": 2 ** median(early) if early else None,
            "lateX50": 2 ** median(late) if late else None,
        }
    # (b) turns 6-12 only
    sub = [r for r in main_rows if r["turn"] >= 6 and r["log2x50"] is not None]
    for side in ("me", "opp"):
        if side == "opp" and not has_opp:
            continue
        rows = [dict(r, y=r["log2x50"]) for r in sub if r["side"] == side]
        rob[f"t6to12_{side}"] = summarize_slope(rows, side, args.bootstrap, seed=31)
    # (b2) same-turn early vs late halves (no turn composition inside a turn)
    for side in ("me", "opp"):
        if side == "opp" and not has_opp:
            continue
        rows = [r for r in main_rows if r["side"] == side]
        table = {}
        for t in TURNS_MAIN:
            e = [r["y"] for r in rows if r["turn"] == t and r["seq"] <= 40]
            l = [r["y"] for r in rows if r["turn"] == t and r["seq"] > 40]
            if e and l:
                table[str(t)] = {
                    "nEarly": len(e), "nLate": len(l),
                    "earlyMedianLog2": median(e), "lateMedianLog2": median(l),
                    "deltaLog2": median(l) - median(e),
                }
        rob[f"perTurnHalves_{side}"] = table
    # (b3) turn-adjusted residual quantiles early vs late (spread, not just level)
    for side in ("me", "opp"):
        if side == "opp" and not has_opp:
            continue
        rows = [r for r in main_rows if r["side"] == side and r["y"] is not None]
        tmed = {t: median([r["y"] for r in rows if r["turn"] == t])
                for t in sorted({r["turn"] for r in rows})}
        res = [(r["seq"], r["y"] - tmed[r["turn"]]) for r in rows]
        early = [v for s, v in res if s <= 40]
        late = [v for s, v in res if s > 40]
        rob[f"residualQuantiles_{side}"] = {
            "early": {"p10": quantile(early, 0.1), "p50": quantile(early, 0.5),
                      "p90": quantile(early, 0.9)},
            "late": {"p10": quantile(late, 0.1), "p50": quantile(late, 0.5),
                     "p90": quantile(late, 0.9)},
        }
    # (c) per-day medians of game-level means
    by_day: dict[str, dict[str, list[float]]] = {}
    for g in games:
        d = g.get("date")
        if not d:
            continue
        slot = by_day.setdefault(d, {"me": [], "opp": [], "intensity": []})
        if g.get("meMeanLog2") is not None:
            slot["me"].append(g["meMeanLog2"])
        if g.get("oppMeanLog2") is not None:
            slot["opp"].append(g["oppMeanLog2"])
        if g.get("intensityMeanLog2") is not None:
            slot["intensity"].append(g["intensityMeanLog2"])
    rob["perDay"] = {
        d: {k: median(v) for k, v in slot.items() if v} for d, slot in sorted(by_day.items())
    }
    rob["gamesPerDay"] = {
        d: sum(1 for g in games if g.get("date") == d)
        for d in sorted({g.get("date") for g in games if g.get("date")})
    }
    # (c2) day-level Kendall tau on the per-day medians (coarse, 10 points)
    from scipy.stats import kendalltau
    days = sorted(by_day)
    rob["perDayKendall"] = {}
    for key in ("me", "opp", "intensity"):
        vals = [rob["perDay"][d].get(key) for d in days if rob["perDay"][d].get(key) is not None]
        if len(vals) >= 5:
            tau, p = kendalltau(range(len(vals)), vals)
            rob["perDayKendall"][key] = {"nDays": len(vals), "tau": float(tau), "p": float(p)}
    # (e) game-level index trend: one observation per game (turn-adjusted), OLS day
    # slope with bootstrap over games. Coarser than the FE model but easy to read.
    for side in ("me", "opp", "intensity"):
        rows = index.get(side) or []
        if len(rows) < 10:
            continue
        xs = np.array([r["seq"] for r in rows], float)
        ys = np.array([r["index"] for r in rows], float)
        X = np.column_stack([np.ones_like(xs), xs - xs.mean()])
        beta, *_ = np.linalg.lstsq(X, ys, rcond=None)
        rng = np.random.default_rng(41)
        dist = np.empty(args.bootstrap)
        for b in range(args.bootstrap):
            pick = rng.integers(0, len(xs), len(xs))
            Xb = X[pick]
            bb, *_ = np.linalg.lstsq(Xb, ys[pick], rcond=None)
            dist[b] = bb[1]
        lo, hi = np.percentile(dist, [2.5, 97.5])
        rob[f"indexTrend_{side}"] = {
            "n": len(rows),
            "slopeLog2PerGame": float(beta[1]),
            "pctPer10Games": (2 ** (10 * beta[1]) - 1) * 100,
            "ci95PctPer10Games": [(2 ** (10 * lo) - 1) * 100, (2 ** (10 * hi) - 1) * 100],
            "pBootstrap": float(min(1.0, 2 * min((dist >= 0).mean(), (dist <= 0).mean()))),
        }

    # (f) trim: drop boards whose CI is missing or very wide (log2 width > 1.0).
    # Sharp-transition boards have a near-step logistic fit and can produce a
    # degenerate CI; they add measurement noise, so check they do not drive trends.
    for side in ("me", "opp"):
        if side == "opp" and not has_opp:
            continue
        trim_rows = []
        for r in main_rows:
            if r["side"] != side:
                continue
            lo, hi = r.get("ciLow"), r.get("ciHigh")
            if not lo or not hi or lo <= 0:
                continue
            if math.log2(hi / lo) > 1.0:
                continue
            trim_rows.append(dict(r, y=r["log2x50"]))
        rob[f"trim_{side}"] = summarize_slope(trim_rows, side, args.bootstrap, seed=53)
        rob[f"trim_{side}"]["nDropped"] = sum(
            1 for r in main_rows if r["side"] == side) - len(trim_rows)

    # (d) composition / survival drift
    seqs = [g["seq"] for g in games]
    max_turns = [g["maxTurn"] for g in games]
    from scipy.stats import spearmanr
    rho_surv, p_surv = spearmanr(seqs, max_turns)
    n_main = [0 if g.get("meMeanLog2") is None else 1 for g in games]
    rob["composition"] = {
        "survivalRhoVsSeq": float(rho_surv),
        "survivalP": float(p_surv),
        "earlyMedianMaxTurn": median([g["maxTurn"] for g in games if g["seq"] <= 40]),
        "lateMedianMaxTurn": median([g["maxTurn"] for g in games if g["seq"] > 40]),
        "nGamesWithMainBoards": int(sum(n_main)),
    }

    (args.out / "analysis.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    if not args.no_figs:
        make_figures(result, boards, games, args.out / "figs", args.window)

    # console summary
    print(json.dumps({
        "sample": result["sample"],
        "trends": {k: {kk: v[kk] for kk in ("n", "nGames", "pctPer10Games",
                                           "ci95PctPer10Games", "pBootstrap", "qBH",
                                           "mde80PctPer10Games")}
                   for k, v in result["trends"].items()},
        "intensity": {k: ({kk: vv[kk] for kk in ("n", "nGames", "pctPer10Games",
                                                 "ci95PctPer10Games", "pBootstrap", "qBH",
                                                 "mde80PctPer10Games")}
                          if isinstance(vv, dict) and "pctPer10Games" in vv else vv)
                      for k, vv in result["intensity"].items()},
        "robustness": {k: v for k, v in result["robustness"].items() if "halves" in k},
    }, ensure_ascii=False, indent=2))
    return 0


def make_figures(result: dict, boards: list[dict], games: list[dict], fig_dir: Path,
                 window: int) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    from datetime import datetime

    plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False
    fig_dir.mkdir(parents=True, exist_ok=True)

    me_color, opp_color, int_color = "#1f6fb4", "#d1603d", "#5a5a5a"
    seq_to_date = {}
    for g in games:
        if g.get("date"):
            seq_to_date.setdefault(g["seq"], datetime.strptime(g["date"], "%Y%m%d"))
    first_seq_by_date: dict[str, int] = {}
    for g in sorted(games, key=lambda x: x["seq"]):
        if g.get("date"):
            first_seq_by_date.setdefault(g["date"], g["seq"])
    date_ticks = [(s, datetime.strptime(d, "%Y%m%d"))
                  for d, s in sorted(first_seq_by_date.items(), key=lambda kv: kv[1])]

    def set_date_ticks(ax, fontsize=7):
        ax.set_xticks([s for s, _ in date_ticks])
        ax.set_xticklabels([d.strftime("%m-%d") for _, d in date_ticks], rotation=45,
                           ha="right", fontsize=fontsize)


    # ---- Figure 1: small multiples t5-t12, me vs opponent + 10-game MA
    turns = [t for t in TURNS_MAIN if str(t) in result["series"].get("me", {})]
    ncol = 4
    nrow = math.ceil(len(turns) / ncol)
    fig, axes = plt.subplots(nrow, ncol, figsize=(4.2 * ncol, 3.0 * nrow), sharex=True,
                             squeeze=False)
    for idx, t in enumerate(turns):
        ax = axes[idx // ncol][idx % ncol]
        for side, color, label in (("me", me_color, "我"), ("opp", opp_color, "对手")):
            s = result["series"].get(side, {}).get(str(t))
            if not s:
                continue
            ax.scatter(s["seq"], s["log2x50"], s=7, alpha=0.25, color=color, linewidths=0)
            ax.plot(s["seq"], s["ma10"], color=color, lw=2.0, label=f"{label} {window} 局均线")
        ax.set_title(f"回合 {t}（n={len(result['series']['me'][str(t)]['seq'])}）", fontsize=10)
        ax.grid(alpha=0.25, lw=0.5)
        ax.set_xlim(0, max(g["seq"] for g in games) + 1)
    for idx in range(len(turns), nrow * ncol):
        axes[idx // ncol][idx % ncol].axis("off")
    # date ticks on the bottom row panels only
    for idx in range(ncol * (nrow - 1), nrow * ncol):
        if idx < len(turns):
            set_date_ticks(axes[idx // ncol][idx % ncol], fontsize=7)
    for i in range(nrow):
        axes[i][0].set_ylabel("log2 X50")
    handles, labels = axes[0][0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", ncol=4, frameon=False, bbox_to_anchor=(0.5, 0.99))
    fig.suptitle(f"现版本（BB 1.88.6.0）分回合 X50 时序：我 vs 对手（细点=单板，粗线={window} 局"
                 f"滑动均线，log2 域）", y=1.03, fontsize=12)
    fig.tight_layout(rect=(0, 0, 1, 0.97))
    fig.savefig(fig_dir / "fig1_turns_me_vs_opp.png", dpi=150, bbox_inches="tight")
    plt.close(fig)

    # ---- Figure 2: turn-adjusted per-game index (me / opp / intensity) + MA + trend
    fig, ax = plt.subplots(figsize=(11.5, 5.0))
    specs = (("me", me_color, "我"), ("opp", opp_color, "对手"),
             ("intensity", int_color, "对局强度"))
    trend_source = {
        "me": result["trends"].get("me"),
        "opp": result["trends"].get("opp"),
        "intensity": result["intensity"].get("trend"),
    }
    txt_lines = []
    for side, color, label in specs:
        pts = [(r["seq"], r["index"]) for r in result["index"].get(side, [])]
        if not pts:
            continue
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        ax.scatter(xs, ys, s=9, alpha=0.22, color=color, linewidths=0)
        ax.plot(xs, rolling_mean_full(ys, window), color=color,
                lw=2.3 if side == "intensity" else 1.7,
                label=f"{label}（{window} 局均线）")
        if len(pts) >= 3:
            xa = np.array(xs, float)
            ya = np.array(ys, float)
            X = np.column_stack([np.ones_like(xa), xa - xa.mean()])
            beta, *_ = np.linalg.lstsq(X, ya, rcond=None)
            grid = np.array([xa.min(), xa.max()])
            ax.plot(grid, beta[0] + beta[1] * (grid - xa.mean()), ls="--", lw=1.1,
                    color=color, alpha=0.9)
        tinfo = trend_source.get(side)
        if tinfo:
            txt_lines.append(
                f"{label}: {tinfo['pctPer10Games']:+.1f}%/10局 "
                f"[{tinfo['ci95PctPer10Games'][0]:+.1f}, {tinfo['ci95PctPer10Games'][1]:+.1f}], "
                f"q={tinfo.get('qBH', float('nan')):.2f}"
            )
    if txt_lines:
        ax.text(0.01, 0.02, "趋势（回合固定效应 + 按局聚类 bootstrap）：\n" + "\n".join(txt_lines),
                transform=ax.transAxes, fontsize=8, va="bottom",
                bbox=dict(boxstyle="round,pad=0.35", fc="white", ec="#cccccc", alpha=0.9))
    set_date_ticks(ax, fontsize=8)
    ax.set_xlabel("对局顺序号（按 gameId 时间升序；刻度为日期）")
    ax.set_ylabel("回合调整后的 log2 X50（跨回合可比）")
    ax.grid(alpha=0.25, lw=0.5)
    ax.legend(ncol=3, frameon=False, fontsize=9, loc="upper left")
    ax.set_title(f"现版本（BB 1.88.6.0）对局强度时序（{window} 局滑动均线；虚线=线性趋势）",
                 fontsize=11)
    fig.tight_layout()
    fig.savefig(fig_dir / "fig2_pooled_intensity.png", dpi=150, bbox_inches="tight")
    plt.close(fig)

    # ---- Figure 3: per-turn profile (medians + IQR), me vs opponent
    fig, ax = plt.subplots(figsize=(8.5, 4.6))
    for side, color, label in (("me", me_color, "我"), ("opp", opp_color, "对手")):
        if side not in result["series"]:
            continue
        med, lo, hi, nn = [], [], [], []
        for t in TURNS_DESC:
            sub = [r for r in boards if r["interior"] and r["turn"] == t and r["side"] == side]
            vals = [r["log2x50"] for r in sub]
            if not vals:
                continue
            nn.append(len(vals))
            med.append(median(vals))
            lo.append(quantile(vals, 0.25))
            hi.append(quantile(vals, 0.75))
        x = [t for t in TURNS_DESC if any(r["interior"] and r["turn"] == t and r["side"] == side
                                          for r in boards)]
        ax.plot(x, med, "-o", color=color, lw=1.8, ms=4, label=f"{label} 中位数")
        ax.fill_between(x, lo, hi, color=color, alpha=0.16, linewidth=0)
    ax.set_xticks(list(TURNS_DESC))
    ax.set_xlabel("回合")
    ax.set_ylabel("log2 X50")
    ax.grid(alpha=0.25, lw=0.5)
    ax.legend(frameon=False)
    ax.set_title("现版本 X50 回合剖面（中位数与 IQR；t13 以后样本很少，仅示意）", fontsize=11)
    fig.tight_layout()
    fig.savefig(fig_dir / "fig3_turn_profile.png", dpi=150, bbox_inches="tight")
    plt.close(fig)

    # ---- Figure 4: per-turn trend forest plot
    fig, ax = plt.subplots(figsize=(7.5, 4.4))
    yticks, ylabels = [], []
    for side, color, label in (("me", me_color, "我"), ("opp", opp_color, "对手")):
        rows = result["perTurn"].get(side) or []
        for i, r in enumerate(rows):
            y = r["turn"] * 2 + (0.25 if side == "me" else -0.25)
            ax.errorbar(r["pctPer10Games"],
                        y,
                        xerr=1.96 * r["seLog2PerGame"] * 10 * math.log(2) * 100,
                        fmt="o", color=color, ms=4, capsize=2, lw=1)
            yticks.append(y)
            ylabels.append(f"t{r['turn']}" if side == "me" else "")
    ax.axvline(0, color="k", lw=0.8, alpha=0.6)
    ax.set_yticks(yticks)
    ax.set_yticklabels(ylabels)
    ax.set_xlabel("每 10 局变化（%，线性近似；误差棒≈95% CI）")
    ax.set_title("分回合趋势（我=上/蓝，对手=下/橙）：都跨 0", fontsize=11)
    ax.grid(alpha=0.25, lw=0.5, axis="x")
    fig.tight_layout()
    fig.savefig(fig_dir / "fig4_per_turn_forest.png", dpi=150, bbox_inches="tight")
    plt.close(fig)

    print(f"figures -> {fig_dir}")


if __name__ == "__main__":
    raise SystemExit(main())
