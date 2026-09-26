"""Q-007 rematch: only use hdt_bb dumps at/after this combat's 2022=0 line."""
import json
import os
from collections import Counter

ROOT = os.path.join(os.environ["APPDATA"], "HearthstoneDeckTracker", "BgHelperDiag")

COUNTERS = [
    ("ElementalPlayCounter", ["BACON_ELEMENTAL_PLAY_COUNTER", "2878"]),
    ("ElementalsGiveExtraAttack", ["BACON_ELEMENTAL_BUFFATKVALUE", "4002"]),
    ("ElementalsGiveExtraHealth", ["BACON_ELEMENTAL_BUFFHEALTHVALUE"]),
    ("PiratesSummonCounter", ["2358"]),
    ("MagnetizeCounter", ["3670"]),
    ("BeastsSummonCounter", ["3962"]),
    ("TastyLobsterCounter", ["4803"]),
    ("GoldenMinionsPlayedCounter", ["4799"]),
    ("FriendlyMinionsDeadLastCombatCounter", ["2717"]),
    ("BattlecryCounter", ["3236"]),
    ("TavernSpellCounter", ["3088"]),
    ("DeathrattleCounter", ["4639"]),
    ("VolumizerAtkBuff", ["4468"]),
    ("VolumizerHealthBuff", ["4469"]),
    ("TavernSpellAtkBuff", ["TAVERN_SPELL_ATTACK_INCREASE"]),
    ("TavernSpellHealthBuff", ["TAVERN_SPELL_HEALTH_INCREASE"]),
    ("ResourcesSpentThisGame", ["NUM_RESOURCES_SPENT_THIS_GAME"]),
]


def tag(e, names):
    if not e:
        return None
    tags = e.get("tags") or {}
    for n in names:
        if n in tags:
            return tags[n]
    return None


def find_input(inv):
    inner = (inv or {}).get("_input")
    if isinstance(inner, dict) and inner.get("$type") == "BobsBuddy.Simulation.Input":
        return inner
    return None


match_tf = Counter()
match_ent = Counter()
nz_o = Counter()
nz_p = Counter()
n = Counter()
hp_ok = 0
tier_ok = 0
hp_n = 0
leftover_skipped = 0

for d in sorted(os.listdir(ROOT)):
    g = os.path.join(ROOT, d)
    if not os.path.isdir(g):
        continue
    recs = [json.loads(r) for r in open(os.path.join(g, "records.jsonl"), encoding="utf-8")]
    tags = [r for r in recs if r.get("type") == "combat_tag"]
    snaps = [r for r in recs if r.get("type") == "entities" and r.get("reason") == "combat_start"]
    bbs = [r for r in recs if r.get("type") == "hdt_bb" and r.get("hasInput")]
    for snap in snaps:
        turn = (snap.get("context") or {}).get("turn")
        ctx = snap.get("context") or {}
        t2022 = next((r for r in tags if r.get("tag") == 2022 and r.get("value") == 0
                      and r.get("lineSeq") >= snap["lineSeq"]), None)
        start_ls = t2022["lineSeq"] if t2022 else snap["lineSeq"]
        first = next((r for r in bbs if r.get("key") == turn and r.get("lineSeq") >= start_ls), None)
        # leftover would have lineSeq << snap
        early = [r for r in bbs if r.get("key") == turn and r.get("lineSeq") < snap["lineSeq"]]
        leftover_skipped += len(early)
        inp = find_input((first or {}).get("invoker"))
        if not inp:
            print(f"  {d} t{turn}: no Input after 2022=0")
            continue
        p, o = inp.get("Player") or {}, inp.get("Opponent") or {}
        ents = snap.get("entities") or []
        op_id = (ctx.get("opponent") or {}).get("id")
        pl_id = (ctx.get("player") or {}).get("id")
        op_ent = next((e for e in ents if not e.get("cardId") and (e.get("tags") or {}).get("HERO_ENTITY")
                       and (e.get("tags") or {}).get("CONTROLLER") == op_id), None)
        pl_ent = next((e for e in ents if not e.get("cardId") and (e.get("tags") or {}).get("HERO_ENTITY")
                       and (e.get("tags") or {}).get("CONTROLLER") == pl_id), None)
        tf = next((e for e in ents if e.get("cardId") == "Bacon_TagTransferPlayerE"
                   and (e.get("tags") or {}).get("ZONE") == 1
                   and (e.get("tags") or {}).get("CONTROLLER") == op_id), None)
        for field, names in COUNTERS:
            n[field] += 1
            in_o = o.get(field)
            in_p = p.get(field)
            if in_o not in (0, False, None):
                nz_o[field] += 1
            if in_p not in (0, False, None):
                nz_p[field] += 1
            tf_v = tag(tf, names)
            ent_v = tag(op_ent, names)
            # HDT GetTag missing = 0
            if in_o == (tf_v if tf_v is not None else 0):
                match_tf[field] += 1
            if in_o == (ent_v if ent_v is not None else 0):
                match_ent[field] += 1

        # health
        ents_by = {e["id"]: e for e in ents}
        hero = ents_by.get((ctx.get("player") or {}).get("hero"))
        if hero:
            hp_n += 1
            hp = ((hero.get("tags") or {}).get("HEALTH") or 0) - ((hero.get("tags") or {}).get("DAMAGE") or 0) + (
                (hero.get("tags") or {}).get("ARMOR") or 0)
            if hp == p.get("Health"):
                hp_ok += 1
            if (pl_ent.get("tags") or {}).get("PLAYER_TECH_LEVEL") == p.get("Tier"):
                tier_ok += 1

