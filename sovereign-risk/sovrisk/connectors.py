"""Data connectors for the default-history panel. NOT YET RUN: this environment's network policy blocks these
hosts (www.imf.org, api.worldbank.org, www.bankofcanada.ca). Check the outputs on first run.

Each function returns rows of (iso3, year, value). Licences: IMF and World Bank data are reusable with attribution;
check the Bank of Canada database terms before redistributing.
"""
import json
import urllib.request

IMF = 'https://www.imf.org/external/datamapper/api/v1/{ind}'
WB = 'https://api.worldbank.org/v2/country/all/indicator/{ind}?format=json&per_page=20000&date={y0}:{y1}'

IMF_SERIES = {'debt_gdp': 'GGXWDG_NGDP', 'growth': 'NGDP_RPCH', 'inflation': 'PCPIPCH', 'ca_gdp': 'BCA_NGDPD'}
WB_SERIES = {'reserves_months': 'FI.RES.TOTL.MO'}


def _get(url):
    with urllib.request.urlopen(url, timeout=60) as r:
        return json.loads(r.read().decode())


def imf_series(ind):
    d = _get(IMF.format(ind=ind))['values'][ind]
    return [(iso, int(y), v) for iso, ys in d.items() for y, v in ys.items() if v is not None]


def wb_series(ind, y0=1980, y1=2026):
    d = _get(WB.format(ind=ind, y0=y0, y1=y1))
    return [(r['countryiso3code'], int(r['date']), r['value']) for r in d[1] if r['value'] is not None and r['countryiso3code']]


def build_panel(default_events, y0=1985, y1=2025):
    """default_events: {iso3: [start years of new defaults or restructurings]}, e.g. from the BoC-BoE database.
    Features are lagged one year (known at the start of the forecast year). Years already in default are dropped."""
    import math
    raw = {}
    for name, ind in IMF_SERIES.items():
        for iso, y, v in imf_series(ind):
            raw.setdefault((iso, y), {})[name] = v
    for name, ind in WB_SERIES.items():
        for iso, y, v in wb_series(ind):
            raw.setdefault((iso, y), {})[name] = v
    rows = []
    for (iso, y), _ in raw.items():
        if not y0 <= y <= y1:
            continue
        f = raw.get((iso, y - 1), {})
        if not all(k in f for k in ('debt_gdp', 'growth', 'inflation', 'ca_gdp')):
            continue
        ev = default_events.get(iso, [])
        past = 1 if any(y - 10 <= e < y for e in ev) else 0
        rows.append({'iso3': iso, 'year': y, 'debt_gdp': f['debt_gdp'], 'growth': f['growth'],
                     'inflation_log': math.log1p(max(f['inflation'], -50) / 100), 'ca_gdp': f['ca_gdp'],
                     'reserves_months': f.get('reserves_months'), 'past_default_10y': past,
                     'default': 1 if y in ev else 0})
    return rows
