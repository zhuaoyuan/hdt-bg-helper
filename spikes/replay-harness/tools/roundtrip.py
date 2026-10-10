# -*- coding: utf-8 -*-
"""P2-T0 offline round-trip: diag _input dump -> ReplaySim -> compare Output.

Usage:
  python roundtrip.py --root data/BgHelperDiag
  python roundtrip.py --root data/BgHelperDiag --mode q009
  python roundtrip.py --root data/BgHelperDiag --mode q011 --limit 30
  python roundtrip.py --root data/BgHelperDiag --mode q013 --limit 20
"""
from __future__ import annotations

import argparse
import json
import math
import os
import re
import subprocess
import sys
import tempfile
import time
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
HARNESS = HERE.parent
REPO = HARNESS.parents[1]
DEFAULT_BB_MAP = REPO / "tools" / "ReplaySim" / "bb-dirs.json"
DEFAULT_EXE = REPO / "tools" / "ReplaySim" / "bin" / "run" / "ReplaySim.exe"
sys.path.insert(0, str(HARNESS.parent / "hdt-diag-logger" / "tools"))
from diag_io import open_text, records_path  # noqa: E402

# Anonymizer does bare substring Replace on known names, so identifiers that
# contain those names as substrings get corrupted too (Player→ControlledByPlayer,
# Wind→Windfury, etc.). Repair the structural collisions we have seen in data.
KEY_REPAIRS = [
    (re.compile(r"^ControlledByplayer_[0-9a-f]{8}$", re.I), "ControlledByPlayer"),
    (re.compile(r"^Megaplayer_[0-9a-f]{8}fury$", re.I), "MegaWindfury"),
    (re.compile(r"^player_[0-9a-f]{8}fury$", re.I), "Windfury"),
    (re.compile(r"^DuosInputplayer_[0-9a-f]{8}Teammate$", re.I), "DuosInputPlayerTeammate"),
    (re.compile(r"^DuosInputplayer_[0-9a-f]{8}$", re.I), "DuosInputPlayer"),
    (re.compile(r"^player_[0-9a-f]{8}Teammate$", re.I), "PlayerTeammate"),
    (re.compile(r"^player_[0-9a-f]{8}$", re.I), "Player"),
]
SIM_PLAYER_TYPE_RE = re.compile(r"^BobsBuddy\.Simulation\.player_[0-9a-f]{8}$", re.I)


def expand_path(p: str) -> str:
    return os.path.expandvars(os.path.expanduser(p))


def load_bb_map(path: Path) -> dict[str, str]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    out = {}
    for k, v in raw.items():
        ver = k.split(":", 1)[0]
        expanded = expand_path(v)
        if ver not in out and os.path.isfile(os.path.join(expanded, "BobsBuddy.dll")):
            out[ver] = expanded
        elif ver not in out:
            out[ver] = expanded  # keep for error messages
    return out


def fix_anon_key(key: str) -> str:
    for pat, repl in KEY_REPAIRS:
        if pat.match(key):
            return repl
    return key


def fix_anon(obj):
    """Repair anonymizer substring collisions on structural JSON keys / Player $type."""
    if isinstance(obj, list):
        return [fix_anon(x) for x in obj]
    if not isinstance(obj, dict):
        return obj
    fixed = {}
    for k, v in obj.items():
        nk = fix_anon_key(k)
        nv = fix_anon(v)
        if k == "$type" and isinstance(nv, str) and SIM_PLAYER_TYPE_RE.match(nv):
            nv = "BobsBuddy.Simulation.Player"
        # merge if repair collapses two keys onto one (prefer first non-null)
        if nk in fixed and fixed[nk] is not None:
            continue
        fixed[nk] = nv
    return fixed


def read_records(game_dir: Path) -> list[dict]:
    path = records_path(str(game_dir))
    if not path:
        return []
    out = []
    with open_text(path) as f:
        for line in f:
            out.append(json.loads(line))
    return out


def segment_combats(records: list[dict]) -> list[list[dict]]:
    combats, cur = [], None
    for r in records:
        if r.get("type") == "combat_phase" and r.get("value") is True:
            cur = []
            combats.append(cur)
            continue
        if cur is not None:
            cur.append(r)
            if r.get("type") == "combat_phase" and r.get("value") is False:
                cur = None
    return combats


