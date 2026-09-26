"""Acceptance report for records written by the HdtDiagLogger plugin (design/P1-diagnostic-logger.md section 5).

Usage:
  python check_capture.py                 # newest game directory
  python check_capture.py --all           # every game directory
  python check_capture.py <game dir> ...  # specific directories
Options:
  --root DIR      records root (default %APPDATA%/HearthstoneDeckTracker/BgHelperDiag)
  --hs-logs DIR   Hearthstone log root for the raw-line comparison
                  (default "C:/Program Files (x86)/Hearthstone/Logs"; pass "none" to skip)

Output contains only counts, ids and anonymised values, so it can be pasted into the repo.
"""
import argparse
import gzip
import json
import os
import re
import sys
from collections import Counter, defaultdict

DEFAULT_ROOT = os.path.join(os.environ.get("APPDATA", ""), "HearthstoneDeckTracker", "BgHelperDiag")
DEFAULT_HS_LOGS = r"C:\Program Files (x86)\Hearthstone\Logs"

# HDT's Power watcher only reads these prefixes (LogWatcherManager.cs:43-46). Of those,
# OnPowerLogLine only gets PowerTaskList.DebugPrintPower (the else branch at :180-185).
FORWARDED_PREFIX = "PowerTaskList.DebugPrintPower"
LINE_PREFIX = re.compile(r"^[A-Z] \d\d:\d\d:\d\d\.\d+ ")
BATTLETAG = re.compile(r"[^\s=#\[\]\"',:{}()]{1,24}#\d{3,6}")
ACCOUNT = re.compile(r"(hi|lo)=\d{6,}")
PLACEHOLDER = re.compile(r"player_[0-9a-f]{8}")
ENTITY = re.compile(r"Entity=(?:\[[^\]]*\]|\S+)")


def open_text(path):
    if path.endswith(".gz"):
        return gzip.open(path, "rt", encoding="utf-8", errors="replace")
    return open(path, "r", encoding="utf-8", errors="replace")


def raw_path(game_dir):
    for name in ("power.log.gz", "power.log"):
        p = os.path.join(game_dir, name)
        if os.path.exists(p):
            return p
    return None


def read_raw(game_dir):
    """Yields (seq, ms, line) from power.log[.gz]; tolerates a truncated gzip trailer (HDT killed)."""
    p = raw_path(game_dir)
    if not p:
        return
    try:
        with open_text(p) as f:
            for row in f:
                seq, ms, line = row.rstrip("\n").split("\t", 2)
                yield int(seq), int(ms), line
    except EOFError:
        print("  WARN: power.log.gz is truncated")


def read_records(game_dir):
    p = os.path.join(game_dir, "records.jsonl")
    if not os.path.exists(p):
        return []
    out = []
    with open(p, encoding="utf-8") as f:
        for i, row in enumerate(f, 1):
            try:
                out.append(json.loads(row))
            except json.JSONDecodeError as e:
                out.append({"type": "_bad_json", "line": i, "error": str(e)})
    return out


def segment_combats(records):
    """Splits records at each combat_phase=true. A segment also covers the following shopping phase, because the
    combat_end snapshot and HDT's validation of the finished combat are recorded after combat_phase=false."""
    combats, current = [], None
    for r in records:
        t = r.get("type")
        if t == "combat_phase" and r.get("value") is True:
            current = {"start": r, "records": []}
            combats.append(current)
            continue
        if current is not None:
            current["records"].append(r)
            if t == "combat_phase" and r.get("value") is False:
                current["end"] = r
    return combats


def combat_row(i, c):
    recs = c["records"]
    ents = [r for r in recs if r.get("type") == "entities"]
    start_snap = next((r for r in ents if r.get("reason") == "combat_start"), None)
    end_snap = next((r for r in ents if r.get("reason") in ("combat_end", "game_end")), None)
    bb = [r for r in recs if r.get("type") == "hdt_bb"]
    errors = [r for r in recs if r.get("type") in ("error", "writer_error")]
    turn = start_snap["context"].get("turn") if start_snap else None
    bb_turns = sorted({r.get("key") for r in bb})
    states = " > ".join(dict.fromkeys(r.get("state") for r in bb if r.get("key") == turn)) or "-"
    max_rerun = max((r.get("reRunCount", 0) for r in bb if r.get("key") == turn), default=None)
    has_output = any(r.get("hasOutput") for r in bb if r.get("key") == turn)
    return {
        "combat": i,
        "turn": turn,
        "startSnap": bool(start_snap),
        "startSnapEntities": start_snap.get("entityCount") if start_snap else None,
        "startSnapMs": round(start_snap.get("captureMs", 0), 1) if start_snap else None,
        "hdtBbDumps": len(bb),
        "hdtBbTurns": bb_turns,
        "states": states,
        "maxReRun": max_rerun,
        "hasOutput": has_output,
        "endSnap": bool(end_snap),
        "errors": len(errors),
    }


