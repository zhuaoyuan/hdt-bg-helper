# -*- coding: utf-8 -*-
"""Combat result reconstruction (facts/combat-result-reconstruction.md §4)."""
from __future__ import annotations

from collections import Counter, defaultdict
from typing import Optional

from ._paths import ensure_spike_paths

ensure_spike_paths()
from diag_io import read_records  # noqa: E402
from power_replay import TagState, read_power  # noqa: E402


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
        return ("tie_or_ghost" if opp_dead else "tie"), 0
    return "conflict", None


def analyze_lb_and_hdt(game_dir: str) -> dict[int, dict]:
    """Return turn -> reconstruction signals (hdt / lb). Keys by combat turn when known."""
    recs = read_records(game_dir)
    power = read_power(game_dir)
    phases = [r for r in recs if r.get("type") == "combat_phase"]
    starts = [r["lineSeq"] for r in phases if r.get("value") is True]
    ends = [r["lineSeq"] for r in phases if r.get("value") is False]
    if not starts:
        return {}
    last_seq = power[-1][0] if power else 0
    combats = []
    for i, s in enumerate(starts):
        nxt = starts[i + 1] if i + 1 < len(starts) else last_seq + 1
        e = next((x for x in ends if s < x < nxt), None)
        combats.append({"idx": i + 1, "start": s, "end": e, "next": nxt})

    for c in combats:
        c["recs"] = [r for r in recs if c["start"] <= r.get("lineSeq", -1) < c["next"]]

    pos = {seq: i for i, (seq, _) in enumerate(power)}
    for c in combats:
        if c["end"] is None or c["end"] not in pos:
            c["settled"] = None
            continue
        i = pos[c["end"]]
        while i + 1 < len(power) and (
            power[i + 1][1].startswith("tag=") or power[i + 1][1].startswith("FULL_ENTITY - Updating")
        ):
            i += 1
        c["settled"] = power[i][0]

    want: dict[int, list] = defaultdict(list)
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
    final = st.leaderboard_heroes()
    for c in combats:
        for key in ("lb_start", "lb_next"):
            c.setdefault(key, final)
        c["reconnects"] = [x for x in st.create_game_lines if c["start"] < x < c["next"]]

    by_turn: dict[int, dict] = {}
    for c in combats:
        rs = c["recs"]
        start_snap = next(
            (r for r in rs if r.get("type") == "entities" and r.get("reason") == "combat_start"),
            None,
        )
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
        end_bb = next((r for r in reversed(same_turn) if r.get("reason") in ("combat_end", "game_end")), None)

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

        ghost = bool(opp_card and "KelThuzad" in opp_card)
        row = {
            "combat": c["idx"],
            "turn": turn,
            "reconnects": len(c["reconnects"]),
            "hasEndSeq": c["end"] is not None,
            "hdtRes": hdt_res,
            "hdtDmg": hdt_dmg,
            "lbSettled": out["settled"],
            "lbNext": out["next"],
            "ghost": ghost,
            "oppLbFound": opp_lb is not None,
        }
        row["recon"] = reconstruct_no_tuanzi(row)
        if turn is not None:
            by_turn[int(turn)] = row
    return by_turn


def reconstruct_no_tuanzi(r: dict) -> dict:
    if r["hdtRes"] is not None and not r["reconnects"]:
        return {"res": r["hdtRes"], "dmg": r["hdtDmg"], "src": "hdt"}
    lb = r["lbSettled"] if r["hasEndSeq"] else r["lbNext"]
    if r["ghost"]:
        if lb["dMe"] is not None and lb["dMe"] > 0:
            return {"res": "loss", "dmg": lb["dMe"], "src": "lb"}
        if lb["dMe"] == 0:
            return {"res": "win_or_tie", "dmg": None, "src": "lb"}
        return {"res": "unknown", "dmg": None, "src": "unknown"}
    if lb["res"] in ("unknown", "conflict"):
        return {"res": "unknown", "dmg": None, "src": "unknown"}
    return {"res": lb["res"].replace("_or_ghost", ""), "dmg": lb["dmg"], "src": "lb"}


def choose_result(tuanzi_turn: Optional[dict], recon_row: Optional[dict]) -> dict:
    """Preferred order: tuanzi actual -> hdt -> lb -> unknown (facts §4)."""
    if tuanzi_turn and tuanzi_turn.get("kind") == "actual" and tuanzi_turn.get("actualRes") in ("win", "tie", "loss"):
        return {
            "result": tuanzi_turn["actualRes"],
            "damage": tuanzi_turn.get("actualDmg"),
            "resultSource": "tuanzi",
            "died": bool(tuanzi_turn.get("died")),
        }
    if recon_row and recon_row.get("recon"):
        rc = recon_row["recon"]
        src = rc.get("src") or "unknown"
        if src == "none":
            src = "unknown"
        return {
            "result": rc.get("res"),
            "damage": rc.get("dmg"),
            "resultSource": src if src in ("hdt", "lb", "tuanzi", "unknown") else "unknown",
            "died": None,
            "reconnects": recon_row.get("reconnects"),
        }
    return {"result": None, "damage": None, "resultSource": "unknown", "died": None}
