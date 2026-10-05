# -*- coding: utf-8 -*-
"""Render a self-contained static HTML review page."""
from __future__ import annotations

import html
import json
from pathlib import Path

from .model import GameReview, turn_detail_text


def _esc(s: object) -> str:
    return html.escape("" if s is None else str(s), quote=True)


def render_html(game: GameReview) -> str:
    model = game.to_dict()
    for t, tr in zip(model["turns"], game.turns):
        t["detailText"] = turn_detail_text(tr)
        t["note"] = None
        if game.notes and isinstance(game.notes.get("turns"), dict):
            t["note"] = game.notes["turns"].get(str(tr.turn)) or game.notes["turns"].get(tr.turn)

    # Avoid </script> breakouts; do not HTML-escape JSON (breaks JSON.parse).
    payload = json.dumps(model, ensure_ascii=False).replace("</", "<\\/")
    turns_opts = "\n".join(
        f'<option value="{t.turn}">T{t.turn}</option>' for t in game.turns
    )
    place = f"#{game.placement}" if game.placement is not None else "—"
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>复盘 {_esc(game.game_id)}</title>
<style>
:root {{
  --bg: #1a1d21;
  --panel: #24282e;
  --text: #e8eaed;
  --muted: #9aa0a6;
  --accent: #8ab4f8;
  --win: #81c995;
  --loss: #f28b82;
  --tie: #fdd663;
  --grid: #3c4043;
}}
* {{ box-sizing: border-box; }}
body {{
  margin: 0; font-family: "Segoe UI", "Microsoft YaHei", sans-serif;
  background: var(--bg); color: var(--text); line-height: 1.45;
}}
header {{
  padding: 1rem 1.25rem; border-bottom: 1px solid var(--grid);
  display: flex; flex-wrap: wrap; gap: .75rem 1.5rem; align-items: baseline;
}}
header h1 {{ font-size: 1.15rem; margin: 0; font-weight: 600; }}
header .meta {{ color: var(--muted); font-size: .9rem; }}
main {{ padding: 1rem 1.25rem 2rem; display: grid; gap: 1rem; }}
.timeline-wrap {{
  background: var(--panel); border-radius: 8px; padding: .75rem 1rem 1rem;
}}
.timeline-wrap h2, .detail h2 {{ font-size: .95rem; margin: 0 0 .5rem; color: var(--muted); font-weight: 600; }}
svg.timeline {{ width: 100%; height: 140px; display: block; }}
.legend {{ font-size: .8rem; color: var(--muted); margin-top: .35rem; }}
.panels {{
  display: grid; grid-template-columns: minmax(220px, 320px) 1fr; gap: 1rem;
}}
@media (max-width: 800px) {{ .panels {{ grid-template-columns: 1fr; }} }}
.detail, .boards {{
  background: var(--panel); border-radius: 8px; padding: 1rem;
}}
.detail dl {{ margin: 0; display: grid; grid-template-columns: auto 1fr; gap: .35rem .75rem; font-size: .92rem; }}
.detail dt {{ color: var(--muted); }}
.detail dd {{ margin: 0; }}
.strength {{ margin: .75rem 0; padding: .65rem .75rem; background: #1a1d21; border-radius: 6px; }}
.hdt {{ border-left: 3px solid var(--accent); padding-left: .65rem; margin-top: .5rem; }}
.boards .side {{ margin-bottom: 1rem; }}
.boards .side:last-child {{ margin-bottom: 0; }}
.boards .label {{ font-size: .9rem; color: var(--muted); margin-bottom: .35rem; }}
.boards img {{ max-width: 100%; height: auto; border-radius: 4px; background: #202427; }}
.missing {{ color: var(--muted); font-size: .9rem; }}
select {{ background: #1a1d21; color: var(--text); border: 1px solid var(--grid); border-radius: 4px; padding: .25rem .4rem; }}
.note {{ margin-top: .75rem; font-size: .85rem; color: var(--muted); white-space: pre-wrap; }}
</style>
</head>
<body>
<header>
  <h1>{_esc(game.my_hero or "复盘")} · 名次 {place}</h1>
  <div class="meta">{_esc(game.game_id)} · BB {_esc(game.bb_version or "?")} · engine {_esc(game.engine_version or "?")}</div>
</header>
<main>
  <section class="timeline-wrap">
    <h2>时间线（点击选回合）</h2>
    <svg class="timeline" id="timeline" viewBox="0 0 800 140" preserveAspectRatio="none"></svg>
    <div class="legend">实心=ok · 空心=wide · L1=放宽 · 灰=缺数/非 ready · 色条=战果</div>
  </section>
  <div class="panels">
    <section class="detail">
      <h2>回合详情
        <select id="turnSelect">{turns_opts}</select>
      </h2>
      <div id="detailBody"></div>
    </section>
    <section class="boards" id="boards"></section>
  </div>
</main>
<script type="application/json" id="model">{payload}</script>
<script>
const model = JSON.parse(document.getElementById('model').textContent);
const byTurn = Object.fromEntries(model.turns.map(t => [t.turn, t]));
let selected = model.turns.length ? model.turns[0].turn : null;

function resultColor(r) {{
  if (r === 'win') return '#81c995';
  if (r === 'loss') return '#f28b82';
  if (r === 'tie') return '#fdd663';
  return '#5f6368';
}}

function drawTimeline() {{
  const svg = document.getElementById('timeline');
  const w = 800, h = 140, padL = 40, padR = 20, padT = 20, padB = 36;
  const turns = model.turns;
  if (!turns.length) {{ svg.innerHTML = ''; return; }}
  const xs = turns.map((_, i) => padL + (i / Math.max(turns.length - 1, 1)) * (w - padL - padR));
  const yScale = (p) => {{
    if (p == null) return padT + (h - padT - padB) / 2;
    return padT + (1 - p) * (h - padT - padB);
  }};
  let parts = [];
  for (const g of [0, 0.5, 1]) {{
    const y = yScale(g);
    parts.push(`<line x1="${{padL}}" x2="${{w-padR}}" y1="${{y}}" y2="${{y}}" stroke="#3c4043" stroke-dasharray="3 4"/>`);
    parts.push(`<text x="8" y="${{y+4}}" fill="#9aa0a6" font-size="11">${{Math.round(g*100)}}</text>`);
  }}
  const barY = h - 18;
  turns.forEach((t, i) => {{
    const x = xs[i];
    parts.push(`<rect x="${{x-8}}" y="${{barY}}" width="16" height="8" rx="2" fill="${{resultColor(t.result)}}"/>`);
    parts.push(`<text x="${{x}}" y="${{h-4}}" text-anchor="middle" fill="#9aa0a6" font-size="11">T${{t.turn}}</text>`);
  }});
  turns.forEach((t, i) => {{
    const x = xs[i];
    const st = t.strength_state;
    const has = t.percentile != null && st !== 'missing' && st !== 'non_ready' && st !== 'insufficient';
    if (has && t.ci95) {{
      const y1 = yScale(t.ci95[0]), y2 = yScale(t.ci95[1]);
      parts.push(`<line x1="${{x}}" x2="${{x}}" y1="${{y1}}" y2="${{y2}}" stroke="#8ab4f8" stroke-width="2" opacity="0.7"/>`);
    }}
    let fill = '#8ab4f8', stroke = '#8ab4f8', r = 5;
    if (st === 'wide') {{ fill = 'transparent'; }}
    if (st === 'relaxed') {{ fill = '#c58af9'; stroke = '#c58af9'; }}
    if (st === 'insufficient' || st === 'missing' || st === 'non_ready') {{ fill = '#5f6368'; stroke = '#5f6368'; r = 4; }}
    const cy = has ? yScale(t.percentile) : yScale(null);
    const mark = (st === 'insufficient')
      ? `<text x="${{x}}" y="${{cy+4}}" text-anchor="middle" fill="#5f6368" font-size="14" font-weight="700">×</text>`
      : `<circle cx="${{x}}" cy="${{cy}}" r="${{r}}" fill="${{fill}}" stroke="${{stroke}}" stroke-width="2"/>`;
    parts.push(`<g class="pt" data-turn="${{t.turn}}" style="cursor:pointer">${{mark}}</g>`);
    if (st === 'relaxed') {{
      parts.push(`<text x="${{x+8}}" y="${{cy-8}}" fill="#c58af9" font-size="10">L1</text>`);
    }}
  }});
  const si = turns.findIndex(t => t.turn === selected);
  if (si >= 0) {{
    parts.push(`<line x1="${{xs[si]}}" x2="${{xs[si]}}" y1="${{padT}}" y2="${{h-padB}}" stroke="#e8eaed" stroke-opacity="0.25"/>`);
  }}
  svg.innerHTML = parts.join('');
  svg.querySelectorAll('.pt').forEach(el => {{
    el.addEventListener('click', () => selectTurn(Number(el.dataset.turn)));
  }});
}}

function tierLabel(t) {{ return t == null ? '酒馆 ?' : ('酒馆 T' + t); }}

function selectTurn(turn) {{
  selected = turn;
  document.getElementById('turnSelect').value = String(turn);
  const t = byTurn[turn];
  if (!t) return;
  const hdt = [
    '胜 ' + (t.hdt_win == null ? '—' : (t.hdt_win*100).toFixed(1) + '%'),
    '平 ' + (t.hdt_tie == null ? '—' : (t.hdt_tie*100).toFixed(1) + '%'),
    '负 ' + (t.hdt_loss == null ? '—' : (t.hdt_loss*100).toFixed(1) + '%'),
  ].join(' · ');
  const dmg = t.damage == null ? '—' : t.damage;
  const note = t.note ? (`<div class="note">备注：${{typeof t.note === 'string' ? t.note : JSON.stringify(t.note)}}</div>`) : '';
  document.getElementById('detailBody').innerHTML = `
    <div class="strength">${{t.detailText || '—'}}</div>
    <dl>
      <dt>对手</dt><dd>${{t.opp_hero || '—'}}</dd>
      <dt>战果</dt><dd>${{t.result || '—'}}（伤 ${{dmg}}，来源 ${{t.result_source || '—'}}）</dd>
      <dt>level</dt><dd>${{t.level || '—'}} ${{(t.flags||[]).join(',')}}</dd>
      <dt>状态</dt><dd>${{t.strength_state}} / 标准层 ${{t.status}}</dd>
    </dl>
    <div class="hdt"><strong>当场模拟（HDT）</strong><br/>${{hdt}}</div>
    ${{note}}`;
  const boards = document.getElementById('boards');
  const img = (src, alt) => src
    ? `<img src="${{src}}" alt="${{alt}}"/>`
    : `<div class="missing">（无阵容图）</div>`;
  boards.innerHTML = `
    <div class="side"><div class="label">己方 · ${{tierLabel(t.my_tavern_tier)}}</div>${{img(t.board_player, 'player board')}}</div>
    <div class="side"><div class="label">对手 · ${{tierLabel(t.opp_tavern_tier)}}</div>${{img(t.board_opponent, 'opponent board')}}</div>`;
  drawTimeline();
}}

document.getElementById('turnSelect').addEventListener('change', (e) => selectTurn(Number(e.target.value)));
if (selected != null) selectTurn(selected);
</script>
</body>
</html>
"""


def write_review(game: GameReview, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    model_path = out_dir / "model.json"
    model_path.write_text(json.dumps(game.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    html_path = out_dir / "index.html"
    html_path.write_text(render_html(game), encoding="utf-8")
    return html_path
