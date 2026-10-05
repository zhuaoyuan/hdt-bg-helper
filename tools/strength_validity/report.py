# -*- coding: utf-8 -*-
"""Build validity evaluation report (JSON + Markdown helpers)."""
from __future__ import annotations

from typing import Any, Optional, Sequence

from .align import GameAgg, TurnPair, aggregate_games, result_code
from .metrics import associate, leave_one_out_rhos, partial_spearman


MIN_N_GAMES = 12
MIN_N_TURNS = 30


def _dir_ok(rho: Optional[float], expect_positive: bool) -> Optional[bool]:
    if rho is None:
        return None
    return (rho > 0) if expect_positive else (rho < 0)


def _verdict_assoc(
    assoc: dict[str, Any],
    *,
    min_n: int,
    expect_positive: bool,
) -> str:
    n = assoc.get("n") or 0
    if n < min_n:
        return "sample_insufficient"
    if assoc.get("rho") is None:
        return "no_estimate"
    direction = _dir_ok(assoc.get("rho"), expect_positive)
    if assoc.get("significant") and direction:
        return "significant_ok"
    if assoc.get("significant") and direction is False:
        return "significant_wrong_direction"
    return "not_significant"


def eval_placement(games: list[GameAgg], *, n_boot: int, n_perm: int, seed: int) -> dict[str, Any]:
    placed = [g for g in games if g.placement is not None and g.mean_percentile is not None]
    # Higher percentile should associate with better (lower) placement → use -placement
    x = [g.mean_percentile for g in placed]
    y = [-float(g.placement) for g in placed]  # type: ignore[arg-type]
    hdt = [g.mean_hdt for g in placed if g.mean_hdt is not None]
    # keep aligned triples
    triples = [
        (g.mean_percentile, -float(g.placement), g.mean_hdt)  # type: ignore[arg-type]
        for g in placed
        if g.mean_hdt is not None
    ]
    pct_vs = associate(x, y, n_boot=n_boot, n_perm=n_perm, seed=seed)
    hdt_vs = None
    partial = None
    if triples:
        xp = [t[0] for t in triples]
        yp = [t[1] for t in triples]
        zp = [t[2] for t in triples]
        hdt_vs = associate(zp, yp, n_boot=n_boot, n_perm=n_perm, seed=seed + 10)
        partial = partial_spearman(xp, yp, zp, n_boot=n_boot, n_perm=n_perm, seed=seed + 20)
    loo = leave_one_out_rhos(x, y)
    loo_sign = None
    if loo and pct_vs.get("rho") is not None:
        base = 1 if pct_vs["rho"] >= 0 else -1
        loo_sign = all(r is not None and (1 if r >= 0 else -1) == base for r in loo)

    # half-split by gameId chronological
    half = None
    if len(placed) >= 4:
        mid = len(placed) // 2
        a, b = placed[:mid], placed[mid:]
        half = {
            "first": associate(
                [g.mean_percentile for g in a],
                [-float(g.placement) for g in a],  # type: ignore[arg-type]
                n_boot=min(n_boot, 2000),
                n_perm=min(n_perm, 2000),
                seed=seed + 30,
            ),
            "second": associate(
                [g.mean_percentile for g in b],
                [-float(g.placement) for g in b],  # type: ignore[arg-type]
                n_boot=min(n_boot, 2000),
                n_perm=min(n_perm, 2000),
                seed=seed + 40,
            ),
        }

    # drop wide-heavy games (all turns wide)
    slim = [g for g in placed if g.n_wide < g.n_turns]
    slim_assoc = None
    if slim and len(slim) != len(placed):
        slim_assoc = associate(
            [g.mean_percentile for g in slim],
            [-float(g.placement) for g in slim],  # type: ignore[arg-type]
            n_boot=n_boot,
            n_perm=n_perm,
            seed=seed + 50,
        )

    verdict = _verdict_assoc(pct_vs, min_n=MIN_N_GAMES, expect_positive=True)
    return {
        "n_games": len(placed),
        "game_ids": [g.game_id for g in placed],
        "percentile_vs_neg_placement": pct_vs,
        "hdt_vs_neg_placement": hdt_vs,
        "partial_percentile_given_hdt": partial,
        "leave_one_out_same_sign": loo_sign,
        "half_split": half,
        "without_all_wide": slim_assoc,
        "verdict": verdict,
        "min_n": MIN_N_GAMES,
        "note": "y = -placement so positive rho means higher percentile ~ better place",
    }


