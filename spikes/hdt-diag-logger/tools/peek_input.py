"""Peek Input collection shapes and TagTransfer tags (anonymous only)."""
import json
import os
import sys

root = os.path.join(os.environ["APPDATA"], "HearthstoneDeckTracker", "BgHelperDiag")
game = sys.argv[1] if len(sys.argv) > 1 else "20260926_082753_e07627"
path = os.path.join(root, game, "records.jsonl")

COUNTER_TAGS = {
    "2878", "4002", "2358", "3670", "3962", "4803", "4799", "2717", "3236",
    "3088", "4639", "4468", "4469", "3989",
    "BACON_ELEMENTAL_PLAY_COUNTER", "BACON_ELEMENTAL_BUFFATKVALUE",
    "BACON_ELEMENTAL_BUFFHEALTHVALUE", "TAVERN_SPELL_ATTACK_INCREASE",
    "TAVERN_SPELL_HEALTH_INCREASE", "NUM_RESOURCES_SPENT_THIS_GAME",
    "BACON_BLOODGEMBUFFATKVALUE", "BACON_BLOODGEMBUFFHEALTHVALUE",
    "PLAYER_TECH_LEVEL", "HEALTH", "DAMAGE", "ARMOR",
    "BACON_HERO_POWER_ACTIVATED", "EXHAUSTED",
    "QUEST_PROGRESS", "QUEST_PROGRESS_TOTAL", "QUEST_REWARD_DATABASE_ID",
    "BACON_COMBAT_DAMAGE_CAP", "BACON_COMBAT_DAMAGE_CAP_ENABLED",
    "BACON_GLOBAL_ANOMALY_DBID", "2022", "3533",
}


def find_input(invoker):
    if not isinstance(invoker, dict):
        return None
    if invoker.get("$type") == "BobsBuddy.Simulation.Input":
        return invoker
    inner = invoker.get("_input")
    if isinstance(inner, dict) and inner.get("$type") == "BobsBuddy.Simulation.Input":
        return inner
    return None


def coll_summary(obj, depth=0):
    if obj is None:
        return "null"
    if not isinstance(obj, dict):
        return type(obj).__name__ + ":" + str(obj)[:40]
    if "$ref" in obj and "$type" not in obj:
        return f"$ref={obj['$ref']}"
    items = obj.get("items")
    if items is not None:
        n = len(items)
        sample = []
        for it in items[:3]:
            if isinstance(it, dict):
                sample.append(it.get("$type", "") + " cid=" + str(it.get("cardId") or it.get("CardId") or it.get("Id") or ""))
            else:
                sample.append(str(it)[:40])
        return f"list n={n} sample={sample}"
    keys = [k for k in obj.keys() if not k.startswith("$")]
    return f"obj type={obj.get('$type')} fields={keys[:12]}"


seen_turns = set()
transfers = []
with open(path, encoding="utf-8") as f:
    for line in f:
        r = json.loads(line)
        t = r.get("type")
        if t == "entities" and r.get("reason") == "combat_start":
            turn = (r.get("context") or {}).get("turn")
            ents = r.get("entities") or []
            tfs = [e for e in ents if e.get("cardId") == "Bacon_TagTransferPlayerE"]
            print(f"\n--- turn {turn} combat_start: TagTransfer n={len(tfs)} ---")
            for e in tfs:
                tags = e.get("tags") or {}
                interesting = {k: v for k, v in tags.items() if k in COUNTER_TAGS or k.isdigit()}
                print(f"  id={e['id']} attached={tags.get('ATTACHED')} zone={tags.get('ZONE')} "
                      f"controller={tags.get('CONTROLLER')} all_tags={len(tags)}")
                print(f"  named/counter tags: {interesting}")
                print(f"  ALL tag keys: {sorted(tags.keys())}")
            # player entities: no cardId, has PLAYER_ID, not a hero
            players = [e for e in ents if not e.get("cardId") and (e.get("tags") or {}).get("PLAYER_ID")
                       and (e.get("tags") or {}).get("HERO_ENTITY")]
            print(f"  player entities n={len(players)}")
            for e in players:
                tags = e.get("tags") or {}
                interesting = {k: tags[k] for k in tags if k in COUNTER_TAGS or k.isdigit()}
                print(f"    id={e['id']} name={e.get('name')} pid={tags.get('PLAYER_ID')} "
                      f"controller={tags.get('CONTROLLER')} counters={interesting}")
            ctx = r.get("context") or {}
            pl, op = ctx.get("player") or {}, ctx.get("opponent") or {}
            print(f"  ctx player id={pl.get('id')} hero={pl.get('hero')} board={pl.get('board')} "
                  f"hand={pl.get('hand')} secrets={pl.get('secretZone')} trinkets={pl.get('trinkets')} "
                  f"quests={pl.get('quests')} questRewards={pl.get('questRewards')} "
                  f"objectives={pl.get('objectives')} setAside={pl.get('setAside')}")
            print(f"  ctx opponent id={op.get('id')} hero={op.get('hero')} board={op.get('board')} "
                  f"hand={op.get('hand')} secrets={op.get('secretZone')} trinkets={op.get('trinkets')} "
                  f"quests={op.get('quests')} questRewards={op.get('questRewards')} "
                  f"objectives={op.get('objectives')} setAside={op.get('setAside')}")

        if t == "hdt_bb" and r.get("hasInput") and r.get("key") not in seen_turns and r.get("state") == "Combat":
            seen_turns.add(r.get("key"))
            inp = find_input(r.get("invoker") or {})
            if not inp:
                print(f"turn {r.get('key')}: no input")
                continue
            print(f"\n=== Input turn={inp.get('turn')} key={r.get('key')} lineSeq={r.get('lineSeq')} ===")
            print(f"  availableRaces={coll_summary(inp.get('availableRaces'))} DamageCap={inp.get('DamageCap')} "
                  f"Anomaly={coll_summary(inp.get('Anomaly'))} isDuos={inp.get('isDuos')}")
            for side in ("Player", "Opponent"):
                p = inp.get(side) or {}
                scalars = {k: p.get(k) for k in sorted(p) if k[0].isupper() and not isinstance(p.get(k), dict)}
                print(f"  {side} scalars: {scalars}")
                for coll in ("Side", "Hand", "Secrets", "HeroPowers", "Trinkets", "Quests", "Objectives"):
                    print(f"    {coll}: {coll_summary(p.get(coll))}")
        if len(seen_turns) >= 3 and transfers:
            pass
