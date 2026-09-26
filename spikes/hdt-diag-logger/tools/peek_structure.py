"""Peek at record JSON keys only (no BattleTags, no full Input)."""
import json
import os
import sys

root = os.path.join(os.environ["APPDATA"], "HearthstoneDeckTracker", "BgHelperDiag")
game = sys.argv[1] if len(sys.argv) > 1 else "20260925_170955_cd944c"
path = os.path.join(root, game, "records.jsonl")


def keys_of(obj, prefix="", depth=0, out=None, max_depth=3):
    if out is None:
        out = set()
    if depth > max_depth or not isinstance(obj, dict):
        return out
    for k, v in obj.items():
        p = f"{prefix}.{k}" if prefix else k
        out.add(p)
        if isinstance(v, dict):
            keys_of(v, p, depth + 1, out, max_depth)
        elif isinstance(v, list) and v and isinstance(v[0], dict):
            keys_of(v[0], p + "[]", depth + 1, out, max_depth)
    return out


def find_input(invoker):
    """Walk invoker dump for the Input object."""
    if not isinstance(invoker, dict):
        return None
    t = invoker.get("$type", "")
    if t.endswith(".Input") or t == "BobsBuddy.Simulation.Input":
        return invoker
    for k, v in invoker.items():
        if k in ("$id", "$type", "$ref"):
            continue
        if isinstance(v, dict):
            found = find_input(v)
            if found:
                return found
    return None


seen = {"entities": 0, "hdt_bb": 0}
with open(path, encoding="utf-8") as f:
    for line in f:
        r = json.loads(line)
        t = r.get("type")
        if t == "entities" and seen["entities"] == 0 and r.get("reason") == "combat_start":
            seen["entities"] += 1
            print("=== entities combat_start top keys ===")
            print(sorted(r.keys()))
            ctx = r.get("context", {})
            print("context keys:", sorted(ctx.keys()))
            print("context.player keys:", sorted((ctx.get("player") or {}).keys()))
            print("context.opponent keys:", sorted((ctx.get("opponent") or {}).keys()))
            print("availableRaces:", ctx.get("availableRaces"))
            print("anomalyDbfId:", ctx.get("anomalyDbfId"))
            print("turn:", ctx.get("turn"), "gameEntityTurn:", ctx.get("gameEntityTurn"))
            ents = r.get("entities") or []
            print("entityCount:", r.get("entityCount"), "list:", len(ents))
            if ents:
                print("entity keys:", sorted(ents[0].keys()))
                print("info keys sample:", sorted((ents[0].get("info") or {}).keys()))
                tag_names = set()
                card_ids = set()
                zones = {}
                for e in ents:
                    tag_names.update((e.get("tags") or {}).keys())
                    cid = e.get("cardId") or ""
                    if cid:
                        card_ids.add(cid)
                    z = (e.get("tags") or {}).get("ZONE")
                    zones[z] = zones.get(z, 0) + 1
                print("tag names count:", len(tag_names))
                print("zones:", zones)
                interesting = [c for c in sorted(card_ids) if any(x in c.lower() for x in (
                    "tagtransfer", "transfer", "enchant", "quest", "secret", "trinket", "hero", "anomaly"))]
                print("interesting cardIds (truncated):", interesting[:40], "n=", len(interesting))
                # player entities
                players = [e for e in ents if (e.get("tags") or {}).get("PLAYER_ID")]
                print("player entities:", [(e["id"], e.get("cardId"), e.get("name"),
                                            {k: (e.get("tags") or {}).get(k) for k in (
                                                "PLAYER_ID", "CONTROLLER", "HERO_ENTITY", "ZONE",
                                                "NUM_RESOURCES_SPENT_THIS_GAME", "PLAYER_TECH_LEVEL")})
                                           for e in players])
        if t == "hdt_bb" and seen["hdt_bb"] == 0 and r.get("hasInput"):
            seen["hdt_bb"] += 1
            print("\n=== hdt_bb first with input ===")
            print("top keys:", sorted(k for k in r.keys() if k != "invoker"))
            print("key/state/reRun/reason/hasOutput:", r.get("key"), r.get("state"),
                  r.get("reRunCount"), r.get("reason"), r.get("hasOutput"))
            inv = r.get("invoker") or {}
            print("invoker type:", inv.get("$type"))
            print("invoker field names:", sorted(k for k in inv.keys() if not k.startswith("$")))
            inp = find_input(inv)
            if inp:
                print("Input type:", inp.get("$type"))
                print("Input fields:", sorted(k for k in inp.keys() if not k.startswith("$")))
                for side in ("Player", "Opponent", "<Player>k__BackingField", "<Opponent>k__BackingField"):
                    if side in inp:
                        pl = inp[side]
                        print(f"  {side} type:", pl.get("$type") if isinstance(pl, dict) else type(pl).__name__)
                        if isinstance(pl, dict):
                            print(f"  {side} fields:", sorted(k for k in pl.keys() if not k.startswith("$")))
            else:
                print("Input not found under invoker")
                # print _input if present
                if "_input" in inv:
                    print("_input keys:", sorted((inv["_input"] or {}).keys())[:40] if isinstance(inv["_input"], dict) else inv["_input"])

        if seen["entities"] and seen["hdt_bb"]:
            break
