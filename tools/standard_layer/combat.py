# -*- coding: utf-8 -*-
"""Discover games, segment combats, pick post-2022=0 hdt_bb, extract Input/Output."""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Iterator, Optional

from ._paths import ensure_spike_paths

ensure_spike_paths()
from diag_io import read_records, records_path  # noqa: E402

# Same repairs as spikes/replay-harness/tools/roundtrip.py (0.1.0 anonymizer collisions).
KEY_REPAIRS = [
    (re.compile(r"^ControlledByplayer_[0-9a-f]{8}$", re.I), "ControlledByPlayer"),
    (re.compile(r"^Megaplayer_[0-9a-f]{8}fury$", re.I), "MegaWindfury"),
    (re.compile(r"^player_[0-9a-f]{8}fury$", re.I), "Windfury"),
    (re.compile(r"^DuosInputplayer_[0-9a-f]{8}Teammate$", re.I), "DuosInputPlayerTeammate"),
    (re.compile(r"^DuosInputplayer_[0-9a-f]{8}$", re.I), "DuosInputPlayer"),
    (re.compile(r"^player_[0-9a-f]{8}Teammate$", re.I), "PlayerTeammate"),
    (re.compile(r"^player_[0-9a-f]{8}$", re.I), "Player"),
]
SIM_PLAYER_TYPE_RE = re.compile(r"^BobsBuddy\.Simulation\.player_[0-9a-f]{8}$", re.I)
ANON_PLAYER_KEY = re.compile(r"^player_[0-9a-f]{8}$", re.I)


def fix_anon_key(key: str) -> str:
    for pat, repl in KEY_REPAIRS:
        if pat.match(key):
            return repl
    return key


def fix_anon(obj: Any) -> Any:
    if isinstance(obj, list):
        return [fix_anon(x) for x in obj]
    if not isinstance(obj, dict):
        return obj
    fixed: dict = {}
    for k, v in obj.items():
        nk = fix_anon_key(k)
        nv = fix_anon(v)
        if k == "$type" and isinstance(nv, str) and SIM_PLAYER_TYPE_RE.match(nv):
            nv = "BobsBuddy.Simulation.Player"
        if nk in fixed and fixed[nk] is not None:
            continue
        fixed[nk] = nv
    return fixed


def load_meta(game_dir: str | Path) -> dict:
    with open(os.path.join(str(game_dir), "meta.json"), encoding="utf-8") as f:
        return json.load(f)


def discover_games(roots: list[str]) -> dict[str, str]:
    """gameId -> absolute path; later roots win on id collision."""
    out: dict[str, str] = {}
    for root in roots:
        if not root or not os.path.isdir(root):
            continue
        for name in sorted(os.listdir(root)):
            d = os.path.join(root, name)
            if not os.path.isdir(d):
                continue
            if not os.path.isfile(os.path.join(d, "meta.json")):
                continue
            if not records_path(d):
                continue
            out[name] = d
    return out


def segment_combats(records: list[dict]) -> list[dict]:
    """Each segment starts at combat_phase=true and includes following shopping until next true."""
    combats: list[dict] = []
    current: dict | None = None
    for r in records:
        t = r.get("type")
        if t == "combat_phase" and r.get("value") is True:
            current = {
                "start": r,
                "end": None,
                "records": [],
                "startSeq": r.get("lineSeq"),
            }
            combats.append(current)
            continue
        if current is not None:
            current["records"].append(r)
            if t == "combat_phase" and r.get("value") is False:
                current["end"] = r
                current["endSeq"] = r.get("lineSeq")
    return combats


def _tag_is_2022_zero(r: dict) -> bool:
    return r.get("type") == "combat_tag" and r.get("tag") in (2022, "2022") and r.get("value") in (0, "0")


def pick_combat_bb(segment: dict) -> tuple[Optional[dict], dict]:
    """Pick Combat hdt_bb after 2022=0 (prefer highest reRunCount). Returns (rec, meta)."""
    recs = segment["records"]
    seq_2022 = None
    for r in recs:
        if _tag_is_2022_zero(r):
            seq_2022 = r.get("lineSeq")
            break

    cands = [
        r
        for r in recs
        if r.get("type") == "hdt_bb"
        and r.get("state") == "Combat"
        and r.get("hasInput")
        and r.get("hasOutput")
        and isinstance(r.get("invoker"), dict)
    ]
    after = [r for r in cands if seq_2022 is None or (r.get("lineSeq") or 0) >= seq_2022]
    pool = after or cands
    meta = {
        "tag2022Seq": seq_2022,
        "candidates": len(cands),
        "after2022": len(after),
        "usedAfter2022": bool(after) or seq_2022 is None,
    }
    if not pool:
        return None, meta
    pool.sort(key=lambda r: (r.get("reRunCount") or 0, r.get("lineSeq") or 0))
    return pool[-1], meta


def find_by_type(obj: Any, suffixes: tuple[str, ...], depth: int = 0) -> Any:
    if not isinstance(obj, dict) or depth > 12:
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


def extract_input(rec: dict) -> Optional[dict]:
    inv = rec.get("invoker") or {}
    inp = inv.get("_input")
    if isinstance(inp, dict) and "Input" in str(inp.get("$type") or ""):
        return fix_anon(inp)
    # Some dumps nest Input under other keys
    found = find_by_type(inv, (".Input",))
    if isinstance(found, dict):
        return fix_anon(found)
    return None


def extract_output(rec: dict) -> Optional[dict]:
    inv = rec.get("invoker") or {}
    out = inv.get("Output")
    if isinstance(out, dict) and out.get("winRate") is not None:
        return out
    return None


