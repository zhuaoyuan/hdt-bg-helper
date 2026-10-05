# -*- coding: utf-8 -*-
"""Cross-check one BgHelperDiag game against a Tuanzi Chinese battle report.

Usage:
  python eval_tuanzi_crosscheck.py <game_dir> <tuanzi_txt> [--official <other_game_dir>]
"""
from __future__ import annotations

import argparse
import json
import os
import re
from collections import Counter
from typing import Any

from diag_io import read_records as load_records


def load_meta(game_dir: str) -> dict:
    with open(os.path.join(game_dir, "meta.json"), encoding="utf-8") as f:
        return json.load(f)


def find_by_type(obj: Any, suffixes: tuple[str, ...], depth: int = 0) -> Any:
    if not isinstance(obj, dict) or depth > 10:
        return None
    t = obj.get("$type") or ""
    if isinstance(t, str) and any(t.endswith(s) or s in t for s in suffixes):
        return obj
    for k, v in obj.items():
        if k in ("$id", "$type", "$ref"):
            continue
        if isinstance(v, dict):
            found = find_by_type(v, suffixes, depth + 1)
            if found:
                return found
        elif isinstance(v, list):
            for it in v:
                if isinstance(it, dict):
                    found = find_by_type(it, suffixes, depth + 1)
                    if found:
                        return found
    return None


def deep_keys(obj: Any, prefix: str = "", depth: int = 0, out: set | None = None, maxd: int = 2) -> set:
    if out is None:
        out = set()
    if depth > maxd or not isinstance(obj, dict):
        return out
    for k, v in obj.items():
        p = f"{prefix}.{k}" if prefix else k
        out.add(p)
        if isinstance(v, dict):
            deep_keys(v, p, depth + 1, out, maxd)
        elif isinstance(v, list) and v and isinstance(v[0], dict):
            deep_keys(v[0], p + "[]", depth + 1, out, maxd)
    return out


def collect_types(obj: Any, out: set | None = None, depth: int = 0) -> set:
    if out is None:
        out = set()
    if depth > 12 or not isinstance(obj, dict):
        return out
    t = obj.get("$type")
    if isinstance(t, str):
        out.add(t.split(",")[0])
    for v in obj.values():
        if isinstance(v, dict):
            collect_types(v, out, depth + 1)
        elif isinstance(v, list):
            for it in v[:5]:
                if isinstance(it, dict):
                    collect_types(it, out, depth + 1)
    return out


def list_items(node: Any) -> list:
    if isinstance(node, list):
        return node
    if isinstance(node, dict):
        return node.get("items") or []
    return []


def get_player_obj(inp: dict, which: str) -> dict | None:
    if which in inp and isinstance(inp[which], dict):
        return inp[which]
    if which == "Player":
        for k, v in inp.items():
            if isinstance(v, dict) and re.fullmatch(r"player_[0-9a-f]{8}", k or ""):
                if "Side" in v:
                    return v
    return None


def minion_from_bb(m: dict) -> dict:
    data = m.get("_data") if isinstance(m.get("_data"), dict) else {}
    atk = data.get("MaxAttack")
    if atk is None:
        atk = data.get("BaseAttack")
    hp = data.get("MaxHealth")
    if hp is None:
        hp = data.get("BaseHealth")
    return {
        "cardId": m.get("CardID") or m.get("CardId"),
        "name": m.get("minionName"),
        "atk": atk,
        "health": hp,
        "golden": bool(data.get("Golden")),
        "tier": m.get("tier"),
    }


def hero_power_ids(side: dict | None) -> list[str]:
    if not side:
        return []
    out = []
    for it in list_items(side.get("HeroPowers")):
        if isinstance(it, dict) and it.get("CardId"):
            out.append(it["CardId"])
    return out


def entity_by_id(entities: list[dict]) -> dict[int, dict]:
    out = {}
    for e in entities or []:
        eid = e.get("id")
        if eid is not None:
            out[int(eid)] = e
    return out