def eval_next_health(
    games: list[GameAgg],
    pairs: list[TurnPair],
    *,
    n_boot: int,
    n_perm: int,
    seed: int,
) -> dict[str, Any]:
    # Game-level primary: mean percentile ↔ mean next health
    g_ok = [g for g in games if g.mean_percentile is not None and g.mean_next_health is not None]
    game_assoc = associate(
        [g.mean_percentile for g in g_ok],
        [g.mean_next_health for g in g_ok],  # type: ignore[misc]
        n_boot=n_boot,
        n_perm=n_perm,
        seed=seed,
    )
    # Turn-level appendix
    t_ok = [p for p in pairs if p.next_health is not None]
    turn_assoc = associate(
        [p.percentile for p in t_ok],
        [float(p.next_health) for p in t_ok],  # type: ignore[arg-type]
        n_boot=n_boot,
        n_perm=n_perm,
        seed=seed + 5,
    )
    sources: dict[str, int] = {}
    for p in t_ok:
        sources[p.health_source or "unknown"] = sources.get(p.health_source or "unknown", 0) + 1

    g_verdict = _verdict_assoc(game_assoc, min_n=MIN_N_GAMES, expect_positive=True)
    t_verdict = _verdict_assoc(turn_assoc, min_n=MIN_N_TURNS, expect_positive=True)
    return {
        "game_level": {**game_assoc, "verdict": g_verdict, "min_n": MIN_N_GAMES, "n_games": len(g_ok)},
        "turn_level_appendix": {
            **turn_assoc,
            "verdict": t_verdict,
            "min_n": MIN_N_TURNS,
            "n_turns": len(t_ok),
            "health_sources": sources,
            "note": "turns within a game are not independent (ADR-0011)",
        },
    }


def eval_result_appendix(pairs: list[TurnPair], *, n_boot: int, n_perm: int, seed: int) -> dict[str, Any]:
    rows = []
    for p in pairs:
        code = result_code(p.result)
        if code is None:
            continue
        rows.append((p.percentile, code, p.hdt))
    if not rows:
        return {"n": 0, "note": "no result labels"}
    pct = associate(
        [r[0] for r in rows],
        [r[1] for r in rows],
        n_boot=n_boot,
        n_perm=n_perm,
        seed=seed,
    )
    hdt_rows = [r for r in rows if r[2] is not None]
    hdt = associate(
        [r[2] for r in hdt_rows],  # type: ignore[misc]
        [r[1] for r in hdt_rows],
        n_boot=n_boot,
        n_perm=n_perm,
        seed=seed + 1,
    )
    return {
        "note": "NOT an exit criterion; combat result appendix only (T0)",
        "percentile_vs_result": pct,
        "hdt_vs_result": hdt,
    }


def exit3_verdict(placement: dict[str, Any], health: dict[str, Any]) -> dict[str, Any]:
    pv = placement.get("verdict")
    hv = health.get("game_level", {}).get("verdict")
    if pv == "sample_insufficient" or hv == "sample_insufficient":
        overall = "sample_insufficient"
    elif pv == "significant_ok" and hv == "significant_ok":
        overall = "pass"
    elif pv in ("not_significant", "significant_wrong_direction", "no_estimate") or hv in (
        "not_significant",
        "significant_wrong_direction",
        "no_estimate",
    ):
        overall = "fail"
    else:
        overall = "sample_insufficient"

    # ADR materials
    n_place = placement.get("n_games") or 0
    if overall == "pass":
        adr0003 = "no_trigger"
        adr0014_width_blocks = False
    elif overall == "fail":
        # distinction lacking at current width → may discuss 0014#2 / 0003
        adr0003 = "discuss_overturn" if n_place >= MIN_N_GAMES else "evidence_insufficient"
        adr0014_width_blocks = n_place >= MIN_N_GAMES
    else:
        adr0003 = "evidence_insufficient"
        adr0014_width_blocks = False

    return {
        "exit3": overall,
        "placement_verdict": pv,
        "health_verdict": hv,
        "adr0003": adr0003,
        "adr0014_width_blocks_validity": adr0014_width_blocks,
        "n_placement_games": n_place,
        "n_health_games": health.get("game_level", {}).get("n_games"),
        "labels": {
            "pass": "通过",
            "fail": "未通过",
            "sample_insufficient": "样本不足无法判定",
            "no_trigger": "不触发",
            "discuss_overturn": "建议讨论推翻",
            "evidence_insufficient": "证据不足",
        },
    }


