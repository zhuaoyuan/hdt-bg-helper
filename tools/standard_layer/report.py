# -*- coding: utf-8 -*-
"""Build quality report dict/text from standard-layer rows."""
from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any


def build_report(rows: list[dict], *, pairs: dict, meta_by_game: dict[str, dict]) -> dict[str, Any]:
    games = sorted({r["gameId"] for r in rows})
    status = Counter(r.get("status") for r in rows)
    sources = Counter(r.get("resultSource") for r in rows)

    # Non-direct-dc turns for ready rate (exit criteria)
    non_dc = [
        r
        for r in rows
        if not (r.get("tuanziKind") == "direct_dc")
    ]
    # If no tuanzi, treat all as non-dc
    if not any(r.get("tuanziKind") for r in rows):
        non_dc = rows
    ready_n = sum(1 for r in non_dc if r.get("status") == "ready")
    ready_rate = (ready_n / len(non_dc)) if non_dc else None

    # Tuanzi cross-check on ready turns that have applicable tuanzi board/sim
    ready_with_tz = [
        r
        for r in rows
        if r.get("status") == "ready"
        and r.get("tuanziCross")
        and r["tuanziCross"].get("applicable")
    ]
    strict = [r for r in ready_with_tz if r["tuanziCross"].get("strictPass") is True]
    strict_fail = [r for r in ready_with_tz if r["tuanziCross"].get("strictPass") is False]
    board_ok = sum(1 for r in ready_with_tz if r["tuanziCross"].get("boardOk") is True)
    sim_ok = sum(1 for r in ready_with_tz if r["tuanziCross"].get("simOk") is True)

    # Paired-game subset (has any tuanziKind) — primary exit-criteria sample
    paired_ids = {r["gameId"] for r in rows if r.get("tuanziKind")}
    paired_rows = [r for r in rows if r["gameId"] in paired_ids]
    paired_non_dc = [r for r in paired_rows if r.get("tuanziKind") != "direct_dc"]
    paired_ready = sum(1 for r in paired_non_dc if r.get("status") == "ready")
    paired_ready_rate = (paired_ready / len(paired_non_dc)) if paired_non_dc else None

    replay_rows = [r for r in rows if r.get("replayDelta")]
    replay_ok = sum(1 for r in replay_rows if r["replayDelta"].get("within3sigma"))
    replay_skip = sum(1 for r in replay_rows if r["replayDelta"].get("error") == "skipped_no_dll")

    gap_counts: Counter = Counter()
    for r in rows:
        for g in r.get("gapFlags") or []:
            gap_counts[g.split(":")[0]] += 1

    # Placement: local final place from raw vs tuanzi label. Only the local
    # player's final place is claimed; full lobby ranking is not available.
    raw_place_by_game: dict[str, int] = {}
    tz_place_by_game: dict[str, int] = {}
    tz_inconsistent_games: set[str] = set()
    for r in rows:
        gid = r.get("gameId")
        if gid is None:
            continue
        gid = str(gid)
        if r.get("placementRaw") is not None:
            raw_place_by_game[gid] = int(r["placementRaw"])
        if r.get("placementTuanzi") is not None:
            tz_place_by_game[gid] = int(r["placementTuanzi"])
        if r.get("placementTuanzi") is not None and r.get("placementTuanziValid") is False:
            tz_inconsistent_games.add(gid)
    compared = sorted(set(raw_place_by_game) & set(tz_place_by_game))
    mismatches = [
        {
            "gameId": gid,
            "raw": raw_place_by_game[gid],
            "tuanzi": tz_place_by_game[gid],
        }
        for gid in compared
        if raw_place_by_game[gid] != tz_place_by_game[gid]
    ]
    placement = {
        "rowsWithPlacement": sum(1 for r in rows if r.get("placement") is not None),
        "rowsWithRawPlacement": sum(1 for r in rows if r.get("placementRaw") is not None),
        "sources": dict(Counter(r.get("placementSource") for r in rows)),
        "rawVsTuanzi": {
            "gamesCompared": len(compared),
            "gamesMatch": len(compared) - len(mismatches),
            "mismatchCount": len(mismatches),
            "mismatchSamples": mismatches[:20],
            "tuanziInconsistentGames": sorted(tz_inconsistent_games),
        },
    }
    rules_coverage = {
        "rowsWithAvailableRaces": sum(
            1 for r in rows if (r.get("rules") or {}).get("availableRaces") is not None
        ),
        "rowsWithAnomaly": sum(1 for r in rows if (r.get("rules") or {}).get("anomalyDbfId") is not None),
        "rowsWithDamageCap": sum(1 for r in rows if (r.get("rules") or {}).get("damageCap") is not None),
        "duosRows": sum(1 for r in rows if (r.get("rules") or {}).get("duos") is True),
    }

    by_bb: Counter = Counter()
    by_hdt: Counter = Counter()
    for gid, m in meta_by_game.items():
        bb = (m.get("bobsBuddy") or {}).get("fileVersion") or (m.get("bobsBuddy") or {}).get("version")
        hdt = (m.get("hdt") or {}).get("fileVersion") or (m.get("hdt") or {}).get("version")
        by_bb[str(bb)] += 1
        by_hdt[str(hdt)] += 1

    # Paired games listing
    paired = []
    for gid, p in sorted(pairs.items()):
        tg = p["game"]
        kinds = Counter(t.get("kind") for t in tg["turns"].values())
        paired.append({
            "gameId": gid,
            "file": p.get("file"),
            "myHero": tg.get("myHero"),
            "place": tg.get("place"),
            "oppNameMatches": p.get("score"),
            "kinds": dict(kinds),
        })

    # Smoke: per-game has session_start + at least one combat with output
    smoke = []
    for gid in games:
        grows = [r for r in rows if r["gameId"] == gid]
        m = meta_by_game.get(gid) or {}
        smoke.append({
            "gameId": gid,
            "plugin": m.get("pluginVersion"),
            "bb": (m.get("bobsBuddy") or {}).get("fileVersion"),
            "hdt": (m.get("hdt") or {}).get("fileVersion"),
            "turns": len(grows),
            "ready": sum(1 for r in grows if r.get("status") == "ready"),
            "missing": sum(1 for r in grows if r.get("status") == "missing"),
            "errors": m.get("errors"),
            "probeInitError": m.get("probeInitError"),
            "ok": any(r.get("hasOutput") for r in grows) and m.get("probeInitError") in (None, "", False),
        })

    return {
        "gamesCount": len(games),
        "turnCount": len(rows),
        "pairedGames": len(pairs),
        "statusCounts": dict(status),
        "resultSources": dict(sources),
        "readyRateNonDirectDc": ready_rate,
        "readyNonDirectDc": ready_n,
        "nonDirectDcTurns": len(non_dc),
        "tuanzi": {
            "readyWithTuanzi": len(ready_with_tz),
            "strictPass": len(strict),
            "strictFail": len(strict_fail),
            "boardOk": board_ok,
            "simOk": sim_ok,
            "strictPassRate": (len(strict) / len(ready_with_tz)) if ready_with_tz else None,
            "failSamples": [
                {"gameId": r["gameId"], "turn": r["turn"], "cross": r["tuanziCross"]}
                for r in strict_fail[:20]
            ],
        },
        "pairedSample": {
            "games": len(paired_ids),
            "turns": len(paired_rows),
            "nonDirectDcTurns": len(paired_non_dc),
            "ready": paired_ready,
            "readyRate": paired_ready_rate,
        },
        "replay": {
            "attempted": len(replay_rows),
            "within3sigma": replay_ok,
            "skippedNoDll": replay_skip,
            "passRate": (replay_ok / max(1, len(replay_rows) - replay_skip)) if replay_rows else None,
        },
        "gapPositives": dict(gap_counts),
        "placement": placement,
        "rules": rules_coverage,
        "versions": {"bobsBuddy": dict(by_bb), "hdt": dict(by_hdt)},
        "paired": paired,
        "smoke": smoke,
        "exitCriteriaHint": {
            "ready_ge_90pct_non_dc_all": (ready_rate is not None and ready_rate >= 0.90),
            "ready_ge_90pct_paired_non_dc": (
                paired_ready_rate is not None and paired_ready_rate >= 0.90
            ),
            "tuanzi_ready_100pct": (
                len(ready_with_tz) > 0 and len(strict_fail) == 0
            ),
            "replay_3sigma": (
                (len(replay_rows) - replay_skip) > 0
                and replay_ok == (len(replay_rows) - replay_skip)
            ) if replay_rows else None,
        },
    }


