"""Q-004 / Q-010 / Q-008: analyse HDT logs for Bob's Buddy simulation input/output coverage.

Usage:  python analyze_logs.py [--log-dir DIR]
Writes: out/log_report.json (aggregate, contains no names), out/analyze_logs_summary.txt (readable summary),
        out/sims.jsonl, out/mod_lines_raw.txt (raw, may contain personal data; out/ is git-ignored).
"""
from __future__ import annotations

import argparse
import collections
import json
import os
import re
import sys

import hdtlog
import srctemplates

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")

CARD_RE = re.compile(r"\b(?:BG\w*|TB_\w+|BGS_\w+|BGN_\w+)\b")


def normalize_mod(msg: str) -> str:
    """Anonymise a modded ('团子') log line into a template."""
    t = msg
    t = re.sub(r"\d+\.\d+\.\d+\.\d+(:\d+)?", "<IP>", t)
    t = re.sub(r"(对手：).*", r"\1<英雄名>", t)
    t = re.sub(r"(随从\d+：).*", "随从N：<中文卡名>（<CardId>）", t)
    t = re.sub(r"(，player：)\w+", r"\1<Player|Opponent>", t)
    t = CARD_RE.sub("<CardId>", t)
    t = re.sub(r"-?\d+", "N", t)
    return t


