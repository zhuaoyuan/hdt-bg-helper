"""Q-006 timing: 3533 vs 2022 vs phase vs Input. Also fix TagTransfer named-tag match."""
import gzip
import json
import os
import re
from collections import Counter, defaultdict

ROOT = os.path.join(os.environ["APPDATA"], "HearthstoneDeckTracker", "BgHelperDiag")


def games():
    return [os.path.join(ROOT, d) for d in sorted(os.listdir(ROOT))
            if os.path.isdir(os.path.join(ROOT, d))]


def recs(d):
    with open(os.path.join(d, "records.jsonl"), encoding="utf-8") as f:
        return [json.loads(r) for r in f]


def raw_lines(d, seqs):
    want = set(seqs)
    p = os.path.join(d, "power.log.gz")
    if not os.path.exists(p):
        p = os.path.join(d, "power.log")
    opener = gzip.open if p.endswith(".gz") else open
    found = {}
    try:
        with opener(p, "rt", encoding="utf-8", errors="replace") as f:
            for row in f:
                seq, _ms, line = row.rstrip("\n").split("\t", 2)
                seq = int(seq)
                if seq in want:
                    found[seq] = line
    except EOFError:
        pass
    return found


def find_input(inv):
    inner = (inv or {}).get("_input")
    if isinstance(inner, dict) and inner.get("$type") == "BobsBuddy.Simulation.Input":
        return inner
    return None


def tag(e, n, default=None):
    return (e.get("tags") or {}).get(n, default)


def coll_n(obj):
    if isinstance(obj, dict) and obj.get("items") is not None:
        return len(obj["items"])
    return 0


def unknown_hand(obj):
    n = 0
    if not isinstance(obj, dict):
        return 0
    for it in obj.get("items") or []:
        t = (it.get("$type") or "") if isinstance(it, dict) else ""
        if "Unknown" in t:
            n += 1
    return n


print("=== 3533 / 2022 / phase / Input alignment ===")
gaps = []
input_on_2022 = 0
input_n = 0
phase_on_3533 = 0
phase_n = 0
snap_vs_input_side = []

for g in games():
    name = os.path.basename(g)
    rs = recs(g)
    tags = [r for r in rs if r.get("type") == "combat_tag"]
    phases = [r for r in rs if r.get("type") == "combat_phase" and r.get("value") is True]
    snaps = [r for r in rs if r.get("type") == "entities" and r.get("reason") == "combat_start"]
    bbs = [r for r in rs if r.get("type") == "hdt_bb" and r.get("hasInput")]
    print(f"\n-- {name} --")
    print("turn | 3533=0 | 2022=0 | phase | snap | firstInput | gap3533to2022 | Input-2022 | phase-3533")
    for ph, snap in zip(phases, snaps):
        turn = (snap.get("context") or {}).get("turn")
        t3533 = next((r for r in tags if r.get("tag") == 3533 and r.get("value") == 0
                      and abs((r.get("lineSeq") or 0) - ph["lineSeq"]) < 20), None)
        t2022 = next((r for r in tags if r.get("tag") == 2022 and r.get("value") == 0
                      and r.get("lineSeq") >= ph["lineSeq"] - 5), None)
        first = next((r for r in bbs if r.get("key") == turn and r.get("lineSeq") >= ph["lineSeq"]), None)
        a = t3533["lineSeq"] if t3533 else None
        b = t2022["lineSeq"] if t2022 else None
        c = ph["lineSeq"]
        d = snap["lineSeq"]
        e = first["lineSeq"] if first else None
        gap = (b - a) if a and b else None
        on2022 = (e == b) if e and b else False
        on3533 = (c == a) if c and a else False
        if gap is not None:
            gaps.append(gap)
        input_n += 1
        input_on_2022 += int(on2022)
        phase_n += 1
        phase_on_3533 += int(on3533)
        inp = find_input((first or {}).get("invoker"))
        p_side = coll_n((inp or {}).get("Player", {}).get("Side")) if inp else None
        o_side = coll_n((inp or {}).get("Opponent", {}).get("Side")) if inp else None
        ctx = snap.get("context") or {}
        # board lists include player entity, hero, hp, enchants... count minions via CARDTYPE=4
        ents = {x["id"]: x for x in snap.get("entities") or []}

        def minions(ids):
            n = 0
            for i in ids or []:
                e = ents.get(i)
                if e and tag(e, "CARDTYPE") == 4:
                    n += 1
            return n
        pm, om = minions(ctx.get("player", {}).get("board")), minions(ctx.get("opponent", {}).get("board"))
        snap_vs_input_side.append((turn, pm, p_side, om, o_side, pm == p_side, om == o_side))
        print(f"  {turn} | {a} | {b} | {c} | {d} | {e} | {gap} | {on2022} | {on3533} "
              f"| minions snap/in P {pm}/{p_side} O {om}/{o_side}")

