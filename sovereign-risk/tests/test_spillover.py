"""RPF-06 spillover network: hand-worked examples on HAND-MADE inputs (countries A, B, C are not real)."""
import copy
import json

import numpy as np
import pytest

from sovrisk import spillover as S
from sovrisk import spillover_data as SD

RB = S.load_rulebook()


def rb_simple():
    """Round numbers so the hand calculation is easy: trade sensitivity = exports share x 2 x 0.5, damping 0.5."""
    rb = copy.deepcopy(RB)
    rb['channels']['trade'].update(income_elasticity=2.0, value_added_share=0.5)
    rb['second_round']['damping'] = 0.5
    return rb


def row(c, p, v, year=2024):
    return {'country': c, 'partner': p, 'value_pct_gdp': v, 'year': year, 'source': 'hand-made'}


TWO = {'trade': [row('A', 'USA', 10), row('B', 'USA', 5), row('A', 'B', 20), row('B', 'A', 10)]}


def test_rulebook_has_sources_and_scenarios():
    for ch in S.CHANNELS:
        c = RB['channels'][ch]
        for k, v in c.items():
            if isinstance(v, (int, float)):
                assert f'{k}_source' in c, f'{ch}.{k} has no source note'
    assert set(RB['scenarios']) == {'us_recession', 'china_slowdown', 'oil_down_30', 'copper_down_25', 'us_rates_up_200'}


def test_two_country_first_and_second_round():
    # US GDP -2%. First round: A exports 10% of GDP to the US -> 0.10 x -2 x 2 x 0.5 = -0.2; B: 0.05 x -2 = -0.1.
    # dA = 0.5 x [[0, 0.2], [0.1, 0]] = [[0, 0.1], [0.05, 0]].
    # Round 2: A = 0.1 x -0.1 = -0.01; B = 0.05 x -0.2 = -0.01. Round 3: A = 0.1 x -0.01 = -0.001, B = -0.0005.
    r = S.run('us_recession', TWO, rb_simple())
    a, b = r['countries']['A'], r['countries']['B']
    assert a['first']['trade'] == pytest.approx(-0.2) and b['first']['trade'] == pytest.approx(-0.1)
    assert r['rounds'][1]['A'] == pytest.approx(-0.01) and r['rounds'][1]['B'] == pytest.approx(-0.01)
    assert r['rounds'][2]['A'] == pytest.approx(-0.001) and r['rounds'][2]['B'] == pytest.approx(-0.0005)
    # all rounds after the first = ((I - dA)^-1 - I) y1 = [-0.2 - 0.01, -0.01 - 0.1] / 0.995 - y1
    assert a['second']['trade'] == pytest.approx(-0.21 / 0.995 + 0.2, abs=1e-8)
    assert b['second']['trade'] == pytest.approx(-0.11 / 0.995 + 0.1, abs=1e-8)
    da = np.array([[0, 0.1], [0.05, 0]])
    tot = np.linalg.solve(np.eye(2) - da, [-0.2, -0.1])
    assert [a['total'], b['total']] == pytest.approx(list(tot), abs=1e-8)


def test_zero_exposures_give_zero():
    zero = {'trade': [row('A', 'USA', 0), row('A', 'B', 0)], 'commodities': [row('A', 'oil', 0)],
            'banks': [row('A', 'USA', 0)], 'remittances': [row('A', 'USA', 0)],
            'rates': [row('A', 'usd_debt_share', 0), row('A', 'gfn', 0)]}
    for sc in RB['scenarios']:
        r = S.run(sc, zero, RB)
        assert all(x['total'] == 0 for x in r['countries'].values())
        assert S.run(sc, {}, RB)['countries'] == {}


def test_damping_shrinks_each_round():
    ex = {'trade': [row('A', 'USA', 30), row('A', 'B', 40), row('B', 'A', 35), row('B', 'C', 20),
                    row('C', 'A', 25), row('C', 'USA', 15)]}
    r = S.run('us_recession', ex, RB)
    sizes = [max(abs(v) for v in rd.values()) for rd in r['rounds']]
    assert r['n_rounds'] > 3
    assert all(later < earlier for earlier, later in zip(sizes, sizes[1:]))
    weaker = copy.deepcopy(RB)
    weaker['second_round']['damping'] = 0.25
    sec = lambda res: sum(sum(x['second'].values()) for x in res['countries'].values())
    assert abs(sec(S.run('us_recession', ex, weaker))) < abs(sec(r))


