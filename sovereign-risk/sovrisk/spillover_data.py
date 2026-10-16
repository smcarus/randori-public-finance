"""Data for the RPF-06 spillover network: fetch and parse the exposure sources into data/spill_*.csv. NOT YET RUN: this
environment's network policy blocks these hosts, so the functions follow the providers' documented URL formats and
have never seen a live response. Check the outputs, and the URL formats, on first run.

Every file written has the long format the model reads: country, partner, value_pct_gdp, year, source.

    trade        IMF International Trade in Goods (IMTS, formerly DOTS), exports by partner, US$ -> % GDP
    commodities  UN Comtrade, exports minus imports of oil, metals, copper and food, US$ -> % GDP
    banks        BIS consolidated banking statistics, foreign claims by bank nationality, US$ -> % GDP
    rates        World Bank IDS, US dollar share of public and publicly guaranteed external debt (%), and gross
                 financing need (% GDP) from the country's IMF/World Bank DSA, which has no API and is entered by hand
    remittances  World Bank bilateral remittance matrix (a spreadsheet download, no API), US$ -> % GDP

The model keys countries by ISO3 (USA, CHN), as the IMF SDMX portal does. BIS uses ISO2 and Comtrade M49 numbers,
so map codes to ISO3 before writing: scripts/fetch_country_data.py does this from data/country_codes.csv, which
ships empty and must be filled. GDP in US$ for the conversions comes from the World Bank (NY.GDP.MKTP.CD).
Licences: IMF, BIS and World Bank data are reusable with attribution; UN Comtrade has its own terms, check them before redistributing.
Nothing here makes up data: a failed download raises an error saying what to fetch and where to put it.
"""
import csv
import json
import urllib.error
import urllib.request
from pathlib import Path

from .config import ROOT

# IMF trade comes through the IMF's SDMX API with the sdmx1 client (sovrisk/imf.py, IMTS dataflow).
# BIS SDMX REST API. CBS key dimensions: FREQ.L_MEASURE.L_REP_CTY.CBS_BANK_TYPE.CBS_BASIS.L_POSITION.L_INSTR.
# REM_MATURITY.CURR_TYPE_BOOK.L_CP_SECTOR.L_CP_COUNTRY. The default key (foreign claims, ultimate risk basis, all
# sectors, all maturities) is a draft, to verify against the BIS key builder.
BIS = 'https://stats.bis.org/api/v1/data/WS_CBS_PUB/{key}/all?startPeriod={y0}&endPeriod={y1}&format=csv'
BIS_KEY = 'Q.S.{lender}.4R.F.C.A.A.TO1.A.{borrower}'
# UN Comtrade. The public preview endpoint needs no key but caps rows; the data endpoint needs a subscription key.
COMTRADE = ('https://comtradeapi.un.org/public/v1/preview/C/A/HS?reporterCode={reporter}&period={year}'
            '&partnerCode=0&cmdCode={cmd}&flowCode=X,M')
COMTRADE_KEYED = ('https://comtradeapi.un.org/data/v1/get/C/A/HS?reporterCode={reporter}&period={year}'
                  '&partnerCode=0&cmdCode={cmd}&flowCode=X,M&subscription-key={key}')
# HS codes per commodity group. Draft mapping, to verify.
HS = {'oil': ['2709', '2710', '2711'],
      'metals': ['26', '72', '74', '75', '76', '78', '79', '80', '81'],
      'copper': ['2603', '74'],
      'food': [f'{i:02d}' for i in range(1, 25)]}
WB = 'https://api.worldbank.org/v2/country/{iso3}/indicator/{ind}?format=json&per_page=20000&date={y0}:{y1}'
WB_COUNTRIES = 'https://api.worldbank.org/v2/country/all?format=json&per_page=400'   # the country list
WB_GDP_USD = 'NY.GDP.MKTP.CD'
WB_USD_DEBT_SHARE = 'DT.CUR.USDL.ZS'   # currency composition of PPG debt, U.S. dollars (%), IDS
WB_REMITTANCE_MATRIX = 'https://www.worldbank.org/en/topic/migration/brief/remittances-data'   # page with the download

