"""Live data for one country, pulled straight from the providers' APIs when you pick it in the dashboard.

    python -m sovrisk.serve            # then open http://localhost:8080 and use the Live country data tab
    python -m sovrisk.live ARG         # the same pull from the command line, printed as JSON

country_profile() calls each feed on its own, so one blocked or failing feed is reported and the others still
come back:

    imf      IMF World Economic Outlook (api.imf.org, SDMX): debt, deficit, growth, inflation, current account, GDP
    wb       World Bank (api.worldbank.org): reserves, REER, private credit, short-term debt, GDP, US$ debt share
    bis      BIS credit-to-GDP gap (stats.bis.org); needs the country's ISO2 code
    market   Yahoo Finance via yfinance: US 10-year yield, Brent, copper and, if a currency is given, its US$ rate
    ews      the RPF-05 early-warning rating computed from the imf, wb and bis series above (rulebook weights)

Nothing is filled in or made up: a series the provider does not return is absent, and a feed that fails says why.
A pull is cached under outputs/live/<ISO3>.json (outputs/ is not committed; Yahoo data must not be redistributed).
NOT YET RUN against live responses: these hosts are blocked in the build environment. Check the first pull by eye.
"""
import argparse
import json
import time
from pathlib import Path

from .config import ROOT

IMF_WEO = {  # series id: (WEO code, label, unit)
    'debt_gdp': ('GGXWDG_NGDP', 'General government gross debt', '% of GDP'),
    'balance_gdp': ('GGXCNL_NGDP', 'General government net lending / borrowing', '% of GDP'),
    'growth': ('NGDP_RPCH', 'Real GDP growth', '%'),
    'inflation': ('PCPIPCH', 'Inflation, average consumer prices', '%'),
    'ca_gdp': ('BCA_NGDPD', 'Current account balance', '% of GDP'),
    'gdp_usd_bn': ('NGDPD', 'Nominal GDP', 'US$ billion'),
}
WB_SERIES = {
    'reserves_months': ('FI.RES.TOTL.MO', 'Total reserves in months of imports', 'months'),
    'reer': ('PX.REX.REER', 'Real effective exchange rate index', '2010 = 100'),
    'credit_gdp': ('FS.AST.PRVT.GD.ZS', 'Domestic credit to private sector', '% of GDP'),
    'st_debt_pct_reserves': ('DT.DOD.DSTC.IR.ZS', 'Short-term external debt', '% of reserves'),
    'gdp_usd': ('NY.GDP.MKTP.CD', 'GDP', 'current US$'),
    'usd_debt_share': ('DT.CUR.USDL.ZS', 'US dollar share of public and publicly guaranteed debt', '%'),
}
MARKET = {'ust_10y': 'US 10-year Treasury yield', 'brent': 'Brent crude oil', 'copper': 'Copper'}
FEEDS = ('imf', 'wb', 'bis', 'market', 'ews')


def _series(label, unit, source, points):
    return {'label': label, 'unit': unit, 'source': source, 'points': sorted([p, v] for p, v in points)}


def _run(fn):
    """Run one feed: {'status': 'ok', 'series': {...}} or {'status': 'error', 'error': ...}; never raises."""
    t = time.time()
    try:
        out = {'status': 'ok', **fn()}
    except Exception as e:  # a blocked host, an HTTP error, a missing package or an unexpected reply
        out = {'status': 'error', 'error': f'{type(e).__name__}: {e}', 'series': {}}
    out['seconds'] = round(time.time() - t, 1)
    return out


def imf_feed(iso3, y0, y1, imf=None):
    from . import imf as imfmod
    series, missing = {}, []
    for sid, (code, label, unit) in IMF_WEO.items():
        pts = [(y, v) for c, y, v in imfmod.weo_series(code, (iso3,), y0, y1, imf=imf) if c == iso3]
        if pts:
            series[sid] = _series(label, unit, f'IMF WEO {code}', pts)
        else:
            missing.append(code)
    return {'series': series, 'missing': missing}


def wb_feed(iso3, y0, y1):
    from .spillover_data import fetch_wb
    series, missing = {}, []
    for sid, (code, label, unit) in WB_SERIES.items():
        pts = [(y, v) for (c, y), v in fetch_wb(iso3, code, y0, y1).items() if c == iso3]
        if pts:
            series[sid] = _series(label, unit, f'World Bank {code}', pts)
        else:
            missing.append(code)
    return {'series': series, 'missing': missing}


def bis_feed(iso2, y0, y1):
    if not iso2:
        raise ValueError('no ISO2 code for this country, so the BIS cannot be asked (the BIS keys countries by ISO2)')
    from .connectors import bis_credit_gap
    pts = [(y, v) for _, y, v in bis_credit_gap(iso2, y0, y1)]
    return {'series': {'credit_gap': _series('Credit-to-GDP gap', 'pp', 'BIS WS_CREDIT_GAP', pts)} if pts else {},
            'missing': [] if pts else ['WS_CREDIT_GAP']}


