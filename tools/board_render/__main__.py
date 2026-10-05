# -*- coding: utf-8 -*-
"""CLI: extract / check / render single-side board strips from BgHelperDiag captures."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from tools.standard_layer._paths import REPO
from tools.standard_layer.combat import discover_games, iter_game_combats

from .art import ArtStore
from .board import compare_sides, side_from_combat, side_from_entities, side_from_input
from .cards import CardStore
from .chrome import ChromeStore
from .render import compose_sides, render_side, save_png


def default_roots() -> list[str]:
    return [
        str(REPO / "data" / "BgHelperDiag"),
        os.path.join(os.environ.get("APPDATA", ""), "HearthstoneDeckTracker", "BgHelperDiag"),
    ]


def resolve_game(roots: list[str], game_key: str) -> tuple[str, str]:
    games = discover_games(roots)
    if game_key in games:
        return game_key, games[game_key]
    matches = [
        (k, v)
        for k, v in games.items()
        if k == game_key or k.endswith("_" + game_key) or k.endswith(game_key)
    ]
    if len(matches) == 1:
        return matches[0]
    if not matches:
        raise SystemExit(f"game not found: {game_key} (searched {len(games)} under {roots})")
    suffix = [m for m in matches if m[0].endswith("_" + game_key)]
    if len(suffix) == 1:
        return suffix[0]
    raise SystemExit("ambiguous game id {!r}: {}".format(game_key, ", ".join(k for k, _ in matches)))


def run_check(game_dir: str, game_id: str, turn_filter: int | None) -> int:
    _meta, _records, combats = iter_game_combats(game_dir)
    mismatches = 0
    compared = 0
    skipped = 0
    details: list[dict] = []
    for c in combats:
        turn = c.get("turn")
        if turn_filter is not None and turn != turn_filter:
            continue
        for side in ("player", "opponent"):
            ents = side_from_entities(
                c.get("entities") or [], c.get("context") or {}, side  # type: ignore[arg-type]
            )
            bb = side_from_input(c.get("input"), side)  # type: ignore[arg-type]
            if not ents.minions and not bb.minions:
                skipped += 1
                continue
            if not ents.minions or not bb.minions:
                skipped += 1
                details.append(
                    {
                        "combat": c.get("combat"),
                        "turn": turn,
                        "side": side,
                        "reason": "one_source_empty",
                        "entitiesLen": len(ents.minions),
                        "inputLen": len(bb.minions),
                    }
                )
                continue
            compared += 1
            diff = compare_sides(ents, bb)
            if diff:
                mismatches += 1
                details.append(
                    {
                        "combat": c.get("combat"),
                        "turn": turn,
                        "side": side,
                        "reason": "tuple_mismatch",
                        **diff[0],
                    }
                )
    summary = {
        "gameId": game_id,
        "compared": compared,
        "mismatches": mismatches,
        "skipped": skipped,
        "ok": mismatches == 0 and compared > 0,
        "details": details,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if compared == 0:
        print("check: no comparable sides", file=sys.stderr)
        return 2
    if mismatches:
        print(f"check: FAIL {mismatches}/{compared} sides mismatch", file=sys.stderr)
        return 1
    print(f"check: OK {compared} sides match (entities vs input)", file=sys.stderr)
    return 0


def run_render(
    game_dir: str,
    game_id: str,
    *,
    side: str,
    turn_filter: int | None,
    out_dir: Path,
    offline: bool,
    chrome_dir: str | None,
    compose: bool,
) -> int:
    art = ArtStore(offline=offline)
    chrome = ChromeStore.open(chrome_dir)
    cards = CardStore.open(offline=offline)
    _meta, _records, combats = iter_game_combats(game_dir)

    game_out = out_dir / game_id
    game_out.mkdir(parents=True, exist_ok=True)

    written: list[dict] = []
    for c in combats:
        turn = c.get("turn")
        if turn_filter is not None and turn != turn_filter:
            continue
        combat_idx = int(c.get("combat") or 0)
        turn_num = int(turn) if turn is not None else 0
        sides = ("player", "opponent") if side == "both" else (side,)
        images = {}
        for s in sides:
            board = side_from_combat(c, s)  # type: ignore[arg-type]
            img = render_side(board, art=art, chrome=chrome, cards=cards)
            name = f"T{turn_num:02d}_c{combat_idx}_{s}.png"
            path = game_out / name
            save_png(img, path)
            images[s] = img
            written.append(
                {
                    "file": str(path),
                    "side": s,
                    "turn": turn,
                    "combat": combat_idx,
                    "minions": len(board.minions),
                    "source": board.source,
                }
            )
        if compose and side == "both" and "player" in images and "opponent" in images:
            stacked = compose_sides(images["player"], images["opponent"])
            cpath = game_out / f"T{turn_num:02d}_c{combat_idx}_both.png"
            save_png(stacked, cpath)
            written.append(
                {
                    "file": str(cpath),
                    "side": "both",
                    "turn": turn,
                    "combat": combat_idx,
                    "composed": True,
                }
            )

    summary = {
        "gameId": game_id,
        "out": str(game_out),
        "files": len(written),
        "missingPortraits": list(art.missing_ids),
        "missingPortraitCount": len(art.missing_ids),
        "chromeSource": chrome.source,
        "chromeDir": str(chrome.chrome_dir) if chrome.chrome_dir else None,
        "cardsSource": cards.source,
        "offline": offline,
        "written": written,
    }
    summary_path = game_out / "summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: summary[k] for k in summary if k != "written"}, ensure_ascii=False, indent=2))
    print(f"wrote {len(written)} png(s) + {summary_path}", file=sys.stderr)
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=(
            "P3-T6: render single-side battlegrounds board strips. "
            "HDT Minion chrome PNGs are read locally only (personal use; never committed)."
        )
    )
    ap.add_argument("--root", action="append", default=None, help="BgHelperDiag root (repeatable)")
    ap.add_argument("--game", default=None, help="Game id or short suffix (e.g. ed11e0)")
    ap.add_argument("--side", choices=("player", "opponent", "both"), default="both")
    ap.add_argument("--turn", type=int, default=None, help="Only this turn number")
    ap.add_argument("--out", default=str(REPO / "data" / "boards"), help="Output directory under data/")
    ap.add_argument("--offline", action="store_true", help="Do not download portraits / cards.json")
    ap.add_argument(
        "--chrome-dir",
        default=None,
        help="Directory of HDT Resources/Minion PNGs (personal use only; not for redistribution)",
    )
    ap.add_argument("--check", action="store_true", help="Compare entities vs BB Input check tuples")
    ap.add_argument(
        "--compose",
        action="store_true",
        help="When --side both, also write a stacked opponent/player PNG (convenience)",
    )
    args = ap.parse_args(argv)

    roots = args.root or default_roots()

    if args.check:
        if not args.game:
            ap.error("--check requires --game")
        gid, gdir = resolve_game(roots, args.game)
        return run_check(gdir, gid, args.turn)

    if not args.game:
        ap.error("--game is required (or use --check)")

    gid, gdir = resolve_game(roots, args.game)
    return run_render(
        gdir,
        gid,
        side=args.side,
        turn_filter=args.turn,
        out_dir=Path(args.out),
        offline=args.offline,
        chrome_dir=args.chrome_dir,
        compose=args.compose,
    )


if __name__ == "__main__":
    raise SystemExit(main())
