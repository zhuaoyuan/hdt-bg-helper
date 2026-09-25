"""Q-008: personal data volume from BgsLastGames.xml, HDT logs and the modded build's combat records.

Usage:  python analyze_volume.py
Writes: out/volume_report.json (aggregate only). Prints an anonymised summary.
Sources (read-only):
  %APPDATA%\\HearthstoneDeckTracker\\BgsLastGames.xml
  %APPDATA%\\HearthstoneDeckTracker\\Logs\\hdt_log_*.txt  (via hdtlog)
  C:\\Program Files\\HDT\\对战记录\\*.txt                 (written by the modded HDT only)
"""
from __future__ import annotations

import collections
import datetime as dt
import glob
import json
import os
import re
import xml.etree.ElementTree as ET

import hdtlog

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")
BGS_XML = os.path.expandvars(r"%APPDATA%\HearthstoneDeckTracker\BgsLastGames.xml")
RECORD_DIR = r"C:\Program Files\HDT\对战记录"


def dist(values):
    c = collections.Counter(values)
    return dict(sorted(c.items()))


def summarize(values):
    v = sorted(x for x in values if x is not None)
    if not v:
        return None
    return {"n": len(v), "min": v[0], "p25": v[len(v) // 4], "median": v[len(v) // 2],
            "p75": v[3 * len(v) // 4], "max": v[-1], "mean": round(sum(v) / len(v), 2)}


def bgs_xml():
    root = ET.parse(BGS_XML).getroot()
    games = []
    for g in root:
        st = dt.datetime.fromisoformat(g.get("StartTime")[:19])
        en = dt.datetime.fromisoformat(g.get("EndTime")[:19])
        games.append({"start": st, "minutes": round((en - st).total_seconds() / 60, 1),
                      "duos": g.get("Duos") == "true", "friendly": g.get("FriendlyGame") == "true",
                      "placement": int(g.get("Placemenent")), "has_rating_after": g.get("RatingAfter") is not None,
                      "final_board_minions": len(g.find("FinalBoard") or [])})
    months = collections.Counter(x["start"].strftime("%Y-%m") for x in games)
    days = collections.Counter(x["start"].date() for x in games)
    return {
        "games": len(games), "first": min(x["start"] for x in games).isoformat(),
        "last": max(x["start"] for x in games).isoformat(),
        "duos": sum(x["duos"] for x in games), "friendly": sum(x["friendly"] for x in games),
        "by_month": dict(sorted(months.items())), "active_days": len(days),
        "games_per_active_day": summarize(list(days.values())),
        "minutes": summarize([x["minutes"] for x in games]),
        "placement": dist(x["placement"] for x in games),
        "fields": ["Player(账号ID)", "StartTime", "EndTime", "Hero", "Rating", "RatingAfter", "Placemenent",
                   "FriendlyGame", "Duos", "FinalBoard/Minion(CardId+Tags)"],
    }


def combat_records():
    """Daily files written by the modded HDT: per combat '第N回合，A VS B' + boards + sim + actual result;
    a game ends with '游戏结束，战绩：第N名，原分数X，现分数Y'."""
    files = sorted(glob.glob(os.path.join(RECORD_DIR, "*.txt")))
    games, cur = [], None
    combats_total = sims_total = unknown_actual = 0
    for f in files:
        m = re.search(r"(\d{4})年(\d\d)月(\d\d)日", os.path.basename(f))
        day = dt.date(int(m[1]), int(m[2]), int(m[3]))
        last_turn = None
        for line in open(f, encoding="utf-8-sig", errors="replace"):
            line = line.strip()
            t = re.match(r"^第(\d+)回合，", line)
            if t:
                turn = int(t.group(1))
                if cur is None or (last_turn is not None and turn < last_turn):
                    if cur is not None:
                        games.append(cur)
                    cur = {"day": day, "turns": set(), "headers": 0, "placement": None, "ended": False}
                if turn != last_turn:
                    combats_total += 1
                cur["turns"].add(turn)
                cur["headers"] += 1
                last_turn = turn
                continue
            if line.startswith("模拟结果"):
                sims_total += 1
            if line.startswith("我拔线了"):
                unknown_actual += 1
            e = re.match(r"^游戏结束，战绩：第(\d+)名", line)
            if e and cur is not None:
                cur["placement"] = int(e.group(1))
                cur["ended"] = True
                games.append(cur)
                cur, last_turn = None, None
        # a game never spans files in practice; close an unfinished one at file end
        if cur is not None:
            games.append(cur)
            cur, last_turn = None, None
    ended = [g for g in games if g["ended"]]
    max_turn = [max(g["turns"]) for g in games if g["turns"]]
    months = collections.Counter(g["day"].strftime("%Y-%m") for g in games)
    days = collections.Counter(g["day"] for g in games)
    return {
        "files": len(files), "first_day": files and str(min(g["day"] for g in games)),
        "last_day": files and str(max(g["day"] for g in games)),
        "games_detected": len(games), "games_with_end_line": len(ended),
        "combat_headers": sum(g["headers"] for g in games), "combats_distinct_turns": combats_total,
        "sim_result_lines": sims_total, "actual_result_unknown_disconnect": unknown_actual,
        "by_month": dict(sorted(months.items())), "active_days": len(days),
        "games_per_active_day": summarize(list(days.values())),
        "max_turn_per_game": summarize(max_turn), "max_turn_dist": dist(max_turn),
        "reach_turn": {t: sum(1 for x in max_turn if x >= t) for t in range(1, 21)},
        "placement": dist(g["placement"] for g in ended),
    }


def logs():
    sessions = hdtlog.load_sessions()
    games = collections.OrderedDict()
    build_of_session = {}
    for s in sessions:
        build_of_session[s.file] = sorted(set(s.carddefs_builds))
        cur = None
        for no, sec, level, src, msg in s.lines:
            k = hdtlog.KEY_RE.match(msg) if src.startswith("BobsBuddyInvoker.") else None
            if k:
                cur = k.group(1)
                g = games.setdefault(cur, {"file": s.file, "hdt": s.hdt_version, "turns": set(), "end": None,
                                           "spectator": False, "day": (s.start_guess or s.mtime).date()})
                g["turns"].add(int(k.group(2)))
            if src == "GameStats.GameEnd" and cur and games[cur]["end"] is None:
                m = re.search(r"ended after (\d+) turns", msg)
                if m:
                    games[cur]["end"] = int(m.group(1))
            if src == "GameEventHandler.SaveAndUpdateStats" and "Spectator" in msg and cur:
                games[cur]["spectator"] = True
    played = [g for g in games.values() if not g["spectator"]]
    by_build = collections.defaultdict(list)
    for g in played:
        b = build_of_session[g["file"]]
        by_build[str(b[-1]) if b else "?"].append(g)
    return {
        "games_total": len(games), "spectated": sum(g["spectator"] for g in games.values()),
        "games_played": len(played),
        "max_combat_turn": summarize([max(g["turns"]) for g in played]),
        "combats_per_game": summarize([len(g["turns"]) for g in played]),
        "by_carddefs_build": {b: {"games": len(v), "days": sorted({str(x["day"]) for x in v}),
                                  "hdt": sorted({x["hdt"] for x in v})} for b, v in sorted(by_build.items())},
    }


def main():
    os.makedirs(OUT, exist_ok=True)
    rep = {"bgs_last_games_xml": bgs_xml(), "hdt_logs": logs(),
           "combat_records": combat_records() if os.path.isdir(RECORD_DIR) else None}
    with open(os.path.join(OUT, "volume_report.json"), "w", encoding="utf-8") as fh:
        json.dump(rep, fh, ensure_ascii=False, indent=1, default=str)
    print(json.dumps(rep, ensure_ascii=False, indent=1, default=str))


if __name__ == "__main__":
    main()