def pick_combat_bb(segment: list[dict]) -> dict | None:
    cands = [
        r
        for r in segment
        if r.get("type") == "hdt_bb"
        and r.get("state") == "Combat"
        and r.get("hasInput")
        and r.get("hasOutput")
    ]
    if not cands:
        return None
    cands.sort(key=lambda r: (r.get("reRunCount") or 0, r.get("lineSeq") or 0))
    return cands[-1]


def extract_input(rec: dict) -> dict | None:
    inv = rec.get("invoker") or {}
    inp = inv.get("_input")
    if isinstance(inp, dict) and "Input" in str(inp.get("$type") or ""):
        return fix_anon(inp)
    return None


def extract_output(rec: dict) -> dict | None:
    inv = rec.get("invoker") or {}
    out = inv.get("Output")
    if isinstance(out, dict) and out.get("winRate") is not None:
        return out
    return None


def turn_of(segment: list[dict], rec: dict) -> int | None:
    for r in segment:
        if r.get("type") == "entities" and r.get("reason") == "combat_start":
            t = (r.get("context") or {}).get("turn")
            if t is not None:
                return t
    return rec.get("key") if isinstance(rec.get("key"), int) else None


def binomial_se(p: float, n: int) -> float:
    if n <= 0:
        return 1.0
    p = min(max(p, 0.0), 1.0)
    return math.sqrt(p * (1.0 - p) / n)


def rates_within_3sigma(rec: dict, sim: dict) -> tuple[bool, dict]:
    n1 = int(rec.get("simulationCount") or 0)
    n2 = int(sim.get("simulationCount") or 0)
    detail = {}
    ok = True
    for key in ("winRate", "tieRate", "lossRate"):
        p1 = float(rec.get(key) or 0.0)
        p2 = float(sim.get(key) or 0.0)
        se = math.sqrt(binomial_se(p1, n1) ** 2 + binomial_se(p2, n2) ** 2)
        delta = abs(p1 - p2)
        # Floor: with n≈1e4, a one-simulation swing is 1e-4; allow a few counts of slack
        # so 0.000 vs 0.001 near-certain outcomes are not false mismatches.
        floor = 3.0 * math.sqrt(0.5 * (1.0 / max(n1, 1) + 1.0 / max(n2, 1)))
        limit = max(3.0 * se, floor) if se > 0 else max(1e-6, floor)
        passed = delta <= limit + 1e-12
        detail[key] = {"rec": p1, "sim": p2, "delta": delta, "limit": limit, "ok": passed}
        ok = ok and passed
    return ok, detail


def run_replay(
    exe: Path,
    bb_dir: str,
    input_obj: dict,
    iterations: int | None,
    max_duration: int,
    perturb: list[str] | None = None,
) -> dict:
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
        json.dump(input_obj, f, ensure_ascii=False)
        tmp = f.name
    try:
        cmd = [
            str(exe),
            "--bb-dir",
            bb_dir,
            "--input",
            tmp,
            "--max-duration",
            str(max_duration),
        ]
        if iterations is not None:
            cmd.extend(["--iterations", str(iterations)])
        for p in perturb or []:
            cmd.extend(["--perturb", p])
        t0 = time.perf_counter()
        proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
        wall = (time.perf_counter() - t0) * 1000.0
        line = (proc.stdout or "").strip().splitlines()
        if not line:
            return {
                "ok": False,
                "error": "no stdout",
                "stderr": (proc.stderr or "")[:500],
                "exitCode": proc.returncode,
                "wallMs": wall,
            }
        try:
            result = json.loads(line[-1])
        except json.JSONDecodeError:
            return {
                "ok": False,
                "error": "bad json: " + line[-1][:300],
                "stderr": (proc.stderr or "")[:500],
                "exitCode": proc.returncode,
                "wallMs": wall,
            }
        result["wallMs"] = wall
        result["exitCode"] = proc.returncode
        return result
    finally:
        try:
            os.unlink(tmp)
        except OSError:
            pass


def iter_combats(root: Path):
    for gd in sorted(root.iterdir()):
        if not gd.is_dir() or not (gd / "meta.json").exists():
            continue
        meta = json.loads((gd / "meta.json").read_text(encoding="utf-8"))
        bb = (meta.get("bobsBuddy") or {}).get("fileVersion") or (meta.get("bobsBuddy") or {}).get("version")
        records = read_records(gd)
        for seg in segment_combats(records):
            rec = pick_combat_bb(seg)
            if not rec:
                yield gd, meta, bb, seg, None, None, None
                continue
            inp = extract_input(rec)
            out = extract_output(rec)
            yield gd, meta, bb, seg, rec, inp, out


