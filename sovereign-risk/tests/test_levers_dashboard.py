"""Lever and dashboard tests that need no analyst inputs."""
import json

import pytest

from sovrisk import load_config
from sovrisk.dashboard import dashboard_data, grade, render
from sovrisk.levers import _improve, load_levers


def test_levers_file_is_valid():
    cfg = load_config()
    L = load_levers(cfg)
    assert len(L['levers']) >= 10
    assert all(lv['category'] in L['categories'] and lv['label'] and lv['detail'] for lv in L['levers'])


def test_improve_moves_toward_lower_risk():
    up = {'type': 'num', 'thresholds': [10, 20, 30, 45, 60]}       # higher value is riskier
    down = {'type': 'num', 'thresholds': [150, 125, 100, 75, 50]}  # higher value is safer
    assert _improve(up, 40, {'improve': 5}) == 35
    assert _improve(down, 80, {'improve': 15}) == 95
    assert _improve(up, 40, {'improve_pct': 10}) == pytest.approx(36)
    assert _improve({'type': 'rubric'}, 10, {'improve': 25}) == 0
    assert _improve(up, None, {'improve': 5}) is None


def test_dashboard_renders_without_inputs():
    cfg = load_config()
    html = render(dashboard_data(cfg))
    assert 'FOR RESEARCH PURPOSES ONLY. CONFIDENTIAL.' in html and 'Stability levers' in html
    assert grade(55.0) == 6 and grade(100) == 10


def test_dashboard_has_pfram_section():
    data = dashboard_data(load_config())
    F = data['pfram']
    assert [p['id'] for p in F['projects']] == ['P1', 'P2', 'P3']
    assert all(len(p['cases']) == 1 + len(F['shocks']) for p in F['projects'])
    assert F['portfolio'][0]['year'] == 2026 and 'PPP fiscal risk (PFRAM 2.0)' in render(data)


def test_dashboard_has_muni_section():
    data = dashboard_data(load_config())
    U = data['muni']
    assert len(U['towns']) == 10 and U['model'].startswith('M-15')
    assert 'Municipal credit scorecard' in render(data)


def test_dashboard_has_srdsf_section():
    data = dashboard_data(load_config())
    R = data['srdsf']
    sig = {s['label']: s for s in R['signals']}
    assert sig['Medium term']['mechanical'] == 'High' and sig['Medium term']['final'] == 'Moderate'
    assert sig['Overall']['final'] == 'Low' and sig['Medium term: fanchart']['mechanical'] == 'High'
    assert R['mt']['index'] == pytest.approx(0.4046, abs=1e-3) and R['mt']['signal'] == 'High'
    assert R['fan']['years'][0] == 2018 and len(R['fan']['p']['95']) == len(R['fan']['years'])
    assert len(R['stress']['tests']) == 5 and R['run']['settled'] and R['run']['gfn_converged']
    html = render(data)
    assert 'Debt sustainability (MAC SRDSF)' in html and 'not endorsed by the IMF' in html
    assert 'Sample country (fictional data from the IMF template)' in html
    sec = html[html.index('<section id="srdsf">'):html.index('</section>', html.index('<section id="srdsf">'))]
    assert 'Albania' not in json.dumps(R) and 'Albania' not in sec   # the selector country drives lookups only
    assert 'Debt sustainability (MAC SRDSF)' in render(dict(data, srdsf=None))   # section hides itself, page renders


def _section(html, sid):
    i = html.index(f'<section id="{sid}">')
    return html[i:html.index('</section>', i)]


def test_dashboard_ews_and_spillover_empty_state():
    """No country data ships with the repository: both sections render their empty state and the rulebook tables."""
    from sovrisk.dashboard import ews_data, spillover_data
    E, S = ews_data(), spillover_data()
    assert E['model'] == 'M-22 v0.1' and not E['has_data'] and E['countries'] == {} and E['series'] == {}
    assert [n['file'] for n in E['needs'] if n['missing']][0] == 'data/ews_panel.csv'
    assert any('ews_panel.csv is missing' in n for n in E['notes'])
    assert {i['id'] for i in E['indicators']} >= {'reserves_months', 'inflation', 'credit_gap'}
    assert all(i['amber'] is not None and i['red'] is not None and i['bad'] in ('low', 'high') for i in E['indicators'])
    assert S['model'] == 'M-23 v0.1' and not S['has_data'] and S['results'] == {}
    assert 'data/spill_trade.csv' in S['missing'] and len(S['missing']) == 5
    assert 'us_recession' in S['scenarios'] and S['params'] and all(p['draft'] for p in S['params'])
    data = dashboard_data(load_config())
    html = render(data)
    ews, spill = _section(html, 'ews'), _section(html, 'spill')
    assert html.index('<section id="srdsf">') < html.index('<section id="ews">') < html.index('<section id="spill">')
    assert 'M-22 v0.1 · untested · not a rating' in ews and 'Indicator thresholds' in ews and 'id="ewempty"' in ews
    assert 'M-23 v0.1 · untested · draft elasticities' in spill and 'Elasticities' in spill and 'Scenarios' in spill
    assert 'No country data is loaded.' in html and 'docs/DATA.md' in html
    assert 'Macro early-warning panel' in render(dict(data, ews=None, spill=None))   # sections hide, page renders


