# -*- coding: utf-8 -*-
"""Parse Tuanzi Chinese battle-report text and pair with diag games."""
from __future__ import annotations

import os
import re
from collections import Counter, defaultdict
from typing import Optional

TURN_RE = re.compile(r"^第(\d+)回合，(.+?) VS (.+)$")
DIRECT_RE = re.compile(r"^第(\d+)回合，我直接拔线")
SIM_RE = re.compile(
    r"模拟结果（模拟(\d+)次）："
    r"([\d.]+)%抬走对面，([\d.]+)%赢，([\d.]+)%平，([\d.]+)%输，([\d.]+)%被抬走"
)
ACTUAL_RE = re.compile(r"^实际结果：(.+)$")
BOARD_RE = re.compile(r"^(我方|对方)随从：(.*)$")
END_RE = re.compile(r"游戏结束，战绩：第(\d+)名")
DAMAGE_RE = re.compile(r"(?:打对面|被对面打)(\d+)")
UNKNOWN_RESULT = "我拔线了，插件并不知道结果"


def parse_minions_zh(s: str) -> list[dict]:
    s = s.strip().rstrip("；").rstrip(";")
    if not s:
        return []
    out = []
    for p in [x for x in s.split("；") if x.strip()]:
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


def parse_tuanzi_file(path: str) -> list[dict]:
    """Return list of games; each has myHero, place, turns{n: turn_dict}."""
    games: list[dict] = []
    cur: dict | None = None
    turn: dict | None = None
    with open(path, encoding="utf-8-sig") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            if cur is None:
                cur = {"turns": {}, "myHero": None, "place": None, "file": os.path.basename(path)}
            m = TURN_RE.match(line)
            if m:
                n = int(m.group(1))
                turn = cur["turns"].setdefault(n, {"turn": n})
                turn.update({
                    "myHero": m.group(2).strip(),
                    "oppHero": m.group(3).strip(),
                    "kind": turn.get("kind") or "pending",
                })
                cur["myHero"] = cur["myHero"] or turn["myHero"]
                continue
            m = DIRECT_RE.match(line)
            if m:
                n = int(m.group(1))
                cur["turns"][n] = {"turn": n, "kind": "direct_dc"}
                turn = None
                continue
            if turn is not None and line.startswith(UNKNOWN_RESULT):
                turn["kind"] = "unknown_result"
                continue
            m = BOARD_RE.match(line)
            if m and turn is not None:
                side = "mine" if m.group(1) == "我方" else "opp"
                turn[side] = parse_minions_zh(m.group(2))
                continue
            m = SIM_RE.search(line)
            if m and turn is not None:
                turn["sim"] = {
                    "count": int(m.group(1)),
                    "theirLethal": float(m.group(2)),
                    "win": float(m.group(3)),
                    "tie": float(m.group(4)),
                    "loss": float(m.group(5)),
                    "myLethal": float(m.group(6)),
                }
                continue
            m = ACTUAL_RE.match(line)
            if m and turn is not None:
                a = m.group(1)
                turn["kind"] = "actual"
                if a.startswith("赢"):
                    turn["actualRes"] = "win"
                elif a.startswith("平"):
                    turn["actualRes"] = "tie"
                elif a.startswith("输"):
                    turn["actualRes"] = "loss"
                else:
                    turn["actualRes"] = "?"
                dm = DAMAGE_RE.search(a)
                turn["actualDmg"] = int(dm.group(1)) if dm else 0
                turn["died"] = "我被抬走" in a
                turn["actualRaw"] = a
                continue
            m = END_RE.search(line)
            if m:
                cur["place"] = int(m.group(1))
                games.append(cur)
                cur, turn = None, None
    if cur and cur["turns"]:
        games.append(cur)
    return games


def load_tuanzi_dir(tdir: str) -> dict[str, list[dict]]:
    """day YYYYMMDD -> list of tuanzi games."""
    by_day: dict[str, list[dict]] = {}
    if not tdir or not os.path.isdir(tdir):
        return by_day
    for name in os.listdir(tdir):
        if not name.endswith(".txt"):
            continue
        # 2026年10月04日.txt
        m = re.match(r"^(\d{4})年(\d{1,2})月(\d{1,2})日\.txt$", name)
        if not m:
            continue
        day = f"{m.group(1)}{int(m.group(2)):02d}{int(m.group(3)):02d}"
        path = os.path.join(tdir, name)
        by_day[day] = parse_tuanzi_file(path)
    return by_day


def pair_games(game_rows: dict[str, list[dict]], tuanzi_by_day: dict[str, list[dict]]) -> dict[str, dict]:
    """Map diag gameId -> {game, score, file} using date + my hero name + opp names per turn."""
    by_day: dict[str, list[str]] = defaultdict(list)
    for gid in sorted(game_rows):
        by_day[gid[:8]].append(gid)
    pairs: dict[str, dict] = {}
    for day, gids in by_day.items():
        tgames = tuanzi_by_day.get(day) or []
        used: set[int] = set()
        for gid in gids:
            rows = game_rows[gid]
            names = Counter(r.get("myHero") for r in rows if r.get("myHero"))
            if not names:
                continue
            my = names.most_common(1)[0][0]
            best, best_score = None, -1
            for ti, tg in enumerate(tgames):
                if ti in used or tg.get("myHero") != my:
                    continue
                score = sum(
                    1
                    for r in rows
                    if r.get("turn") in tg["turns"]
                    and tg["turns"][r["turn"]].get("oppHero") == r.get("oppHero")
                )
                if score > best_score:
                    best, best_score = ti, score
            if best is not None and best_score > 0:
                used.add(best)
                pairs[gid] = {
                    "game": tgames[best],
                    "score": best_score,
                    "file": tgames[best].get("file"),
                }
    return pairs


def turn_from_pair(pair: Optional[dict], turn: Optional[int]) -> Optional[dict]:
    if not pair or turn is None:
        return None
    return pair["game"]["turns"].get(turn)