print(f"\nphase line == 3533=0: {phase_on_3533}/{phase_n}")
print(f"first Input line == 2022=0: {input_on_2022}/{input_n}")
if gaps:
    print(f"lines between 3533=0 and 2022=0: n={len(gaps)} min={min(gaps)} max={max(gaps)} "
          f"median={sorted(gaps)[len(gaps)//2]}")
side_p = sum(1 for t in snap_vs_input_side if t[5])
side_o = sum(1 for t in snap_vs_input_side if t[6])
print(f"minion count snap==Input Player {side_p}/{len(snap_vs_input_side)} "
      f"Opponent {side_o}/{len(snap_vs_input_side)}")
mismatch = [t for t in snap_vs_input_side if not t[5] or not t[6]]
if mismatch:
    print("  mismatches (turn, snapP, inP, snapO, inO):",
          [(t[0], t[1], t[2], t[3], t[4]) for t in mismatch])

# What is on the 3533=0 line vs 2022=0
print("\n=== sample lines at 3533=0 and 2022=0 (first game, first 3 combats) ===")
g0 = games()[0]
rs = recs(g0)
tags = [r for r in rs if r.get("type") == "combat_tag"]
want = [r["lineSeq"] for r in tags if r.get("value") == 0][:8]
raw = raw_lines(g0, want)
for r in tags:
    if r.get("value") == 0 and r["lineSeq"] in raw:
        line = re.sub(r"player_[0-9a-f]{8}", "<P>", raw[r["lineSeq"]])
        print(f"  tag={r['tag']} lineSeq={r['lineSeq']} entity={r.get('entity')} | {line[:160]}")

# Named vs numeric elemental tag
print("\n=== ElementalPlayCounter: TF named tag vs Input ===")
match_named = 0
n = 0
for g in games():
    rs = recs(g)
    snaps = [r for r in rs if r.get("type") == "entities" and r.get("reason") == "combat_start"]
    bbs = [r for r in rs if r.get("type") == "hdt_bb" and r.get("hasInput")]
    for snap in snaps:
        turn = (snap.get("context") or {}).get("turn")
        ctx = snap.get("context") or {}
        op_id = (ctx.get("opponent") or {}).get("id")
        ents = snap.get("entities") or []
        op_ent = next((e for e in ents if not e.get("cardId") and tag(e, "HERO_ENTITY")
                       and tag(e, "CONTROLLER") == op_id), None)
        tf = next((e for e in ents if e.get("cardId") == "Bacon_TagTransferPlayerE"
                   and tag(e, "ZONE") == 1 and tag(e, "CONTROLLER") == op_id), None)
        first = next((r for r in bbs if r.get("key") == turn), None)
        inp = find_input((first or {}).get("invoker"))
        o = (inp or {}).get("Opponent") or {}
        in_val = o.get("ElementalPlayCounter")
        tf_val = tag(tf, "BACON_ELEMENTAL_PLAY_COUNTER") if tf else None
        if tf_val is None and tf:
            tf_val = tag(tf, "2878")
        n += 1
        if in_val == (tf_val or 0) or (in_val == 0 and tf_val is None):
            match_named += 1
        if in_val not in (0, None) or tf_val not in (0, None):
            print(f"  {os.path.basename(g)} t{turn}: Input={in_val} TF_named={tf_val} "
                  f"ent={tag(op_ent, 'BACON_ELEMENTAL_PLAY_COUNTER') if op_ent else None}")