print("leftover dumps skipped (same turn key, earlier lineSeq):", leftover_skipped)
print("Player Health/Tier match after filter:", hp_ok, "/", hp_n, "tier", tier_ok, "/", hp_n)
print("\nfield | n | matchTF(or0) | matchOppEnt(or0) | nzOpp | nzPlayer")
for field, _ in COUNTERS:
    print(f"  {field}: {n[field]} | {match_tf[field]} | {match_ent[field]} | {nz_o[field]} | {nz_p[field]}")

# 2717 detail
print("\n2717 detail (ent / tf / Input.Opponent):")
combo = Counter()
for d in sorted(os.listdir(ROOT)):
    g = os.path.join(ROOT, d)
    if not os.path.isdir(g):
        continue
    recs = [json.loads(r) for r in open(os.path.join(g, "records.jsonl"), encoding="utf-8")]
    tags = [r for r in recs if r.get("type") == "combat_tag"]
    snaps = [r for r in recs if r.get("type") == "entities" and r.get("reason") == "combat_start"]
    bbs = [r for r in recs if r.get("type") == "hdt_bb" and r.get("hasInput")]
    for snap in snaps:
        turn = (snap.get("context") or {}).get("turn")
        ctx = snap.get("context") or {}
        t2022 = next((r for r in tags if r.get("tag") == 2022 and r.get("value") == 0
                      and r.get("lineSeq") >= snap["lineSeq"]), None)
        start_ls = t2022["lineSeq"] if t2022 else snap["lineSeq"]
        first = next((r for r in bbs if r.get("key") == turn and r.get("lineSeq") >= start_ls), None)
        inp = find_input((first or {}).get("invoker"))
        o = ((inp or {}).get("Opponent") or {})
        op_id = (ctx.get("opponent") or {}).get("id")
        op_ent = next((e for e in snap.get("entities") or []
                       if not e.get("cardId") and (e.get("tags") or {}).get("HERO_ENTITY")
                       and (e.get("tags") or {}).get("CONTROLLER") == op_id), None)
        tf = next((e for e in snap.get("entities") or []
                   if e.get("cardId") == "Bacon_TagTransferPlayerE"
                   and (e.get("tags") or {}).get("ZONE") == 1
                   and (e.get("tags") or {}).get("CONTROLLER") == op_id), None)
        combo[f"ent={tag(op_ent, ['2717'])} tf={tag(tf, ['2717'])} in={o.get('FriendlyMinionsDeadLastCombatCounter')}"] += 1
print(dict(combo))
