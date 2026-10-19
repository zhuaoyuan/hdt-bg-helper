# -*- coding: utf-8 -*-
"""Model-based estimate of the dummy-ladder 50% point (log2 L logistic + CI).

Why this module
---------------
v1 read the 50% point off the first crossing of two adjacent rungs (linear
interpolation). That uses only two points, is sensitive to where the discrete
rungs happen to fall, and reports no uncertainty. This module fits a monotone
logistic in log2(level) to *all* sampled rungs, takes the fitted 0.5 point as
the estimate, and reports an asymptotic interval.

Model
-----
    s(L) = 1 / (1 + exp((log2 L - a) / b))          b > 0
    X50  = 2 ** a

where s(L) = P(win) + 0.5 * P(tie) over ``iterations`` Monte-Carlo games per
rung. The fit is a quasi-binomial logistic regression (IRLS): each rung is
``n`` games with fractional score ``s`` (a tie counts 0.5), and the working
weights are the binomial information ``n * p * (1-p)``. Saturated rungs
(s = 0 or 1) therefore carry little information instead of an inverse-variance
weight that would blow up at the boundaries.

The logistic is only a smooth monotone curve through the score points; it is
not a probability model of win/tie/loss. A nonparametric isotonic fit is also
reported as a shape diagnostic (``x50Isotonic``).

Pure stdlib (no numpy/scipy), same environment as the other spike scripts.

CLI
---
    python model_estimate.py --selftest
    python model_estimate.py --curves out-wide/curves.json --out out-wide/curves-model.json
"""
from __future__ import annotations

import argparse
import json
import math
import random
from dataclasses import dataclass
from pathlib import Path

CAP_LOG2 = 20.0          # 2^20 = 1,048,576 is the hard top of the ladder
_B_GRID = tuple(0.1 * (1.2 ** i) for i in range(21))   # 0.10 .. 3.83


@dataclass(frozen=True)
class Point:
    """One ladder rung for one board."""

    level: int
    wins: float
    ties: float
    losses: float

    @property
    def n(self) -> float:
        return float(self.wins + self.ties + self.losses)

    @property
    def score(self) -> float:
        n = self.n
        if n <= 0:
            return 0.0
        return (self.wins + 0.5 * self.ties) / n


@dataclass
class Fit:
    a: float          # log2 of the 50% point
    b: float          # logistic scale (>0)
    sse: float        # weighted sum of squared residuals
    n_points: int

    @property
    def x50(self) -> float:
        return 2.0 ** self.a


# ---------------------------------------------------------------------------
# basics


def predict(x: float, a: float, b: float) -> float:
    """Logistic score at x = log2(level)."""
    z = (x - a) / b
    if z > 40.0:
        return 0.0
    if z < -40.0:
        return 1.0
    return 1.0 / (1.0 + math.exp(z))


def _points(points) -> list[Point]:
    return [p for p in points if p.n > 0]


def _sse0(pts: list[Point], a: float, b: float) -> float:
    """Unweighted SSE, used only for the IRLS starting point."""
    total = 0.0
    for p in pts:
        d = p.score - predict(math.log2(p.level), a, b)
        total += d * d
    return total


def _initial_fit(pts: list[Point]) -> tuple[float, float]:
    xs = [math.log2(p.level) for p in pts]
    lo, hi = min(xs) - 2.0, max(xs) + 2.0
    best_v, best_a, best_b = math.inf, 0.0, 1.0
    a = lo
    while a <= hi + 1e-9:
        for b in _B_GRID:
            v = _sse0(pts, a, b)
            if v < best_v:
                best_v, best_a, best_b = v, a, b
        a += 0.2
    for _ in range(2):
        v0, a0, b0 = best_v, best_a, best_b
        for i in range(-8, 9):
            a = a0 + 0.025 * i
            for j in range(-8, 9):
                b = b0 * (1.0 + 0.03 * j)
                if b <= 0.02:
                    continue
                v = _sse0(pts, a, b)
                if v < best_v:
                    best_v, best_a, best_b = v, a, b
        if (best_v, best_a, best_b) == (v0, a0, b0):
            break
    return best_a, best_b


def _p_from_eta(eta: float) -> float:
    if eta > 40.0:
        return 1.0
    if eta < -40.0:
        return 0.0
    return 1.0 / (1.0 + math.exp(-eta))