def market_feed(y0, y1, currency=None, yf=None):
    from . import market
    want = {k: market.SERIES[k] for k in MARKET}
    if currency:
        want.update(market.fx_series([currency.upper()]))
    rows = market.fetch(want, f'{y0}-01-01', f'{y1}-12-31', yf=yf)
    series = {}
    for r in rows:
        label = MARKET.get(r['series']) or f"Exchange rate, {r['series'][3:]} per US dollar"
        s = series.setdefault(r['series'], _series(label, r['unit'], f"Yahoo Finance {r['ticker']}", []))
        s['points'].append([r['date'], float(r['value'])])
    for s in series.values():
        s['points'].sort()
    return {'series': series, 'missing': []}


def ews_feed(iso3, feeds):
    """The early-warning rating from whatever the imf, wb and bis feeds returned (rulebook weights)."""
    from .ews import ews_table
    cols = {'ca_gdp': 'imf', 'inflation': 'imf', 'reserves_months': 'wb', 'reer': 'wb', 'credit_gdp': 'wb',
            'st_debt_pct_reserves': 'wb', 'credit_gap': 'bis'}
    by = {}
    for col, feed in cols.items():
        for y, v in feeds.get(feed, {}).get('series', {}).get(col, {}).get('points', []):
            by.setdefault(int(y), {})[col] = v
    if not by:
        raise ValueError('no early-warning series came back from the IMF, World Bank or BIS feeds')
    rows = []
    for y, d in sorted(by.items()):
        st = d.pop('st_debt_pct_reserves', None)
        rows.append({'country': iso3, 'year': y, **d, 'reserves_std': 10000 / st if st else None})
    t = ews_table(rows)
    return {'series': {}, 'rating': t['countries'][iso3], 'weighting': t['weighting'], 'model': t['model']}


def country_codes(root=ROOT):
    """{ISO3: {'iso2', 'name'}} from data/country_codes.csv when filled, else from the World Bank country list."""
    import csv
    path = Path(root) / 'data' / 'country_codes.csv'
    rows = list(csv.DictReader(open(path))) if path.exists() else []
    if not rows:
        from .spillover_data import fetch_wb_countries
        rows = [c for c in fetch_wb_countries() if not c['aggregate']]
    return {r['iso3']: {'iso2': r.get('iso2') or '', 'name': r.get('name') or r['iso3']} for r in rows if r.get('iso3')}


def country_profile(iso3, y0=2000, y1=None, currency=None, iso2=None, feeds=FEEDS, imf=None, yf=None):
    """Pull every feed for one country. Returns {'country', 'years', 'pulled', 'feeds': {name: result}}."""
    iso3 = iso3.upper()
    y1 = y1 or time.gmtime().tm_year
    out = {}
    if 'imf' in feeds:
        out['imf'] = _run(lambda: imf_feed(iso3, y0, y1, imf))
    if 'wb' in feeds:
        out['wb'] = _run(lambda: wb_feed(iso3, y0, y1))
    if 'bis' in feeds:
        out['bis'] = _run(lambda: bis_feed(iso2, y0, y1))
    if 'market' in feeds:
        out['market'] = _run(lambda: market_feed(max(y0, y1 - 10), y1, currency, yf))
    if 'ews' in feeds:
        out['ews'] = _run(lambda: ews_feed(iso3, out))
    return {'country': iso3, 'years': [y0, y1], 'currency': currency, 'pulled': time.strftime('%Y-%m-%d %H:%M:%S'),
            'feeds': out}


def save(profile, root=ROOT):
    path = Path(root) / 'outputs' / 'live' / f"{profile['country']}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(profile, default=str))
    return path


def main(argv=None):
    ap = argparse.ArgumentParser(description='Pull live data for one country from the IMF, World Bank, BIS and Yahoo.')
    ap.add_argument('country', help='ISO3 code, e.g. ARG')
    ap.add_argument('--years', default='2000-', help='e.g. 2005-2026 (default 2000 to this year)')
    ap.add_argument('--fx', default=None, help='ISO 4217 currency for the exchange rate, e.g. ARS')
    ap.add_argument('--root', default=None)
    a = ap.parse_args(argv)
    root = Path(a.root) if a.root else ROOT
    y0, _, y1 = a.years.partition('-')
    try:
        iso2 = country_codes(root).get(a.country.upper(), {}).get('iso2')
    except Exception:
        iso2 = None
    p = country_profile(a.country, int(y0), int(y1) if y1 else None, a.fx, iso2)
    print(json.dumps({k: (v if k != 'feeds' else {f: {'status': r['status'], 'error': r.get('error'),
                                                       'series': sorted(r['series'])} for f, r in v.items()})
                      for k, v in p.items()}, indent=2, default=str))
    print('saved', save(p, root))


if __name__ == '__main__':
    main()
