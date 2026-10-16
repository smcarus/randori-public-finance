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

from . import ews, load_config, muni, pfram, run_model, spillover
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
        'srdsf': srdsf_data(root),
        'ews': ews_data(root),
        'spill': spillover_data(root),
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


def ews_data(root=ROOT):
    """Macro early-warning panel (sovrisk.ews, RPF-05). Always carries the rulebook thresholds and the notes on missing
    files; with data/ews_panel.csv it also carries each country's ratings, score and indicator history."""
    root = Path(root)
    if not (root / 'rulebook' / 'ews.yaml').exists():
        return None
    cfg = ews.load(root)
    rb = cfg['rulebook']
    out = {'model': ews.MODEL, 'has_data': bool(cfg['panel']), 'notes': cfg['notes'],
           'needs': [{'file': 'data/ews_panel.csv', 'required': True}, {'file': 'data/crisis_dates.csv', 'required': False}],
           'indicators': [{k: i.get(k) for k in ('id', 'label', 'unit', 'bad', 'amber', 'red', 'weight', 'optional', 'note')}
                          for i in rb['indicators']],
           'points': rb.get('points'), 'countries': {}, 'series': {}, 'weighting': None}
    for n in out['needs']:
        n['missing'] = not (root / n['file']).exists()
    if not cfg['panel']:
        return _clean(out)
    t = ews.ews_table(cfg)
    out.update(weighting=t['weighting'], weights=t['weights'], notes=t['notes'], countries=t['countries'])
    for r in sorted(ews.fill_derived(rb, cfg['panel']), key=lambda r: int(r['year'])):
        s = out['series'].setdefault(str(r['country']), {'years': [], **{i['id']: [] for i in rb['indicators']}})
        s['years'].append(int(r['year']))
        for i in rb['indicators']:
            s[i['id']].append(ews._val(r.get(i['id'])))
    return _clean(out)


def _rel(root, p):
    try:
        return Path(p).resolve().relative_to(Path(root).resolve()).as_posix()
    except ValueError:
        return str(p)


def spillover_data(root=ROOT):
    """Spillover network (sovrisk.spillover, RPF-06). Always carries the scenarios, the elasticities with their source
    notes and the missing exposure files; with exposure data it also carries every scenario's GDP impact by channel
    and the exposures to each scenario's shocked partners."""
    root = Path(root)
    if not (root / 'rulebook' / 'spillover.yaml').exists():
        return None
    rb = spillover.load_rulebook(root)
    ex, missing = spillover.load_exposures(root, rb)
    params = []
    for ch, c in list(rb['channels'].items()) + [('second_round', rb.get('second_round', {}))]:
        for k, v in c.items():
            if isinstance(v, (int, float)) and not isinstance(v, bool) and f'{k}_source' in c:
                src = ' '.join(str(c[f'{k}_source']).split())
                params.append({'channel': ch, 'param': k, 'value': v, 'source': src, 'draft': 'to verify' in src.lower()})
    out = {'model': spillover.MODEL, 'channels': {ch: rb['channels'][ch]['label'] for ch in spillover.CHANNELS},
           'files': {ch: 'data/' + rb['channels'][ch]['file'] for ch in spillover.CHANNELS},
           'missing': [_rel(root, m) for m in missing], 'params': params,
           'scenarios': {k: {'label': s.get('label', k), 'gdp': s.get('gdp') or {}, 'price': s.get('price') or {},
                             'rate': s.get('rate') or {}} for k, s in rb['scenarios'].items()},
           'has_data': any(ex.values()), 'results': {}, 'exposure': {}}
    if not out['has_data']:
        return _clean(out)
    lat = {ch: spillover.latest(ex[ch]) for ch in spillover.CHANNELS}
    every = sorted({c for v in lat.values() for c, _ in v})
    for k, s in out['scenarios'].items():
        try:
            r = spillover.run(k, ex, rb)
            out['results'][k] = {'n_rounds': r['n_rounds'], 'countries': {c: {f: x[f] for f in ('by_channel', 'first', 'second', 'total')}
                                                                          for c, x in r['countries'].items()}}
        except ValueError as e:
            out['results'][k] = {'error': str(e), 'countries': {}}
        cols = []   # exposure to the partners this scenario shocks, % of GDP of the receiving country
        for ch in ('trade', 'banks', 'remittances'):
            cols += [{'channel': ch, 'partner': p, 'values': {c: lat[ch].get((c, p)) for c in every}} for p in s['gdp']]
        cols += [{'channel': 'commodities', 'partner': p, 'values': {c: lat['commodities'].get((c, p)) for c in every}}
                 for p in s['price']]
        if 'USD' in s['rate']:   # what the rates channel prices: US dollar share of debt x gross financing need
            v = {c: (lat['rates'][(c, 'usd_debt_share')] * lat['rates'][(c, 'gfn')] / 100
                     if (c, 'usd_debt_share') in lat['rates'] and (c, 'gfn') in lat['rates'] else None) for c in every}
            cols.append({'channel': 'rates', 'partner': 'USD gross financing need', 'values': v})
        out['exposure'][k] = [c for c in cols if any(x is not None for x in c['values'].values())]
    return _clean(out)


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


# MAC SRDSF (RPF-04): where each number lives in the template. Rows are 1-based Excel rows, columns letters.
SRDSF_SIGNALS = [   # (label, Output row, column of the mechanical signal or None, column of the final assessment or None)
    ('Overall', 19, None, 'O'), ('Near term', 23, 'N', 'O'), ('Medium term', 27, 'N', 'O'),
    ('Medium term: fanchart', 28, 'N', None), ('Medium term: GFN', 29, 'N', None),
    ('Medium term: stress test', 30, 'N', None), ('Long term', 32, None, 'O'),
    ('Sustainability assessment', 36, 'N', 'O')]
SRDSF_DRIVERS = [(218, 'Institutional quality'), (219, 'Stress history'), (220, 'Cyclical position'),
                 (221, 'Debt burden & buffers'), (222, 'Global conditions')]
SRDSF_STRESS = [('Banking crisis', 541, 558), ('Commodity prices', 542, 559), ('Contingent liabilities', 543, 560),
                ('Exchange rate', 544, 561), ('Natural disasters', 545, 562)]   # Charts rows: debt/GDP, GFN/GDP
SRDSF_MT = [('Fanchart width (% of GDP)', 298), ('Probability of debt non-stabilization (%)', 301),
            ('Terminal debt-to-GDP x institutions index', 304), ('Average baseline GFN (% of GDP)', 314),
            ("Initial banks' claims on the general government (% of bank assets)", 317),
            ("Change in banks' claims in stress (% of bank assets)", 320)]
SRDSF_CACHE_VERSION = b'srdsf-dashboard v1'   # bump when _srdsf_compute changes what it extracts
SRDSF_SOURCES = [
    ('Risk signals', 'Output!L19:O39 (SignalsTable on Signals!A3:M23)'),
    ('Fan chart', 'Charts!C521:M527 (FAN!FanDataOut percentiles; baseline from BaseDB)'),
    ('Near-term logit', 'Output!CG213:CJ222 (LOGIT!DataNT)'),
    ('GFN path', 'Charts!C554:M557'), ('Medium-term index', 'Output!EO298:EQ339, Charts!C3600:F3603'),
    ('Stress tests', 'Charts!C534:O545 and C555:O562 (paths shown only for activated tests)')]


def _xl(v):
    """A template cell as JSON: numbers stay numbers, Excel errors become None, text stays text."""
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return None if math.isnan(v) or math.isinf(v) else float(v)
    if isinstance(v, str) and v.startswith('#'):
        return None
    return v


def _srdsf_inputs(root):
    root = Path(root)
    golden = root / 'tests' / 'golden' / 'srdsf'
    files = sorted(golden.glob('*.json.gz')) + [golden / 'names.json', root / 'tests' / 'golden' / 'srdsf_alt' / 'changes.json']
    files += sorted((Path(__file__).parent / 'srdsf').glob('*.py'))
    return golden, files


