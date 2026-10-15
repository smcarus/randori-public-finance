"""Dashboard: one self-contained HTML page with a colour-coded risk map and a page per country.

    python -m sovrisk.dashboard --out outputs/dashboard.html

Open the file in a browser. The numbers and the world map outline are embedded. plotly.js is embedded too when the
`plotly` Python package is installed (pip install -e .[dashboard]); otherwise the page loads it from cdnjs.
"""
import argparse
import json
import math
from datetime import date
from pathlib import Path

import numpy as np

from . import load_config, run_model
from .backtest import pd_backtest
from .config import ROOT
from .decisions import bond_table, default_table, pri_book, _rows
from .montecarlo import simulate
from .levers import lever_table, load_levers
from .pri import PERILS

ISO3 = {'Argentina': 'ARG', 'Belize': 'BLZ', 'Chile': 'CHL', 'Colombia': 'COL', 'Ecuador': 'ECU', 'El Salvador': 'SLV',
        'Guatemala': 'GTM', 'Honduras': 'HND', 'Nicaragua': 'NIC', 'Nigeria': 'NGA', 'Peru': 'PER', 'Senegal': 'SEN',
        'Tanzania': 'TZA', 'Venezuela': 'VEN', 'Zambia': 'ZMB', 'Zimbabwe': 'ZWE', 'Bolivia': 'BOL', 'Brazil': 'BRA',
        'Mexico': 'MEX', 'Paraguay': 'PRY', 'Uruguay': 'URY', 'Panama': 'PAN', 'Costa Rica': 'CRI', 'Jamaica': 'JAM',
        'Dominican Republic': 'DOM', 'Ghana': 'GHA', 'Kenya': 'KEN', 'Ethiopia': 'ETH', 'Egypt': 'EGY', 'South Africa': 'ZAF',
        'Angola': 'AGO', 'Mozambique': 'MOZ', 'Uganda': 'UGA', "Cote d'Ivoire": 'CIV', 'Cameroon': 'CMR'}
PERIL_NAMES = {'ci': 'Inconvertibility', 'expropriation': 'Expropriation', 'political_violence': 'Political violence',
               'breach': 'Breach of contract', 'nhsfo': 'Non-honoring'}
CDN = 'https://cdnjs.cloudflare.com/ajax/libs/plotly.js/2.35.2/plotly.min.js'
ASSETS = Path(__file__).parent / 'assets'


def _plotly_tag():
    try:
        import plotly
        js = (Path(plotly.__file__).parent / 'package_data' / 'plotly.min.js').read_text(encoding='utf-8')
        return '<script>' + js.replace('</script', '<\\/script') + '</script>'
    except (ImportError, OSError):
        return f'<script src="{CDN}"></script>'


