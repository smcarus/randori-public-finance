"""PFRAM 2.0 port: parity with the real workbook, recalculated in LibreOffice (scripts/pfram_golden.py)."""
import json
import math
from pathlib import Path

import pytest

from sovrisk import pfram as P

GOLDEN = Path(__file__).resolve().parent / 'golden' / 'pfram'
CASES = sorted(p.stem for p in GOLDEN.glob('*.json'))
DATA = P.load()


def _run(case):
    g = json.loads((GOLDEN / f'{case}.json').read_text())
    p = next(x for x in DATA['projects'] if x.id == g['project'])
    shock = DATA['shocks'][g['shock']] if g['shock'] else None
    return g, P.run_project(p, DATA['macro'], shock, effective_rate=g['wacc'])


@pytest.mark.parametrize('case', CASES)
def test_every_template_row_matches_workbook(case):
    g, res = _run(case)
    R = res['rows']
    checked = 0
    for r, xs in g['rows'].items():
        r = int(r)
        if r not in R:               # heading and spacer rows: the workbook must show no numbers there
            assert not any(isinstance(v, (int, float)) and v for v in xs), f'row {r} not computed'
            continue
        for i, v in enumerate(xs):
            py = R[r][i] if i < len(R[r]) else 0.0
            if isinstance(v, (int, float)):
                assert py == pytest.approx(v, rel=1e-7, abs=1e-6), f'{case} row {r} column {i}'
                checked += 1
            elif v is not None:      # an Excel error such as #DIV/0!
                assert py is None or math.isnan(py) or py == 0, f'{case} row {r} column {i}: workbook shows {v}'
    assert checked > 5000


@pytest.mark.parametrize('case', CASES)
def test_scalars_match_workbook(case):
    g, res = _run(case)
    s, R, T = g['scalars'], res['rows'], res['rows']['termination']
    assert res['summary']['share_government_funded'] == pytest.approx(s['I17'], abs=1e-9)
    assert sum(R[200]) == pytest.approx(s['T36'], rel=1e-9, abs=1e-6)
    assert -sum(R[233]) == pytest.approx(s['T37'], rel=1e-9, abs=1e-6)
    assert res['summary']['project_irr'] == pytest.approx(s['T38'], abs=1e-9)
    assert res['summary']['equity_irr'] == pytest.approx(s['C169'], abs=1e-9)
    assert T['book_value'] == pytest.approx(s['A651'], abs=1e-6)
    assert T['lost_profit_npv'] == pytest.approx(s['A652'], rel=1e-9)
    assert res['summary']['debt_guarantee_max'] == pytest.approx(s['R14'], abs=1e-6)


@pytest.mark.parametrize('case', [c for c in CASES if '_' not in c])
def test_effective_rate_meets_goal_seek_condition(case):
    """EIR_Seek: total net lending/borrowing equals minus total availability payments (or WACC = project IRR)."""
    g, _ = _run(case)
    s = g['scalars']
    if s['T37'] == 0:
        assert g['wacc'] == pytest.approx(s['T38'], abs=1e-9)
    else:
        assert s['T36'] == pytest.approx(s['T37'], abs=1e-4)


def test_risk_rating_table():
    assert P.risk_rating('Low', 'Low') == 'Irrelevant'
    assert P.risk_rating('Low', 'Medium') == P.risk_rating('Medium', 'Low') == 'Low'
    assert P.risk_rating('Low', 'High') == P.risk_rating('Medium', 'Medium') == 'Medium'
    assert P.risk_rating('High', 'Medium') == 'High'
    assert P.risk_rating('high', 'HIGH') == 'Critical'
    assert P.risk_rating('', 'High') == ''


def test_portfolio_adds_projects():
    res = [P.run_project(p, DATA['macro']) for p in DATA['projects']]
    pf = P.portfolio(res, DATA['macro'])
    y0 = pf[0]
    assert y0['ppp_debt'] == pytest.approx(sum(r['rows'][208][0] for r in res))
    assert y0['gross_debt_with_ppp_pct'] == pytest.approx(
        (DATA['macro'].gross_debt[0] * 1e3 + y0['ppp_debt']) / (DATA['macro'].nominal_gdp[0] * 1e3) * 100)


def test_start_year_must_match_macro():
    p = DATA['projects'][0]
    q = P.Project.from_dict({**{k: getattr(p, k) for k in ('id', 'name', 'funding', 'contract_length')},
                             'start_year': p.start_year + 1})
    with pytest.raises(ValueError):
        P.run_project(q, DATA['macro'])
