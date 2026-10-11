# -*- coding: utf-8 -*-
"""Self-contained HTML: sequence charts for one sim pool."""
from __future__ import annotations

import html
from typing import Any, Optional


def _esc(s: object) -> str:
    return html.escape("" if s is None else str(s), quote=True)


def _fmt_pct(v: Optional[float]) -> str:
    if v is None:
        return "—"
    return f"{v * 100:.1f}"


def _fmt_rho(trend: dict) -> str:
    rho = trend.get("rho")
    p = trend.get("pvalue")
    n = trend.get("n")
    if rho is None:
        return f"n={n}，相关无法计算"
    sig = ""
    if p is not None and p < 0.05:
        sig = "，p<0.05"
    elif p is not None:
        sig = f"，p={p:.2f}"
    direction = "随顺序上升" if rho > 0 else "随顺序下降"
    return f"ρ={rho:.2f}（{direction}{sig}，n={n}）"


def _polyline(
    xs: list[float],
    ys: list[Optional[float]],
    *,
    x0: float,
    y0: float,
    x1: float,
    y1: float,
    vmin: float,
    vmax: float,
    smin: float,
    smax: float,
) -> str:
    """Break the stroke where y is missing. Coordinates: data x = seq, y = value."""

    def px(x: float) -> float:
        if smax == smin:
            return (x0 + x1) / 2
        return x0 + (x - smin) / (smax - smin) * (x1 - x0)

    def py(y: float) -> float:
        if vmax == vmin:
            return (y0 + y1) / 2
        return y1 - (y - vmin) / (vmax - vmin) * (y1 - y0)

    parts: list[str] = []
    cur: list[str] = []
    for x, y in zip(xs, ys):
        if y is None:
            if len(cur) >= 2:
                parts.append(" ".join(cur))
            cur = []
            continue
        cur.append(f"{px(x):.1f},{py(y):.1f}")
    if len(cur) >= 2:
        parts.append(" ".join(cur))
    return "".join(f'<polyline fill="none" points="{p}"/>' for p in parts)


def _chart(
    *,
    title: str,
    xs: list[float],
    series: list[tuple[str, str, list[Optional[float]], str]],
    ymin: float,
    ymax: float,
    y_label: str,
    width: int = 960,
    height: int = 280,
) -> str:
    """series: (css-class, legend, values, dasharray or empty)."""
    pad_l, pad_r, pad_t, pad_b = 48, 16, 28, 32
    x0, y0 = pad_l, pad_t
    x1, y1 = width - pad_r, height - pad_b
    smin = min(xs) if xs else 1
    smax = max(xs) if xs else 1
    polys = []
    for css, _legend, ys, dash in series:
        body = _polyline(xs, ys, x0=x0, y0=y0, x1=x1, y1=y1, vmin=ymin, vmax=ymax, smin=smin, smax=smax)
        polys.append(f'<g class="{css}" stroke-dasharray="{dash}">{body}</g>')
    ticks = []
    for frac, label in ((0, ymin), (0.5, (ymin + ymax) / 2), (1, ymax)):
        yy = y1 - frac * (y1 - y0)
        ticks.append(
            f'<line x1="{x0}" y1="{yy:.1f}" x2="{x1}" y2="{yy:.1f}" class="grid"/>'
            f'<text x="{x0 - 6}" y="{yy + 4:.1f}" class="tick" text-anchor="end">{label:.0f}</text>'
        )
    if xs:
        for x in xs:
            if int(x) == 1 or int(x) == int(smax) or int(x) % 5 == 0:
                px = x0 + (x - smin) / (smax - smin or 1) * (x1 - x0)
                ticks.append(
                    f'<text x="{px:.1f}" y="{height - 8}" class="tick" text-anchor="middle">{int(x)}</text>'
                )
    legend = " ".join(
        f'<span class="lg {css}">{_esc(name)}</span>' for css, name, _ys, _d in series
    )
    return f"""<figure class="chart">
<figcaption>{_esc(title)}</figcaption>
<svg viewBox="0 0 {width} {height}" role="img">
{''.join(ticks)}
{''.join(polys)}
<text x="{x0}" y="16" class="ylab">{_esc(y_label)}</text>
</svg>
<div class="legend">{legend}</div>
</figure>"""