def hero_card_from_entities(ctx_side: dict, entities: list[dict]) -> str | None:
    if not ctx_side:
        return None
    hid = ctx_side.get("hero")
    by_id = entity_by_id(entities)
    e = by_id.get(int(hid)) if hid is not None else None
    if e:
        return e.get("cardId")
    return None


def board_minions_from_entities(ctx_side: dict, entities: list[dict]) -> list[dict]:
    if not ctx_side:
        return []
    by_id = entity_by_id(entities)
    out = []
    for eid in ctx_side.get("board") or []:
        e = by_id.get(int(eid))
        if not e:
            continue
        tags = e.get("tags") or {}
        zone = tags.get("ZONE")
        ctype = tags.get("CARDTYPE")
        if zone not in (1, "1", "PLAY"):
            continue
        if ctype not in (4, "4", "MINION"):
            continue
        premium = tags.get("PREMIUM")
        out.append({
            "cardId": e.get("cardId"),
            "name": e.get("name"),
            "atk": int(tags["ATK"]) if tags.get("ATK") is not None else None,
            "health": int(tags["HEALTH"]) if tags.get("HEALTH") is not None else None,
            "golden": bool(premium) if premium is not None else False,
        })
    return out


def segment_combats(records: list[dict]) -> list[dict]:
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


def best_bb_for_turn(recs: list[dict], turn: int | None) -> dict | None:
    bbs = [r for r in recs if r.get("type") == "hdt_bb"]
    if turn is not None:
        same = [r for r in bbs if r.get("key") == turn]
        if same:
            bbs = same
    with_out = [r for r in bbs if r.get("hasOutput")]
    pool = with_out or bbs
    if not pool:
        return None
    combatish = [r for r in pool if r.get("state") == "Combat"]
    return (combatish or pool)[-1]


def extract_output(out: dict | None) -> dict:
    if not isinstance(out, dict):
        return {}
    return {
        "win": out.get("winRate"),
        "tie": out.get("tieRate"),
        "loss": out.get("lossRate"),
        "myLethal": out.get("myDeathRate"),
        "theirLethal": out.get("theirDeathRate"),
        "avDamage": out.get("avDamage"),
        "medianDamage": out.get("medianDamage"),
        "simCount": out.get("simulationCount"),
        "friendlyHealth": out.get("friendlyHealth"),
        "opponentHealth": out.get("opponentHealth"),
        "exit": out.get("myExitCondition"),
    }


def extract_combat_views(records: list[dict]) -> list[dict]:
    views = []
    for i, c in enumerate(segment_combats(records), 1):
        ents_recs = [r for r in c["records"] if r.get("type") == "entities"]
        start = next((r for r in ents_recs if r.get("reason") == "combat_start"), None)
        end = next((r for r in ents_recs if r.get("reason") in ("combat_end", "game_end")), None)
        turn = (start.get("context") or {}).get("turn") if start else None
        ctx = (start or {}).get("context") or {}
        entities = (start or {}).get("entities") or []
        bb = best_bb_for_turn(c["records"], turn)
        inv = bb.get("invoker") if bb else None
        inp = find_by_type(inv, (".Input",)) if inv else None
        out = inv.get("Output") if isinstance(inv, dict) else None
        player = get_player_obj(inp, "Player") if inp else None
        opponent = get_player_obj(inp, "Opponent") if inp else None
        p_mins = [minion_from_bb(m) for m in list_items((player or {}).get("Side"))]
        o_mins = [minion_from_bb(m) for m in list_items((opponent or {}).get("Side"))]
        views.append({
            "combat": i,
            "turn": turn,
            "playerHeroCard": hero_card_from_entities(ctx.get("player") or {}, entities),
            "oppHeroCard": hero_card_from_entities(ctx.get("opponent") or {}, entities),
            "playerHeroPowers": hero_power_ids(player),
            "oppHeroPowers": hero_power_ids(opponent),
            "playerMinions": p_mins,
            "oppMinions": o_mins,
            "entityPlayerMinions": board_minions_from_entities(ctx.get("player") or {}, entities),
            "entityOppMinions": board_minions_from_entities(ctx.get("opponent") or {}, entities),
            "output": extract_output(out if isinstance(out, dict) else None),
            "bbState": bb.get("state") if bb else None,
            "hasOutput": bool(bb and bb.get("hasOutput")),
            "inputHasPlayerKey": bool(inp and "Player" in inp),
            "inputAnonPlayerKeys": [k for k in (inp or {}) if re.fullmatch(r"player_[0-9a-f]{8}", k or "")],
            "playerHealth": (player or {}).get("Health"),
            "oppHealth": (opponent or {}).get("Health"),
            "endSnap": bool(end),
        })
    return views


