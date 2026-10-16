"""Pull country data from the IMF, World Bank, BIS and UN Comtrade APIs into the data/ files that RPF-05 (early-warning
panel) and RPF-06 (spillover network) read. NOT YET RUN against live responses: check the first output by eye.

    python scripts/fetch_country_data.py ews         --countries ARG,ZMB,SLV
    python scripts/fetch_country_data.py trade       --countries ARG,ZMB,SLV --partners USA,CHN --years 2015-2024
    python scripts/fetch_country_data.py banks       --countries ARG,ZMB,SLV --partners USA,GBR,ESP --years 2015-2024
    python scripts/fetch_country_data.py commodities --countries ARG,ZMB,SLV --years 2024
    python scripts/fetch_country_data.py rates       --countries ARG,ZMB,SLV --years 2015-2024
    python scripts/fetch_country_data.py remittances --countries ARG,ZMB,SLV --matrix path/to/matrix.csv --years 2021
    python scripts/fetch_country_data.py imf-describe --flow WEO     # check an IMF dataflow's dimensions and codes
    python scripts/fetch_country_data.py codes                       # fill data/country_codes.csv from the World Bank
    python scripts/fetch_country_data.py market --years 2015-2026 --fx ARS,ZMW   # Yahoo Finance prices (private file)

IMF data (ews, trade) comes through the IMF's SDMX API with the sdmx1 client, sdmx.Client('IMF_DATA') (see
sovrisk/imf.py; pip install sdmx1). banks, commodities and remittances need data/country_codes.csv (iso3, iso2, m49,
name), because the BIS keys countries by ISO2, Comtrade by M49 number and the remittance matrix by name; ews uses
its iso2 column for the BIS credit gap if it is filled. The codes command fills iso3, iso2 and name for every
economy from the World Bank country list (api.worldbank.org/v2/country/all); m49 stays as you entered it. The
market command writes data/market_prices.csv from Yahoo Finance (yfinance), which is kept out of the public repo. Fill it for each country you
use, partners included. A UN Comtrade subscription key, if you have one, is read from the COMTRADE_KEY environment
variable. Nothing is filled with made-up values: a failed download stops with an error and writes nothing.
"""
import argparse
import csv
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sovrisk import connectors as cn            # noqa: E402
from sovrisk import spillover_data as sd        # noqa: E402

COMMODITIES = ('oil', 'metals', 'copper', 'food')


def load_codes(path):
    if not Path(path).exists():
        sys.exit(f'{path} not found: create it with columns iso3, iso2, m49, name (see the README)')
    rows = list(csv.DictReader(open(path, newline='', encoding='utf-8-sig')))
    if not rows:
        sys.exit(f'{path} has no rows: add one per country and partner (see the README)')
    return rows


def years(text):
    a, _, b = text.partition('-')
    return int(a), int(b or a)


def gdp_usd(countries, y0, y1):
    """{(iso3, year): GDP in US$} from the World Bank (NY.GDP.MKTP.CD)."""
    out = {}
    for c in countries:
        out.update(sd.fetch_wb(c, sd.WB_GDP_USD, y0, y1))
    return out


def by(codes, field):
    return {r['iso3']: r[field] for r in codes if r.get(field)}


def need(mapping, iso3s, field):
    missing = [c for c in iso3s if c not in mapping]
    if missing:
        sys.exit(f'data/country_codes.csv has no {field} for {", ".join(missing)}')


def trade(a, codes):
    y0, y1 = years(a.years)
    flows = [f for c in a.countries for f in sd.fetch_imf_exports(c, a.partners, y0, y1)]
    return sd.to_pct_gdp(flows, gdp_usd(a.countries, y0, y1), 'IMF IMTS exports'), 'spill_trade.csv'


def banks(a, codes):
    iso2, y0, y1 = by(codes, 'iso2'), *years(a.years)
    need(iso2, a.countries + a.partners, 'iso2')
    to3 = {v: k for k, v in iso2.items()}
    flows = [(to3.get(b, b), to3.get(l, l), y, usd)
             for c in a.countries for p in a.partners
             for b, l, y, usd in sd.fetch_bis_claims(iso2[p], iso2[c], y0, y1)]
    return sd.to_pct_gdp(flows, gdp_usd(a.countries, y0, y1), 'BIS CBS foreign claims'), 'spill_banks.csv'


def commodities(a, codes):
    m49, (y0, y1) = by(codes, 'm49'), years(a.years)
    need(m49, a.countries, 'm49')
    key = os.environ.get('COMTRADE_KEY')
    flows = [(c, k, y, usd)
             for c in a.countries for year in range(y0, y1 + 1) for com in COMMODITIES
             for _, k, y, usd in sd.fetch_comtrade(m49[c], year, com, key=key)]
    return sd.to_pct_gdp(flows, gdp_usd(a.countries, y0, y1), 'UN Comtrade net exports'), 'spill_commodities.csv'


def rates(a, codes):
    y0, y1 = years(a.years)
    rows = [{'country': c, 'partner': 'usd_debt_share', 'value_pct_gdp': v, 'year': y,
             'source': f'World Bank IDS {sd.WB_USD_DEBT_SHARE}'}
            for c in a.countries for (_, y), v in sd.fetch_wb(c, sd.WB_USD_DEBT_SHARE, y0, y1).items()]
    print('Add a gfn row per country by hand (gross financing need, % of GDP, from its IMF DSA or sovrisk.srdsf); '
          'the rates channel skips a country without one.')
    return rows, 'spill_rates.csv'