def fit_logistic(points) -> Fit | None:
    """Quasi-binomial logistic fit by IRLS over log2(level).

    Each rung contributes ``n`` games with fractional score ``s`` (ties count
    0.5). The working weights are ``n * p * (1-p)``, so saturated rungs carry
    little information and no variance floor is needed.

    Parameterization used internally: ``p = logistic(beta0 + beta1 * x)`` with
    ``beta1 < 0`` (p decreases as x = log2(level) grows). The starting point is
    an unweighted grid fit, so the result does not depend on an arbitrary
    initial guess.
    """
    pts = _points(points)
    if len(pts) < 3:
        return None
    a0, b0 = _initial_fit(pts)
    beta0, beta1 = a0 / b0, -1.0 / b0
    for _ in range(100):
        s00 = s01 = s11 = t0 = t1 = 0.0
        for p in pts:
            x = math.log2(p.level)
            eta = beta0 + beta1 * x
            pr = _p_from_eta(eta)
            if pr <= 0.0 or pr >= 1.0:
                pr = min(1.0 - 1e-12, max(1e-12, pr))
            w = p.n * pr * (1.0 - pr)
            z = eta + (p.score - pr) / (pr * (1.0 - pr))
            s00 += w
            s01 += w * x
            s11 += w * x * x
            t0 += w * z
            t1 += w * z * x
        det = s00 * s11 - s01 * s01
        if det <= 1e-12 or s00 <= 0:
            break
        nb0 = (t0 * s11 - t1 * s01) / det
        nb1 = (t1 * s00 - t0 * s01) / det
        if not (math.isfinite(nb0) and math.isfinite(nb1)) or nb1 >= 0.0:
            break
        step = max(abs(nb0 - beta0), abs(nb1 - beta1))
        beta0, beta1 = nb0, nb1
        if step < 1e-9:
            break
    if beta1 >= 0.0:
        a, b = a0, b0
    else:
        a, b = -beta0 / beta1, -1.0 / beta1
    sse = 0.0
    for p in pts:
        d = p.score - predict(math.log2(p.level), a, b)
        sse += p.n * d * d
    return Fit(a, b, sse, len(pts))


def asymptotic_ci(fit: Fit, points) -> dict | None:
    """95% interval for the 50% point from the IRLS Fisher information.

    W = n * p * (1-p), Cov = (J' W J)^-1. Conditional on the realized rung
    design (a two-stage design; see the v2 design doc), not a bootstrap.
    """
    pts = _points(points)
    a00 = a01 = a11 = 0.0
    for p in pts:
        x = math.log2(p.level)
        pr = predict(x, fit.a, fit.b)
        g = pr * (1.0 - pr)
        w = p.n * g
        dz = (x - fit.a) / fit.b
        d_a = -g / fit.b                # d score / d a
        d_b = -g * dz / fit.b           # d score / d b
        a00 += w * d_a * d_a
        a01 += w * d_a * d_b
        a11 += w * d_b * d_b
    det = a00 * a11 - a01 * a01
    if det <= 1e-12 or a11 <= 0:
        return None
    var_a = a11 / det
    if var_a <= 0 or not math.isfinite(var_a):
        return None
    se = math.sqrt(var_a)
    lo = max(fit.a - 1.96 * se, -5.0)
    hi = min(fit.a + 1.96 * se, CAP_LOG2 + 5.0)
    return {"lo": 2.0 ** lo, "hi": 2.0 ** hi, "seLog2": se}


# ---------------------------------------------------------------------------
# alternative summaries (kept for comparison / diagnostics)


def x50_interp(points) -> float | None:
    """v1 primary: first >=0.5 -> <0.5 crossing, linear in log2(level)."""
    pts = sorted(_points(points), key=lambda p: p.level)
    if len(pts) < 2:
        return None
    scores = [p.score for p in pts]
    if scores[0] < 0.5 or scores[-1] >= 0.5:
        return None
    for i in range(len(pts) - 1):
        left, right = scores[i], scores[i + 1]
        if left >= 0.5 > right:
            span = left - right
            if span < 1e-9:
                return float(pts[i].level)
            t = (left - 0.5) / span
            x0 = math.log2(pts[i].level)
            x1 = math.log2(pts[i + 1].level)
            return 2.0 ** (x0 + t * (x1 - x0))
    return None


