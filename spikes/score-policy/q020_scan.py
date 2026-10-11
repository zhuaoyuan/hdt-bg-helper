# -*- coding: utf-8 -*-
"""Q-020 spike: compare stored damageResults to DamageCap on a few real combats.

Reads local BgHelperDiag only. Prints aggregates. Does not write personal data.
"""
from __future__ import annotations

import gzip
import json
import os
from collections import Counter
from pathlib import Path


def open_text(path: Path):
    if str(path).endswith(".gz"):
        return gzip.open(path, "rt", encoding="utf-8", errors="replace")
    return open(path, "r", encoding="utf-8", errors="replace")


def records_path(game: Path) -> Path | None:
    for name in ("records.jsonl.gz", "records.jsonl"):
        p = game / name
        if p.exists():
            return p
    return None


def list_items(node):
    if isinstance(node, list):
        return node
    if isinstance(node, dict):
        items = node.get("items")
        if isinstance(items, list):
            return items
    return []


def walk_input(inv: dict) -> dict | None:
    inp = inv.get("_input")
    return inp if isinstance(inp, dict) else None


def summarize_damage(values: list, cap) -> dict:
    nums = []
    for v in values:
        if isinstance(v, bool):
            continue
        if isinstance(v, (int, float)):
            nums.append(int(v))
        elif isinstance(v, dict) and "value" in v:
            nums.append(int(v["value"]))
    if not nums:
        return {"n": 0}
    c = Counter(nums)
    over = [x for x in nums if cap is not None and abs(x) > int(cap)]
    at = [x for x in nums if cap is not None and abs(x) == int(cap) and x != 0]
    return {
        "n": len(nums),
        "min": min(nums),
        "max": max(nums),
        "zeros": c[0],
        "pos": sum(1 for x in nums if x > 0),
        "neg": sum(1 for x in nums if x < 0),
        "overAbs": len(over),
        "atAbsCap": len(at),
        "unique": len(c),
        "top": c.most_common(6),
    }


def side_power(inp: dict, which: str) -> dict:
    side = inp.get(which)
    if not isinstance(side, dict):
        return {"tier": None, "n": 0, "atk": None}
    tier = side.get("Tier")
    atk = 0
    n = 0
    for m in list_items(side.get("Side")):
        if not isinstance(m, dict):
            continue
        data = m.get("_data") if isinstance(m.get("_data"), dict) else {}
        a = data.get("MaxAttack")
        if a is None:
            a = data.get("BaseAttack")
        if isinstance(a, (int, float)):
            atk += int(a)
            n += 1
    return {"tier": tier, "n": n, "atk": atk}


def scan_game(game: Path) -> list[dict]:
    path = records_path(game)
    if path is None:
        return []
    rows = []
    seen = set()
    with open_text(path) as f:
        for line in f:
            if "hdt_bb" not in line:
                continue
            r = json.loads(line)
            if r.get("type") != "hdt_bb" or not r.get("hasOutput"):
                continue
            if r.get("state") != "Combat":
                continue
            turn = r.get("key")
            if turn in seen:
                continue
            inv = r.get("invoker") or {}
            out = inv.get("Output")
            inp = walk_input(inv)
            if not isinstance(out, dict) or not isinstance(inp, dict):
                continue
            cap = inp.get("DamageCap")
            dr = out.get("damageResults")
            items = list_items(dr)
            stats = summarize_damage(items, cap)
            if stats.get("n", 0) == 0:
                # record shape once
                stats["shape"] = type(dr).__name__
                if isinstance(dr, dict):
                    stats["drKeys"] = [k for k in dr.keys() if not str(k).startswith("$")]
                    items_node = dr.get("items")
                    stats["itemsType"] = type(items_node).__name__
                    if isinstance(items_node, list) and items_node:
                        stats["item0Type"] = type(items_node[0]).__name__
                        if isinstance(items_node[0], dict):
                            stats["item0Keys"] = list(items_node[0].keys())[:12]
            win = float(out.get("winRate") or 0)
            tie = float(out.get("tieRate") or 0)
            loss = float(out.get("lossRate") or 0)
            me = side_power(inp, "Player")
            opp = side_power(inp, "Opponent")
            rows.append({
                "game": game.name,
                "turn": turn,
                "cap": cap,
                "win": round(win, 3),
                "tie": round(tie, 3),
                "loss": round(loss, 3),
                "av": out.get("avDamage"),
                "med": out.get("medianDamage"),
                "sims": out.get("simulationCount"),
                "myTier": me["tier"],
                "myN": me["n"],
                "myAtk": me["atk"],
                "oppTier": opp["tier"],
                "oppN": opp["n"],
                "oppAtk": opp["atk"],
                **{k: stats[k] for k in stats if k != "top"},
                "top": stats.get("top"),
            })
            seen.add(turn)
    return rows


def main() -> None:
    root = Path(os.environ["APPDATA"]) / "HearthstoneDeckTracker" / "BgHelperDiag"
    games = sorted(p for p in root.iterdir() if p.is_dir())
    all_rows = []
    for g in games:
        all_rows.extend(scan_game(g))

    def cap_pos(r):
        try:
            return int(r["cap"] or 0) > 0
        except (TypeError, ValueError):
            return False

    pos = [r for r in all_rows if cap_pos(r)]
    zero_cap = [r for r in all_rows if not cap_pos(r)]
    over_pos = [r for r in pos if r.get("overAbs")]
    over_zero = [r for r in zero_cap if (r.get("max") or 0) > 15 or (r.get("min") or 0) < -15]
    stuck = [
        r for r in pos
        if r.get("n") and r["win"] >= 0.99 and r["max"] == int(r["cap"]) and r["min"] == int(r["cap"])
        and (r.get("myAtk") or 0) + (r.get("myTier") or 0) > int(r["cap"]) + 5
    ]
    print(f"combats={len(all_rows)} cap>0={len(pos)} over_when_cap>0={len(over_pos)} cap0={len(zero_cap)} abs>15_when_cap0={len(over_zero)}")
    print(f"blowouts_stuck_at_cap_but_atk+tier>cap+5: {len(stuck)}")
    for r in stuck[:8]:
        print(
            f"  {r['game']} t={r['turn']} cap={r['cap']} myAtk={r['myAtk']} myTier={r['myTier']} myN={r['myN']} "
            f"oppAtk={r['oppAtk']} oppTier={r['oppTier']} n={r['n']} dmg={r['min']}..{r['max']}"
        )
    print("--- cap0 samples with |dmg|>15 ---")
    for r in over_zero[:6]:
        print(
            f"  {r['game']} t={r['turn']} cap={r['cap']} W={r['win']} dmg={r['min']}..{r['max']} "
            f"myAtk={r['myAtk']}+T{r['myTier']} oppAtk={r['oppAtk']}+T{r['oppTier']}"
        )


if __name__ == "__main__":
    main()