def mode_roundtrip(args, bb_map: dict[str, str], exe: Path):
    stats = Counter()
    rows = []
    for gd, meta, bb, seg, rec, inp, out in iter_combats(Path(args.root)):
        if args.versions and bb not in args.versions:
            continue
        turn = turn_of(seg, rec) if rec else None
        if rec is None or inp is None or out is None:
            stats["no_output"] += 1
            continue
        bb_dir = bb_map.get(bb)
        if not bb_dir or not os.path.isfile(os.path.join(bb_dir, "BobsBuddy.dll")):
            stats["skipped_no_dll"] += 1
            rows.append({"game": gd.name, "turn": turn, "bb": bb, "status": "skipped_no_dll"})
            continue
        if stats["attempted"] >= args.limit > 0:
            break
        stats["attempted"] += 1
        iters = int(out.get("simulationCount") or 10000)
        sim = run_replay(exe, bb_dir, inp, iters, args.max_duration)
        if not sim.get("ok"):
            stats["hydrate_or_sim_fail"] += 1
            rows.append(
                {
                    "game": gd.name,
                    "turn": turn,
                    "bb": bb,
                    "status": "fail",
                    "error": sim.get("error"),
                    "warnings": (sim.get("hydrateWarnings") or [])[:5],
                }
            )
            if args.verbose:
                print(f"FAIL {gd.name} T{turn}: {sim.get('error')}", file=sys.stderr)
            continue
        ok, detail = rates_within_3sigma(out, sim)
        status = "pass" if ok else "mismatch"
        stats[status] += 1
        row = {
            "game": gd.name,
            "turn": turn,
            "bb": bb,
            "status": status,
            "elapsedMs": sim.get("elapsedMs"),
            "wallMs": sim.get("wallMs"),
            "hydrateMs": sim.get("hydrateMs"),
            "detail": detail,
            "warnings": sim.get("hydrateWarnings") or [],
        }
        rows.append(row)
        if args.verbose or status != "pass":
            d = detail
            print(
                f"{status.upper():8} {gd.name} T{turn} BB={bb} "
                f"w {d['winRate']['rec']:.3f}->{d['winRate']['sim']:.3f} "
                f"t {d['tieRate']['rec']:.3f}->{d['tieRate']['sim']:.3f} "
                f"l {d['lossRate']['rec']:.3f}->{d['lossRate']['sim']:.3f} "
                f"ms={sim.get('elapsedMs')}"
            )

    print_summary("roundtrip", stats, rows, args)
    return rows, stats


def mode_q009(args, bb_map, exe):
    """Timing only on versions with DLL."""
    args.mode = "roundtrip"
    rows, stats = mode_roundtrip(args, bb_map, exe)
    by_game = defaultdict(float)
    times = []
    for r in rows:
        if r.get("status") not in ("pass", "mismatch"):
            continue
        ms = float(r.get("wallMs") or r.get("elapsedMs") or 0)
        times.append(ms)
        by_game[r["game"]] += ms
    if times:
        times_sorted = sorted(times)
        def pct(p):
            return times_sorted[min(len(times_sorted) - 1, int(p * (len(times_sorted) - 1)))]
        game_totals = sorted(by_game.values())
        print("\n=== Q-009 timing (wall ms, successful hydrate+sim) ===")
        print(f"combats: {len(times)}  games: {len(by_game)}")
        print(
            f"per combat ms: min={times_sorted[0]:.0f} p50={pct(0.5):.0f} "
            f"p90={pct(0.9):.0f} max={times_sorted[-1]:.0f} sum={sum(times):.0f}"
        )
        print(
            f"per game ms: min={game_totals[0]:.0f} p50={game_totals[len(game_totals)//2]:.0f} "
            f"max={game_totals[-1]:.0f}  budget=600000 (10 min)"
        )
        over = [g for g, ms in by_game.items() if ms > 600_000]
        print(f"games over 10 min budget: {len(over)}")
    return rows, stats


