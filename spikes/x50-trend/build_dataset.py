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
    ap.add_argument("--version", default=None,
                    help="(legacy) only keep games whose BB version equals this")
    ap.add_argument("--versions", default=None,
                    help="comma list of BB versions to keep, e.g. 1.85.0.0,1.88.6.0")
    ap.add_argument("--pool", default=None,
                    help="sim pool name; expands to its member versions (overrides --versions)")
    ap.add_argument("--player-curves", type=Path, default=PLAYER_CURVES)
    ap.add_argument("--opp-curves", type=Path, default=OPP_CURVES)
    ap.add_argument("--out", type=Path, default=OUT)
    args = ap.parse_args()

    if args.pool:
        import sys as _sys
        _sys.path.insert(0, str(REPO / "tools"))
        from strength.sim_pools import member_versions
        versions = set(member_versions(args.pool))
        label = f"pool {args.pool}"
    elif args.versions:
        versions = {v.strip() for v in args.versions.split(",") if v.strip()}
        label = "versions " + ",".join(sorted(versions))
    elif args.version:
        versions = {args.version}
        label = f"version {args.version}"
    else:
        versions = {"1.88.6.0"}
        label = "version 1.88.6.0"
    if not versions:
        raise SystemExit("empty version filter")
    args.out = Path(args.out).resolve()
    args.player_curves = Path(args.player_curves).resolve()
    args.opp_curves = Path(args.opp_curves).resolve()

    games = load_turns(TURNS)
    cur_games = {g: v for g, v in games.items() if v["bbVersion"] in versions}
    if not cur_games:
        raise SystemExit(f"no games with {label}")
    gids = sorted(cur_games)
    seq = {gid: i for i, gid in enumerate(gids, start=1)}
    version_of = {gid: cur_games[gid]["bbVersion"] for gid in gids}
    # versions ordered by first appearance in time (for figures / interpretation)
    ordered_versions = []
    for gid in gids:
        if version_of[gid] not in ordered_versions:
            ordered_versions.append(version_of[gid])

    player = index_curves(load_json(args.player_curves))
    opp = index_curves(load_json(args.opp_curves)) if args.opp_curves.is_file() else {}
    if not opp:
        print(f"[warn] {args.opp_curves} missing: building player-only table")

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
                "version": version_of[gid],
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
            {"gameId": r["gameId"], "version": r["version"], "seq": r["seq"], "date": r["date"],
             "placement": cur_games[r["gameId"]]["placement"],
             "maxTurn": cur_games[r["gameId"]]["maxTurn"]},
        )
        if r["interior"] and 5 <= r["turn"] <= 12 and r["log2x50"] is not None:
            slot.setdefault("_me", []).append(r["log2x50"] if r["side"] == "me" else None)
            slot.setdefault("_opp", []).append(r["log2x50"] if r["side"] == "opp" else None)
    game_rows: list[dict] = []
    for gid in gids:
        slot = by_game.get(gid, {"gameId": gid, "version": version_of[gid], "seq": seq[gid],
                                 "date": cur_games[gid]["date"],
                                 "placement": cur_games[gid]["placement"],
                                 "maxTurn": cur_games[gid]["maxTurn"]})
        me = [v for v in slot.get("_me", []) if v is not None]
        op = [v for v in slot.get("_opp", []) if v is not None]
        game_rows.append(
            {
                "gameId": gid,
                "version": version_of[gid],
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

    version_boundaries = []
    for i in range(1, len(ordered_versions)):
        v = ordered_versions[i]
        first_seq = next(s for s in range(1, len(gids) + 1) if version_of[gids[s - 1]] == v)
        version_boundaries.append({
            "from": ordered_versions[i - 1], "to": v, "seq": first_seq,
            "prevLastGame": gids[first_seq - 2] if first_seq > 1 else None,
            "nextFirstGame": gids[first_seq - 1],
        })
    manifest = {
        "filter": label,
        "versions": ordered_versions,
        "gamesByVersion": {v: sum(1 for g in gids if version_of[g] == v)
                           for v in ordered_versions},
        "boardsByVersionSide": {
            v: {s: sum(1 for r in rows if r["side"] == s and r["version"] == v)
                for s in ("me", "opp")}
            for v in ordered_versions
        },
        "interiorBySideTurn": {
            s: {str(t): sum(1 for r in rows if r["side"] == s and r["interior"] and r["turn"] == t)
                for t in range(1, 18)}
            for s in ("me", "opp")
        },
        "interiorByVersionSideTurn": {
            v: {
                s: {str(t): sum(1 for r in rows if r["version"] == v and r["side"] == s
                                and r["interior"] and r["turn"] == t)
                    for t in range(1, 18)}
                for s in ("me", "opp")
            }
            for v in ordered_versions
        },
        "versionBoundaries": version_boundaries,
        "playerCurves": str(args.player_curves.relative_to(REPO)),
        "oppCurves": str(args.opp_curves.relative_to(REPO)) if opp else None,
        "games": len(gids),
        "boards": len(rows),
        "boardsBySide": {s: sum(1 for r in rows if r["side"] == s) for s in ("me", "opp")},
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
