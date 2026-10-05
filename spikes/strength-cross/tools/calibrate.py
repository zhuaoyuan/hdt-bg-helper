# -*- coding: utf-8 -*-
"""P3-T1 calibration experiments E1–E3 (E5 optional).

Reuses P3-T0 out_both pair set + ReplaySim --batch. Does not implement tools/strength.

Usage (from repo root):
  python spikes/strength-cross/tools/calibrate.py --e1 --baseline spikes/strength-cross/out_both
  python spikes/strength-cross/tools/calibrate.py --e2 --e3 --baseline spikes/strength-cross/out_both
  python spikes/strength-cross/tools/calibrate.py --e5 --baseline spikes/strength-cross/out_both
  python spikes/strength-cross/tools/calibrate.py --all
"""
from __future__ import annotations

import argparse
import json
import math
import os
import random
import statistics
import subprocess
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np

HERE = Path(__file__).resolve().parent
SPIKE = HERE.parent
REPO = SPIKE.parents[1]
sys.path.insert(0, str(REPO / "tools"))
sys.path.insert(0, str(HERE))

from cross_eval import (  # noqa: E402
    DEFAULT_BB_MAP,
    DEFAULT_EXE,
    DEFAULT_TURNS,
    build_cross_jobs,
    collect_boards,
    default_roots,
    load_bb_map,
    load_turns,
    run_batch,
    spearman,
)
from cross_input import score_of  # noqa: E402

DEFAULT_BASELINE = SPIKE / "out_both"
DEFAULT_OUT = SPIKE / "out_calibrate"


def expand(p: str) -> str:
    return os.path.expandvars(os.path.expanduser(p))


def pctile(arr: list[float] | np.ndarray, p: float) -> float | None:
    if len(arr) == 0:
        return None
    a = np.sort(np.asarray(arr, dtype=float))
    idx = min(len(a) - 1, max(0, int(round((p / 100.0) * (len(a) - 1)))))
    return float(a[idx])


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_results(path: Path) -> list[dict]:
    """Prefer .results.jsonl; fall back to cross_results.json."""
    if path.is_dir():
        jl = path / "cross_results.results.jsonl"
        js = path / "cross_results.json"
    elif path.name.endswith(".results.jsonl") or path.suffix == ".jsonl":
        jl, js = path, path.with_suffix(".json")
    else:
        jl = path.with_name(path.stem + ".results.jsonl")
        js = path
    if jl.is_file():
        out = []
        with jl.open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    out.append(json.loads(line))
        return out
    raw = load_json(js)
    return raw["results"] if isinstance(raw, dict) else raw


def load_baseline_bundle(baseline: Path) -> dict:
    pair_meta = load_json(baseline / "pair_meta.json")
    boards_idx = load_json(baseline / "boards_index.json")
    results = load_results(baseline)
    return {"pair_meta": pair_meta, "boards_idx": boards_idx, "results": results, "dir": baseline}


def is_ghost_board(board: dict) -> bool:
    if board.get("side") != "Opponent":
        return False
    inp = board.get("input") or {}
    hero = (inp.get("Opponent") or {}).get("Hero") or {}
    cid = str(hero.get("CardID") or hero.get("CardId") or "")
    return "KelThuzad" in cid


def game_time_key(gid: str) -> str:
    """gameId like 20261002_112126_xxx sorts chronologically."""
    return gid


def build_score_maps(
    pair_meta: list[dict],
    results: list[dict],
) -> tuple[dict[str, dict[str, float]], dict[str, dict[str, float]], dict[str, int]]:
    """Return (scores[cand][ref]=s, se2[cand][ref]=s(1-s)/n, sims[cand|ref])."""
    by_id = {r.get("id"): r for r in results if r.get("id")}
    scores: dict[str, dict[str, float]] = defaultdict(dict)
    se2: dict[str, dict[str, float]] = defaultdict(dict)
    sims: dict[str, int] = {}
    for m in pair_meta:
        r = by_id.get(m["id"])
        if not r or not r.get("ok"):
            continue
        s = float(score_of(r.get("winRate"), r.get("tieRate")))
        n = int(r.get("simulationCount") or 0)
        scores[m["candId"]][m["refId"]] = s
        p = min(max(s, 0.0), 1.0)
        se2[m["candId"]][m["refId"]] = (p * (1.0 - p) / n) if n > 0 else 0.25
        sims[m["id"]] = n
    return scores, se2, sims


def index_boards(boards_idx: list[dict]) -> dict[str, dict]:
    return {b["id"]: b for b in boards_idx}


def boards_by_turn(boards_idx: list[dict]) -> dict[int, list[dict]]:
    by: dict[int, list[dict]] = defaultdict(list)
    for b in boards_idx:
        by[int(b["turn"])].append(b)
    return by


def ordered_games(boards_idx: list[dict]) -> list[str]:
    return sorted({b["gameId"] for b in boards_idx}, key=game_time_key)


def panel_game_set(all_games: list[str], k: int | None) -> set[str]:
    if k is None or k >= len(all_games):
        return set(all_games)
    return set(all_games[:k])


def weighted_mean(vals: list[float], weights: list[float]) -> float | None:
    if not vals:
        return None
    sw = sum(weights)
    if sw <= 0:
        return None
    return sum(v * w for v, w in zip(vals, weights)) / sw