def pct(values, p):
    if not values:
        return None
    s = sorted(values)
    k = min(len(s) - 1, max(0, int(round(p / 100 * (len(s) - 1)))))
    return s[k]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--log-dir", default=hdtlog.DEFAULT_LOG_DIR)
    args = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    sys.stdout = open(os.path.join(OUT, "analyze_logs_summary.txt"), "w", encoding="utf-8")

    sessions = hdtlog.load_sessions(args.log_dir)
    templates_by_rev = {}

    report = {"sessions": [], "games": [], "sims": {}, "fields": {}, "q010": {}}
    all_sims = []
    mod_templates = collections.Counter()
    mod_raw = []
    unmatched_bb = collections.Counter()
    seen_src_lines = collections.defaultdict(collections.Counter)  # rev -> line -> count
    counter_keys = collections.Counter()
    validation = collections.Counter()
    errors = collections.Counter()
    games = {}

    for s in sessions:
        sims = hdtlog.parse_sims(s)
        all_sims.extend(sims)
        rev = srctemplates.VERSION_REV.get(s.hdt_version or "")
        if rev and rev not in templates_by_rev:
            templates_by_rev[rev] = [t for t in srctemplates.extract(srctemplates.git_show(rev))
                                     if t["line"] > 125 or t["has_literal"]]
        tpls = templates_by_rev.get(rev, [])
        lit_tpls = [t for t in tpls if t["has_literal"]]

        n_rerun_lines = 0
        game_of_line = None
        spectator_flag = False
        for no, sec, level, src, msg in s.lines:
            if hdtlog.MOD_MARK in msg:
                mod_templates[(src, normalize_mod(msg))] += 1
                mod_raw.append(f"{s.file}:{no}: {src} >> {msg}")
            if src.startswith("BobsBuddyInvoker."):
                if hdtlog.MOD_MARK not in msg:
                    hit = next((t for t in lit_tpls if t["regex"].match(msg)), None)
                    if hit:
                        seen_src_lines[rev][hit["line"]] += 1
                    else:
                        shape = "minion" if hdtlog.parse_minion(msg) else (
                            "guid_key" if hdtlog.KEY_RE.match(msg) else "other")
                        unmatched_bb[(src, shape if shape != "other" else re.sub(r"\d+", "N", msg)[:100])] += 1
                k = hdtlog.KEY_RE.match(msg)
                if k:
                    gid, turn = k.group(1), int(k.group(2))
                    g = games.setdefault(gid, {"file": s.file, "hdt": s.hdt_version,
                                               "builds": s.carddefs_builds[:], "keys": set(),
                                               "end_turns": None, "spectator": False,
                                               "start_guess": s.start_guess.isoformat() if s.start_guess else None,
                                               "mtime": s.mtime.isoformat()})
                    g["keys"].add(turn)
                    game_of_line = gid
                if src == "BobsBuddyInvoker.TryRerun":
                    n_rerun_lines += 1
                if src == "BobsBuddyInvoker.SetupInputPlayer":
                    for kk in re.findall(r"(\w+)=", msg):
                        counter_keys[kk] += 1
                if src == "BobsBuddyInvoker.ValidateSimulationResultAsync" and msg.startswith("result="):
                    validation[msg] += 1
                if src == "BobsBuddyInvoker.HasErrorState" or "Exception" in msg or msg.startswith("Unsupported"):
                    errors[re.sub(r"\d+", "N", msg)[:120]] += 1
            if src == "GameStats.GameEnd":
                m = re.search(r"ended after (\d+) turns", msg)
                if m and game_of_line and games[game_of_line]["end_turns"] is None:
                    games[game_of_line]["end_turns"] = int(m.group(1))
            if src == "GameEventHandler.SaveAndUpdateStats" and "Spectator" in msg and game_of_line:
                games[game_of_line]["spectator"] = True

        report["sessions"].append({
            "file": s.file, "hdt_version": s.hdt_version, "os": s.os, "carddefs_builds": sorted(set(s.carddefs_builds)),
            "start_guess": s.start_guess.isoformat() if s.start_guess else None, "mtime": s.mtime.isoformat(),
            "lines": len(s.lines), "sim_blocks": len(sims), "rerun_log_lines": n_rerun_lines,
            "snapshots": sum(1 for l in s.lines if l[3] == "BobsBuddyInvoker.SnapshotBoardState"
                             and l[4] == "Snapshotting board state..."),
            "combat_keys": len({x.key for x in sims}),
        })

    # ---- simulations
    first = [x for x in all_sims if x.rerun_index == 0]
    reruns = [x for x in all_sims if x.rerun_index > 0]
    keys = collections.Counter(x.key for x in all_sims)
    outs = [x.output for x in all_sims if x.output]
    exitc = collections.Counter(o.get("exit") for o in outs)
    iters = collections.Counter(o.get("iterations") for o in outs)
    rerun_diff = collections.Counter()
    prev_by_key = {}
    for x in all_sims:
        p = prev_by_key.get(x.key)
        if p is not None:
            changed = []
            for i, (a, b) in enumerate(zip(p.sides, x.sides)):
                who = ["player", "opponent", "p_mate", "o_mate"][i]
                for f in ("hero_powers", "hand_raw", "minions", "quests"):
                    if getattr(a, f) != getattr(b, f):
                        changed.append(f"{who}.{f}")
            if p.secrets != x.secrets:
                changed.append("secrets")
            rerun_diff[(str(x.trigger), ",".join(changed) or "(identical)")] += 1
        prev_by_key[x.key] = x
    report["rerun_input_diff"] = [(a, b, n) for (a, b), n in rerun_diff.most_common()]

    # Same logged input, simulated twice: spread of win rate = BB Monte-Carlo noise (+ unlogged input changes)
    deltas = []
    prev_by_key = {}
    for x in all_sims:
        p = prev_by_key.get(x.key)
        if p is not None and p.output and x.output and "win" in p.output and "win" in x.output:
            same = all(getattr(a, f) == getattr(b, f) for a, b in zip(p.sides, x.sides)
                       for f in ("hero_powers", "hand_raw", "minions", "quests")) and p.secrets == x.secrets
            if same:
                deltas.append(max(abs(p.output[k] - x.output[k]) for k in ("win", "tie", "loss")))
        prev_by_key[x.key] = x
    report["identical_logged_input_pairs"] = {"pairs": len(deltas), "max_abs_delta_pct_points": sorted(deltas)}

    # Calibration: last simulation of each combat vs HDT's own result line
    last_out = {}
    for x in all_sims:
        if x.output and "win" in x.output:
            last_out[x.key] = x.output
    outcome_of_key = {}
    for s in sessions:
        k_cur = None
        for no, sec, level, src, msg in s.lines:
            if src == "BobsBuddyInvoker.StartShoppingAsync":
                k = hdtlog.KEY_RE.match(msg)
                if k and msg.strip() == k.group(0):
                    k_cur = k.group(0)
            if src == "BobsBuddyInvoker.ValidateSimulationResultAsync" and msg.startswith("result=") and k_cur:
                outcome_of_key[k_cur] = re.match(r"result=(\w+)", msg).group(1)
                k_cur = None
    cal = collections.defaultdict(list)
    for k, o in last_out.items():
        r = outcome_of_key.get(k)
        if r in ("Win", "Loss", "Tie"):
            cal[r].append(o)
    brier = []
    for r, lst in cal.items():
        for o in lst:
            p = {"Win": o["win"], "Tie": o["tie"], "Loss": o["loss"]}
            brier.append(sum((p[c] / 100 - (1.0 if c == r else 0.0)) ** 2 for c in p))
    report["calibration"] = {
        r: {"n": len(lst), "mean_pred_win": round(sum(o["win"] for o in lst) / len(lst), 1),
            "mean_pred_tie": round(sum(o["tie"] for o in lst) / len(lst), 1),
            "mean_pred_loss": round(sum(o["loss"] for o in lst) / len(lst), 1)} for r, lst in cal.items()}
    report["calibration"]["brier_3class_mean"] = round(sum(brier) / len(brier), 3) if brier else None

    report["sims"] = {
        "blocks": len(all_sims), "first_runs": len(first), "rerun_blocks": len(reruns),
        "blocks_by_trigger": dict(collections.Counter(str(x.trigger) for x in all_sims)),
        "tryrerun_log_lines": sum(r["rerun_log_lines"] for r in report["sessions"]),
        "snapshot_attempts": sum(r["snapshots"] for r in report["sessions"]),
        "distinct_combat_keys": len(keys), "blocks_without_output": sum(1 for x in all_sims if not x.output),
        "exit_conditions": dict(exitc), "iterations_top": iters.most_common(8),
        "max_iter_threads": collections.Counter(f"{x.max_iter}/{x.threads}" for x in all_sims).most_common(),
        "duration_ms_p50_p90_max": [pct([o["duration_ms"] for o in outs], p) for p in (50, 90, 100)],
        "time_exit_iter_p10_p50": [pct([o["iterations"] for o in outs if o["exit"] == "Time"], p) for p in (10, 50)],
        "output_keys": sorted({k for o in outs for k in o}),
        "validation_results": dict(validation),
        "errors": errors.most_common(20),
        "unparsed_input_lines": collections.Counter(
            re.sub(r"\d+", "N", m)[:80] for x in all_sims for _, m in x.unparsed).most_common(20),
    }

    # ---- field coverage
    flags, kvs, hand_kinds, ench, dr = (collections.Counter() for _ in range(5))
    n_minions = n_mod_minion = sides_with_hp = sides = mism = 0
    hp_data_nonzero = 0
    quest_lines = 0
    secret_lines = collections.Counter()
    opp_hand_nonempty = 0
    block_feats = collections.Counter()
    blocks_plain = 0
    for x in all_sims:
        for i, sd in enumerate(x.sides[:2]):
            sides += 1
            sides_with_hp += bool(sd.hero_powers)
            hp_data_nonzero += sum(1 for h in sd.hero_powers if h["data"] != "0")
            n_minions += len(sd.minions)
            n_mod_minion += len(sd.mod_minions)
            if sd.mod_minions and len(sd.mod_minions) != len(sd.minions):
                mism += 1
            quest_lines += len(sd.quests)
            if i == 1 and sd.hand:
                opp_hand_nonempty += 1
            for h in sd.hand:
                hand_kinds[("player:" if i == 0 else "opponent:") +
                           ("minion" if h.startswith("[") else re.sub(r"\d+", "N", h))] += 1
            for mn in sd.minions:
                flags.update(mn["flags"])
                for k, v in mn["kv"].items():
                    kvs[k] += 1
                    if k == "Enchantments":
                        ench.update(re.findall(r"(\w+)\(", v))
                    if k == "Deathrattles":
                        dr.update(t.strip() for t in v.strip("[]").split(","))
        for k, v in x.secrets.items():
            secret_lines[k] += len(v)
        feats = []
        if any(sd.quests for sd in x.sides):
            feats.append("quest")
        if x.secrets:
            feats.append("secret")
        if any("Enchantments" in mn["kv"] or "Deathrattles" in mn["kv"] or "AttachedModularEntity" in mn["kv"]
               for sd in x.sides for mn in sd.minions):
            feats.append("minion_extras")
        if any(h["data"] != "0" for sd in x.sides for h in sd.hero_powers):
            feats.append("hp_data")
        block_feats.update(feats or ["plain"])
        blocks_plain += not feats
    report["fields"] = {
        "block_features": dict(block_feats), "blocks_plain": blocks_plain,
        "sides": sides, "sides_with_hero_power_line": sides_with_hp, "hero_power_data_nonzero": hp_data_nonzero,
        "minions": n_minions, "mod_minion_lines": n_mod_minion, "sides_mod_minion_count_mismatch": mism,
        "minion_flags": dict(flags.most_common()), "minion_kv": dict(kvs.most_common()),
        "enchantment_types": len(ench), "enchantments_top": ench.most_common(15),
        "deathrattle_tokens": dict(dr), "hand_item_kinds": dict(hand_kinds.most_common()),
        "opponent_hand_nonempty_blocks": opp_hand_nonempty, "quest_lines": quest_lines,
        "secret_lines": dict(secret_lines), "setup_input_player_counter_keys": dict(counter_keys.most_common()),
        "sample_secret_values": sorted({v for x in all_sims for vs in x.secrets.values() for v in vs})[:20],
    }

    # ---- Q-010: source statements vs log
    q010 = {"unmatched_bobsbuddy_lines": [(a, b, n) for (a, b), n in unmatched_bb.most_common(40)],
            "mod_templates": [(a, b, n) for (a, b), n in mod_templates.most_common()],
            "never_seen_source_statements": {}}
    for rev, tpls in templates_by_rev.items():
        seen_texts = {t["text"] for t in tpls if seen_src_lines[rev][t["line"]]}
        q010["never_seen_source_statements"][rev] = [
            (t["line"], t["text"]) for t in tpls if t["has_literal"] and t["text"] not in seen_texts]
    report["q010"] = q010

    # ---- games (Q-008)
    for gid, g in games.items():
        report["games"].append({
            "game": f"g{len(report['games']) + 1:03d}", "file": g["file"], "hdt": g["hdt"], "builds": sorted(set(g["builds"])),
            "session_start_guess": g["start_guess"], "session_mtime": g["mtime"],
            "combat_turns": sorted(g["keys"]), "max_combat_turn": max(g["keys"]),
            "end_turns": g["end_turns"], "spectator": g["spectator"],
            "sim_blocks": sum(1 for x in all_sims if x.key and x.key.startswith(gid)),
        })

    with open(os.path.join(OUT, "log_report.json"), "w", encoding="utf-8") as fh:
        json.dump(report, fh, ensure_ascii=False, indent=1, default=str)
    with open(os.path.join(OUT, "mod_lines_raw.txt"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(mod_raw))
    with open(os.path.join(OUT, "sims.jsonl"), "w", encoding="utf-8") as fh:
        for x in all_sims:
            fh.write(json.dumps({"file": x.file, "line": x.line, "key": x.key, "rerun": x.rerun_index,
                                 "trigger": x.trigger,
                                 "sides": [sd.__dict__ for sd in x.sides], "secrets": x.secrets,
                                 "output": x.output}, ensure_ascii=False) + "\n")

    # ---- anonymised console summary
    print("== sessions")
    for r in report["sessions"]:
        print(f"  {r['file']} hdt={r['hdt_version']} os={r['os']} builds={r['carddefs_builds']} start~{r['start_guess']} "
              f"end={r['mtime'][:16]} sims={r['sim_blocks']} reruns={r['rerun_log_lines']} snaps={r['snapshots']}")
    print("== sims", json.dumps(report["sims"], ensure_ascii=False, default=str, indent=1))
    print("== repeated blocks of the same combat: trigger | what changed vs previous block")
    for a, b, n in report["rerun_input_diff"]:
        print(f"  {n:4d} {a} | {b}")
    print("== identical logged input pairs", json.dumps(report["identical_logged_input_pairs"]))
    print("== calibration", json.dumps(report["calibration"]))
    print("== fields", json.dumps(report["fields"], ensure_ascii=False, default=str, indent=1))
    print("== q010 unmatched BobsBuddyInvoker lines (no mod mark)")
    for a, b, n in q010["unmatched_bobsbuddy_lines"]:
        print(f"  {n:5d} {a} | {b}")
    print("== q010 mod templates")
    for a, b, n in q010["mod_templates"]:
        print(f"  {n:5d} {a} | {b}")
    print("== q010 source statements never seen in logs of that version")
    for rev, lst in q010["never_seen_source_statements"].items():
        print(f"  [{rev}]")
        for ln, t in lst:
            print(f"     {ln}: {t}")
    print("== games")
    for g in report["games"]:
        print(f"  {g['game']} {g['file']} hdt={g['hdt']} builds={g['builds']} maxTurn={g['max_combat_turn']} "
              f"endTurns={g['end_turns']} spect={g['spectator']} sims={g['sim_blocks']} ncombats={len(g['combat_turns'])}")


if __name__ == "__main__":
    main()
