# -*- coding: utf-8 -*-
"""CLI: import BgHelperDiag (+ Tuanzi) into per-turn standard layer JSONL + quality report."""
from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import os
import sys
from pathlib import Path

from . import __version__ as STANDARD_LAYER_VERSION
from .combat import discover_games, iter_game_combats, rules_block, session_start_reason
from .crosscheck import crosscheck_turn
from .gaps import detect_gaps
from .placement import final_local_place
from .report import build_report, format_report
from .result import analyze_lb_and_hdt, choose_result
from .status import classify_status
from .tuanzi import load_tuanzi_dir, pair_games, turn_from_pair
from ._paths import REPO


def build_row(
    game_id: str,
    game_dir: str,
    meta: dict,
    session_reason: str | None,
    combat: dict,
    tuanzi_pair: dict | None,
    recon_by_turn: dict[int, dict],
    final_place: int | None,
    *,
    do_replay: bool,
    replay_cache: dict,
) -> dict:
    turn = combat.get("turn")
    tz_turn = turn_from_pair(tuanzi_pair, turn)
    recon = recon_by_turn.get(int(turn)) if turn is not None else None
    chosen = choose_result(tz_turn, recon)
    tz_place = tuanzi_pair["game"].get("place") if tuanzi_pair else None
    tz_died = bool(
        tuanzi_pair
        and any(bool(t.get("died")) for t in (tuanzi_pair["game"].get("turns") or {}).values())
    )
    # A tuanzi record that says "#1" but also says "I was carried out" is
    # internally inconsistent; do not propagate that place into the label.
    tz_place_valid = not (tz_place == 1 and tz_died)
    if tz_place is not None and tz_place_valid:
        placement = tz_place
        placement_source = "tuanzi"
    elif final_place is not None:
        placement = final_place
        placement_source = "raw_lb"
    else:
        placement = None
        placement_source = None

    gap_flags = detect_gaps(combat.get("input"), combat.get("entities"))
    status, reasons = classify_status(
        meta=meta,
        session_reason=session_reason,
        combat=combat,
        tuanzi_turn=tz_turn,
        gap_flags=gap_flags,
    )
    cross = crosscheck_turn(combat, tz_turn)

    rules = rules_block(combat, meta)

    row = {
        "gameId": game_id,
        "turn": turn,
        "combat": combat.get("combat"),
        "myHero": combat.get("myHero"),
        "oppHero": combat.get("oppHero"),
        "myHeroCard": combat.get("myHeroCard"),
        "oppHeroCard": combat.get("oppHeroCard"),
        "inputRef": combat.get("inputRef"),
        "output": combat.get("outputSummary"),
        "result": chosen.get("result"),
        "damage": chosen.get("damage"),
        "placement": placement,
        "placementRaw": final_place,
        "placementTuanzi": tz_place,
        "placementTuanziValid": tz_place_valid,
        "placementSource": placement_source,
        "rules": rules,
        "resultSource": chosen.get("resultSource"),
        "status": status,
        "statusReasons": reasons,
        "gapFlags": gap_flags,
        "hasOutput": combat.get("hasOutput"),
        "hasInput": combat.get("hasInput"),
        "tuanziKind": (tz_turn or {}).get("kind"),
        "tuanziCross": cross,
        "sessionStartReason": session_reason,
        "meta": {
            "pluginVersion": meta.get("pluginVersion"),
            "bbVersion": (meta.get("bobsBuddy") or {}).get("fileVersion")
            or (meta.get("bobsBuddy") or {}).get("version"),
            "hdtVersion": (meta.get("hdt") or {}).get("fileVersion") or (meta.get("hdt") or {}).get("version"),
            "hearthDbVersion": (meta.get("hearthDb") or {}).get("fileVersion")
            or (meta.get("hearthDb") or {}).get("version"),
            "hearthstoneBuild": meta.get("hearthstoneBuild"),
            "duos": bool(meta.get("isBattlegroundsDuosMatch")),
            "schemaVersion": meta.get("schemaVersion"),
        },
    }

    if do_replay and combat.get("input") and combat.get("outputSummary"):
        from .replay import replay_one

        bb_ver = row["meta"]["bbVersion"]
        cache_key = (game_id, turn, combat.get("inputRef", {}).get("lineSeq"))
        if cache_key in replay_cache:
            row["replayDelta"] = replay_cache[cache_key]
        else:
            rd = replay_one(combat["input"], combat["outputSummary"], str(bb_ver))
            replay_cache[cache_key] = rd
            row["replayDelta"] = rd

    return row


