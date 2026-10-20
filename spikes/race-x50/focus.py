# -*- coding: utf-8 -*-
"""Focused, pre-specified analysis: do a few high-impact tribes (UNDEAD, QUILBOAR)
present in the lobby race pool shift player X50 combat power?

This is the follow-up to ``analyze.py`` (which scanned all 10 tribes and all
turn x tribe cells).  Per owner guidance we do NOT scan all race-pool
combinations; we fix a small family before looking at effect sizes:

  * primary (confirmatory)   : UNDEAD, QUILBOAR  (owner-named high-impact tribes)
  * secondary (exploratory)  : MECHANICAL, PIRATE (the t8 lead from Q-023),
                               DRAGON (largest |effect| in the first screen)

Data: X50 from the dummy-ladder v2 adaptive run (all interior boards), race
pool from the standard layer ``rules.availableRaces``.  Race pool is constant
within a game, and every game has exactly 5 of the 10 tribes, so all race
effects are game-level and inference is clustered by game.

Estimators:
  * primary   : unweighted game mean of the within-turn residual of log2 X50
                (same as the first report, so the point estimates reproduce);
  * precision : inverse-variance weighted game mean using per-board CI
                (robustness to X50 measurement error);
  * reliable  : boards with narrow CI only (se <= 0.1), >=4 boards per game;
  * adjusted  : OLS with the other focused tribes + BB version + game order.

Uncertainty: game-level (cluster) bootstrap CIs and permutation p-values.
The analysis window t5-12 mirrors the first report (X50 is only usable from
t5 on); t9-12 and t11-12 are pre-specified late-game windows because these
tribes are scaling tribes, and t5-15 is a sensitivity window.

Run from the repo root:
  python spikes/race-x50/focus.py --bootstrap 10000 --permutations 10000
"""
from __future__ import annotations

import argparse
import json
import math
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

REPO = Path(__file__).resolve().parents[2]

ALL_RACES = [
    "ABERRATION",
    "BEAST",
    "DEMON",
    "DRAGON",
    "ELEMENTAL",
    "MECHANICAL",
    "MURLOC",
    "PIRATE",
    "QUILBOAR",
    "UNDEAD",
]
PRIMARY = ("UNDEAD", "QUILBOAR")
SECONDARY = ("MECHANICAL", "PIRATE", "DRAGON")
FOCUS = PRIMARY + SECONDARY
Z975 = 1.959963984540054
Z80 = 0.8416212335729143
# X50 measurement error is small relative to the real turn-to-turn variation of a
# board (~0.32 log2^2); weighting boards by 1/se^2 alone lets a handful of
# ultra-narrow-CI boards dominate a game mean.  The floor keeps all boards
# informative and only down-weights the clearly unusable ones.
TAU2_FLOOR = 0.25
SE_FILL = 0.7


