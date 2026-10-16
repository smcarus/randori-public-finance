"""Lever and dashboard tests that need no analyst inputs."""
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
