"""Field/schema mining across BgHelperDiag games."""
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(sys.argv[1] if len(sys.argv) > 1 else r"C:\projects\github\hdt-bg-helper\data\BgHelperDiag")


def deep_keys(obj):
    keys = set()
    if not isinstance(obj, dict):
        return keys
    for k, v in obj.items():
        if k.startswith("$"):
            continue
        keys.add(k)
        if k in ("Player", "Opponent", "PlayerTeammate", "OpponentTeammate") and isinstance(v, dict):
            for k2 in v:
                if not k2.startswith("$"):
                    keys.add(f"{k}.{k2}")
    return keys


def list_items(wrapper):
    if isinstance(wrapper, dict):
        return wrapper.get("items") or []
    if isinstance(wrapper, list):
        return wrapper
    return []


def card_id_from_entity(h):
    if not isinstance(h, dict):
        return None
    for k in ("CardId", "cardId", "Id", "id"):
        if isinstance(h.get(k), str) and h.get(k):
            return h[k]
    data = h.get("Data")
    if isinstance(data, dict):
        for k in ("CardId", "cardId", "Id", "id", "MinionId"):
            if isinstance(data.get(k), str) and data.get(k):
                return data[k]
        # type string often encodes the minion class
        t = data.get("$type") or ""
        if "BobsBuddy" in t:
            return t
    t = h.get("$type") or ""
    return t or None


def main():
    schema_by_bb = defaultdict(set)
    hand_stats = Counter()
    hand_types = Counter()
    trinket_stats = Counter()
    trinket_ids = Counter()
    tf_2717 = Counter()
    resources = Counter()
    anomaly = Counter()
    damage_caps = Counter()
    races = Counter()
    player_minions = []
    opp_minions = []
    combat_inputs = 0

    for gd in sorted(ROOT.iterdir()):
        if not gd.is_dir():
            continue
        meta = json.loads((gd / "meta.json").read_text(encoding="utf-8"))
        bb = meta.get("bobsBuddy", {}).get("fileVersion")
        seen_schema = False
        for line in open(gd / "records.jsonl", encoding="utf-8"):
            r = json.loads(line)
            if r.get("type") != "hdt_bb" or not r.get("hasInput"):
                continue
            if r.get("state") != "Combat":
                continue
            inp = (r.get("invoker") or {}).get("_input")
            if not isinstance(inp, dict):
                continue
            if not seen_schema:
                schema_by_bb[bb] |= deep_keys(inp)
                seen_schema = True
            # one dump per turn key preferably when inputChanged
            if not (r.get("inputChanged") or r.get("reason") == "combat_start"):
                continue
            combat_inputs += 1
            opp = inp.get("Opponent") or {}
            player = inp.get("Player") or {}
            damage_caps[inp.get("DamageCap")] += 1
            if inp.get("Anomaly") is None:
                anomaly["null"] += 1
            else:
                anomaly["non_null"] += 1
            race_items = list_items(inp.get("availableRaces"))
            if race_items:
                races[tuple(race_items)] += 1
            tf_2717[opp.get("FriendlyMinionsDeadLastCombatCounter")] += 1
            resources[opp.get("ResourcesSpentThisGame")] += 1
            for h in list_items(opp.get("Hand")):
                hand_stats["cards"] += 1
                hand_types[h.get("$type", "?") if isinstance(h, dict) else type(h).__name__] += 1
                cid = card_id_from_entity(h)
                if cid and not str(cid).startswith("BobsBuddy") and "Unknown" not in str(cid):
                    hand_stats["known"] += 1
                else:
                    hand_stats["unknown_or_type_only"] += 1
            for side_name, side in (("P", player), ("O", opp)):
                items = list_items(side.get("Trinkets"))
                if items:
                    trinket_stats[f"{side_name}_with"] += 1
                for t in items:
                    trinket_stats["items"] += 1
                    cid = None
                    if isinstance(t, dict):
                        cid = t.get("CardId") or t.get("cardId")
                        if cid is None:
                            for k, v in t.items():
                                if isinstance(v, str) and ("MagicItem" in v or v.startswith("BG")):
                                    cid = v
                                    break
                        if cid is None:
                            cid = t.get("$type")
                    if cid:
                        trinket_ids[str(cid)] += 1
                    else:
                        trinket_stats["no_id"] += 1
                        if trinket_stats["no_id"] <= 2:
                            print("trinket keys", sorted(t.keys()) if isinstance(t, dict) else t)
            player_minions.append(len(list_items(player.get("Side"))))
            opp_minions.append(len(list_items(opp.get("Side"))))

    bbs = sorted(schema_by_bb)
    print("BB versions", bbs)
    print("combat input dumps mined", combat_inputs)
    base = schema_by_bb[bbs[0]]
    for bb in bbs[1:]:
        added = sorted(schema_by_bb[bb] - base)
        removed = sorted(base - schema_by_bb[bb])
        print(f"\n{bbs[0]} -> {bb}: +{len(added)} -{len(removed)}")
        if added:
            print("  +", added)
        if removed:
            print("  -", removed)
    print("\nonly in first", sorted(schema_by_bb[bbs[0]] - schema_by_bb[bbs[-1]]))
    print("only in last", sorted(schema_by_bb[bbs[-1]] - schema_by_bb[bbs[0]]))

    print("\nHand", dict(hand_stats), "types", dict(hand_types))
    print("Trinket", dict(trinket_stats), "unique", len(trinket_ids))
    print("top trinkets", trinket_ids.most_common(12))
    print("Opp 2717/FriendlyMinionsDead", dict(sorted(tf_2717.items(), key=lambda x: -(x[1] or 0))[:12]))
    print("Opp ResourcesSpent", dict(list(resources.items())[:8]))
    print("DamageCap", dict(damage_caps))
    print("Anomaly", dict(anomaly))
    print("race sets", len(races), "top", races.most_common(5))
    print(
        "minions P/O avg",
        sum(player_minions) / len(player_minions),
        sum(opp_minions) / len(opp_minions),
        "n",
        len(player_minions),
    )


if __name__ == "__main__":
    main()
