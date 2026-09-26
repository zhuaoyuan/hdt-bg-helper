"""Health mismatches, Output timing fields, leftover invokers."""
import json
import os
from collections import Counter

ROOT = os.path.join(os.environ["APPDATA"], "HearthstoneDeckTracker", "BgHelperDiag")


def games():
    return [os.path.join(ROOT, d) for d in sorted(os.listdir(ROOT))
            if os.path.isdir(os.path.join(ROOT, d))]


def tag(e, n, default=None):
    return (e.get("tags") or {}).get(n, default)


def find_input(inv):
    inner = (inv or {}).get("_input")
    if isinstance(inner, dict) and inner.get("$type") == "BobsBuddy.Simulation.Input":
        return inner
    return None


out_keys = Counter()
durations = []
for g in games():
    name = os.path.basename(g)
    recs = [json.loads(r) for r in open(os.path.join(g, "records.jsonl"), encoding="utf-8")]
    snaps = [r for r in recs if r.get("type") == "entities" and r.get("reason") == "combat_start"]
    bbs = [r for r in recs if r.get("type") == "hdt_bb"]
    print(f"\n=== {name} leftover keys / Output fields ===")
    first_bb = next((r for r in bbs if r.get("hasInput")), None)
    print("  first hdt_bb key/reason/lineSeq/turns-in-dump:",
          first_bb.get("key") if first_bb else None,
          first_bb.get("reason") if first_bb else None)
    # leftover: keys at combat 1
    c1 = [r for r in bbs if r.get("lineSeq", 0) < 4000]
    print("  early dumps keys:", sorted({r.get("key") for r in c1}))

    for r in bbs:
        out = (r.get("invoker") or {}).get("Output")
        if isinstance(out, dict) and out.get("$type", "").endswith("Output"):
            out_keys.update(k for k in out if not k.startswith("$"))
            for k in ("duration", "elapsed", "time", "milliseconds", "totalTime",
                      "simulationTime", "timeElapsed", "myExitCondition"):
                if k in out and out[k] not in (None, 0, ""):
                    durations.append((k, out[k]))
            # print numeric-ish extra once
    printed = False
    for r in bbs:
        out = (r.get("invoker") or {}).get("Output")
        if not isinstance(out, dict):
            continue
        nums = {k: out[k] for k in out if not k.startswith("$") and isinstance(out[k], (int, float, str))
                and k not in ("$type",)}
        if not printed and nums.get("simulationCount"):
            print("  Output scalar sample:", {k: v for k, v in nums.items() if k not in (
                "winRate", "tieRate", "lossRate", "myDeathRate", "theirDeathRate") or True})
            printed = True
            break

    print("  Health/Tier mismatches:")
    for snap in snaps:
        turn = (snap.get("context") or {}).get("turn")
        ctx = snap.get("context") or {}
        ents = {e["id"]: e for e in snap.get("entities") or []}
        first = next((r for r in bbs if r.get("key") == turn and r.get("hasInput")), None)
        inp = find_input((first or {}).get("invoker"))
        if not inp:
            continue
        for side, ctxp, pin in (("P", ctx.get("player") or {}, inp.get("Player") or {}),
                                ("O", ctx.get("opponent") or {}, inp.get("Opponent") or {})):
            hero = ents.get(ctxp.get("hero"))
            if not hero:
                continue
            hp = (tag(hero, "HEALTH") or 0) - (tag(hero, "DAMAGE") or 0) + (tag(hero, "ARMOR") or 0)
            hdt = pin.get("Health")
            dmg = pin.get("DamageTaken")
            tier_h = tag(hero, "PLAYER_TECH_LEVEL")
            pent = next((e for e in snap.get("entities") or []
                         if not e.get("cardId") and tag(e, "HERO_ENTITY")
                         and tag(e, "CONTROLLER") == ctxp.get("id")), None)
            tier_p = tag(pent, "PLAYER_TECH_LEVEL") if pent else None
            if hp != hdt or (tier_p != pin.get("Tier") and tier_h != pin.get("Tier")):
                print(f"    t{turn} {side}: snapHP={hp} (H={tag(hero,'HEALTH')} D={tag(hero,'DAMAGE')} "
                      f"A={tag(hero,'ARMOR')}) InputH={hdt} dmgTaken={dmg} "
                      f"tierHero={tier_h} tierPlayer={tier_p} InputT={pin.get('Tier')}")

print("\nOutput keys union:", sorted(out_keys))
print("duration-like:", durations[:10], "n=", len(durations))
