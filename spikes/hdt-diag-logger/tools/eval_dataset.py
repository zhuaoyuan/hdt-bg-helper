"""One-shot evaluation of BgHelperDiag records (completeness + version cohorts)."""
import collections
import json
import os
import sys
from pathlib import Path

from diag_io import read_records

ROOT = Path(sys.argv[1] if len(sys.argv) > 1 else r"C:\projects\github\hdt-bg-helper\data\BgHelperDiag")
APPDATA = Path(os.environ.get("APPDATA", "")) / "HearthstoneDeckTracker" / "BgHelperDiag"


def load_meta(gd: Path):
    p = gd / "meta.json"
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8"))


def load_records(gd: Path):
    return read_records(str(gd))


def segment_combats(records):
    combats, current = [], None
    for r in records:
        if r.get("type") == "combat_phase" and r.get("value") is True:
            if current is not None:
                combats.append(current)
            current = {"recs": [r]}
        elif current is not None:
            current["recs"].append(r)
    if current is not None:
        combats.append(current)
    return combats


def dump_parts(r):
    dump = r.get("dump") or r
    if not isinstance(dump, dict):
        dump = {}
    inp = dump.get("input") if "input" in dump else r.get("input")
    outp = dump.get("output") or dump.get("Output") or r.get("output")
    rr = dump.get("reRunCount")
    if rr is None:
        rr = r.get("reRunCount")
    return inp, outp, rr


def analyze_game(gd: Path):
    meta = load_meta(gd)
    records = load_records(gd)
    types = collections.Counter(r.get("type") for r in records)
    combats = segment_combats(records)
    complete = partial = 0
    missing_detail = collections.Counter()
    inputs_with = outputs_with = reruns = anomalies = 0
    opp_secrets = opp_hand_known = opp_hand_unknown = 0
    damage_caps = set()
    race_sets = []
    sim_counts = []
    combat_tags_2022 = combat_tags_3533 = 0
    leftover_before_first_combat = 0

    first_combat_seq = None
    for r in records:
        if r.get("type") == "combat_phase" and r.get("value") is True:
            first_combat_seq = r.get("seq")
            break

    for r in records:
        if r.get("type") == "combat_tag":
            tag = r.get("tag")
            val = r.get("value")
            if tag in (2022, "2022") and val == 0:
                combat_tags_2022 += 1
            if tag in (3533, "3533") and val == 0:
                combat_tags_3533 += 1
        if r.get("type") != "hdt_bb":
            continue
        if first_combat_seq is not None and r.get("seq") is not None and r.get("seq") < first_combat_seq:
            leftover_before_first_combat += 1
        inp, outp, rr = dump_parts(r)
        if inp:
            inputs_with += 1
            if inp.get("Anomaly") or inp.get("anomalyDbfId"):
                anomalies += 1
            races = inp.get("availableRaces") or inp.get("AvailableRaces")
            if races:
                race_sets.append(tuple(sorted(str(x) for x in races)))
            dc = inp.get("DamageCap", inp.get("damageCap"))
            if dc is not None:
                damage_caps.add(dc)
            opp = inp.get("Opponent") or inp.get("opponent") or {}
            for h in opp.get("Hand") or opp.get("hand") or []:
                cid = h.get("CardId") or h.get("cardId") if isinstance(h, dict) else None
                if cid in (None, "", "Unknown", "UNKNOWN"):
                    opp_hand_unknown += 1
                else:
                    opp_hand_known += 1
            if opp.get("Secrets") or opp.get("secrets"):
                opp_secrets += 1
        if outp:
            outputs_with += 1
            sc = outp.get("simulationCount") or outp.get("SimulationCount")
            if sc is not None:
                sim_counts.append(sc)
        if rr is not None and int(rr) > 0:
            reruns += 1

    for c in combats:
        recs = c["recs"]
        ent_reasons = [r.get("reason") for r in recs if r.get("type") == "entities"]
        has_start = "combat_start" in ent_reasons
        has_end = "combat_end" in ent_reasons
        has_input = has_output = False
        for r in recs:
            if r.get("type") != "hdt_bb":
                continue
            inp, outp, _ = dump_parts(r)
            if inp:
                has_input = True
            if outp:
                has_output = True
        if has_start and has_input and has_output and has_end:
            complete += 1
        else:
            partial += 1
            if not has_start:
                missing_detail["no_combat_start_entities"] += 1
            if not has_input:
                missing_detail["no_input"] += 1
            if not has_output:
                missing_detail["no_output"] += 1
            if not has_end:
                missing_detail["no_combat_end_entities"] += 1

    sizes = {}
    for name in ("records.jsonl.gz", "records.jsonl", "power.log.gz", "power.log", "meta.json"):
        p = gd / name
        if p.exists():
            sizes[name] = p.stat().st_size

    return {
        "id": gd.name,
        "meta": meta,
        "types": dict(types),
        "bad_json": types.get("_bad_json", 0),
        "n_combats": len(combats),
        "complete_combats": complete,
        "partial_combats": partial,
        "missing": dict(missing_detail),
        "inputs_with": inputs_with,
        "outputs_with": outputs_with,
        "reruns": reruns,
        "anomalies_inputs": anomalies,
        "opp_secrets_rounds": opp_secrets,
        "opp_hand_known": opp_hand_known,
        "opp_hand_unknown": opp_hand_unknown,
        "sim_counts_unique": sorted(set(sim_counts))[:12],
        "combat_tags_2022_zero": combat_tags_2022,
        "combat_tags_3533_zero": combat_tags_3533,
        "leftover_bb_before_combat": leftover_before_first_combat,
        "unique_race_sets": len(set(race_sets)),
        "damage_caps": sorted(damage_caps),
        "sizes": sizes,
    }