def _srdsf_compute(root):
    """Run the port on the template sample with only the country selector changed (see srdsf_data)."""
    from .srdsf import run as R
    from .srdsf.book import ci
    golden, _ = _srdsf_inputs(root)
    alt = json.loads((Path(root) / 'tests' / 'golden' / 'srdsf_alt' / 'changes.json').read_text())
    country = [x for x in alt if x[0] == 'Questions' and x[1] == 'C4']   # the country selector only, no macro edits
    book = R.load(golden)
    R.blank(book)
    for sheet, cell, v in country:
        book[sheet][cell] = v
    res = R.run(book, fan=True, gfn=True)
    O, C = book['Output'], book['Charts']
    g = lambda S, r, col: _xl(S.get(r, ci(col)))
    rng = lambda S, r, c0, c1: [_xl(S.get(r, c)) for c in range(ci(c0), ci(c1) + 1)]
    years = [int(y) for y in rng(C, 521, 'C', 'M')]
    signals = [{'label': lab, 'mechanical': g(O, r, m) if m else None, 'final': g(O, r, f) if f else None,
                'row': r} for lab, r, m, f in SRDSF_SIGNALS]
    lsp = rng(O, 215, 'CG', 'CJ')
    gfn_out = res.get('gfn')
    return {
        'model': 'RPF-04 v0.1',
        'run': {'passes': res['passes'], 'settled': res['settled'], 'fan_seed': res.get('fan', {}).get('seed'),
                'fan_paths': res.get('fan', {}).get('ntraj'),
                'gfn_converged': bool(gfn_out[0]) if isinstance(gfn_out, tuple) else False,
                'gfn_note': gfn_out if isinstance(gfn_out, str) else None},
        'signals': signals, 'stabilizes': g(O, 39, 'P'),
        'fan': {'years': years, 'actual': rng(C, 534, 'C', 'M'), 'baseline': rng(C, 535, 'C', 'M'),
                'p': {k: rng(C, r, 'C', 'M') for k, r in (('5', 523), ('25', 524), ('50', 525), ('75', 526), ('95', 527))}},
        'logit': {'years': [int(y) for y in rng(O, 213, 'CG', 'CJ')], 'windows': rng(O, 214, 'CG', 'CJ'),
                  'lsp': lsp, 'change': rng(O, 216, 'CG', 'CJ'),
                  'drivers': [{'name': n, 'values': rng(O, r, 'CG', 'CJ')} for r, n in SRDSF_DRIVERS]},
        'gfn': {'years': [int(y) for y in rng(C, 554, 'C', 'M')], 'actual': rng(C, 555, 'C', 'M'),
                'baseline': rng(C, 556, 'C', 'M'), 'stress': rng(C, 557, 'C', 'M')},
        'mt': {'components': [{'label': lab, 'value': g(O, r, 'EO'), 'contribution': g(O, r, 'EP')} for lab, r in SRDSF_MT],
               'dfi': g(O, 332, 'EP'), 'dfi_norm': g(O, 332, 'EQ'), 'gfi': g(O, 333, 'EP'), 'gfi_norm': g(O, 333, 'EQ'),
               'weights': [g(O, 332, 'ET'), g(O, 333, 'ET')], 'index': g(O, 334, 'EQ'), 'signal': g(O, 335, 'EQ'),
               'final': g(O, 336, 'EQ'), 'years': [int(y) for y in rng(C, 3600, 'C', 'F')], 'history': rng(C, 3601, 'C', 'F'),
               'low': g(C, 3602, 'F'), 'high': g(C, 3603, 'F'), 'notes': [g(O, 338, 'EL'), g(O, 339, 'EL')]},
        'stress': {'years': years, 'debt_baseline': rng(C, 535, 'C', 'M'), 'debt_actual': rng(C, 534, 'C', 'M'),
                   'gfn_baseline': rng(C, 556, 'C', 'M'), 'gfn_actual': rng(C, 555, 'C', 'M'),
                   'tests': [{'name': n, 'active': bool(C.get(rd, ci('O'))), 'debt': rng(C, rd, 'C', 'M'),
                              'gfn': rng(C, rg, 'C', 'M')} for n, rd, rg in SRDSF_STRESS]},
        'sources': SRDSF_SOURCES,
    }


