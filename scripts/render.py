#!/usr/bin/env python3
"""
13F IDEA ENGINE — renderer (standalone / personal).

Reads data/ideas.json (multi-quarter, ~100 funds, with estimated cost basis /
return since) and writes a self-contained index.html at the repo root. Data is
inlined and minified, so it opens with a double-click — no server, no network.

    python3 scripts/build.py      # refresh the data
    python3 scripts/render.py     # rebuild index.html
    open index.html               # (macOS) view it

Standard library only.
"""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "ideas.json"
OUT = ROOT / "index.html"

PAGE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>13F Idea Engine</title>
<style>
  :root {
    --bg:#f4f6fb; --panel:#ffffff; --ink:#131a2b; --muted:#5a6478; --faint:#8b93a7;
    --line:#e6eaf2; --line2:#eef1f8;
    --accent:#4f46e5; --accent2:#7c3aed; --accent-soft:#eceafe;
    --pos:#0e9f6e; --pos-soft:#e3f7ef; --neg:#e11d48; --neg-soft:#fdeaef;
    --new:#7c3aed; --new-soft:#f0eafe;
    --hi:#10b981; --med:#f59e0b; --lo:#94a3b8;
    --shadow:0 1px 2px rgba(16,24,40,.05),0 4px 16px rgba(16,24,40,.05);
    --grad:linear-gradient(100deg,#4f46e5,#7c3aed 40%,#0ea5e9 100%);
  }
  @media (prefers-color-scheme: dark) {
    :root {
      --bg:#0b0e17; --panel:#141a27; --ink:#e9edf6; --muted:#9aa4bb; --faint:#697089;
      --line:#232b3d; --line2:#1b2233;
      --accent:#818cf8; --accent2:#a78bfa; --accent-soft:#20223f;
      --pos:#34d399; --pos-soft:#0f2a20; --neg:#fb7185; --neg-soft:#2e1520;
      --new:#a78bfa; --new-soft:#241a3a;
      --hi:#34d399; --med:#fbbf24; --lo:#64748b;
      --shadow:0 1px 2px rgba(0,0,0,.4);
      --grad:linear-gradient(100deg,#6366f1,#8b5cf6 40%,#38bdf8 100%);
    }
  }
  * { box-sizing:border-box; }
  html,body { margin:0; }
  body { background:var(--bg); color:var(--ink);
    font:14px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif; -webkit-font-smoothing:antialiased; }
  .wrap { max-width:1220px; margin:0 auto; padding:0 20px 90px; }
  a { color:var(--accent); text-decoration:none; }

  .hero { background:var(--grad); color:#fff; border-radius:0 0 20px 20px; margin:0 -20px 22px; padding:26px 24px 22px; box-shadow:var(--shadow); }
  .hero .eyebrow { font-size:11px; letter-spacing:.16em; text-transform:uppercase; font-weight:700; opacity:.85; }
  .hero h1 { font-size:27px; margin:5px 0 8px; letter-spacing:-.02em; }
  .hero .meta { font-size:13px; opacity:.92; }
  .hero .toolbar { display:flex; flex-wrap:wrap; gap:10px; align-items:center; margin-top:16px; }
  .hero select { background:rgba(255,255,255,.16); color:#fff; border:1px solid rgba(255,255,255,.35); border-radius:10px; padding:9px 13px; font-size:13px; font-weight:600; outline:none; }
  .hero select option { color:#131a2b; }
  .hero .qlabel { font-size:11px; letter-spacing:.1em; text-transform:uppercase; opacity:.85; font-weight:700; }

  .note { color:var(--muted); font-size:12.5px; max-width:860px; border-left:3px solid var(--line); padding-left:12px; margin:0 0 22px; }

  .stats { display:grid; grid-template-columns:repeat(auto-fit,minmax(150px,1fr)); gap:12px; margin:0 0 26px; }
  .stat { background:var(--panel); border:1px solid var(--line); border-radius:14px; padding:14px 16px; box-shadow:var(--shadow); position:relative; overflow:hidden; }
  .stat::before { content:""; position:absolute; left:0; top:0; bottom:0; width:4px; background:var(--sc,var(--accent)); }
  .stat .k { font-size:11px; letter-spacing:.06em; text-transform:uppercase; color:var(--faint); font-weight:700; }
  .stat .v { font-size:27px; font-weight:700; letter-spacing:-.02em; margin-top:3px; }
  .stat .s { font-size:12px; color:var(--muted); margin-top:1px; }

  .section-title { display:flex; align-items:baseline; gap:10px; margin:30px 0 12px; }
  .section-title h2 { font-size:16px; margin:0; letter-spacing:-.01em; }
  .section-title .c { color:var(--faint); font-size:13px; }

  .controls { display:flex; flex-wrap:wrap; gap:10px; align-items:center; margin-bottom:14px; }
  .controls input[type=search], .controls select { background:var(--panel); color:var(--ink); border:1px solid var(--line); border-radius:10px; padding:8px 11px; font-size:13px; outline:none; }
  .controls input[type=search] { min-width:200px; flex:1 1 200px; }
  .controls input:focus, .controls select:focus { border-color:var(--accent); box-shadow:0 0 0 3px var(--accent-soft); }
  .seg { display:inline-flex; border:1px solid var(--line); border-radius:10px; overflow:hidden; background:var(--panel); }
  .seg button { background:transparent; color:var(--muted); border:none; padding:8px 12px; font-size:13px; cursor:pointer; }
  .seg button.on { background:var(--grad); color:#fff; }
  .controls .spacer { flex:1; }
  .controls label.mini { color:var(--faint); font-size:12px; }

  .card { background:var(--panel); border:1px solid var(--line); border-radius:16px; box-shadow:var(--shadow); overflow:hidden; }
  .scroll { overflow-x:auto; }
  table { width:100%; border-collapse:collapse; min-width:640px; }
  thead th { text-align:left; font-size:11px; letter-spacing:.05em; text-transform:uppercase; color:var(--faint); font-weight:700; padding:11px 14px; border-bottom:1px solid var(--line); white-space:nowrap; }
  thead th.num { text-align:right; }
  tbody tr.idea { border-bottom:1px solid var(--line2); cursor:pointer; }
  tbody tr.idea:last-child { border-bottom:none; }
  tbody tr.idea:hover { background:var(--line2); }
  td { padding:11px 14px; vertical-align:middle; white-space:nowrap; }
  td.num { text-align:right; font-variant-numeric:tabular-nums; }
  .rank { color:var(--faint); font-variant-numeric:tabular-nums; width:34px; }
  .tk { font-weight:700; letter-spacing:-.01em; }
  .tk .cusip { font-weight:500; color:var(--faint); font-size:12px; }
  .issuer { color:var(--muted); font-size:12.5px; white-space:normal; }
  .chev { color:var(--faint); transition:transform .15s; display:inline-block; }
  tr.open .chev { transform:rotate(90deg); }

  .pill { display:inline-block; padding:2px 9px; border-radius:999px; font-size:11.5px; font-weight:600; white-space:nowrap; border:1px solid transparent; }
  .badge-new { background:var(--new-soft); color:var(--new); margin-left:6px; }
  .funds { display:inline-flex; align-items:center; gap:6px; justify-content:flex-end; }
  .funds-n { font-weight:700; font-variant-numeric:tabular-nums; }
  .dots { display:inline-flex; gap:2px; }
  .dot { width:7px; height:7px; border-radius:50%; background:var(--accent); opacity:.9; }
  .px { color:var(--muted); font-variant-numeric:tabular-nums; }
  .ret { font-weight:800; font-variant-numeric:tabular-nums; }
  .ret.up { color:var(--pos); } .ret.down { color:var(--neg); } .ret.flat { color:var(--faint); }

  .conv { display:flex; align-items:center; gap:9px; justify-content:flex-end; }
  .conv .bar { width:56px; height:8px; border-radius:5px; background:var(--line); overflow:hidden; }
  .conv .bar > i { display:block; height:100%; border-radius:5px; }
  .conv .val { font-variant-numeric:tabular-nums; font-weight:700; width:24px; text-align:right; }
  .conv.High .bar>i{background:linear-gradient(90deg,#10b981,#34d399);} .conv.Medium .bar>i{background:linear-gradient(90deg,#f59e0b,#fbbf24);} .conv.Low .bar>i{background:var(--lo);}

  tr.detail td { padding:0; background:var(--bg); }
  tr.detail .inner { padding:6px 14px 14px 48px; }
  .btable { width:100%; border-collapse:collapse; margin-top:4px; min-width:520px; }
  .btable th { text-align:left; font-size:10.5px; text-transform:uppercase; letter-spacing:.05em; color:var(--faint); font-weight:700; padding:6px 10px; }
  .btable td { padding:6px 10px; border-top:1px solid var(--line); font-size:12.5px; white-space:nowrap; }
  .btable td.num { text-align:right; font-variant-numeric:tabular-nums; }
  .act { font-weight:700; text-transform:uppercase; font-size:10.5px; letter-spacing:.04em; padding:1px 7px; border-radius:6px; }
  .act.new { color:var(--new); background:var(--new-soft); } .act.add { color:var(--pos); background:var(--pos-soft); }
  .up { color:var(--pos); font-weight:600; } .down { color:var(--neg); font-weight:600; }
  .style { font-size:11px; color:var(--faint); }

  /* manager leaderboard diverging bars */
  .lb td { padding:9px 12px; border-top:1px solid var(--line2); }
  .lb tr:hover { background:var(--line2); }
  .divbar { position:relative; height:16px; width:200px; }
  .divbar .mid { position:absolute; left:50%; top:-2px; bottom:-2px; width:1px; background:var(--line); }
  .divbar i { position:absolute; top:2px; height:12px; border-radius:3px; }
  .divbar i.pos { left:50%; background:linear-gradient(90deg,#10b981,#34d399); }
  .divbar i.neg { right:50%; background:linear-gradient(90deg,#fb7185,#e11d48); }

  .empty { padding:40px; text-align:center; color:var(--faint); }

  /* inaam impact-class toggle chips + per-idea badges */
  .chips { display:flex; flex-direction:column; gap:7px; margin-bottom:8px; }
  .chiprow { display:flex; align-items:center; gap:6px; flex-wrap:wrap; }
  .chiplabel { font-size:10.5px; text-transform:uppercase; letter-spacing:.06em; color:var(--faint); font-weight:700; width:104px; flex:none; }
  .chip { border:1px solid var(--line); background:var(--panel); color:var(--muted); border-radius:999px; padding:5px 12px; font-size:12.5px; font-weight:600; cursor:pointer; white-space:nowrap; }
  .chip:hover { border-color:hsl(var(--ch) 60% 55%); }
  .chip.on { background:hsl(var(--ch) 68% 48%); color:#fff; border-color:transparent; }
  .chipclear { font-size:12px; color:var(--accent); cursor:pointer; margin-left:4px; }
  .ibadge { display:inline-block; min-width:16px; text-align:center; border-radius:5px; padding:0 5px; font-size:10px; font-weight:800; margin-left:3px;
    background:hsl(var(--ch) 78% 92%); color:hsl(var(--ch) 55% 32%); }
  @media (prefers-color-scheme: dark) { .ibadge { background:hsl(var(--ch) 42% 22%); color:hsl(var(--ch) 72% 74%); } }

  footer { margin-top:36px; color:var(--faint); font-size:11.5px; line-height:1.6; }
  @media (max-width:720px){ .hide-sm{ display:none; } .hero h1{font-size:22px;} }
</style>
</head>
<body>
<div class="wrap">
  <div class="hero">
    <div class="eyebrow">13F Idea Engine</div>
    <h1 id="heroh1">What top funds are buying</h1>
    <div class="meta" id="submeta"></div>
    <div class="toolbar">
      <span class="qlabel">Quarter</span>
      <select id="period"></select>
      <span class="qlabel" id="periodinfo"></span>
    </div>
  </div>

  <div class="note" id="note"></div>
  <div class="stats" id="stats"></div>

  <div class="section-title"><h2>inaam impact classes</h2><span class="c" id="inaamsub">toggle a pillar / class to filter the ideas below</span></div>
  <div class="chips" id="inaamchips"></div>

  <div class="section-title"><h2>Ideas</h2><span class="c" id="ideacount"></span></div>
  <div class="controls">
    <input type="search" id="q" placeholder="Search ticker or issuer…" autocomplete="off">
    <select id="theme"></select>
    <div class="seg" id="minbuyers">
      <button data-v="2" class="on">2+ funds</button>
      <button data-v="3">3+ funds</button>
      <button data-v="1">All</button>
    </div>
    <div class="spacer"></div>
    <label class="mini" for="sort">Sort</label>
    <select id="sort">
      <option value="rank">Rank (funds · conviction)</option>
      <option value="ret">Return since (best)</option>
      <option value="retw">Return since (worst)</option>
      <option value="buyers">Most funds</option>
    </select>
  </div>
  <div class="card scroll">
    <table>
      <thead><tr>
        <th class="rank">#</th>
        <th>Name</th>
        <th class="hide-sm">Theme</th>
        <th class="num">Funds</th>
        <th class="num">Now</th>
        <th class="num">Target</th>
        <th class="num">Return</th>
        <th class="num hide-sm">Conv.</th>
      </tr></thead>
      <tbody id="rows"></tbody>
    </table>
    <div class="empty" id="empty" style="display:none">No ideas match your filters.</div>
  </div>

  <div class="section-title"><h2>Manager scorecard</h2><span class="c">value-weighted return of each fund's buys this quarter, to date</span></div>
  <div class="card scroll"><table class="lb"><thead><tr>
    <th class="rank">#</th><th>Fund</th><th class="num hide-sm">13F AUM</th><th class="hide-sm">Style</th>
    <th class="num">Buys</th><th class="num hide-sm">Positions</th><th class="num">Return since</th><th></th>
  </tr></thead><tbody id="lb"></tbody></table></div>

  <footer id="footer"></footer>
</div>

<script id="data" type="application/json">__DATA__</script>
<script>
const DATA = JSON.parse(document.getElementById('data').textContent);
const $ = s => document.querySelector(s);
const el = (t,c,h)=>{const e=document.createElement(t); if(c)e.className=c; if(h!=null)e.innerHTML=h; return e;};

const fmtMoney = v => { if(v==null) return '—'; const a=Math.abs(v), s=v<0?'-':'';
  if(a>=1e9) return s+'$'+(a/1e9).toFixed(2)+'B'; if(a>=1e6) return s+'$'+(a/1e6).toFixed(1)+'M';
  if(a>=1e3) return s+'$'+(a/1e3).toFixed(0)+'K'; return s+'$'+a; };
const fmtPx = v => v==null ? '—' : '$'+v.toLocaleString(undefined,{minimumFractionDigits:2,maximumFractionDigits:2});
const fmtPct = w => w==null ? '—' : (w*100).toFixed(2)+'%';
const fmtChg = c => c==null ? '' : (c>0?'+':'')+Math.round(c*100)+'%';
const retCls = r => r==null ? 'flat' : r>0.001 ? 'up' : r<-0.001 ? 'down' : 'flat';
const fmtRet = r => r==null ? '—' : (r>0?'+':'')+(r*100).toFixed(1)+'%';
function targetCell(i){
  if(i.target==null) return '<span class="px">—</span>';
  const u = i.upside==null ? '' : ` <span class="ret ${retCls(i.upside)}" style="font-size:11px">${fmtRet(i.upside)}</span>`;
  const tt = i.target_n ? ` title="${i.target_n} analysts"` : '';
  return `<span class="px"${tt}>${fmtPx(i.target)}</span>${u}`;
}

const THEME_HUE = { 'Green Energy & Decarbonisation':152,'Energy & Power':25,'Financials':42,
  'Healthcare':340,'Tech & Communications':255,'Industrials & Materials':210,'Consumer':280,'Other / review':220 };
const dark = matchMedia('(prefers-color-scheme: dark)').matches;
function themeStyle(t){ const h=THEME_HUE[t]??220; return dark
  ? `background:hsl(${h} 40% 20%);color:hsl(${h} 70% 78%);border-color:hsl(${h} 40% 30%)`
  : `background:hsl(${h} 80% 96%);color:hsl(${h} 55% 34%);border-color:hsl(${h} 70% 88%)`; }

let CUR = null, AUM = {};
let state = { q:'', theme:'', min:2, sort:'rank', inaam:new Set() };

const PILLAR_HUE = {Energy:150, Agriculture:200, Consumption:275, Waste:35, Health:340};
const INAAM = DATA.inaam_classes || [];
const INAAM_BY_KEY = {}; INAAM.forEach(c=>INAAM_BY_KEY[c.key]=c);
function inaamBadges(i){
  if(!i.inaam || !i.inaam.length) return '';
  return ' '+i.inaam.map(k=>{ const c=INAAM_BY_KEY[k]; if(!c) return '';
    const h=PILLAR_HUE[c.pillar]??220;
    return `<span class="ibadge" style="--ch:${h}" title="${c.pillar} · ${c.name} (Class ${c.key})">${k}</span>`; }).join('');
}
function renderChips(){
  const box=$('#inaamchips'); box.innerHTML='';
  const order=[], groups={};
  INAAM.forEach(c=>{ if(!groups[c.pillar]){groups[c.pillar]=[]; order.push(c.pillar);} groups[c.pillar].push(c); });
  order.forEach(p=>{
    const row=el('div','chiprow'); row.append(el('span','chiplabel',p));
    groups[p].forEach(c=>{
      const b=el('button','chip'+(state.inaam.has(c.key)?' on':'')); b.style.setProperty('--ch', PILLAR_HUE[p]??220);
      b.textContent=`${c.key} · ${c.name}`;
      b.onclick=()=>{ state.inaam.has(c.key)?state.inaam.delete(c.key):state.inaam.add(c.key); b.classList.toggle('on'); render(); };
      row.append(b);
    });
    box.append(row);
  });
  const clr=el('span','chipclear','clear'); clr.onclick=()=>{ state.inaam.clear(); renderChips(); render(); };
  box.lastChild.append(clr);
}
const NT = DATA.n_managers_total || 95;
const PC = DATA.period_counts || {};
$('#heroh1').textContent = `What ${NT} top funds are buying`;

const psel = $('#period');
DATA.periods.forEach(p=>{ const b=DATA.by_period[p]; const c=PC[p]??b.n_managers;
  psel.append(new Option(`${b.prev} → ${p}   (${c}/${NT} funds filed)`, p)); });
psel.value = DATA.default_period;
psel.addEventListener('change', ()=>loadPeriod(psel.value));

const aumStr = n => AUM[n]!=null ? `$${AUM[n].toLocaleString()}M` : '';

function median(xs){ if(!xs.length) return null; const s=[...xs].sort((a,b)=>a-b); const m=s.length>>1;
  return s.length%2 ? s[m] : (s[m-1]+s[m])/2; }

function loadPeriod(p){
  CUR = DATA.by_period[p];
  AUM = {}; CUR.managers.forEach(m=>AUM[m.name]=m.aum_m);
  const filed = PC[p] ?? CUR.n_managers;
  $('#submeta').textContent = `${filed} of ${NT} funds filed this quarter · ${CUR.n_ideas} ideas · ${CUR.prev} → ${p}`;
  $('#periodinfo').textContent = `generated ${DATA.generated_at}`;
  $('#note').textContent = DATA.note || '';

  const rets = CUR.ideas.filter(i=>i.ret!=null).map(i=>i.ret);
  const med = median(rets);
  const stats = [
    ['Funds reporting', CUR.n_managers, `of ${NT} tracked`, 'var(--accent)'],
    ['Consensus (3+)', CUR.ideas.filter(i=>i.n_buyers>=3).length, 'bought by 3+ funds', 'var(--new)'],
    ['Ideas surfaced', CUR.n_ideas, `${CUR.ideas.filter(i=>i.ticker).length} priced`, 'var(--med)'],
    ['Median return since', fmtRet(med), 'these buys, to today', med==null?'var(--lo)':med>=0?'var(--pos)':'var(--neg)'],
  ];
  const sc=$('#stats'); sc.innerHTML='';
  stats.forEach(([k,v,s,col])=>{ const c=el('div','stat'); c.style.setProperty('--sc',col);
    c.append(el('div','k',k), el('div','v',v), el('div','s',s)); sc.append(c); });

  const themes=[...new Set(CUR.ideas.map(i=>i.theme))].sort();
  const t=$('#theme'); const keep=state.theme; t.innerHTML=''; t.append(new Option('All themes',''));
  themes.forEach(x=>t.append(new Option(x.replace(' / review',''), x)));
  if([...t.options].some(o=>o.value===keep)) t.value=keep; else state.theme='';

  renderLeaderboard();
  render();
}

function score(i){
  switch(state.sort){
    case 'ret':  return i.ret==null? 1e9 : -i.ret;
    case 'retw': return i.ret==null? 1e9 :  i.ret;
    case 'buyers': return -(i.n_buyers*1000+i.conviction);
    default: return -(i.n_buyers*100000 + i.conviction*100 + i.sum_weight);
  }
}

function render(){
  const q=state.q.toLowerCase();
  let list = CUR.ideas.filter(i=>
    i.n_buyers>=state.min &&
    (!state.theme || i.theme===state.theme) &&
    (!state.inaam.size || (i.inaam||[]).some(c=>state.inaam.has(c))) &&
    (!q || (i.ticker&&i.ticker.toLowerCase().includes(q)) || (i.issuer||'').toLowerCase().includes(q)));
  list.sort((a,b)=>score(a)-score(b));
  $('#ideacount').textContent = `${list.length} shown`;
  const tb=$('#rows'); tb.innerHTML=''; $('#empty').style.display = list.length ? 'none':'block';

  list.slice(0,400).forEach((i,idx)=>{
    const tr=el('tr','idea');
    const nameCell = `<span class="chev">›</span> <span class="tk">${i.ticker||('<span class="cusip">'+i.cusip+'</span>')}</span>`
      + (i.has_new?'<span class="pill badge-new">NEW</span>':'') + inaamBadges(i) + `<div class="issuer">${i.issuer||''}</div>`;
    const dots = Array(Math.min(i.n_buyers,5)).fill('<span class="dot"></span>').join('');
    const pct = Math.max(4, i.conviction);
    tr.innerHTML =
      `<td class="rank">${idx+1}</td>`+
      `<td>${nameCell}</td>`+
      `<td class="hide-sm"><span class="pill" style="${themeStyle(i.theme)}">${(i.theme||'').replace(' / review','')}</span></td>`+
      `<td class="num"><span class="funds"><span class="dots">${dots}</span><span class="funds-n">${i.n_buyers}</span></span></td>`+
      `<td class="num px">${fmtPx(i.cur_price)}</td>`+
      `<td class="num">${targetCell(i)}</td>`+
      `<td class="num"><span class="ret ${retCls(i.ret)}">${fmtRet(i.ret)}</span></td>`+
      `<td class="num hide-sm"><div class="conv ${i.conviction_label}"><div class="bar"><i style="width:${pct}%"></i></div><span class="val">${i.conviction}</span></div></td>`;
    const detail=el('tr','detail'); detail.style.display='none';
    detail.innerHTML=`<td colspan="8"><div class="inner"></div></td>`;
    tr.addEventListener('click',()=>{ const open=detail.style.display==='none';
      detail.style.display=open?'':'none'; tr.classList.toggle('open',open);
      if(open&&!detail.dataset.built){ buildDetail(detail.querySelector('.inner'), i); detail.dataset.built='1'; }});
    tb.append(tr,detail);
  });
}

function buildDetail(box,i){
  const now = i.cur_price!=null ? `Now <b>${fmtPx(i.cur_price)}</b>` : '';
  const tgt = i.target!=null ? ` · analyst target <b>${fmtPx(i.target)}</b> (${fmtRet(i.upside)} upside)` : '';
  box.append(el('div',null,`<div style="font-size:12px;color:var(--muted);margin:2px 0 8px">`+
    `${now}${tgt}. Est. buy = avg price the quarter each fund first opened this position `+
    `(“≥” = opened before our data window); $ gain uses each fund's reported share count.</div>`));
  const t=el('table','btable');
  t.innerHTML='<thead><tr><th>Fund</th><th>Action</th><th>Opened</th><th class="num">Est. buy</th>'+
    '<th class="num">Return</th><th class="num">Position</th><th class="num">% book</th>'+
    '<th class="num">Δ shares</th><th class="num">Est. $ gain</th></tr></thead>';
  const tb=el('tbody');
  i.buyers.forEach(b=>{
    const aum = AUM[b.manager]!=null ? ` <span style="color:var(--faint)">(${aumStr(b.manager)})</span>` : '';
    const opened = b.opened ? (b.opened_before?'≥ ':'')+b.opened : '—';
    const chg = b.chg==null?'':`<span class="${b.chg>0?'up':'down'}">${fmtChg(b.chg)}</span>`;
    const g = b.est_gain==null?'—':`<span class="${b.est_gain>=0?'up':'down'}">${fmtMoney(b.est_gain)}</span>`;
    const r=el('tr'); r.innerHTML=
      `<td><b>${b.manager}</b>${aum}</td>`+
      `<td><span class="act ${b.action}">${b.action}</span></td>`+
      `<td class="style">${opened}</td>`+
      `<td class="num px">${fmtPx(b.est_entry)}</td>`+
      `<td class="num"><span class="ret ${retCls(b.ret)}">${fmtRet(b.ret)}</span></td>`+
      `<td class="num">${fmtMoney(b.value)}</td>`+
      `<td class="num">${fmtPct(b.weight)}</td>`+
      `<td class="num">${chg}</td>`+
      `<td class="num">${g}</td>`;
    tb.append(r);
  });
  t.append(tb); box.append(t);
}

function renderLeaderboard(){
  const ms=[...CUR.managers];
  const maxAbs = Math.max(0.01, ...ms.filter(m=>m.ret!=null).map(m=>Math.abs(m.ret)));
  const tb=$('#lb'); tb.innerHTML='';
  ms.forEach((m,idx)=>{
    const r=m.ret;
    const w = r==null?0:Math.min(50, Math.abs(r)/maxAbs*50);
    const bar = r==null ? '' : (r>=0
      ? `<i class="pos" style="width:${w}%"></i>` : `<i class="neg" style="width:${w}%"></i>`);
    const tr=el('tr');
    tr.innerHTML =
      `<td class="rank">${idx+1}</td>`+
      `<td><b>${m.name}</b></td>`+
      `<td class="num hide-sm">${m.aum_m!=null?'$'+m.aum_m.toLocaleString()+'M':'—'}</td>`+
      `<td class="hide-sm style">${(m.tag||'').replace(/-/g,' ')}</td>`+
      `<td class="num">${m.buys||0}</td>`+
      `<td class="num hide-sm">${m.positions}</td>`+
      `<td class="num"><span class="ret ${retCls(r)}">${fmtRet(r)}</span></td>`+
      `<td><div class="divbar"><div class="mid"></div>${bar}</div></td>`;
    tb.append(tr);
  });
}

$('#q').addEventListener('input',e=>{state.q=e.target.value; render();});
$('#theme').addEventListener('change',e=>{state.theme=e.target.value; render();});
$('#sort').addEventListener('change',e=>{state.sort=e.target.value; render();});
$('#minbuyers').addEventListener('click',e=>{ const b=e.target.closest('button'); if(!b) return;
  [...e.currentTarget.children].forEach(x=>x.classList.remove('on')); b.classList.add('on'); state.min=+b.dataset.v; render(); });

$('#footer').innerHTML =
  'Source: SEC EDGAR 13F-HR (long-only, US-listed) + OpenFIGI (CUSIP→ticker) + Yahoo (daily prices) + '+
  (DATA.targets_source==='finnhub'?'Finnhub':'Yahoo')+' (analyst targets). '+
  'Each fund\'s est. buy = average daily close over the quarter that fund first opened the position — 13F discloses no trade date or price, so this is an approximation ("≥" = opened before our data window). '+
  'AUM = the fund\'s US-listed 13F book value (excludes cash, bonds, shorts, non-US). Return is to the latest close. 13F lags up to 45 days. Idea generator, not investment advice.';

renderChips();
loadPeriod(DATA.default_period);
</script>
</body>
</html>
"""


def main():
    if not DATA.exists():
        raise SystemExit(f"missing {DATA} — run scripts/build.py first")
    data = json.loads(DATA.read_text())
    payload = json.dumps(data, separators=(",", ":")).replace("<", "\\u003c")
    OUT.write_text(PAGE.replace("__DATA__", payload))
    kb = OUT.stat().st_size / 1024
    print(f"Wrote {OUT}  ({kb:.0f} KB, {len(data.get('periods', []))} quarters)")
    print(f"Open it:  open {OUT}")


if __name__ == "__main__":
    main()
