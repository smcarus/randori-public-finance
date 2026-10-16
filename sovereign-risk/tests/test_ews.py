"""M-22 early-warning panel: ratings, percentiles, signals-method weights, one-sided HP filter, missing data.
All panels here are hand-made test inputs, not country data."""
import math
import shutil

import numpy as np
import pytest

from sovrisk import ews as E

RB = E.load()['rulebook']
IND = {i['id']: i for i in RB['indicators']}


def test_rulebook_is_valid():
    assert E.check_rulebook(RB) == []


@pytest.mark.parametrize('ind,v,want', [
    # low is bad: amber < 4, red < 3
    ('reserves_months', 5, 'green'), ('reserves_months', 4, 'green'), ('reserves_months', 3.99, 'amber'),
    ('reserves_months', 3, 'amber'), ('reserves_months', 2.5, 'red'),
    ('reserves_std', 150, 'green'), ('reserves_std', 120, 'amber'), ('reserves_std', 99, 'red'),
    ('ca_gdp', -2, 'green'), ('ca_gdp', -4, 'amber'), ('ca_gdp', -5, 'amber'), ('ca_gdp', -6, 'red'),
    # high is bad
    ('inflation', 10, 'green'), ('inflation', 10.1, 'amber'), ('inflation', 20, 'amber'), ('inflation', 21, 'red'),
    ('credit_gap', 1, 'green'), ('credit_gap', 5, 'amber'), ('credit_gap', 12, 'red'),
    ('reer_dev', 15, 'amber'), ('reer_dev', 25, 'red'), ('gfn_gdp', 12, 'amber'), ('gfn_gdp', 16, 'red'),
    ('inflation', None, None), ('inflation', '', None), ('inflation', 'n/a', None),
])
def test_threshold_ratings(ind, v, want):
    assert E.rate(IND[ind], v) == want


def test_bad_thresholds_are_caught():
    rb = {'indicators': [dict(IND['inflation'], red=5), dict(IND['ca_gdp'], bad='up')]}
    errs = E.check_rulebook(rb)
    assert len(errs) == 2


def test_percentile_own_history():
    h = [1, 2, 3, 4, 5]
    assert E.percentile(5, h) == 100 and E.percentile(1, h) == 0 and E.percentile(3, h) == 50
    assert E.percentile(2, [2, 2, 1, None, '']) == pytest.approx(75)   # one below, one tie: (1 + 0.5) / 2
    assert E.percentile(3, [3]) is None and E.percentile(None, h) is None


def _crisis_panel():
    # One country, 2000-2009, crisis starting 2005. Window 2 years: 2003 and 2004 are pre-crisis; 2005 is left out.
    infl = [5, 5, 5, 15, 25, 30, 5, 5, 12, 5]       # signals 2003, 2004 (good) and 2008 (false): A2 B1 C0 D6
    ca = [-4, -4, -1, -4, -1, -1, -4, -1, -1, -1]   # signals 2000, 2001, 2003, 2006: A1 B3 C1 D4
    rows = [{'country': 'X', 'year': 2000 + i, 'inflation': infl[i], 'ca_gdp': ca[i], 'reserves_months': 6}
            for i in range(10)]
    return rows, [{'country': 'X', 'year': 2005, 'type': 'currency'}]


def test_nsr_hand_worked():
    rows, crises = _crisis_panel()
    n = E.nsr_table(RB, rows, crises)
    assert (n['inflation']['A'], n['inflation']['B'], n['inflation']['C'], n['inflation']['D']) == (2, 1, 0, 6)
    assert (n['ca_gdp']['A'], n['ca_gdp']['B'], n['ca_gdp']['C'], n['ca_gdp']['D']) == (1, 3, 1, 4)
    assert n['inflation']['nsr'] == pytest.approx((1 / 7) / (2 / 2))
    assert n['ca_gdp']['nsr'] == pytest.approx((3 / 7) / (1 / 2))
    assert math.isinf(n['reserves_months']['nsr']) and math.isinf(n['credit_gap']['nsr'])   # no good signals / no data
    w = E.nsr_weights(n)
    # 1/NSR = 7 and 7/6, normalised: 6/7 and 1/7; the rest dropped
    assert w['inflation'] == pytest.approx(6 / 7) and w['ca_gdp'] == pytest.approx(1 / 7)
    assert sum(w.values()) == pytest.approx(1) and w['reserves_months'] == 0


def test_nsr_at_or_above_one_is_dropped():
    w = E.nsr_weights({'a': {'nsr': 0.5}, 'b': {'nsr': 1.0}, 'c': {'nsr': 2.0}, 'd': {'nsr': 0.25}})
    assert w == pytest.approx({'a': 1 / 3, 'b': 0, 'c': 0, 'd': 2 / 3})


def test_crisis_type_filter():
    rows, crises = _crisis_panel()
    rb = dict(RB, signals=dict(RB['signals'], crisis_types=['banking']))
    assert math.isinf(E.nsr_table(rb, rows, crises)['inflation']['nsr'])


def test_table_uses_nsr_weights_and_names_drivers():
    rows, crises = _crisis_panel()
    t = E.ews_table(rows, crises=crises, rb=RB)
    assert t['weighting'].startswith('signals')
    s = t['countries']['X']
    assert s['year'] == 2009 and s['score'] == 0 and s['drivers'] == []
    t = E.ews_table(rows, crises=crises, rb=RB, year=2008)    # inflation 12 amber, ca -1 green
    s = t['countries']['X']
    assert s['score'] == pytest.approx(50 * 6 / 7) and s['drivers'] == ['Inflation']
    assert s['indicators']['inflation']['percentile'] == pytest.approx(100 * 5 / 8)   # 12 vs 5,5,5,15,25,30,5,5,12: five below