def test_explosive_network_is_refused():
    rb = copy.deepcopy(RB)
    rb['second_round']['damping'] = 1.0
    with pytest.raises(ValueError, match='would not shrink'):
        S.run('us_recession', {'trade': [row('A', 'USA', 10), row('A', 'B', 80)]}, rb)


def test_commodity_sign_exporter_loses_importer_gains():
    ex = {'commodities': [row('A', 'oil', 15), row('B', 'oil', -5), row('C', 'copper', 10)]}
    r = S.run('oil_down_30', ex, RB)['countries']
    k = RB['channels']['commodities']['income_pass_through']
    assert r['A']['first']['commodities'] == pytest.approx(0.15 * -30 * k) and r['A']['total'] < 0
    assert r['B']['first']['commodities'] == pytest.approx(0.05 * 30 * k) and r['B']['total'] > 0
    assert 'C' not in r      # copper does not move in the oil scenario


def test_rates_channel_scales_with_usd_debt_share():
    def hit(share):
        ex = {'rates': [row('A', 'usd_debt_share', share), row('A', 'gfn', 15)]}
        return S.run('us_rates_up_200', ex, RB)['countries']['A']['first']['rates']
    r = RB['channels']['rates']
    assert hit(60) == pytest.approx(-2 * r['yield_pass_through'] * 0.6 * 0.15 * r['fiscal_multiplier'])
    assert hit(60) == pytest.approx(2 * hit(30)) and hit(0) == 0 and hit(60) < 0


def test_latest_year_wins():
    ex = {'trade': [row('A', 'USA', 10, 2020), row('A', 'USA', 20, 2023)]}
    assert S.latest(ex['trade']) == {('A', 'USA'): 20.0}


def test_parsers_and_pct_gdp_on_hand_made_responses():
    wb = [{'page': 1}, [{'countryiso3code': 'AAA', 'date': '2023', 'value': 200e9},
                        {'countryiso3code': 'AAA', 'date': '2022', 'value': None}]]
    gdp = SD.parse_wb(wb)
    assert gdp == {('AAA', 2023): 200e9}
    ct = {'data': [{'reporterISO': 'AAA', 'period': 2023, 'flowCode': 'X', 'primaryValue': 30e9},
                   {'reporterISO': 'AAA', 'period': 2023, 'flowCode': 'M', 'primaryValue': 10e9}]}
    flows = SD.parse_comtrade(ct, 'oil')
    rows = SD.to_pct_gdp(flows + [('AAA', 'oil', 2021, 1e9)], gdp, 'hand-made')
    assert rows == [{'country': 'AAA', 'partner': 'oil', 'value_pct_gdp': 10.0, 'year': 2023, 'source': 'hand-made'}]
    with pytest.raises(SD.DataUnavailable):
        SD.write([], 'spill_trade.csv')


def test_world_bank_reads_every_page_and_refuses_an_error_reply(monkeypatch):
    pages = {1: [{'page': 1, 'pages': 2}, [{'countryiso3code': 'AAA', 'date': '2023', 'value': 1.0}]],
             2: [{'page': 2, 'pages': 2}, [{'countryiso3code': 'BBB', 'date': '2023', 'value': 2.0}]]}
    seen = []

    def fake_get(url, what):
        seen.append(url)
        return json.dumps(pages[int(url.rsplit('page=', 1)[1])])
    monkeypatch.setattr(SD, '_get', fake_get)
    assert SD.fetch_wb('all', 'SP.POP.TOTL', 2023, 2023) == {('AAA', 2023): 1.0, ('BBB', 2023): 2.0}
    assert len(seen) == 2 and 'country/all/indicator/SP.POP.TOTL' in seen[0]
    with pytest.raises(SD.DataUnavailable, match='Invalid value'):
        SD.parse_wb([{'message': [{'id': '120', 'key': 'Invalid value', 'value': 'The provided parameter value is not valid'}]}])