def mode_q011(args, bb_map, exe):
    """Same input on native BB vs alternate available BB.

    --alt-version forces the foreign DLL (e.g. 1.85 boards vs 1.88.6).
    --versions limits which *capture* BB versions are attempted.
    """
    alts = [v for v in bb_map if os.path.isfile(os.path.join(bb_map[v], "BobsBuddy.dll"))]
    stats = Counter()
    rows = []
    roots = args.roots if getattr(args, "roots", None) else [args.root]
    for root in roots:
        for gd, meta, bb, seg, rec, inp, out in iter_combats(Path(root)):
            if rec is None or inp is None or out is None:
                continue
            if args.versions and bb not in args.versions:
                continue
            if not bb_map.get(bb) or not os.path.isfile(os.path.join(bb_map[bb], "BobsBuddy.dll")):
                stats["skipped_no_dll"] += 1
                continue
            if args.alt_version:
                alt_ver = args.alt_version
                if alt_ver == bb:
                    stats["alt_same_as_native"] += 1
                    continue
                if not bb_map.get(alt_ver) or not os.path.isfile(
                    os.path.join(bb_map[alt_ver], "BobsBuddy.dll")
                ):
                    stats["skipped_no_alt_dll"] += 1
                    continue
            else:
                others = [v for v in alts if v != bb]
                if not others:
                    stats["no_alt"] += 1
                    continue
                # legacy heuristic: for 1.85 prefer oldest other; else newest
                alt_ver = others[0] if bb.startswith("1.85") else others[-1]
            if stats["attempted"] >= args.limit > 0:
                break
            stats["attempted"] += 1
            turn = turn_of(seg, rec)
            iters = int(out.get("simulationCount") or 10000)
            native = run_replay(exe, bb_map[bb], inp, iters, args.max_duration)
            foreign = run_replay(exe, bb_map[alt_ver], inp, iters, args.max_duration)
            if not native.get("ok") or not foreign.get("ok"):
                stats["fail"] += 1
                rows.append(
                    {
                        "game": gd.name,
                        "turn": turn,
                        "bb": bb,
                        "alt": alt_ver,
                        "status": "fail",
                        "nativeError": None if native.get("ok") else native.get("error"),
                        "altError": None if foreign.get("ok") else foreign.get("error"),
                        "nativeStderr": None if native.get("ok") else (native.get("stderr") or "")[:300],
                        "altStderr": None if foreign.get("ok") else (foreign.get("stderr") or "")[:300],
                    }
                )
                if args.verbose:
                    print(
                        f"FAIL {gd.name} T{turn} native_ok={native.get('ok')} "
                        f"alt_ok={foreign.get('ok')} altErr={(foreign.get('error') or '')[:120]}"
                    )
                continue
            ok, detail = rates_within_3sigma(native, foreign)
            status = "same" if ok else "diff"
            stats[status] += 1
            # also vs recorded Output (literal "recalc with new BB")
            ok_rec, detail_rec = rates_within_3sigma(out, foreign)
            status_rec = "rec_same" if ok_rec else "rec_diff"
            stats[status_rec] += 1
            rows.append(
                {
                    "game": gd.name,
                    "turn": turn,
                    "bb": bb,
                    "alt": alt_ver,
                    "status": status,
                    "statusVsRecorded": status_rec,
                    "detail": detail,
                    "detailVsRecorded": detail_rec,
                    "nativeExit": native.get("myExitCondition"),
                    "altExit": foreign.get("myExitCondition"),
                    "deltaWin": detail["winRate"]["delta"],
                    "deltaWinVsRecorded": detail_rec["winRate"]["delta"],
                }
            )
            if args.verbose or status == "diff" or status_rec == "rec_diff":
                print(
                    f"{status.upper():4}/{status_rec} {gd.name} T{turn} {bb} vs {alt_ver} "
                    f"Δwin={detail['winRate']['delta']:.4f} "
                    f"Δwin_rec={detail_rec['winRate']['delta']:.4f}"
                )
        else:
            continue
        break  # inner broke on limit
    print_summary("q011", stats, rows, args)
    if rows:
        diffs = [r for r in rows if r.get("status") == "diff"]
        deltas = [float(r["deltaWin"]) for r in rows if r.get("deltaWin") is not None]
        if deltas:
            deltas_s = sorted(deltas)
            print(
                f"Δwin (native vs alt): n={len(deltas)} max={deltas_s[-1]:.4f} "
                f"p95={deltas_s[min(len(deltas_s)-1, int(0.95*(len(deltas_s)-1)))]:.4f} "
                f"mean={sum(deltas)/len(deltas):.4f} significant={len(diffs)}"
            )
    return rows, stats