def format_report(report: dict) -> str:
    lines = []
    lines.append(f"games={report['gamesCount']} turns={report['turnCount']} paired={report['pairedGames']}")
    lines.append(f"status: {report['statusCounts']}")
    lines.append(f"resultSource: {report['resultSources']}")
    rr = report["readyRateNonDirectDc"]
    lines.append(
        f"ready (non-direct-dc): {report['readyNonDirectDc']}/{report['nonDirectDcTurns']}"
        + (f" = {rr:.1%}" if rr is not None else "")
    )
    tz = report["tuanzi"]
    lines.append(
        f"tuanzi strict on ready: {tz['strictPass']}/{tz['readyWithTuanzi']}"
        + (f" = {tz['strictPassRate']:.1%}" if tz["strictPassRate"] is not None else "")
        + f" (boardOk={tz['boardOk']} simOk={tz['simOk']})"
    )
    ps = report.get("pairedSample") or {}
    if ps.get("games"):
        pr = ps.get("readyRate")
        lines.append(
            f"paired sample: games={ps['games']} ready (non-dc)={ps['ready']}/{ps['nonDirectDcTurns']}"
            + (f" = {pr:.1%}" if pr is not None else "")
        )
    if tz["failSamples"]:
        lines.append("  fail samples:")
        for s in tz["failSamples"][:10]:
            lines.append(f"    {s['gameId']} T{s['turn']} {s['cross']}")
    rp = report["replay"]
    if rp["attempted"]:
        lines.append(
            f"replay: within3σ={rp['within3sigma']}/{rp['attempted'] - rp['skippedNoDll']} "
            f"(skipped_no_dll={rp['skippedNoDll']})"
        )
    if report["gapPositives"]:
        lines.append(f"gap positives: {report['gapPositives']}")
    pl = report.get("placement") or {}
    if pl:
        rt = pl.get("rawVsTuanzi") or {}
        lines.append(
            "placement: rows={rows} raw={raw} sources={sources} "
            "rawVsTuanzi={match}/{compared} (mismatch={mismatch}, tuanziInconsistent={bad})".format(
                rows=pl.get("rowsWithPlacement"),
                raw=pl.get("rowsWithRawPlacement"),
                sources=pl.get("sources"),
                match=rt.get("gamesMatch"),
                compared=rt.get("gamesCompared"),
                mismatch=rt.get("mismatchCount"),
                bad=len(rt.get("tuanziInconsistentGames") or []),
            )
        )
    lines.append(f"BB versions: {report['versions']['bobsBuddy']}")
    rc = report.get("rules") or {}
    if rc:
        lines.append(
            "rules: races={races} anomaly={anomaly} damageCap={cap} duos={duos}".format(
                races=rc.get("rowsWithAvailableRaces"),
                anomaly=rc.get("rowsWithAnomaly"),
                cap=rc.get("rowsWithDamageCap"),
                duos=rc.get("duosRows"),
            )
        )
    lines.append(f"HDT versions: {report['versions']['hdt']}")
    lines.append(f"exitCriteria hint: {report['exitCriteriaHint']}")
    lines.append("paired games:")
    for p in report["paired"]:
        lines.append(
            f"  {p['gameId']} <- {p['file']} {p['myHero']} place={p['place']} "
            f"oppMatches={p['oppNameMatches']} kinds={p['kinds']}"
        )
    bad_smoke = [s for s in report["smoke"] if not s["ok"]]
    if bad_smoke:
        lines.append(f"smoke failures ({len(bad_smoke)}):")
        for s in bad_smoke[:15]:
            lines.append(f"  {s}")
    return "\n".join(lines)
