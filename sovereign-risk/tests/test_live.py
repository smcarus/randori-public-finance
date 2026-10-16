"""Live country pull (sovrisk.live), the local server (sovrisk.serve) and the early-warning panel builder. Every provider is replaced by a stand-in
returning hand-made numbers for a hypothetical country AAA; no network. None of these numbers is real data."""
import json
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

import pytest

from sovrisk import connectors, imf, live, market, serve, spillover_data


@pytest.fixture
def feeds(monkeypatch):
    years = range(2005, 2025)
    monkeypatch.setattr(imf, 'weo_series', lambda code, countries, y0, y1, imf=None:
                        [(countries[0], y, {'BCA_NGDPD': -6.0, 'PCPIPCH': 4.0}.get(code, 50.0)) for y in years])
    monkeypatch.setattr(spillover_data, 'fetch_wb', lambda iso3, code, y0, y1:
                        {(iso3, y): {'FI.RES.TOTL.MO': 2.5, 'DT.DOD.DSTC.IR.ZS': 50.0}.get(code, 100.0 + y - 2005) for y in years})
    monkeypatch.setattr(connectors, 'bis_credit_gap', lambda iso2, y0, y1: [(iso2, y, 1.0) for y in years])
    monkeypatch.setattr(market, 'fetch', lambda series, start, end, yf=None:
                        [{'series': k, 'ticker': t, 'date': '2024-01-01', 'value': 1.0, 'unit': u, 'source': 'x'}
                         for k, (t, u) in series.items()])


def test_profile_pulls_every_feed_and_rates(feeds):
    p = live.country_profile('aaa', 2005, 2024, currency='zzz', iso2='AA')
    assert p['country'] == 'AAA'
    assert {k: f['status'] for k, f in p['feeds'].items()} == dict.fromkeys(live.FEEDS, 'ok')
    assert set(p['feeds']['imf']['series']) == set(live.IMF_WEO)
    assert set(p['feeds']['wb']['series']) == set(live.WB_SERIES)
    assert 'fx_ZZZ' in p['feeds']['market']['series']
    r = p['feeds']['ews']['rating']
    assert r['year'] == 2024
    assert r['indicators']['reserves_months']['rating'] == 'red'     # 2.5 months < 3
    assert r['indicators']['ca_gdp']['rating'] == 'red'              # -6 < -5
    assert r['indicators']['reserves_std']['value'] == pytest.approx(200.0)   # 10000 / 50
    assert r['indicators']['inflation']['rating'] == 'green'


def test_one_failing_feed_does_not_stop_the_others(feeds, monkeypatch):
    def blocked(*a, **k):
        raise OSError('403 host not allowed')
    monkeypatch.setattr(spillover_data, 'fetch_wb', blocked)
    p = live.country_profile('AAA', 2005, 2024, iso2=None)
    f = p['feeds']
    assert f['wb']['status'] == 'error' and '403' in f['wb']['error'] and f['wb']['series'] == {}
    assert f['bis']['status'] == 'error' and 'ISO2' in f['bis']['error']
    assert f['imf']['status'] == 'ok' and f['market']['status'] == 'ok'
    assert f['ews']['status'] == 'ok'                                 # rated from the IMF series alone
    assert f['ews']['rating']['indicators']['reserves_months']['rating'] is None


def test_save_writes_under_outputs(tmp_path, feeds):
    path = live.save(live.country_profile('AAA', 2005, 2024, iso2='AA', feeds=('imf',)), tmp_path)
    assert path == tmp_path / 'outputs' / 'live' / 'AAA.json'
    assert json.loads(path.read_text())['feeds']['imf']['status'] == 'ok'


@pytest.fixture
def server(tmp_path, feeds):
    app = serve.App(tmp_path, page='<html>dashboard</html>')
    app._codes = {'AAA': {'iso2': 'AA', 'name': 'Country A'}}
    srv = ThreadingHTTPServer(('127.0.0.1', 0), serve.handler(app))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f'http://127.0.0.1:{srv.server_address[1]}', tmp_path
    srv.shutdown()


def _get(url):
    try:
        with urllib.request.urlopen(url, timeout=10) as r:
            return r.status, r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


def test_server_routes(server):
    base, root = server
    assert _get(base + '/') == (200, '<html>dashboard</html>')
    code, body = _get(base + '/api/countries')
    assert code == 200 and json.loads(body) == [{'iso3': 'AAA', 'iso2': 'AA', 'name': 'Country A'}]
    code, body = _get(base + '/api/country/aaa?y0=2005&y1=2024&fx=zzz')
    p = json.loads(body)
    assert code == 200 and p['name'] == 'Country A' and p['feeds']['bis']['status'] == 'ok'
    assert (root / 'outputs' / 'live' / 'AAA.json').exists()
    assert _get(base + '/api/country/AAA?fx=12x')[0] == 400
    assert _get(base + '/api/nothing')[0] == 404


def test_server_listens_on_localhost_only():
    import inspect
    assert "('127.0.0.1', a.port)" in inspect.getsource(serve.main)


def test_ews_panel_skips_countries_the_bis_does_not_cover(monkeypatch, tmp_path):
    monkeypatch.setattr(connectors, 'imf_series', lambda ind, countries=(): [(c, 2024, 1.0) for c in countries])
    monkeypatch.setattr(connectors, 'wb_series', lambda ind, y0, y1: [('AAA', 2024, 50.0), ('BBB', 2024, 50.0)])

    def gap(iso2, y0, y1):
        if iso2 == 'BB':
            raise connectors.EWSFetchError('404: no BIS series')
        return [(iso2, 2024, 3.0)]
    monkeypatch.setattr(connectors, 'bis_credit_gap', gap)
    rows = connectors.build_ews_panel(tmp_path / 'p.csv', {'AAA': 'AA', 'BBB': 'BB'}, ['AAA', 'BBB'], 2024, 2024)
    assert {r['country']: r.get('credit_gap') for r in rows} == {'AAA': 3.0, 'BBB': None}