def isotonic_x50(points) -> tuple[float | None, int]:
    """Nonparametric shape check: PAVA (non-increasing) + 50% crossing."""
    pts = sorted(_points(points), key=lambda p: p.level)
    if len(pts) < 3:
        return None, 0
    blocks: list[list[float]] = []   # [value, weight, count]
    for p in pts:
        blocks.append([p.score, p.n, 1])
        while len(blocks) >= 2 and blocks[-2][0] < blocks[-1][0]:
            v2, w2, c2 = blocks.pop()
            v1, w1, c1 = blocks.pop()
            blocks.append([(v1 * w1 + v2 * w2) / (w1 + w2), w1 + w2, c1 + c2])
    fitted: list[float] = []
    for value, _w, count in blocks:
        fitted.extend([value] * int(count))
    for i in range(1, len(fitted)):
        if fitted[i - 1] >= 0.5 > fitted[i]:
            x0 = math.log2(pts[i - 1].level)
            x1 = math.log2(pts[i].level)
            t = (fitted[i - 1] - 0.5) / (fitted[i - 1] - fitted[i])
            return 2.0 ** (x0 + t * (x1 - x0)), len(blocks)
    return None, len(blocks)


def bracket(points) -> tuple[int, int] | None:
    """First adjacent pair with s >= 0.5 > s, by level."""
    pts = sorted(_points(points), key=lambda p: p.level)
    for i in range(len(pts) - 1):
        if pts[i].score >= 0.5 > pts[i + 1].score:
            return pts[i].level, pts[i + 1].level
    return None


def monotone(scores, tol: float = 0.05) -> bool:
    return all(b <= a + tol for a, b in zip(scores, scores[1:]))


# ---------------------------------------------------------------------------
# adaptive design


def _level_from_log2(x: float) -> int:
    x = max(0.0, min(float(x), CAP_LOG2))
    return max(1, int(round(2.0 ** x)))


def choose_levels(points, *, n: int = 4, stage: int = 1,
                  existing=None, lo: int = 1, hi: int = 1 << 20) -> list[int]:
    """Pick up to ``n`` new rungs.

    Stage 1: two geometric points inside the observed bracket (robust to a
    step-like curve) + two logistic targets (p=0.25, 0.75).
    Stage 2: two logistic targets around the current fit (p=0.4, 0.6).

    Placement uses the fit on already-sampled rungs; it never looks at the
    outcome of the rungs it proposes (a two-stage design).
    """
    pts = sorted(_points(points), key=lambda p: p.level)
    have = set(existing or ())
    chosen: list[int] = []

    def add(level: int, low: int | None = None, high: int | None = None) -> None:
        if len(chosen) >= n:
            return
        low = lo if low is None else low
        high = hi if high is None else high
        level = max(low, min(high, int(level)))
        # Nudge to the nearest free integer: at small levels the geometric
        # proposal rounds onto an already-sampled rung (e.g. bracket (1,4)).
        for candidate in (level, level - 1, level + 1, level - 2, level + 2,
                          level - 3, level + 3):
            if low <= candidate <= high and candidate not in have and candidate not in chosen:
                chosen.append(candidate)
                return

    br = bracket(pts)
    if br and stage == 1:
        l0, l1 = br
        x0, x1 = math.log2(l0), math.log2(l1)
        add(_level_from_log2(x0 + 0.5 * (x1 - x0)), l0 + 1, l1 - 1)
        add(_level_from_log2(x0 + 0.25 * (x1 - x0)), l0 + 1, l1 - 1)

    fit = fit_logistic(pts)
    targets = (0.25, 0.75) if stage == 1 else (0.4, 0.6)
    if fit is not None:
        for t in targets:
            add(_level_from_log2(fit.a + fit.b * math.log((1.0 - t) / t)))
    if len(chosen) < n and fit is not None:
        for t in (0.15, 0.85):
            add(_level_from_log2(fit.a + fit.b * math.log((1.0 - t) / t)))
    if len(chosen) < n and br:
        l0, l1 = br
        add(_level_from_log2(0.5 * (math.log2(l0) + math.log2(l1))), l0 + 1, l1 - 1)
    return sorted(chosen)


# ---------------------------------------------------------------------------
# summary


def median(values):
    xs = sorted(v for v in values if v is not None)
    if not xs:
        return None
    mid = len(xs) // 2
    return xs[mid] if len(xs) % 2 else 0.5 * (xs[mid - 1] + xs[mid])


def ranks(values):
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


def pearson(xs, ys):
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