def remittances(a, codes):
    if not a.matrix:
        sys.exit('--matrix is required: download the bilateral remittance matrix from ' + sd.WB_REMITTANCE_MATRIX)
    y0, _ = years(a.years)
    to3 = {r['name']: r['iso3'] for r in codes if r.get('name')}
    flows, unknown = [], set()
    for rec, snd, y, usd in sd.parse_remittance_matrix(a.matrix, y0):
        if rec == snd:
            continue
        if rec in to3 and snd in to3 and to3[rec] in a.countries:
            flows.append((to3[rec], to3[snd], y, usd))
        else:
            unknown.update(n for n in (rec, snd) if n not in to3)
    if unknown:
        print(f'{len(unknown)} names in the matrix are not in country_codes.csv and were skipped')
    return sd.to_pct_gdp(flows, gdp_usd(a.countries, y0, y0), 'World Bank bilateral remittance matrix'), \
        'spill_remittances.csv'


def country_codes(a):
    """Write data/country_codes.csv from the World Bank country list, economies only, keeping any m49 already
    entered. Names are the World Bank's, which the bilateral remittance matrix also uses."""
    path = Path(a.codes)
    old = {r['iso3']: r for r in csv.DictReader(open(path, newline='', encoding='utf-8-sig'))} if path.exists() else {}
    wb = [c for c in sd.fetch_wb_countries() if not c['aggregate']]
    rows = [{'iso3': c['iso3'], 'iso2': c['iso2'], 'm49': old.get(c['iso3'], {}).get('m49', ''), 'name': c['name']}
            for c in sorted(wb, key=lambda c: c['iso3'])]
    rows += [r for k, r in sorted(old.items()) if k not in {c['iso3'] for c in wb}]    # keep hand-added rows
    with open(path, 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=['iso3', 'iso2', 'm49', 'name'], extrasaction='ignore')
        w.writeheader()
        w.writerows(rows)
    print(f'wrote {len(rows)} rows to {path}; m49 is filled for {sum(1 for r in rows if r["m49"])} '
          '(add M49 numbers by hand for the commodities command)')


def market_prices(a):
    from sovrisk import market
    if not a.years:
        sys.exit('--years is required, e.g. --years 2015-2026')
    y0, y1 = years(a.years)
    series = {**market.SERIES, **market.fx_series([c.strip().upper() for c in a.fx.split(',') if c.strip()])}
    rows = market.fetch(series, f'{y0}-01-01', f'{y1}-12-31', a.interval)
    print(f'wrote {len(rows)} rows to {market.write(rows)} (private: not for the public repo)')


def ews(a, codes):
    iso2 = by(codes, 'iso2') if codes else {}
    y0, y1 = years(a.years) if a.years else (1980, 2026)
    rows = cn.build_ews_panel(countries=a.countries, iso2_by_iso3={c: iso2[c] for c in a.countries if c in iso2},
                              y0=y0, y1=y1)
    print(f'wrote {len(rows)} rows to data/ews_panel.csv')


def main(argv=None):
    ap = argparse.ArgumentParser(description='Pull country data into data/ for RPF-05 and RPF-06.')
    ap.add_argument('what', choices=['ews', 'trade', 'banks', 'commodities', 'rates', 'remittances', 'imf-describe',
                                       'codes', 'market'])
    ap.add_argument('--countries', default='', help='ISO3 codes, comma-separated')
    ap.add_argument('--partners', default='', help='ISO3 codes of partner economies (trade, banks)')
    ap.add_argument('--years', default='', help='a year or a range, e.g. 2015-2024')
    ap.add_argument('--matrix', help='remittance matrix saved as CSV (remittances)')
    ap.add_argument('--codes', default=str(ROOT / 'data' / 'country_codes.csv'))
    ap.add_argument('--flow', default='WEO', help='IMF dataflow id (imf-describe)')
    ap.add_argument('--fx', default='', help='currency codes for exchange rates per US$, e.g. ARS,ZMW (market)')
    ap.add_argument('--interval', default='1mo', help='price interval: 1d, 1wk or 1mo (market)')
    a = ap.parse_args(argv)
    if a.what == 'imf-describe':
        from sovrisk import imf
        for i, (dim, codes) in enumerate(imf.describe(a.flow)):
            print(f"{i + 1}. {dim:24s} {', '.join(codes)}")
        return
    if a.what == 'codes':
        return country_codes(a)
    if a.what == 'market':
        return market_prices(a)
    if not a.countries:
        ap.error('--countries is required')
    a.countries = [c.strip().upper() for c in a.countries.split(',') if c.strip()]
    a.partners = [c.strip().upper() for c in a.partners.split(',') if c.strip()]
    if a.what in ('trade', 'banks') and not a.partners:
        ap.error('--partners is required for trade and banks')
    if a.what != 'ews' and not a.years:
        ap.error('--years is required')
    if a.what == 'ews':
        codes = list(csv.DictReader(open(a.codes, newline='', encoding='utf-8-sig'))) if Path(a.codes).exists() else []
        if not by(codes, 'iso2'):
            print('no iso2 codes in country_codes.csv: skipping the BIS credit gap; ews.py will compute gaps from credit_gdp')
        return ews(a, codes)
    codes = [] if a.what in ('rates', 'trade') else load_codes(a.codes)
    rows, name = {'trade': trade, 'banks': banks, 'commodities': commodities, 'rates': rates,
                  'remittances': remittances}[a.what](a, codes)
    print(f'wrote {len(rows)} rows to {sd.write(rows, name)}')


if __name__ == '__main__':
    main()
