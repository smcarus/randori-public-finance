"""RPF-03 municipal credit scorecard: rulebook checks and scoring behaviour on illustrative towns."""
import copy

import pytest

from sovrisk import muni as M

D = M.load()
RB = D['rulebook']


def test_rulebook_is_valid():
    assert M.check_rulebook(RB) == []


def test_bad_weights_are_caught():
    rb = copy.deepcopy(RB)
    rb['factors']['economy']['weight'] = 0.4
    assert any('factor weights' in e for e in M.check_rulebook(rb))


def test_points_add_up_to_score():
    for t in D['towns']:
        s = M.score_town(RB, t)
        assert sum(x['points'] for x in s['indicators'].values() if x['points'] is not None) == pytest.approx(s['score'])
        assert 0 <= s['score'] <= 100 and s['grade'] == M.grade(s['score'])


@pytest.mark.parametrize('ind', [i for i in RB['indicators'] if i.get('type', 'num') == 'num'], ids=lambda i: i['id'])
def test_moving_toward_safe_end_never_raises_score(ind):
    """Monotonicity: a value nearer the 0-score threshold never gives a higher town score."""
    t0 = dict(D['towns'][4])
    t = ind['thresholds']
    lo, hi = M.score_town(RB, {**t0, ind['id']: t[0]}), M.score_town(RB, {**t0, ind['id']: t[4]})
    mid = M.score_town(RB, {**t0, ind['id']: t[2]})
    assert lo['score'] <= mid['score'] <= hi['score']


def test_missing_indicator_rescales_weights():
    t = dict(D['towns'][0])
    t['opeb_pct_rev'] = None
    s = M.score_town(RB, t)
    assert s['indicators']['opeb_pct_rev']['score'] is None
    assert s['factors']['debt']['coverage'] == pytest.approx(0.85)
    assert sum(x['points'] for x in s['indicators'].values() if x['points'] is not None) == pytest.approx(s['score'])


def test_flags_and_stress():
    assert M.indicator_score({'type': 'flag'}, 'yes') == 0 and M.indicator_score({'type': 'flag'}, 'no') == 100
    r = M.run_all()
    for t in r['towns'].values():
        assert all(t['stress'][c]['score'] >= t['base']['score'] - 1e-9 for c in RB['stress'])


def test_percentiles_run_0_to_100():
    p = M.percentiles(RB, D['towns'])
    col = [p[t['town']]['net_debt_pct_eqv'] for t in D['towns']]
    assert min(col) == 0 and max(col) == 100


def test_golden_illustrative_scores():
    r = M.run_all()['towns']
    assert r['Town A']['base']['score'] == pytest.approx(9.3, abs=0.05)
    assert r['Town F']['base']['score'] == pytest.approx(81.2, abs=0.05)
    assert [n for n, _ in sorted(r.items(), key=lambda kv: kv[1]['base']['score'])][:3] == ['Town A', 'Town C', 'Town B']


def test_all_towns_are_marked_illustrative():
    assert all('ILLUSTRATIVE' in t['note'] for t in D['towns'])


def test_any_state_with_ma_benchmark():
    """Towns come from several states; a state with no levy limit drops that indicator; administration is scored
    against the Massachusetts benchmark for every town."""
    r = M.run_all()['towns']
    assert len({t['state'] for t in r.values()}) > 3 and RB['benchmark_state'] == 'Massachusetts'
    b = r['Town B']['base']
    assert r['Town B']['state'] == 'CT' and b['indicators']['excess_levy_capacity']['score'] is None
    assert b['factors']['finances']['coverage'] == pytest.approx(0.85)
    assert r['Town A']['base']['benchmark'] == {'state': 'Massachusetts', 'met': 8, 'of': 8, 'gaps': []}
    d = r['Town D']['base']['benchmark']
    assert d['met'] == 0 and len(d['gaps']) == 8
    assert all('benchmark' in i for i in RB['indicators'] if i['factor'] == 'governance' and i['id'] != 'audit_findings')
