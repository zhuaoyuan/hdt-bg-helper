# -*- coding: utf-8 -*-
"""Compute Opponent-side percentiles for one game (reuse strength cache)."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Callable

_REPO = Path(__file__).resolve().parents[2]
_TOOLS = _REPO / "tools"
if str(_TOOLS) not in sys.path:
    sys.path.insert(0, str(_TOOLS))

from tools.strength.batch import load_bb_map  # noqa: E402
from tools.strength.cache import StrengthCache  # noqa: E402
from tools.strength.config import (  # noqa: E402
    BOOTSTRAP_B,
    G_MIN,
    ITERATIONS,
    L1_ENABLED,
    MAX_DURATION_MS,
    PANEL_GAMES,
    W_RELAX,
)
from tools.strength.engine import (  # noqa: E402
    build_score_map,
    ensure_pairs,
    evaluate_candidate,
    strength_out_path,
)
from tools.strength.panel import build_panel  # noqa: E402
from tools.strength.pool import bucket_boards, collect_boards, load_turns  # noqa: E402
from tools.strength._paths import DEFAULT_CACHE, DEFAULT_EXE, DEFAULT_TURNS, default_diag_roots  # noqa: E402


def opp_cache_path(bb_version: str) -> Path:
    return strength_out_path(bb_version).with_name("strength_opp.jsonl")


def load_opp_cache(path: Path) -> dict[str, dict]:
    out: dict[str, dict] = {}
    if not path.is_file():
        return out
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            bid = r.get("boardId")
            if bid:
                out[str(bid)] = r
    return out


def save_opp_cache(path: Path, by_id: dict[str, dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = sorted(
        by_id.values(),
        key=lambda r: (str(r.get("gameId") or ""), int(r.get("turn") or 0)),
    )
    with path.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def _game_matches(board_gid: str, game_id: str) -> bool:
    return board_gid == game_id or board_gid.endswith("_" + game_id) or board_gid.endswith(game_id)


def ensure_opponent_strength(
    game_id: str,
    *,
    bb_version: str,
    turns: list[int],
    roots: list[str] | None = None,
    turns_jsonl: Path | None = None,
    cache_path: Path | None = None,
    progress: Callable[[str], None] | None = None,
) -> dict[int, dict]:
    """Return turn -> Opponent strength row for one game; cache to strength_opp.jsonl."""
    log = progress or (lambda m: print(m, flush=True))
    opp_path = opp_cache_path(bb_version)
    cached = load_opp_cache(opp_path)

    hit: dict[int, dict] = {}
    missing_turns: list[int] = []
    for t in turns:
        bid = f"{game_id}|t{t}|Opponent"
        row = cached.get(bid)
        if row is None:
            # fuzzy: any cached row for this turn+game
            for r in cached.values():
                if (
                    int(r.get("turn") or -1) == t
                    and _game_matches(str(r.get("gameId") or ""), game_id)
                    and str(r.get("side")) == "Opponent"
                ):
                    row = r
                    break
        if row is not None:
            hit[t] = row
        else:
            missing_turns.append(t)
    if not missing_turns:
        return hit

    log(f"computing Opponent percentiles for {game_id} turns {missing_turns}…")
    turns_by = load_turns(turns_jsonl or DEFAULT_TURNS)
    max_turn = max(max(turns), 12)
    boards = collect_boards(
        roots or default_diag_roots(),
        bb_version,
        turns_by,
        max_turn=max_turn,
        include_opponent=True,
    )

    bb_map = load_bb_map()
    bb_dir = bb_map.get(bb_version)
    if not bb_dir or not os.path.isfile(os.path.join(bb_dir, "BobsBuddy.dll")):
        raise FileNotFoundError(f"no BobsBuddy.dll for {bb_version}: {bb_dir}")

    with StrengthCache(cache_path or DEFAULT_CACHE) as cache:
        ensure_pairs(
            boards,
            cache,
            bb_version=bb_version,
            exe=Path(DEFAULT_EXE),
            bb_dir=bb_dir,
            k=PANEL_GAMES,
            target_sims=ITERATIONS,
            iterations=ITERATIONS,
            max_duration=MAX_DURATION_MS,
            threads=None,
            dry_run=False,
            fill_l1=L1_ENABLED,
            progress=log,
        )
        buckets = bucket_boards(boards)
        by_turn = {t: bl for (v, t), bl in buckets.items() if v == bb_version}
        panels: dict[int, set[str]] = {}
        for t, bl in by_turn.items():
            panels[t] = set(build_panel(bl, bb_version=bb_version, turn=t, k=PANEL_GAMES).board_ids)
        thin = any(len({b.game_id for b in bl}) - 1 < G_MIN for bl in by_turn.values())
        slack = 1 if (thin and L1_ENABLED) else 0
        scores, _missing = build_score_map(
            boards,
            panels,
            cache,
            bb_version=bb_version,
            target_sims=ITERATIONS,
            turn_slack=slack,
        )
        opps = []
        for t in missing_turns:
            for b in by_turn.get(t, []):
                if b.side == "Opponent" and _game_matches(b.game_id, game_id):
                    opps.append(b)
        # Prefer exact game id
        exact = [b for b in opps if b.game_id == game_id]
        if exact:
            opps = exact
        # One opponent board per turn
        by_t: dict[int, object] = {}
        for b in opps:
            by_t.setdefault(b.turn, b)
        log(f"  evaluating {len(by_t)} Opponent candidates (B={BOOTSTRAP_B})…")
        for t, cand in sorted(by_t.items()):
            row = evaluate_candidate(
                cand,  # type: ignore[arg-type]
                by_turn=by_turn,
                panels=panels,
                scores=scores,
                g_min=G_MIN,
                l1_enabled=L1_ENABLED,
                w_relax=W_RELAX,
                bootstrap_b=BOOTSTRAP_B,
                player_only=False,
                panel_games_k=PANEL_GAMES,
                iterations=ITERATIONS,
            )
            cached[cand.board_id] = row  # type: ignore[attr-defined]
            hit[int(t)] = row

    save_opp_cache(opp_path, cached)
    log(f"wrote Opponent strength cache {opp_path}")
    return hit
