# -*- coding: utf-8 -*-
"""Q-014: reconstruct per-combat actual results (win/tie/loss + damage) from BgHelperDiag
records and score them against Tuanzi battle-report text.

Signals per combat:
  hdt  : BobsBuddyInvoker fields dumped at combat_end (LastAttackingHero / LastAttackingHeroAttack),
         i.e. HDT's own result detection; needs the hero attack to be seen in the log.
  lb   : leaderboard hero entities (PLAYER_LEADERBOARD_PLACE): effective HP = HEALTH - DAMAGE + ARMOR
         for me and the combat opponent, replayed from power.log.gz, START -> END and START -> next START.

Usage:
  python eval_q014_reconstruct.py [--root DIR ...] [--tuanzi DIR] [--csv OUT] [--verbose]
Default roots: data/BgHelperDiag and %APPDATA%/HearthstoneDeckTracker/BgHelperDiag.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import re
from collections import Counter, defaultdict

from diag_io import read_records as load_records, records_path
from power_replay import read_power, TagState

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
DEFAULT_ROOTS = [
    os.path.join(REPO, "data", "BgHelperDiag"),
    os.path.join(os.environ.get("APPDATA", ""), "HearthstoneDeckTracker", "BgHelperDiag"),
]
DEFAULT_TUANZI = os.path.join(REPO, "data", "tuanzi")


# ---------------------------------------------------------------- diag side


def eff_hp(h: dict | None) -> int | None:
    if not h:
        return None
    return int(h["health"] or 0) - int(h["damage"] or 0) + int(h["armor"] or 0)


def classify(d_me: int | None, d_opp: int | None, opp_dead: bool) -> tuple[str, int | None]:
    if d_me is None:
        return "unknown", None
    if d_opp is None:
        if d_me > 0:
            return "loss", d_me
        return "unknown", None
    if d_me > 0 and d_opp <= 0:
        return "loss", d_me
    if d_opp > 0 and d_me <= 0:
        return "win", d_opp
    if d_me == 0 and d_opp == 0:
        return ("tie_or_ghost" if opp_dead else "tie"), 0
    if d_me <= 0 and d_opp <= 0:
        # healing / armor gain only; no combat damage seen
        return ("tie_or_ghost" if opp_dead else "tie"), 0
    return "conflict", None


def analyze_game(game_dir: str) -> list[dict]:
    recs = load_records(game_dir)
    power = read_power(game_dir)
    phases = [r for r in recs if r.get("type") == "combat_phase"]
    starts = [r["lineSeq"] for r in phases if r.get("value") is True]
    ends = [r["lineSeq"] for r in phases if r.get("value") is False]
    if not starts:
        return []
    last_seq = power[-1][0] if power else 0
    combats = []
    for i, s in enumerate(starts):
        nxt = starts[i + 1] if i + 1 < len(starts) else last_seq + 1
        e = next((x for x in ends if s < x < nxt), None)
        combats.append({"idx": i + 1, "start": s, "end": e, "next": nxt})

    # attach records
    for c in combats:
        c["recs"] = [r for r in recs if c["start"] <= r.get("lineSeq", -1) < c["next"]]

    # After a reconnect the END line is the first line of a FULL_ENTITY re-dump that carries the
    # post-combat hero DAMAGE/ARMOR; "settled" = first line after that dump.
    pos = {seq: i for i, (seq, _) in enumerate(power)}
    for c in combats:
        if c["end"] is None or c["end"] not in pos:
            c["settled"] = None
            continue
        i = pos[c["end"]]
        while i + 1 < len(power) and (power[i + 1][1].startswith("tag=") or power[i + 1][1].startswith("FULL_ENTITY - Updating")):
            i += 1
        c["settled"] = power[i][0]

    # snapshot leaderboard at points of interest
    want = defaultdict(list)
    for c in combats:
        want[c["start"]].append((c, "lb_start"))
        if c["end"] is not None:
            want[c["end"]].append((c, "lb_end"))
        if c["settled"] is not None:
            want[c["settled"]].append((c, "lb_settled"))
        want[c["next"] - 1].append((c, "lb_next"))
    st = TagState()
    for seq, payload in power:
        st.feed(seq, payload)
        if seq in want:
            snap = st.leaderboard_heroes()
            turn_tag = st.get(st.game_entity, "TURN")
            for c, key in want[seq]:
                c[key] = snap
                c[key + "_turntag"] = turn_tag
    # anything not reached (e.g. next-1 beyond log) -> final state
    final = st.leaderboard_heroes()
    for c in combats:
        for key in ("lb_start", "lb_next"):
            c.setdefault(key, final)
        c["reconnects"] = [x for x in st.create_game_lines if c["start"] < x < c["next"]]

    rows = []
    for c in combats:
        rs = c["recs"]
        start_snap = next((r for r in rs if r.get("type") == "entities" and r.get("reason") == "combat_start"), None)
        ctx = (start_snap or {}).get("context") or {}
        ents = {e.get("id"): e for e in (start_snap or {}).get("entities") or []}
        turn = ctx.get("turn")
        my_hero = (ctx.get("player") or {}).get("hero")
        opp_hero = (ctx.get("opponent") or {}).get("hero")
        opp_card = (ents.get(opp_hero) or {}).get("cardId") if opp_hero is not None else None
        my_card = (ents.get(my_hero) or {}).get("cardId") if my_hero is not None else None

        bbs = [r for r in rs if r.get("type") == "hdt_bb" and isinstance(r.get("invoker"), dict)]
        if turn is None:
            ts = [r["invoker"].get("_turn") for r in bbs if r.get("state") == "Combat"]
            turn = ts[-1] if ts else None
        if turn is None and c.get("lb_start_turntag"):
            turn = (int(c["lb_start_turntag"]) + 1) // 2
        same_turn = [r for r in bbs if r["invoker"].get("_turn") == turn]
        has_output = any(r.get("state") == "Combat" and r.get("hasOutput") for r in same_turn)
        end_bb = next((r for r in reversed(same_turn) if r.get("reason") in ("combat_end", "game_end")), None)
        names = [r["invoker"].get("_playerHeroName") for r in same_turn if r["invoker"].get("_playerHeroName")]
        opp_names = [r["invoker"].get("_opponentHeroName") for r in same_turn if r["invoker"].get("_opponentHeroName")]

        hdt_res, hdt_dmg = None, None
        if end_bb is not None:
            inv = end_bb["invoker"]
            la = inv.get("LastAttackingHero")
            if isinstance(la, dict) and la.get("$entity") is not None:
                if my_hero is not None and la["$entity"] == my_hero:
                    hdt_res = "win"
                elif my_card is not None and la.get("cardId") == my_card and opp_card != my_card:
                    hdt_res = "win"
                else:
                    hdt_res = "loss"
                hdt_dmg = inv.get("LastAttackingHeroAttack")
            else:
                hdt_res = "tie"
                hdt_dmg = 0

        lbs = c["lb_start"]
        me_lb = lbs.get(my_hero) if my_hero is not None else None
        if me_lb is None and my_card:
            me_lb = next((h for h in lbs.values() if h["card"] == my_card), None)
        my_ctrl = me_lb["controller"] if me_lb else None
        opp_lb = None
        if opp_card:
            cands = [h for h in lbs.values() if h["card"] == opp_card and h["controller"] != my_ctrl]
            if not cands:
                cands = [h for h in lbs.values() if h["card"] == opp_card]
            opp_lb = cands[0] if len(cands) == 1 else None
        opp_dead = bool(opp_lb and (eff_hp(opp_lb) or 0) <= 0)

        def delta(key, h):
            if h is None or key not in c or c[key] is None:
                return None
            after = c[key].get(h["id"])
            if after is None:
                return None
            return eff_hp(h) - eff_hp(after)

        out = {}
        for tag, key in (("end", "lb_end"), ("settled", "lb_settled"), ("next", "lb_next")):
            dm, do = delta(key, me_lb), delta(key, opp_lb)
            res, dmg = classify(dm, do, opp_dead)
            out[tag] = {"dMe": dm, "dOpp": do, "res": res, "dmg": dmg}
        me_after = c.get("lb_next", {}).get(me_lb["id"]) if me_lb else None
        died = me_lb is not None and me_after is not None and eff_hp(me_after) <= 0

        ghost = bool(opp_card and "KelThuzad" in opp_card)
        rows.append({
            "game": os.path.basename(game_dir),
            "combat": c["idx"],
            "turn": turn,
            "myName": Counter(names).most_common(1)[0][0] if names else None,
            "oppName": opp_names[-1] if opp_names else None,
            "myCard": my_card,
            "oppCard": opp_card,
            "hasStartSnap": start_snap is not None,
            "hasOutput": has_output,
            "hasEndSeq": c["end"] is not None,
            "reconnects": len(c["reconnects"]),
            "hdtRes": hdt_res,
            "hdtDmg": hdt_dmg,
            "oppLbFound": opp_lb is not None,
            "oppDead": opp_dead,
            "meHpStart": eff_hp(me_lb),
            "lbEnd": out["end"],
            "lbSettled": out["settled"],
            "lbNext": out["next"],
            "oppCardsOnLb": sorted(h["card"] or "?" for h in lbs.values() if h["controller"] != my_ctrl) if opp_lb is None else None,
            "diedByLb": died,
            "ghost": ghost,
        })
        rows[-1]["recon"] = reconstruct(rows[-1])
    return rows


def reconstruct(r: dict) -> dict:
    """Recommended pipeline (no Tuanzi text): HDT field if no reconnect, else leaderboard delta."""
    if r["hdtRes"] is not None and not r["reconnects"]:
        return {"res": r["hdtRes"], "dmg": r["hdtDmg"], "src": "hdt"}
    lb = r["lbSettled"] if r["hasEndSeq"] else r["lbNext"]
    if r["ghost"]:
        if lb["dMe"] is not None and lb["dMe"] > 0:
            return {"res": "loss", "dmg": lb["dMe"], "src": "lb"}
        if lb["dMe"] == 0:
            return {"res": "win_or_tie", "dmg": None, "src": "lb_ghost"}
        return {"res": "unknown", "dmg": None, "src": "none"}
    if lb["res"] in ("unknown", "conflict"):
        return {"res": "unknown", "dmg": None, "src": "none"}
    return {"res": lb["res"].replace("_or_ghost", ""), "dmg": lb["dmg"], "src": "lb"}


# ---------------------------------------------------------------- tuanzi side

T_TURN = re.compile(r"^第(\d+)回合，(.+?) VS (.+)$")
T_DIRECT = re.compile(r"^第(\d+)回合，我直接拔线")
T_ACTUAL = re.compile(r"^实际结果：(.+)$")
T_UNKNOWN = "我拔线了，插件并不知道结果"
T_END = re.compile(r"游戏结束，战绩：第(\d+)名")
T_DMG = re.compile(r"(?:打对面|被对面打)(\d+)")


def parse_tuanzi_games(path: str) -> list[dict]:
    games, cur = [], None
    turn = None
    with open(path, encoding="utf-8-sig") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            if cur is None:
                cur = {"turns": {}, "myHero": None, "place": None}
            m = T_TURN.match(line)
            if m:
                n = int(m.group(1))
                turn = cur["turns"].setdefault(n, {"turn": n})
                turn.update({"myHero": m.group(2), "oppHero": m.group(3)})
                turn.setdefault("kind", "pending")
                cur["myHero"] = cur["myHero"] or m.group(2)
                continue
            m = T_DIRECT.match(line)
            if m:
                n = int(m.group(1))
                cur["turns"][n] = {"turn": n, "kind": "direct_dc"}
                turn = None
                continue
            if turn is not None and line.startswith(T_UNKNOWN):
                turn["kind"] = "unknown_result"
                continue
            m = T_ACTUAL.match(line)
            if m and turn is not None:
                a = m.group(1)
                turn["kind"] = "actual"
                turn["actualRes"] = "win" if a.startswith("赢") else "tie" if a.startswith("平") else "loss" if a.startswith("输") else "?"
                dm = T_DMG.search(a)
                turn["actualDmg"] = int(dm.group(1)) if dm else 0
                turn["died"] = "我被抬走" in a
                continue
            m = T_END.search(line)
            if m:
                cur["place"] = int(m.group(1))
                games.append(cur)
                cur, turn = None, None
    if cur and cur["turns"]:
        games.append(cur)
    return games


def tuanzi_file_for(day: str, tdir: str) -> str | None:
    name = f"{day[:4]}年{day[4:6]}月{day[6:8]}日.txt"
    p = os.path.join(tdir, name)
    return p if os.path.exists(p) else None


def pair_games(game_rows: dict[str, list[dict]], tdir: str) -> dict[str, dict]:
    """Map diag game id -> tuanzi game, by date + my hero Chinese name + opponent names per turn."""
    by_day = defaultdict(list)
    for gid in sorted(game_rows):
        by_day[gid[:8]].append(gid)
    pairs = {}
    for day, gids in by_day.items():
        p = tuanzi_file_for(day, tdir)
        if not p:
            continue
        tgames = parse_tuanzi_games(p)
        used = set()
        for gid in gids:
            rows = game_rows[gid]
            names = Counter(r["myName"] for r in rows if r["myName"])
            if not names:
                continue
            my = names.most_common(1)[0][0]
            best, best_score = None, 0
            for ti, tg in enumerate(tgames):
                if ti in used or tg["myHero"] != my:
                    continue
                score = sum(1 for r in rows if r["turn"] in tg["turns"]
                            and tg["turns"][r["turn"]].get("oppHero") == r["oppName"])
                if score > best_score:
                    best, best_score = ti, score
            if best is not None:
                used.add(best)
                pairs[gid] = {"file": os.path.basename(p), "game": tgames[best], "score": best_score}
    return pairs


# ---------------------------------------------------------------- scoring

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", action="append")
    ap.add_argument("--tuanzi", default=DEFAULT_TUANZI)
    ap.add_argument("--csv", default=None)
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()
    roots = args.root or DEFAULT_ROOTS

    dirs = {}
    for root in roots:
        if not os.path.isdir(root):
            continue
        for name in sorted(os.listdir(root)):
            d = os.path.join(root, name)
            if records_path(d) and os.path.isfile(os.path.join(d, "power.log.gz")):
                dirs.setdefault(name, d)

    game_rows = {}
    for name, d in sorted(dirs.items()):
        try:
            game_rows[name] = analyze_game(d)
        except Exception as ex:  # keep going on odd captures
            print(f"[skip] {name}: {type(ex).__name__}: {ex}")
    all_rows = [r for rows in game_rows.values() for r in rows]
    print(f"games={len(game_rows)} combats={len(all_rows)}")

    # --- A. internal agreement: hdt vs lb on every combat with an hdt result and no reconnect
    agree = Counter()
    disagree = []
    for r in all_rows:
        if r["hdtRes"] is None or r["reconnects"]:
            continue
        lb = r["lbSettled"] if r["hasEndSeq"] else r["lbNext"]
        h, l = r["hdtRes"], lb["res"]
        if l == "tie_or_ghost":
            l = "tie"
        agree["n"] += 1
        if h == l:
            agree["res_ok"] += 1
            if h == "tie" or (r["hdtDmg"] == lb["dmg"]):
                agree["dmg_ok"] += 1
            elif r["diedByLb"]:
                agree["dmg_lethal_capped"] += 1
            else:
                disagree.append(("dmg", r))
        else:
            disagree.append(("res", r))
    print("\n[A] HDT LastAttackingHero vs leaderboard delta (no reconnect):", dict(agree))
    for kind, r in disagree[:25]:
        print(f"   {kind} {r['game']} T{r['turn']} hdt={r['hdtRes']}/{r['hdtDmg']} lbSettled={r['lbSettled']} "
              f"oppCard={r['oppCard']} oppLb={r['oppLbFound']} oppDead={r['oppDead']} died={r['diedByLb']} "
              f"lbOppCards={r['oppCardsOnLb']}")

    # --- B. against tuanzi text
    pairs = pair_games(game_rows, args.tuanzi)
    print(f"\n[B] tuanzi pairing: {len(pairs)} games")
    for gid, p in sorted(pairs.items()):
        tg = p["game"]
        kinds = Counter(t["kind"] for t in tg["turns"].values())
        print(f"   {gid} <- {p['file']} {tg['myHero']} place={tg['place']} oppNameMatches={p['score']} kinds={dict(kinds)}")

    score = defaultdict(Counter)
    detail = []
    for gid, p in sorted(pairs.items()):
        rows = {r["turn"]: r for r in game_rows[gid] if r["turn"] is not None}
        for n, t in sorted(p["game"]["turns"].items()):
            r = rows.get(n)
            kind = t["kind"]
            if r is None:
                score[kind]["no_diag_combat"] += 1
                detail.append((gid, n, kind, t, None))
                continue
            score[kind]["n"] += 1
            if r["reconnects"]:
                score[kind]["reconnect_in_window"] += 1
            if r["hasOutput"]:
                score[kind]["has_bb_output"] += 1
            for sig in ("hdt", "lbEnd", "lbSettled", "lbNext", "lbOnly", "recon"):
                if sig == "hdt":
                    res, dmg = r["hdtRes"], r["hdtDmg"]
                elif sig == "recon":
                    res, dmg = r["recon"]["res"], r["recon"]["dmg"]
                elif sig == "lbOnly":
                    # what the pipeline gives if HDT's field were missing (pretend disconnect)
                    fake = dict(r, hdtRes=None)
                    rr = reconstruct(fake)
                    res, dmg = rr["res"], rr["dmg"]
                else:
                    res, dmg = r[sig]["res"], r[sig]["dmg"]
                if res is None or res in ("unknown", "conflict"):
                    score[kind][f"{sig}_none"] += 1
                    continue
                if res == "win_or_tie":
                    score[kind][f"{sig}_ambiguous"] += 1
                    if kind == "actual" and t["actualRes"] in ("win", "tie"):
                        score[kind][f"{sig}_ambiguous_consistent"] += 1
                    continue
                score[kind][f"{sig}_given"] += 1
                if kind != "actual":
                    continue
                exp = t["actualRes"]
                got = "tie" if res == "tie_or_ghost" else res
                if got == exp:
                    score[kind][f"{sig}_res_ok"] += 1
                    if exp == "tie" or dmg == t["actualDmg"]:
                        score[kind][f"{sig}_dmg_ok"] += 1
                    elif t.get("died"):
                        score[kind][f"{sig}_dmg_lethal"] += 1
            detail.append((gid, n, kind, t, r))
    print("\n[B] scores by tuanzi turn kind:")
    for kind, c in score.items():
        print(f"   {kind}: {dict(sorted(c.items()))}")

    print("\n[B] per-turn detail (non-matching or disconnect turns):")
    for gid, n, kind, t, r in detail:
        if r is None:
            print(f"   {gid} T{n} {kind}: no diag combat")
            continue
        ls = r["lbSettled"]
        ok = kind == "actual" and r["hdtRes"] == t["actualRes"] and ls["res"].replace("_or_ghost", "") == t["actualRes"] \
            and (t["actualRes"] == "tie" or ls["dmg"] == t["actualDmg"])
        if ok and not args.verbose:
            continue
        exp = f"{t.get('actualRes')}/{t.get('actualDmg')}{'/died' if t.get('died') else ''}" if kind == "actual" else kind
        print(f"   {gid} T{n} exp={exp} hdt={r['hdtRes']}/{r['hdtDmg']} lbEnd={r['lbEnd']['res']}/{r['lbEnd']['dmg']} "
              f"lbSettled={ls['res']}/{ls['dmg']} (dMe={ls['dMe']} dOpp={ls['dOpp']}) "
              f"lbNext={r['lbNext']['res']}/{r['lbNext']['dmg']} "
              f"rc={r['reconnects']} out={r['hasOutput']} oppCard={r['oppCard']} oppLb={r['oppLbFound']} "
              f"oppDead={r['oppDead']} hp={r['meHpStart']} lbOppCards={r['oppCardsOnLb']}")

    # --- C. coverage of the recommended pipeline over every captured combat
    cov = Counter()
    for r in all_rows:
        rc = r["recon"]
        cov[f"src={rc['src']}"] += 1
        if r["reconnects"]:
            cov[f"reconnect:src={rc['src']}"] += 1
            if r["hasEndSeq"] and r["lbSettled"] != r["lbNext"]:
                cov["reconnect:settled!=next"] += 1
    print(f"\n[C] recommended pipeline over {len(all_rows)} combats:", dict(sorted(cov.items())))
    for r in all_rows:
        if r["reconnects"]:
            print(f"   reconnect {r['game']} T{r['turn']} out={r['hasOutput']} recon={r['recon']} hdt={r['hdtRes']}/{r['hdtDmg']}")

    if args.csv:
        with open(args.csv, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["game", "turn", "hasOutput", "reconnects", "hdtRes", "hdtDmg",
                        "lbEndRes", "lbEndDmg", "lbNextRes", "lbNextDmg", "oppLbFound", "oppDead", "diedByLb"])
            for r in all_rows:
                w.writerow([r["game"], r["turn"], r["hasOutput"], r["reconnects"], r["hdtRes"], r["hdtDmg"],
                            r["lbEnd"]["res"], r["lbEnd"]["dmg"], r["lbNext"]["res"], r["lbNext"]["dmg"],
                            r["oppLbFound"], r["oppDead"], r["diedByLb"]])


if __name__ == "__main__":
    main()
