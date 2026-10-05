# -*- coding: utf-8 -*-
"""P3-T0: cross-simulate boards, compute S(x)/percentile, bootstrap & correlations.

Usage:
  python cross_eval.py --smoke
  python cross_eval.py --run
  python cross_eval.py --analyze-only spikes/strength-cross/out/run-...
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

HERE = Path(__file__).resolve().parent
SPIKE = HERE.parent
REPO = SPIKE.parents[1]
sys.path.insert(0, str(REPO / "tools"))
sys.path.insert(0, str(HERE))

from cross_input import make_cross_input, score_of  # noqa: E402
from standard_layer.combat import discover_games, iter_game_combats, load_meta  # noqa: E402

DEFAULT_EXE = REPO / "tools" / "ReplaySim" / "bin" / "run" / "ReplaySim.exe"
DEFAULT_BB_MAP = REPO / "tools" / "ReplaySim" / "bb-dirs.json"
DEFAULT_TURNS = REPO / "data" / "standard" / "turns.jsonl"


def expand(p: str) -> str:
    return os.path.expandvars(os.path.expanduser(p))


def load_bb_map(path: Path) -> dict[str, str]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    out: dict[str, str] = {}
    for k, v in raw.items():
        ver = k.split(":", 1)[0]
        expanded = expand(v)
        if ver not in out and os.path.isfile(os.path.join(expanded, "BobsBuddy.dll")):
            out[ver] = expanded
        elif ver not in out:
            out[ver] = expanded
    return out


def default_roots() -> list[str]:
    return [
        str(REPO / "data" / "BgHelperDiag"),
        expand(r"%APPDATA%\HearthstoneDeckTracker\BgHelperDiag"),
    ]


def load_turns(path: Path) -> dict[tuple[str, int], dict]:
    by: dict[tuple[str, int], dict] = {}
    if not path.is_file():
        return by
    with path.open(encoding="utf-8") as f:
        for line in f:
            row = json.loads(line)
            t = row.get("turn")
            if t is None:
                continue
            by[(row["gameId"], int(t))] = row
    return by


def board_id(game_id: str, turn: int, side: str) -> str:
    return f"{game_id}|t{turn}|{side}"


def collect_boards(
    roots: list[str],
    bb_version: str,
    turns_by: dict[tuple[str, int], dict],
    max_turn: int | None,
) -> list[dict]:
    games = discover_games(roots)
    boards: list[dict] = []
    for gid, gdir in sorted(games.items()):
        meta = load_meta(gdir)
        bb = (meta.get("bobsBuddy") or {}).get("fileVersion") or (meta.get("bobsBuddy") or {}).get(
            "version"
        )
        if str(bb) != bb_version:
            continue
        if meta.get("isBattlegroundsDuosMatch"):
            continue
        try:
            _, _, combats = iter_game_combats(gdir)
        except Exception as ex:  # noqa: BLE001
            print(f"[skip] {gid}: {ex}", file=sys.stderr)
            continue
        for c in combats:
            inp = c.get("input")
            turn = c.get("turn")
            if not inp or turn is None or not c.get("hasOutput"):
                continue
            if max_turn is not None and int(turn) > max_turn:
                continue
            row = turns_by.get((gid, int(turn)))
            # Prefer standard-layer ready; if missing row, accept combat with output.
            if row is not None and row.get("status") not in (None, "ready"):
                continue
            if row is None and not (c.get("hasInput") and c.get("hasOutput")):
                continue
            out_sum = c.get("outputSummary") or {}
            label = {
                "result": (row or {}).get("result"),
                "damage": (row or {}).get("damage"),
                "resultSource": (row or {}).get("resultSource"),
                "hdtWin": (out_sum.get("winRate") if out_sum else None)
                or ((row or {}).get("output") or {}).get("winRate"),
                "hdtTie": (out_sum.get("tieRate") if out_sum else None)
                or ((row or {}).get("output") or {}).get("tieRate"),
                "hdtLoss": (out_sum.get("lossRate") if out_sum else None)
                or ((row or {}).get("output") or {}).get("lossRate"),
                "placement": (row or {}).get("placement"),
            }
            for side in ("Player", "Opponent"):
                if not isinstance(inp.get(side), dict):
                    continue
                boards.append(
                    {
                        "id": board_id(gid, int(turn), side),
                        "gameId": gid,
                        "turn": int(turn),
                        "side": side,
                        "input": inp,
                        "output": out_sum,
                        "label": label,
                        "gameDir": gdir,
                    }
                )
    return boards


def binomial_se(p: float, n: int) -> float:
    if n <= 0:
        return 1.0
    p = min(max(p, 0.0), 1.0)
    return math.sqrt(p * (1.0 - p) / n)


def rates_within_3sigma(rec: dict, sim: dict) -> bool:
    n1 = int(rec.get("simulationCount") or 0)
    n2 = int(sim.get("simulationCount") or 0)
    for key in ("winRate", "tieRate", "lossRate"):
        p1 = float(rec.get(key) or 0.0)
        p2 = float(sim.get(key) or 0.0)
        se = math.sqrt(binomial_se(p1, n1) ** 2 + binomial_se(p2, n2) ** 2)
        floor = 3.0 * math.sqrt(0.5 * (1.0 / max(n1, 1) + 1.0 / max(n2, 1)))
        limit = max(3.0 * se, floor) if se > 0 else max(1e-6, floor)
        if abs(p1 - p2) > limit + 1e-12:
            return False
    return True


def run_batch(
    exe: Path,
    bb_dir: str,
    jobs: list[dict],
    out_path: Path,
    *,
    iterations: int,
    threads: int | None,
    max_duration: int,
) -> list[dict]:
    jobs_path = out_path.with_suffix(".jobs.jsonl")
    with jobs_path.open("w", encoding="utf-8") as f:
        for j in jobs:
            f.write(json.dumps(j, ensure_ascii=False) + "\n")

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
    if threads is not None:
        cmd.extend(["--threads", str(threads)])

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
        "jobs": len(jobs),
        "results": len(results),
        "ok": sum(1 for r in results if r.get("ok")),
        "stderrTail": (proc.stderr or "")[-1000:],
    }
    out_path.write_text(json.dumps({"summary": summary, "results": results}, ensure_ascii=False, indent=2), encoding="utf-8")
    (out_path.with_suffix(".results.jsonl")).write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in results) + ("\n" if results else ""),
        encoding="utf-8",
    )
    return results


def run_smoke(
    boards: list[dict],
    exe: Path,
    bb_dir: str,
    out_dir: Path,
    *,
    limit: int,
    iterations: int,
    seed: int,
) -> dict:
    random.seed(seed)
    # Prefer Player-side boards with original opponent present (same input).
    cands = [b for b in boards if b["side"] == "Player" and b.get("output")]
    random.shuffle(cands)
    cands = cands[:limit]
    jobs = []
    meta = []
    for b in cands:
        cross = make_cross_input(b["input"], b["input"], player_side="Player", opp_side="Opponent")
        jid = f"smoke|{b['id']}"
        jobs.append({"id": jid, "input": cross})
        meta.append({"id": jid, "boardId": b["id"], "rec": b["output"]})
    results = run_batch(
        exe,
        bb_dir,
        jobs,
        out_dir / "smoke.json",
        iterations=iterations,
        threads=None,
        max_duration=5000,
    )
    by_id = {r.get("id"): r for r in results}
    passed = 0
    details = []
    for m in meta:
        sim = by_id.get(m["id"]) or {}
        ok = bool(sim.get("ok")) and rates_within_3sigma(m["rec"], sim)
        passed += int(ok)
        details.append(
            {
                "id": m["id"],
                "ok": ok,
                "simOk": bool(sim.get("ok")),
                "win": {"rec": m["rec"].get("winRate"), "sim": sim.get("winRate")},
                "error": sim.get("error"),
            }
        )
    report = {
        "n": len(meta),
        "passed": passed,
        "passRate": passed / len(meta) if meta else 0.0,
        "details": details,
    }
    (out_dir / "smoke_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def build_cross_jobs(
    boards: list[dict],
    *,
    candidate_sides: set[str],
    ref_sides: set[str],
    turn_slack: int,
) -> tuple[list[dict], list[dict]]:
    """Return (jobs, pair_meta). job id = candId||refId."""
    by_turn: dict[int, list[dict]] = defaultdict(list)
    for b in boards:
        by_turn[b["turn"]].append(b)

    jobs: list[dict] = []
    meta: list[dict] = []
    turns = sorted(by_turn)
    for t in turns:
        pool_turns = range(t - turn_slack, t + turn_slack + 1)
        refs = [b for tt in pool_turns for b in by_turn.get(tt, []) if b["side"] in ref_sides]
        cands = [b for b in by_turn[t] if b["side"] in candidate_sides]
        for cand in cands:
            for ref in refs:
                if ref["id"] == cand["id"]:
                    continue
                if ref["gameId"] == cand["gameId"]:
                    continue
                jid = f"{cand['id']}||{ref['id']}"
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
    return jobs, meta


def spearman(xs: list[float], ys: list[float]) -> float | None:
    n = len(xs)
    if n < 3:
        return None

    def rank(vals: list[float]) -> list[float]:
        order = sorted(range(n), key=lambda i: vals[i])
        ranks = [0.0] * n
        i = 0
        while i < n:
            j = i
            while j + 1 < n and vals[order[j + 1]] == vals[order[i]]:
                j += 1
            avg = (i + j) / 2.0 + 1.0
            for k in range(i, j + 1):
                ranks[order[k]] = avg
            i = j + 1
        return ranks

    rx, ry = rank(xs), rank(ys)
    mx = sum(rx) / n
    my = sum(ry) / n
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    denx = math.sqrt(sum((a - mx) ** 2 for a in rx))
    deny = math.sqrt(sum((b - my) ** 2 for b in ry))
    if denx == 0 or deny == 0:
        return None
    return num / (denx * deny)


def auc_binary(scores: list[float], labels: list[int]) -> float | None:
    """ROC AUC for binary labels 0/1; ignores non-binary."""
    pairs = [(s, y) for s, y in zip(scores, labels) if y in (0, 1)]
    if len(pairs) < 4:
        return None
    pos = [s for s, y in pairs if y == 1]
    neg = [s for s, y in pairs if y == 0]
    if not pos or not neg:
        return None
    # Mann–Whitney
    total = 0.0
    for p in pos:
        for n in neg:
            if p > n:
                total += 1.0
            elif p == n:
                total += 0.5
    return total / (len(pos) * len(neg))


def result_code(result: str | None) -> float | None:
    if result == "win":
        return 1.0
    if result == "tie":
        return 0.5
    if result == "loss":
        return 0.0
    return None


def analyze(
    boards: list[dict],
    pair_meta: list[dict],
    results: list[dict],
    *,
    bootstrap_b: int,
    seed: int,
    baseline_k: int,
) -> dict:
    random.seed(seed)
    by_id = {r.get("id"): r for r in results if r.get("id")}
    board_by = {b["id"]: b for b in boards}

    # scores[cand][ref] = s
    scores: dict[str, dict[str, float]] = defaultdict(dict)
    sim_ms = []
    hydrate_ms = []
    ok_pairs = 0
    for m in pair_meta:
        r = by_id.get(m["id"])
        if not r or not r.get("ok"):
            continue
        ok_pairs += 1
        s = score_of(r.get("winRate"), r.get("tieRate"))
        scores[m["candId"]][m["refId"]] = s
        if r.get("elapsedMs") is not None:
            sim_ms.append(float(r["elapsedMs"]))
        if r.get("hydrateMs") is not None:
            hydrate_ms.append(float(r["hydrateMs"]))

    # Per-candidate S and percentile within same turn + same candidate side set
    by_turn_side: dict[tuple[int, str], list[str]] = defaultdict(list)
    for bid, b in board_by.items():
        if bid in scores:
            by_turn_side[(b["turn"], b["side"])].append(bid)

    rows = []
    for bid, ref_map in scores.items():
        b = board_by[bid]
        refs = list(ref_map.keys())
        if not refs:
            continue
        s_vals = [ref_map[r] for r in refs]
        s_mean = sum(s_vals) / len(s_vals)
        peers = by_turn_side[(b["turn"], b["side"])]
        peer_s = []
        for pid in peers:
            if pid == bid:
                continue
            pm = scores.get(pid)
            if not pm:
                continue
            peer_s.append(sum(pm.values()) / len(pm))
        # percentile: fraction of peers with S <= s_mean
        if peer_s:
            pct = sum(1 for x in peer_s if x <= s_mean) / len(peer_s)
        else:
            pct = None

        # bootstrap on reference pool
        boot_pct = []
        if peer_s and len(refs) >= 3:
            for _ in range(bootstrap_b):
                sample = [random.choice(refs) for _ in range(len(refs))]
                s_b = sum(ref_map[r] for r in sample) / len(sample)
                # peer S also re-averaged on same resampled refs where available
                peer_sb = []
                for pid in peers:
                    if pid == bid:
                        continue
                    pm = scores.get(pid) or {}
                    vals = [pm[r] for r in sample if r in pm]
                    if vals:
                        peer_sb.append(sum(vals) / len(vals))
                if peer_sb:
                    boot_pct.append(sum(1 for x in peer_sb if x <= s_b) / len(peer_sb))
        width = None
        if len(boot_pct) >= 20:
            qs = sorted(boot_pct)
            lo = qs[max(0, int(0.025 * len(qs)))]
            hi = qs[min(len(qs) - 1, int(0.975 * len(qs)))]
            width = (hi - lo) * 100.0  # percentile points

        lab = b.get("label") or {}
        rows.append(
            {
                "boardId": bid,
                "gameId": b["gameId"],
                "turn": b["turn"],
                "side": b["side"],
                "S": s_mean,
                "nRef": len(refs),
                "percentile": pct,
                "bootWidthPctPoints": width,
                "result": lab.get("result"),
                "resultCode": result_code(lab.get("result")),
                "damage": lab.get("damage"),
                "placement": lab.get("placement"),
                "hdtWin": lab.get("hdtWin"),
                "hdtScore": score_of(lab.get("hdtWin"), lab.get("hdtTie")),
                "resultSource": lab.get("resultSource"),
            }
        )

    # Correlations on Player candidates with labels
    player_rows = [r for r in rows if r["side"] == "Player" and r["percentile"] is not None]
    labeled = [r for r in player_rows if r["resultCode"] is not None]
    damage_rows = [r for r in player_rows if isinstance(r.get("damage"), (int, float))]
    place_rows = [
        r
        for r in player_rows
        if isinstance(r.get("placement"), (int, float)) and r.get("percentile") is not None
    ]
    loss_dmg = [
        r
        for r in player_rows
        if r.get("result") == "loss"
        and isinstance(r.get("damage"), (int, float))
        and r.get("percentile") is not None
    ]

    def _mean_pct(res: str) -> float | None:
        xs = [r["percentile"] for r in player_rows if r.get("result") == res and r.get("percentile") is not None]
        return (sum(xs) / len(xs)) if xs else None

    corr = {
        "nPlayerScored": len(player_rows),
        "nLabeled": len(labeled),
        "spearman_pct_vs_result": spearman(
            [r["percentile"] for r in labeled], [r["resultCode"] for r in labeled]
        )
        if labeled
        else None,
        "spearman_S_vs_result": spearman([r["S"] for r in labeled], [r["resultCode"] for r in labeled])
        if labeled
        else None,
        "spearman_pct_vs_damage": spearman(
            [r["percentile"] for r in damage_rows], [float(r["damage"]) for r in damage_rows]
        )
        if damage_rows
        else None,
        "spearman_pct_vs_damage_on_loss": spearman(
            [r["percentile"] for r in loss_dmg], [float(r["damage"]) for r in loss_dmg]
        )
        if loss_dmg
        else None,
        "nWithPlacement": len(place_rows),
        "spearman_pct_vs_placement": spearman(
            [r["percentile"] for r in place_rows], [float(r["placement"]) for r in place_rows]
        )
        if place_rows
        else None,
        "spearman_hdt_vs_placement": spearman(
            [r["hdtScore"] for r in place_rows if r.get("hdtScore") is not None],
            [float(r["placement"]) for r in place_rows if r.get("hdtScore") is not None],
        )
        if place_rows
        else None,
        "mean_pct_by_result": {
            "win": _mean_pct("win"),
            "tie": _mean_pct("tie"),
            "loss": _mean_pct("loss"),
        },
        "spearman_hdt_vs_result": spearman(
            [r["hdtScore"] for r in labeled if r.get("hdtScore") is not None],
            [r["resultCode"] for r in labeled if r.get("hdtScore") is not None],
        ),
    }

    # Incremental: AUC for win vs not-win
    win_labels = []
    pct_scores = []
    hdt_scores = []
    for r in labeled:
        if r["result"] not in ("win", "loss", "tie"):
            continue
        y = 1 if r["result"] == "win" else 0
        win_labels.append(y)
        pct_scores.append(r["percentile"])
        hdt_scores.append(r["hdtScore"] if r.get("hdtScore") is not None else 0.0)
    corr["auc_percentile_win"] = auc_binary(pct_scores, win_labels)
    corr["auc_hdt_win"] = auc_binary(hdt_scores, win_labels)
    # simple blend
    if pct_scores and hdt_scores:
        blend = [0.5 * p + 0.5 * h for p, h in zip(pct_scores, hdt_scores)]
        corr["auc_blend_win"] = auc_binary(blend, win_labels)
        corr["auc_delta_blend_minus_hdt"] = (
            None
            if corr["auc_blend_win"] is None or corr["auc_hdt_win"] is None
            else corr["auc_blend_win"] - corr["auc_hdt_win"]
        )

    widths = [r["bootWidthPctPoints"] for r in player_rows if r.get("bootWidthPctPoints") is not None]
    stability = {
        "nWithBoot": len(widths),
        "bootWidth_p50": statistics.median(widths) if widths else None,
        "bootWidth_p90": sorted(widths)[int(0.9 * (len(widths) - 1))] if widths else None,
        "bootWidth_mean": statistics.mean(widths) if widths else None,
        "frac_width_le_20": (sum(1 for w in widths if w <= 20) / len(widths)) if widths else None,
    }

    # Baseline: fixed K refs sampled across turns from Opponent+Player pool
    all_ref_ids = [b["id"] for b in boards]
    random.shuffle(all_ref_ids)
    baseline_ids = all_ref_ids[: min(baseline_k, len(all_ref_ids))]
    base_rows = []
    for r in player_rows:
        bid = r["boardId"]
        rm = scores.get(bid) or {}
        vals = [rm[x] for x in baseline_ids if x in rm]
        if not vals:
            continue
        base_rows.append({**r, "S_base": sum(vals) / len(vals), "nBase": len(vals)})
    base_labeled = [r for r in base_rows if r["resultCode"] is not None]
    baseline = {
        "k": len(baseline_ids),
        "nScored": len(base_rows),
        "spearman_Sbase_vs_result": spearman(
            [r["S_base"] for r in base_labeled], [r["resultCode"] for r in base_labeled]
        )
        if base_labeled
        else None,
        "spearman_S_vs_result": corr["spearman_S_vs_result"],
    }

    # Cost
    def pctile(arr, p):
        if not arr:
            return None
        s = sorted(arr)
        return s[min(len(s) - 1, max(0, int(p * (len(s) - 1))))]

    # Per-game: sum sim time for pairs where cand in game (Player only)
    per_game_ms: dict[str, float] = defaultdict(float)
    for m in pair_meta:
        r = by_id.get(m["id"])
        if not r or not r.get("ok"):
            continue
        if m["candSide"] != "Player":
            continue
        per_game_ms[m["candGame"]] += float(r.get("elapsedMs") or 0)

    cost = {
        "okPairs": ok_pairs,
        "pairMeta": len(pair_meta),
        "simMs_p50": pctile(sim_ms, 0.5),
        "simMs_p90": pctile(sim_ms, 0.9),
        "simMs_sum": sum(sim_ms) if sim_ms else 0,
        "hydrateMs_p50": pctile(hydrate_ms, 0.5),
        "perGameSimMs_max": max(per_game_ms.values()) if per_game_ms else None,
        "perGameSimMs_p50": pctile(list(per_game_ms.values()), 0.5) if per_game_ms else None,
        "gamesScored": len(per_game_ms),
        "under_10min_budget": (
            all(v <= 600_000 for v in per_game_ms.values()) if per_game_ms else None
        ),
    }

    # Pool size vs width (bucket by nRef)
    by_n: dict[str, list[float]] = defaultdict(list)
    for r in player_rows:
        w = r.get("bootWidthPctPoints")
        if w is None:
            continue
        n = r["nRef"]
        bucket = "1-5" if n <= 5 else "6-10" if n <= 10 else "11-20" if n <= 20 else "21+"
        by_n[bucket].append(w)
    stability["widthByNRef"] = {k: {"n": len(v), "median": statistics.median(v)} for k, v in sorted(by_n.items())}

    return {
        "corr": corr,
        "stability": stability,
        "baseline": baseline,
        "cost": cost,
        "rows": rows,
        "nBoardsScored": len(scores),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="P3-T0 strength cross-eval")
    ap.add_argument("--root", action="append", default=None)
    ap.add_argument("--turns", default=str(DEFAULT_TURNS))
    ap.add_argument("--bb-version", default="1.85.0.0")
    ap.add_argument("--bb-map", default=str(DEFAULT_BB_MAP))
    ap.add_argument("--exe", default=str(DEFAULT_EXE))
    ap.add_argument("--out", default=str(SPIKE / "out"))
    ap.add_argument("--max-turn", type=int, default=12)
    ap.add_argument("--smoke", action="store_true")
    ap.add_argument("--run", action="store_true")
    ap.add_argument("--analyze-only", default=None, help="Directory with cross_results.json + pair_meta.json")
    ap.add_argument("--smoke-limit", type=int, default=30)
    ap.add_argument("--iterations", type=int, default=4000)
    ap.add_argument("--smoke-iterations", type=int, default=10000)
    ap.add_argument("--max-duration", type=int, default=4000)
    ap.add_argument("--turn-slack", type=int, default=0, help="Include refs from turn±slack")
    ap.add_argument(
        "--mode",
        default="player_vs_player",
        choices=["player_vs_player", "player_vs_both", "both_vs_both"],
    )
    ap.add_argument("--bootstrap", type=int, default=200)
    ap.add_argument("--baseline-k", type=int, default=20)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--limit-jobs", type=int, default=0, help="Debug: cap job count")
    args = ap.parse_args(argv)

    roots = args.root or default_roots()
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    bb_map = load_bb_map(Path(args.bb_map))
    bb_dir = bb_map.get(args.bb_version)
    if not bb_dir or not os.path.isfile(os.path.join(bb_dir, "BobsBuddy.dll")):
        print(f"No BobsBuddy.dll for {args.bb_version}: {bb_dir}", file=sys.stderr)
        return 2
    exe = Path(args.exe)
    if not exe.is_file():
        print(f"ReplaySim missing: {exe}", file=sys.stderr)
        return 2

    turns_by = load_turns(Path(args.turns))
    boards = collect_boards(roots, args.bb_version, turns_by, args.max_turn)
    (out_dir / "boards_index.json").write_text(
        json.dumps(
            [
                {
                    "id": b["id"],
                    "gameId": b["gameId"],
                    "turn": b["turn"],
                    "side": b["side"],
                    "label": b["label"],
                }
                for b in boards
            ],
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"boards={len(boards)} games={len({b['gameId'] for b in boards})} bb={args.bb_version}")

    if args.smoke:
        smoke = run_smoke(
            boards,
            exe,
            bb_dir,
            out_dir,
            limit=args.smoke_limit,
            iterations=args.smoke_iterations,
            seed=args.seed,
        )
        print(f"smoke {smoke['passed']}/{smoke['n']} = {smoke['passRate']:.1%}")
        if smoke["passRate"] < 0.95:
            return 1
        if not args.run:
            return 0

    if args.analyze_only:
        d = Path(args.analyze_only)
        results = json.loads((d / "cross_results.json").read_text(encoding="utf-8"))["results"]
        pair_meta = json.loads((d / "pair_meta.json").read_text(encoding="utf-8"))
        boards_idx = json.loads((d / "boards_index.json").read_text(encoding="utf-8"))
        # reload full boards for inputs not needed; reconstruct minimal from index + prior boards
        board_full = {b["id"]: b for b in boards}
        for bi in boards_idx:
            if bi["id"] not in board_full:
                board_full[bi["id"]] = {**bi, "input": None, "output": {}}
            elif bi.get("label"):
                board_full[bi["id"]]["label"] = bi["label"]
        analysis = analyze(
            list(board_full.values()),
            pair_meta,
            results,
            bootstrap_b=args.bootstrap,
            seed=args.seed,
            baseline_k=args.baseline_k,
        )
        (d / "analysis.json").write_text(
            json.dumps({k: v for k, v in analysis.items() if k != "rows"}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        (d / "scores.jsonl").write_text(
            "\n".join(json.dumps(r, ensure_ascii=False) for r in analysis["rows"]) + "\n",
            encoding="utf-8",
        )
        print(json.dumps(analysis["corr"], ensure_ascii=False, indent=2))
        print(json.dumps(analysis["stability"], ensure_ascii=False, indent=2))
        print(json.dumps(analysis["cost"], ensure_ascii=False, indent=2))
        return 0

    if not args.run:
        print("Nothing to do; pass --smoke and/or --run", file=sys.stderr)
        return 2

    if args.mode == "player_vs_player":
        cand_sides, ref_sides = {"Player"}, {"Player"}
    elif args.mode == "player_vs_both":
        cand_sides, ref_sides = {"Player"}, {"Player", "Opponent"}
    else:
        cand_sides, ref_sides = {"Player", "Opponent"}, {"Player", "Opponent"}

    jobs, pair_meta = build_cross_jobs(
        boards, candidate_sides=cand_sides, ref_sides=ref_sides, turn_slack=args.turn_slack
    )
    if args.limit_jobs and len(jobs) > args.limit_jobs:
        jobs = jobs[: args.limit_jobs]
        keep = {j["id"] for j in jobs}
        pair_meta = [m for m in pair_meta if m["id"] in keep]

    (out_dir / "pair_meta.json").write_text(json.dumps(pair_meta, ensure_ascii=False), encoding="utf-8")
    print(f"jobs={len(jobs)} mode={args.mode} turn_slack={args.turn_slack}")

    results = run_batch(
        exe,
        bb_dir,
        jobs,
        out_dir / "cross_results.json",
        iterations=args.iterations,
        threads=None,
        max_duration=args.max_duration,
    )
    summary = json.loads((out_dir / "cross_results.json").read_text(encoding="utf-8"))["summary"]
    print("batch", summary)

    analysis = analyze(
        boards,
        pair_meta,
        results,
        bootstrap_b=args.bootstrap,
        seed=args.seed,
        baseline_k=args.baseline_k,
    )
    (out_dir / "analysis.json").write_text(
        json.dumps({k: v for k, v in analysis.items() if k != "rows"}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (out_dir / "scores.jsonl").write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in analysis["rows"]) + "\n",
        encoding="utf-8",
    )
    print("corr", json.dumps(analysis["corr"], ensure_ascii=False))
    print("stability", json.dumps(analysis["stability"], ensure_ascii=False))
    print("baseline", json.dumps(analysis["baseline"], ensure_ascii=False))
    print("cost", json.dumps(analysis["cost"], ensure_ascii=False))
    return 0 if summary.get("ok", 0) > 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