def _turn_values(games: list[dict], turn: int, key: str) -> list[Optional[float]]:
    out: list[Optional[float]] = []
    for g in games:
        raw = (g.get(key) or {}).get(str(turn))
        out.append(None if raw is None else float(raw) * 100.0)
    return out


def render_html(model: dict[str, Any]) -> str:
    games: list[dict] = model["games"]
    xs = [float(g["seq"]) for g in games]
    window = int(model["window"])
    pool = model["simPool"]
    members = "、".join(model.get("members") or [])
    trend = model["trend"]

    player = [None if g["playerMean"] is None else float(g["playerMean"]) * 100 for g in games]
    opp = [None if g["oppMean"] is None else float(g["oppMean"]) * 100 for g in games]
    player_roll = [
        None if v is None else float(v) * 100 for v in model["playerMeanRoll"]
    ]
    opp_roll = [None if v is None else float(v) * 100 for v in model["oppMeanRoll"]]
    survival = [None if g["survivalTurns"] is None else float(g["survivalTurns"]) for g in games]
    survival_roll = [None if v is None else float(v) for v in model["survivalRoll"]]

    global_chart = _chart(
        title="全局综合战力（局内可用回合分位的平均）",
        xs=xs,
        series=[
            ("player", "己方", player, ""),
            ("opp", "对手", opp, ""),
            ("player-roll", f"己方滚动均值（{window}）", player_roll, "5 4"),
            ("opp-roll", f"对手滚动均值（{window}）", opp_roll, "5 4"),
        ],
        ymin=0,
        ymax=100,
        y_label="分位",
    )
    surv_max = max([v for v in survival if v is not None] or [1])
    survival_chart = _chart(
        title="生存回合（该局最后一次战斗的回合号）",
        xs=xs,
        series=[
            ("surv", "生存回合", survival, ""),
            ("surv-roll", f"滚动均值（{window}）", survival_roll, "5 4"),
        ],
        ymin=0,
        ymax=max(12, surv_max + 1),
        y_label="回合",
    )

    turn_blocks = []
    for t in model.get("turns") or []:
        pv = _turn_values(games, int(t), "playerByTurn")
        ov = _turn_values(games, int(t), "oppByTurn")
        if sum(v is not None for v in pv) < 3:
            continue
        turn_blocks.append(
            _chart(
                title=f"回合 {t}",
                xs=xs,
                series=[
                    ("player", "己方", pv, ""),
                    ("opp", "对手", ov, ""),
                ],
                ymin=0,
                ymax=100,
                y_label="分位",
                height=200,
            )
        )

    rows = []
    for g in games:
        rows.append(
            "<tr>"
            f"<td>{g['seq']}</td>"
            f"<td>{_esc(g['gameId'])}</td>"
            f"<td>{_esc(g['bbVersion'])}</td>"
            f"<td>{_fmt_pct(g['playerMean'])}</td>"
            f"<td>{g['playerN']}</td>"
            f"<td>{_fmt_pct(g['oppMean'])}</td>"
            f"<td>{g['oppN']}</td>"
            f"<td>{_esc(g['survivalTurns'])}</td>"
            f"<td>{_esc(g['survivalSource'])}</td>"
            f"<td>{_esc(g['placement'] if g['placement'] is not None else '—')}</td>"
            "</tr>"
        )

    first = games[0]["gameId"][:8] if games else "—"
    last = games[-1]["gameId"][:8] if games else "—"
    n_from_strength = sum(1 for g in games if g["survivalSource"] == "strength")
    src_note = ""
    if n_from_strength:
        src_note = f"其中 {n_from_strength} 局不在当前标准层，生存回合取分位文件里出现过的最大回合。"

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>战力时序 { _esc(pool) }</title>
<style>
:root {{
  --bg: #12151a; --card: #1c222b; --ink: #e7ecf2; --muted: #9aa6b4; --line: #2c3542;
  --player: #6cb6ff; --opp: #f0a36a; --surv: #7dcea0;
}}
body {{ margin: 0; background: var(--bg); color: var(--ink);
  font: 15px/1.5 "Segoe UI", "Microsoft YaHei", sans-serif; }}
