# -*- coding: utf-8 -*-
"""Build the per-board X50 time-series table for one BB version.

Inputs (all local, gitignored):
  spikes/dummy-ladder/out-adaptive-all/curves.json   player-side X50 (v2)
  spikes/dummy-ladder/out-opp-188/curves.json        opponent-side X50 (v2)
  data/standard/turns.jsonl                          version / placement / survival

Outputs (gitignored):
  spikes/x50-trend/out/boards.csv
  spikes/x50-trend/out/games.csv
  spikes/x50-trend/out/dataset.json                  manifest with counts / filter
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PLAYER_CURVES = REPO / "spikes/dummy-ladder/out-adaptive-all/curves.json"
OPP_CURVES = REPO / "spikes/dummy-ladder/out-opp-188/curves.json"
TURNS = REPO / "data/standard/turns.jsonl"
OUT = REPO / "spikes/x50-trend/out"


def load_json(path: Path):
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def load_turns(path: Path) -> dict[str, dict]:
    """gameId -> {bbVersion, maxTurn, placement, date} from the standard layer."""
    games: dict[str, dict] = {}
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            gid = row["gameId"]
            meta = row.get("meta") or {}
            slot = games.setdefault(
                gid,
                {
                    "gameId": gid,
                    "bbVersion": meta.get("bbVersion"),
                    "maxTurn": 0,
                    "placement": None,
                    "date": gid.split("_")[0],
                    "rows": 0,
                },
            )
            slot["rows"] += 1
            slot["maxTurn"] = max(slot["maxTurn"], int(row.get("turn") or 0))
            if row.get("placement") is not None:
                slot["placement"] = int(row["placement"])
    return games


def index_curves(curves: list[dict]) -> dict[str, dict]:
    return {row["boardId"]: row for row in curves}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--version", default="1.88.6.0",
                    help="only keep games whose BB version equals this")
    ap.add_argument("--out", type=Path, default=OUT)
    args = ap.parse_args()

    games = load_turns(TURNS)
    cur_games = {g: v for g, v in games.items() if v["bbVersion"] == args.version}
    if not cur_games:
        raise SystemExit(f"no games with bbVersion={args.version}")
    gids = sorted(cur_games)
    seq = {gid: i for i, gid in enumerate(gids, start=1)}

    player = index_curves(load_json(PLAYER_CURVES))
    opp = index_curves(load_json(OPP_CURVES)) if OPP_CURVES.is_file() else {}
    if not opp:
        print(f"[warn] {OPP_CURVES} missing: building player-only table")

    rows: list[dict] = []
    seen_boards: set[str] = set()
    for curves, side in ((player, "me"), (opp, "opp")):
        for board_id, row in curves.items():
            gid = row.get("gameId")
            if gid not in cur_games:
                continue
            turn = int(row["turn"])
            x50 = row.get("x50")
            ci = row.get("ci") or [None, None]
            rec = {
                "boardId": board_id,
                "gameId": gid,
                "seq": seq[gid],
                "date": cur_games[gid]["date"],
                "turn": turn,
                "side": side,
                "status": row.get("status"),
                "interior": int(row.get("status") == "interior"),
                "x50": x50,
                "log2x50": (math.log2(x50) if x50 and x50 > 0 else None),
                "ciLow": ci[0],
                "ciHigh": ci[1],
                "seLog2": row.get("seLog2"),
                "nPoints": row.get("nPoints"),
                "sims": row.get("sims"),
            }
            key = f"{gid}|{turn}|{side}"
            if key in seen_boards:
                raise SystemExit(f"duplicate board key {key}")
            seen_boards.add(key)
            rows.append(rec)
    rows.sort(key=lambda r: (r["seq"], r["turn"], r["side"]))

    # per-game aggregates: mean log2 X50 over interior turns 5-12 (main window)
    by_game: dict[str, dict] = {}
    for r in rows:
        slot = by_game.setdefault(
            r["gameId"],
            {"gameId": r["gameId"], "seq": r["seq"], "date": r["date"],
             "placement": cur_games[r["gameId"]]["placement"],
             "maxTurn": cur_games[r["gameId"]]["maxTurn"]},
        )
        if r["interior"] and 5 <= r["turn"] <= 12 and r["log2x50"] is not None:
            slot.setdefault("_me", []).append(r["log2x50"] if r["side"] == "me" else None)
            slot.setdefault("_opp", []).append(r["log2x50"] if r["side"] == "opp" else None)
    game_rows: list[dict] = []
    for gid in gids:
        slot = by_game.get(gid, {"gameId": gid, "seq": seq[gid], "date": cur_games[gid]["date"],
                                 "placement": cur_games[gid]["placement"],
                                 "maxTurn": cur_games[gid]["maxTurn"]})
        me = [v for v in slot.get("_me", []) if v is not None]
        op = [v for v in slot.get("_opp", []) if v is not None]
        game_rows.append(
            {
                "gameId": gid,
                "seq": seq[gid],
                "date": cur_games[gid]["date"],
                "placement": cur_games[gid]["placement"],
                "maxTurn": cur_games[gid]["maxTurn"],
                "nMe": len(me),
                "nOpp": len(op),
                "meMeanLog2": (sum(me) / len(me)) if me else None,
                "oppMeanLog2": (sum(op) / len(op)) if op else None,
                "intensityMeanLog2": (sum(me + op) / len(me + op)) if me and op else None,
            }
        )

    def fmt(v):
        if v is None:
            return ""
        if isinstance(v, float):
            return f"{v:.6g}"
        return str(v)

    args.out.mkdir(parents=True, exist_ok=True)
    board_fields = list(rows[0].keys()) if rows else []
    with (args.out / "boards.csv").open("w", encoding="utf-8", newline="") as f:
        f.write(",".join(board_fields) + "\n")
        for r in rows:
            f.write(",".join(fmt(r[k]) for k in board_fields) + "\n")
    game_fields = list(game_rows[0].keys())
    with (args.out / "games.csv").open("w", encoding="utf-8", newline="") as f:
        f.write(",".join(game_fields) + "\n")
        for r in game_rows:
            f.write(",".join(fmt(r[k]) for k in game_fields) + "\n")

    manifest = {
        "version": args.version,
        "playerCurves": str(PLAYER_CURVES.relative_to(REPO)),
        "oppCurves": str(OPP_CURVES.relative_to(REPO)) if opp else None,
        "games": len(gids),
        "boards": len(rows),
        "boardsBySide": {s: sum(1 for r in rows if r["side"] == s) for s in ("me", "opp")},
        "interiorBySideTurn": {
            s: {str(t): sum(1 for r in rows if r["side"] == s and r["interior"] and r["turn"] == t)
                for t in range(1, 18)}
            for s in ("me", "opp")
        },
        "firstGame": gids[0],
        "lastGame": gids[-1],
        "dates": sorted({r["date"] for r in game_rows}),
    }
    (args.out / "dataset.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