def main():
    games = [analyze_game(gd) for gd in sorted(ROOT.iterdir()) if gd.is_dir()]
    print("ROOT", ROOT)
    print("GAMES", len(games))

    by_ver = collections.defaultdict(list)
    for g in games:
        m = g["meta"] or {}
        key = (
            (m.get("hdt") or {}).get("fileVersion"),
            (m.get("bobsBuddy") or {}).get("fileVersion"),
            (m.get("hearthDb") or {}).get("fileVersion"),
            m.get("hearthstoneBuild"),
        )
        by_ver[key].append(g)

    print("\n=== VERSION COHORTS ===")
    for k, gs in sorted(by_ver.items(), key=lambda x: x[1][0]["id"]):
        dates = [g["id"][:8] for g in gs]
        print(
            "HDT=%s BB=%s HearthDb=%s HS=%s | n=%d | %s..%s"
            % (k[0], k[1], k[2], k[3], len(gs), min(dates), max(dates))
        )
        print("  " + ", ".join(g["id"] for g in gs))

    print("\n=== PER-GAME SUMMARY ===")
    hdr = (
        f'{"id":28} {"end":14} {"comb":>5} {"ok":>4} {"part":>4} '
        f'{"err":>4} {"dump":>5} {"bb":>5} {"in":>4} {"out":>4} '
        f'{"MB":>6} {"duos":>5} {"left":>5}'
    )
    print(hdr)
    total_ok = total_part = total_combats = 0
    issues = []
    for g in games:
        m = g["meta"] or {}
        end = m.get("endReason", "?")
        errs = m.get("errors", -1)
        dumps = m.get("hdtBobsBuddyDumps", -1)
        hdt_bb = g["types"].get("hdt_bb", 0)
        mb = (g["sizes"].get("records.jsonl.gz", 0) or g["sizes"].get("records.jsonl", 0)) / 1e6
        duos = m.get("isBattlegroundsDuosMatch")
        print(
            f'{g["id"]:28} {str(end):14} {g["n_combats"]:5} {g["complete_combats"]:4} '
            f'{g["partial_combats"]:4} {errs:4} {dumps:5} {hdt_bb:5} {g["inputs_with"]:4} '
            f'{g["outputs_with"]:4} {mb:6.1f} {str(duos):>5} {g["leftover_bb_before_combat"]:5}'
        )
        total_ok += g["complete_combats"]
        total_part += g["partial_combats"]
        total_combats += g["n_combats"]
        if g["partial_combats"] or g["bad_json"] or errs or "endedAt" not in m:
            issues.append(g)

    print(
        f"\nTOTAL combats={total_combats} complete={total_ok} partial={total_part} "
        f"complete_rate={total_ok / total_combats if total_combats else 0:.3f}"
    )
    print("games_with_issues", len(issues))
    for g in issues:
        m = g["meta"] or {}
        print(
            " ISSUE",
            g["id"],
            "partial",
            g["partial_combats"],
            "missing",
            g["missing"],
            "bad_json",
            g["bad_json"],
            "errors",
            m.get("errors"),
            "end",
            m.get("endReason"),
            "endedAt",
            "endedAt" in m,
            "probe",
            m.get("probeInitError"),
            "disabled",
            m.get("disabled"),
        )

    print("\n=== COVERAGE SIGNALS ===")
    print("duos games", sum(1 for g in games if (g["meta"] or {}).get("isBattlegroundsDuosMatch")))
    print("anomaly input dumps", sum(g["anomalies_inputs"] for g in games))
    print("rerun dumps (>0)", sum(g["reruns"] for g in games))
    print("opp secret rounds", sum(g["opp_secrets_rounds"] for g in games))
    print(
        "opp hand known/unknown",
        sum(g["opp_hand_known"] for g in games),
        sum(g["opp_hand_unknown"] for g in games),
    )
    caps = collections.Counter()
    for g in games:
        for c in g["damage_caps"]:
            caps[c] += 1
    print("damageCap values (games containing)", dict(caps))
    print("simCount uniques sample", sorted({sc for g in games for sc in g["sim_counts_unique"]})[:20])
    print(
        "leftover invoker dumps before first combat (games>0)",
        sum(1 for g in games if g["leftover_bb_before_combat"] > 0),
        "total dumps",
        sum(g["leftover_bb_before_combat"] for g in games),
    )

    by_day = collections.Counter(g["id"][:8] for g in games)
    print("\n=== BY DAY ===")
    for d, n in sorted(by_day.items()):
        print(d, n)

    total_rec = sum(
        g["sizes"].get("records.jsonl.gz", 0) + g["sizes"].get("records.jsonl", 0) for g in games
    )
    total_pow = sum(
        g["sizes"].get("power.log.gz", 0) + g["sizes"].get("power.log", 0) for g in games
    )
    print(f"\nSIZE records[.jsonl|.gz]={total_rec / 1e9:.2f} GB  power={total_pow / 1e6:.1f} MB")
    print(f"avg records/game={total_rec / max(len(games), 1) / 1e6:.1f} MB")

    # cohort completeness
    print("\n=== COMPLETENESS BY COHORT ===")
    for k, gs in sorted(by_ver.items(), key=lambda x: x[1][0]["id"]):
        c = sum(g["n_combats"] for g in gs)
        ok = sum(g["complete_combats"] for g in gs)
        part = sum(g["partial_combats"] for g in gs)
        err = sum((g["meta"] or {}).get("errors", 0) or 0 for g in gs)
        print(
            f"HS={k[3]} HDT={k[0]} BB={k[1]}: games={len(gs)} combats={c} ok={ok} partial={part} meta_errors={err}"
        )

    if APPDATA.exists():
        print("\n=== APPDATA OLD ===")
        for gd in sorted(APPDATA.iterdir()):
            if not gd.is_dir():
                continue
            m = load_meta(gd)
            if not m:
                continue
            print(
                gd.name,
                m.get("hdt", {}).get("fileVersion"),
                m.get("bobsBuddy", {}).get("fileVersion"),
                m.get("hearthstoneBuild"),
                m.get("endReason"),
                m.get("recordCounts"),
            )


if __name__ == "__main__":
    main()