def output_summary(out: Optional[dict]) -> Optional[dict]:
    if not isinstance(out, dict):
        return None
    return {
        "winRate": out.get("winRate"),
        "tieRate": out.get("tieRate"),
        "lossRate": out.get("lossRate"),
        "myDeathRate": out.get("myDeathRate"),
        "theirDeathRate": out.get("theirDeathRate"),
        "simulationCount": out.get("simulationCount"),
        "avDamage": out.get("avDamage"),
        "medianDamage": out.get("medianDamage"),
        "friendlyHealth": out.get("friendlyHealth"),
        "opponentHealth": out.get("opponentHealth"),
    }


def get_player_obj(inp: dict, which: str) -> Optional[dict]:
    if which in inp and isinstance(inp[which], dict):
        return inp[which]
    if which == "Player":
        for k, v in inp.items():
            if isinstance(v, dict) and ANON_PLAYER_KEY.fullmatch(k or ""):
                if "Side" in v:
                    return v
    return None


def list_items(node: Any) -> list:
    if isinstance(node, list):
        return node
    if isinstance(node, dict):
        return node.get("items") or []
    return []


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
        "baseAtk": data.get("BaseAttack"),
        "baseHealth": data.get("BaseHealth"),
        "golden": bool(data.get("Golden")),
        "tier": m.get("tier"),
    }


def board_from_input(inp: Optional[dict]) -> tuple[list[dict], list[dict]]:
    if not inp:
        return [], []
    player = get_player_obj(inp, "Player")
    opponent = get_player_obj(inp, "Opponent")
    p = [minion_from_bb(m) for m in list_items((player or {}).get("Side")) if isinstance(m, dict)]
    o = [minion_from_bb(m) for m in list_items((opponent or {}).get("Side")) if isinstance(m, dict)]
    return p, o


def start_context(segment: dict) -> dict:
    start = next(
        (r for r in segment["records"] if r.get("type") == "entities" and r.get("reason") == "combat_start"),
        None,
    )
    if not start:
        return {}
    return {
        "context": start.get("context") or {},
        "entities": start.get("entities") or [],
        "entityCount": start.get("entityCount"),
        "lineSeq": start.get("lineSeq"),
    }


def entity_by_id(entities: list[dict]) -> dict[int, dict]:
    out = {}
    for e in entities or []:
        eid = e.get("id")
        if eid is not None:
            out[int(eid)] = e
    return out


def hero_card(ctx_side: dict | None, entities: list[dict]) -> Optional[str]:
    if not ctx_side:
        return None
    hid = ctx_side.get("hero")
    if hid is None:
        return None
    e = entity_by_id(entities).get(int(hid))
    return e.get("cardId") if e else None


def turn_of(segment: dict, bb: Optional[dict]) -> Optional[int]:
    ctx = start_context(segment)
    t = (ctx.get("context") or {}).get("turn")
    if t is not None:
        return int(t)
    if bb and isinstance(bb.get("key"), int):
        return bb["key"]
    if bb and isinstance(bb.get("invoker"), dict):
        tt = bb["invoker"].get("_turn")
        if isinstance(tt, int):
            return tt
    return None


def hero_names(bb: Optional[dict]) -> tuple[Optional[str], Optional[str]]:
    if not bb or not isinstance(bb.get("invoker"), dict):
        return None, None
    inv = bb["invoker"]
    return inv.get("_playerHeroName"), inv.get("_opponentHeroName")


def session_start_reason(records: list[dict]) -> Optional[str]:
    for r in records:
        if r.get("type") == "event" and r.get("name") == "session_start":
            return r.get("reason")
    return None


def analyze_combat(segment: dict, combat_idx: int) -> dict:
    bb, pick_meta = pick_combat_bb(segment)
    ctx_info = start_context(segment)
    ctx = ctx_info.get("context") or {}
    entities = ctx_info.get("entities") or []
    inp = extract_input(bb) if bb else None
    out = extract_output(bb) if bb else None
    p_board, o_board = board_from_input(inp)
    my_name, opp_name = hero_names(bb)
    turn = turn_of(segment, bb)
    return {
        "combat": combat_idx,
        "turn": turn,
        "myHero": my_name,
        "oppHero": opp_name,
        "myHeroCard": hero_card(ctx.get("player"), entities),
        "oppHeroCard": hero_card(ctx.get("opponent"), entities),
        "playerMinions": p_board,
        "oppMinions": o_board,
        "entities": entities,
        # context.<side>.board ids for entities@combat_start (P3-T6 board_render).
        "context": ctx,
        "hasStartSnap": bool(ctx_info),
        "hasOutput": out is not None,
        "hasInput": inp is not None,
        "bb": bb,
        "input": inp,
        "output": out,
        "outputSummary": output_summary(out),
        "inputRef": {
            "lineSeq": bb.get("lineSeq") if bb else None,
            "reason": bb.get("reason") if bb else None,
            "reRunCount": bb.get("reRunCount") if bb else None,
            "state": bb.get("state") if bb else None,
            "key": bb.get("key") if bb else None,
        },
        "pickMeta": pick_meta,
        "startSeq": segment.get("startSeq"),
        "endSeq": segment.get("endSeq"),
        "nextSeq": None,  # filled by caller
    }


def iter_game_combats(game_dir: str) -> tuple[dict, list[dict], list[dict]]:
    meta = load_meta(game_dir)
    records = read_records(game_dir)
    segments = segment_combats(records)
    combats = []
    for i, seg in enumerate(segments):
        row = analyze_combat(seg, i + 1)
        if i + 1 < len(segments):
            row["nextSeq"] = segments[i + 1].get("startSeq")
        combats.append(row)
    return meta, records, combats