def missing_reasons(row):
    reasons = []
    if not row["startSnap"]:
        reasons.append("no combat_start entity snapshot")
    if row["hdtBbDumps"] == 0:
        reasons.append("no hdt_bb dump (probe unavailable or HDT did not simulate)")
    elif not row["hasOutput"]:
        reasons.append("hdt_bb without Output for this turn (too few simulations / unsupported / error)")
    if not row["endSnap"]:
        reasons.append("no combat_end snapshot")
    return reasons


def perf_summary(records):
    perf = [r for r in records if r.get("type") == "perf"]
    if not perf:
        return None
    stats = perf[-1]["stats"]
    rows = {}
    for name, s in stats.items():
        rows[name] = {k: s.get(k) for k in ("count", "totalMs", "maxMs", "p50UpperUs", "p99UpperUs", "threads")}
        rows[name]["totalMs"] = round(rows[name]["totalMs"] or 0, 1)
        rows[name]["maxMs"] = round(rows[name]["maxMs"] or 0, 2)
    return rows


def anonymisation_scan(game_dir):
    hits = Counter()
    for name in os.listdir(game_dir):
        p = os.path.join(game_dir, name)
        if name == "salt.txt" or not os.path.isfile(p):
            continue
        try:
            with open_text(p) as f:
                for line in f:
                    for m in BATTLETAG.finditer(line):
                        hits[(name, "battletag")] += 1
                    for m in ACCOUNT.finditer(line):
                        hits[(name, "account_id")] += 1
        except (EOFError, OSError, UnicodeDecodeError):
            pass
    return hits


def normalise(line):
    line = LINE_PREFIX.sub("", line.rstrip())
    line = PLACEHOLDER.sub("<P>", line)
    line = BATTLETAG.sub("<P>", line)
    line = ACCOUNT.sub(lambda m: m.group(1) + "=<P>", line)
    return line


def find_hs_power_logs(hs_root):
    if not hs_root or not os.path.isdir(hs_root):
        return []
    files = []
    for d in sorted(os.listdir(hs_root)):
        full = os.path.join(hs_root, d)
        if os.path.isdir(full):
            for name in ("Power.log", "Power_old.log"):
                p = os.path.join(full, name)
                if os.path.exists(p):
                    files.append(p)
        elif d.startswith("Power") and d.endswith(".log"):
            files.append(full)
    return files


def compare_with_hs(game_dir, hs_root):
    ours = [line for _, _, line in read_raw(game_dir)]
    if not ours:
        return "no raw lines"
    first = normalise(ours[0])
    best = None
    game_name = os.path.basename(game_dir)
    date_hint = None
    if len(game_name) >= 8 and game_name[:8].isdigit():
        date_hint = f"{game_name[:4]}_{game_name[4:6]}_{game_name[6:8]}"
    paths = find_hs_power_logs(hs_root)
    if date_hint:
        dated = [p for p in paths if date_hint in p]
        if dated:
            paths = dated
    for path in paths:
        theirs = []
        collecting = False
        with open(path, encoding="utf-8", errors="replace") as f:
            for raw in f:
                l = raw.rstrip("\n")
                content = LINE_PREFIX.sub("", l)
                if not content.startswith(FORWARDED_PREFIX):
                    continue
                if not collecting:
                    if normalise(l) != first:
                        continue
                    collecting = True
                theirs.append(l)
        if not collecting:
            continue
        compared = min(len(ours), len(theirs))
        equal = 0
        entity_only = 0
        first_bad = None
        for i in range(compared):
            a, b = normalise(ours[i]), normalise(theirs[i])
            if a == b:
                equal += 1
            elif ENTITY.sub("<E>", a) == ENTITY.sub("<E>", b):
                entity_only += 1
            elif first_bad is None:
                first_bad = i
        structural = compared - equal - entity_only
        label = f"{os.path.basename(os.path.dirname(path))}/{os.path.basename(path)}"
        result = (
            f"{label}: ours={len(ours)} hs_forwarded={len(theirs)} compared={compared} "
            f"equal={equal} entityName_only={entity_only} structural={structural}"
        )
        extra = len(theirs) - len(ours)
        if extra > 0:
            result += f" hs_extra_after={extra}"
        elif extra < 0:
            result += f" ours_extra={-extra}"
        if first_bad is not None:
            result += f" first structural mismatch at seq {first_bad + 1}"
        # Prefer the session whose prefix actually matches this game (CREATE_GAME appears in every log).
        score = (equal + entity_only, -structural, -abs(extra))
        if best is None or score > best[0]:
            best = (score, result)
    return best[1] if best else "first raw line not found in Hearthstone logs (log rotated, or first line anonymised)"


