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

from . import load_config, muni, pfram, run_model
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
        'pfram': pfram_data(root),
        'muni': muni_data(root),
    })


def muni_data(root=ROOT):
    """Municipal credit scorecard (sovrisk.muni): scores, factors, stress cases and peer percentiles per town."""
    if not (Path(root) / 'rulebook' / 'muni.yaml').exists():
        return None
    r = muni.run_all(root)
    rb = r['rulebook']
    return {'model': r['model'], 'factors': {k: f['label'] for k, f in rb['factors'].items()},
            'cases': list(rb.get('stress', {})),
            'stress_notes': {c: [x['note'] for x in v] for c, v in rb.get('stress', {}).items()},
            'towns': r['towns']}


def pfram_data(root=ROOT):
    """PPP fiscal risk (sovrisk.pfram): the portfolio's effect on headline indicators and one page per project."""
    if not (Path(root) / 'data' / 'pfram_projects.yaml').exists():
        return None
    r = pfram.run_all(root)
    end = max(p.start_year + p.contract_length for p in r['projects'])
    cut = lambda rows: [x for x in rows if x['year'] <= end]
    projects = []
    for i, res in enumerate(r['base']):
        p, s, R = res['project'], res['summary'], res['rows']
        peak = max(range(len(R[208])), key=lambda j: R[208][j])
        projects.append({
            'id': p.id, 'name': p.name, 'type': p.type, 'funding': p.funding, 'start': p.start_year,
            'end': p.start_year + p.contract_length - 1, 'illustrative': p.illustrative,
            'cost': s['total_construction_cost'], 'effective_rate': s['effective_rate'], 'equity_irr': s['equity_irr'],
            'project_irr': s['project_irr'], 'on_balance_sheet': s['on_balance_sheet'],
            'debt_guarantee_max': s['debt_guarantee_max'], 'peak_liabilities': R[208][peak],
            'peak_liabilities_pct': R[740][peak], 'peak_year': res['years'][peak], 'termination': R['termination'],
            'risks': [{'category': k, 'likelihood': v[0], 'impact': v[1], 'rating': pfram.risk_rating(*v)}
                      for k, v in (p.risks or {}).items()],
            'cases': {'Base case': pfram.project_table(res),
                      **{f'Shock: {k}': pfram.project_table(v[i]) for k, v in r['shocked'].items()}},
        })
    return {'country': r['country'], 'note': r['note'], 'quirks': pfram.QUIRKS,
            'shocks': {k: {f: getattr(v, f) for f in ('gdp', 'gdp_years', 'er', 'er_years', 'inflation', 'inflation_years')}
                       for k, v in r['shocks'].items()},
            'portfolio': cut(r['portfolio']), 'portfolio_shocked': {k: cut(v) for k, v in r['portfolio_shocked'].items()},
            'projects': projects}


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
.rm{display:grid;grid-template-columns:70px repeat(3,1fr);gap:4px;font-size:12px}.rm div{padding:6px;border-radius:6px;min-height:54px}.rm .ax{color:var(--muted);font-weight:600;min-height:0;display:flex;align-items:center}.rm b{display:block;font-size:11px}.kpi small{font-size:12px;font-weight:400}details summary{cursor:pointer;color:var(--muted)}.scroll{overflow-x:auto}
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
<section id="muni">
<div class="row"><h2 style="margin:0">Municipal credit scorecard</h2><span class="tag" id="mumodel"></span></div>
<div class="muted" id="musub"></div>
<div class="grid" style="margin-top:12px">
<div class="card"><h2>Towns ranked by risk score</h2><div class="muted">0 is lowest risk, 100 highest. Markers show the score under each stress case.</div><div id="murank" class="chart" style="height:380px"></div></div>
<div class="card"><h2 id="mufh">Factor scores</h2><div class="muted">Base case and stress cases, 0 to 100</div><div id="mufac" class="chart" style="height:380px"></div></div>
</div>
<div class="row"><h2 style="margin:0" id="muname"></h2><select id="mupick"></select></div>
<div class="kpis" id="mukpis"></div>
<div class="grid">
<div class="card"><h2>What drives the score</h2><div class="muted">Points each indicator adds to the town score (they sum to the score)</div><div id="mupts" class="chart" style="height:460px"></div></div>
<div class="card"><h2>Against the other towns</h2><div class="muted">Percentile rank on each indicator; 100 is the riskiest town in the set</div><div id="mupct" class="chart" style="height:460px"></div></div>
</div>
<div class="card" style="margin-top:16px"><details><summary>Indicator table for this town</summary><div class="scroll" id="mutable"></div></details></div>
</section>
<section id="pfram">
<div class="row"><h2 style="margin:0">PPP fiscal risk (PFRAM 2.0)</h2><span class="tag" id="pfillus"></span></div>
<div class="muted" id="pfsub"></div>
<div class="grid" style="margin-top:12px">
<div class="card"><h2>Government liabilities from PPPs, by project</h2><div class="muted">% of GDP. The dashed line is the portfolio total under the shock.</div><div id="pfliab" class="chart"></div></div>
<div class="card"><h2>Gross public debt with and without PPPs</h2><div class="muted">% of GDP</div><div id="pfdebt" class="chart"></div></div>
<div class="card"><h2>Contingent liabilities, by project</h2><div class="muted">Maximum exposure from debt and revenue guarantees, % of GDP</div><div id="pfcont" class="chart"></div></div>
<div class="card"><h2>PPP effect on the fiscal balance</h2><div class="muted">% of GDP; negative means the PPPs add to the deficit</div><div id="pfbal" class="chart"></div></div>
</div>
<div class="row"><h2 style="margin:0" id="pfname"></h2><select id="pfpick"></select><select id="pfcase"></select></div>
<div class="kpis" id="pfkpis"></div>
<div class="grid">
<div class="card"><h2>Government flows</h2><div class="muted">DOM million a year</div><div id="pfgov" class="chart"></div></div>
<div class="card"><h2>Government balance sheet</h2><div class="muted">DOM million, end of year</div><div id="pfbs" class="chart"></div></div>
<div class="card"><h2>Private partner cash flows</h2><div class="muted">DOM million a year</div><div id="pfpriv" class="chart"></div></div>
<div class="card"><h2 id="pftermh">Early termination</h2><div class="muted" id="pftermn"></div><div id="pfterm" class="chart"></div></div>
<div class="card"><h2>Risk matrix</h2><div class="muted">Likelihood by fiscal impact, as in the workbook's risk sheet</div><div id="pfrisk" style="margin-top:8px"></div></div>
<div class="card"><h2>Workbook quirks kept for parity</h2><ul id="pfquirks" class="muted" style="padding-left:18px;margin:0"></ul></div>
</div>
<div class="card" style="margin-top:16px"><details><summary>Annual table for this project and case</summary><div class="scroll" id="pftable"></div></details></div>
</section>
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
const _show = show; show = n => { _show(n); if (D.countries[n]) renderLevers(); };
show(names.includes('Belize') ? 'Belize' : names[0]);

