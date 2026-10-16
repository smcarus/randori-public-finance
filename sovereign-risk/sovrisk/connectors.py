"""Data connectors for the default-history panel (default_fit) and the RPF-05 early-warning panel (ews). NOT YET RUN:
the build environment's network policy blocks these hosts (api.imf.org, api.worldbank.org, stats.bis.org). Check
the outputs on first run. IMF series come through the IMF's SDMX API with the sdmx1 client (sovrisk/imf.py).

imf_series and wb_series return rows of (iso3, year, value); bis_credit_gap returns (iso2, year, value);
build_panel and build_ews_panel return dict rows. Default dates (the BoC-BoE database) are passed in, not fetched.
Licences: IMF, World Bank and BIS data are reusable with attribution; check the Bank of Canada database terms
before redistributing.
"""
import urllib.request

WB = 'https://api.worldbank.org/v2/country/all/indicator/{ind}?format=json&per_page=20000&date={y0}:{y1}'

IMF_SERIES = {'debt_gdp': 'GGXWDG_NGDP', 'growth': 'NGDP_RPCH', 'inflation': 'PCPIPCH', 'ca_gdp': 'BCA_NGDPD'}
WB_SERIES = {'reserves_months': 'FI.RES.TOTL.MO'}


def imf_series(ind, countries=()):
    """One IMF World Economic Outlook indicator for every country (or the ISO3 codes given), via sovrisk.imf."""
    from . import imf
    return imf.weo_series(ind, countries)


def wb_economies():
    """ISO3 codes of the economies in the World Bank's country list (api.worldbank.org/v2/country/all), without the
    regional and income aggregates. Fetched once per run."""
    global _ECONOMIES
    if _ECONOMIES is None:
        from .spillover_data import fetch_wb_countries
        _ECONOMIES = {c['iso3'] for c in fetch_wb_countries() if not c['aggregate']}
    return _ECONOMIES


_ECONOMIES = None


def wb_series(ind, y0=1980, y1=2026):
    """One World Bank indicator for every economy (the API's country/all endpoint, every page), with the regional
    and income aggregates dropped using the country list."""
    from .spillover_data import fetch_wb
    keep = wb_economies()
    return [(iso, y, v) for (iso, y), v in sorted(fetch_wb('all', ind, y0, y1).items()) if iso in keep]


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


# ---- RPF-05 early-warning panel (sovrisk/ews.py) -------------------------------------------------------------------
# NOT YET RUN: api.imf.org, api.worldbank.org and stats.bis.org are blocked in the build environment. The URL formats
# follow each provider's documented API; check the first real response. Nothing here invents or fills data: a series
# that cannot be fetched raises EWSFetchError, and a cell with no observation is left blank. The one exception is the
# BIS credit gap in build_ews_panel: a country the BIS does not cover is named and skipped, and its gap stays blank
# (ews.py computes it from credit_gdp).
#   IMF WEO (SDMX)  BCA_NGDPD  current account, % of GDP              -> ca_gdp
#                   PCPIPCH    inflation, average consumer prices, %  -> inflation
#   World Bank WDI  FI.RES.TOTL.MO     total reserves in months of imports             -> reserves_months
#                   PX.REX.REER        real effective exchange rate index (2010 = 100)  -> reer (ews.py derives reer_dev)
#                   FS.AST.PRVT.GD.ZS  domestic credit to private sector, % of GDP     -> credit_gdp (fallback gap)
#   World Bank IDS  DT.DOD.DSTC.IR.ZS  short-term external debt, % of total reserves   -> reserves_std = 10000 / x
#   BIS             WS_CREDIT_GAP, key Q.{ISO2}.P.A.C (quarterly, private non-financial sector, all lenders,
#                   credit-to-GDP gap in pp); the year's Q4 value, else its last quarter    -> credit_gap
# gfn_gdp (gross financing need) is not fetched: take it from the debt sustainability module (sovrisk.srdsf, GFN_GDP).
BIS = 'https://stats.bis.org/api/v1/data/{flow}/{key}/all?detail=dataonly'
EWS_IMF = {'ca_gdp': 'BCA_NGDPD', 'inflation': 'PCPIPCH'}
EWS_WB = {'reserves_months': 'FI.RES.TOTL.MO', 'reer': 'PX.REX.REER', 'credit_gdp': 'FS.AST.PRVT.GD.ZS',
          'st_debt_pct_reserves': 'DT.DOD.DSTC.IR.ZS'}