def dir_size(game_dir):
    return {n: os.path.getsize(os.path.join(game_dir, n)) for n in sorted(os.listdir(game_dir))}


def report(game_dir, hs_root):
    print(f"=== {os.path.basename(game_dir)}")
    meta_path = os.path.join(game_dir, "meta.json")
    meta = json.load(open(meta_path, encoding="utf-8")) if os.path.exists(meta_path) else {}
    keys = ("pluginVersion", "gameTypeAtStart", "gameTypeAtEnd", "isBattlegroundsMatch", "isBattlegroundsDuosMatch",
            "hearthstoneBuild", "endReason", "lines", "records", "hdtBobsBuddyDumps", "errors", "writerErrors", "disabled",
            "probeInitError")
    for k in keys:
        if k in meta:
            print(f"  {k}: {meta[k]}")
    for k in ("hdt", "bobsBuddy", "hearthDb"):
        if k in meta:
            print(f"  {k}: {meta[k].get('fileVersion')} ({meta[k].get('directory')})")
    if "endedAt" not in meta:
        print("  WARN: meta.json has no endedAt (game not finished, or HDT closed mid-game)")
    print("  files:", ", ".join(f"{n}={s:,}" for n, s in dir_size(game_dir).items()))

    records = read_records(game_dir)
    counts = Counter(r.get("type") for r in records)
    print("  record types:", dict(counts))
    bad = [r for r in records if r.get("type") == "_bad_json"]
    if bad:
        print(f"  WARN: {len(bad)} unparsable record lines")
    for r in [r for r in records if r.get("type") in ("error", "writer_error")][:5]:
        print(f"  error [{r.get('where', 'writer')}]: {r.get('exception', '').splitlines()[0][:200]}")

    combats = segment_combats(records)
    print(f"  combats: {len(combats)}")
    header = ("combat", "turn", "startSnap", "startSnapEntities", "startSnapMs", "hdtBbDumps", "hdtBbTurns",
              "states", "maxReRun", "hasOutput", "endSnap", "errors")
    print("  " + " | ".join(header))
    incomplete = 0
    for i, c in enumerate(combats, 1):
        row = combat_row(i, c)
        print("  " + " | ".join(str(row[h]) for h in header))
        reasons = missing_reasons(row)
        if reasons:
            incomplete += 1
            print("      missing: " + "; ".join(reasons))
    print(f"  complete combats: {len(combats) - incomplete}/{len(combats)}")

    perf = perf_summary(records)
    if perf:
        print("  perf (final):")
        for name, s in perf.items():
            print(f"    {name}: {s}")
        line_threads = set(perf.get("line", {}).get("threads") or [])
        update_threads = set(perf.get("update", {}).get("threads") or [])
        if line_threads and update_threads:
            print(f"  line thread == update thread: {line_threads == update_threads} ({sorted(line_threads)} / {sorted(update_threads)})")

    hits = anonymisation_scan(game_dir)
    print("  anonymisation:", "OK (no BattleTag / account id patterns)" if not hits else f"FAIL {dict(hits)}")

    if hs_root:
        print("  raw lines vs Hearthstone Power.log:", compare_with_hs(game_dir, hs_root))
    print()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dirs", nargs="*")
    ap.add_argument("--root", default=DEFAULT_ROOT)
    ap.add_argument("--hs-logs", default=DEFAULT_HS_LOGS)
    ap.add_argument("--all", action="store_true")
    args = ap.parse_args()
    if args.hs_logs.lower() == "none":
        args.hs_logs = ""

    dirs = args.dirs
    if not dirs:
        if not os.path.isdir(args.root):
            sys.exit(f"no records root: {args.root}")
        games = sorted(d for d in os.listdir(args.root) if os.path.isdir(os.path.join(args.root, d)))
        if not games:
            sys.exit(f"no game directories under {args.root}")
        dirs = [os.path.join(args.root, d) for d in (games if args.all else games[-1:])]
    for d in dirs:
        report(d, args.hs_logs)


if __name__ == "__main__":
    main()