// ---------------------------------------------------------------- municipal credit scorecard
{ const U = D.muni;
if (!U) { document.getElementById('muni').style.display = 'none'; } else {
const SER = dark ? ['#3987e5','#d95926','#199e70'] : ['#2a78d6','#eb6834','#1baf7a'];   // validated categorical slots 1-3
const surf = dark ? '#1b2129' : '#fff', SYM = ['circle', 'diamond'];
const tn = Object.keys(U.towns).sort((a,b)=>U.towns[a].base.score-U.towns[b].base.score);
document.getElementById('mumodel').textContent = `${U.model} · illustrative towns · untested · not a credit rating`;
document.getElementById('musub').textContent = `${tn.length} hypothetical Massachusetts towns scored on economy, finances, debt and governance (rulebook/muni.yaml). `
  + U.cases.map(c=>`${c}: ${U.stress_notes[c].join('; ')}.`).join(' ');
const rk = tn.slice().reverse();
Plotly.newPlot('murank', [{type:'bar', orientation:'h', name:'Base case', y:rk, x:rk.map(n=>U.towns[n].base.score), marker:{color:SER[0]},
    text:rk.map(n=>`grade ${U.towns[n].base.grade}`), textposition:'inside', insidetextanchor:'start', textfont:{color:'#fff'},
    customdata:rk.map(n=>U.towns[n].profile), hovertemplate:'%{y} (%{customdata}): %{x:.1f}<extra>Base case</extra>'},
  ...U.cases.map((c,i)=>({type:'scatter', mode:'markers', name:c, y:rk, x:rk.map(n=>U.towns[n].stress[c].score),
    marker:{color:SER[i+1], size:10, symbol:SYM[i%2], line:{color:surf, width:2}}, hovertemplate:`%{y}: %{x:.1f}<extra>${c}</extra>`}))],
  L({margin:{l:70,r:24,t:10,b:30}, xaxis:{range:[0,100], gridcolor:grid}, legend:{orientation:'h', y:-0.12}, hovermode:'y unified'}), cfg);
document.getElementById('murank').on('plotly_click', e => showMuni(e.points[0].y));
const mp = document.getElementById('mupick'); tn.forEach(n => mp.add(new Option(`${n} (${U.towns[n].profile})`, n)));
mp.onchange = () => showMuni(mp.value);
function showMuni(n){
  const t = U.towns[n], b = t.base; mp.value = n;
  document.getElementById('muname').textContent = n;
  document.getElementById('mufh').textContent = `Factor scores: ${n}`;
  const k = [['Risk score', num(b.score)], ['Grade (1-10)', b.grade], ...U.cases.map(c=>[c, num(t.stress[c].score)]),
    ['Profile', `<span style="font-size:16px">${t.profile}</span>`], ['Population', (t.population||0).toLocaleString('en-US')], ['Data coverage', pct(b.coverage,0)]];
  document.getElementById('mukpis').innerHTML = k.map(([a,v])=>`<div class="kpi"><span>${a}</span><b>${v}</b></div>`).join('');
  const fk = Object.keys(U.factors);
  Plotly.react('mufac', [['Base case', b], ...U.cases.map(c=>[c, t.stress[c]])].map(([name, s], i)=>({type:'bar', orientation:'h', name,
    y:fk.map(f=>U.factors[f]), x:fk.map(f=>s.factors[f].score), marker:{color:SER[i], line:{color:surf, width:1}},
    hovertemplate:`%{y}: %{x:.1f}<extra>${name}</extra>`})),
    L({barmode:'group', margin:{l:10,r:24,t:10,b:30}, yaxis:{automargin:true, autorange:'reversed'}, xaxis:{range:[0,100], gridcolor:grid}, legend:{orientation:'h', y:-0.12}}), cfg);
  const ids = Object.keys(b.indicators).filter(i=>b.indicators[i].score!=null);
  const byPts = ids.slice().sort((x,y)=>b.indicators[x].points-b.indicators[y].points);
  Plotly.react('mupts', [{type:'bar', orientation:'h', y:byPts.map(i=>b.indicators[i].label), x:byPts.map(i=>b.indicators[i].points), marker:{color:SER[0]},
    customdata:byPts.map(i=>[U.factors[b.indicators[i].factor], b.indicators[i].value, b.indicators[i].unit, b.indicators[i].score]),
    text:byPts.map(i=>num(b.indicators[i].points)), textposition:'outside', cliponaxis:false,
    hovertemplate:'%{y}<br>%{customdata[0]}<br>value %{customdata[1]} %{customdata[2]} · score %{customdata[3]:.0f}<br>adds %{x:.1f} points<extra></extra>'}],
    L({margin:{l:10,r:30,t:10,b:30}, yaxis:{automargin:true}, xaxis:{gridcolor:grid, rangemode:'tozero'}}), cfg);
  const byPct = ids.filter(i=>t.percentile[i]!=null).sort((x,y)=>t.percentile[x]-t.percentile[y]);
  Plotly.react('mupct', [{type:'bar', orientation:'h', y:byPct.map(i=>b.indicators[i].label), x:byPct.map(i=>t.percentile[i]), marker:{color:SER[0]},
    customdata:byPct.map(i=>[b.indicators[i].value, b.indicators[i].unit]),
    hovertemplate:'%{y}: percentile %{x:.0f}<br>value %{customdata[0]} %{customdata[1]}<extra></extra>'}],
    L({margin:{l:10,r:24,t:10,b:30}, yaxis:{automargin:true}, xaxis:{range:[0,100], tickvals:[0,25,50,75,100], gridcolor:grid},
      shapes:[{type:'line', x0:50, x1:50, y0:0, y1:1, yref:'paper', line:{color:dark?'#9aa4b2':'#5b6575', width:1, dash:'dot'}}],
      annotations:[{x:50, y:0, yref:'paper', yanchor:'bottom', xanchor:'left', xshift:4, text:'median town', showarrow:false, font:{size:11}}]}), cfg);
  document.getElementById('mutable').innerHTML = '<table><tr><th>Indicator</th><th>Factor</th><th>Value</th><th>Unit</th><th>Score</th><th>Points</th><th>Percentile</th>'
    + U.cases.map(c=>`<th>Score, ${c}</th>`).join('') + '</tr>'
    + Object.keys(b.indicators).map(i=>{ const x = b.indicators[i]; return `<tr><td>${x.label}</td><td>${U.factors[x.factor]}</td><td>${x.value??''}</td><td>${x.unit}</td><td>${num(x.score,0)}</td><td>${num(x.points)}</td><td>${num(t.percentile[i],0)}</td>`
      + U.cases.map(c=>`<td>${num(t.stress[c].indicators[i].score,0)}</td>`).join('') + '</tr>'; }).join('') + '</table>';
}
showMuni(tn[Math.floor(tn.length/2)]);
}}