def spearman(xs, ys):
    if len(xs) < 3:
        return None
    return pearson(ranks(xs), ranks(ys))


def estimate(points) -> dict:
    """All summaries for one board's sampled rungs."""
    pts = sorted(_points(points), key=lambda p: p.level)
    fit = fit_logistic(pts)
    ci = asymptotic_ci(fit, pts) if fit is not None else None
    iso, blocks = isotonic_x50(pts)
    interp = x50_interp(pts)
    return {
        "x50": None if fit is None else round(fit.x50, 3),
        "ci": None if ci is None else [round(ci["lo"], 3), round(ci["hi"], 3)],
        "seLog2": None if ci is None else round(ci["seLog2"], 4),
        "a": None if fit is None else round(fit.a, 4),
        "b": None if fit is None else round(fit.b, 4),
        "sse": None if fit is None else round(fit.sse, 4),
        "x50Interp": None if interp is None else round(interp, 3),
        "x50Isotonic": None if iso is None else round(iso, 3),
        "isotonicBlocks": blocks,
        "levels": [p.level for p in pts],
        "scores": [round(p.score, 4) for p in pts],
        "nPoints": len(pts),
        "sims": int(round(sum(p.n for p in pts))),
        "monotone": monotone([p.score for p in pts]),
    }


# ---------------------------------------------------------------------------
# re-score an existing curves.json (no new simulations)


def points_from_curve(row: dict, iterations: int = 500) -> list[Point]:
    """Rebuild pseudo-counts from the rounded scores in a v1 curves.json.

    The v1 file stores ``scores`` but not win/tie counts. Reconstructing
    wins = s*n and losses = (1-s)*n keeps the score exact; the variance is then
    s(1-s)/n (slightly larger than the true one when ties exist), so the CI is
    mildly conservative. Fine for an estimator comparison.
    """
    levels = row.get("levels") or []
    scores = row.get("scores") or []
    n = float(iterations)
    out: list[Point] = []
    for level, score in zip(levels, scores):
        s = min(1.0, max(0.0, float(score)))
        out.append(Point(int(level), s * n, 0.0, (1.0 - s) * n))
    return out


def rescore_curves(src: Path, dst: Path, iterations: int = 500) -> int:
    rows = json.loads(src.read_text(encoding="utf-8"))
    dst.parent.mkdir(parents=True, exist_ok=True)
    out = []
    for row in rows:
        pts = points_from_curve(row, iterations=iterations)
        if len(pts) < 3:
            continue
        est = estimate(pts)
        merged = dict(row)
        merged.update({
            "model": est,
            "x50Model": est["x50"],
            "x50ModelCi": est["ci"],
            # v1's ladder status (interior/below/above); a model value for a
            # censored board is an extrapolation and should be flagged.
            "modelCensored": row.get("x50Status") != "interior",
        })
        out.append(merged)
    dst.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    both = [r for r in out if r.get("x50Model") and r.get("x50")]
    rho = spearman([math.log2(r["x50Model"]) for r in both],
                   [math.log2(r["x50"]) for r in both])
    ratios = [abs(math.log2(r["x50Model"] / r["x50"])) for r in both]
    widths = []
    for r in out:
        ci = (r.get("model") or {}).get("ci")
        if ci and ci[0] > 0 and ci[1] > 0:
            widths.append(math.log2(ci[1] / ci[0]))
    med = median(ratios)
    print(f"boards={len(out)} paired={len(both)} "
          f"spearman(model, interp)={None if rho is None else round(rho, 4)}")
    print(f"median |log2 ratio|={None if med is None else round(med, 4)}"
          f" (x{None if med is None else round(2 ** med, 3)})"
          f" max={None if not ratios else round(max(ratios), 4)}"
          f" >10%={sum(1 for v in ratios if v > math.log2(1.10))}"
          f" >25%={sum(1 for v in ratios if v > math.log2(1.25))}")
    medw = median(widths)
    print(f"median CI width={None if medw is None else round(medw, 4)} log2"
          f" (x{None if medw is None else round(2 ** medw, 3)})")
    print(f"wrote {dst}")
    return 0


# ---------------------------------------------------------------------------
# self-test


def _synth_points(a: float, b: float, levels, n: int, rng: random.Random) -> list[Point]:
    pts: list[Point] = []
    for level in levels:
        p = predict(math.log2(level), a, b)
        wins = sum(1 for _ in range(n) if rng.random() < p)
        pts.append(Point(int(level), float(wins), 0.0, float(n - wins)))
    return pts


