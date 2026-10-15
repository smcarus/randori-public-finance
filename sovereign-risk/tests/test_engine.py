"""Engine tests that need no analyst inputs. Expected values are worked by hand from the formulas."""
import math

import numpy as np
import pytest

from sovrisk.backtest import kupiec, pd_from_score
from sovrisk.default_fit import auc, benchmark_gap, blend_pd, cds_implied_pd, logit_fit
from sovrisk.restructuring import bond_recovery, holdout_risk, pv, recovery_at_default, schedule
from sovrisk.scoring import _interp


def test_interp_up_and_down():
    t = [0, 10, 20, 30, 40]
    assert _interp(-5, t) == 0 and _interp(45, t) == 100
    assert _interp(15, t) == pytest.approx(37.5)
    assert _interp(15, t[::-1]) == pytest.approx(62.5)


def test_pd_from_score():
    assert pd_from_score(50, -9, 0.09) == pytest.approx(1 / (1 + math.exp(4.5)))
    assert pd_from_score(100, -9, 0.09, cap=0.45) == 0.45


def test_kupiec():
    lr, p = kupiec(5, 250, 0.01)
    exp = -2 * (245 * math.log(0.99) + 5 * math.log(0.01)) + 2 * (245 * math.log(245 / 250) + 5 * math.log(5 / 250))
    assert lr == pytest.approx(exp)
    assert 0 < p < 1
    assert kupiec(0, 0, 0.01) == (None, None)


def test_bullet_bond_at_par():
    flows = schedule(100, 0.05, 2030, None, 2025)
    assert [cf for _, cf in flows] == [5, 5, 5, 5, 105]
    assert pv(flows, 0.05, 2025) == pytest.approx(100)


def test_bond_recovery_no_change_means_no_haircut():
    bond = {'face': 100, 'coupon': 0.05, 'maturity': 2030, 'amort_start': None}
    terms = {'face_haircut': 0, 'new_coupon': 0.05, 'new_maturity': 2030, 'grace_years': 10, 'exit_yield': 0.05}
    r = bond_recovery(bond, terms, 2025)
    assert r['npv_haircut_sz'] == pytest.approx(0)
    assert r['recovery_per_100'] == pytest.approx(100)


def test_restructuring_helpers():
    assert holdout_risk('None') == 'High' and holdout_risk('Two-limb') == 'Low'
    assert recovery_at_default(50, 12, 0.1) == pytest.approx(50 / 1.1)


def test_cds_and_blend():
    assert cds_implied_pd(600, 0.4) == pytest.approx(1 - math.exp(-0.1))
    assert cds_implied_pd(None) is None
    assert blend_pd(None, 0.02, 0.7) == 0.02
    assert blend_pd(0.1, 0.1, 0.7) == pytest.approx(0.1)
    g, flag = benchmark_gap(0.5, 0.1, 1.0)
    assert g == pytest.approx(math.log(9)) and flag == 'Model above market'


def test_logit_recovers_coefficients():
    rng = np.random.default_rng(0)
    x = rng.normal(size=20000)
    X = np.column_stack([np.ones_like(x), x])
    y = (rng.random(20000) < 1 / (1 + np.exp(-(-2 + 1.5 * x)))).astype(float)
    b = logit_fit(X, y)
    assert b[0] == pytest.approx(-2, abs=0.1) and b[1] == pytest.approx(1.5, abs=0.1)
    assert auc(1 / (1 + np.exp(-X @ b)), y) > 0.8
