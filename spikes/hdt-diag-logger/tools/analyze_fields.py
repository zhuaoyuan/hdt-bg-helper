"""Field-level analysis of diagnostic captures (P1-T3, Q-006, Q-007).

Output is counts, tag ids and anonymised values only — safe to paste into the repo.
"""
import gzip
import json
import os
import re
from collections import Counter, defaultdict

ROOT = os.path.join(os.environ["APPDATA"], "HearthstoneDeckTracker", "BgHelperDiag")

# HDT ReadPlayerCounter tags (facts/bobsbuddy-simulator-input.md 3.7)
COUNTER_FIELDS = [
    ("ElementalPlayCounter", "2878"),
    ("ElementalsGiveExtraAttack", "BACON_ELEMENTAL_BUFFATKVALUE"),
    ("ElementalsGiveExtraHealth", "BACON_ELEMENTAL_BUFFHEALTHVALUE"),
    ("PiratesSummonCounter", "2358"),
    ("MagnetizeCounter", "3670"),
    ("BeastsSummonCounter", "3962"),
    ("TastyLobsterCounter", "4803"),
    ("GoldenMinionsPlayedCounter", "4799"),
    ("FriendlyMinionsDeadLastCombatCounter", "2717"),
    ("BattlecryCounter", "3236"),
    ("TavernSpellCounter", "3088"),
    ("DeathrattleCounter", "4639"),
    ("VolumizerAtkBuff", "4468"),
    ("VolumizerHealthBuff", "4469"),
]
TAVERN_ATK = "TAVERN_SPELL_ATTACK_INCREASE"
TAVERN_HP = "TAVERN_SPELL_HEALTH_INCREASE"
RESOURCES = "NUM_RESOURCES_SPENT_THIS_GAME"

PLAYER_ENCHANTS = {
    "BG25_008pe": "EternalKnight/Legion",
    "BG36_MagicItem_216pe": "GreaterEternalPortrait",
    "BG36_MagicItem_216e": "GreaterEternalLegion(minion)",
    "BGDUO31_208pe": "SanlaynScribe",
    "BG25_011pe": "UndeadBonus",
    "BG34_Giant_362pe": "TimewarpedGoldrinn",
    "BGS_018pe": "Goldrinn",
    "BG_TTN_401pe": "AncestralAutomaton",
    "BG31_808pe": "Beetles",
    "BG34_402pe": "Whelp",
    "BG26_159pe": "BloodGem",
    "BG33_112pe": "Haunted",
}

COMBAT_UPDATE_HINTS = re.compile(
    r"BLOCK_END|tag=ZONE |tag=COPIED_FROM_ENTITY_ID|tag=ATK |"
    r"tag=PROPOSED_ATTACKER|TRIGGER_VISUAL|keyword=SECRET|"
    r"BG22_HERO_000p|BG35_952|BG26_354|BG34_142|BG34_143|"
    r"BG35_MagicItem_754|BG32_HERO_001|BG27_004|BG_TTN_401|"
    r"BGDUO_125|BGDUO_HERO_101|BGDUO_MagicItem_003|BGDUO_105|"
    r"BG34_Giant_619|BG34_Giant_074",
    re.I,
)


def games():
    return [os.path.join(ROOT, d) for d in sorted(os.listdir(ROOT))
            if os.path.isdir(os.path.join(ROOT, d))]


def read_records(game_dir):
    path = os.path.join(game_dir, "records.jsonl")
    out = []
    with open(path, encoding="utf-8") as f:
        for row in f:
            out.append(json.loads(row))
    return out


def read_raw_at(game_dir, seqs):
    """Return {seq: line} for requested lineSeqs (and a small window)."""
    want = set()
    for s in seqs:
        if s:
            want.update(range(max(1, s - 2), s + 3))
    p = os.path.join(game_dir, "power.log.gz")
    if not os.path.exists(p):
        p = os.path.join(game_dir, "power.log")
    found = {}
    opener = gzip.open if p.endswith(".gz") else open
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


def find_input(invoker):
    if not isinstance(invoker, dict):
        return None
    inner = invoker.get("_input")
    if isinstance(inner, dict) and inner.get("$type") == "BobsBuddy.Simulation.Input":
        return inner
    return None


def tag(e, name, default=None):
    return (e.get("tags") or {}).get(name, default)


def zone_play(e):
    return tag(e, "ZONE") == 1