HOSTS = {'imf': 'api.imf.org', 'bis': 'stats.bis.org', 'comtrade': 'comtradeapi.un.org',
         'wb': 'api.worldbank.org'}
FIELDS = ['country', 'partner', 'value_pct_gdp', 'year', 'source']


class DataUnavailable(RuntimeError):
    pass


def _get(url, what):
    try:
        with urllib.request.urlopen(url, timeout=60) as r:
            return r.read().decode()
    except (urllib.error.URLError, OSError) as e:
        raise DataUnavailable(f'Could not fetch {what} from {url} ({e}). The network may be blocking the host. '
                              'Download it by hand and use the matching parse_* function; no data was written.') from e


# --- IMF trade ---------------------------------------------------------------------------------------------------

def fetch_imf_exports(reporter, partners, y0, y1):
    """Annual goods exports (US$) from reporter to each partner, as [(reporter, partner, year, US$)]. The IMF SDMX
    portal keys countries by ISO3, so reporter and partners are ISO3 codes."""
    from . import imf
    try:
        return imf.imts_exports(reporter, partners, y0, y1)
    except imf.IMFUnavailable as e:
        raise DataUnavailable(f'IMF trade (IMTS): {e}') from e


# --- BIS banks ---------------------------------------------------------------------------------------------------

def fetch_bis_claims(lender, borrower, y0, y1, key=BIS_KEY):
    """Foreign claims of banks headquartered in lender (ISO2, or 5A for all) on borrower (ISO2)."""
    return parse_bis_csv(_get(BIS.format(key=key.format(lender=lender, borrower=borrower), y0=y0, y1=y1), 'BIS CBS'))


def parse_bis_csv(text):
    """BIS SDMX csv -> [(borrower, lender, year, US$)], keeping the last quarter of each year. BIS CBS amounts are
    in US$ millions."""
    by = {}
    for r in csv.DictReader(text.splitlines()):
        if r.get('OBS_VALUE') in (None, '', 'NaN'):
            continue
        k = (r['L_CP_COUNTRY'], r['L_REP_CTY'], int(r['TIME_PERIOD'][:4]))
        if k not in by or r['TIME_PERIOD'] > by[k][0]:
            by[k] = (r['TIME_PERIOD'], float(r['OBS_VALUE']) * 1e6)
    return [(b, l, y, v) for (b, l, y), (_, v) in by.items()]


# --- UN Comtrade commodities -------------------------------------------------------------------------------------

def fetch_comtrade(reporter, year, commodity, key=None):
    """Exports and imports (US$) of one commodity group. reporter is the M49 numeric code."""
    cmd = ','.join(HS[commodity])
    url = (COMTRADE_KEYED if key else COMTRADE).format(reporter=reporter, year=year, cmd=cmd, key=key)
    return parse_comtrade(json.loads(_get(url, 'UN Comtrade')), commodity)


def parse_comtrade(d, commodity):
    """Comtrade JSON -> [(reporterISO, commodity, year, net exports US$)]. Codes that nest (2603 inside 26) would be
    double counted, so HS lists should not overlap."""
    net = {}
    for r in d.get('data', []):
        sign = {'X': 1, 'M': -1}.get(r.get('flowCode'))
        if sign is None or r.get('primaryValue') is None:
            continue
        k = (r.get('reporterISO') or str(r['reporterCode']), int(r['period']))
        net[k] = net.get(k, 0.0) + sign * float(r['primaryValue'])
    return [(c, commodity, y, v) for (c, y), v in net.items()]


# --- World Bank --------------------------------------------------------------------------------------------------