def srdsf_data(root=ROOT, cache=None):
    """MAC SRDSF (sovrisk.srdsf, RPF-04): risk signals, fan chart, near-term logit, GFN and medium-term index, stress
    tests, computed from the IMF template's fictional sample (tests/golden/srdsf).

    With no country selected most peer-group lookups of the template return #N/A, so only the country selector
    (Questions!C4, as in tests/golden/srdsf_alt/changes.json) is set to a listed country; all data stay the template's
    fictional sample and the country name is never put in the result. The run takes about a minute, so the result is
    cached in outputs/srdsf_dashboard.json under a hash of the inputs and of the port's source; the cache can be
    deleted at any time and is rebuilt on the next call."""
    import hashlib
    import os
    golden, files = _srdsf_inputs(root)
    if not (golden / 'Output.json.gz').exists():
        return None
    h = hashlib.sha256(SRDSF_CACHE_VERSION)
    for f in files:
        if f.exists():
            h.update(f.name.encode() + b'\0' + f.read_bytes())
    key = h.hexdigest()
    cache = Path(cache) if cache else Path(root) / 'outputs' / 'srdsf_dashboard.json'
    try:
        c = json.loads(cache.read_text(encoding='utf-8'))
        if c.get('key') == key:
            return c['data']
    except (OSError, ValueError, KeyError, AttributeError):
        pass
    data = _clean(_srdsf_compute(root))
    try:
        cache.parent.mkdir(parents=True, exist_ok=True)
        tmp = cache.with_suffix(f'.{os.getpid()}.tmp')
        tmp.write_text(json.dumps({'key': key, 'data': data}), encoding='utf-8')
        os.replace(tmp, cache)
    except OSError:
        pass
    return data


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
.empty{margin-top:12px;border-style:dashed}.empty h3{font-size:14px;margin:0 0 6px}.empty ul{margin:6px 0;padding-left:18px}.empty code,.src code{font-size:12px}
.chipx{display:inline-block;white-space:nowrap;padding:1px 7px;border-radius:4px;font-weight:600;font-size:12px}
.sbar{display:flex;align-items:center;gap:6px;min-width:120px}.sbar i{display:block;height:10px;border-radius:0 4px 4px 0;background:var(--sbar)}.sbar span{font-variant-numeric:tabular-nums}
.ewsm{display:grid;gap:12px;grid-template-columns:repeat(auto-fill,minmax(260px,1fr))}.ewsm .card{padding:10px}.ewsm h3{font-size:13px;margin:0}.ewsm .chart{height:190px}
.src{font-size:12px;color:var(--muted)}.par{padding:7px 0;border-bottom:1px solid var(--line)}.par .src{margin-top:2px}tr.pick td{background:rgba(127,127,127,.08)}td.c{cursor:pointer}
.tabs{position:sticky;top:0;z-index:5;display:flex;gap:4px;overflow-x:auto;padding:0 16px;background:var(--card);border-bottom:1px solid var(--line)}
.tabs button{border:0;border-bottom:2px solid transparent;border-radius:0;background:none;padding:10px 12px;white-space:nowrap;color:var(--muted)}
.tabs button[aria-selected=true]{color:var(--ink);border-bottom-color:#2e7d5b;font-weight:600}.tabs button small{display:block;font-size:11px;font-weight:400;color:var(--muted)}
input{font:inherit;padding:5px 8px;border-radius:6px;border:1px solid var(--line);background:var(--card);color:var(--ink)}
.chart{width:100%;height:320px}#map{height:430px}.row{display:flex;gap:12px;align-items:center;flex-wrap:wrap;margin:18px 0 12px}
</style></head><body>
<div class="banner">FOR RESEARCH PURPOSES ONLY. CONFIDENTIAL. Untested, preliminary and illustrative. Not investment advice and not a credit rating.</div>
<header><h1>__TITLE__</h1><div class="muted" id="sub"></div></header>
<nav class="tabs" id="tabs" role="tablist" aria-label="Dashboard sections"></nav>
<main>
<section id="sov">
<div class="card"><h2>Risk map</h2><div class="muted">Colour shows the country score (higher is riskier). Click a country to open its page.</div><div id="map"></div></div>
<div class="grid" style="margin-top:16px">
<div class="card"><h2>Countries ranked</h2><div id="rank" class="chart" style="height:420px"></div></div>
</div>
<div class="row"><h2 style="margin:0" id="cname"></h2><select id="pick"></select><button id="golive" hidden title="Pull this country's latest data from the APIs">Pull live data</button><span id="csrc"></span></div>
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
<div class="card"><h2>Restructuring</h2><div id="bonds"></div></div>
</div>
<div class="card" style="margin-top:16px"><h2>Calibration (backtest)</h2><div id="calnote" class="muted"></div><div id="cal" class="chart"></div></div>
</section>
<section id="port">
<div class="row"><h2 style="margin:0">Portfolio loss</h2></div>
<div class="grid">
<div class="card"><h2>Portfolio loss (Monte Carlo)</h2><div id="mcsum" class="muted"></div><div id="hist" class="chart"></div></div>
<div class="card"><h2>Share of portfolio expected shortfall, by country</h2><div class="muted">How much of the tail loss each country accounts for</div><div id="esshare" class="chart" style="height:420px"></div></div>
</div>
<div class="row"><h2 style="margin:0">Political risk insurance</h2><select id="pripick" aria-label="Country"></select></div>
<div class="grid">
<div class="card"><h2 id="prih">Policies for this country</h2><div id="pri"></div><div id="pric" class="chart"></div></div>
<div class="card"><h2>All policies in the book</h2><div class="muted">Click a row to open that country</div><div class="scroll" id="pribook" style="margin-top:8px"></div></div>
</div>
</section>
<section id="live">
<div class="row"><h2 style="margin:0">Live country data</h2><span class="tag">Pulled from the providers' APIs · not yet checked against live responses</span></div>
<div class="muted">Pick a country and pull its latest series from the IMF World Economic Outlook, the World Bank, the BIS credit gaps and Yahoo Finance, then rate it on the early-warning panel (RPF-05). Each feed is pulled on its own: one that fails says why and the others still show.</div>
<div id="lvnote" style="margin-top:12px"></div>
<div id="lvform" class="row" hidden>
<select id="lvpick" aria-label="Country"></select>
<label class="muted">From <input id="lvy0" type="number" value="2000" min="1960" max="2100" style="width:80px"></label>
<label class="muted">Currency <input id="lvfx" placeholder="e.g. ARS" maxlength="3" style="width:70px" title="ISO 4217 code for the exchange rate against the US dollar (optional)"></label>
<button id="lvgo">Pull live data</button> <button id="lvre" title="Ignore the copy pulled earlier in this session">Pull again</button>
<span id="lvstat" class="muted"></span>
</div>
<div id="lvbody" hidden>
<div class="grid">
<div class="card"><h2>Feeds</h2><div class="scroll" id="lvfeeds"></div></div>
<div class="card"><h2>Early-warning rating</h2><div id="lvews"></div></div>
</div>
<div class="ewsm" id="lvcharts" style="margin-top:16px"></div>
</div>
</section>
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
<section id="srdsf">
<div class="row"><h2 style="margin:0">Debt sustainability (MAC SRDSF)</h2><span class="tag">Sample country (fictional data from the IMF template)</span></div>
<div class="muted" id="srsub">RPF-04 v0.1 · independent port of the IMF MAC SRDSF template · not endorsed by the IMF · sample country with fictional data · untested for real use</div>
<div class="grid" style="margin-top:12px">
<div class="card"><h2>Risk of sovereign stress: signals</h2><div class="muted">Mechanical signal from the template's tools and the final assessment (staff judgment in the template)</div><div id="srsig" class="scroll" style="margin-top:8px"></div></div>
<div class="card"><h2>Debt fan chart</h2><div class="muted">Gross public debt, % of GDP: percentile bands of the simulated paths and the baseline</div><div id="srfan" class="chart"></div></div>
<div class="card"><h2>Near-term logit stress probability</h2><div class="muted" id="srlogitn"></div><div id="srlogit" class="chart"></div></div>
<div class="card"><h2>Gross financing needs</h2><div class="muted">% of GDP: baseline and the GFN module's stress scenario</div><div id="srgfn" class="chart"></div></div>
<div class="card"><h2>Medium-term index against its thresholds</h2><div class="muted" id="srmtn"></div><div id="srmti" class="chart" style="height:200px"></div><div id="srmtt" class="scroll"></div></div>
<div class="card"><h2>Stress tests: debt</h2><div class="muted">Gross public debt, % of GDP, baseline and each activated stress test</div><div id="srstd" class="chart"></div></div>
<div class="card"><h2>Stress tests: gross financing needs</h2><div class="muted">GFN, % of GDP, baseline and each activated stress test</div><div id="srstg" class="chart"></div></div>
<div class="card"><h2>Stress-test status</h2><div id="srstn"></div></div>
</div>
<div class="card" style="margin-top:16px"><details><summary>Data tables for these charts</summary><div class="scroll" id="srtable"></div></details></div>
<div class="muted" id="srfoot" style="margin-top:10px;font-size:12px"></div>
</section>
<section id="ews">
<div class="row"><h2 style="margin:0">Macro early-warning panel</h2><span class="tag" id="ewtag">RPF-05 v0.1 · untested · not a rating</span></div>
<div class="muted" id="ewsub"></div>
<div id="ewempty"></div>
<div id="ewbody" hidden>
<div class="card" style="margin-top:12px"><h2>Countries by warning score</h2><div class="muted" id="ewtn"></div><div class="scroll" id="ewtab" style="margin-top:8px"></div></div>
<div class="row"><h2 style="margin:0" id="ewname"></h2><select id="ewpick" aria-label="Country"></select></div>
<div class="muted" id="ewcn"></div>
<div class="ewsm" id="ewsm"></div>
</div>
<div class="card" style="margin-top:16px" id="ewthwrap"><h2>Indicator thresholds</h2><div class="muted">From rulebook/ews.yaml. Draft thresholds for review; they need no country data.</div><div class="scroll" id="ewth" style="margin-top:8px"></div></div>
</section>
<section id="spill">
<div class="row"><h2 style="margin:0">Spillover network</h2><span class="tag" id="sptag">RPF-06 v0.1 · untested · draft elasticities</span></div>
<div class="muted" id="spsub"></div>
<div id="spempty"></div>
<div id="spbody" hidden>
<div class="row"><label for="sppick" class="muted">Scenario</label><select id="sppick"></select><span class="muted" id="spshock"></span></div>
<div class="grid">
<div class="card"><h2>GDP impact by channel</h2><div class="muted" id="spbn">% change in GDP, first and second round together. The diamond is the total.</div><div id="spbar" class="chart" style="height:380px"></div></div>
<div class="card"><h2>Exposure to the shocked partners</h2><div class="muted" id="sphn">% of the receiving country's GDP, latest year</div><div id="spheat" class="chart" style="height:380px"></div></div>
</div>
<div class="card" style="margin-top:16px"><details><summary>Table: impact by channel and round</summary><div class="scroll" id="sptable"></div></details></div>
</div>
<div class="card" style="margin-top:16px"><h2>Scenarios</h2><div class="muted">From rulebook/spillover.yaml. A scenario shocks only what it lists.</div><div class="scroll" id="spscen" style="margin-top:8px"></div></div>
<div class="card" style="margin-top:16px"><h2>Elasticities</h2><div class="muted">From rulebook/spillover.yaml. None is a fitted estimate.</div><div class="scroll" id="sppar" style="margin-top:8px"></div></div>
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

const sel = document.getElementById('pick'), psel = document.getElementById('pripick');
names.forEach(n => { sel.add(new Option(n, n)); psel.add(new Option(n, n)); }); sel.onchange = () => show(sel.value); psel.onchange = () => show(psel.value);
{ const es = names.filter(n => D.countries[n].es_share != null).sort((a,b)=>D.countries[a].es_share-D.countries[b].es_share);
  Plotly.newPlot('esshare', [{type:'bar', orientation:'h', y:es, x:es.map(n=>100*D.countries[n].es_share), marker:{color:'#4c78a8'},
    hovertemplate:'%{y}: %{x:.1f}% of ES<extra></extra>'}], L({margin:{l:10,r:10,t:10,b:40}, yaxis:{automargin:true}, xaxis:{title:{text:'% of portfolio ES'}, gridcolor:grid}}), cfg);
  document.getElementById('esshare').on('plotly_click', e => show(e.points[0].y));
  const book = names.flatMap(n => D.countries[n].policies.map(p => ({n, ...p})));
  document.getElementById('pribook').innerHTML = book.length ? '<table><tr><th>Country</th><th>Policy</th><th>Sector</th><th>Term</th><th>Premium</th><th>Claim prob.</th></tr>'
    + book.map(p=>`<tr data-c="${p.n}"><td class="c">${p.n}</td><td>${p.id}</td><td>${p.sector}</td><td>${p.term}y</td><td>${num(p.premium_bps)} bps</td><td>${pct(p.claim_prob_term)}</td></tr>`).join('') + '</table>'
    : '<div class="muted">No policies in data/pri_policies.csv.</div>';
  document.querySelectorAll('#pribook tr[data-c]').forEach(tr => tr.onclick = () => show(tr.dataset.c)); }

function show(n){
  const c = D.countries[n]; if(!c) return; sel.value = psel.value = n; cur = n;
  document.getElementById('prih').textContent = `Policies for ${n}`;
  document.querySelectorAll('#pribook tr[data-c]').forEach(tr => tr.classList.toggle('pick', tr.dataset.c===n));
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
if (names.length) show(names.includes('Belize') ? 'Belize' : names[0]);
else {  // no country scored (the public repo ships data/countries.csv and data/inputs.csv header-only): list the levers anyway
  document.getElementById('pick').style.display = 'none';
  document.getElementById('pripick').style.display = 'none'; document.getElementById('pric').style.display = 'none';
  document.getElementById('pri').innerHTML = '<div class="muted">No country is loaded: add one to data/countries.csv and its policies to data/pri_policies.csv.</div>';
  document.getElementById('levres').innerHTML = '<div class="card empty" style="flex:1"><h3>No country is loaded, so the levers have nothing to act on.</h3>' +
    '<div class="muted">Add at least one country to <code>data/countries.csv</code> (and its indicator values to <code>data/inputs.csv</code>), ' +
    'then rebuild with <code>python -m sovrisk.dashboard</code>. Each lever then shows its effect on that country\'s score, default probability and losses.</div></div>';
  document.getElementById('levgrid').innerHTML = D.lever_categories.map(cat => `<div class="levcat"><h3>${cat}</h3>` +
    D.levers.filter(l=>l.category===cat).map(l => `<label class="tog" title="${l.detail.replace(/"/g,'&quot;')}">
      <input type="checkbox" disabled><span class="sw"></span>
      <span><b>${l.label}</b> <span class="badge none">needs a country</span><small>${l.detail}</small></span></label>`).join('') + '</div>').join('');
  document.getElementById('lvall').disabled = document.getElementById('lvnone').disabled = true;
  document.getElementById('levimpact').style.display = 'none';
  document.getElementById('levimpact').previousElementSibling.style.display = 'none';
}

// ---------------------------------------------------------------- municipal credit scorecard
{ const U = D.muni;
if (!U) { document.getElementById('muni').style.display = 'none'; } else {
const SER = dark ? ['#3987e5','#d95926','#199e70'] : ['#2a78d6','#eb6834','#1baf7a'];   // validated categorical slots 1-3
const surf = dark ? '#1b2129' : '#fff', SYM = ['circle', 'diamond'];
const tn = Object.keys(U.towns).sort((a,b)=>U.towns[a].base.score-U.towns[b].base.score);
document.getElementById('mumodel').textContent = `${U.model} · illustrative towns · untested · not a credit rating`;
document.getElementById('musub').textContent = `${tn.length} hypothetical towns in several states, scored on economy, finances, debt and governance (rulebook/muni.yaml). Administration is scored against Massachusetts practice, the benchmark for every state. `
  + U.cases.map(c=>`${c}: ${U.stress_notes[c].join('; ')}.`).join(' ');
const rk = tn.slice().reverse();
Plotly.newPlot('murank', [{type:'bar', orientation:'h', name:'Base case', y:rk, x:rk.map(n=>U.towns[n].base.score), marker:{color:SER[0]},
    text:rk.map(n=>`grade ${U.towns[n].base.grade}`), textposition:'inside', insidetextanchor:'start', textfont:{color:'#fff'},
    customdata:rk.map(n=>U.towns[n].profile), hovertemplate:'%{y} (%{customdata}): %{x:.1f}<extra>Base case</extra>'},
  ...U.cases.map((c,i)=>({type:'scatter', mode:'markers', name:c, y:rk, x:rk.map(n=>U.towns[n].stress[c].score),
    marker:{color:SER[i+1], size:10, symbol:SYM[i%2], line:{color:surf, width:2}}, hovertemplate:`%{y}: %{x:.1f}<extra>${c}</extra>`}))],
  L({margin:{l:70,r:24,t:10,b:30}, xaxis:{range:[0,100], gridcolor:grid}, legend:{orientation:'h', y:-0.12}, hovermode:'y unified'}), cfg);
document.getElementById('murank').on('plotly_click', e => showMuni(e.points[0].y));
const mp = document.getElementById('mupick'); tn.forEach(n => mp.add(new Option(`${n} (${U.towns[n].profile}${U.towns[n].state ? ', ' + U.towns[n].state : ''})`, n)));
mp.onchange = () => showMuni(mp.value);
function showMuni(n){
  const t = U.towns[n], b = t.base; mp.value = n;
  document.getElementById('muname').textContent = n;
  document.getElementById('mufh').textContent = `Factor scores: ${n}`;
  const k = [['Risk score', num(b.score)], ['Grade (1-10)', b.grade], ...U.cases.map(c=>[c, num(t.stress[c].score)]),
    ['Profile', `<span style="font-size:16px">${t.profile}${t.state ? ', ' + t.state : ''}</span>`], ['MA administration benchmark', `${b.benchmark.met} of ${b.benchmark.of} met`], ['Population', (t.population||0).toLocaleString('en-US')], ['Data coverage', pct(b.coverage,0)]];
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

// ---------------------------------------------------------------- MAC SRDSF (RPF-04)
{ const R = D.srdsf;
if (!R) { document.getElementById('srdsf').style.display = 'none'; } else {
// categorical slots 1-5 of the validated palette (checked with a palette validator: light on #fff, dark on #1b2129, adjacent pairs)
const SER = dark ? ['#3987e5','#d95926','#199e70','#c98500','#d55181'] : ['#2a78d6','#eb6834','#1baf7a','#eda100','#e87ba4'];
const muted = dark ? '#9aa4b2' : '#5b6575', surf = dark ? '#1b2129' : '#fff';
const ST = {Low:{c:'#0ca30c', i:'▽'}, Moderate:{c:'#fab219', i:'◇'}, High:{c:'#ec835a', i:'△'}, Yes:{c:'#0ca30c', i:'✓'}, No:{c:'#ec835a', i:'✗'}};
const esc = s => String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;');
const chip = (v, empty) => { if (v==null || v==='' || v==='…') return `<span class="muted">${empty||'—'}</span>`;
  const s = ST[v]; if (!s) return `<span class="muted">${esc(v)}</span>`;
  return `<span style="display:inline-block;white-space:nowrap;padding:1px 8px;border-radius:4px;border:1px solid ${s.c};background:${s.c}2e;font-weight:600">${s.i} ${v}</span>`; };
const rgba = (h, a) => `rgba(${parseInt(h.slice(1,3),16)},${parseInt(h.slice(3,5),16)},${parseInt(h.slice(5,7),16)},${a})`;
const lastIdx = a => { let k = -1; a.forEach((v,i)=>{ if (v!=null) k = i; }); return k; };
const endText = (ys, label) => { const k = lastIdx(ys); return ys.map((_,i)=> i===k ? label : ''); };
const sline = (x, y, name, color, extra={}) => Object.assign({type:'scatter', mode:'lines+text', x, y, name, connectgaps:false,
  line:{color, width:2}, text:endText(y, name==='Actual' ? '' : name), textposition:'middle right', textfont:{color:ink, size:11}, cliponaxis:false,
  hovertemplate:`${name}: %{y:.1f}%<extra></extra>`}, extra);
const LL = (o={}) => L(Object.assign({hovermode:'x unified', margin:{l:40,r:95,t:10,b:30}, legend:{orientation:'h', y:-0.15},
  xaxis:{gridcolor:grid, dtick:2, tickangle:0}, yaxis:{gridcolor:grid, ticksuffix:'%'}}, o));
// the series that end before the projection (Actual) carry no direct label: their end sits on the baseline's start

// risk-signal table
const nm = {'Near term':'n.a. (see note 1)', 'Medium term: stress test':'no test activated'};
document.getElementById('srsig').innerHTML = '<table><tr><th>Horizon</th><th>Mechanical signal</th><th>Final assessment</th></tr>'
  + R.signals.map(s=>{ const sub = s.label.startsWith('Medium term:');
      return `<tr><td style="${sub?'padding-left:20px':''}">${esc(sub ? s.label.replace('Medium term: ','') : s.label)}</td><td>${chip(s.mechanical, nm[s.label])}</td><td>${chip(s.final, sub ? 'part of medium term' : (s.final==='n.a.' ? 'n.a.' : '—'))}</td></tr>`; }).join('')
  + `<tr><td>Debt stabilizes in the baseline</td><td>${chip(R.stabilizes)}</td><td></td></tr></table>`
  + '<div class="muted" style="font-size:12px;margin-top:6px">— : the template produces no value for this cell. 1/ In the template sample the near-term signal is not available ("n.a."); it is also not applicable when there is a disbursing IMF arrangement.</div>';

// fan chart: bands start at the last actual year, as in the template's chart
const F = R.fan, fy = F.years, k0 = lastIdx(F.actual);
const band = p => F.p[p].map((v,i)=> i===k0 ? F.actual[k0] : v);
const fb = (lo, hi, name, alpha) => [
  {type:'scatter', mode:'lines', x:fy, y:band(lo), line:{width:0}, showlegend:false, hoverinfo:'skip', connectgaps:false},
  {type:'scatter', mode:'lines', x:fy, y:band(hi), line:{width:0}, fill:'tonexty', fillcolor:rgba(SER[0], alpha),
   name, customdata:band(lo), hovertemplate:`${name}: %{customdata:.1f}% to %{y:.1f}%<extra></extra>`}];
Plotly.newPlot('srfan', [...fb('5','95','5th–95th percentile',0.16), ...fb('25','75','25th–75th percentile',0.34),
  sline(fy, F.actual, 'Actual', ink, {line:{color:ink, width:2}}),
  sline(fy, F.baseline, 'Baseline', SER[1], {line:{color:SER[1], width:2}})],
  LL({yaxis:{gridcolor:grid, ticksuffix:'%', rangemode:'tozero'}}), cfg);

// near-term logit: driver contributions to the change in the stress probability, one stacked bar per year
const G = R.logit, gx = G.years.map(String), avail = G.lsp.map(v=>typeof v==='number');
const lspNow = G.lsp.filter(v=>typeof v==='number');
document.getElementById('srlogitn').innerHTML = (lspNow.length ? `Logit stress probability ${pct(lspNow[lspNow.length-1],1)} (year of data ${G.years[lastIdx(G.lsp.map(v=>typeof v==='number'?v:null))]}). ` : '')
  + 'Bars: contribution of each driver to the change in the probability from the year before, percentage points. Data for year t predict stress in t+1 to t+2.'
  + (avail.some(a=>!a) ? ' Years marked n.a. have no value in the template sample.' : '');
Plotly.newPlot('srlogit', [...G.drivers.map((d,i)=>({type:'bar', name:d.name, x:gx, y:d.values.map(v=>v==null?null:100*v),
    marker:{color:SER[i], line:{color:surf, width:1}}, customdata:G.windows, hovertemplate:`${d.name}: %{y:+.2f} pp<extra></extra>`})),
  {type:'scatter', mode:'markers', name:'Total change', x:gx, y:G.change.map(v=>typeof v==='number'?100*v:null),
    marker:{symbol:'diamond', size:11, color:ink, line:{color:surf, width:2}}, customdata:G.windows, hovertemplate:'Total change: %{y:+.2f} pp (predicts stress in %{customdata})<extra></extra>'}],
  L({barmode:'relative', bargap:0.45, hovermode:'x unified', margin:{l:45,r:10,t:10,b:55}, legend:{orientation:'h', y:-0.3},
    yaxis:{gridcolor:grid, ticksuffix:' pp', zeroline:true, zerolinecolor:muted}, xaxis:{gridcolor:grid, type:'category', categoryorder:'array', categoryarray:gx, range:[-0.5, gx.length-0.5], tickangle:0, title:{text:'Year of data', font:{size:11}}},
    annotations:gx.map((x,i)=>[x,i]).filter(([,i])=>!avail[i]).map(([,i])=>({x:i, y:0, yanchor:'bottom', text:'n.a.', showarrow:false, font:{size:11, color:muted}}))}), cfg);

// GFN path
const N = R.gfn;
Plotly.newPlot('srgfn', [sline(N.years, N.actual, 'Actual', ink), sline(N.years, N.baseline, 'Baseline', SER[0]),
  sline(N.years, N.stress, 'Stress scenario', SER[1], {line:{color:SER[1], width:2, dash:'dash'}})],
  LL({yaxis:{gridcolor:grid, ticksuffix:'%', rangemode:'tozero'}}), cfg);

// medium-term index: weighted normalized components stacked, against the low/high thresholds
const M = R.mt, xmax = Math.max(0.6, 1.25*(M.index||0), 1.15*(M.high||0));
document.getElementById('srmtn').innerHTML = M.index==null ? 'Medium-term index not available.' :
  `Index ${num(M.index,3)} · mechanical signal ${chip(M.signal)} · final assessment ${chip(M.final)}. Thresholds ${num(M.low,3)} (low) and ${num(M.high,3)} (high).`;
const zone = (x0, x1, s, label) => ({type:'rect', xref:'x', yref:'paper', x0, x1, y0:0, y1:1, fillcolor:ST[s].c, opacity:0.13, line:{width:0}, layer:'below'});
const zl = (x, t) => ({x, y:1, yref:'paper', yanchor:'bottom', text:t, showarrow:false, font:{size:11, color:ink}});
const parts = [['Debt fanchart', M.dfi_norm, M.weights[0], M.dfi], ['GFN financeability', M.gfi_norm, M.weights[1], M.gfi]];
Plotly.newPlot('srmti', M.index==null ? [] : [...parts.map(([n,v,w,raw],i)=>({type:'bar', orientation:'h', name:`${n} (weight ${w})`, y:['Index'], x:[v*w],
    marker:{color:SER[i], line:{color:surf, width:2}}, customdata:[[v, raw]], hovertemplate:`${n}: index %{customdata[1]:.2f}, normalized %{customdata[0]:.3f}, weighted %{x:.3f}<extra></extra>`})),
  {type:'scatter', mode:'markers+text', name:'Medium-term index', y:['Index'], x:[M.index], marker:{symbol:'line-ns', size:30, line:{color:ink, width:3}},
    text:[num(M.index,3)], textposition:'middle right', textfont:{color:ink, size:12}, hovertemplate:'Medium-term index %{x:.3f}<extra></extra>'}],
  L({barmode:'stack', margin:{l:45,r:10,t:22,b:30}, legend:{orientation:'h', y:-0.35}, xaxis:{range:[0,xmax], gridcolor:grid}, yaxis:{showticklabels:false},
    shapes:[zone(0,M.low,'Low'), zone(M.low,M.high,'Moderate'), zone(M.high,xmax,'High')],
    annotations:[zl(M.low/2,'▽ Low'), zl((M.low+M.high)/2,'◇ Moderate'), zl((M.high+xmax)/2,'△ High')]}), cfg);
document.getElementById('srmtt').innerHTML = '<table><tr><th>Component</th><th>Value</th><th>Contribution</th></tr>'
  + M.components.map(c=>`<tr><td>${esc(c.label)}</td><td>${num(c.value,1)}</td><td>${num(c.contribution,2)}</td></tr>`).join('')
  + `<tr><td>Debt fanchart index · GFN financeability index</td><td colspan="2">${num(M.dfi,2)} · ${num(M.gfi,2)}</td></tr></table>`
  + `<div class="muted" style="font-size:12px;margin-top:6px">${M.notes.filter(Boolean).map(esc).join(' ')}${M.history.slice(0,-1).every(v=>v==null) ? ` Earlier years (${M.years.slice(0,-1).join(', ')}) are not available in the sample.` : ''}</div>`;

// stress tests: colour follows the test (fixed slot), never its rank
const S = R.stress, act = S.tests.map((t,i)=>[t,i]).filter(([t])=>t.active);
const stc = (key, base, actual) => [sline(S.years, S[actual], 'Actual', ink), sline(S.years, S[base], 'Baseline', muted, {line:{color:muted, width:2, dash:'dot'}}),
  ...act.map(([t,i])=>sline(S.years, t[key], t.name, SER[i]))];
if (!act.length) ['srstd','srstg'].forEach(id => document.getElementById(id).previousElementSibling.textContent += ' (none is activated in the sample, so only the baseline is shown)');
Plotly.newPlot('srstd', stc('debt', 'debt_baseline', 'debt_actual'), LL({yaxis:{gridcolor:grid, ticksuffix:'%', rangemode:'tozero'}}), cfg);
Plotly.newPlot('srstg', stc('gfn', 'gfn_baseline', 'gfn_actual'), LL({yaxis:{gridcolor:grid, ticksuffix:'%', rangemode:'tozero'}}), cfg);
document.getElementById('srstn').innerHTML = '<table><tr><th>Stress test</th><th>Status</th></tr>'
  + S.tests.map((t,i)=>`<tr><td><span style="display:inline-block;width:10px;height:10px;border-radius:2px;background:${SER[i]};margin-right:6px"></span>${t.name}</td><td>${t.active ? '<b>Activated</b>' : '<span class="muted">Not activated</span>'}</td></tr>`).join('') + '</table>'
  + '<div class="muted" style="font-size:12px;margin-top:6px">The template runs a stress test only when its trigger fires (Signals sheet, "Activated" column); an activated test adds its path to the two charts.</div>';

// table view
const tbl = (title, years, rows, d=1) => `<h2 style="margin-top:12px">${title}</h2><table><tr><th></th>${years.map(y=>`<th>${y}</th>`).join('')}</tr>`
  + rows.map(([n,v])=>`<tr><td>${esc(n)}</td>${v.map(x=>`<td>${typeof x==='number' ? num(x,d) : ''}</td>`).join('')}</tr>`).join('') + '</table>';
document.getElementById('srtable').innerHTML = tbl('Debt, % of GDP', fy, [['Actual', F.actual], ['Baseline', F.baseline],
    ...['5','25','50','75','95'].map(p=>[`Percentile ${p}`, F.p[p]]), ...S.tests.filter(t=>t.active).map(t=>[t.name, t.debt])])
  + tbl('Gross financing needs, % of GDP', N.years, [['Actual', N.actual], ['Baseline', N.baseline], ['Stress scenario', N.stress], ...S.tests.filter(t=>t.active).map(t=>[t.name, t.gfn])])
  + tbl('Near-term logit, percentage points (year of data)', G.years, [['Stress probability (%)', G.lsp.map(v=>typeof v==='number'?100*v:null)],
    ['Change', G.change.map(v=>typeof v==='number'?100*v:null)], ...G.drivers.map(d=>[d.name, d.values.map(v=>v==null?null:100*v)])], 2);

const ru = R.run;
document.getElementById('srfoot').innerHTML = '<b>Sample country.</b> The numbers are the fictional sample shipped with the IMF template, run through the Python port. '
  + 'The template\'s country selector (Questions!C4) is set to a listed emerging-market country only so that its peer-group lookups (country group, IFS code, currency union) resolve; '
  + 'none of that country\'s data are used and the output does not describe it. '
  + `Fan chart from ${ru.fan_paths ? ru.fan_paths.toLocaleString('en-US') : 'the'} simulated paths with the template's stored seed; GFN converge macro ${ru.gfn_converged ? 'converged' : 'did not converge' + (ru.gfn_note ? ` (${esc(ru.gfn_note)})` : '')}; `
  + `${ru.passes} formula passes, ${ru.settled ? 'settled' : 'not settled'}. Sources: ` + R.sources.map(([a,b])=>`${a}: ${b}`).join('; ') + '.';
}}

// ---------------------------------------------------------------- shared by the RPF-05 and RPF-06 sections
const SER5 = dark ? ['#3987e5','#d95926','#199e70','#c98500','#d55181'] : ['#2a78d6','#eb6834','#1baf7a','#eda100','#e87ba4'];   // validated categorical slots 1-5
const ink2 = dark ? '#9aa4b2' : '#5b6575', surf2 = dark ? '#1b2129' : '#fff';
const esc2 = s => String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;');
const rgba2 = (h, a) => `rgba(${parseInt(h.slice(1,3),16)},${parseInt(h.slice(3,5),16)},${parseInt(h.slice(5,7),16)},${a})`;
const fv = v => v==null ? 'n/a' : (Math.abs(v)>=100 ? v.toFixed(0) : v.toFixed(1));
const emptyCard = (items, tail) => `<div class="card empty"><h3>No country data is loaded.</h3><div class="muted">This section needs these files in <code>data/</code>, none of which ship with the repository:</div><ul>${items.join('')}</ul><div class="muted">${tail}</div></div>`;

// ---------------------------------------------------------------- macro early-warning panel (RPF-05)
{ const E = D.ews;
if (!E) { document.getElementById('ews').style.display = 'none'; } else {
// status chips as in the SRDSF section: icon + label + value, never colour alone
const RT = {green:{c:'#0ca30c', i:'▽', t:'Green'}, amber:{c:'#fab219', i:'◇', t:'Amber'}, red:{c:'#ec835a', i:'△', t:'Red'}};
const chipR = (g, txt, bare) => { const s = RT[g]; return `<span class="chipx" style="border:1px solid ${s.c};background:${s.c}2e">${s.i}${bare ? '' : ' ' + s.t}${txt ? ' ' + txt : ''}</span>`; };
const IN = E.indicators, cmp = i => i.bad==='low' ? '&lt;' : '&gt;';
document.getElementById('ewtag').textContent = `${E.model} · untested · not a rating`;
document.getElementById('ewsub').textContent = 'Green / amber / red ratings on external, credit and price indicators against the thresholds in rulebook/ews.yaml, and a warning score from 0 (all green) to 100 (all red). Not a credit rating.';
document.getElementById('ewth').innerHTML = '<table><tr><th>Indicator (unit)</th><th>Amber</th><th>Red</th><th>Risky when</th></tr>'
  + IN.map(i=>`<tr><td>${esc2(i.label)} <span class="muted">(${esc2(i.unit)})</span>${i.optional ? ' <span class="muted">optional</span>' : ''}${i.note ? `<div class="src">${esc2(i.note)}</div>` : ''}</td>`
    + `<td>${chipR('amber', cmp(i) + ' ' + i.amber, 1)}</td><td>${chipR('red', cmp(i) + ' ' + i.red, 1)}</td>`
    + `<td>${i.bad==='low' ? 'low' : 'high'}</td></tr>`).join('') + '</table>'
  + `<div class="muted" style="font-size:12px;margin-top:6px">Breaching a threshold is strict. Points per rating: green ${E.points.green}, amber ${E.points.amber}, red ${E.points.red}. Fallback weights: ${IN.every(i=>i.weight===IN[0].weight) ? `${IN[0].weight} for every indicator` : IN.map(i=>`${esc2(i.label)} ${i.weight}`).join(', ')}; with data/crisis_dates.csv they come from the signals method (1 / noise-to-signal ratio).</div>`;
if (!E.has_data) {
  document.getElementById('ewempty').innerHTML = emptyCard(E.notes.map(n=>{ const m = n.match(/^(\S+) is missing:?\s*(.*)$/);
      return m ? `<li><code>${esc2(m[1])}</code>${/ews_panel/.test(m[1]) ? ' (required)' : ' (optional)'}: ${esc2(m[2])}</li>` : `<li>${esc2(n)}</li>`; }),
    'See <b>docs/DATA.md</b> for the columns, units and sources, and for fetching the panel or entering it by hand. The thresholds below need no data.');
} else {
document.getElementById('ewbody').hidden = false;
const C = E.countries, cn = Object.keys(C).sort((a,b)=>(C[b].score??-1)-(C[a].score??-1) || a.localeCompare(b));
document.getElementById('ewtn').textContent = `Sorted by warning score. Weights: ${E.weighting}. * computed here from credit_gdp or reer (not supplied). A year in brackets is an older value used for a missing year. Click a row for the indicator history.`
  + (E.notes.length ? ' ' + E.notes.join(' ') : '');
const tab = document.getElementById('ewtab'); tab.style.setProperty('--sbar', SER5[0]);
tab.innerHTML = '<table><tr><th>Country</th><th>Year</th><th>Warning score</th>' + IN.map(i=>`<th>${esc2(i.label)}<br><span style="font-weight:400">${esc2(i.unit)}</span></th>`).join('') + '</tr>'
  + cn.map(c=>{ const s = C[c];
      return `<tr data-c="${esc2(c)}"><td class="c"><b>${esc2(c)}</b></td><td>${s.year}</td><td><div class="sbar" title="Warning score ${fv(s.score)}"><i style="width:${s.score==null?0:Math.max(2,s.score)}px"></i><span>${s.score==null ? 'n/a' : s.score.toFixed(0)}</span></div></td>`
        + IN.map(i=>{ const x = s.indicators[i.id];
            return `<td>${x.rating ? chipR(x.rating, fv(x.value) + (x.derived ? '*' : '') + (x.year!==s.year ? ` (${x.year})` : '')) : '<span class="muted">no data</span>'}</td>`; }).join('') + '</tr>'; }).join('') + '</table>';
tab.querySelectorAll('tr[data-c]').forEach(tr => { tr.style.cursor = 'pointer'; tr.onclick = () => showEws(tr.dataset.c); });
const ep = document.getElementById('ewpick'); cn.forEach(c => ep.add(new Option(c, c))); ep.onchange = () => showEws(ep.value);
const sm = document.getElementById('ewsm');
function showEws(c){
  const s = C[c], H = E.series[c]; ep.value = c;
  tab.querySelectorAll('tr[data-c]').forEach(tr => tr.classList.toggle('pick', tr.dataset.c===c));
  document.getElementById('ewname').textContent = `${c}: indicator history`;
  document.getElementById('ewcn').innerHTML = `Warning score <b>${fv(s.score)}</b> in ${s.year} · weight covered ${pct(s.coverage,0)} · top drivers: ${s.drivers.length ? s.drivers.map(esc2).join(', ') : 'none'}. Shaded bands: ◇ amber and △ red zones from the rulebook.`;
  sm.querySelectorAll('.chart').forEach(d => Plotly.purge(d));
  const show = IN.filter(i => H && H[i.id].some(v=>v!=null));
  sm.innerHTML = show.map(i=>`<div class="card"><h3>${esc2(i.label)}</h3><div class="muted" style="font-size:12px">${esc2(i.unit)} · risky when ${i.bad}${s.indicators[i.id].derived ? ' · latest value computed here' : ''}</div><div class="chart" id="ewc_${i.id}"></div></div>`).join('')
    + (show.length < IN.length ? `<div class="muted" style="font-size:12px;align-self:center">No data for: ${IN.filter(i=>!show.includes(i)).map(i=>esc2(i.label)).join(', ')}.</div>` : '');
  show.forEach(i => {
    const ys = H[i.id], xs = H.years, v = ys.filter(x=>x!=null).concat([i.amber, i.red]);
    let lo = Math.min(...v), hi = Math.max(...v); const pad = 0.12*(hi-lo || 1); lo -= pad; hi += pad;
    const [ab, rb] = i.bad==='high' ? [[i.amber, i.red], [i.red, hi]] : [[i.red, i.amber], [lo, i.red]];
    const bandS = ([y0, y1], g) => ({type:'rect', xref:'paper', x0:0, x1:1, y0, y1, fillcolor:RT[g].c, opacity:0.16, line:{width:0}, layer:'below'});
    const bandA = ([y0, y1], g) => ({xref:'paper', x:1, xanchor:'right', y:(y0+y1)/2, text:`${RT[g].i} ${g}`, showarrow:false, font:{size:10, color:ink2}, bgcolor:rgba2(surf2, 0.75)});
    Plotly.newPlot('ewc_' + i.id, [{type:'scatter', mode:'lines+markers', x:xs, y:ys, connectgaps:false, line:{color:SER5[0], width:2},
        marker:{size:5, color:SER5[0]}, hovertemplate:`%{x}: %{y:.1f} ${esc2(i.unit)}<extra></extra>`}],
      L({margin:{l:36,r:8,t:6,b:24}, showlegend:false, xaxis:{gridcolor:grid, tickformat:'d', nticks:5}, yaxis:{gridcolor:grid, range:[lo, hi], nticks:5},
        shapes:[bandS(ab,'amber'), bandS(rb,'red')], annotations:[bandA(ab,'amber'), bandA(rb,'red')]}), cfg);
  });
}
showEws(cn[0]);
}}}

// ---------------------------------------------------------------- spillover network (RPF-06)
{ const S = D.spill;
if (!S) { document.getElementById('spill').style.display = 'none'; } else {
const CH = Object.keys(S.channels), SHORT = {trade:'Trade', commodities:'Commodities', banks:'Banks', rates:'Rates', remittances:'Remittances'};
const sgn = (v, u) => `${v>0?'+':v<0?'−':''}${Math.abs(v)}${u}`;
const shockText = s => [...Object.entries(s.gdp).map(([k,v])=>`${k} GDP ${sgn(v,'%')}`), ...Object.entries(s.price).map(([k,v])=>`${k} price ${sgn(v,'%')}`),
  ...Object.entries(s.rate).map(([k,v])=>`${k} rates ${sgn(v,' bp')}`)].join(', ');
document.getElementById('sptag').textContent = `${S.model} · untested · draft elasticities`;
document.getElementById('spsub').textContent = 'How a shock abroad hits each country\'s GDP through five channels (trade, commodities, banks, rates, remittances), first round plus damped second-round effects through trade. Results are % changes in GDP. Not a forecast.';
document.getElementById('spscen').innerHTML = '<table><tr><th>Scenario</th><th>Shock</th><th>Id</th></tr>'
  + Object.entries(S.scenarios).map(([k,s])=>`<tr><td>${esc2(s.label)}</td><td>${esc2(shockText(s))}</td><td><code style="font-size:12px">${esc2(k)}</code></td></tr>`).join('') + '</table>';
document.getElementById('sppar').innerHTML = S.params.map(p=>`<div class="par"><div><b>${esc2(SHORT[p.channel] || 'Second round')}</b> · <code style="font-size:12px">${esc2(p.param)}</code> = <b>${p.value}</b> ${p.draft ? '<span class="tag">◇ Draft, to verify</span>' : ''}</div>`
  + `<div class="src">${esc2(p.source)}</div></div>`).join('');
if (!S.has_data) {
  document.getElementById('spempty').innerHTML = emptyCard(S.missing.map(f=>{ const ch = CH.find(c=>S.files[c]===f);
      return `<li><code>${esc2(f)}</code>${ch ? ': ' + esc2(S.channels[ch]) : ''}</li>`; }),
    'Each is long format (country, partner, value_pct_gdp, year, source); a missing file counts that channel as zero. See <b>docs/DATA.md</b> for sources, and sovrisk/spillover_data.py for the fetch and parse helpers. The scenarios and elasticities below need no data.');
} else {
document.getElementById('spbody').hidden = false;
if (S.missing.length) document.getElementById('spsub').textContent += ` Missing files (those channels count as zero): ${S.missing.join(', ')}.`;
const sp = document.getElementById('sppick'); Object.entries(S.scenarios).forEach(([k,s]) => sp.add(new Option(s.label, k)));
sp.onchange = () => showSpill(sp.value);
const mid = dark ? '#3a4350' : '#e3e6eb';
function showSpill(k){
  const R = S.results[k] || {countries:{}}, X = R.countries, cs = Object.keys(X).sort((a,b)=>X[a].total-X[b].total);
  document.getElementById('spshock').textContent = 'Shock: ' + shockText(S.scenarios[k]);
  document.getElementById('spbn').textContent = R.error ? `Not computed: ${R.error}` : !cs.length ? 'No country is exposed to this shock in the data loaded.'
    : `% change in GDP, first and second round together (second round converged in ${R.n_rounds - 1} rounds). The diamond is the total; worst hit on the left.`;
  Plotly.react('spbar', cs.length ? [...CH.map((ch,i)=>({type:'bar', name:SHORT[ch], x:cs, y:cs.map(c=>X[c].by_channel[ch] || null), marker:{color:SER5[i], line:{color:surf2, width:1}},
      customdata:cs.map(c=>[X[c].first[ch], X[c].second[ch]]), showlegend:true, hovertemplate:`${SHORT[ch]}: %{y:.3f}% (first round %{customdata[0]:.3f}, second %{customdata[1]:.3f})<extra></extra>`})),
    {type:'scatter', mode:'markers', name:'Total', x:cs, y:cs.map(c=>X[c].total), marker:{symbol:'diamond', size:11, color:ink, line:{color:surf2, width:2}}, hovertemplate:'Total: %{y:.3f}%<extra></extra>'}] : [],
    L({barmode:'relative', bargap:0.35, hovermode:'x unified', margin:{l:50,r:10,t:10,b:40}, legend:{orientation:'h', y:-0.18},
      yaxis:{gridcolor:grid, ticksuffix:'%', zeroline:true, zerolinecolor:ink2}, xaxis:{gridcolor:grid, type:'category'}}), cfg);
  const cols = S.exposure[k] || [], ec = cs.length ? cs : [...new Set(cols.flatMap(c=>Object.keys(c.values)))];
  const z = ec.map(c=>cols.map(col=>col.values[c] ?? null)), zm = Math.max(1e-9, ...z.flat().filter(v=>v!=null).map(Math.abs));
  document.getElementById('sphn').textContent = cols.length ? '% of the receiving country\'s GDP, latest year, for the partners this scenario shocks. Commodities are net exports (negative: net importer, gains on a price fall). Rates: US dollar share of public debt × gross financing need. Blank: no data.'
    : 'No exposure data for the partners this scenario shocks.';
  Plotly.react('spheat', cols.length ? [{type:'heatmap', x:cols.map(c=>`${SHORT[c.channel]}<br>${c.partner}`), y:ec, z, zmin:-zm, zmax:zm, zmid:0,
      colorscale:[[0, SER5[0]], [0.5, mid], [1, SER5[1]]], xgap:2, ygap:2, text:z.map(r=>r.map(v=>v==null ? '' : v.toFixed(1))), texttemplate:'%{text}',
      colorbar:{title:{text:'% GDP', side:'right'}, thickness:10}, hovertemplate:'%{y} · %{x}: %{z:.2f}% of GDP<extra></extra>', hoverongaps:false}] : [],
    L({margin:{l:50,r:10,t:10,b:60}, xaxis:{side:'bottom', tickangle:0, showgrid:false, zeroline:false}, yaxis:{type:'category', autorange:'reversed', showgrid:false, zeroline:false}}), cfg);
  document.getElementById('sptable').innerHTML = '<table><tr><th>Country</th>' + CH.map(ch=>`<th>${SHORT[ch]}</th>`).join('') + '<th>First round</th><th>Second round</th><th>Total</th></tr>'
    + cs.map(c=>{ const x = X[c], sum = o => CH.reduce((a,ch)=>a+o[ch],0);
        return `<tr><td>${esc2(c)}</td>${CH.map(ch=>`<td>${x.by_channel[ch].toFixed(3)}</td>`).join('')}<td>${sum(x.first).toFixed(3)}</td><td>${sum(x.second).toFixed(3)}</td><td><b>${x.total.toFixed(3)}</b></td></tr>`; }).join('')
    + '</table><div class="muted" style="font-size:12px;margin-top:6px">% change in GDP. Second-round effects are traced back to the channel that started them.</div>';
}
showSpill(Object.keys(S.scenarios)[0]);
}}}
</script>
<script>
// ---------------------------------------------------------------- live country data (needs python -m sovrisk.serve)
{ const el = id => document.getElementById(id), h = s => String(s ?? '').replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
  const FEEDS = {imf:'IMF World Economic Outlook', wb:'World Bank', bis:'BIS credit gap', market:'Yahoo Finance', ews:'Early-warning rating'};
  const RC = {green:'#1a9850', amber:'#d08c00', red:'#c0392b'};
  let codes = [];
  const offline = why => { el('lvnote').innerHTML = '<div class="card empty"><h3>Live pulls need the local server.</h3><div class="muted">Run <code>python -m sovrisk.serve</code> in the <code>sovereign-risk</code> folder and open <code>http://localhost:8080</code>. The server pulls from the IMF, World Bank, BIS and Yahoo Finance on your machine, so those sites must be reachable from it.' + (why ? ' (' + h(why) + ')' : '') + '</div></div>'; };
  async function init(){
    if (!location.protocol.startsWith('http')) return offline('');
    try { const r = await fetch('api/countries'); if (!r.ok) throw new Error((await r.json()).error || r.status); codes = await r.json(); }
    catch (e) { return offline('could not list countries: ' + e.message); }
    if (!codes.length) return offline('the country list is empty');
    codes.forEach(c => el('lvpick').add(new Option(`${c.name} (${c.iso3})`, c.iso3)));
    el('lvform').hidden = false; el('lvgo').onclick = () => pull(false); el('lvre').onclick = () => pull(true);
    const gl = el('golive'); if (gl && D.countries && Object.keys(D.countries).length) { gl.hidden = false; gl.onclick = () => {
      const n = (el('pick').value || '').toLowerCase(), c = codes.find(c => c.name.toLowerCase() === n) || codes.find(c => c.name.toLowerCase().startsWith(n));
      if (c) el('lvpick').value = c.iso3; const b = document.querySelector('#tabs button[data-g=live]'); if (b) b.click(); if (c) pull(false); }; }
  }
  async function pull(refresh){
    const iso = el('lvpick').value, fx = el('lvfx').value.trim(), q = new URLSearchParams({y0: el('lvy0').value || 2000});
    if (fx) q.set('fx', fx); if (refresh) q.set('refresh', 1);
    el('lvstat').textContent = `Pulling ${iso}…`; el('lvgo').disabled = el('lvre').disabled = true;
    try { const r = await fetch(`api/country/${iso}?${q}`), p = await r.json(); if (!r.ok) throw new Error(p.error || r.status); show(p);
      el('lvstat').textContent = `${p.name || iso}: pulled ${p.pulled}`; }
    catch (e) { el('lvstat').textContent = 'Pull failed: ' + e.message; }
    finally { el('lvgo').disabled = el('lvre').disabled = false; }
  }
  function show(p){
    el('lvbody').hidden = false;
    el('lvfeeds').innerHTML = '<table><tr><th>Feed</th><th>Status</th><th>Series</th><th>Not returned</th><th>Time</th></tr>' + Object.entries(p.feeds).map(([k, f]) =>
      `<tr><td>${FEEDS[k] || h(k)}</td><td>${f.status === 'ok' ? '<b style="color:#1a9850">✓ OK</b>' : '<b style="color:#c0392b">✕ Failed</b><div class="muted" style="font-size:12px">' + h(f.error) + '</div>'}</td>` +
      `<td>${k === 'ews' ? (f.rating ? 'rated' : '') : Object.keys(f.series || {}).length}</td><td class="muted">${h((f.missing || []).join(', '))}</td><td>${f.seconds ?? ''}s</td></tr>`).join('') + '</table>';
    const e = p.feeds.ews;
    el('lvews').innerHTML = e && e.status === 'ok' && e.rating ? `<div class="kpis" style="margin:0 0 10px"><div class="kpi"><span>Warning score (0 to 100)</span><b>${e.rating.score == null ? '—' : e.rating.score.toFixed(0)}</b></div><div class="kpi"><span>Year rated</span><b>${e.rating.year}</b></div></div>` +
      '<table><tr><th>Indicator</th><th>Value</th><th>Year</th><th>Rating</th></tr>' + Object.values(e.rating.indicators).map(i =>
        `<tr><td>${h(i.label)} <span class="muted">(${h(i.unit)})</span></td><td>${i.value == null ? '—' : (+i.value).toFixed(1)}</td><td>${i.year ?? ''}</td><td>${i.rating ? `<b style="color:${RC[i.rating]}">${i.rating}</b>` : '<span class="muted">no data</span>'}</td></tr>`).join('') +
      `</table><div class="muted" style="font-size:12px;margin-top:6px">${h(e.model)} · ${h(e.weighting)} weights · untested · not a rating</div>`
      : `<div class="muted">${e ? h(e.error || 'Not computed.') : 'Not computed.'}</div>`;
    const all = Object.entries(p.feeds).flatMap(([k, f]) => Object.entries(f.series || {}).map(([id, s]) => ({k, id, s})));
    el('lvcharts').innerHTML = all.map((o, i) => `<div class="card"><h3>${h(o.s.label)}</h3><div class="muted" style="font-size:12px">${h(o.s.unit)} · ${h(o.s.source)}</div><div id="lvc${i}" class="chart"></div></div>`).join('');
    all.forEach((o, i) => Plotly.newPlot(`lvc${i}`, [{type:'scatter', mode:'lines', x:o.s.points.map(q => q[0]), y:o.s.points.map(q => q[1]), line:{color:'#4c78a8', width:2},
      hovertemplate:'%{x}: %{y:.2f}<extra></extra>'}], L({margin:{l:45,r:10,t:10,b:30}, showlegend:false, xaxis:{gridcolor:grid, nticks:6, ...(typeof o.s.points[0]?.[0] === 'number' ? {tickformat:'d'} : {type:'date'})}, yaxis:{gridcolor:grid, type:'linear'}}), cfg));
  }
  init();
}
</script>
<script>
// Group the page by type of work: one tab per group, each holding the sections below. A group whose sections all
// hid themselves (no data) gets no tab. The open tab is kept in the address (#credit) so a link opens it.
{ const GROUPS = [
    {id:'credit', label:'Sovereign credit', sub:'Scorecard, levers, default, restructuring', secs:['sov']},
    {id:'live', label:'Live country data', sub:'IMF, World Bank, BIS, Yahoo', secs:['live']},
    {id:'portfolio', label:'Portfolio and insurance', sub:'Monte Carlo loss, political risk insurance', secs:['port']},
    {id:'dsa', label:'Debt sustainability', sub:'IMF MAC SRDSF', secs:['srdsf']},
    {id:'macro', label:'Macro surveillance', sub:'Early warning, spillovers', secs:['ews','spill']},
    {id:'ppp', label:'PPP fiscal risk', sub:'PFRAM 2.0', secs:['pfram']},
    {id:'muni', label:'Municipal credit', sub:'Town scorecard', secs:['muni']}];
  const el = id => document.getElementById(id), shown = id => el(id) && el(id).style.display !== 'none';
  const live = GROUPS.filter(g => g.secs.some(shown)), nav = el('tabs');
  live.forEach(g => { const b = document.createElement('button'); b.setAttribute('role','tab'); b.dataset.g = g.id;
    b.innerHTML = `${g.label}<small>${g.sub}</small>`; b.onclick = () => { openTab(g.id); history.replaceState(null, '', '#' + g.id); }; nav.appendChild(b); });
  function openTab(id){
    live.forEach(g => g.secs.filter(shown).forEach(s => { el(s).hidden = g.id !== id; }));
    nav.querySelectorAll('button').forEach(b => b.setAttribute('aria-selected', b.dataset.g === id));
    window.dispatchEvent(new Event('resize'));   // charts drawn while hidden take their real width now
  }
  const want = location.hash.slice(1);
  if (live.length) openTab(live.some(g => g.id === want) ? want : live[0].id); else nav.hidden = true;
}
</script></body></html>'''


if __name__ == '__main__':
    main()