def compare_structure(a_dir: str, b_dir: str) -> None:
    a_meta, b_meta = load_meta(a_dir), load_meta(b_dir)
    a_rows, b_rows = load_records(a_dir), load_records(b_dir)
    print("\n=== STRUCTURE COMPARE (A=tuanzi-capture, B=official-sample) ===")
    print("A hdt/bb/dir:", a_meta.get("hdt"), "/", a_meta.get("bobsBuddy"))
    print("B hdt/bb/dir:", b_meta.get("hdt"), "/", b_meta.get("bobsBuddy"))
    print("A record types:", dict(Counter(r.get("type") for r in a_rows)))
    print("B record types:", dict(Counter(r.get("type") for r in b_rows)))

    def sample(rows):
        for r in rows:
            if r.get("type") == "hdt_bb" and r.get("hasOutput") and r.get("state") == "Combat":
                inv = r.get("invoker")
                return find_by_type(inv, (".Input",)), inv.get("Output") if isinstance(inv, dict) else None, inv
        return None, None, None

    ai, ao, ainv = sample(a_rows)
    bi, bo, binv = sample(b_rows)
    # Normalize anonymised Player key name for fair key compare
    def norm_input_keys(inp: dict | None) -> set:
        if not inp:
            return set()
        keys = deep_keys(inp, maxd=2)
        fixed = set()
        for k in keys:
            fixed.add(re.sub(r"player_[0-9a-f]{8}", "Player", k))
        return fixed

    a_keys, b_keys = norm_input_keys(ai), norm_input_keys(bi)
    print("Input keys only-in-A:", sorted(a_keys - b_keys), "n=", len(a_keys - b_keys))
    print("Input keys only-in-B:", sorted(b_keys - a_keys), "n=", len(b_keys - a_keys))
    print("Input keys shared (normalized):", len(a_keys & b_keys), "A", len(a_keys), "B", len(b_keys))
    a_types, b_types = collect_types(ainv), collect_types(binv)
    print("Invoker $type only-A n=", len(a_types - b_types), "sample", sorted(a_types - b_types)[:15])
    print("Invoker $type only-B n=", len(b_types - a_types), "sample", sorted(b_types - a_types)[:15])
    if isinstance(ao, dict) and isinstance(bo, dict):
        ascal = sorted(k for k, v in ao.items() if not str(k).startswith("$") and not isinstance(v, (dict, list)))
        bscal = sorted(k for k, v in bo.items() if not str(k).startswith("$") and not isinstance(v, (dict, list)))
        print("Output scalars A:", ascal)
        print("Output scalars B:", bscal)
        print("Output scalar diff A-B:", sorted(set(ascal) - set(bscal)))
        print("Output scalar diff B-A:", sorted(set(bscal) - set(ascal)))
    blob = json.dumps(ainv) if ainv else ""
    print("A literal Player key:", '"Player":' in blob)
    print("A player_xxxxxxxx rename:", bool(re.search(r'"player_[0-9a-f]{8}"\s*:', blob)))
    blob_b = json.dumps(binv) if binv else ""
    print("B literal Player key:", '"Player":' in blob_b)
    print("B player_xxxxxxxx rename:", bool(re.search(r'"player_[0-9a-f]{8}"\s*:', blob_b)))
    # Side / minion shape
    def side_shape(inp):
        if not inp:
            return None
        p = get_player_obj(inp, "Player") or get_player_obj(inp, "Opponent")
        if not p:
            return None
        side = p.get("Side")
        items = list_items(side)
        m0 = items[0] if items else {}
        data = m0.get("_data") if isinstance(m0.get("_data"), dict) else {}
        return {
            "sideType": (side or {}).get("$type") if isinstance(side, dict) else type(side).__name__,
            "n": len(items),
            "minionHas": sorted([k for k in ("CardID", "minionName", "_data") if k in m0]),
            "dataHas": sorted([k for k in ("MaxAttack", "MaxHealth", "BaseAttack", "BaseHealth", "Golden") if k in data]),
        }
    print("A side shape:", side_shape(ai))
    print("B side shape:", side_shape(bi))