def round_robin_row(
    cand_id: str,
    *,
    turn: int,
    cand_game: str,
    scores: dict[str, dict[str, float]],
    se2: dict[str, dict[str, float]],
    board_by: dict[str, dict],
    by_turn: dict[int, list[dict]],
    panel_games: set[str],
    turn_slack: int = 0,
    w_relax: float = 0.5,
    mc_noise: bool = False,
    rng: np.random.Generator | None = None,
) -> dict | None:
    """Leave-one-game round-robin S/Q for one Player candidate (out_both schema).

    Peers for ranking = other Player boards with score rows in R.
    Opponent boards may appear in the opponent set O.
    """
    if cand_id not in scores:
        return None

    def board_weight(b: dict) -> float:
        return 1.0 if int(b["turn"]) == turn else w_relax

    pool_turns = range(turn - turn_slack, turn + turn_slack + 1)
    pool = [b for tt in pool_turns for b in by_turn.get(tt, [])]
    # R: not same game; panel filter applies to opponent set / peer set membership for ranking pool
    R = [b for b in pool if b["gameId"] != cand_game]
    if not R:
        return None

    # Opponent set O: panel ∩ R, and must have score from cand
    O = [
        b
        for b in R
        if b["gameId"] in panel_games and b["id"] in scores[cand_id]
    ]
    if not O:
        return None

    def s_val(cid: str, rid: str) -> float | None:
        sm = scores.get(cid)
        if not sm or rid not in sm:
            return None
        s = sm[rid]
        if mc_noise and rng is not None:
            var = se2.get(cid, {}).get(rid, 0.0)
            if var > 0:
                s = float(np.clip(s + rng.normal(0.0, math.sqrt(var)), 0.0, 1.0))
        return s

    # S(x)
    s_vals, s_ws = [], []
    for b in O:
        sv = s_val(cand_id, b["id"])
        if sv is None:
            continue
        s_vals.append(sv)
        s_ws.append(board_weight(b))
    S = weighted_mean(s_vals, s_ws)
    if S is None:
        return None

    # Peers: Player boards in R (have their own score rows). Panel not required for peer identity.
    peers = [b for b in R if b.get("side") == "Player" and b["id"] in scores and b["id"] != cand_id]
    peer_S = []
    peer_w = []
    for p in peers:
        # O_p = O excluding p's game
        vals, ws = [], []
        for b in O:
            if b["gameId"] == p["gameId"]:
                continue
            sv = s_val(p["id"], b["id"])
            if sv is None:
                continue
            vals.append(sv)
            ws.append(board_weight(b))
        sp = weighted_mean(vals, ws)
        if sp is None:
            continue
        peer_S.append(sp)
        peer_w.append(board_weight(p))

    if not peer_S:
        Q = None
    else:
        # weighted empirical CDF with half for ties
        num = 0.0
        den = sum(peer_w)
        for sp, w in zip(peer_S, peer_w):
            if sp < S:
                num += w
            elif sp == S:
                num += 0.5 * w
        Q = num / den if den > 0 else None

    n_games = len({b["gameId"] for b in R})
    return {
        "boardId": cand_id,
        "gameId": cand_game,
        "turn": turn,
        "S": S,
        "percentile": Q,
        "nGames": n_games,
        "nOpp": len(O),
        "nPeers": len(peer_S),
    }


def compute_all_Q(
    scores: dict[str, dict[str, float]],
    se2: dict[str, dict[str, float]],
    boards_idx: list[dict],
    *,
    panel_k: int | None = None,
    turn_slack: int = 0,
    w_relax: float = 0.5,
    candidate_turns: set[int] | None = None,
) -> dict[str, dict]:
    board_by = index_boards(boards_idx)
    by_turn = boards_by_turn(boards_idx)
    games = ordered_games(boards_idx)
    panel = panel_game_set(games, panel_k)
    out: dict[str, dict] = {}
    for cid, ref_map in scores.items():
        b = board_by.get(cid)
        if not b or b.get("side") != "Player":
            continue
        if candidate_turns is not None and int(b["turn"]) not in candidate_turns:
            continue
        row = round_robin_row(
            cid,
            turn=int(b["turn"]),
            cand_game=b["gameId"],
            scores=scores,
            se2=se2,
            board_by=board_by,
            by_turn=by_turn,
            panel_games=panel,
            turn_slack=turn_slack,
            w_relax=w_relax,
        )
        if row and row.get("percentile") is not None:
            out[cid] = row
    return out