def is_player_entity(e):
    return not e.get("cardId") and tag(e, "HERO_ENTITY") and tag(e, "PLAYER_ID")


def attached_to(ents, host_id):
    return [e for e in ents if tag(e, "ATTACHED") == host_id]


def coll_n(obj):
    if not isinstance(obj, dict):
        return 0
    items = obj.get("items")
    return len(items) if items is not None else 0


def coll_types(obj):
    if not isinstance(obj, dict):
        return []
    out = []
    for it in obj.get("items") or []:
        if isinstance(it, dict):
            t = (it.get("$type") or "").rsplit(".", 1)[-1]
            cid = it.get("cardId") or it.get("CardId") or ""
            out.append(f"{t}:{cid}" if cid else t)
        else:
            out.append(str(it))
    return out


def scalars(player):
    if not isinstance(player, dict):
        return {}
    return {k: player.get(k) for k in player
            if k[0:1].isupper() and not isinstance(player.get(k), (dict, list))}


def analyze_game(game_dir):
    name = os.path.basename(game_dir)
    recs = read_records(game_dir)
    print(f"\n========== {name} ==========")

    combat_tags = [r for r in recs if r.get("type") == "combat_tag"]
    phases = [r for r in recs if r.get("type") == "combat_phase"]
    ents_recs = [r for r in recs if r.get("type") == "entities"]
    bb_recs = [r for r in recs if r.get("type") == "hdt_bb"]
    events = [r for r in recs if r.get("type") == "event"]

    # --- Q-006: same-line timing of combat start ---
    starts = [r for r in phases if r.get("value") is True]
    print("\n-- Q-006 combat-start lineSeq alignment --")
    print("combat | tag2022=0 | phase=true | entities | first Input | sameLine | outstanding")
    q006_same = 0
    q006_total = 0
    outstanding_total = 0
    outstanding_ents = 0
    tag2022_entity = Counter()
    for i, ph in enumerate(starts, 1):
        ls = ph.get("lineSeq")
        tags_at = [r for r in combat_tags if r.get("lineSeq") == ls and r.get("tag") == 2022 and r.get("value") == 0]
        # also allow nearby (queued delay)
        tags_near = [r for r in combat_tags if r.get("tag") == 2022 and r.get("value") == 0
                     and abs((r.get("lineSeq") or 0) - ls) <= 5]
        snap = next((r for r in ents_recs if r.get("reason") == "combat_start" and r.get("lineSeq") == ls), None)
        turn = (snap.get("context") or {}).get("turn") if snap else None
        first_in = next((r for r in bb_recs if r.get("key") == turn and r.get("hasInput")
                         and r.get("lineSeq") >= ls), None)
        tag_ls = tags_at[0]["lineSeq"] if tags_at else (tags_near[0]["lineSeq"] if tags_near else None)
        in_ls = first_in.get("lineSeq") if first_in else None
        same = tag_ls == ls and (snap is not None) and in_ls == ls
        q006_total += 1
        q006_same += int(same)
        outst = 0
        if snap:
            for e in snap.get("entities") or []:
                if (e.get("info") or {}).get("HasOutstandingTagChanges"):
                    outst += 1
                    outstanding_ents += 1
            outstanding_total += outst
        print(f"  {i} turn={turn} | {tag_ls} | {ls} | "
              f"{snap.get('lineSeq') if snap else None} | {in_ls} | {same} | {outst}")
        for t in tags_at or tags_near[:1]:
            ent = str(t.get("entity") or "")
            # keep only entity id if present
            m = re.search(r"id=(\d+)", ent)
            tag2022_entity[m.group(1) if m else "name-or-other"] += 1

    print(f"  same-line start (tag2022 + phase + snapshot + Input): {q006_same}/{q006_total}")
    print(f"  HasOutstandingTagChanges at combat_start: {outstanding_ents} entities across {q006_total} combats")
    print(f"  tag 2022 entity: {dict(tag2022_entity)}")

    # tag 3533
    t3533 = Counter((r.get("value"), bool(re.search(r"id=", str(r.get("entity"))))) for r in combat_tags if r.get("tag") == 3533)
    t2022 = Counter(r.get("value") for r in combat_tags if r.get("tag") == 2022)
    print(f"  combat_tag 2022 values: {dict(t2022)}; 3533 (value, hasId): {dict(t3533)}")

    # --- reruns vs power line ---
    print("\n-- Q-006 in-combat Input/reRun dumps --")
    rerun_lines = []
    for r in bb_recs:
        if r.get("reRunCount", 0) > 0 or (r.get("reason") == "line" and r.get("inputChanged")):
            rerun_lines.append(r.get("lineSeq"))
    raw = read_raw_at(game_dir, rerun_lines)
    rerun_hits = 0
    for r in bb_recs:
        if r.get("reRunCount", 0) <= 0 and not (r.get("reason") == "line" and r.get("inputChanged")):
            continue
        ls = r.get("lineSeq")
        line = raw.get(ls, "")
        hint = bool(COMBAT_UPDATE_HINTS.search(line))
        rerun_hits += int(hint)
        snippet = re.sub(r"player_[0-9a-f]{8}", "<P>", line)[:140]
        print(f"  turn={r.get('key')} reRun={r.get('reRunCount')} reason={r.get('reason')} "
              f"lineSeq={ls} hint={hint} | {snippet}")
    print(f"  rerun/input-change dumps whose own line looks like a 5.2 trigger: "
          f"{rerun_hits}/{len(rerun_lines)}")

    # public events vs BB
    sec_ev = [r for r in events if r.get("name") == "opponent_secret_triggered"]
    print(f"  opponent_secret_triggered events: {len(sec_ev)}")

    # --- per-combat field / Q-007 ---
    print("\n-- per-combat snapshot vs HDT Input --")
    header = ("turn", "tfPlay", "oppHand", "oppSec", "plSec", "oppTrink", "plTrink",
              "oppQuest", "obj", "hpActP", "hpActO", "resP", "resO", "deadP", "deadO",
              "deadTf", "deadInpO")
    print("  " + " | ".join(header))

    tf_tag_presence = Counter()  # tag -> combats where active TF has it
    tf_tag_nonzero = Counter()
    field_nonzero = {side: Counter() for side in ("Player", "Opponent")}
    field_match_tf = Counter()  # Input opponent field == active TF tag
    field_match_player = Counter()
    field_n = Counter()
    enchant_side = Counter()  # (cardId, attached_to_local) 
    secret_known_opp = 0
    secret_unknown_opp = 0
    hand_known_opp = 0
    hand_unknown_opp = 0
    races = Counter()
    anomalies = Counter()
    damage_caps = Counter()
    unassigned_nonzero = Counter()  # DeepBlues etc on Input
    hp_cards = Counter()
    trinket_cards = Counter()
    quest_cards = Counter()
    deity = 0
    tavish = 0
    malorne = 0
    kelthuzad = 0
    outputs = []

    UNASSIGNED = ("DeepBluesCounter", "AnySpellCounter", "BackToBackCounter",
                  "BackToBackAtk", "BackToBackHealth")

    start_snaps = [r for r in ents_recs if r.get("reason") == "combat_start"]
    for snap in start_snaps:
        ctx = snap.get("context") or {}
        turn = ctx.get("turn")
        ents = snap.get("entities") or []
        by_id = {e["id"]: e for e in ents}
        pl_ctx, op_ctx = ctx.get("player") or {}, ctx.get("opponent") or {}
        pl_id, op_id = pl_ctx.get("id"), op_ctx.get("id")
        # player entities: match CONTROLLER == player id and HERO_ENTITY
        pl_ent = next((e for e in ents if is_player_entity(e) and tag(e, "CONTROLLER") == pl_id), None)
        op_ent = next((e for e in ents if is_player_entity(e) and tag(e, "CONTROLLER") == op_id), None)

        tfs = [e for e in ents if e.get("cardId") == "Bacon_TagTransferPlayerE"]
        tf_play = [e for e in tfs if zone_play(e) and tag(e, "ATTACHED") == (op_ent["id"] if op_ent else None)]
        # also accept TF attached to opponent player and in PLAY even if attach id mismatch
        if not tf_play:
            tf_play = [e for e in tfs if zone_play(e) and tag(e, "CONTROLLER") == op_id]
        tf = tf_play[0] if tf_play else None

        first_in = next((r for r in bb_recs if r.get("key") == turn and r.get("hasInput")
                         and r.get("state") in ("Combat", "Shopping", "GameOver")), None)
        inp = find_input((first_in or {}).get("invoker") or {}) or {}
        p_in, o_in = inp.get("Player") or {}, inp.get("Opponent") or {}
        p_sc, o_sc = scalars(p_in), scalars(o_in)

        for side, sc in (("Player", p_sc), ("Opponent", o_sc)):
            for k, v in sc.items():
                if v not in (0, False, None, 0.0):
                    field_nonzero[side][k] += 1
            for k in UNASSIGNED:
                if sc.get(k) not in (0, False, None):
                    unassigned_nonzero[f"{side}.{k}"] += 1

        if tf:
            ttags = tf.get("tags") or {}
            for k, v in ttags.items():
                tf_tag_presence[k] += 1
                if v not in (0, None):
                    tf_tag_nonzero[k] += 1
            for field, tname in COUNTER_FIELDS + [("TavernSpellAtkBuff", TAVERN_ATK),
                                                   ("TavernSpellHealthBuff", TAVERN_HP)]:
                field_n[field] += 1
                tf_val = ttags.get(tname)
                op_val = (op_ent.get("tags") or {}).get(tname) if op_ent else None
                in_val = o_sc.get(field)
                if in_val is not None and tf_val == in_val:
                    field_match_tf[field] += 1
                if in_val is not None and op_val == in_val:
                    field_match_player[field] += 1

        # hero power activation
        def hp_activated(hero_id):
            if not hero_id:
                return None
            # hero powers: CARDTYPE=10 typically, CONTROLLER match, ZONE play, on board list
            return None

        pl_board = set(pl_ctx.get("board") or [])
        op_board = set(op_ctx.get("board") or [])
        pl_hps = [by_id[i] for i in pl_board if i in by_id and (by_id[i].get("cardId") or "").endswith("p")
                  or (i in by_id and tag(by_id[i], "CARDTYPE") == 10)]
        # CARDTYPE HERO_POWER = 10
        def hps_of(board_ids, controller):
            out = []
            for i in board_ids:
                e = by_id.get(i)
                if not e:
                    continue
                if tag(e, "CARDTYPE") == 10:
                    out.append(e)
            return out
        pl_hps = hps_of(pl_board, pl_id)
        op_hps = hps_of(op_board, op_id)
        def hp_act(hs):
            if not hs:
                return "-"
            flags = []
            for e in hs:
                ex = tag(e, "EXHAUSTED")
                act = tag(e, "BACON_HERO_POWER_ACTIVATED")
                flags.append(f"ex={ex}/act={act}")
            return ",".join(flags)

        # player enchants attached to player entities
        for host, local in ((pl_ent, True), (op_ent, False)):
            if not host:
                continue
            for e in attached_to(ents, host["id"]):
                cid = e.get("cardId") or ""
                if cid in PLAYER_ENCHANTS:
                    enchant_side[(PLAYER_ENCHANTS[cid], "local" if local else "opp",
                                  "play" if zone_play(e) else f"z{tag(e,'ZONE')}")] += 1

        # secrets vs objectives in secret zone
        def zone_cards(ids):
            cards = []
            for i in ids or []:
                e = by_id.get(i)
                if e:
                    cards.append((e.get("cardId") or "?unknown", tag(e, "CARDTYPE"),
                                  (e.get("info") or {}).get("Hidden")))
            return cards
        op_sec = zone_cards(op_ctx.get("secretZone"))
        pl_sec = zone_cards(pl_ctx.get("secretZone"))
        op_hand = zone_cards(op_ctx.get("hand"))
        pl_hand = zone_cards(pl_ctx.get("hand"))
        for cid, ct, hid in op_sec:
            # skip objectives (Deity sigil etc. often CARDTYPE spell/enchant in secret zone)
            if cid in ("BG_OldGod",) or "OldGod" in (cid or "") or cid.startswith("BG33_"):
                continue
            if cid.startswith("?") or not cid or cid == "?unknown":
                secret_unknown_opp += 1
            else:
                secret_known_opp += 1
        for cid, ct, hid in op_hand:
            if cid.startswith("?") or cid == "?unknown" or not cid:
                hand_unknown_opp += 1
            else:
                hand_known_opp += 1

        for cid, _, _ in zone_cards(pl_ctx.get("trinkets")) + zone_cards(op_ctx.get("trinkets")):
            if cid and not cid.startswith("?"):
                trinket_cards[cid] += 1
        for cid, _, _ in zone_cards(pl_ctx.get("quests")) + zone_cards(op_ctx.get("quests")):
            if cid:
                quest_cards[cid] += 1
        for e in ents:
            cid = e.get("cardId") or ""
            if cid == "BG_OldGod" or cid.startswith("BG33_Anomaly") or "OldGod" in cid:
                deity += 1
            if "Tavish" in cid or cid.startswith("BG22_HERO_000"):
                tavish += 1
            if "Malorne" in cid or cid in ("BG32_HERO_001_Buddy", "BG32_HERO_001_Buddy_G"):
                malorne += 1
            if cid == "TB_BaconShop_HERO_KelThuzad":
                kelthuzad += 1
        for e in pl_hps + op_hps:
            hp_cards[e.get("cardId") or "?"] += 1

        for rname in ctx.get("availableRaces") or []:
            races[rname] += 1
        anomalies[str(ctx.get("anomalyDbfId"))] += 1
        damage_caps[inp.get("DamageCap")] += 1

        if first_in and first_in.get("hasOutput"):
            out = (first_in.get("invoker") or {}).get("Output") or {}
            outputs.append({
                "turn": turn,
                "win": out.get("winRate"),
                "tie": out.get("tieRate"),
                "loss": out.get("lossRate"),
                "n": out.get("simulationCount"),
                "exit": out.get("myExitCondition"),
            })

        print("  " + " | ".join(str(x) for x in [
            turn,
            len(tf_play),
            f"{coll_n(o_in.get('Hand'))}/{len(op_ctx.get('hand') or [])}",
            f"{coll_n(o_in.get('Secrets'))}/{len(op_ctx.get('secretZone') or [])}",
            f"{coll_n(p_in.get('Secrets'))}/{len(pl_ctx.get('secretZone') or [])}",
            f"{coll_n(o_in.get('Trinkets'))}/{len(op_ctx.get('trinkets') or [])}",
            f"{coll_n(p_in.get('Trinkets'))}/{len(pl_ctx.get('trinkets') or [])}",
            f"{coll_n(o_in.get('Quests'))}/{len(op_ctx.get('quests') or [])}",
            f"{coll_n(o_in.get('Objectives'))}+{coll_n(p_in.get('Objectives'))}",
            hp_act(pl_hps),
            hp_act(op_hps),
            p_sc.get("ResourcesSpentThisGame"),
            o_sc.get("ResourcesSpentThisGame"),
            tag(pl_ent, "2717") if pl_ent else None,
            tag(op_ent, "2717") if op_ent else None,
            tag(tf, "2717") if tf else None,
            o_sc.get("FriendlyMinionsDeadLastCombatCounter"),
        ]))

    print("\n-- Q-007 TagTransfer tags on active (PLAY, attached to opponent) --")
    print("  tag | present | nonzero")
    interesting = set(t for _, t in COUNTER_FIELDS) | {TAVERN_ATK, TAVERN_HP, RESOURCES,
                                                       "PLAYER_TECH_LEVEL", "ATTACHED", "ZONE",
                                                       "CONTROLLER", "2717", "2878", "4002"}
    for k, n in tf_tag_presence.most_common():
        mark = " <=" if k in interesting or k.isdigit() else ""
        print(f"  {k}: {n} / {q006_total} present, {tf_tag_nonzero[k]} nonzero{mark}")

    print("\n-- opponent Input field vs TagTransfer / player-entity --")
    print("  field | n | matchTF | matchPlayerEnt | Input.Opponent nonzero | Input.Player nonzero")
    for field, tname in COUNTER_FIELDS + [("TavernSpellAtkBuff", TAVERN_ATK),
                                           ("TavernSpellHealthBuff", TAVERN_HP),
                                           ("ResourcesSpentThisGame", RESOURCES)]:
        print(f"  {field}: {field_n[field]} | {field_match_tf[field]} | {field_match_player[field]} | "
              f"{field_nonzero['Opponent'][field]} | {field_nonzero['Player'][field]}")

    print("\n-- player-enchant attachments (card → local/opp) --")
    if enchant_side:
        for k, n in sorted(enchant_side.items()):
            print(f"  {k}: {n}")
    else:
        print("  (none of the 3.6 enchant cardIds seen)")

    print("\n-- coverage --")
    print(f"  availableRaces: {dict(races)}")
    print(f"  anomalyDbfId: {dict(anomalies)}")
    print(f"  DamageCap: {dict(damage_caps)}")
    print(f"  opponent hand known/unknown cards (snapshot): {hand_known_opp}/{hand_unknown_opp}")
    print(f"  opponent secret-zone known/unknown (raw zone, includes objectives): {secret_known_opp}/{secret_unknown_opp}")
    print(f"  trinket cardIds: {dict(trinket_cards)}")
    print(f"  quest cardIds: {dict(quest_cards)}")
    print(f"  deity-related entities seen: {deity}; Tavish-related: {tavish}; Malorne: {malorne}; KT: {kelthuzad}")
    print(f"  hero power cardIds: {dict(hp_cards)}")
    print(f"  HDT-unassigned fields nonzero on Input: {dict(unassigned_nonzero) or 'none'}")
    print(f"  Input.Player nonzero fields: {dict(field_nonzero['Player'])}")
    print(f"  Input.Opponent nonzero fields: {dict(field_nonzero['Opponent'])}")

    # Output summary (rates only)
    with_out = [r for r in bb_recs if r.get("hasOutput") and r.get("key")]
    print(f"  hdt_bb with Output: {len(with_out)}")
    # simulation counts from later dumps
    sim_n = Counter()
    exits = Counter()
    for r in bb_recs:
        if not r.get("hasOutput"):
            continue
        out = (r.get("invoker") or {}).get("Output")
        if not isinstance(out, dict):
            continue
        sim_n[out.get("simulationCount")] += 1
        exits[out.get("myExitCondition")] += 1
    print(f"  simulationCount: {dict(sim_n)}; exit: {dict(exits)}")

    return {
        "q006_same": q006_same,
        "q006_total": q006_total,
        "outstanding": outstanding_ents,
        "tf_tags": tf_tag_presence,
        "tf_nonzero": tf_tag_nonzero,
        "field_match_tf": field_match_tf,
        "field_match_player": field_match_player,
        "field_n": field_n,
        "field_nz_p": field_nonzero["Player"],
        "field_nz_o": field_nonzero["Opponent"],
        "unassigned": unassigned_nonzero,
        "enchants": enchant_side,
        "races": races,
        "trinkets": trinket_cards,
        "quests": quest_cards,
        "malorne": malorne,
        "tavish": tavish,
        "hand_known": hand_known_opp,
        "hand_unknown": hand_unknown_opp,
    }


