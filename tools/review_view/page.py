# -*- coding: utf-8 -*-
"""Render a self-contained static HTML review page."""
from __future__ import annotations

import html
import json
from pathlib import Path

from .model import GameReview, opp_detail_text, turn_detail_text


def _esc(s: object) -> str:
    return html.escape("" if s is None else str(s), quote=True)


def render_html(game: GameReview) -> str:
    model = game.to_dict()
    for t, tr in zip(model["turns"], game.turns):
        t["detailText"] = turn_detail_text(tr)
        t["oppDetailText"] = opp_detail_text(tr)
        t["note"] = None
        if game.notes and isinstance(game.notes.get("turns"), dict):
            t["note"] = game.notes["turns"].get(str(tr.turn)) or game.notes["turns"].get(tr.turn)

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
@import url("https://fonts.googleapis.com/css2?family=DM+Sans:ital,opsz,wght@0,9..40,400;0,9..40,600;0,9..40,700;1,9..40,400&family=Fraunces:opsz,wght@9..144,600;9..144,700&display=swap");
:root {{
  --bg0: #12151a;
  --bg1: #1c222b;
  --panel: rgba(32, 38, 48, 0.92);
  --panel-border: rgba(255, 255, 255, 0.06);
  --text: #f2efe8;
  --muted: #9aa3b2;
  /* me/opp distinct from W/L/T (green/red/yellow) */
  --me: #5b9cf5;
  --me-dim: rgba(91, 156, 245, 0.32);
  --opp: #e879a9;
  --opp-dim: rgba(232, 121, 169, 0.32);
  --hp: #cbd5e1;
  --hp-dim: rgba(203, 213, 225, 0.25);
  --win: #3ecf8e;
  --loss: #ef6b6b;
  --tie: #e6c35c;
  --up: #7eb6ff;
  --sel: rgba(255, 255, 255, 0.14);
  --shadow: 0 12px 40px rgba(0,0,0,0.35);
  --radius: 14px;
  --font: "DM Sans", "Segoe UI", "Microsoft YaHei", sans-serif;
  --display: "Fraunces", "Palatino Linotype", "Microsoft YaHei", serif;
}}
* {{ box-sizing: border-box; }}
body {{
  margin: 0; min-height: 100vh; font-family: var(--font); color: var(--text); line-height: 1.5;
  background:
    radial-gradient(1100px 560px at 8% -8%, rgba(91, 156, 245, 0.14), transparent 55%),
    radial-gradient(900px 500px at 100% 0%, rgba(232, 121, 169, 0.10), transparent 50%),
    linear-gradient(165deg, var(--bg0), var(--bg1) 45%, #161a21);
}}
header {{
  padding: 1.35rem 1.5rem 1.1rem; border-bottom: 1px solid var(--panel-border);
  display: flex; flex-wrap: wrap; gap: .6rem 1.5rem; align-items: baseline; justify-content: space-between;
}}
header h1 {{ font-family: var(--display); font-size: 1.45rem; margin: 0; font-weight: 700; letter-spacing: -0.02em; }}
header .meta {{ color: var(--muted); font-size: .88rem; }}
main {{ padding: 1.15rem 1.5rem 2.5rem; display: grid; gap: 1.1rem; max-width: 1200px; margin: 0 auto; }}
.card {{
  background: var(--panel); border: 1px solid var(--panel-border);
  border-radius: var(--radius); box-shadow: var(--shadow); padding: 1rem 1.15rem 1.15rem;
}}
.card h2 {{
  font-size: .78rem; margin: 0 0 .75rem; color: var(--muted);
  font-weight: 600; letter-spacing: .08em; text-transform: uppercase;
}}
svg.timeline {{ width: 100%; height: 230px; display: block; }}
.legend {{
  display: flex; flex-wrap: wrap; gap: .45rem 1rem;
  font-size: .8rem; color: var(--muted); margin-top: .65rem; align-items: center;
}}
.legend label {{
  display: inline-flex; align-items: center; gap: .35rem; cursor: pointer; user-select: none;
}}
.legend input {{ accent-color: var(--me); }}
.legend i {{
  display: inline-block; width: 10px; height: 10px; border-radius: 50%;
  border: 2px solid transparent;
}}
.legend .me i {{ background: var(--me); }}
.legend .opp i {{ background: var(--opp); }}
.legend .hp i {{ background: var(--hp); border-radius: 2px; }}
.legend .wide i {{ background: transparent; border-color: var(--me); }}
.legend .up i {{
  width: 0; height: 0; border-radius: 0; background: transparent;
  border-left: 5px solid transparent; border-right: 5px solid transparent;
  border-bottom: 9px solid var(--up);
}}
.turn-nav {{
  display: inline-flex; align-items: center; gap: .35rem;
  margin-left: .5rem; vertical-align: middle;
  text-transform: none; letter-spacing: normal; font-weight: 500;
}}
.turn-nav button {{
  width: 2rem; height: 1.85rem; border-radius: 8px; border: 1px solid var(--panel-border);
  background: rgba(0,0,0,0.35); color: var(--text); font-size: 1rem; line-height: 1;
  cursor: pointer; font-family: inherit;
}}
.turn-nav button:hover:not(:disabled) {{ background: rgba(255,255,255,0.08); }}
.turn-nav button:disabled {{ opacity: 0.35; cursor: default; }}
.panels {{ display: grid; grid-template-columns: minmax(240px, 340px) 1fr; gap: 1.1rem; }}
@media (max-width: 860px) {{ .panels {{ grid-template-columns: 1fr; }} }}
.detail dl {{ margin: 0; display: grid; grid-template-columns: 4.5rem 1fr; gap: .4rem .75rem; font-size: .92rem; }}
.detail dt {{ color: var(--muted); }}
.detail dd {{ margin: 0; }}
.strength {{
  margin: 0 0 .85rem; padding: .75rem .85rem; background: rgba(0,0,0,0.28);
  border-radius: 10px; border-left: 3px solid var(--me);
}}
.strength.opp {{ border-left-color: var(--opp); margin-top: .65rem; }}
.strength .who {{ font-size: .72rem; letter-spacing: .06em; text-transform: uppercase; color: var(--muted); margin-bottom: .25rem; }}
.hdt {{ margin-top: .85rem; padding: .65rem .75rem; background: rgba(126, 182, 255, 0.08); border-radius: 10px; font-size: .9rem; }}
.boards {{ display: grid; gap: 1rem; }}
.boards .side {{
  padding: .75rem; background: rgba(0,0,0,0.22); border-radius: 12px; border: 1px solid var(--panel-border);
}}
.boards .label {{
  display: flex; flex-wrap: wrap; align-items: center; gap: .35rem .55rem;
  font-size: .9rem; margin-bottom: .55rem;
}}
.boards .label .who {{ font-weight: 700; }}
.boards .label .who.me {{ color: var(--me); }}
.boards .label .who.opp {{ color: var(--opp); }}
.boards .pill {{
  display: inline-flex; align-items: center; gap: .3rem;
  padding: .15rem .55rem; border-radius: 999px; font-size: .78rem;
  background: rgba(255,255,255,0.06); color: var(--muted);
}}
.boards .pill.pct.me {{ color: var(--me); background: var(--me-dim); }}
.boards .pill.pct.opp {{ color: var(--opp); background: var(--opp-dim); }}
.boards .pill.result.win {{ color: #0b1a12; background: var(--win); font-weight: 700; }}
.boards .pill.result.loss {{ color: #1a0b0b; background: var(--loss); font-weight: 700; }}
.boards .pill.result.tie {{ color: #1a1608; background: var(--tie); font-weight: 700; }}
.boards .pill.result.unk {{ color: var(--muted); }}
.boards img {{ max-width: 100%; height: auto; border-radius: 8px; background: #1a1f26; display: block; }}
.missing {{ color: var(--muted); font-size: .9rem; padding: .5rem 0; }}
select {{
  background: rgba(0,0,0,0.35); color: var(--text); border: 1px solid var(--panel-border);
  border-radius: 8px; padding: .3rem .55rem; font-family: inherit;
}}
.note {{ margin-top: .75rem; font-size: .85rem; color: var(--muted); white-space: pre-wrap; }}
.badge-row {{ display: flex; flex-wrap: wrap; gap: .4rem; margin: .55rem 0 .2rem; }}
.badge {{ font-size: .72rem; padding: .15rem .45rem; border-radius: 6px; background: rgba(255,255,255,0.06); color: var(--muted); }}
</style>
</head>
<body>
<header>
  <h1>{_esc(game.my_hero or "复盘")} · 名次 {place}</h1>
  <div class="meta">{_esc(game.game_id)} · BB {_esc(game.bb_version or "?")} · engine {_esc(game.engine_version or "?")}</div>
</header>
<main>
  <section class="card timeline-wrap">
    <h2>时间线</h2>
    <svg class="timeline" id="timeline" viewBox="0 0 900 230" preserveAspectRatio="none"></svg>
    <div class="legend">
      <label class="me"><input type="checkbox" id="togMe" checked/><i></i>己方分位</label>
      <label class="opp"><input type="checkbox" id="togOpp" checked/><i></i>对手分位</label>
      <label class="hp"><input type="checkbox" id="togHp" checked/><i></i>己方血量</label>
      <span class="wide" style="display:inline-flex;align-items:center;gap:.35rem"><i></i>宽区间（空心）</span>
      <span class="up" style="display:inline-flex;align-items:center;gap:.35rem"><i></i>己方升本</span>
      <span>底色条 = 战果</span>
    </div>
  </section>
  <div class="panels">
    <section class="card detail">
      <h2>回合详情
        <span class="turn-nav">
          <button type="button" id="turnPrev" title="上一回合" aria-label="上一回合">‹</button>
          <select id="turnSelect">{turns_opts}</select>
          <button type="button" id="turnNext" title="下一回合" aria-label="下一回合">›</button>
        </span>
      </h2>
      <div id="detailBody"></div>
    </section>
    <section class="card boards" id="boards"></section>
  </div>
</main>
<script type="application/json" id="model">{payload}</script>
<script>
const model = JSON.parse(document.getElementById('model').textContent);
const byTurn = Object.fromEntries(model.turns.map(t => [t.turn, t]));
let selected = model.turns.length ? model.turns[0].turn : null;
const seriesOn = {{ me: true, opp: true, hp: true }};

function resultColor(r) {{
  if (r === 'win') return '#3ecf8e';
  if (r === 'loss') return '#ef6b6b';
  if (r === 'tie') return '#e6c35c';
  return '#5f6368';
}}
function hasPct(st, p) {{
  return p != null && st !== 'missing' && st !== 'non_ready' && st !== 'insufficient';
}}
function invertResult(r) {{
  if (r === 'win') return 'loss';
  if (r === 'loss') return 'win';
  return r;
}}
function resultPill(result, damage, {{ forOpponent }}) {{
  const r = forOpponent ? invertResult(result) : result;
  if (r === 'win') return `<span class="pill result win">胜</span>`;
  if (r === 'loss') {{
    const d = damage == null ? '' : ('(-' + damage + ')');
    return `<span class="pill result loss">负${{d}}</span>`;
  }}
  if (r === 'tie') return `<span class="pill result tie">平</span>`;
  return `<span class="pill result unk">—</span>`;
}}

function drawSeries(parts, turns, xs, yScale, {{ pctKey, ciKey, stKey, color, wideHollow }}) {{
  let poly = [];
  turns.forEach((t, i) => {{
    if (!hasPct(t[stKey], t[pctKey])) return;
    poly.push(`${{xs[i]}},${{yScale(t[pctKey])}}`);
  }});
  if (poly.length >= 2) {{
    parts.push(`<polyline fill="none" stroke="${{color}}" stroke-width="2" stroke-opacity="0.5" points="${{poly.join(' ')}}"/>`);
  }}
  turns.forEach((t, i) => {{
    const x = xs[i];
    const st = t[stKey], p = t[pctKey], ok = hasPct(st, p);
    if (ok && t[ciKey]) {{
      const y1 = yScale(t[ciKey][0]), y2 = yScale(t[ciKey][1]);
      parts.push(`<line x1="${{x}}" x2="${{x}}" y1="${{y1}}" y2="${{y2}}" stroke="${{color}}" stroke-width="2" opacity="0.4"/>`);
    }}
    let fill = color, stroke = color, r = 5;
    if (st === 'wide' && wideHollow) fill = 'transparent';
    if (st === 'insufficient' || st === 'missing' || st === 'non_ready') {{
      fill = '#5f6368'; stroke = '#5f6368'; r = 3.5;
    }}
    const cy = ok ? yScale(p) : yScale(null);
    if (st === 'insufficient') {{
      parts.push(`<text x="${{x}}" y="${{cy+4}}" text-anchor="middle" fill="#5f6368" font-size="12" font-weight="700">×</text>`);
    }} else {{
      parts.push(`<circle cx="${{x}}" cy="${{cy}}" r="${{r}}" fill="${{fill}}" stroke="${{stroke}}" stroke-width="2"/>`);
    }}
  }});
}}

function drawHpSeries(parts, turns, xs, yHp) {{
  let poly = [];
  turns.forEach((t, i) => {{
    if (t.my_health == null) return;
    poly.push(`${{xs[i]}},${{yHp(t.my_health)}}`);
  }});
  if (poly.length >= 2) {{
    parts.push(`<polyline fill="none" stroke="#cbd5e1" stroke-width="2" stroke-dasharray="5 4" stroke-opacity="0.85" points="${{poly.join(' ')}}"/>`);
  }}
  turns.forEach((t, i) => {{
    if (t.my_health == null) return;
    const x = xs[i], y = yHp(t.my_health);
    parts.push(`<rect x="${{x-4}}" y="${{y-4}}" width="8" height="8" fill="#cbd5e1" stroke="#0f1216" stroke-width="1" rx="1"/>`);
  }});
}}

function drawTimeline() {{
  const svg = document.getElementById('timeline');
  const w = 900, h = 230, padL = 44, padR = 44, padT = 28, padB = 62;
  const turns = model.turns;
  if (!turns.length) {{ svg.innerHTML = ''; return; }}
  const xs = turns.map((_, i) => padL + (i / Math.max(turns.length - 1, 1)) * (w - padL - padR));
  const yScale = (p) => {{
    if (p == null) return padT + (h - padT - padB) / 2;
    return padT + (1 - p) * (h - padT - padB);
  }};
  const hps = turns.map(t => t.my_health).filter(v => v != null);
  const hpMax = Math.max(40, ...(hps.length ? hps : [40]));
  const hpMin = 0;
  const yHp = (hp) => padT + (1 - (hp - hpMin) / (hpMax - hpMin)) * (h - padT - padB);

  let parts = [];
  // selected turn column highlight
  const si = turns.findIndex(t => t.turn === selected);
  if (si >= 0) {{
    const x = xs[si];
    const band = (xs[1] - xs[0]) * 0.55 || 22;
    parts.push(`<rect x="${{x - band/2}}" y="${{padT - 6}}" width="${{band}}" height="${{h - padT - padB + 12}}" rx="6" fill="rgba(255,255,255,0.10)"/>`);
    parts.push(`<rect x="${{x - band/2}}" y="${{h - 34}}" width="${{band}}" height="26" rx="4" fill="rgba(91,156,245,0.28)"/>`);
  }}
  for (const g of [0, 0.5, 1]) {{
    const y = yScale(g);
    parts.push(`<line x1="${{padL}}" x2="${{w-padR}}" y1="${{y}}" y2="${{y}}" stroke="rgba(255,255,255,0.08)" stroke-dasharray="3 5"/>`);
    parts.push(`<text x="10" y="${{y+4}}" fill="#9aa3b2" font-size="11">${{Math.round(g*100)}}</text>`);
  }}
  // right axis HP ticks
  if (seriesOn.hp) {{
    for (const hv of [0, Math.round(hpMax/2), hpMax]) {{
      const y = yHp(hv);
      parts.push(`<text x="${{w-6}}" y="${{y+4}}" text-anchor="end" fill="#9aa3b2" font-size="10">${{hv}}</text>`);
    }}
  }}
  turns.forEach((t, i) => {{
    const x = xs[i];
    if (t.my_tavern_up) {{
      parts.push(`<line x1="${{x}}" x2="${{x}}" y1="${{padT}}" y2="${{h-padB}}" stroke="#7eb6ff" stroke-opacity="0.2" stroke-dasharray="4 3"/>`);
      parts.push(`<polygon points="${{x}},${{padT-14}} ${{x-6}},${{padT-4}} ${{x+6}},${{padT-4}}" fill="#7eb6ff"/>`);
      parts.push(`<text x="${{x}}" y="${{padT-18}}" text-anchor="middle" fill="#7eb6ff" font-size="10">升本</text>`);
    }}
  }});
  const barY = h - 36;
  turns.forEach((t, i) => {{
    const x = xs[i];
    const sel = t.turn === selected;
    parts.push(`<rect x="${{x-9}}" y="${{barY}}" width="18" height="8" rx="2" fill="${{resultColor(t.result)}}"/>`);
    parts.push(`<text x="${{x}}" y="${{h-8}}" text-anchor="middle" fill="${{sel ? '#f2efe8' : '#9aa3b2'}}" font-size="${{sel ? 12 : 11}}" font-weight="${{sel ? 700 : 400}}">T${{t.turn}}</text>`);
  }});
  if (seriesOn.opp) {{
    drawSeries(parts, turns, xs, yScale, {{
      pctKey: 'opp_percentile', ciKey: 'opp_ci95', stKey: 'opp_strength_state',
      color: '#e879a9', wideHollow: true
    }});
  }}
  if (seriesOn.me) {{
    drawSeries(parts, turns, xs, yScale, {{
      pctKey: 'percentile', ciKey: 'ci95', stKey: 'strength_state',
      color: '#5b9cf5', wideHollow: true
    }});
  }}
  if (seriesOn.hp) drawHpSeries(parts, turns, xs, yHp);
  turns.forEach((t, i) => {{
    parts.push(`<rect class="pt" data-turn="${{t.turn}}" x="${{xs[i]-14}}" y="${{padT}}" width="28" height="${{h-padT-padB}}" fill="transparent" style="cursor:pointer"/>`);
  }});
  svg.innerHTML = parts.join('');
  svg.querySelectorAll('.pt').forEach(el => {{
    el.addEventListener('click', () => selectTurn(Number(el.dataset.turn)));
  }});
}}

function tierLabel(t) {{ return t == null ? '酒馆 ?' : ('酒馆 T' + t); }}
function pctPill(p, st, cls) {{
  if (!hasPct(st, p)) return `<span class="pill">分位 —</span>`;
  return `<span class="pill pct ${{cls}}">分位 ${{(p*100).toFixed(1)}}%</span>`;
}}

function selectTurn(turn) {{
  selected = turn;
  document.getElementById('turnSelect').value = String(turn);
  const idx = model.turns.findIndex(t => t.turn === turn);
  document.getElementById('turnPrev').disabled = idx <= 0;
  document.getElementById('turnNext').disabled = idx < 0 || idx >= model.turns.length - 1;
  const t = byTurn[turn];
  if (!t) return;
  const hdt = [
    '胜 ' + (t.hdt_win == null ? '—' : (t.hdt_win*100).toFixed(1) + '%'),
    '平 ' + (t.hdt_tie == null ? '—' : (t.hdt_tie*100).toFixed(1) + '%'),
    '负 ' + (t.hdt_loss == null ? '—' : (t.hdt_loss*100).toFixed(1) + '%'),
  ].join(' · ');
  const dmg = t.damage == null ? '—' : t.damage;
  const note = t.note ? (`<div class="note">备注：${{typeof t.note === 'string' ? t.note : JSON.stringify(t.note)}}</div>`) : '';
  const upBadges = [
    t.my_tavern_up ? '<span class="badge">己方升本</span>' : '',
    t.opp_tavern_up ? '<span class="badge">对手升本</span>' : '',
  ].join('');
  const hpLine = t.my_health == null ? '—' : (t.my_health + ' 血');
  document.getElementById('detailBody').innerHTML = `
    <div class="strength"><div class="who">己方战力</div>${{t.detailText || '—'}}</div>
    <div class="strength opp"><div class="who">对手战力</div>${{t.oppDetailText || '—'}}</div>
    <div class="badge-row">${{upBadges}}</div>
    <dl>
      <dt>对手</dt><dd>${{t.opp_hero || '—'}}</dd>
      <dt>战果</dt><dd>${{t.result || '—'}}（伤 ${{dmg}}，来源 ${{t.result_source || '—'}}）</dd>
      <dt>血量</dt><dd>${{hpLine}}</dd>
      <dt>己方</dt><dd>${{t.level || '—'}} ${{(t.flags||[]).join(',')}} · ${{t.strength_state}} / ${{t.status}}</dd>
      <dt>对手</dt><dd>${{t.opp_level || '—'}} ${{(t.opp_flags||[]).join(',')}} · ${{t.opp_strength_state}}</dd>
    </dl>
    <div class="hdt"><strong>当场模拟（HDT）</strong><br/>${{hdt}}</div>
    ${{note}}`;
  document.getElementById('boards').innerHTML = `
    <div class="side">
      <div class="label">
        <span class="who me">己方</span>
        <span class="pill">${{tierLabel(t.my_tavern_tier)}}${{t.my_tavern_up ? ' · 升本' : ''}}</span>
        ${{pctPill(t.percentile, t.strength_state, 'me')}}
        ${{resultPill(t.result, t.damage, {{ forOpponent: false }})}}
      </div>
      ${{t.board_player ? `<img src="${{t.board_player}}" alt="player board"/>` : `<div class="missing">（无阵容图）</div>`}}
    </div>
    <div class="side">
      <div class="label">
        <span class="who opp">对手</span>
        <span class="pill">${{tierLabel(t.opp_tavern_tier)}}${{t.opp_tavern_up ? ' · 升本' : ''}}</span>
        ${{pctPill(t.opp_percentile, t.opp_strength_state, 'opp')}}
        ${{resultPill(t.result, t.damage, {{ forOpponent: true }})}}
      </div>
      ${{t.board_opponent ? `<img src="${{t.board_opponent}}" alt="opponent board"/>` : `<div class="missing">（无阵容图）</div>`}}
    </div>`;
  drawTimeline();
}}

function stepTurn(delta) {{
  const idx = model.turns.findIndex(t => t.turn === selected);
  if (idx < 0) return;
  const next = model.turns[idx + delta];
  if (next) selectTurn(next.turn);
}}

document.getElementById('turnSelect').addEventListener('change', (e) => selectTurn(Number(e.target.value)));
document.getElementById('turnPrev').addEventListener('click', () => stepTurn(-1));
document.getElementById('turnNext').addEventListener('click', () => stepTurn(1));
['togMe','togOpp','togHp'].forEach((id, i) => {{
  const key = ['me','opp','hp'][i];
  document.getElementById(id).addEventListener('change', (e) => {{
    seriesOn[key] = e.target.checked;
    drawTimeline();
  }});
}});
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