def clustered_bootstrap_widths(
    scores: dict[str, dict[str, float]],
    se2: dict[str, dict[str, float]],
    boards_idx: list[dict],
    *,
    panel_k: int | None,
    B: int,
    seed: int,
    turn_slack: int = 0,
    w_relax: float = 0.5,
    mc_noise: bool = True,
    candidate_ids: list[str] | None = None,
) -> dict[str, float]:
    """Return boardId -> 95% CI width in percentile points."""
    rng = np.random.default_rng(seed)
    board_by = index_boards(boards_idx)
    by_turn = boards_by_turn(boards_idx)
    games = ordered_games(boards_idx)
    panel = panel_game_set(games, panel_k)

    if candidate_ids is None:
        candidate_ids = [
            cid
            for cid in scores
            if board_by.get(cid, {}).get("side") == "Player"
        ]

    # Precompute per-turn game lists for resampling R
    turn_games: dict[int, list[str]] = {}
    for t, blist in by_turn.items():
        turn_games[t] = sorted({b["gameId"] for b in blist}, key=game_time_key)

    widths: dict[str, float] = {}
    for cid in candidate_ids:
        b = board_by[cid]
        turn = int(b["turn"])
        cand_game = b["gameId"]
        # games available in pool turns excluding cand
        pool_turns = range(turn - turn_slack, turn + turn_slack + 1)
        avail = sorted(
            {
                g
                for tt in pool_turns
                for g in turn_games.get(tt, [])
                if g != cand_game
            },
            key=game_time_key,
        )
        if len(avail) < 3:
            continue
        boot_q = []
        for _ in range(B):
            # resample games with replacement → multiplicity weights via repeating boards
            sampled = [avail[i] for i in rng.integers(0, len(avail), size=len(avail))]
            # Build synthetic R by duplicating boards of sampled games (multiplicity)
            # Efficient approach: restrict panel/O/peers to sampled set with counts
            counts: dict[str, int] = defaultdict(int)
            for g in sampled:
                counts[g] += 1
            # Manually compute S/Q with game weights
            pool = [bb for tt in pool_turns for bb in by_turn.get(tt, [])]
            R = [bb for bb in pool if bb["gameId"] in counts]
            O = [
                bb
                for bb in R
                if bb["gameId"] in panel and bb["id"] in scores.get(cid, {})
            ]
            if not O:
                continue

            def board_w(bb: dict) -> float:
                w = float(counts[bb["gameId"]])
                if int(bb["turn"]) != turn:
                    w *= w_relax
                return w

            def s_val(c: str, rid: str) -> float | None:
                sm = scores.get(c)
                if not sm or rid not in sm:
                    return None
                s = sm[rid]
                if mc_noise:
                    var = se2.get(c, {}).get(rid, 0.0)
                    if var > 0:
                        s = float(np.clip(s + rng.normal(0.0, math.sqrt(var)), 0.0, 1.0))
                return s

            s_vals, s_ws = [], []
            for bb in O:
                sv = s_val(cid, bb["id"])
                if sv is None:
                    continue
                s_vals.append(sv)
                s_ws.append(board_w(bb))
            S = weighted_mean(s_vals, s_ws)
            if S is None:
                continue
            peers = [
                bb
                for bb in R
                if bb.get("side") == "Player" and bb["id"] in scores and bb["id"] != cid
            ]
            peer_S, peer_w = [], []
            for p in peers:
                vals, ws = [], []
                for bb in O:
                    if bb["gameId"] == p["gameId"]:
                        continue
                    sv = s_val(p["id"], bb["id"])
                    if sv is None:
                        continue
                    vals.append(sv)
                    ws.append(board_w(bb))
                sp = weighted_mean(vals, ws)
                if sp is None:
                    continue
                peer_S.append(sp)
                peer_w.append(board_w(p))
            if not peer_S:
                continue
            num = 0.0
            den = sum(peer_w)
            for sp, w in zip(peer_S, peer_w):
                if sp < S:
                    num += w
                elif sp == S:
                    num += 0.5 * w
            boot_q.append(num / den)
        if len(boot_q) >= 20:
            qs = sorted(boot_q)
            lo = qs[max(0, int(0.025 * len(qs)))]
            hi = qs[min(len(qs) - 1, int(0.975 * len(qs)))]
            widths[cid] = (hi - lo) * 100.0
    return widths


def delta_p95(base: dict[str, dict], other: dict[str, dict], key: str = "percentile") -> dict:
    diffs = []
    common = set(base) & set(other)
    for cid in common:
        a = base[cid].get(key)
        b = other[cid].get(key)
        if a is None or b is None:
            continue
        # percentile in [0,1] → points
        if key == "percentile":
            diffs.append(abs(a - b) * 100.0)
        else:
            diffs.append(abs(a - b))
    if not diffs:
        return {"n": 0}
    return {
        "n": len(diffs),
        "p50": pctile(diffs, 50),
        "p95": pctile(diffs, 95),
        "max": max(diffs),
        "mean": float(statistics.mean(diffs)),
    }


def S_spearman(base: dict[str, dict], other: dict[str, dict]) -> float | None:
    xs, ys = [], []
    for cid in set(base) & set(other):
        if base[cid].get("S") is None or other[cid].get("S") is None:
            continue
        xs.append(base[cid]["S"])
        ys.append(other[cid]["S"])
    return spearman(xs, ys)