def main():
    totals = []
    for g in games():
        totals.append(analyze_game(g))
    print("\n========== ALL GAMES ==========")
    same = sum(t["q006_same"] for t in totals)
    n = sum(t["q006_total"] for t in totals)
    print(f"Q-006 same-line combat start: {same}/{n}")
    print(f"HasOutstandingTagChanges entities: {sum(t['outstanding'] for t in totals)}")
    print(f"Malorne entities: {sum(t['malorne'] for t in totals)}; Tavish-related: {sum(t['tavish'] for t in totals)}")
    print(f"opponent hand known/unknown: {sum(t['hand_known'] for t in totals)}/{sum(t['hand_unknown'] for t in totals)}")
    tf = Counter(); tfnz = Counter()
    for t in totals:
        tf.update(t["tf_tags"]); tfnz.update(t["tf_nonzero"])
    print("TagTransfer tag presence (all games, active TF):")
    for k, v in tf.most_common():
        print(f"  {k}: present {v}/{n}, nonzero {tfnz[k]}")
    mtf, mpl, fn = Counter(), Counter(), Counter()
    nzp, nzo = Counter(), Counter()
    for t in totals:
        mtf.update(t["field_match_tf"]); mpl.update(t["field_match_player"]); fn.update(t["field_n"])
        nzp.update(t["field_nz_p"]); nzo.update(t["field_nz_o"])
    print("opponent field match (all games):")
    for field, tname in COUNTER_FIELDS + [("TavernSpellAtkBuff", TAVERN_ATK),
                                           ("TavernSpellHealthBuff", TAVERN_HP),
                                           ("ResourcesSpentThisGame", RESOURCES)]:
        print(f"  {field}: n={fn[field]} matchTF={mtf[field]} matchEnt={mpl[field]} "
              f"nzOpp={nzo[field]} nzPlayer={nzp[field]}")
    ench = Counter()
    for t in totals:
        ench.update(t["enchants"])
    print("player enchants:", dict(ench) or "none")
    tr = Counter(); qu = Counter(); ra = Counter()
    for t in totals:
        tr.update(t["trinkets"]); qu.update(t["quests"]); ra.update(t["races"])
    print("trinkets:", dict(tr), "quests:", dict(qu), "races:", dict(ra))


if __name__ == "__main__":
    main()