# --------------------------------------------------------------------------- #
# data
# --------------------------------------------------------------------------- #
def load_joined(curves_path: Path, turns_path: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    curves = json.loads(curves_path.read_text(encoding="utf-8"))
    turns = [json.loads(line) for line in turns_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    tby = {(r["gameId"], int(r["turn"])): r for r in turns}
    rows = []
    for c in curves:
        if c.get("status") != "interior":
            continue
        turn = int(c["turn"])
        trow = tby.get((c["gameId"], turn))
        if not trow:
            continue
        rules = trow.get("rules") or {}
        races = tuple(sorted(rules.get("availableRaces") or []))
        x50 = float(c["x50"])
        ci = c.get("ci")
        se = None
        if ci and ci[0] and ci[1] and ci[0] > 0 and ci[1] > 0:
            se = (math.log2(ci[1]) - math.log2(ci[0])) / (2 * Z975)
        rows.append(
            {
                "gameId": c["gameId"],
                "turn": turn,
                "log2x50": math.log2(x50),
                "se": se,
                "races": races,
                "bb": (trow.get("meta") or {}).get("bbVersion"),
                "hero": trow.get("myHeroCard"),
                "placement": trow.get("placement"),
                "winRate": (trow.get("output") or {}).get("winRate"),
            }
        )
    boards = pd.DataFrame(rows)
    games = (
        boards.groupby("gameId", as_index=False)
        .agg(races=("races", "first"), bb=("bb", "first"), hero=("hero", "first"), placement=("placement", "first"))
        .sort_values("gameId")
        .reset_index(drop=True)
    )
    games["order"] = np.arange(len(games), dtype=float)
    games["orderZ"] = (games["order"] - games["order"].mean()) / max(games["order"].std(ddof=1), 1e-12)
    for r in ALL_RACES:
        games[r] = games["races"].apply(lambda s, r=r: int(r in s))
    gid_idx = {g: i for i, g in enumerate(games["gameId"])}
    boards["game_idx"] = boards["gameId"].map(gid_idx).astype(int)
    boards = boards.sort_values(["game_idx", "turn"]).reset_index(drop=True)
    return boards, games


def window_residuals(boards: pd.DataFrame, tmin: int, tmax: int) -> pd.DataFrame:
    """Within-turn residuals of log2 X50 for one analysis window."""
    b = boards[(boards["turn"] >= tmin) & (boards["turn"] <= tmax)].copy()
    if b.empty:
        raise SystemExit(f"empty window t{tmin}-{tmax}")
    b["tmean"] = b.groupby("turn")["log2x50"].transform("mean")
    b["res"] = b["log2x50"] - b["tmean"]
    return b


def game_outcome(b: pd.DataFrame, n_games: int, mode: str = "unweighted", se_max: float | None = None, min_boards: int = 1):
    """Per-game outcome; returns dict with y (nan for excluded games), n, weights."""
    bb = b
    if se_max is not None:
        bb = bb[bb["se"].notna() & (bb["se"] <= se_max)]
    y = np.full(n_games, np.nan)
    n = np.zeros(n_games)
    w = np.zeros(n_games)
    if bb.empty:
        return {"y": y, "n": n, "w": w}
    if mode == "unweighted":
        g = bb.groupby("game_idx")["res"].agg(["mean", "size"])
        g = g[g["size"] >= min_boards]
        y[g.index.values] = g["mean"].values
        n[g.index.values] = g["size"].values
    elif mode in ("floor", "ivw"):
        bw = bb.copy()
        se = bw["se"].fillna(SE_FILL).to_numpy(float)
        if mode == "floor":
            bw["w"] = 1.0 / (np.maximum(se, 0.002) ** 2 + TAU2_FLOOR)
        else:
            bw["w"] = 1.0 / np.maximum(se, 0.002) ** 2
        bw["wr"] = bw["w"] * bw["res"]
        g = bw.groupby("game_idx").agg(sw=("w", "sum"), swr=("wr", "sum"), cnt=("w", "size"))
        g = g[g["cnt"] >= min_boards]
        y[g.index.values] = (g["swr"] / g["sw"]).values
        n[g.index.values] = g["cnt"].values
        w[g.index.values] = g["sw"].values
    else:
        raise ValueError(mode)
    return {"y": y, "n": n, "w": w}


# --------------------------------------------------------------------------- #
# inference helpers (game-level / cluster)
# --------------------------------------------------------------------------- #
def _diff(y: np.ndarray, pres: np.ndarray, w: np.ndarray | None = None) -> float:
    p = pres == 1
    if w is None:
        return float(y[p].mean() - y[~p].mean())
    num_p = float((w[p] * y[p]).sum())
    den_p = float(w[p].sum())
    num_a = float((w[~p] * y[~p]).sum())
    den_a = float(w[~p].sum())
    return num_p / den_p - num_a / den_a


def _diff_matrix(yb: np.ndarray, P: np.ndarray, wb: np.ndarray | None = None) -> np.ndarray:
    """yb, P: (B, n) outcome and 0/1 presence per row."""
    if wb is None:
        sp = (P * yb).sum(1)
        cp = P.sum(1)
        sa = yb.sum(1) - sp
        ca = np.full(yb.shape[0], yb.shape[1], dtype=float) - cp
    else:
        wy = yb * wb
        sp = (P * wy).sum(1)
        cp = (P * wb).sum(1)
        sa = wy.sum(1) - sp
        ca = wb.sum(1) - cp
    return sp / cp - sa / ca


def diff_ci(y, pres, valid, weights=None, B=10000, rng=None):
    """Point estimate + bootstrap CI for present-vs-absent at game level."""
    rng = rng or np.random.default_rng(0)
    yv = y[valid]
    pv = pres[valid]
    wv = None if weights is None else weights[valid]
    obs = _diff(yv, pv, wv)
    n = len(yv)
    idx = rng.integers(0, n, size=(B, n))
    Pb = pv[idx]
    yb = yv[idx]
    wb = None if wv is None else wv[idx]
    boot = _diff_matrix(yb, Pb, wb)
    lo, hi = np.quantile(boot, [0.025, 0.975])
    return {
        "diffLog2": obs,
        "bootMedian": float(np.median(boot)),
        "bootSd": float(np.std(boot, ddof=1)),
        "ci95": [float(lo), float(hi)],
        "nPresent": int(pv.sum()),
        "nAbsent": int(n - pv.sum()),
        "boot": boot,
    }


def perm_p(y, pres, valid, weights=None, B=10000, rng=None):
    rng = rng or np.random.default_rng(1)
    yv = y[valid]
    pv = pres[valid]
    wv = None if weights is None else weights[valid]
    obs = abs(_diff(yv, pv, wv))
    n = len(yv)
    perms = np.argsort(rng.random((B, n)), axis=1)
    Pb = pv[perms]
    yb = np.broadcast_to(yv, (B, n))
    wb = None if wv is None else np.broadcast_to(wv, (B, n))
    d = _diff_matrix(yb, Pb, wb)
    return float((1 + np.sum(np.abs(d) >= obs - 1e-12)) / (B + 1))


def analytic_se(y, pres, weights=None) -> float:
    p = pres == 1
    if weights is None:
        vp = y[p].var(ddof=1) / max(p.sum(), 2)
        va = y[~p].var(ddof=1) / max((~p).sum(), 2)
    else:
        vp = 1.0 / weights[p].sum()
        va = 1.0 / weights[~p].sum()
    return float(math.sqrt(vp + va))


def bh_q(pvals: list[float]) -> list[float]:
    m = len(pvals)
    order = np.argsort(pvals)
    q = np.empty(m)
    prev = 1.0
    for rank, idx in reversed(list(enumerate(order))):
        val = pvals[idx] * m / (rank + 1)
        prev = min(prev, val)
        q[idx] = prev
    return [float(min(qi, 1.0)) for qi in q]


def bayes_summary(delta: float, se: float, thresholds=(0.07, 0.14), prior_sd=0.10) -> dict:
    """Normal-normal summaries: flat prior and a skeptical N(0, prior_sd^2) prior."""
    out = {"flat": {}, "skeptical": {}}
    for name, mean, sd in (
        ("flat", delta, se),
        ("skeptical", (delta / se**2) / (1 / se**2 + 1 / prior_sd**2), 1.0 / math.sqrt(1 / se**2 + 1 / prior_sd**2)),
    ):
        d = {"postMean": float(mean), "postSd": float(sd), "pPositive": float(stats.norm.cdf(mean / sd))}
        for thr in thresholds:
            d[f"pWithin{thr}"] = float(stats.norm.cdf((thr - mean) / sd) - stats.norm.cdf((-thr - mean) / sd))
            d[f"pAbove{thr}"] = float(1 - stats.norm.cdf((thr - mean) / sd))
        out[name] = d
    return out


# --------------------------------------------------------------------------- #
# analyses
# --------------------------------------------------------------------------- #
def window_effects(b, games, races, B, Bp, rng, weights=None, weighted_mode="floor", valid_extra=None):
    """Race effects for one window.  weights=None -> unweighted game means."""
    n_games = len(games)
    go = game_outcome(b, n_games, mode=weighted_mode if weights is not None else "unweighted")
    y = go["y"]
    valid = ~np.isnan(y)
    if valid_extra is not None:
        valid = valid & valid_extra
    out = {}
    for r in races:
        pres = games[r].to_numpy(int)
        e = diff_ci(y, pres, valid, weights=go["w"] if weights is not None else None, B=B, rng=rng)
        p = perm_p(y, pres, valid, weights=go["w"] if weights is not None else None, B=Bp, rng=rng)
        out[r] = {
            "diffLog2": e["diffLog2"],
            "ratio": float(2 ** e["diffLog2"]),
            "pct": float((2 ** e["diffLog2"] - 1) * 100),
            "ci95Log2": e["ci95"],
            "ci95Ratio": [float(2 ** e["ci95"][0]), float(2 ** e["ci95"][1])],
            "permP": p,
            "se": e["bootSd"],
            "nPresent": e["nPresent"],
            "nAbsent": e["nAbsent"],
        }
    return out, go


def tail_effects(y, pres, valid, rng, B=10000):
    p = pres[valid] == 1
    yv = y[valid]
    a, b = yv[p], yv[~p]
    qs = [0.1, 0.25, 0.5, 0.75, 0.9]
    obs = [float(np.quantile(a, q) - np.quantile(b, q)) for q in qs]
    n = len(yv)
    idx = rng.integers(0, n, size=(B, n))
    yb = yv[idx]
    pb = p[idx]
    boots = np.empty((B, len(qs)))
    for i in range(B):
        ai, bi = yb[i][pb[i]], yb[i][~pb[i]]
        boots[i] = [np.quantile(ai, q) - np.quantile(bi, q) for q in qs]
    cis = [list(np.quantile(boots[:, j], [0.025, 0.975])) for j in range(len(qs))]
    var_ratio = float(a.var(ddof=1) / b.var(ddof=1))
    br = []
    for _ in range(min(B, 2000)):
        ii = rng.integers(0, n, n)
        yy, pp = yv[ii], p[ii]
        va, vb = yy[pp].var(ddof=1), yy[~pp].var(ddof=1)
        br.append(va / vb)
    levene = stats.levene(a, b)
    return {
        "quantiles": qs,
        "diffLog2": obs,
        "ci95": cis,
        "varRatio": var_ratio,
        "varRatioCi95": [float(np.quantile(br, 0.025)), float(np.quantile(br, 0.975))],
        "leveneP": float(levene.pvalue),
        "meanPresent": float(a.mean()),
        "meanAbsent": float(b.mean()),
        "medianPresent": float(np.median(a)),
        "medianAbsent": float(np.median(b)),
    }


def group_contrasts(b, games, B, rng):
    """2x2 table (UNDEAD, QUILBOAR): neither / U only / Q only / both."""
    n_games = len(games)
    y = game_outcome(b, n_games, "unweighted")["y"]
    valid = ~np.isnan(y)
    u = games["UNDEAD"].to_numpy(int)
    q = games["QUILBOAR"].to_numpy(int)
    yv = y[valid]
    uv, qv = u[valid], q[valid]
    masks = {
        "neither": (uv == 0) & (qv == 0),
        "undeadOnly": (uv == 1) & (qv == 0),
        "quilboarOnly": (uv == 0) & (qv == 1),
        "both": (uv == 1) & (qv == 1),
    }
    obs = {k: (float(yv[m].mean()) if m.sum() else None) for k, m in masks.items()}
    obs_n = {k: int(m.sum()) for k, m in masks.items()}
    # interaction: both - undeadOnly - quilboarOnly + neither
    inter = obs["both"] - obs["undeadOnly"] - obs["quilboarOnly"] + obs["neither"]
    n = len(yv)
    idx = rng.integers(0, n, size=(B, n))
    yb = yv[idx]
    ub, qb = uv[idx], qv[idx]
    bs = {k: np.empty(B) for k in masks}
    inter_b = np.empty(B)
    for i in range(B):
        mm = {
            "neither": (ub[i] == 0) & (qb[i] == 0),
            "undeadOnly": (ub[i] == 1) & (qb[i] == 0),
            "quilboarOnly": (ub[i] == 0) & (qb[i] == 1),
            "both": (ub[i] == 1) & (qb[i] == 1),
        }
        for k, m in mm.items():
            bs[k][i] = yb[i][m].mean() if m.sum() else np.nan
        inter_b[i] = bs["both"][i] - bs["undeadOnly"][i] - bs["quilboarOnly"][i] + bs["neither"][i]
    out = {
        "groupMeans": {k: {"mean": obs[k], "n": obs_n[k], "ci95": [float(np.nanquantile(bs[k], 0.025)), float(np.nanquantile(bs[k], 0.975))]} for k in masks},
        "interactionLog2": float(inter),
        "interactionCi95": [float(np.nanquantile(inter_b, 0.025)), float(np.nanquantile(inter_b, 0.975))],
        "interactionP": float(2 * min(np.mean(inter_b <= 0), np.mean(inter_b >= 0))),
    }
    # burden: number of the two tribes present (0,1,2) -> linear trend
    burden = u + q
    obs_means = {}
    for k in (0, 1, 2):
        m = burden == k
        obs_means[str(k)] = float(y[m].mean()) if m.sum() else None
    # OLS slope on burden (simple linear trend)
    X = np.column_stack([np.ones(valid.sum()), burden[valid].astype(float)])
    beta = np.linalg.lstsq(X, yv, rcond=None)[0]
    boot_slopes = np.empty(B)
    for i in range(B):
        Xb = np.column_stack([np.ones(n), burden[idx[i]].astype(float)])
        boot_slopes[i] = np.linalg.lstsq(Xb, yb[i], rcond=None)[0][1]
    out["burdenMeans"] = obs_means
    out["burdenN"] = {str(k): int((burden == k).sum()) for k in (0, 1, 2)}
    out["burdenSlopeLog2PerTribe"] = float(beta[1])
    out["burdenSlopeCi95"] = [float(np.quantile(boot_slopes, 0.025)), float(np.quantile(boot_slopes, 0.975))]
    return out


def adjusted_model(b, games, B, rng):
    """y ~ U + Q + MECHANICAL + PIRATE + DRAGON + BB1.88.6 + game order."""
    n_games = len(games)
    y = game_outcome(b, n_games, "unweighted")["y"]
    valid = ~np.isnan(y)
    cols = ["UNDEAD", "QUILBOAR", "MECHANICAL", "PIRATE", "DRAGON"]
    X = np.column_stack(
        [np.ones(valid.sum())]
        + [games[c].to_numpy(float)[valid] for c in cols]
        + [(games["bb"].to_numpy() == "1.88.6.0").astype(float)[valid]]
        + [games["orderZ"].to_numpy(float)[valid]]
    )
    names = ["intercept"] + cols + ["bb1886", "orderZ"]
    yv = y[valid]
    beta = np.linalg.lstsq(X, yv, rcond=None)[0]
    n = len(yv)
    idx = rng.integers(0, n, size=(B, n))
    boots = np.empty((B, X.shape[1]))
    for i in range(B):
        boots[i] = np.linalg.lstsq(X[idx[i]], yv[idx[i]], rcond=None)[0]
    out = {}
    for j, nm in enumerate(names):
        out[nm] = {
            "coef": float(beta[j]),
            "ci95": [float(np.quantile(boots[:, j], 0.025)), float(np.quantile(boots[:, j], 0.975))],
        }
    return out


def board_level_model(b, games, races, B, rng):
    """Board-level OLS: res ~ turn FE + race presence; game-clustered bootstrap CI.

    Uses every board (no per-game averaging), so it is equivalent to a
    board-count-weighted game mean with a common turn adjustment.
    """
    turns = sorted(b["turn"].unique())
    turn_cols = [(b["turn"] == t).to_numpy(float) for t in turns[1:]]
    gi = b["game_idx"].to_numpy(int)
    res = b["res"].to_numpy(float)
    gidx = np.unique(gi)
    rows_by_game = {g: np.where(gi == g)[0] for g in gidx}
    out = {}
    for r in races:
        pres = games[r].to_numpy(int)[gi]
        X = np.column_stack([np.ones(len(b))] + turn_cols + [pres])
        beta = np.linalg.lstsq(X, res, rcond=None)[0]
        boot = []
        for _ in range(B):
            pick = rng.choice(gidx, size=len(gidx), replace=True)
            rows = np.concatenate([rows_by_game[g] for g in pick])
            try:
                bcoef = np.linalg.lstsq(X[rows], res[rows], rcond=None)[0]
            except np.linalg.LinAlgError:
                continue
            boot.append(bcoef[-1])
        boot = np.array(boot)
        out[r] = {
            "coefLog2": float(beta[-1]),
            "ci95Log2": [float(np.quantile(boot, 0.025)), float(np.quantile(boot, 0.975))],
            "nBoot": int(len(boot)),
        }
    return out


def growth_effects(b, games, B, rng):
    """Per-game slope of log2 X50 over t5-10 vs race presence."""
    bb = b[(b["turn"] >= 5) & (b["turn"] <= 10)]
    rows = []
    for gid, grp in bb.groupby("game_idx"):
        if grp["turn"].nunique() < 4:
            continue
        slope = float(np.polyfit(grp["turn"].to_numpy(float), grp["log2x50"].to_numpy(float), 1)[0])
        rows.append((int(gid), slope))
    if not rows:
        return {}
    idxs, slopes = zip(*rows)
    idxs = np.array(idxs)
    slopes = np.array(slopes)
    out = {}
    for r in PRIMARY:
        pres = games[r].to_numpy(int)[idxs]
        obs = float(slopes[pres == 1].mean() - slopes[pres == 0].mean())
        n = len(slopes)
        idx = rng.integers(0, n, size=(B, n))
        sb = slopes[idx]
        pb = pres[idx]
        sp = (sb * pb).sum(1) / pb.sum(1)
        sa = (sb * (1 - pb)).sum(1) / (1 - pb).sum(1)
        d = sp - sa
        out[r] = {
            "diffLog2PerTurn": obs,
            "ci95": [float(np.quantile(d, 0.025)), float(np.quantile(d, 0.975))],
            "nPresent": int(pres.sum()),
            "nAbsent": int((1 - pres).sum()),
            "medianSlope": float(np.median(slopes)),
        }
    return out


def trajectory_model(b, games, B, rng):
    """Board-level res ~ turn FE + race + race x turn(centered) for UNDEAD/QUILBOAR."""
    turns = sorted(b["turn"].unique())
    turn_dummies = [t for t in turns if t != turns[0]]
    Xparts = [np.ones(len(b))]
    for t in turn_dummies:
        Xparts.append((b["turn"] == t).to_numpy(float))
    tc = (b["turn"].to_numpy(float) - 8.0)
    gi = b["game_idx"].to_numpy(int)
    gidx = np.unique(gi)
    rows_by_game = {g: np.where(gi == g)[0] for g in gidx}
    out = {}
    for r in PRIMARY:
        pres = games[r].to_numpy(int)[gi]
        X = np.column_stack(Xparts + [pres, pres * tc])
        beta = np.linalg.lstsq(X, b["res"].to_numpy(float), rcond=None)[0]
        # cluster bootstrap by game
        boot = []
        for _ in range(B):
            pick = rng.choice(gidx, size=len(gidx), replace=True)
            rows = np.concatenate([rows_by_game[g] for g in pick])
            Xb, yb = X[rows], b["res"].to_numpy(float)[rows]
            try:
                bcoef = np.linalg.lstsq(Xb, yb, rcond=None)[0]
            except np.linalg.LinAlgError:
                continue
            boot.append((bcoef[-2], bcoef[-1]))
        boot = np.array(boot)
        out[r] = {
            "effectAtT8": float(beta[-2]),
            "effectAtT8Ci95": [float(np.quantile(boot[:, 0], 0.025)), float(np.quantile(boot[:, 0], 0.975))],
            "slopeDiffLog2PerTurn": float(beta[-1]),
            "slopeDiffCi95": [float(np.quantile(boot[:, 1], 0.025)), float(np.quantile(boot[:, 1], 0.975))],
            "nBoot": int(len(boot)),
        }
    return out


def confounding_checks(games, y, valid):
    out = {}
    # BB version vs presence (Fisher)
    for r in FOCUS:
        pres = games[r].to_numpy(int)
        v = (games["bb"].to_numpy() == "1.88.6.0").astype(int)
        tab = [[int(((v == 1) & (pres == 1)).sum()), int(((v == 0) & (pres == 1)).sum())],
               [int(((v == 1) & (pres == 0)).sum()), int(((v == 0) & (pres == 0)).sum())]]
        out.setdefault("bbVersion", {})[r] = {
            "table_1.88.6_present_absent": tab[0],
            "table_1.85_present_absent": tab[1],
            "fisherP": float(stats.fisher_exact(tab).pvalue),
        }
    # game order (time) balance
    out["gameOrder"] = {}
    for r in FOCUS:
        pres = games[r].to_numpy(int)
        mw = stats.mannwhitneyu(games.loc[pres == 1, "order"], games.loc[pres == 0, "order"])
        out["gameOrder"][r] = {"medianOrderPresent": float(games.loc[pres == 1, "order"].median()),
                               "medianOrderAbsent": float(games.loc[pres == 0, "order"].median()),
                               "mwuP": float(mw.pvalue)}
    # hero association (Cramer's V) for the focused races + permutation null
    out["heroAssociation"] = {}
    hero = games["hero"].fillna("NA").astype(str)
    rng = np.random.default_rng(7)

    def _v(pres: np.ndarray) -> float:
        tab = pd.crosstab(hero, pres).to_numpy()
        chi2, p, dof, _ = stats.chi2_contingency(tab)
        v = math.sqrt(chi2 / (tab.sum() * (min(tab.shape) - 1))) if min(tab.shape) > 1 else np.nan
        return float(v), float(p)

    for r in FOCUS:
        pres = games[r].to_numpy(int)
        v, p = _v(pres)
        null = np.array([_v(rng.permutation(pres))[0] for _ in range(1000)])
        out["heroAssociation"][r] = {
            "nHeroes": int(hero.nunique()),
            "cramersV": v,
            "chi2P": p,
            "permP": float((1 + np.sum(null >= v)) / 1001),
            "nullMedianV": float(np.median(null)),
        }
    # U-Q association
    u = games["UNDEAD"].to_numpy(int)
    q = games["QUILBOAR"].to_numpy(int)
    tab = np.array([[int(((u == 1) & (q == 1)).sum()), int(((u == 1) & (q == 0)).sum())],
                    [int(((u == 0) & (q == 1)).sum()), int(((u == 0) & (q == 0)).sum())]])
    out["undeadQuilboar"] = {"table": tab.tolist(), "fisherP": float(stats.fisher_exact(tab).pvalue),
                             "phi": float((tab[0, 0] * tab[1, 1] - tab[0, 1] * tab[1, 0]) /
                                          math.sqrt(tab.sum(1).prod() * tab.sum(0).prod()))}
    # boards per game vs presence
    out["boardsPerGame"] = {}
    for r in FOCUS:
        pres = games[r].to_numpy(int)
        mw = stats.mannwhitneyu(y["n"][pres == 1], y["n"][pres == 0])
        out["boardsPerGame"][r] = {"medianPresent": float(np.median(y["n"][pres == 1])),
                                   "medianAbsent": float(np.median(y["n"][pres == 0])),
                                   "mwuP": float(mw.pvalue)}
    # time trend / noisy-board count vs residual
    out["timeTrendSpearman"] = {
        "y_vs_gameOrder": float(stats.spearmanr(y["y"][valid], games["order"].to_numpy(float)[valid]).statistic),
        "y_vs_nBoards": float(stats.spearmanr(y["y"][valid], y["n"][valid]).statistic),
    }
    return out


def power_table(effects, targets=(0.07, 0.14, 0.21)) -> dict:
    out = {}
    for r, e in effects.items():
        se = e["se"]
        n_obs = max(e["nPresent"] + e["nAbsent"], 1)
        mde = (Z975 + Z80) * se
        out[r] = {
            "se": se,
            "mde80": mde,
            "mde80Pct": float((2 ** mde - 1) * 100),
            "nReq": {str(t): float(n_obs * (mde / t) ** 2) for t in targets},
        }
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--curves", default=str(REPO / "spikes/dummy-ladder/out-adaptive-all/curves.json"))
    ap.add_argument("--turns", default=str(REPO / "data/standard/turns.jsonl"))
    ap.add_argument("--out", default=str(REPO / "spikes/race-x50/out-focus"))
    ap.add_argument("--bootstrap", type=int, default=10000)
    ap.add_argument("--permutations", type=int, default=10000)
    ap.add_argument("--seed", type=int, default=20261020)
    args = ap.parse_args()

    boards, games = load_joined(Path(args.curves), Path(args.turns))
    n_games = len(games)
    rng = np.random.default_rng(args.seed)
    B = args.bootstrap
    Bp = args.permutations

    windows = {
        "main_t5_12": (5, 12),
        "balanced_t5_8": (5, 8),
        "early_t5_7": (5, 7),
        "mid_t8_10": (8, 10),
        "late_t9_12": (9, 12),
        "veryLate_t11_12": (11, 12),
        "sensitivity_t5_15": (5, 15),
    }

    results: dict = {
        "inputs": {"curves": args.curves, "turns": args.turns, "bootstrap": B, "permutations": Bp, "seed": args.seed},
        "coverage": {
            "boardsInterior": int(len(boards)),
            "games": int(n_games),
            "turnBoardCounts": {int(k): int(v) for k, v in boards["turn"].value_counts().sort_index().items()},
            "bbGames": {str(k): int(v) for k, v in games["bb"].value_counts().items()},
            "presenceGames": {r: int(games[r].sum()) for r in ALL_RACES},
        },
    }

    # --- main window, unweighted (reproduces the first report) ------------
    b_main = window_residuals(boards, 5, 12)
    main_eff, main_go = window_effects(b_main, games, ALL_RACES, B, Bp, rng)
    results["mainWindowUnweighted"] = main_eff
    results["mainWindowPower"] = power_table({r: main_eff[r] for r in FOCUS})
    results["mainWindowBayes"] = {
        r: bayes_summary(main_eff[r]["diffLog2"], main_eff[r]["se"]) for r in FOCUS
    }

    # BH: primary family (2 tests, Holm = BH for m=2), secondary family (3 tests)
    p_primary = [main_eff[r]["permP"] for r in PRIMARY]
    q_primary = bh_q(p_primary)
    p_secondary = [main_eff[r]["permP"] for r in SECONDARY]
    q_secondary = bh_q(p_secondary)
    results["multiplicity"] = {
        "primaryFamily": {r: {"p": p_primary[i], "qBH": q_primary[i]} for i, r in enumerate(PRIMARY)},
        "secondaryFamily": {r: {"p": p_secondary[i], "qBH": q_secondary[i]} for i, r in enumerate(SECONDARY)},
        "note": "primary = owner-named UNDEAD/QUILBOAR; secondary = Q-023 t8 lead + negative control; no scan over race combinations.",
    }

    # --- windows ----------------------------------------------------------
    results["windows"] = {}
    for name, (tmin, tmax) in windows.items():
        b = b_main if (tmin, tmax) == (5, 12) else window_residuals(boards, tmin, tmax)
        eff, go = window_effects(b, games, FOCUS, B, Bp, rng)
        results["windows"][name] = {
            "turns": [tmin, tmax],
            "nBoards": int(len(b)),
            "gamesWithData": int(np.sum(~np.isnan(go["y"]))),
            "effects": eff,
        }

    # --- robustness to X50 measurement quality ---------------------------
    # (a) drop boards with missing or wide CI; game mean stays unweighted.
    go_trim = game_outcome(b_main, n_games, "unweighted", se_max=0.5)
    valid_trim = ~np.isnan(go_trim["y"])
    eff_trim = {}
    for r in FOCUS:
        pres = games[r].to_numpy(int)
        e = diff_ci(go_trim["y"], pres, valid_trim, B=B, rng=rng)
        p = perm_p(go_trim["y"], pres, valid_trim, B=Bp, rng=rng)
        eff_trim[r] = {"diffLog2": e["diffLog2"], "ci95Log2": e["ci95"], "permP": p,
                       "nPresent": e["nPresent"], "nAbsent": e["nAbsent"]}
    results["trimUnreliable"] = {
        "gamesUsed": int(valid_trim.sum()),
        "note": ("boards with se>0.5 or missing CI dropped. The dropped fraction is turn-dependent "
                 "(t5 ~50%, t8 ~9%) and only MECHANICAL shows a count imbalance (17.1% vs 23.5%); "
                 "it is a descriptive sensitivity, not a like-for-like comparison."),
        "effects": eff_trim,
    }

    # (b) down-weight only clearly noisy boards: w = 1/(se^2 + TAU2_FLOOR).
    go_floor = game_outcome(b_main, n_games, "floor")
    eff_floor, _ = window_effects(b_main, games, FOCUS, B, Bp, rng, weights=True)
    results["floorWeighted"] = {
        "gamesUsed": int(np.sum(~np.isnan(go_floor["y"]))),
        "note": "game mean weighted by 1/(se^2+0.25); floor prevents ultra-narrow-CI boards from dominating.",
        "effects": eff_floor,
    }

    # (c) board-level model with turn fixed effects (uses all boards).
    results["boardLevelModel"] = board_level_model(b_main, games, FOCUS, min(B, 3000), rng)

    # --- adjusted model (other focused races + version + time) -----------
    results["adjustedModel"] = adjusted_model(b_main, games, 3000, rng)

    # --- 2x2 / burden -----------------------------------------------------
    results["undeadXQuilboar"] = group_contrasts(b_main, games, B, rng)

    # --- tails ------------------------------------------------------------
    y_main = game_outcome(b_main, n_games, "unweighted")["y"]
    valid_main = ~np.isnan(y_main)
    results["tails"] = {r: tail_effects(y_main, games[r].to_numpy(int), valid_main, rng, B=B) for r in PRIMARY}

    # --- growth / trajectory ---------------------------------------------
    results["growthSlope"] = growth_effects(boards, games, B, rng)
    results["trajectory"] = trajectory_model(b_main, games, min(B, 3000), rng)

    # --- t8 lead re-estimate (same data; NOT independent confirmation) ----
    b_t8 = window_residuals(boards, 8, 8)
    eff_t8, _ = window_effects(b_t8, games, SECONDARY, B, Bp, rng)
    results["t8LeadReestimate"] = {
        "note": "Same 112 games that generated Q-023; this is a re-estimate, not independent confirmation.",
        "effects": eff_t8,
    }

    # --- version split (UNDEAD/QUILBOAR only) -----------------------------
    results["versionSplit"] = {}
    for bbv, mask in (("1.85.0.0", games["bb"].to_numpy() == "1.85.0.0"), ("1.88.6.0", games["bb"].to_numpy() == "1.88.6.0")):
        y = y_main.copy()
        valid_v = valid_main & mask
        eff = {}
        for r in PRIMARY:
            pres = games[r].to_numpy(int)
            e = diff_ci(y, pres, valid_v, B=B, rng=rng)
            p = perm_p(y, pres, valid_v, B=B, rng=rng)
            eff[r] = {"diffLog2": e["diffLog2"], "ci95Log2": e["ci95"], "permP": p,
                      "nPresent": e["nPresent"], "nAbsent": e["nAbsent"]}
        results["versionSplit"][bbv] = {"games": int(mask.sum()), "effects": eff}

    # --- confounding checks ---------------------------------------------
    results["confounding"] = confounding_checks(games, {"y": y_main, "n": game_outcome(b_main, n_games)["n"]}, valid_main)

    # --- per-turn descriptive (UNDEAD/QUILBOAR) ---------------------------
    per_turn = {}
    for t in range(5, 13):
        bt = window_residuals(boards, t, t)
        yt = game_outcome(bt, n_games)["y"]
        validt = ~np.isnan(yt)
        per_turn[str(t)] = {}
        for r in PRIMARY:
            pres = games[r].to_numpy(int)
            e = diff_ci(yt, pres, validt, B=min(B, 4000), rng=rng)
            per_turn[str(t)][r] = {"diffLog2": e["diffLog2"], "ci95Log2": e["ci95"],
                                   "nPresent": e["nPresent"], "nAbsent": e["nAbsent"]}
    results["perTurnDescriptive"] = per_turn

    # --- write ------------------------------------------------------------
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "focus.json").write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    games.to_csv(out / "games_focus.csv", index=False)
    b_main.to_csv(out / "boards_focus.csv", index=False)

    # console summary
    print(f"games={n_games} boards(t5-12)={len(b_main)}")
    print("\n== main window t5-12 (unweighted game means) ==")
    for r in FOCUS + tuple(x for x in ALL_RACES if x not in FOCUS):
        e = main_eff[r]
        print(f"  {r:11s} n={e['nPresent']:3d}/{e['nAbsent']:3d}  d={e['diffLog2']:+.3f} log2 "
              f"({e['pct']:+.1f}%)  CI [{e['ci95Log2'][0]:+.3f},{e['ci95Log2'][1]:+.3f}]  p={e['permP']:.3f}")
    print("\n== primary multiplicity (BH) ==")
    print(json.dumps(results["multiplicity"], ensure_ascii=False, indent=1))
    print("\n== windows (UNDEAD/QUILBOAR) ==")
    for name, w in results["windows"].items():
        print(f"  {name:18s} games={w['gamesWithData']:3d}")
        for r in FOCUS:
            e = w["effects"][r]
            print(f"     {r:9s} d={e['diffLog2']:+.3f}  CI [{e['ci95Log2'][0]:+.3f},{e['ci95Log2'][1]:+.3f}]  p={e['permP']:.3f}")
    print("\n== power (main window) ==")
    print(json.dumps(results["mainWindowPower"], ensure_ascii=False, indent=1))
    print("\n== bayes (main window) ==")
    print(json.dumps(results["mainWindowBayes"], ensure_ascii=False, indent=1))
    print("\n== U x Q 2x2 / burden ==")
    print(json.dumps({k: v for k, v in results["undeadXQuilboar"].items()}, ensure_ascii=False, indent=1))
    print("\n== tails ==")
    print(json.dumps(results["tails"], ensure_ascii=False, indent=1))
    print("\n== robustness: trim / floor-weighted / board-level ==")
    print(json.dumps({"trim": results["trimUnreliable"], "floor": results["floorWeighted"],
                      "boardLevel": results["boardLevelModel"]}, ensure_ascii=False, indent=1))
    print("\n== adjusted ==")
    print(json.dumps(results["adjustedModel"], ensure_ascii=False, indent=1))
    print("\n== version split ==")
    print(json.dumps(results["versionSplit"], ensure_ascii=False, indent=1))
    print("\n== confounding ==")
    print(json.dumps(results["confounding"], ensure_ascii=False, indent=1))
    print(f"\nwrote {out/'focus.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