# --- Tuanzi report ---

TURN_RE = re.compile(r"^第(\d+)回合，(.+?) VS (.+)$")
SIM_RE = re.compile(
    r"模拟结果（模拟(\d+)次）："
    r"([\d.]+)%抬走对面，([\d.]+)%赢，([\d.]+)%平，([\d.]+)%输，([\d.]+)%被抬走"
)
ACTUAL_RE = re.compile(r"^实际结果：(.+)$")
BOARD_RE = re.compile(r"^(我方|对方)随从：(.*)$")
END_RE = re.compile(r"游戏结束，战绩：第(\d+)名")
DAMAGE_RE = re.compile(r"(?:打对面|被对面打)(\d+)")


def parse_minions_zh(s: str) -> list[dict]:
    s = s.strip().rstrip("；").rstrip(";")
    if not s:
        return []
    parts = [p for p in s.split("；") if p.strip()]
    out = []
    for p in parts:
        p = p.strip()
        m = re.match(r"^(.+?)（金）（(\d+)-(\d+)）$", p)
        if m:
            out.append({"name": m.group(1), "golden": True, "atk": int(m.group(2)), "health": int(m.group(3))})
            continue
        m = re.match(r"^(.+?)（(\d+)-(\d+)）$", p)
        if m:
            out.append({"name": m.group(1), "golden": False, "atk": int(m.group(2)), "health": int(m.group(3))})
            continue
        out.append({"name": p, "golden": None, "atk": None, "health": None, "parse_error": True})
    return out


def parse_tuanzi(path: str) -> tuple[list[dict], dict | None]:
    text = open(path, encoding="utf-8").read()
    turns = []
    end = None
    cur = None
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        m = TURN_RE.match(line)
        if m:
            cur = {"turn": int(m.group(1)), "myHero": m.group(2).strip(), "oppHero": m.group(3).strip()}
            turns.append(cur)
            continue
        if cur is None:
            m = END_RE.search(line)
            if m:
                end = {"place": int(m.group(1)), "raw": line}
            continue
        m = BOARD_RE.match(line)
        if m:
            side = "mine" if m.group(1) == "我方" else "opp"
            cur[side] = parse_minions_zh(m.group(2))
            continue
        m = SIM_RE.search(line)
        if m:
            cur["sim"] = {
                "count": int(m.group(1)),
                "theirLethal": float(m.group(2)),
                "win": float(m.group(3)),
                "tie": float(m.group(4)),
                "loss": float(m.group(5)),
                "myLethal": float(m.group(6)),
            }
            continue
        m = ACTUAL_RE.match(line)
        if m:
            actual = m.group(1)
            cur["actual"] = actual
            cur["actualWin"] = "赢" in actual and "输" not in actual[:1]
            if actual.startswith("赢"):
                cur["actualResult"] = "win"
            elif actual.startswith("平"):
                cur["actualResult"] = "tie"
            elif actual.startswith("输"):
                cur["actualResult"] = "loss"
            else:
                cur["actualResult"] = "unknown"
            dm = DAMAGE_RE.search(actual)
            cur["actualDamage"] = int(dm.group(1)) if dm else 0
            cur["actualDied"] = "被抬走" in actual
            continue
        m = END_RE.search(line)
        if m:
            end = {"place": int(m.group(1)), "raw": line}
    return turns, end


