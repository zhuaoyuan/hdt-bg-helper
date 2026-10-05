# -*- coding: utf-8 -*-
"""CLI: build offline static HTML review pages from turns + strength + boards."""
from __future__ import annotations

import argparse
import sys
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from tools.board_render.__main__ import default_roots as diag_roots, resolve_game
from tools.standard_layer._paths import REPO

from .boards import (
    collect_board_paths,
    copy_boards_into,
    render_boards_if_needed,
    tiers_from_combats,
)
from .page import write_review
from .join import (
    build_game_review,
    filter_turns,
    index_player_strength,
    load_jsonl,
    load_notes,
)


def _resolve_game_ids(turns: list[dict], game: str | None, all_games: bool) -> list[str]:
    if all_games:
        ids = sorted({str(r["gameId"]) for r in turns if r.get("gameId")})
        if not ids:
            raise SystemExit("no gameId in turns.jsonl")
        return ids
    if not game:
        raise SystemExit("pass --game or --all")
    matched = filter_turns(turns, game)
    if not matched:
        raise SystemExit(f"no turns for game {game!r}")
    return [str(matched[0]["gameId"])]


def build_one(
    game_id: str,
    *,
    turns_all: list[dict],
    strength_all: list[dict],
    boards_root: Path | None,
    out_root: Path,
    render_boards: bool,
    allow_missing_strength: bool,
    offline_boards: bool,
) -> Path:
    turn_rows = filter_turns(turns_all, game_id)
    if not turn_rows:
        raise SystemExit(f"no turns for {game_id}")
    canonical = str(turn_rows[0]["gameId"])
    strength_by = index_player_strength(strength_all, canonical)

    if not allow_missing_strength:
        missing_ready = [
            int(r["turn"])
            for r in turn_rows
            if r.get("status") == "ready" and int(r["turn"]) not in strength_by
        ]
        if missing_ready:
            raise SystemExit(
                f"{canonical}: ready turns missing strength: {missing_ready[:8]}"
                + ("…" if len(missing_ready) > 8 else "")
                + " (pass --allow-missing-strength to continue)"
            )

    tiers: dict[int, tuple[int | None, int | None]] = {}
    game_dir = None
    try:
        _gid, game_dir = resolve_game(diag_roots(), canonical)
        tiers = tiers_from_combats(game_dir)
    except SystemExit:
        tiers = {}

    turns_list = [int(r["turn"]) for r in turn_rows]
    combat_by = {int(r["turn"]): int(r["combat"]) for r in turn_rows if r.get("combat") is not None}

    if render_boards:
        boards_cache = out_root.parent / "boards_cache"
        render_boards_if_needed(canonical, boards_cache, offline=offline_boards)
        boards_root = boards_cache

    board_paths = collect_board_paths(boards_root, canonical, turns_list, combat_by)
    out_dir = out_root / canonical
    rel_boards = copy_boards_into(out_dir / "boards", board_paths)

    notes = load_notes(out_dir / "notes.json")
    game = build_game_review(
        game_id=canonical,
        turn_rows=turn_rows,
        strength_by_turn=strength_by,
        tiers_by_turn=tiers,
        boards_by_turn=rel_boards,
        notes=notes,
        allow_missing_strength=allow_missing_strength,
    )
    return write_review(game, out_dir)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="P3-T5: offline static HTML post-game review")
    ap.add_argument("--game", default=None, help="game id or short suffix (e.g. ed11e0)")
    ap.add_argument("--all", action="store_true", help="build every gameId in turns.jsonl")
    ap.add_argument("--turns", default=str(REPO / "data" / "standard" / "turns.jsonl"))
    ap.add_argument(
        "--strength",
        default=str(REPO / "data" / "strength" / "1.85.0.0" / "strength.jsonl"),
    )
    ap.add_argument("--boards", default=None, help="existing board_render output root")
    ap.add_argument("--out", default=str(REPO / "data" / "review"))
    ap.add_argument(
        "--render-boards",
        action="store_true",
        help="call tools.board_render if needed (writes under <out>/../boards_cache)",
    )
    ap.add_argument("--online-art", action="store_true", help="allow board_render to download art")
    ap.add_argument("--allow-missing-strength", action="store_true")
    ap.add_argument("--serve", action="store_true", help="serve --out over localhost after build")
    ap.add_argument("--port", type=int, default=8765)
    args = ap.parse_args(argv)

    turns_path = Path(args.turns)
    strength_path = Path(args.strength)
    if not turns_path.is_file():
        raise SystemExit(f"turns not found: {turns_path}")
    if not strength_path.is_file() and not args.allow_missing_strength:
        raise SystemExit(f"strength not found: {strength_path}")

    turns_all = load_jsonl(turns_path)
    strength_all = load_jsonl(strength_path) if strength_path.is_file() else []
    boards_root = Path(args.boards) if args.boards else None
    out_root = Path(args.out)
    out_root.mkdir(parents=True, exist_ok=True)

    game_ids = _resolve_game_ids(turns_all, args.game, args.all)
    written: list[Path] = []
    for gid in game_ids:
        path = build_one(
            gid,
            turns_all=turns_all,
            strength_all=strength_all,
            boards_root=boards_root,
            out_root=out_root,
            render_boards=args.render_boards,
            allow_missing_strength=args.allow_missing_strength,
            offline_boards=not args.online_art,
        )
        written.append(path)
        print(path)

    if args.serve:
        # Serve the out root so relative boards/ work.
        class Handler(SimpleHTTPRequestHandler):
            def __init__(self, *a, **k):
                super().__init__(*a, directory=str(out_root), **k)

        httpd = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
        print(f"serving http://127.0.0.1:{args.port}/ (Ctrl+C to stop)", file=sys.stderr)
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("stopped", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