def run_exe_batch(
    exe: Path,
    bb_dir: str,
    jobs_path: Path,
    out_dir: Path,
    *,
    iterations: int,
    max_duration: int,
) -> list[dict]:
    out_dir.mkdir(parents=True, exist_ok=True)
    cmd = [
        str(exe),
        "--bb-dir",
        bb_dir,
        "--batch",
        str(jobs_path),
        "--iterations",
        str(iterations),
        "--max-duration",
        str(max_duration),
    ]
    print(f"[batch] iters={iterations} jobs={jobs_path} -> {out_dir}", flush=True)
    t0 = time.perf_counter()
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    wall = time.perf_counter() - t0
    results: list[dict] = []
    for line in (proc.stdout or "").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            results.append(json.loads(line))
        except json.JSONDecodeError:
            results.append({"ok": False, "error": "bad_json", "detail": line[:200]})
    summary = {
        "wallSec": wall,
        "exitCode": proc.returncode,
        "jobsFile": str(jobs_path),
        "iterations": iterations,
        "maxDuration": max_duration,
        "results": len(results),
        "ok": sum(1 for r in results if r.get("ok")),
        "stderrTail": (proc.stderr or "")[-1500:],
    }
    (out_dir / "cross_results.json").write_text(
        json.dumps({"summary": summary, "results": results}, ensure_ascii=False),
        encoding="utf-8",
    )
    (out_dir / "cross_results.results.jsonl").write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in results) + ("\n" if results else ""),
        encoding="utf-8",
    )
    (out_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[batch] done wall={wall:.1f}s ok={summary['ok']}/{summary['results']}", flush=True)
    return results


def ensure_jobs_from_baseline(baseline: Path, boards_full: list[dict] | None = None) -> Path:
    jobs = baseline / "cross_results.jobs.jsonl"
    if jobs.is_file():
        return jobs
    raise FileNotFoundError(f"Missing jobs file: {jobs}")


def write_subset_jobs(src_jobs: Path, pair_ids: set[str], dest: Path) -> int:
    dest.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with src_jobs.open(encoding="utf-8") as fin, dest.open("w", encoding="utf-8") as fout:
        for line in fin:
            if not line.strip():
                continue
            # id is first field; parse minimally
            obj = json.loads(line)
            if obj.get("id") in pair_ids:
                fout.write(line if line.endswith("\n") else line + "\n")
                n += 1
    return n


def experiment_e1(
    baseline: Path,
    out_root: Path,
    *,
    exe: Path,
    bb_dir: str,
    tiers: list[int],
    truth_n: int,
    truth_iters: int,
    bootstrap_b: int,
    seed: int,
    skip_sim: bool,
) -> dict:
    bundle = load_baseline_bundle(baseline)
    pair_meta = bundle["pair_meta"]
    boards_idx = bundle["boards_idx"]
    base_results = bundle["results"]
    base_scores, base_se2, _ = build_score_maps(pair_meta, base_results)
    base_Q = compute_all_Q(base_scores, base_se2, boards_idx, panel_k=None)
    print(f"[E1] baseline Q rows={len(base_Q)} pairs={len(pair_meta)}", flush=True)

    e1_dir = out_root / "e1"
    e1_dir.mkdir(parents=True, exist_ok=True)
    jobs_path = ensure_jobs_from_baseline(baseline)

    # Truth subset
    rng = random.Random(seed)
    all_ids = [m["id"] for m in pair_meta]
    truth_ids = set(rng.sample(all_ids, min(truth_n, len(all_ids))))
    truth_jobs = e1_dir / f"truth_{truth_n}.jobs.jsonl"
    truth_out = e1_dir / f"truth_{truth_iters}"
    if not skip_sim and not (truth_out / "summary.json").is_file():
        n = write_subset_jobs(jobs_path, truth_ids, truth_jobs)
        print(f"[E1] truth jobs written n={n}", flush=True)
        run_exe_batch(
            exe,
            bb_dir,
            truth_jobs,
            truth_out,
            iterations=truth_iters,
            max_duration=max(truth_iters, 20000),
        )
    elif (truth_out / "summary.json").is_file():
        print(f"[E1] reuse truth results {truth_out}", flush=True)

    truth_cmp = {}
    if (truth_out / "cross_results.results.jsonl").is_file() or (truth_out / "cross_results.json").is_file():
        truth_res = load_results(truth_out)
        by_t = {r.get("id"): r for r in truth_res if r.get("ok")}
        by_b = {r.get("id"): r for r in base_results if r.get("ok")}
        abs_ds = []
        for pid in truth_ids:
            a, b = by_t.get(pid), by_b.get(pid)
            if not a or not b:
                continue
            sa = score_of(a.get("winRate"), a.get("tieRate"))
            sb = score_of(b.get("winRate"), b.get("tieRate"))
            abs_ds.append(abs(sa - sb))
        truth_cmp = {
            "n": len(abs_ds),
            "absDeltaS_p50": pctile(abs_ds, 50),
            "absDeltaS_p95": pctile(abs_ds, 95),
            "absDeltaS_mean": float(statistics.mean(abs_ds)) if abs_ds else None,
            "note": f"|s_4000 - s_{truth_iters}| on {truth_n}-pair subset",
        }

    # Bootstrap width for baseline (subsample candidates for speed if many)
    cand_ids = list(base_Q.keys())
    rng2 = random.Random(seed + 1)
    boot_cands = cand_ids if len(cand_ids) <= 120 else rng2.sample(cand_ids, 120)
    print(f"[E1] baseline clustered bootstrap B={bootstrap_b} nCand={len(boot_cands)}", flush=True)
    base_widths = clustered_bootstrap_widths(
        base_scores,
        base_se2,
        boards_idx,
        panel_k=None,
        B=bootstrap_b,
        seed=seed,
        mc_noise=True,
        candidate_ids=boot_cands,
    )
    base_width_med = pctile(list(base_widths.values()), 50)

    tier_reports = []
    chosen = None
    for it in tiers:
        tier_dir = e1_dir / f"iter_{it}"
        if not skip_sim and not (tier_dir / "summary.json").is_file():
            run_exe_batch(
                exe,
                bb_dir,
                jobs_path,
                tier_dir,
                iterations=it,
                max_duration=max(it, 1000),
            )
        else:
            print(f"[E1] reuse iter={it} {tier_dir}", flush=True)
        if not (tier_dir / "cross_results.results.jsonl").is_file() and not (
            tier_dir / "cross_results.json"
        ).is_file():
            tier_reports.append({"iterations": it, "error": "missing_results"})
            continue
        res = load_results(tier_dir)
        scores, se2, _ = build_score_maps(pair_meta, res)
        Qmap = compute_all_Q(scores, se2, boards_idx, panel_k=None)
        dQ = delta_p95(base_Q, Qmap, "percentile")
        sp = S_spearman(base_Q, Qmap)
        widths = clustered_bootstrap_widths(
            scores,
            se2,
            boards_idx,
            panel_k=None,
            B=bootstrap_b,
            seed=seed,
            mc_noise=True,
            candidate_ids=boot_cands,
        )
        w_med = pctile(list(widths.values()), 50)
        width_increase = None if (base_width_med is None or w_med is None) else (w_med - base_width_med)
        ok = (
            dQ.get("p95") is not None
            and dQ["p95"] <= 3.0
            and sp is not None
            and sp >= 0.99
            and width_increase is not None
            and width_increase <= 1.0
        )
        report = {
            "iterations": it,
            "deltaQ_pts": dQ,
            "spearmanS": sp,
            "bootWidthMedian_pts": w_med,
            "bootWidthIncrease_pts": width_increase,
            "passes": ok,
            "summary": load_json(tier_dir / "summary.json") if (tier_dir / "summary.json").is_file() else None,
        }
        tier_reports.append(report)
        print(
            f"[E1] iter={it} dQ_p95={dQ.get('p95')} spearmanS={sp} "
            f"widthMed={w_med} dWidth={width_increase} pass={ok}",
            flush=True,
        )
        if ok and chosen is None:
            chosen = it

    # also evaluate 4000 itself as trivial pass reference
    result = {
        "baselineIterations": 4000,
        "baselineQ_n": len(base_Q),
        "baselineBootWidthMedian_pts": base_width_med,
        "bootstrapB": bootstrap_b,
        "bootstrapCandidates": len(boot_cands),
        "truth": truth_cmp,
        "tiers": tier_reports,
        "chosenIterations": chosen,
        "rule": "|dQ| p95<=3 AND spearman(S)>=0.99 AND median boot width increase<=1; pick minimal tier",
        "peerNote": "Q ranks among Player peers only (out_both candidates are Player-side)",
    }
    (e1_dir / "report.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


def experiment_e2(
    baseline: Path,
    out_root: Path,
    *,
    Ks: list[int | None],
) -> dict:
    bundle = load_baseline_bundle(baseline)
    scores, se2, _ = build_score_maps(bundle["pair_meta"], bundle["results"])
    boards_idx = bundle["boards_idx"]
    full = compute_all_Q(scores, se2, boards_idx, panel_k=None)
    reports = []
    chosen = None
    for k in Ks:
        label = "all" if k is None else str(k)
        qm = compute_all_Q(scores, se2, boards_idx, panel_k=k)
        dQ = delta_p95(full, qm, "percentile")
        ok = dQ.get("p95") is not None and dQ["p95"] <= 3.0
        reports.append({"K": label, "deltaQ_pts": dQ, "passes": ok, "n": len(qm)})
        print(f"[E2] K={label} dQ_p95={dQ.get('p95')} pass={ok}", flush=True)
        if ok and k is not None and chosen is None:
            chosen = k
        if ok and k is None and chosen is None:
            chosen = None  # all
    # pick minimal finite K that passes; if only all passes, chosen stays None → "all"
    finite_pass = [r for r in reports if r["passes"] and r["K"] != "all"]
    if finite_pass:
        chosen = min(int(r["K"]) for r in finite_pass)
    else:
        chosen = "all"
    result = {
        "full_n": len(full),
        "nGames": len({b["gameId"] for b in boards_idx}),
        "rows": reports,
        "chosenK": chosen,
        "rule": "minimal K with |dQ| p95<=3 vs full panel",
    }
    d = out_root / "e2"
    d.mkdir(parents=True, exist_ok=True)
    (d / "report.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


def experiment_e3(
    baseline: Path,
    out_root: Path,
    *,
    turn_slack_scores: dict[str, dict[str, float]] | None,
    turn_slack_se2: dict[str, dict[str, float]] | None,
    Gs: list[int],
    w_candidates: list[float],
    repeats: int,
    seed: int,
    turns: range,
) -> dict:
    """G_min / L1 / w_relax calibration.

    If turn_slack score maps are provided (same-turn + ±1 pairs merged), evaluate L1;
    otherwise only L0 G_min.
    """
    bundle = load_baseline_bundle(baseline)
    scores0, se20, _ = build_score_maps(bundle["pair_meta"], bundle["results"])
    boards_idx = bundle["boards_idx"]
    board_by = index_boards(boards_idx)
    by_turn = boards_by_turn(boards_idx)

    # merge turn±1 scores if available
    if turn_slack_scores:
        scores_l1 = defaultdict(dict)
        se2_l1 = defaultdict(dict)
        for src_s, src_e in ((scores0, se20), (turn_slack_scores, turn_slack_se2 or {})):
            for c, rm in src_s.items():
                scores_l1[c].update(rm)
            for c, rm in src_e.items():
                se2_l1[c].update(rm)
        scores_l1 = {k: dict(v) for k, v in scores_l1.items()}
        se2_l1 = {k: dict(v) for k, v in se2_l1.items()}
        have_l1 = True
    else:
        scores_l1, se2_l1 = scores0, se20
        have_l1 = False

    full_L0 = compute_all_Q(scores0, se20, boards_idx, panel_k=None, turn_slack=0)
    # candidates on t4-t10
    cands = [
        cid
        for cid, row in full_L0.items()
        if int(row["turn"]) in turns
    ]
    rng = random.Random(seed)

    def downsample_Q(
        scores: dict,
        se2: dict,
        *,
        G: int,
        turn_slack: int,
        w_relax: float,
        cand_id: str,
    ) -> float | None:
        b = board_by[cand_id]
        turn = int(b["turn"])
        cand_game = b["gameId"]
        pool_turns = range(turn - turn_slack, turn + turn_slack + 1)
        avail_games = sorted(
            {
                bb["gameId"]
                for tt in pool_turns
                for bb in by_turn.get(tt, [])
                if bb["gameId"] != cand_game
            },
            key=game_time_key,
        )
        if len(avail_games) < G:
            return None
        picked = set(rng.sample(avail_games, G))
        # restrict boards_idx view via panel=picked and by filtering pool through panel_games
        row = round_robin_row(
            cand_id,
            turn=turn,
            cand_game=cand_game,
            scores=scores,
            se2=se2,
            board_by=board_by,
            by_turn=by_turn,
            panel_games=picked,  # also acts as R filter for O; peers still from full R
            turn_slack=turn_slack,
            w_relax=w_relax,
        )
        # For true downsample of R, need peers also restricted to picked games:
        if row is None:
            return None
        # Recompute with R restricted: temporarily filter by_turn
        filtered_by_turn: dict[int, list[dict]] = {}
        for tt, blist in by_turn.items():
            filtered_by_turn[tt] = [
                bb for bb in blist if bb["gameId"] in picked or bb["gameId"] == cand_game
            ]
        row2 = round_robin_row(
            cand_id,
            turn=turn,
            cand_game=cand_game,
            scores=scores,
            se2=se2,
            board_by=board_by,
            by_turn=filtered_by_turn,
            panel_games=picked,
            turn_slack=turn_slack,
            w_relax=w_relax,
        )
        return None if row2 is None else row2.get("percentile")

    g_errors: dict[int, list[float]] = {g: [] for g in Gs}
    l1_errors: dict[tuple[int, float], list[float]] = defaultdict(list)
    l0_vs_l1: dict[tuple[int, float], list[float]] = defaultdict(list)

    for G in Gs:
        for _rep in range(repeats):
            for cid in cands:
                q_full = full_L0[cid]["percentile"]
                q_l0 = downsample_Q(scores0, se20, G=G, turn_slack=0, w_relax=1.0, cand_id=cid)
                if q_l0 is None or q_full is None:
                    continue
                err0 = abs(q_l0 - q_full) * 100.0
                g_errors[G].append(err0)
                if have_l1:
                    for w in w_candidates:
                        q_l1 = downsample_Q(
                            scores_l1, se2_l1, G=G, turn_slack=1, w_relax=w, cand_id=cid
                        )
                        if q_l1 is None:
                            continue
                        err1 = abs(q_l1 - q_full) * 100.0
                        l1_errors[(G, w)].append(err1)
                        l0_vs_l1[(G, w)].append(err1 - err0)

    g_summary = []
    chosen_g = None
    for G in Gs:
        errs = g_errors[G]
        med = pctile(errs, 50) if errs else None
        g_summary.append(
            {
                "G": G,
                "n": len(errs),
                "absErrPts_p50": med,
                "absErrPts_p95": pctile(errs, 95) if errs else None,
                "passes_median_le_10": med is not None and med <= 10.0,
            }
        )
        if med is not None and med <= 10.0 and chosen_g is None:
            chosen_g = G
    print("[E3] G_min scan:", json.dumps(g_summary, ensure_ascii=False), flush=True)

    w_summary = []
    chosen_w = None
    enable_l1 = False
    if have_l1 and chosen_g is not None:
        # pick w with smallest median error at chosen_g; enable L1 if better than L0
        l0_med = next(x["absErrPts_p50"] for x in g_summary if x["G"] == chosen_g)
        best = None
        for w in w_candidates:
            errs = l1_errors[(chosen_g, w)]
            med = pctile(errs, 50) if errs else None
            delta = pctile(l0_vs_l1[(chosen_g, w)], 50) if l0_vs_l1[(chosen_g, w)] else None
            row = {
                "G": chosen_g,
                "w_relax": w,
                "n": len(errs),
                "absErrPts_p50": med,
                "vsL0_medianDeltaErrPts": delta,
                "betterThanL0": med is not None and l0_med is not None and med < l0_med,
            }
            w_summary.append(row)
            if med is not None and (best is None or med < best[0]):
                best = (med, w, row["betterThanL0"])
        if best:
            chosen_w = best[1]
            enable_l1 = bool(best[2])
        print("[E3] L1/w:", json.dumps(w_summary, ensure_ascii=False), flush=True)
    else:
        print("[E3] L1 skipped (no turn±1 scores yet)", flush=True)

    result = {
        "turns": f"{turns.start}-{turns.stop - 1}",
        "repeats": repeats,
        "nCandidates": len(cands),
        "haveL1scores": have_l1,
        "G_scan": g_summary,
        "chosen_G_min": chosen_g,
        "L1_w_scan": w_summary,
        "chosen_w_relax": chosen_w,
        "enable_L1": enable_l1,
        "rule": "G_min = minimal G with L0 median |dQ|<=10 pts; w_relax = argmin error; enable L1 only if better than L0",
    }
    d = out_root / "e3"
    d.mkdir(parents=True, exist_ok=True)
    (d / "report.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


def build_turn_slack_jobs(
    boards: list[dict],
    *,
    turns: set[int],
) -> tuple[list[dict], list[dict]]:
    """Jobs for refs at turn±1 only (exclude same-turn; baseline already has those)."""
    by_turn: dict[int, list[dict]] = defaultdict(list)
    for b in boards:
        by_turn[b["turn"]].append(b)
    jobs, meta = [], []
    for t in sorted(turns):
        cands = [b for b in by_turn.get(t, []) if b["side"] == "Player"]
        refs = [
            b
            for tt in (t - 1, t + 1)
            for b in by_turn.get(tt, [])
            if b["side"] in ("Player", "Opponent") and not is_ghost_board(b)
        ]
        for cand in cands:
            for ref in refs:
                if ref["gameId"] == cand["gameId"]:
                    continue
                jid = f"{cand['id']}||{ref['id']}"
                from cross_input import make_cross_input

                cross = make_cross_input(
                    cand["input"],
                    ref["input"],
                    player_side=cand["side"],
                    opp_side=ref["side"],
                )
                jobs.append({"id": jid, "input": cross})
                meta.append(
                    {
                        "id": jid,
                        "candId": cand["id"],
                        "refId": ref["id"],
                        "candGame": cand["gameId"],
                        "refGame": ref["gameId"],
                        "turn": t,
                        "candSide": cand["side"],
                        "refSide": ref["side"],
                        "refTurn": ref["turn"],
                    }
                )
    return jobs, meta


def experiment_e3_prepare_l1(
    out_root: Path,
    *,
    exe: Path,
    bb_dir: str,
    roots: list[str],
    bb_version: str,
    turns_path: Path,
    iterations: int,
    skip_sim: bool,
) -> tuple[dict[str, dict[str, float]], dict[str, dict[str, float]], list[dict]]:
    turns_by = load_turns(turns_path)
    boards = collect_boards(roots, bb_version, turns_by, max_turn=12)
    # filter ghosts from opponent
    boards = [b for b in boards if not is_ghost_board(b)]
    jobs, meta = build_turn_slack_jobs(boards, turns=set(range(4, 11)))
    d = out_root / "e3" / "turn_slack1"
    d.mkdir(parents=True, exist_ok=True)
    (d / "pair_meta.json").write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
    jobs_path = d / "jobs.jsonl"
    if not skip_sim and not (d / "summary.json").is_file():
        with jobs_path.open("w", encoding="utf-8") as f:
            for j in jobs:
                f.write(json.dumps(j, ensure_ascii=False) + "\n")
        print(f"[E3] turn±1 jobs={len(jobs)}", flush=True)
        run_exe_batch(
            exe,
            bb_dir,
            jobs_path,
            d,
            iterations=iterations,
            max_duration=max(iterations, 1000),
        )
    else:
        print(f"[E3] reuse turn±1 {d}", flush=True)
    res = load_results(d)
    scores, se2, _ = build_score_maps(meta, res)
    return scores, se2, boards


def experiment_e5(
    out_root: Path,
    *,
    exe: Path,
    bb_dir: str,
    roots: list[str],
    turns_path: Path,
    iterations: int,
    skip_sim: bool,
    seed: int,
) -> dict:
    """Cross-version: 1.85 candidates vs 1.81.2 refs, simulated with 1.85 DLL."""
    turns_by = load_turns(turns_path)
    boards_185 = [b for b in collect_boards(roots, "1.85.0.0", turns_by, 12) if not is_ghost_board(b)]
    boards_181 = [b for b in collect_boards(roots, "1.81.2.0", turns_by, 12) if not is_ghost_board(b)]
    print(
        f"[E5] 1.85 games={len({b['gameId'] for b in boards_185})} "
        f"1.81 games={len({b['gameId'] for b in boards_181})}",
        flush=True,
    )
    if not boards_181:
        return {"error": "no_1.81.2_boards", "enable_L2": False}

    by_turn_185: dict[int, list[dict]] = defaultdict(list)
    by_turn_181: dict[int, list[dict]] = defaultdict(list)
    for b in boards_185:
        by_turn_185[b["turn"]].append(b)
    for b in boards_181:
        by_turn_181[b["turn"]].append(b)

    # Same-turn cross: Player cand from 1.85 vs both sides from 1.81
    jobs, meta = [], []
    for t, cands in by_turn_185.items():
        refs = [b for b in by_turn_181.get(t, []) if b["side"] in ("Player", "Opponent")]
        for cand in cands:
            if cand["side"] != "Player":
                continue
            for ref in refs:
                jid = f"{cand['id']}||{ref['id']}"
                from cross_input import make_cross_input

                cross = make_cross_input(
                    cand["input"],
                    ref["input"],
                    player_side=cand["side"],
                    opp_side=ref["side"],
                )
                jobs.append({"id": jid, "input": cross})
                meta.append(
                    {
                        "id": jid,
                        "candId": cand["id"],
                        "refId": ref["id"],
                        "candGame": cand["gameId"],
                        "refGame": ref["gameId"],
                        "turn": t,
                        "candSide": cand["side"],
                        "refSide": ref["side"],
                    }
                )

    d = out_root / "e5"
    d.mkdir(parents=True, exist_ok=True)
    (d / "pair_meta.json").write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
    jobs_path = d / "jobs.jsonl"
    if not skip_sim and not (d / "summary.json").is_file():
        with jobs_path.open("w", encoding="utf-8") as f:
            for j in jobs:
                f.write(json.dumps(j, ensure_ascii=False) + "\n")
        print(f"[E5] cross-version jobs={len(jobs)}", flush=True)
        run_exe_batch(
            exe, bb_dir, jobs_path, d, iterations=iterations, max_duration=max(iterations, 1000)
        )
    else:
        print(f"[E5] reuse {d}", flush=True)

    # Pure 1.85 Q from baseline out_both if available, else compute from fresh same-version
    # For fair compare: for each 1.85 cand, Q against 1.81 refs vs Q against 1.85 refs (leave-one-game)
    # Load baseline 1.85 scores
    baseline = DEFAULT_BASELINE
    if not (baseline / "pair_meta.json").is_file():
        return {"error": "missing_1.85_baseline", "enable_L2": False}
    bundle = load_baseline_bundle(baseline)
    scores_185, se2_185, _ = build_score_maps(bundle["pair_meta"], bundle["results"])
    boards_idx_185 = bundle["boards_idx"]
    Q_pure = compute_all_Q(scores_185, se2_185, boards_idx_185, panel_k=None)

    res_x = load_results(d)
    scores_x, se2_x, _ = build_score_maps(meta, res_x)

    # Build synthetic boards_idx for cross: cand from 185 idx + refs from 181
    boards_idx_x = []
    seen = set()
    for b in boards_idx_185:
        boards_idx_x.append(b)
        seen.add(b["id"])
    for b in boards_181:
        if b["id"] not in seen:
            boards_idx_x.append(
                {
                    "id": b["id"],
                    "gameId": b["gameId"],
                    "turn": b["turn"],
                    "side": b["side"],
                    "label": b.get("label"),
                }
            )
            seen.add(b["id"])

    # For cross Q: only use scores_x (185 cand vs 181 refs). Peers also need scores among themselves —
    # we don't have 181-vs-181. Approximate: Q of cand vs 181-only opponent set, peers = other 185
    # Player cands scored against same 181 refs (all 181 games as panel).
    Q_cross: dict[str, dict] = {}
    board_by = index_boards(boards_idx_x)
    by_turn = boards_by_turn(boards_idx_x)
    games_181 = {b["gameId"] for b in boards_181}
    for cid in scores_x:
        b = board_by.get(cid)
        if not b or b.get("side") != "Player":
            continue
        row = round_robin_row(
            cid,
            turn=int(b["turn"]),
            cand_game=b["gameId"],
            scores=scores_x,
            se2=se2_x,
            board_by=board_by,
            by_turn=by_turn,
            panel_games=games_181,
            turn_slack=0,
        )
        # peers will be other 185 Player boards that also have scores_x rows
        if row and row.get("percentile") is not None:
            Q_cross[cid] = row

    dQ = delta_p95(Q_pure, Q_cross, "percentile")
    enable = dQ.get("p95") is not None and dQ["p95"] <= 5.0
    result = {
        "jobs": len(jobs),
        "Q_pure_n": len(Q_pure),
        "Q_cross_n": len(Q_cross),
        "deltaQ_pts": dQ,
        "enable_L2": enable,
        "rule": "|dQ| p95<=5 pts vs pure 1.85 Q",
        "iterations": iterations,
        "note": "1.81 boards as refs; simulated with 1.85 DLL; peers are 1.85 Player cands scored on same 1.81 panel",
    }
    (d / "report.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[E5] dQ_p95={dQ.get('p95')} enable_L2={enable}", flush=True)
    return result


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="P3-T1 strength calibration E1–E5")
    ap.add_argument("--baseline", default=str(DEFAULT_BASELINE))
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    ap.add_argument("--exe", default=str(DEFAULT_EXE))
    ap.add_argument("--bb-map", default=str(DEFAULT_BB_MAP))
    ap.add_argument("--bb-version", default="1.85.0.0")
    ap.add_argument("--turns", default=str(DEFAULT_TURNS))
    ap.add_argument("--root", action="append", default=None)
    ap.add_argument("--e1", action="store_true")
    ap.add_argument("--e2", action="store_true")
    ap.add_argument("--e3", action="store_true")
    ap.add_argument("--e5", action="store_true")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--skip-sim", action="store_true", help="Analyze only; reuse prior sim outputs")
    ap.add_argument("--e1-tiers", default="250,500,1000,2000")
    ap.add_argument("--truth-n", type=int, default=300)
    ap.add_argument("--truth-iters", type=int, default=20000)
    ap.add_argument("--bootstrap", type=int, default=200, help="Clustered bootstrap B for E1 width")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--e3-repeats", type=int, default=50)
    ap.add_argument("--sim-iterations", type=int, default=1000, help="Iters for E3 L1 / E5 new jobs")
    args = ap.parse_args(argv)

    do_e1 = args.e1 or args.all
    do_e2 = args.e2 or args.all
    do_e3 = args.e3 or args.all
    do_e5 = args.e5 or args.all
    if not (do_e1 or do_e2 or do_e3 or do_e5):
        print("Pass --e1/--e2/--e3/--e5 or --all", file=sys.stderr)
        return 2

    baseline = Path(args.baseline)
    out_root = Path(args.out)
    out_root.mkdir(parents=True, exist_ok=True)
    exe = Path(args.exe)
    bb_map = load_bb_map(Path(args.bb_map))
    bb_dir = bb_map.get(args.bb_version)
    if not bb_dir or not os.path.isfile(os.path.join(bb_dir, "BobsBuddy.dll")):
        print(f"No BobsBuddy.dll for {args.bb_version}: {bb_dir}", file=sys.stderr)
        return 2
    if (do_e1 or do_e3 or do_e5) and not args.skip_sim and not exe.is_file():
        print(f"ReplaySim missing: {exe}", file=sys.stderr)
        return 2

    roots = args.root or default_roots()
    summary: dict[str, Any] = {"baseline": str(baseline), "out": str(out_root)}

    if do_e1:
        tiers = [int(x) for x in args.e1_tiers.split(",") if x.strip()]
        summary["e1"] = experiment_e1(
            baseline,
            out_root,
            exe=exe,
            bb_dir=bb_dir,
            tiers=tiers,
            truth_n=args.truth_n,
            truth_iters=args.truth_iters,
            bootstrap_b=args.bootstrap,
            seed=args.seed,
            skip_sim=args.skip_sim,
        )

    if do_e2:
        summary["e2"] = experiment_e2(
            baseline, out_root, Ks=[10, 15, 20, 30, None]
        )

    if do_e3:
        # Prepare turn±1 sims at sim-iterations (often 1000 after E1 hint)
        turn_scores = turn_se2 = None
        try:
            turn_scores, turn_se2, _ = experiment_e3_prepare_l1(
                out_root,
                exe=exe,
                bb_dir=bb_dir,
                roots=roots,
                bb_version=args.bb_version,
                turns_path=Path(args.turns),
                iterations=args.sim_iterations,
                skip_sim=args.skip_sim,
            )
        except Exception as ex:  # noqa: BLE001
            print(f"[E3] turn±1 prepare failed: {ex}", flush=True)
        summary["e3"] = experiment_e3(
            baseline,
            out_root,
            turn_slack_scores=turn_scores,
            turn_slack_se2=turn_se2,
            Gs=[4, 6, 8, 12],
            w_candidates=[0.25, 0.5, 1.0],
            repeats=args.e3_repeats,
            seed=args.seed,
            turns=range(4, 11),
        )

    if do_e5:
        summary["e5"] = experiment_e5(
            out_root,
            exe=exe,
            bb_dir=bb_dir,
            roots=roots,
            turns_path=Path(args.turns),
            iterations=args.sim_iterations,
            skip_sim=args.skip_sim,
            seed=args.seed,
        )

    (out_root / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print("=== CALIBRATION SUMMARY ===", flush=True)
    print(json.dumps(summary, ensure_ascii=False, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