def pct100(x) -> float | None:
    if x is None:
        return None
    v = float(x)
    if 0 <= v <= 1.0000001:
        return round(v * 100.0, 3)
    return round(v, 3)


def approx_eq(a, b, tol=0.6) -> bool:
    if a is None or b is None:
        return False
    return abs(float(a) - float(b)) <= tol


def board_sig(ms: list[dict]) -> list[tuple]:
    return sorted(
        (int(m["atk"]), int(m["health"]), bool(m.get("golden")))
        for m in ms
        if m.get("atk") is not None and m.get("health") is not None
    )


def infer_actual_from_output(out: dict) -> dict:
    """Infer realized combat outcome from BB output health/damage fields is not enough;
    use medianDamage sign as proxy for predicted typical result, not actual.
    Actual must come from entity health deltas or tuanzi text.
    """
    return {}


def health_delta_result(views_i: dict, views_next_player_health: int | None, tuanzi_actual: dict) -> None:
    pass


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("game_dir")
    ap.add_argument("tuanzi_txt")
    ap.add_argument("--official", default=None)
    args = ap.parse_args()

    meta = load_meta(args.game_dir)
    rows = load_records(args.game_dir)
    print("=== META ===")
    print(json.dumps({
        "pluginVersion": meta.get("pluginVersion"),
        "hdt": meta.get("hdt"),
        "bobsBuddy": meta.get("bobsBuddy"),
        "hearthDb": meta.get("hearthDb"),
        "hearthstoneBuild": meta.get("hearthstoneBuild"),
        "gameType": meta.get("gameTypeAtEnd"),
        "isDuos": meta.get("isBattlegroundsDuosMatch"),
        "records": meta.get("records"),
        "errors": meta.get("errors"),
        "endReason": meta.get("endReason"),
    }, ensure_ascii=False, indent=2))

    if args.official:
        compare_structure(args.game_dir, args.official)

    views = extract_combat_views(rows)
    print("\n=== DIAG COMBATS ===")
    for v in views:
        o = v["output"]
        print(
            f"T{v['turn']} heroes={v['playerHeroCard']}/{v['oppHeroCard']} "
            f"hpowers={v['playerHeroPowers']}/{v['oppHeroPowers']} "
            f"board={len(v['playerMinions'])}/{len(v['oppMinions'])} "
            f"PlayerKey={v['inputHasPlayerKey']} anon={v['inputAnonPlayerKeys']}"
        )
        print("  player:", [(m["name"] or m["cardId"], m["atk"], m["health"], m["golden"]) for m in v["playerMinions"]])
        print("  opp   :", [(m["name"] or m["cardId"], m["atk"], m["health"], m["golden"]) for m in v["oppMinions"]])
        print("  sim%  :", {
            "n": o.get("simCount"),
            "win": pct100(o.get("win")),
            "tie": pct100(o.get("tie")),
            "loss": pct100(o.get("loss")),
            "myLethal": pct100(o.get("myLethal")),
            "theirLethal": pct100(o.get("theirLethal")),
            "avDmg": o.get("avDamage"),
            "medDmg": o.get("medianDamage"),
            "hp": (o.get("friendlyHealth"), o.get("opponentHealth")),
        })

    tuanzi, end = parse_tuanzi(args.tuanzi_txt)
    print("\n=== TUANZI ===")
    for t in tuanzi:
        print(f"T{t['turn']} {t['myHero']} VS {t['oppHero']} "
              f"board={len(t.get('mine') or [])}/{len(t.get('opp') or [])} "
              f"sim={t.get('sim')} actual={t.get('actual')}")
    if end:
        print("end:", end)

    print("\n=== CROSSCHECK ===")
    n = min(len(views), len(tuanzi))
    stats = Counter()
    for i in range(n):
        v, t = views[i], tuanzi[i]
        stats["turns"] += 1

        # board counts + atk/hp/golden multisets (order-insensitive)
        bb_ok = board_sig(v["playerMinions"]) == board_sig(t.get("mine") or []) and \
            board_sig(v["oppMinions"]) == board_sig(t.get("opp") or [])
        ent_ok = board_sig(v["entityPlayerMinions"]) == board_sig(t.get("mine") or []) and \
            board_sig(v["entityOppMinions"]) == board_sig(t.get("opp") or [])
        count_ok = len(v["playerMinions"]) == len(t.get("mine") or []) and \
            len(v["oppMinions"]) == len(t.get("opp") or [])
        if count_ok:
            stats["count_ok"] += 1
        if bb_ok:
            stats["bb_board_ok"] += 1
        if ent_ok:
            stats["ent_board_ok"] += 1

        o = v["output"]
        sim = t.get("sim") or {}
        sim_ok = (
            approx_eq(pct100(o.get("win")), sim.get("win"))
            and approx_eq(pct100(o.get("tie")), sim.get("tie"))
            and approx_eq(pct100(o.get("loss")), sim.get("loss"))
            and approx_eq(pct100(o.get("myLethal")), sim.get("myLethal"))
            and approx_eq(pct100(o.get("theirLethal")), sim.get("theirLethal"))
            and (o.get("simCount") == sim.get("count") or abs((o.get("simCount") or 0) - (sim.get("count") or -1)) <= 2)
        )
        if sim_ok:
            stats["sim_ok"] += 1

        # actual result vs medianDamage / avDamage
        med = o.get("medianDamage")
        actual = t.get("actualResult")
        dmg = t.get("actualDamage") or 0
        # BB damage: positive = damage to opponent, negative = damage to self
        if actual == "win":
            result_ok = med is not None and med > 0
            dmg_ok = approx_eq(abs(float(med)), dmg, tol=0.01) or approx_eq(abs(float(o.get("avDamage") or 0)), dmg, tol=1.0)
        elif actual == "loss":
            result_ok = med is not None and med < 0
            dmg_ok = approx_eq(abs(float(med)), dmg, tol=0.01) or approx_eq(abs(float(o.get("avDamage") or 0)), dmg, tol=1.0)
        elif actual == "tie":
            result_ok = med is not None and float(med) == 0
            dmg_ok = dmg == 0
        else:
            result_ok = False
            dmg_ok = False
        # medianDamage is the *simulated typical* damage, not guaranteed actual.
        # Prefer: if |median|==actual damage and sign matches result, treat as strong agreement.
        # For ties with 56% tie rate, median can be 0 while actual is tie - good.
        # For wins, medianDamage often equals actual when deterministic.
        if result_ok:
            stats["result_sign_ok"] += 1
        if dmg_ok:
            stats["damage_ok"] += 1

        print(
            f"T{t['turn']}: count_ok={count_ok} bb_board_ok={bb_ok} ent_board_ok={ent_ok} "
            f"sim_ok={sim_ok} result_sign_vs_median={result_ok} dmg_vs_median/av={dmg_ok} "
            f"actual={actual}/{dmg} med={med} av={o.get('avDamage')}"
        )
        if not bb_ok:
            print("  diag player", board_sig(v["playerMinions"]), "tuanzi", board_sig(t.get("mine") or []))
            print("  diag opp   ", board_sig(v["oppMinions"]), "tuanzi", board_sig(t.get("opp") or []))
            print("  names diag ", [m.get("name") for m in v["playerMinions"]], "|", [m.get("name") for m in v["oppMinions"]])
            print("  names tuanzi", [m.get("name") for m in (t.get("mine") or [])], "|", [m.get("name") for m in (t.get("opp") or [])])

    print("\n=== SUMMARY ===")
    print(dict(stats))
    print("complete_combats", f"{sum(1 for v in views if v['hasOutput'] and v['endSnap'])}/{len(views)}")


if __name__ == "__main__":
    main()