def import_all(
    roots: list[str],
    tuanzi_dir: str | None,
    *,
    do_replay: bool = False,
    game_filter: set[str] | None = None,
) -> tuple[list[dict], dict, dict[str, dict], dict]:
    games = discover_games(roots)
    if game_filter:
        games = {k: v for k, v in games.items() if k in game_filter or k.split("_")[-1] in game_filter}

    # First pass: combat views for pairing
    combat_views: dict[str, list[dict]] = {}
    meta_by_game: dict[str, dict] = {}
    session_by_game: dict[str, str | None] = {}
    full_combats: dict[str, list[dict]] = {}
    dirs: dict[str, str] = {}
    final_place_by_game: dict[str, int | None] = {}

    for gid, gdir in sorted(games.items()):
        try:
            meta, records, combats = iter_game_combats(gdir)
        except Exception as ex:  # noqa: BLE001 — keep going on odd captures
            print(f"[skip] {gid}: {type(ex).__name__}: {ex}", file=sys.stderr)
            continue
        meta_by_game[gid] = meta
        session_by_game[gid] = session_start_reason(records)
        final_place_by_game[gid] = final_local_place(records)
        full_combats[gid] = combats
        dirs[gid] = gdir
        combat_views[gid] = [
            {"turn": c.get("turn"), "myHero": c.get("myHero"), "oppHero": c.get("oppHero")}
            for c in combats
        ]

    tuanzi_by_day = load_tuanzi_dir(tuanzi_dir) if tuanzi_dir else {}
    pairs = pair_games(combat_views, tuanzi_by_day) if tuanzi_by_day else {}

    rows: list[dict] = []
    replay_cache: dict = {}
    for gid, combats in sorted(full_combats.items()):
        gdir = dirs[gid]
        meta = meta_by_game[gid]
        session_reason = session_by_game[gid]
        try:
            recon = analyze_lb_and_hdt(gdir)
        except Exception as ex:  # noqa: BLE001
            print(f"[warn] result reconstruct {gid}: {type(ex).__name__}: {ex}", file=sys.stderr)
            recon = {}
        pair = pairs.get(gid)
        final_place = final_place_by_game.get(gid)
        for c in combats:
            rows.append(
                build_row(
                    gid,
                    gdir,
                    meta,
                    session_reason,
                    c,
                    pair,
                    recon,
                    final_place,
                    do_replay=do_replay,
                    replay_cache=replay_cache,
                )
            )

    report = build_report(rows, pairs=pairs, meta_by_game=meta_by_game)
    return rows, report, meta_by_game, pairs


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def write_dataset_manifest(
    out_dir: Path,
    *,
    roots: list[str],
    turns_path: Path,
    report_path: Path,
    report_txt: Path,
    report: dict,
) -> Path:
    """Write the canonical-dataset manifest next to turns/quality report.

    This does not move or delete the historical ``data/standard_*`` outputs; it
    only records which files/versions the current importer considers canonical.
    """
    dataset = {
        "datasetVersion": 1,
        "standardLayerVersion": STANDARD_LAYER_VERSION,
        "generatedAt": _dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "canonical": True,
        "roots": roots,
        "files": {
            "turns": {
                "path": turns_path.name,
                "sha256": _sha256(turns_path),
                "bytes": turns_path.stat().st_size,
            },
            "qualityReport": {
                "path": report_path.name,
                "sha256": _sha256(report_path),
                "bytes": report_path.stat().st_size,
            },
            "qualityReportText": {
                "path": report_txt.name,
                "sha256": _sha256(report_txt),
                "bytes": report_txt.stat().st_size,
            },
        },
        "counts": {
            "games": report.get("gamesCount"),
            "turns": report.get("turnCount"),
            "status": report.get("statusCounts"),
        },
        "placement": report.get("placement"),
        "rules": report.get("rules"),
        "versions": report.get("versions"),
    }
    path = out_dir / "dataset.json"
    path.write_text(json.dumps(dataset, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="P2-T3: import diag captures into standard-layer turns")
    ap.add_argument(
        "--root",
        action="append",
        default=None,
        help="BgHelperDiag root (repeatable). Default: data/BgHelperDiag + %%APPDATA%%/.../BgHelperDiag",
    )
    ap.add_argument("--tuanzi", default=str(REPO / "data" / "tuanzi"), help="Tuanzi text directory")
    ap.add_argument("--out", default=str(REPO / "data" / "standard"), help="Output directory")
    ap.add_argument("--replay", action="store_true", help="Run same-version BB round-trip for replayDelta")
    ap.add_argument("--game", action="append", default=None, help="Only these game ids (or short suffixes)")
    ap.add_argument("--report-only", action="store_true", help="Print report, still writes files unless --stdout")
    ap.add_argument("--stdout", action="store_true", help="Also print JSONL rows to stdout")
    args = ap.parse_args(argv)

    roots = args.root or [
        str(REPO / "data" / "BgHelperDiag"),
        os.path.join(os.environ.get("APPDATA", ""), "HearthstoneDeckTracker", "BgHelperDiag"),
    ]
    game_filter = set(args.game) if args.game else None

    rows, report, _meta, _pairs = import_all(
        roots,
        args.tuanzi if os.path.isdir(args.tuanzi) else None,
        do_replay=args.replay,
        game_filter=game_filter,
    )

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    turns_path = out_dir / "turns.jsonl"
    report_path = out_dir / "quality_report.json"
    report_txt = out_dir / "quality_report.txt"

    with turns_path.open("w", encoding="utf-8") as f:
        for r in rows:
            # Drop bulky fields never needed in the table file
            slim = {k: v for k, v in r.items() if k not in ("_raw",)}
            f.write(json.dumps(slim, ensure_ascii=False) + "\n")
            if args.stdout:
                print(json.dumps(slim, ensure_ascii=False))

    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    text = format_report(report)
    report_txt.write_text(text + "\n", encoding="utf-8")
    dataset_path = write_dataset_manifest(
        out_dir,
        roots=roots,
        turns_path=turns_path,
        report_path=report_path,
        report_txt=report_txt,
        report=report,
    )
    print(text)
    print(f"\nwrote {turns_path} ({len(rows)} rows)")
    print(f"wrote {report_path}")
    print(f"wrote {report_txt}")
    print(f"wrote {dataset_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