main {{ max-width: 1020px; margin: 0 auto; padding: 24px 16px 48px; }}
h1 {{ font-size: 1.4rem; margin: 0 0 8px; }}
p {{ color: var(--muted); margin: 0 0 12px; }}
.cards {{ display: flex; gap: 12px; flex-wrap: wrap; margin: 16px 0; }}
.card {{ background: var(--card); border-radius: 8px; padding: 12px 14px; min-width: 200px; flex: 1; }}
.card b {{ display: block; color: var(--ink); font-weight: 600; }}
figure.chart {{ background: var(--card); border-radius: 8px; padding: 8px 12px 12px; margin: 0 0 14px; }}
figcaption {{ font-weight: 600; margin: 4px 0; }}
svg {{ width: 100%; height: auto; }}
.grid {{ stroke: var(--line); stroke-width: 1; }}
.tick, .ylab {{ fill: var(--muted); font-size: 11px; }}
polyline {{ stroke-width: 1.6; }}
.player polyline {{ stroke: var(--player); }}
.opp polyline {{ stroke: var(--opp); }}
.player-roll polyline {{ stroke: var(--player); opacity: 0.7; }}
.opp-roll polyline {{ stroke: var(--opp); opacity: 0.7; }}
.surv polyline {{ stroke: var(--surv); }}
.surv-roll polyline {{ stroke: var(--surv); opacity: 0.75; }}
.legend {{ display: flex; gap: 14px; flex-wrap: wrap; color: var(--muted); font-size: 13px; }}
.lg::before {{ content: ""; display: inline-block; width: 14px; height: 3px; margin-right: 6px; vertical-align: middle; }}
.lg.player::before, .lg.player-roll::before {{ background: var(--player); }}
.lg.opp::before, .lg.opp-roll::before {{ background: var(--opp); }}
.lg.surv::before, .lg.surv-roll::before {{ background: var(--surv); }}
table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
th, td {{ border-bottom: 1px solid var(--line); padding: 4px 6px; text-align: right; }}
th:nth-child(2), td:nth-child(2) {{ text-align: left; }}
h2 {{ font-size: 1.05rem; margin: 22px 0 8px; }}
</style>
</head>
<body>
<main>
<h1>当前版本对局战力时序</h1>
<p>模拟池 {_esc(pool)}（成员 {_esc(members)}）。横轴是顺序号，按 gameId 时间从早到晚，共 {len(games)} 局（{first} → {last}）。分位是相对这一个池的百分位，不是 HDT 当场胜率。综合战力是该局有分位的回合的算术平均；没有分位的回合不进入平均。对手曲线是同一套循环赛的点估计，没有置信区间；缓存里没有次数的回合会断开。{src_note}</p>
<div class="cards">
  <div class="card"><b>己方综合战力</b>{_esc(_fmt_rho(trend["playerMean"]))}</div>
  <div class="card"><b>对手综合战力</b>{_esc(_fmt_rho(trend["oppMean"]))}</div>
  <div class="card"><b>生存回合</b>{_esc(_fmt_rho(trend["survival"]))}</div>
</div>
<p>ρ 是顺序号与该项的 Spearman。ρ&gt;0 表示越往后越高。p 只说明这串数字排起来像不像单调，不能单独当成「技术在进步」。</p>
{global_chart}
{survival_chart}
<h2>各回合</h2>
<p>只画至少 3 局有己方分位的回合。没打到该回合的局是断点。</p>
{''.join(turn_blocks)}
<h2>逐局</h2>
<table>
<thead><tr><th>序</th><th>gameId</th><th>BB</th><th>己方均分位</th><th>己方回合数</th><th>对手均分位</th><th>对手回合数</th><th>生存</th><th>生存来源</th><th>名次</th></tr></thead>
<tbody>
{''.join(rows)}
</tbody>
</table>
</main>
</body>
</html>
"""