def _fake_root(tmp_path):
    """Hand-made test inputs in a temporary copy (never in data/ of the repository)."""
    import csv
    import shutil
    from sovrisk.config import ROOT
    root = tmp_path / 'root'
    shutil.copytree(ROOT / 'rulebook', root / 'rulebook')
    (root / 'data').mkdir()
    with open(root / 'data' / 'ews_panel.csv', 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['country', 'year', 'reserves_months', 'reserves_std', 'ca_gdp', 'reer', 'credit_gdp', 'credit_gap', 'inflation'])
        for y in range(2010, 2025):
            w.writerow(['XAA', y, 6, 200, -1, 100, 30, 0, 3])
            w.writerow(['XBB', y, 2, 90, -6, 100, 40, 12, 25 if y == 2024 else 5])
    def wr(name, rows):
        with open(root / 'data' / name, 'w', newline='') as f:
            w = csv.writer(f)
            w.writerow(['country', 'partner', 'value_pct_gdp', 'year', 'source'])
            w.writerows([[c, p, v, 2024, 'test'] for c, p, v in rows])
    wr('spill_trade.csv', [('XAA', 'USA', 10), ('XBB', 'USA', 5), ('XBB', 'XAA', 2)])
    wr('spill_commodities.csv', [('XAA', 'oil', 8), ('XBB', 'oil', -4)])
    wr('spill_rates.csv', [('XAA', 'usd_debt_share', 50), ('XAA', 'gfn', 10)])
    return root


def test_dashboard_ews_and_spillover_with_fake_data(tmp_path):
    from sovrisk.dashboard import ews_data, spillover_data
    root = _fake_root(tmp_path)
    E = ews_data(root)
    assert E['has_data'] and set(E['countries']) == {'XAA', 'XBB'} and E['weighting'] == 'rulebook'
    a, b = E['countries']['XAA'], E['countries']['XBB']
    assert a['score'] == 0 and b['score'] == pytest.approx(500 / 6) and b['indicators']['inflation']['rating'] == 'red'
    assert E['series']['XBB']['years'] == list(range(2010, 2025)) and E['series']['XBB']['inflation'][-1] == 25
    assert E['series']['XAA']['gfn_gdp'] == [None] * 15
    S = spillover_data(root)
    assert S['has_data'] and set(S['missing']) == {'data/spill_banks.csv', 'data/spill_remittances.csv'}
    us = S['results']['us_recession']['countries']
    assert us['XAA']['by_channel']['trade'] == pytest.approx(10 / 100 * -2 * 2.0 * 0.7)
    assert us['XBB']['second']['trade'] < 0 and set(us['XAA']['by_channel']) == {'trade', 'commodities', 'banks', 'rates', 'remittances'}
    assert [(c['channel'], c['partner']) for c in S['exposure']['us_recession']] == [('trade', 'USA')]
    oil = S['exposure']['oil_down_30'][0]
    assert oil['channel'] == 'commodities' and oil['values'] == {'XAA': 8, 'XBB': -4}
    assert S['results']['oil_down_30']['countries']['XBB']['by_channel']['commodities'] > 0   # importer gains
    rates = S['exposure']['us_rates_up_200'][0]
    assert rates['channel'] == 'rates' and rates['values']['XAA'] == pytest.approx(5) and rates['values']['XBB'] is None
    html = render(dict(dashboard_data(load_config()), ews=E, spill=S))
    assert '"XBB"' in html and 'id="ewbody"' in _section(html, 'ews') and 'id="spbody"' in _section(html, 'spill')