// ---------------------------------------------------------------- PPP fiscal risk (PFRAM 2.0)
const F = D.pfram;
if (!F) { document.getElementById('pfram').style.display = 'none'; } else {
const SER = dark ? ['#3987e5','#d95926','#199e70'] : ['#2a78d6','#eb6834','#1baf7a'];   // validated categorical slots 1-3
const muted = dark ? '#9aa4b2' : '#5b6575', surf = dark ? '#1b2129' : '#fff';
const STATUS = {Irrelevant:'#c9ced6', Low:'#0ca30c', Medium:'#fab219', High:'#ec835a', Critical:'#d03b3b'};
const ICON = {Irrelevant:'○', Low:'▽', Medium:'◇', High:'△', Critical:'▲'};
const m0 = x => x==null ? 'n/a' : Math.round(x).toLocaleString('en-US');
const shockName = Object.keys(F.portfolio_shocked)[0];
const yrs = F.portfolio.map(r=>r.year);
const lineL = (o={}) => L(Object.assign({hovermode:'x unified', margin:{l:45,r:20,t:20,b:30}, legend:{orientation:'h', y:-0.15}}, o));
// direct label at each line's largest value (the legend carries identity too); lines alternate above and below
let lineN = 0;
const peakText = (ys, label) => { if (!label || ys.every(v=>!v)) return ys.map(()=>''); let k = 0; ys.forEach((v,i)=>{ if (Math.abs(v||0) > Math.abs(ys[k]||0)) k = i; }); return ys.map((_,i)=> i===k ? label : ''); };
const line = (x, y, name, color, extra={}) => Object.assign({type:'scatter', mode:'lines+text', x, y, name, line:{color, width:2},
  text:peakText(y, 'label' in extra ? extra.label : name), textposition:(lineN++ % 2) ? 'bottom center' : 'top center', textfont:{color:ink, size:11}, cliponaxis:false,
  hovertemplate:`${name}: %{y:,.2f}<extra></extra>`}, extra, {label:undefined});
const sh = F.shocks[shockName], span = (a,b) => a==null ? '' : (a===b ? `${a}` : `${a}-${b}`);
const shDesc = sh ? [sh.gdp ? `real GDP growth ${sh.gdp>0?'+':''}${(100*sh.gdp).toFixed(0)} pts in ${span(...sh.gdp_years)}` : '',
  sh.er ? `depreciation ${sh.er>0?'+':''}${(100*sh.er).toFixed(0)} pts in ${span(...sh.er_years)}` : '',
  sh.inflation ? `inflation ${sh.inflation>0?'+':''}${(100*sh.inflation).toFixed(0)} pts in ${span(...sh.inflation_years)}` : ''].filter(Boolean).join(', ') : '';
document.getElementById('pfillus').textContent = 'Illustrative projects, not real';
document.getElementById('pfsub').textContent = `${F.country}: ${F.projects.length} hypothetical PPPs, run through a Python port of the IMF and World Bank PFRAM 2.0 workbook. `
  + (sh ? `Shock "${shockName}": ${shDesc}. ` : '') + F.note;

const at = (p, key, cas='Base case') => { const m = Object.fromEntries(p.cases[cas].map(r=>[r.year, r[key]])); return yrs.map(y => m[y] ?? 0); };
const PS = F.portfolio_shocked[shockName] || [];
Plotly.newPlot('pfliab', [...F.projects.map((p,i)=>({type:'bar', name:p.name, x:yrs, y:at(p,'liabilities_pct_gdp'),
    marker:{color:SER[i%3], line:{color:surf, width:1}}, hovertemplate:`${p.name}: %{y:.2f}%<extra></extra>`})),
  ...(PS.length ? [{type:'scatter', mode:'lines', name:'Total, shock', x:PS.map(r=>r.year), y:PS.map(r=>r.ppp_debt_pct),
    line:{color:ink, width:2, dash:'dash'}, hovertemplate:'Total under shock: %{y:.2f}%<extra></extra>'}] : [])],
  L({barmode:'stack', bargap:0.25, hovermode:'x unified', margin:{l:40,r:10,t:10,b:30}, legend:{orientation:'h', y:-0.15}, yaxis:{gridcolor:grid, ticksuffix:'%'}}), cfg);
const P0 = F.portfolio;
Plotly.newPlot('pfdebt', [line(yrs, P0.map(r=>r.gross_debt_pct), 'Without PPPs', muted, {line:{color:muted, width:2, dash:'dot'}}),
  line(yrs, P0.map(r=>r.gross_debt_with_ppp_pct), 'With PPPs', SER[0]),
  ...(PS.length ? [line(PS.map(r=>r.year), PS.map(r=>r.gross_debt_with_ppp_pct), 'With PPPs, shock', SER[1], {label:'', line:{color:SER[1], width:2, dash:'dash'}})] : [])],
  lineL({yaxis:{gridcolor:grid, ticksuffix:'%'}}), cfg);
Plotly.newPlot('pfcont', F.projects.map((p,i)=>line(yrs, at(p,'contingent_pct_gdp'), p.name, SER[i%3], {label:p.id})), lineL({yaxis:{gridcolor:grid, ticksuffix:'%'}}), cfg);
Plotly.newPlot('pfbal', [line(yrs, P0.map(r=>r.ppp_nlb_pct), 'Overall', SER[0]), line(yrs, P0.map(r=>r.ppp_cash_pct), 'Cash', SER[1])],
  lineL({yaxis:{gridcolor:grid, ticksuffix:'%', zeroline:true, zerolinecolor:muted}}), cfg);

const pp = document.getElementById('pfpick'), pc = document.getElementById('pfcase');
F.projects.forEach(p => pp.add(new Option(`${p.id} ${p.name}`, p.id)));
Object.keys(F.projects[0].cases).forEach(k => pc.add(new Option(k, k)));
document.getElementById('pfquirks').innerHTML = F.quirks.map(q=>`<li>${q}</li>`).join('');
function showPF(){
  const p = F.projects.find(x=>x.id===pp.value), cas = pc.value, T = p.cases[cas], y = T.map(r=>r.year), col = k => T.map(r=>r[k]);
  const t = p.termination, peak = T.reduce((b,r)=> r.liabilities > b.liabilities ? r : b, T[0]);
  document.getElementById('pfname').textContent = p.name;
  const k = [['Construction cost', `${m0(p.cost)}m`], ['Effective interest rate', pct(p.effective_rate,2)], ['Equity IRR', pct(p.equity_irr,1)],
    ['Peak government liabilities', `${num(peak.liabilities_pct_gdp,2)}% GDP <small class="muted">${peak.year}</small>`],
    ['Government balance sheet', p.on_balance_sheet ? 'On' : 'Off'], ['Largest debt guarantee', `${m0(p.debt_guarantee_max)}m`],
    ['Termination payment', t.year ? `${m0(t.payment)}m <small class="muted">${t.year}</small>` : 'none']];
  document.getElementById('pfkpis').innerHTML = k.map(([a,b])=>`<div class="kpi"><span>${a}</span><b>${b}</b></div>`).join('')
    + `<div class="kpi"><span>Funding</span><b style="font-size:16px">${p.funding}</b></div>`;
  Plotly.react('pfgov', [line(y, col('net_lending_borrowing'), 'Net lending', SER[0]), line(y, col('gov_net_cash'), 'Net cash', SER[1])],
    lineL({yaxis:{gridcolor:grid, zeroline:true, zerolinecolor:muted}}), cfg);
  Plotly.react('pfbs', [line(y, col('liabilities'), 'Liabilities', SER[0]), line(y, col('nonfinancial_assets'), 'Assets', SER[1]),
    line(y, col('contingent_max'), 'Contingent', SER[2])], lineL({yaxis:{gridcolor:grid, rangemode:'tozero'}}), cfg);
  Plotly.react('pfpriv', [line(y, col('revenue'), 'Revenue', SER[0]), line(y, col('debt_service'), 'Debt service', SER[1]),
    line(y, col('dividends'), 'Dividends', SER[2])], lineL({yaxis:{gridcolor:grid, rangemode:'tozero'}}), cfg);
  document.getElementById('pftermh').textContent = t.year ? `Early termination in ${t.year}` : 'Early termination';
  document.getElementById('pftermn').textContent = t.year ? `Government net lending, DOM million. Payment on ${t.method}: ${m0(t.payment)}m (book value ${m0(t.book_value)}m; lost profits ${m0(t.lost_profit_npv)}m).`
    : 'No termination year entered for this project.';
  Plotly.react('pfterm', t.year ? [line(y, col('net_lending_borrowing'), 'Contract runs', SER[0], {label:''}),
    line(y, col('termination_nlb'), 'Terminated', SER[1], {label:'', line:{color:SER[1], width:2, dash:'dash'}})] : [],
    lineL({yaxis:{gridcolor:grid, zeroline:true, zerolinecolor:muted}, shapes: t.year ? [{type:'line', x0:t.year, x1:t.year, y0:0, y1:1, yref:'paper', line:{color:muted, width:1, dash:'dot'}}] : []}), cfg);
  const lv = ['High','Medium','Low'], iv = ['Low','Medium','High'];
  const cell = (l,i) => { const r = p.risks.filter(x=>x.likelihood===l && x.impact===i), rating = ['Irrelevant','Low','Medium','High','Critical'][lv.length-lv.indexOf(l)-1+iv.indexOf(i)];
    return `<div style="background:${STATUS[rating]}33;border:1px solid ${STATUS[rating]}" title="${rating}"><b>${ICON[rating]} ${rating}</b>${r.map(x=>x.category).join('<br>')}</div>`; };
  document.getElementById('pfrisk').innerHTML = `<div class="rm"><div class="ax"></div>${iv.map(i=>`<div class="ax">Impact ${i.toLowerCase()}</div>`).join('')}`
    + lv.map(l=>`<div class="ax">Likelihood ${l.toLowerCase()}</div>` + iv.map(i=>cell(l,i)).join('')).join('') + '</div>'
    + (p.risks.length ? '' : '<div class="muted">No risks entered for this project.</div>');
  const cols = Object.keys(T[0]);
  document.getElementById('pftable').innerHTML = '<table><tr>' + cols.map(c=>`<th>${c.replace(/_/g,' ')}</th>`).join('') + '</tr>'
    + T.map(r=>'<tr>' + cols.map(c=>`<td>${c==='year' ? r[c] : c.endsWith('pct_gdp') ? num(r[c],2) : m0(r[c])}</td>`).join('') + '</tr>').join('') + '</table>';
}
pp.onchange = pc.onchange = showPF; showPF();
}
</script></body></html>'''


if __name__ == '__main__':
    main()