# ---- HP filter ---------------------------------------------------------------------------------------------------

def test_hp_linear_series_has_zero_gap():
    y = 50 + 2.5 * np.arange(30)
    for lam in (1562.5, 400000):
        assert np.allclose(E.hp_trend(y, lam), y)
        assert np.allclose(E.hp_one_sided(y, lam), y)
    g = E.credit_gap_series(range(1990, 2020), y, 1562.5, 10)
    assert min(g) == 1999 and np.allclose(list(g.values()), 0, atol=1e-8)


def test_hp_lambda_zero_is_identity_and_three_points_by_hand():
    y = np.array([1.0, 4.0, 2.0, 8.0])
    assert np.allclose(E.hp_trend(y, 0), y)
    # n = 3, lam = 1: (I + K'K) tau = y with K = [1 -2 1]; check the solution satisfies the normal equations
    y3 = np.array([0.0, 3.0, 0.0])
    tau = E.hp_trend(y3, 1)
    k = tau[0] - 2 * tau[1] + tau[2]
    assert np.allclose(tau + k * np.array([1, -2, 1]), y3)
    # k = (y0 - 2y1 + y2) - 6k, so k = -6/7 and tau = y - k(1, -2, 1) = (6/7, 9/7, 6/7)
    assert tau == pytest.approx([6 / 7, 9 / 7, 6 / 7])


def test_one_sided_uses_only_past_data():
    rng = np.random.default_rng(1)
    y = np.cumsum(rng.normal(size=40)) + 100
    one = E.hp_one_sided(y, 1562.5, min_obs=5)
    assert np.isnan(one[:4]).all() and not np.isnan(one[4:]).any()
    for t in (4, 17, 39):
        assert one[t] == pytest.approx(E.hp_trend(y[:t + 1], 1562.5)[-1])
    # last point equals the two-sided trend on the full sample; earlier points differ from it
    two = E.hp_trend(y, 1562.5)
    assert one[-1] == pytest.approx(two[-1])
    assert not np.allclose(one[10:-1], two[10:-1])
    # changing the future does not move the trend up to t
    y2 = y.copy()
    y2[25:] += 50
    assert np.allclose(E.hp_one_sided(y2, 1562.5, 5)[:25], one[:25], equal_nan=True)


def test_credit_gap_restarts_after_a_break_and_bis_gap_is_kept():
    yrs = list(range(2000, 2012)) + list(range(2014, 2020))
    g = E.credit_gap_series(yrs, [float(i) for i in range(len(yrs))], 1562.5, 10)
    assert 2011 in g and 2014 not in g and 2019 not in g          # only 6 years since the break
    rows = [{'country': 'Z', 'year': 2000 + i, 'credit_gdp': 40 + i * i, 'credit_gap': 7.0 if i == 11 else None}
            for i in range(12)]
    f = E.fill_derived(RB, rows)
    assert f[11]['credit_gap'] == 7.0 and 'credit_gap' not in f[11]['_derived']
    assert f[10]['credit_gap'] > 0 and 'credit_gap' in f[10]['_derived'] and f[8]['credit_gap'] is None


def test_reer_deviation_from_previous_ten_years():
    rows = [{'country': 'R', 'year': 2000 + i, 'reer': 100.0} for i in range(10)] + \
           [{'country': 'R', 'year': 2010, 'reer': 125.0}]
    f = E.fill_derived(RB, rows)
    assert f[10]['reer_dev'] == pytest.approx(25) and f[9].get('reer_dev') is None
    assert E.ews_table(rows, rb=RB)['countries']['R']['indicators']['reer_dev']['rating'] == 'red'


# ---- missing data ------------------------------------------------------------------------------------------------

def test_missing_indicators_drop_out_and_weights_rescale():
    rows = [{'country': 'M', 'year': 2020, 'inflation': 25, 'ca_gdp': '', 'reserves_months': 5}]
    s = E.ews_table(rows, rb=RB)['countries']['M']
    assert s['score'] == pytest.approx(50)          # red and green, equal weights
    assert s['coverage'] == pytest.approx(2 / 7)
    assert s['indicators']['ca_gdp']['rating'] is None and s['indicators']['gfn_gdp']['value'] is None
    assert sum(x['points'] for x in s['indicators'].values() if x['points']) == pytest.approx(s['score'])
    assert s['drivers'] == ['Inflation']


def test_stale_values_and_empty_countries():
    rows = [{'country': 'S', 'year': 2019, 'inflation': 15}, {'country': 'S', 'year': 2020, 'inflation': None},
            {'country': 'N', 'year': 2020}]
    t = E.ews_table(rows, rb=RB)['countries']
    assert t['S']['indicators']['inflation']['year'] == 2019 and t['S']['indicators']['inflation']['rating'] == 'amber'
    rb = dict(RB, stale_years=0)
    assert E.ews_table(rows, rb=rb)['countries']['S']['score'] is None
    assert t['N']['score'] is None and t['N']['drivers'] == []


def test_missing_files_are_reported(tmp_path):
    (tmp_path / 'rulebook').mkdir()
    shutil.copy(E.ROOT / 'rulebook' / 'ews.yaml', tmp_path / 'rulebook')
    d = E.load(tmp_path)
    assert d['panel'] == [] and any('ews_panel.csv is missing' in n for n in d['notes'])
    t = E.ews_table(d)
    assert t['countries'] == {} and t['weighting'] == 'rulebook'