EWS_COLUMNS = ['country', 'year', 'reserves_months', 'reserves_std', 'ca_gdp', 'reer', 'reer_dev', 'credit_gdp',
               'credit_gap', 'inflation', 'gfn_gdp']


class EWSFetchError(RuntimeError):
    pass


def _ews_fetch(fn, what, *args):
    try:
        return fn(*args)
    except Exception as e:  # network refusal, HTTP error, or an unexpected response shape
        raise EWSFetchError(f'could not fetch {what}: {type(e).__name__}: {e}. If the host is blocked, run where '
                            'api.imf.org, api.worldbank.org and stats.bis.org are reachable; no data was written.') from e


def bis_credit_gap(iso2, y0=1980, y1=2026):
    """BIS credit-to-GDP gap (pp) for one country (BIS uses ISO2 codes): [(iso2, year, gap)], one value per year."""
    import csv
    import io
    url = BIS.format(flow='WS_CREDIT_GAP', key=f'Q.{iso2}.P.A.C')

    def get():
        req = urllib.request.Request(url, headers={'Accept': 'application/vnd.sdmx.data+csv;version=1.0.0'})
        with urllib.request.urlopen(req, timeout=60) as r:
            rows = list(csv.DictReader(io.StringIO(r.read().decode())))
        if rows and not {'TIME_PERIOD', 'OBS_VALUE'} <= set(rows[0]):
            raise ValueError(f'unexpected columns {list(rows[0])[:8]}')
        return rows
    best = {}
    for r in _ews_fetch(get, f'BIS credit gap for {iso2} ({url})'):
        t, v = r['TIME_PERIOD'], r['OBS_VALUE']          # TIME_PERIOD like 2024-Q4
        if not v or v == 'NaN':
            continue
        y, q = int(t[:4]), int(t[-1])
        if y0 <= y <= y1 and q >= best.get(y, (0, None))[0]:
            best[y] = (q, float(v))
    return [(iso2, y, v) for y, (q, v) in sorted(best.items())]


def build_ews_panel(path=None, iso2_by_iso3=None, countries=None, y0=1980, y1=2026):
    """Fetch the early-warning series and write data/ews_panel.csv (or path). countries: ISO3 codes to keep (default:
    every economy in the World Bank country list; regional and income aggregates are dropped). iso2_by_iso3:
    {ISO3: ISO2} for the BIS gap; without it the BIS is skipped and ews.py computes gaps from credit_gdp. Returns the
    rows written."""
    import csv
    from pathlib import Path
    raw = {}
    for col, ind in EWS_IMF.items():
        for iso, y, v in _ews_fetch(imf_series, f'IMF WEO {ind} (api.imf.org, SDMX)', ind, tuple(countries or ())):
            raw.setdefault((iso, y), {})[col] = v
    for col, ind in EWS_WB.items():
        for iso, y, v in _ews_fetch(wb_series, f'World Bank {ind} ({WB.format(ind=ind, y0=y0, y1=y1)})', ind, y0, y1):
            raw.setdefault((iso, y), {})[col] = v
    no_gap = []
    for iso3, iso2 in (iso2_by_iso3 or {}).items():
        try:
            gaps = bis_credit_gap(iso2, y0, y1)
        except EWSFetchError:    # the BIS publishes gaps for about 44 economies; ews.py computes the rest
            no_gap.append(iso3)
            continue
        for _, y, v in gaps:
            raw.setdefault((iso3, y), {})['credit_gap'] = v
    if no_gap:
        print(f'BIS credit gap not available for {len(no_gap)} of {len(iso2_by_iso3)} countries '
              f'({", ".join(no_gap[:12])}{", ..." if len(no_gap) > 12 else ""}): ews.py computes their gaps from credit_gdp')
    keep = set(countries) if countries else wb_economies()
    rows = []
    for (iso, y), d in sorted(raw.items()):
        if not y0 <= y <= y1 or iso not in keep:
            continue
        st = d.pop('st_debt_pct_reserves', None)
        d['reserves_std'] = 10000 / st if st else None
        rows.append({'country': iso, 'year': y, **d})
    path = Path(path) if path else Path(__file__).resolve().parents[1] / 'data' / 'ews_panel.csv'
    with open(path, 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=EWS_COLUMNS, extrasaction='ignore')
        w.writeheader()
        w.writerows(rows)
    return rows