def _clean(x):
    if isinstance(x, dict):
        return {str(k): _clean(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_clean(v) for v in x]
    if isinstance(x, np.ndarray):
        return _clean(x.tolist())
    if isinstance(x, (np.floating, float)):
        return None if math.isnan(x) or math.isinf(x) else float(x)
    if isinstance(x, np.integer):
        return int(x)
    return x


def grade(s):
    return None if s is None else min(10, int(s // 10) + 1)


def dashboard_data(cfg, root=ROOT):
    """Everything the page shows, as plain numbers. Model scores where available, preliminary scores otherwise."""
    m = run_model(cfg)
    names = cfg.rulebook['pillars']
    dt = default_table(cfg, m, root)
    mc = simulate(cfg, m)
    pols = {p['policy_id']: p for p in _rows('pri_policies.csv', root)}
    book = pri_book(cfg, m, dt, root)
    bonds = {b['bond_id']: b for b in _rows('bonds.csv', root)}
    btab = bond_table(cfg, root)
    levers = load_levers(cfg, root)
    lt = lever_table(cfg, levers, m, root)
    countries = {}
    for cn in cfg.countries:
        r = m[cn]
        sc = r['base']['score']
        used = sc if sc else cfg.preliminary[cn]
        sens = sorted(((iid, v) for iid, v in r['sensitivity'].items() if v), key=lambda t: -t[1])[:10]
        ind = r['base']['indicators']
        countries[cn] = {
            'iso3': ISO3.get(cn), 'region': cfg.regions[cn], 'score': used, 'grade': grade(used),
            'source': 'Model' if sc else 'Preliminary', 'preliminary': cfg.preliminary[cn],
            'cases': {c: {'score': r[c]['score'], 'grade': r[c]['grade'],
                          'pillars': [r[c]['pillars'][p]['final'] for p in range(1, 8)]} for c in ('base', 'best', 'worst')},
            'sensitivity': [{'id': iid, 'pillar': ind[iid]['pillar'], 'value': ind[iid]['value'], 'score': ind[iid]['score'],
                             'points': v} for iid, v in sens],
            'default': {k: dt[cn][k] for k in ('scorecard_pd', 'fitted_pd', 'blended_pd', 'pd_low', 'pd_high', 'market_pd',
                                               'flag')},
            'es_share': mc['es_share'].get(cn), 'es_contribution': mc['es_contribution'].get(cn),
            'policies': [{'id': pid, 'sector': pols[pid]['sector'], 'term': pols[pid]['term_years'], 'limit': pols[pid]['limit'],
                          'note': pols[pid]['note'], 'premium_bps': 1e4 * res['total']['premium_rate'],
                          'claim_prob_term': res['total']['any_claim_prob_term'],
                          'perils': {PERIL_NAMES[k]: {'el': v['el_total'], 'claim_prob_term': v['claim_prob_term'],
                                                      'premium_bps': 1e4 * v['premium_rate']}
                                     for k, v in res['perils'].items()}}
                         for pid, res in book.items() if pols[pid]['country'] == cn],
            'bonds': [{'id': bid, 'note': bonds[bid]['note'], 'sz_haircut': v['npv_haircut_sz'],
                       'market_haircut': v['market_haircut_ct'], 'recovery': v['recovery_per_100'],
                       'deal_months': v['deal_months'], 'recovery_at_default': v['recovery_at_default'],
                       'holdout_risk': v['holdout_risk']} for bid, v in btab.items() if bonds[bid]['country'] == cn],
            'levers': lt[cn],
        }
    mcs = cfg.settings['monte_carlo']
    bt = pd_backtest(cfg)
    return _clean({
        'as_of': date.today().isoformat(), 'pillar_names': [names[p] for p in range(1, 8)], 'countries': countries,
        'weights': [cfg.settings['pillar_weights'][p] for p in range(1, 8)], 'smallw': cfg.settings['smallw'],
        'levers': [{k: lv[k] for k in ('id', 'category', 'label', 'detail')} for lv in levers['levers']],
        'lever_categories': levers['categories'],
        'portfolio': {'confidence_levels': mcs['confidence_levels'], 'var': mc['var'], 'es': mc['es'],
                      'expected_loss': mc['expected_loss'], 'histogram': mc['histogram'], 'max_loss': mc['max_loss'],
                      'default_counts': mc['default_counts'], 'trials': len(mc['total_loss']),
                      'exposure': sum(cfg.mc_portfolio[c]['exposure'] for c in cfg.countries)},
        'backtest': {'brier': bt.get('brier'), 'skill': bt.get('skill'), 'n': bt.get('n'), 'bins': bt.get('bins', []),
                     'synthetic': bool(cfg.settings['backtest'].get('include_synthetic'))},
    })


def render(data, title='Sovereign Risk Dashboard'):
    world = (ASSETS / 'world_110m.json').read_text(encoding='utf-8')
    page = PAGE.replace('__TITLE__', title).replace('__DATA__', json.dumps(data).replace('</', '<\\/'))
    page = page.replace('__WORLD__', world)
    return page.replace('<script src="__CDN__"></script>', _plotly_tag())


def main(argv=None):
    ap = argparse.ArgumentParser(description='Write the sovereign risk dashboard (HTML).')
    ap.add_argument('--root', default=None, help='repository root holding rulebook/ and data/')
    ap.add_argument('--out', default='outputs/dashboard.html')
    a = ap.parse_args(argv)
    root = Path(a.root) if a.root else ROOT
    cfg = load_config(root)
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render(dashboard_data(cfg, root)), encoding='utf-8')
    print(f'Dashboard written to {out}')


PAGE = r'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__</title>
<script src="__CDN__"></script>
<style>
:root{--bg:#f6f7f9;--card:#fff;--ink:#1d2430;--muted:#5b6575;--line:#dde2e8;--warn:#8a5a00;--warnbg:#fff4d6}
@media (prefers-color-scheme: dark){:root{--bg:#12161c;--card:#1b2129;--ink:#e6e9ee;--muted:#9aa4b2;--line:#2c343f;--warn:#ffd27a;--warnbg:#3a2e12}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:14px/1.45 system-ui,-apple-system,Segoe UI,Arial,sans-serif}
header{padding:16px;border-bottom:1px solid var(--line);background:var(--card)}
h1{font-size:20px;margin:0 0 4px}h2{font-size:15px;margin:0 0 8px}.muted{color:var(--muted)}
.banner{background:var(--warnbg);color:var(--warn);padding:8px 16px;font-weight:600;font-size:13px}
main{max-width:1200px;margin:0 auto;padding:16px}.grid{display:grid;gap:16px;grid-template-columns:repeat(auto-fit,minmax(340px,1fr))}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:14px;min-width:0}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(130px,1fr));gap:10px;margin-bottom:16px}
.kpi{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:10px}.kpi b{display:block;font-size:22px}
.kpi span{color:var(--muted);font-size:12px}select{font:inherit;padding:6px 8px;border-radius:6px;border:1px solid var(--line);background:var(--card);color:var(--ink)}
table{width:100%;border-collapse:collapse;font-size:13px}td,th{text-align:left;padding:5px 6px;border-bottom:1px solid var(--line)}th{color:var(--muted);font-weight:600}
.tag{display:inline-block;padding:1px 6px;border-radius:4px;font-size:12px;background:var(--warnbg);color:var(--warn)}
.lev{margin-bottom:16px;border:2px solid #2e7d5b}.levhead{display:flex;justify-content:space-between;align-items:center;gap:8px;flex-wrap:wrap}
button{font:inherit;padding:5px 10px;border-radius:6px;border:1px solid var(--line);background:var(--card);color:var(--ink);cursor:pointer}
.levgrid{display:grid;gap:14px;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));margin-top:10px}.levcat h3{font-size:13px;margin:0 0 6px;color:var(--muted);text-transform:uppercase;letter-spacing:.04em}
.tog{display:grid;grid-template-columns:auto 1fr;gap:8px;align-items:start;padding:7px 8px;border:1px solid var(--line);border-radius:8px;margin-bottom:6px;cursor:pointer}
.tog.on{border-color:#2e7d5b;background:rgba(46,125,91,.08)}.tog input{position:absolute;opacity:0}.tog small{display:block;color:var(--muted);font-size:12px}
.sw{width:34px;height:20px;border-radius:10px;background:var(--line);position:relative;margin-top:1px;transition:.15s}.sw:after{content:'';position:absolute;top:2px;left:2px;width:16px;height:16px;border-radius:50%;background:#fff;transition:.15s}
.tog.on .sw{background:#2e7d5b}.tog.on .sw:after{left:16px}.badge{display:inline-block;margin:2px 0;font-size:12px;padding:1px 6px;border-radius:4px;background:rgba(46,125,91,.12);color:#2e7d5b;font-weight:600}.badge.none{background:var(--line);color:var(--muted);font-weight:400}
.tog:focus-within{outline:2px solid #2e7d5b}.kpi em{display:block;font-style:normal;font-size:12px;color:#2e7d5b;font-weight:600}
.chart{width:100%;height:320px}#map{height:430px}.row{display:flex;gap:12px;align-items:center;flex-wrap:wrap;margin:18px 0 12px}
</style></head><body>
<div class="banner">FOR RESEARCH PURPOSES ONLY. CONFIDENTIAL. Untested, preliminary and illustrative. Not investment advice and not a credit rating.</div>
<header><h1>__TITLE__</h1><div class="muted" id="sub"></div></header>
<main>
<div class="card"><h2>Risk map</h2><div class="muted">Colour shows the country score (higher is riskier). Click a country to open its page.</div><div id="map"></div></div>
<div class="grid" style="margin-top:16px">
<div class="card"><h2>Countries ranked</h2><div id="rank" class="chart" style="height:420px"></div></div>
<div class="card"><h2>Portfolio loss (Monte Carlo)</h2><div id="mcsum" class="muted"></div><div id="hist" class="chart"></div></div>
</div>
<div class="row"><h2 style="margin:0" id="cname"></h2><select id="pick"></select><span id="csrc"></span></div>
<div class="kpis" id="kpis"></div>
<div class="card lev"><div class="levhead"><h2 style="margin:0">Stability levers</h2><div><button id="lvall">All on</button> <button id="lvnone">Reset</button></div></div>
<div class="muted">Switch on measures that lower risk and add stability. Each badge shows that lever's effect on its own for this country. Magnitudes are illustrative (rulebook/levers.yaml).</div>
<div id="levres" class="kpis" style="margin:12px 0 0"></div>
<div id="levgrid" class="levgrid"></div>
<h2 style="margin-top:14px">Effect of each lever on the country score</h2><div id="levimpact" class="chart" style="height:420px"></div>
<div id="levnote" class="muted"></div></div>
<div class="grid">
<div class="card"><h2>Pillar scores: base, best, worst and with levers</h2><div id="pillars" class="chart"></div></div>
<div class="card"><h2>Pillar profile</h2><div id="radar" class="chart"></div></div>
<div class="card"><h2>Most sensitive indicators</h2><div class="muted">Country-score points per 25-point move in the indicator score</div><div id="sens" class="chart"></div></div>
<div class="card"><h2>Default probability</h2><div id="pd" class="chart"></div><div id="pdnote" class="muted"></div></div>
<div class="card"><h2>Political risk insurance</h2><div id="pri"></div><div id="pric" class="chart"></div></div>
<div class="card"><h2>Restructuring</h2><div id="bonds"></div></div>
</div>
<div class="card" style="margin-top:16px"><h2>Calibration (backtest)</h2><div id="calnote" class="muted"></div><div id="cal" class="chart"></div></div>
</main>
<script>window.PlotlyGeoAssets = {topojson: {world_110m: __WORLD__}};</script>
<script>
const D = __DATA__;
const dark = matchMedia('(prefers-color-scheme: dark)').matches;
const ink = dark ? '#e6e9ee' : '#1d2430', grid = dark ? '#2c343f' : '#dde2e8';
const base = {paper_bgcolor:'rgba(0,0,0,0)', plot_bgcolor:'rgba(0,0,0,0)', font:{color:ink, size:12},
  margin:{l:40,r:10,t:10,b:40}, xaxis:{gridcolor:grid}, yaxis:{gridcolor:grid}, legend:{orientation:'h', y:-0.2}};
const L = o => Object.assign({}, base, o), cfg = {displayModeBar:false, responsive:true};
const scale = [[0,'#1a9850'],[0.3,'#a6d96a'],[0.5,'#fee08b'],[0.7,'#f46d43'],[1,'#a50026']];
const pct = (x,d=1) => x==null ? 'n/a' : (100*x).toFixed(d)+'%', num = (x,d=1) => x==null ? 'n/a' : x.toFixed(d);
const short = D.pillar_names.map(x=>x.split(' ')[0]);
const names = Object.keys(D.countries).sort((a,b)=>D.countries[b].score-D.countries[a].score);
document.getElementById('sub').textContent = `${names.length} countries · generated ${D.as_of} · model scores where available, preliminary scores otherwise`;

const withIso = names.filter(n=>D.countries[n].iso3);
Plotly.newPlot('map', [{type:'choropleth', locationmode:'ISO-3', locations:withIso.map(n=>D.countries[n].iso3),
  z:withIso.map(n=>D.countries[n].score), text:withIso, customdata:withIso.map(n=>[D.countries[n].grade, D.countries[n].source]),
  hovertemplate:'<b>%{text}</b><br>Score %{z:.1f} · grade %{customdata[0]}<br>%{customdata[1]}<extra></extra>',
  colorscale:scale, zmin:0, zmax:100, marker:{line:{color:dark?'#12161c':'#fff', width:0.5}}, colorbar:{title:{text:'Score'}, thickness:12}}],
  L({margin:{l:0,r:0,t:0,b:0}, geo:{showframe:false, showcoastlines:false, projection:{type:'natural earth'},
  bgcolor:'rgba(0,0,0,0)', landcolor:dark?'#2c343f':'#e9ecf0', showland:true, showcountries:true, countrycolor:dark?'#3a4350':'#cfd5dc',
  lataxis:{range:[-58,40]}, lonaxis:{range:[-120,60]}}}), cfg);
document.getElementById('map').on('plotly_click', e => show(e.points[0].text));

const rk = names.slice().reverse();
Plotly.newPlot('rank', [{type:'bar', orientation:'h', y:rk, x:rk.map(n=>D.countries[n].score),
  marker:{color:rk.map(n=>D.countries[n].score), colorscale:scale, cmin:0, cmax:100},
  text:rk.map(n=>D.countries[n].source==='Model'?'model':'prelim'), textposition:'inside', insidetextanchor:'start',
  hovertemplate:'%{y}: %{x:.1f}<extra></extra>'}], L({margin:{l:95,r:10,t:10,b:30}, xaxis:{range:[0,100], gridcolor:grid}}), cfg);
document.getElementById('rank').on('plotly_click', e => show(e.points[0].y));

const P = D.portfolio, w = P.max_loss/P.histogram.length;
document.getElementById('mcsum').innerHTML = P.confidence_levels.map((c,i)=>`VaR ${pct(c)} <b>${num(P.var[i],2)}</b> · ES <b>${num(P.es[i],2)}</b>`).join('<br>')
  + `<br>Expected loss <b>${num(P.expected_loss,2)}</b> of ${num(P.exposure,0)} exposure (US$m) · ${P.trials} trials`;
Plotly.newPlot('hist', [{type:'bar', x:P.histogram.map((_,i)=>(i+0.5)*w), y:P.histogram, width:w*0.95, marker:{color:'#4c78a8'},
  hovertemplate:'Loss ≈ %{x:.1f}: %{y} trials<extra></extra>'}],
  L({xaxis:{title:{text:'Portfolio loss (US$m)'}, gridcolor:grid}, yaxis:{title:{text:'Trials'}, type:'log', gridcolor:grid}}), cfg);

const sel = document.getElementById('pick');
names.forEach(n => sel.add(new Option(n, n))); sel.onchange = () => show(sel.value);

function show(n){
  const c = D.countries[n]; if(!c) return; sel.value = n; cur = n;
  document.getElementById('cname').textContent = n;
  document.getElementById('csrc').innerHTML = c.source==='Model' ? '' : '<span class="tag">Preliminary score only: no model inputs yet</span>';
  const k = [['Score', num(c.score)], ['Grade', c.grade], ['Best / worst', `${num(c.cases.best.score)} / ${num(c.cases.worst.score)}`],
    ['Default PD (blended)', pct(c.default.blended_pd,2)], ['Market-implied PD', pct(c.default.market_pd,2)],
    ['Share of portfolio ES', pct(c.es_share)]];
  document.getElementById('kpis').innerHTML = k.map(([a,b])=>`<div class="kpi"><span>${a}</span><b>${b}</b></div>`).join('');
  const cols = {base:'#4c78a8', best:'#54a24b', worst:'#e45756'};
  Plotly.react('radar', ['best','base','worst'].map(s=>({type:'scatterpolar', name:s, r:[...c.cases[s].pillars, c.cases[s].pillars[0]],
    theta:[...short, short[0]], fill:'toself', opacity:0.45, line:{color:cols[s]}})),
    L({polar:{bgcolor:'rgba(0,0,0,0)', radialaxis:{range:[0,100], gridcolor:grid, tickfont:{size:9}}, angularaxis:{gridcolor:grid, tickfont:{size:10}}}, margin:{l:80,r:80,t:30,b:40}}), cfg);
  const s = c.sensitivity.slice().reverse();
  Plotly.react('sens', [{type:'bar', orientation:'h', y:s.map(x=>x.id), x:s.map(x=>x.points), marker:{color:'#f58518'},
    customdata:s.map(x=>[x.value, x.score]), hovertemplate:'%{y}: %{x:.2f} pts<br>value %{customdata[0]} · score %{customdata[1]:.0f}<extra></extra>'}],
    L({margin:{l:120,r:10,t:10,b:30}, xaxis:{tickformat:'.2f', gridcolor:grid}}), cfg);
  const d = c.default, bars = [['Scorecard', d.scorecard_pd], ['Fitted', d.fitted_pd], ['Blended', d.blended_pd], ['Market (CDS)', d.market_pd]];
  Plotly.react('pd', [{type:'bar', x:bars.map(b=>b[0]), y:bars.map(b=>b[1]==null?0:100*b[1]), marker:{color:['#9d755d','#4c78a8','#1d2430','#b279a2']},
    text:bars.map(b=>b[1]==null?'not available':pct(b[1],2)), textposition:'outside',
    error_y: d.pd_low!=null&&d.pd_high!=null ? {type:'data', symmetric:false, array:[0,100*(d.pd_high-d.fitted_pd),0,0], arrayminus:[0,100*(d.fitted_pd-d.pd_low),0,0]} : undefined}],
    L({yaxis:{title:{text:'PD (%)'}, gridcolor:grid, rangemode:'tozero'}}), cfg);
  document.getElementById('pdnote').textContent = (d.fitted_pd==null ? 'Default history not fitted yet, so the blended PD equals the scorecard PD. ' : '')
    + (d.market_pd==null ? 'No CDS spread entered.' : (d.flag||''));
  const pri = c.policies;
  document.getElementById('pri').innerHTML = pri.length ? '<table><tr><th>Policy</th><th>Sector</th><th>Term</th><th>Premium</th><th>Claim prob. over term</th></tr>'
    + pri.map(p=>`<tr><td>${p.id}</td><td>${p.sector}</td><td>${p.term}y</td><td>${num(p.premium_bps)} bps</td><td>${pct(p.claim_prob_term)}</td></tr>`).join('')
    + '</table><div class="muted">' + [...new Set(pri.map(p=>p.note))].join(' ') + '</div>' : '<div class="muted">No policies for this country in data/pri_policies.csv.</div>';
  const per = [...new Set(pri.flatMap(p=>Object.keys(p.perils)))];
  Plotly.react('pric', pri.length ? per.map(k=>({type:'bar', name:k, x:pri.map(p=>p.id), y:pri.map(p=>p.perils[k]?.premium_bps||0)}))
    : [], L({barmode:'stack', yaxis:{title:{text:'Premium (bps)'}, gridcolor:grid}}), cfg);
  document.getElementById('pric').style.display = pri.length ? '' : 'none';
  const b = c.bonds;
  document.getElementById('bonds').innerHTML = b.length ? '<table><tr><th>Bond</th><th>NPV haircut</th><th>Recovery /100</th><th>Months to deal</th><th>Value at default</th><th>Holdout risk</th></tr>'
    + b.map(x=>`<tr><td>${x.id}</td><td>${pct(x.sz_haircut)}</td><td>${num(x.recovery)}</td><td>${x.deal_months}</td><td>${num(x.recovery_at_default)}</td><td>${x.holdout_risk}</td></tr>`).join('')
    + '</table><div class="muted">' + [...new Set(b.map(x=>x.note))].join(' ') + '</div>' : '<div class="muted">No bonds for this country in data/bonds.csv.</div>';
}

const B = D.backtest, bins = (B.bins||[]).filter(x=>x.n>0);
document.getElementById('calnote').textContent = bins.length ? `Brier ${num(B.brier,4)} · skill ${num(B.skill,3)} · ${B.n} forecasts with outcomes` + (B.synthetic ? ' · includes SYNTHETIC rows' : '')
  : 'No forecasts with outcomes yet.';
Plotly.newPlot('cal', [{x:[0,1], y:[0,1], mode:'lines', name:'Perfect', line:{dash:'dot', color:grid}},
  {x:bins.map(x=>x.mean_pd), y:bins.map(x=>x.observed_rate), mode:'lines+markers', name:'Model', marker:{size:bins.map(x=>6+Math.sqrt(x.n))}}],
  L({xaxis:{title:{text:'Forecast PD'}, gridcolor:grid, range:[0,0.5]}, yaxis:{title:{text:'Observed default rate'}, gridcolor:grid, range:[0,0.5]}}), cfg);


let cur = null; const active = new Set();
const lo = p => Math.log(p/(1-p)), ilo = z => 1/(1+Math.exp(-z)), GREEN = '#2e7d5b';
function combine(c){
  const L = c.levers, b = L.base, on = [...active];
  const pil = b.pillars.map((v,i)=> v==null ? null : Math.max(0, Math.min(100, v + on.reduce((s,id)=> s + ((L.single[id].pillars[i] ?? v) - v), 0))));
  let score = b.score;
  if (b.from_model && pil.every(v=>v!=null)) { const W = D.weights, sw = D.smallw, std = pil.reduce((s,v,i)=>s+W[i]*v, 0);
    score = b.small_state ? sw*pil[6] + (1-sw)/(1-W[6])*(std - W[6]*pil[6]) : std; }
  const pd = ilo(lo(b.pd) + on.reduce((s,id)=> s + lo(L.single[id].pd) - lo(b.pd), 0));
  const lm = on.reduce((s,id)=> s*L.single[id].lgd_mult, 1), el = b.expected_loss*(pd/b.pd)*lm;
  const pri = {}; for (const [k,v] of Object.entries(b.pri)) { let pr = v.premium_bps, ne = v.net_el;
    on.forEach(id=>{ const s = L.single[id].pri[k]; pr *= s.premium_bps/v.premium_bps; ne *= s.net_el/v.net_el; }); pri[k] = {premium_bps:pr, net_el:ne}; }
  const bonds = {}; for (const [k,v] of Object.entries(b.bonds)) { let r = v.recovery, m = v.deal_months, h = v.holdout_risk;
    on.forEach(id=>{ const s = L.single[id].bonds[k]; r += s.recovery-v.recovery; m += s.deal_months-v.deal_months; if (s.holdout_risk!==v.holdout_risk) h = s.holdout_risk; });
    m = Math.max(0, m); bonds[k] = {recovery:r, deal_months:m, holdout_risk:h, recovery_at_default:r/Math.pow(1+v.exit_yield, m/12)}; }
  return {pillars:pil, score, pd, el, pri, bonds, lm};
}
function badge(c, id){
  const b = c.levers.base, s = c.levers.single[id], d = s.score - b.score, out = [];
  if (Math.abs(d) >= 0.005) out.push(`${d.toFixed(2)} pts`);
  if (s.lgd_mult !== 1) out.push(`loss ×${s.lgd_mult}`);
  const pk = Object.keys(b.pri); if (pk.length && Math.abs(s.pri[pk[0]].net_el - b.pri[pk[0]].net_el) > 1e-9 && Math.abs(d) < 0.005) out.push(`net PRI ×${(s.pri[pk[0]].net_el/b.pri[pk[0]].net_el).toFixed(2)}`);
  const bk = Object.keys(b.bonds); if (bk.length) { const dr = s.bonds[bk[0]].recovery_at_default - b.bonds[bk[0]].recovery_at_default; if (Math.abs(dr) > 0.05) out.push(`recovery +${dr.toFixed(1)}`); }
  return out.length ? `<span class="badge">${out.join(' · ')}</span>` : `<span class="badge none">${b.from_model ? 'no effect here' : 'needs model inputs'}</span>`;
}
function renderLevers(){
  const c = D.countries[cur], b = c.levers.base, x = combine(c), any = active.size > 0;
  const kp = (label, base, now, fmt, unit='') => `<div class="kpi"><span>${label}</span><b>${fmt(any ? now : base)}${unit}</b>` +
    (any ? `<em>${now<base?'▼':now>base?'▲':'='} from ${fmt(base)}${unit}</em>` : '<em style="color:var(--muted);font-weight:400">no levers on</em>') + '</div>';
  const priB = Object.values(b.pri).reduce((s,v)=>s+v.net_el,0), priX = Object.values(x.pri).reduce((s,v)=>s+v.net_el,0);
  const bk = Object.keys(b.bonds), recB = bk.length ? bk.reduce((s,k)=>s+b.bonds[k].recovery_at_default,0)/bk.length : null,
        recX = bk.length ? bk.reduce((s,k)=>s+x.bonds[k].recovery_at_default,0)/bk.length : null;
  document.getElementById('levres').innerHTML = kp('Country score', b.score, x.score, v=>v.toFixed(1)) +
    kp('Grade', b.grade, Math.min(10, Math.floor(x.score/10)+1), v=>String(v)) +
    kp('Default PD', b.pd, x.pd, v=>(100*v).toFixed(2), '%') +
    kp('Expected loss on exposure', 1000*b.expected_loss, 1000*x.el, v=>v.toFixed(0), 'k') +
    (Object.keys(b.pri).length ? kp('PRI net expected loss', priB, priX, v=>v.toFixed(2), 'm') : '') +
    (recB!=null ? kp('Bond value at default /100', recB, recX, v=>v.toFixed(1)) : '');
  const g = document.getElementById('levgrid'); g.innerHTML = D.lever_categories.map(cat => `<div class="levcat"><h3>${cat}</h3>` +
    D.levers.filter(l=>l.category===cat).map(l => `<label class="tog ${active.has(l.id)?'on':''}" title="${l.detail.replace(/"/g,'&quot;')}">
      <input type="checkbox" data-id="${l.id}" ${active.has(l.id)?'checked':''}><span class="sw"></span>
      <span><b>${l.label}</b> ${badge(c, l.id)}<small>${l.detail}</small></span></label>`).join('') + '</div>').join('');
  g.querySelectorAll('input').forEach(i => i.onchange = () => { i.checked ? active.add(i.dataset.id) : active.delete(i.dataset.id); renderLevers(); });
  const imp = D.levers.map(l => ({l, d: c.levers.single[l.id].score - b.score})).filter(o=>Math.abs(o.d)>=0.005).sort((a,b)=>b.d-a.d);
  Plotly.react('levimpact', [{type:'bar', orientation:'h', y:imp.map(o=>o.l.label), x:imp.map(o=>o.d),
    marker:{color:imp.map(o=>active.has(o.l.id)?GREEN:'#9fbfb0')}, hovertemplate:'%{y}: %{x:.2f} pts<extra></extra>'}],
    L({margin:{l:10,r:10,t:10,b:40}, yaxis:{automargin:true}, xaxis:{title:{text:'Change in country score (points, lower is safer)'}, gridcolor:grid, tickformat:'.2f'}}), cfg);
  document.getElementById('levimpact').style.display = imp.length ? '' : 'none';
  document.getElementById('levnote').textContent = (b.from_model ? '' : 'This country has only a preliminary score, so levers that work through the scorecard cannot move it yet. ') +
    (active.size > 1 ? 'With several levers on, the page adds their single effects; run python -m sovrisk.levers for the exact combined result.' : '');
  const cols = {base:'#4c78a8', best:'#54a24b', worst:'#e45756'};
  const tr = ['base','best','worst'].map(s=>({type:'bar', name:s[0].toUpperCase()+s.slice(1), x:D.pillar_names, y:c.cases[s].pillars, marker:{color:cols[s]}}));
  if (any) tr.push({type:'bar', name:'With levers', x:D.pillar_names, y:x.pillars, marker:{color:GREEN, pattern:{shape:'/'}}});
  Plotly.react('pillars', tr, L({barmode:'group', yaxis:{range:[0,100], gridcolor:grid}, margin:{l:35,r:10,t:30,b:90}, legend:{orientation:'h', y:1.12}}), cfg);
}
document.getElementById('lvall').onclick = () => { D.levers.forEach(l=>active.add(l.id)); renderLevers(); };
document.getElementById('lvnone').onclick = () => { active.clear(); renderLevers(); };
const _show = show; show = n => { _show(n); renderLevers(); };
show(names.includes('Belize') ? 'Belize' : names[0]);
</script></body></html>'''


if __name__ == '__main__':
    main()