def fetch_wb(iso3, indicator, y0, y1):
    """One World Bank indicator for one country (iso3, or 'all'), reading every page of the response."""
    url = WB.format(iso3=iso3, ind=indicator, y0=y0, y1=y1)
    out, page, pages = {}, 1, 1
    while page <= pages:
        d = json.loads(_get(f'{url}&page={page}', f'World Bank {indicator}'))
        out.update(parse_wb(d))
        pages = int((d[0] or {}).get('pages') or 1)
        page += 1
    return out


def fetch_wb_countries():
    """The World Bank's country list (api.worldbank.org/v2/country/all), every page: one dict per economy or
    aggregate with iso3, iso2, name, region, income and aggregate (True for regional and income groups)."""
    out, page, pages = [], 1, 1
    while page <= pages:
        d = json.loads(_get(f'{WB_COUNTRIES}&page={page}', 'World Bank country list'))
        out += parse_wb_countries(d)
        pages = int((d[0] or {}).get('pages') or 1)
        page += 1
    return out


def parse_wb_countries(d):
    """World Bank country-list JSON -> [{iso3, iso2, name, region, income, aggregate}]. Aggregates (World, Euro
    area, income groups) have region id 'NA'."""
    if d and isinstance(d[0], dict) and 'message' in d[0]:
        raise DataUnavailable(f"World Bank API error: {d[0]['message']}")
    return [{'iso3': c['id'], 'iso2': c['iso2Code'], 'name': c['name'].strip(), 'region': c['region']['value'].strip(),
             'income': c['incomeLevel']['value'].strip(), 'aggregate': c['region']['id'] == 'NA'}
            for c in (d[1] if len(d) > 1 and d[1] else [])]


def parse_wb(d):
    """World Bank API JSON ([page info, rows]) -> {(iso3, year): value}. An error reply (a message and no rows,
    e.g. for an unknown indicator) raises DataUnavailable rather than reading as no data."""
    if d and isinstance(d[0], dict) and 'message' in d[0]:
        raise DataUnavailable(f"World Bank API error: {d[0]['message']}")
    if len(d) < 2 or d[1] is None:
        return {}
    return {(r['countryiso3code'], int(r['date'])): float(r['value']) for r in d[1]
            if r['value'] is not None and r['countryiso3code']}


def parse_remittance_matrix(path, year, receivers_in_columns=True):
    """World Bank bilateral remittance matrix saved as CSV: first column the country names, first row the country
    names, cells US$ millions. In the published file, sending countries run down the rows and receiving countries
    across the columns; this is to verify on the file you download (set receivers_in_columns=False if flipped).
    Returns [(receiver, sender, year, US$)] with country NAMES: map them to ISO3 before writing."""
    rows = list(csv.reader(open(path, newline='', encoding='utf-8-sig')))
    head, out = rows[0], []
    for r in rows[1:]:
        for j, cell in enumerate(r[1:], 1):
            try:
                v = float(cell.replace(',', ''))
            except ValueError:
                continue
            rec, snd = (head[j], r[0]) if receivers_in_columns else (r[0], head[j])
            out.append((rec, snd, year, v * 1e6))
    return out


# --- to % of GDP and to the model's files ------------------------------------------------------------------------

def to_pct_gdp(flows, gdp_usd, source):
    """[(country, partner, year, US$)] + {(country, year): GDP US$} -> rows in the model's long format. Rows whose
    GDP is missing are dropped, not guessed."""
    out = []
    for c, p, y, usd in flows:
        g = gdp_usd.get((c, y))
        if g:
            out.append({'country': c, 'partner': p, 'value_pct_gdp': 100 * usd / g, 'year': y, 'source': source})
    return out


def write(rows, name, root=ROOT):
    """Write rows to data/<name>, e.g. spill_trade.csv. Refuses an empty list so a failed fetch leaves no file."""
    if not rows:
        raise DataUnavailable(f'no rows for {name}; nothing written')
    path = Path(root) / 'data' / name
    with open(path, 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows({k: r[k] for k in FIELDS} for r in rows)
    return path