print(f"  ElementalPlayCounter Input==(TF named or 0): {match_named}/{n}")

# Opponent secrets / unknown hand / hero HP
print("\n=== opponent secrets, unknown hand, hero/tier match ===")
sec_n = sec_known = 0
unk = known_hand = 0
hp_match = tier_match = 0
hp_n = 0
secret_types = Counter()
for g in games():
    rs = recs(g)
    snaps = [r for r in rs if r.get("type") == "entities" and r.get("reason") == "combat_start"]
    bbs = [r for r in rs if r.get("type") == "hdt_bb" and r.get("hasInput")]
    for snap in snaps:
        turn = (snap.get("context") or {}).get("turn")
        ctx = snap.get("context") or {}
        ents = {e["id"]: e for e in snap.get("entities") or []}
        first = next((r for r in bbs if r.get("key") == turn), None)
        inp = find_input((first or {}).get("invoker"))
        if not inp:
            continue
        o, p = inp.get("Opponent") or {}, inp.get("Player") or {}
        for it in (o.get("Secrets") or {}).get("items") or []:
            sec_n += 1
            secret_types[str(it)[:40]] += 1
            if it not in (None, "null"):
                sec_known += 1
        unk += unknown_hand(o.get("Hand"))
        known_hand += coll_n(o.get("Hand")) - unknown_hand(o.get("Hand"))
        # hero health from snapshot
        op_hero = ents.get((ctx.get("opponent") or {}).get("hero"))
        pl_hero = ents.get((ctx.get("player") or {}).get("hero"))

        def hero_hp(e):
            if not e:
                return None
            return (tag(e, "HEALTH") or 0) - (tag(e, "DAMAGE") or 0) + (tag(e, "ARMOR") or 0)

        hp_n += 1
        if hero_hp(pl_hero) == p.get("Health"):
            hp_match += 1
        if tag(pl_hero, "PLAYER_TECH_LEVEL") == p.get("Tier") or tag(
                next((e for e in snap.get("entities") or []
                      if not e.get("cardId") and tag(e, "CONTROLLER") == (ctx.get("player") or {}).get("id")
                      and tag(e, "HERO_ENTITY")), None),
                "PLAYER_TECH_LEVEL") == p.get("Tier"):
            tier_match += 1
print(f"  opponent Input secrets non-null: {sec_known}/{sec_n} types={dict(secret_types)}")
print(f"  opponent Input hand known/UnknownCard: {known_hand}/{unk}")
print(f"  Player Health snapshot==Input: {hp_match}/{hp_n}; Tier match ~ {tier_match}/{hp_n}")

# 2717 gap
print("\n=== 2717 FriendlyMinionsDeadLastCombat: player-entity vs TF vs Input ===")
rows = Counter()
for g in games():
    rs = recs(g)
    snaps = [r for r in rs if r.get("type") == "entities" and r.get("reason") == "combat_start"]
    bbs = [r for r in rs if r.get("type") == "hdt_bb" and r.get("hasInput")]
    for snap in snaps:
        turn = (snap.get("context") or {}).get("turn")
        ctx = snap.get("context") or {}
        op_id = (ctx.get("opponent") or {}).get("id")
        op_ent = next((e for e in snap.get("entities") or []
                       if not e.get("cardId") and tag(e, "HERO_ENTITY") and tag(e, "CONTROLLER") == op_id), None)
        tf = next((e for e in snap.get("entities") or []
                   if e.get("cardId") == "Bacon_TagTransferPlayerE" and tag(e, "ZONE") == 1
                   and tag(e, "CONTROLLER") == op_id), None)
        inp = find_input((next((r for r in bbs if r.get("key") == turn), None) or {}).get("invoker"))
        in_val = ((inp or {}).get("Opponent") or {}).get("FriendlyMinionsDeadLastCombatCounter")
        ent_val = tag(op_ent, "2717")
        tf_val = tag(tf, "2717")
        key = f"ent={ent_val} tf={tf_val} in={in_val}"
        rows[key] += 1
print("  combinations:", dict(rows))
