# -*- coding: utf-8 -*-
"""CLI: chronological strength charts for the current sim pool."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from tools.review_view.opp_strength import load_opp_cache, opp_cache_path
from tools.strength._paths import DEFAULT_TURNS, REPO
from tools.strength.engine import strength_out_path

from .opp_points import opponent_point_percentiles
from .page import render_html
from .series import build_series, load_jsonl


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(description="当前模拟池对局战力时序（离线 HTML）")
    p.add_argument("--sim-pool", default="1.85.0.0")
    p.add_argument("--strength", type=Path, default=None)
    p.add_argument("--turns", type=Path, default=DEFAULT_TURNS)
    p.add_argument("--window", type=int, default=8)
    p.add_argument(
        "--compute-opp",
        action="store_true",
        help="从已有对战缓存补对手分位点估计（不跑新模拟）",
    )
    p.add_argument("--out", type=Path, default=None)
    args = p.parse_args(argv)

    strength_path = args.strength or strength_out_path(args.sim_pool)
    out = args.out or (REPO / "data" / "progress" / f"{args.sim_pool}.html")
    if args.compute_opp:
        opponent_point_percentiles(args.sim_pool, turns_jsonl=args.turns)

    strength_rows = load_jsonl(strength_path)
    turns_rows = load_jsonl(args.turns)
    opp_rows = list(load_opp_cache(opp_cache_path(args.sim_pool)).values())
    model = build_series(
        strength_rows,
        turns_rows,
        opp_rows,
        sim_pool=args.sim_pool,
        window=args.window,
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render_html(model), encoding="utf-8")
    json_path = out.with_suffix(".json")
    json_path.write_text(json.dumps(model, ensure_ascii=False, indent=2), encoding="utf-8")
    trend = model["trend"]["playerMean"]
    print(
        json.dumps(
            {
                "out": str(out),
                "nGames": model["nGames"],
                "playerRho": trend.get("rho"),
                "playerP": trend.get("pvalue"),
            },
            ensure_ascii=False,
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