def selftest() -> int:
    """Synthetic recovery + CI coverage + adaptive placement sanity."""
    rng = random.Random(20261019)
    ok = True

    # 1. recovery of a known logistic
    a0, b0 = math.log2(64.0), 0.8
    levels = [4, 8, 16, 32, 64, 128, 256, 512]
    pts = _synth_points(a0, b0, levels, 2000, rng)
    fit = fit_logistic(pts)
    if fit is None:
        print("FAIL: fit is None on synthetic data")
        return 1
    err_a = abs(fit.a - a0)
    err_b = abs(fit.b - b0) / b0
    print(f"recovery: a {fit.a:.3f} (true {a0:.3f}, err {err_a:.3f}), "
          f"b {fit.b:.3f} (true {b0:.3f}, rel err {err_b:.3f})")
    ok &= err_a < 0.15 and err_b < 0.30

    # 2. CI coverage across independent noisy datasets
    cover = 0
    trials = 40
    for _ in range(trials):
        pts = _synth_points(a0, b0, levels, 500, rng)
        fit = fit_logistic(pts)
        ci = asymptotic_ci(fit, pts) if fit is not None else None
        if ci is not None and ci["lo"] <= 64.0 <= ci["hi"]:
            cover += 1
    rate = cover / trials
    print(f"CI coverage: {cover}/{trials}={rate:.2f} (target 0.85-1.00)")
    ok &= rate >= 0.85

    # 3. interp vs model on a densely sampled synthetic curve
    dense = [2, 3, 4, 5, 6, 8, 10, 12, 16, 20, 24, 32, 40, 48,
             64, 80, 96, 128, 192, 256]
    pts = _synth_points(a0, b0, dense, 2000, rng)
    m = fit_logistic(pts)
    i = x50_interp(pts)
    if m is None or i is None:
        print("FAIL: interp/model missing on dense curve")
        return 1
    ratio = max(m.x50, i) / min(m.x50, i)
    print(f"dense curve: model {m.x50:.2f} interp {i:.2f} ratio {ratio:.3f}")
    ok &= ratio < 1.25

    # 4. adaptive placement
    chosen = choose_levels(pts, n=4, stage=1)
    print(f"adaptive stage1 levels: {chosen}")
    ok &= len(chosen) == 4 and all(1 <= lv <= 1 << 20 for lv in chosen)

    # 5. exact 0/1 rungs must not blow up the fit or shrink the CI
    sat_levels = [2, 4, 8, 16, 32, 64, 128, 256, 512, 1024]
    sat: list[Point] = []
    for level in sat_levels:
        p = predict(math.log2(level), a0, b0)
        if p <= 0.02:
            sat.append(Point(level, 0.0, 0.0, 500.0))
        elif p >= 0.98:
            sat.append(Point(level, 500.0, 0.0, 0.0))
        else:
            wins = sum(1 for _ in range(500) if rng.random() < p)
            sat.append(Point(level, float(wins), 0.0, float(500 - wins)))
    f2 = fit_logistic(sat)
    ci2 = asymptotic_ci(f2, sat) if f2 is not None else None
    if f2 is None or ci2 is None:
        print("FAIL: saturated fit/ci missing")
        return 1
    err2 = abs(f2.a - a0)
    width2 = math.log2(ci2["hi"] / ci2["lo"])
    print(f"saturated: a {f2.a:.3f} (true {a0:.3f}, err {err2:.3f}), "
          f"CI width {width2:.3f} log2")
    ok &= err2 < 0.20 and width2 > 0.02

    print("SELFTEST", "PASSED" if ok else "FAILED")
    return 0 if ok else 1


# ---------------------------------------------------------------------------


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--selftest", action="store_true", help="run synthetic checks")
    ap.add_argument("--curves", type=Path, help="re-score a v1 curves.json")
    ap.add_argument("--out", type=Path, help="output path for --curves")
    ap.add_argument("--iterations", type=int, default=500,
                    help="simulations per rung used by the v1 curve file")
    args = ap.parse_args()

    if args.selftest:
        return selftest()
    if args.curves:
        out = args.out or args.curves.with_name(args.curves.stem + "-model.json")
        return rescore_curves(args.curves, out, iterations=args.iterations)
    ap.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