Q013_FIELDS = [
    "Player.DeepBluesCounter",
    "Player.AnySpellCounter",
    "Player.BackToBackCounter",
    "Opponent.DeepBluesCounter",
    "Opponent.AnySpellCounter",
    "Opponent.BackToBackCounter",
]


def mode_q013(args, bb_map, exe):
    stats = Counter()
    rows = []
    for gd, meta, bb, seg, rec, inp, out in iter_combats(Path(args.root)):
        if rec is None or inp is None or out is None:
            continue
        bb_dir = bb_map.get(bb)
        if not bb_dir or not os.path.isfile(os.path.join(bb_dir, "BobsBuddy.dll")):
            stats["skipped_no_dll"] += 1
            continue
        if stats["attempted"] >= args.limit > 0:
            break
        # skip empty boards — need some combat complexity
        side = (((inp.get("Player") or {}).get("Side") or {}).get("items") or [])
        if len(side) < 2:
            continue
        stats["attempted"] += 1
        turn = turn_of(seg, rec)
        iters = int(out.get("simulationCount") or 10000)
        base = run_replay(exe, bb_dir, inp, iters, args.max_duration)
        if not base.get("ok"):
            stats["fail"] += 1
            continue
        perturbs = [f"{f}=7" for f in Q013_FIELDS]
        mod = run_replay(exe, bb_dir, inp, iters, args.max_duration, perturb=perturbs)
        if not mod.get("ok"):
            stats["fail"] += 1
            rows.append({"game": gd.name, "turn": turn, "status": "perturb_fail", "error": mod.get("error")})
            continue
        ok, detail = rates_within_3sigma(base, mod)
        status = "insensitive" if ok else "sensitive"
        stats[status] += 1
        rows.append({"game": gd.name, "turn": turn, "bb": bb, "status": status, "detail": detail})
        if args.verbose or status == "sensitive":
            print(f"{status} {gd.name} T{turn} Δwin={detail['winRate']['delta']:.4f}")
    print_summary("q013", stats, rows, args)
    return rows, stats


def print_summary(mode, stats, rows, args):
    print(f"\n=== {mode} summary ===")
    for k, v in sorted(stats.items()):
        print(f"  {k}: {v}")
    if args.json_out:
        Path(args.json_out).write_text(json.dumps({"stats": stats, "rows": rows}, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"wrote {args.json_out}")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", default=str(HARNESS.parents[1] / "data" / "BgHelperDiag"))
    ap.add_argument(
        "--roots",
        nargs="*",
        default=None,
        help="optional multiple diag roots (overrides --root)",
    )
    ap.add_argument("--bb-map", default=str(DEFAULT_BB_MAP))
    ap.add_argument("--exe", default=str(DEFAULT_EXE))
    ap.add_argument("--mode", choices=["roundtrip", "q009", "q011", "q013"], default="roundtrip")
    ap.add_argument("--limit", type=int, default=0, help="max combats to attempt (0=all)")
    ap.add_argument("--max-duration", type=int, default=5000)
    ap.add_argument("--versions", nargs="*", help="only these BB fileVersions")
    ap.add_argument(
        "--alt-version",
        default="",
        help="q011: foreign BB fileVersion (e.g. 1.88.6.0)",
    )
    ap.add_argument("--json-out", default="")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    exe = Path(args.exe)
    if not exe.exists():
        print(f"ReplaySim not found: {exe}\nBuild it first.", file=sys.stderr)
        return 2
    bb_map = load_bb_map(Path(args.bb_map))
    print("BB map:")
    for ver, d in sorted(bb_map.items()):
        ok = os.path.isfile(os.path.join(d, "BobsBuddy.dll"))
        print(f"  {ver}: {d} ({'OK' if ok else 'MISSING'})")

    if args.mode == "roundtrip":
        mode_roundtrip(args, bb_map, exe)
    elif args.mode == "q009":
        mode_q009(args, bb_map, exe)
    elif args.mode == "q011":
        mode_q011(args, bb_map, exe)
    elif args.mode == "q013":
        mode_q013(args, bb_map, exe)
    return 0


if __name__ == "__main__":
    sys.exit(main())