def build_report(
    pairs: list[TurnPair],
    *,
    bb_version: str,
    strength_path: str,
    max_turn: int | None,
    n_boot: int = 5000,
    n_perm: int = 5000,
    seed: int = 0,
    include_result_appendix: bool = True,
) -> dict[str, Any]:
    games = aggregate_games(pairs)
    placement = eval_placement(games, n_boot=n_boot, n_perm=n_perm, seed=seed)
    health = eval_next_health(games, pairs, n_boot=n_boot, n_perm=n_perm, seed=seed + 100)
    exit3 = exit3_verdict(placement, health)
    report: dict[str, Any] = {
        "bbVersion": bb_version,
        "strengthPath": strength_path,
        "maxTurn": max_turn,
        "n_turn_pairs": len(pairs),
        "n_games": len(games),
        "placement": placement,
        "next_health": health,
        "exit3": exit3,
        "recommend_more_paired_games": (placement.get("n_games") or 0) < MIN_N_GAMES,
    }
    if include_result_appendix:
        report["result_appendix"] = eval_result_appendix(
            pairs, n_boot=min(n_boot, 2000), n_perm=min(n_perm, 2000), seed=seed + 200
        )
    return report


def report_to_markdown(report: dict[str, Any]) -> str:
    e = report["exit3"]
    labels = e["labels"]
    p = report["placement"]
    h = report["next_health"]["game_level"]
    ht = report["next_health"]["turn_level_appendix"]
    pct = p["percentile_vs_neg_placement"]
    lines = [
        f"# P3-T4 validity snapshot (`{report['bbVersion']}`)",
        "",
        f"- strength: `{report['strengthPath']}`",
        f"- maxTurn: {report['maxTurn']}",
        f"- turn pairs: {report['n_turn_pairs']}; games: {report['n_games']}",
        "",
        "## Exit criterion #3",
        "",
        f"- **{labels.get(e['exit3'], e['exit3'])}**",
        f"- placement n={p['n_games']} verdict=`{p['verdict']}`",
        f"- next-health (game) n={h.get('n_games')} verdict=`{h.get('verdict')}`",
        "",
        "## Placement (mean percentile vs −placement)",
        "",
        f"| metric | value |",
        f"| --- | ---: |",
        f"| n | {pct.get('n')} |",
        f"| Spearman rho | {_fmt(pct.get('rho'))} |",
        f"| bootstrap 95% CI | {_fmt_ci(pct.get('ci95'))} |",
        f"| permutation p | {_fmt(pct.get('perm_p'))} |",
        f"| significant | {pct.get('significant')} |",
    ]
    hdt = p.get("hdt_vs_neg_placement") or {}
    part = p.get("partial_percentile_given_hdt") or {}
    lines += [
        "",
        "### vs HDT on placement",
        "",
        f"| metric | HDT | percentile given HDT (partial) |",
        f"| --- | ---: | ---: |",
        f"| n | {hdt.get('n')} | {part.get('n')} |",
        f"| rho | {_fmt(hdt.get('rho'))} | {_fmt(part.get('rho'))} |",
        f"| CI95 | {_fmt_ci(hdt.get('ci95'))} | {_fmt_ci(part.get('ci95'))} |",
        f"| perm p | {_fmt(hdt.get('perm_p'))} | {_fmt(part.get('perm_p'))} |",
        "",
        "## Next-turn health",
        "",
        f"| level | n | rho | CI95 | perm p | significant | verdict |",
        f"| --- | ---: | ---: | --- | ---: | --- | --- |",
        f"| game mean | {h.get('n')} | {_fmt(h.get('rho'))} | {_fmt_ci(h.get('ci95'))} | {_fmt(h.get('perm_p'))} | {h.get('significant')} | {h.get('verdict')} |",
        f"| turn (appendix) | {ht.get('n')} | {_fmt(ht.get('rho'))} | {_fmt_ci(ht.get('ci95'))} | {_fmt(ht.get('perm_p'))} | {ht.get('significant')} | {ht.get('verdict')} |",
        "",
        f"health sources (turn): {ht.get('health_sources')}",
        "",
        "## ADR materials",
        "",
        f"- ADR-0003: **{labels.get(e['adr0003'], e['adr0003'])}**",
        f"- ADR-0014 width-blocks-validity: **{e['adr0014_width_blocks_validity']}**",
        f"- recommend more paired games: **{report.get('recommend_more_paired_games')}**",
        "",
    ]
    return "\n".join(lines)


def _fmt(v: Any) -> str:
    if v is None:
        return "n/a"
    if isinstance(v, float):
        return f"{v:.4f}"
    return str(v)


def _fmt_ci(ci: Any) -> str:
    if not ci or len(ci) < 2:
        return "n/a"
    return f"[{ci[0]:.4f}, {ci[1]:.4f}]"
