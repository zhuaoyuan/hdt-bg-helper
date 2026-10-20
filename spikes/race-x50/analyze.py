# -*- coding: utf-8 -*-
"""Explore lobby race-pool composition vs player X50 strength.

X50 comes from the dummy-ladder v2 adaptive run (all turns 1-17, Player side).
Lobby races come from the standard layer's ``rules.availableRaces``.

The script:
  1. joins X50 boards to race pools (game-level constant, 5 races);
  2. removes the turn effect (within-turn residual);
  3. estimates whether race-pool presence explains X50 at game level;
  4. reports per-turn exploratory effects and growth-rate effects;
  5. evaluates whether exact race pools / race-pool clusters can be used as
     separate strength pools (sample sizes, R^2).

Run from the repo root:
  python spikes/race-x50/analyze.py
"""
from __future__ import annotations

import argparse
import collections
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats
from scipy.cluster.hierarchy import fcluster, linkage
from scipy.spatial.distance import squareform

REPO = Path(__file__).resolve().parents[2]


def load_joined(curves_path: Path, turns_path: Path, tmin: int, tmax: int) -> pd.DataFrame:
    curves = json.loads(curves_path.read_text(encoding="utf-8"))
    turns = [json.loads(line) for line in turns_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    tby = {(r["gameId"], int(r["turn"])): r for r in turns}
    rows = []
    for c in curves:
        if c.get("status") != "interior":
            continue
        turn = int(c["turn"])
        if turn < tmin or turn > tmax:
            continue
        trow = tby.get((c["gameId"], turn))
        if not trow:
            continue
        rules = trow.get("rules") or {}
        races = tuple(sorted(rules.get("availableRaces") or []))
        rows.append(
            {
                "gameId": c["gameId"],
                "turn": turn,
                "x50": float(c["x50"]),
                "log2x50": math.log2(float(c["x50"])),
                "ci": c.get("ci"),
                "races": races,
                "hero": trow.get("myHeroCard"),
                "bb": (trow.get("meta") or {}).get("bbVersion"),
            }
        )
    df = pd.DataFrame(rows)
    if df.empty:
        raise SystemExit("no joined boards; check curves/turns paths and filters")
    df["turnMean"] = df.groupby("turn")["log2x50"].transform("mean")
    df["turnSd"] = df.groupby("turn")["log2x50"].transform("std")
    df["res"] = df["log2x50"] - df["turnMean"]
    df["z"] = df["res"] / df["turnSd"]
    return df


def race_columns(df: pd.DataFrame, races: list[str]) -> pd.DataFrame:
    out = df.copy()
    for r in races:
        out[r] = out["races"].apply(lambda rs: int(r in rs))
    return out


def game_table(df: pd.DataFrame, races: list[str]) -> pd.DataFrame:
    g = df.groupby("gameId", as_index=False).agg(
        res=("res", "mean"),
        z=("z", "mean"),
        n=("res", "size"),
        races=("races", "first"),
        hero=("hero", "first"),
        bb=("bb", "first"),
    )
    return race_columns(g, races)


def fit_race_model(g: pd.DataFrame, races: list[str]) -> tuple[float, float, dict[str, float]]:
    """OLS y = intercept + race presence (drop last race); return R2/adj/beta."""
    cols = races[:-1]
    X = np.column_stack([np.ones(len(g))] + [g[c].to_numpy(float) for c in cols])
    y = g["res"].to_numpy(float)
    beta = np.linalg.lstsq(X, y, rcond=None)[0]
    pred = X @ beta
    r2 = 1.0 - float(((y - pred) ** 2).sum() / ((y - y.mean()) ** 2).sum())
    p = X.shape[1]
    adj = 1.0 - (1.0 - r2) * (len(g) - 1) / max(1, len(g) - p)
    return r2, adj, {name: float(b) for name, b in zip(cols, beta[1:])}


def permutation_joint_p(g: pd.DataFrame, races: list[str], observed_r2: float, n: int, rng: np.random.Generator) -> float:
    presence = g[races].to_numpy(int)
    y = g["res"].to_numpy(float)
    count = 0
    for _ in range(n):
        idx = rng.permutation(len(g))
        X = np.column_stack([np.ones(len(g))] + [presence[idx, j] for j in range(len(races) - 1)])
        beta = np.linalg.lstsq(X, y, rcond=None)[0]
        pred = X @ beta
        r2 = 1.0 - float(((y - pred) ** 2).sum() / ((y - y.mean()) ** 2).sum())
        if r2 >= observed_r2 - 1e-12:
            count += 1
    return (count + 1) / (n + 1)


def single_effects(g: pd.DataFrame, races: list[str], n_boot: int, n_perm: int, rng: np.random.Generator) -> dict:
    out: dict[str, dict] = {}
    y = g["res"].to_numpy(float)
    presence = g[races].to_numpy(int)
    for j, r in enumerate(races):
        a = y[presence[:, j] == 1]
        b = y[presence[:, j] == 0]
        diff = float(a.mean() - b.mean())
        se = math.sqrt(a.var(ddof=1) / len(a) + b.var(ddof=1) / len(b))
        boot = []
        for _ in range(n_boot):
            idx = rng.integers(0, len(y), len(y))
            yy = y[idx]
            aa = yy[presence[idx, j] == 1]
            bb = yy[presence[idx, j] == 0]
            boot.append(float(aa.mean() - bb.mean()))
        count = 0
        for _ in range(n_perm):
            idx = rng.permutation(len(y))
            aa = y[idx][presence[:, j] == 1]
            bb = y[idx][presence[:, j] == 0]
            if abs(float(aa.mean() - bb.mean())) >= abs(diff) - 1e-12:
                count += 1
        out[r] = {
            "nPresent": int(len(a)),
            "nAbsent": int(len(b)),
            "diffLog2": diff,
            "se": se,
            "ci95": [float(np.quantile(boot, 0.025)), float(np.quantile(boot, 0.975))],
            "permP": (count + 1) / (n_perm + 1),
        }
    return out


def per_turn(df: pd.DataFrame, races: list[str], n_perm: int, rng: np.random.Generator) -> list[dict]:
    out = []
    for t in sorted(df["turn"].unique()):
        g = game_table(df[df["turn"] == t], races)
        r2, adj, beta = fit_race_model(g, races)
        tests = []
        for r in races:
            a = g.loc[g[r] == 1, "res"]
            b = g.loc[g[r] == 0, "res"]
            diff = float(a.mean() - b.mean())
            se = math.sqrt(a.var(ddof=1) / len(a) + b.var(ddof=1) / len(b))
            tests.append({"race": r, "diffLog2": diff, "t": diff / se if se > 0 else None})
        top = max(tests, key=lambda e: abs(e["t"]) if e["t"] is not None else -1.0)

        # Joint R2 permutation p for this turn.
        P = g[races].to_numpy(int)
        y = g["res"].to_numpy(float)
        cnt = 0
        for _ in range(n_perm):
            idx = rng.permutation(len(g))
            X = np.column_stack([np.ones(len(g))] + [P[idx, j] for j in range(len(races) - 1)])
            beta_p = np.linalg.lstsq(X, y, rcond=None)[0]
            pred = X @ beta_p
            r2p = 1.0 - float(((y - pred) ** 2).sum() / ((y - y.mean()) ** 2).sum())
            if r2p >= r2 - 1e-12:
                cnt += 1
        joint_p = (cnt + 1) / (n_perm + 1)

        # Top-effect permutation p (uncorrected; exploratory).
        j = races.index(top["race"])
        observed = abs(top["diffLog2"])
        cnt = 0
        for _ in range(n_perm):
            idx = rng.permutation(len(y))
            aa = y[idx][P[:, j] == 1]
            bb = y[idx][P[:, j] == 0]
            if abs(float(aa.mean() - bb.mean())) >= observed - 1e-12:
                cnt += 1
        top_p = (cnt + 1) / (n_perm + 1)

        out.append(
            {
                "turn": int(t),
                "nGames": int(len(g)),
                "r2": r2,
                "adjR2": adj,
                "jointPermP": joint_p,
                "topRace": top["race"],
                "topDiffLog2": top["diffLog2"],
                "topT": top["t"],
                "topEffectPermP": top_p,
                "effects": tests,
            }
        )
    return out


def growth(df: pd.DataFrame, races: list[str]) -> dict:
    rows = []
    for gid, grp in df[(df["turn"] >= 5) & (df["turn"] <= 10)].groupby("gameId"):
        if grp["turn"].nunique() < 4:
            continue
        slope = float(np.polyfit(grp["turn"].to_numpy(float), grp["log2x50"].to_numpy(float), 1)[0])
        rows.append({"gameId": gid, "slope": slope, "races": grp["races"].iloc[0]})
    if not rows:
        return {"nGames": 0, "effects": {}}
    s = race_columns(pd.DataFrame(rows), races)
    out = {}
    for r in races:
        a = s.loc[s[r] == 1, "slope"]
        b = s.loc[s[r] == 0, "slope"]
        diff = float(a.mean() - b.mean())
        se = math.sqrt(a.var(ddof=1) / len(a) + b.var(ddof=1) / len(b))
        out[r] = {"nPresent": int(len(a)), "nAbsent": int(len(b)), "diffLog2PerTurn": diff, "se": se, "t": diff / se}
    return {"nGames": int(len(s)), "medianSlope": float(s["slope"].median()), "effects": out}


def split_feasibility(g: pd.DataFrame, races: list[str]) -> dict:
    pool_counts = collections.Counter(g["races"])
    rsets = [set(x) for x in g["races"]]
    n = len(g)

    # Exact race pools
    exact = {
        "uniquePools": len(pool_counts),
        "maxGamesPerPool": max(pool_counts.values()),
        "poolSizeDistribution": dict(sorted(collections.Counter(pool_counts.values()).items())),
    }

    # Jaccard components at a few thresholds
    components = {}
    for thr in (0.8, 0.6):
        seen = set()
        comps = []
        for i in range(n):
            if i in seen:
                continue
            stack = [i]
            seen.add(i)
            comp = []
            while stack:
                v = stack.pop()
                comp.append(v)
                for w in range(n):
                    if w in seen:
                        continue
                    jac = len(rsets[v] & rsets[w]) / len(rsets[v] | rsets[w])
                    if jac >= thr:
                        seen.add(w)
                        stack.append(w)
            comps.append(comp)
        components[str(thr)] = {
            "nComponents": len(comps),
            "maxSize": max(len(c) for c in comps),
            "sizes": sorted((len(c) for c in comps), reverse=True),
        }

    # Hierarchical clustering on Jaccard distance
    D = np.zeros((n, n))
    for i in range(n):
        for j in range(i + 1, n):
            jac = len(rsets[i] & rsets[j]) / len(rsets[i] | rsets[j])
            D[i, j] = D[j, i] = 1.0 - jac
    Z = linkage(squareform(D, checks=False), method="average")
    clusters = []
    y = g["res"].to_numpy(float)
    for k in range(2, 9):
        cl = fcluster(Z, k, criterion="maxclust")
        sizes = sorted(collections.Counter(cl.tolist()).values(), reverse=True)
        X = np.column_stack([np.ones(n)] + [(cl == c).astype(float) for c in sorted(set(cl))[1:]])
        beta = np.linalg.lstsq(X, y, rcond=None)[0]
        pred = X @ beta
        r2 = 1.0 - float(((y - pred) ** 2).sum() / ((y - y.mean()) ** 2).sum())
        adj = 1.0 - (1.0 - r2) * (n - 1) / max(1, n - X.shape[1])
        clusters.append({"k": k, "sizes": sizes, "r2": r2, "adjR2": adj})
    return {
        "exact": exact,
        "jaccardComponents": components,
        "hierarchicalClusters": clusters,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--curves", default=str(REPO / "spikes/dummy-ladder/out-adaptive-all/curves.json"))
    ap.add_argument("--turns", default=str(REPO / "data/standard/turns.jsonl"))
    ap.add_argument("--out", default=str(REPO / "spikes/race-x50/out"))
    ap.add_argument("--turns-min", type=int, default=5)
    ap.add_argument("--turns-max", type=int, default=12)
    ap.add_argument("--permutations", type=int, default=5000)
    ap.add_argument("--bootstrap", type=int, default=5000)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()

    df = load_joined(Path(args.curves), Path(args.turns), args.turns_min, args.turns_max)
    races = sorted({r for rs in df["races"] for r in rs})
    g = game_table(df, races)
    rng = np.random.default_rng(args.seed)

    r2, adj, beta = fit_race_model(g, races)
    perm_p = permutation_joint_p(g, races, r2, args.permutations, rng)
    singles = single_effects(g, races, args.bootstrap, args.permutations, rng)
    growth_res = growth(df, races)
    split = split_feasibility(g, races)

    between_var = float(g["res"].var(ddof=1))
    within_var = float(np.mean(df.groupby("gameId")["res"].var(ddof=1)))
    total_var = float(df["log2x50"].var(ddof=1))
    turn_res_var = float(df["res"].var(ddof=1))

    summary = {
        "inputs": {"curves": args.curves, "turns": args.turns, "turnsMin": args.turns_min, "turnsMax": args.turns_max},
        "coverage": {
            "boards": int(len(df)),
            "games": int(g["gameId"].nunique()),
            "turnBoardCounts": {int(k): int(v) for k, v in sorted(df["turn"].value_counts().items())},
            "bbGames": {str(k): int(v) for k, v in g["bb"].value_counts().items()},
            "heroes": int(g["hero"].nunique()),
            "races": races,
            "racePresenceGames": {r: int(g[r].sum()) for r in races},
            "exactPools": int(g["races"].nunique()),
            "poolSizeDistribution": dict(sorted(collections.Counter(collections.Counter(g["races"]).values()).items())),
        },
        "variance": {
            "totalLog2Var": total_var,
            "turnResidualVar": turn_res_var,
            "betweenGameResidualVar": between_var,
            "withinGameResidualVarMean": within_var,
            "betweenShareOfResidual": between_var / turn_res_var if turn_res_var else None,
        },
        "joint": {
            "r2": r2,
            "adjR2": adj,
            "permP": perm_p,
            "betaDropLastRace": beta,
            "lastRace": races[-1],
        },
        "singleRaceEffects": singles,
        "perTurn": per_turn(df, races, args.permutations, rng),
        "growth": growth_res,
        "splitFeasibility": split,
        "interpretation": {
            "turnEffectDominates": total_var > 0 and turn_res_var / total_var < 0.2,
            "betweenGameShare": between_var / turn_res_var if turn_res_var else None,
            "raceModelR2": r2,
            "raceModelAdjR2": adj,
            "raceModelPermP": perm_p,
        },
    }
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    g.to_csv(out / "games.csv", index=False)
    df.to_csv(out / "boards.csv", index=False)
    print(json.dumps({k: summary[k] for k in ("coverage", "variance", "joint")}, ensure_ascii=False, indent=2))
    print(f"wrote {out / 'summary.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
