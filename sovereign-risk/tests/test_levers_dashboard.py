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
