"""Market prices from Yahoo Finance through the yfinance package: US Treasury yields, oil, copper and exchange rates.

    python scripts/fetch_country_data.py market --years 2015-2026 --fx ARS,ZMW

Writes data/market_prices.csv (series, ticker, date, value, unit, source), one row per period (monthly by default).
The file is in .gitignore: Yahoo's terms do not allow redistributing its data, so it stays in the private copy and
never goes to the public repo.

Yahoo carries no sovereign CDS and few emerging-market government bonds, so data/market_spreads.csv (5-year CDS, used
for the market-implied default probability) is still entered by hand.

NOT YET RUN against a live response: Yahoo's hosts are blocked in the build environment. Check the first output by
eye: Yahoo quotes the Treasury yield indices (^IRX, ^FVX, ^TNX) in percent, and an exchange rate 'ARS=X' as local
currency per US dollar. Install the package with pip install yfinance, or pip install -e .[data].
"""
import csv
from pathlib import Path

from .config import ROOT

# series id: (Yahoo ticker, unit)
SERIES = {
    'ust_3m': ('^IRX', '% (13-week T-bill yield)'),
    'ust_5y': ('^FVX', '% (5-year Treasury yield)'),
    'ust_10y': ('^TNX', '% (10-year Treasury yield)'),
    'brent': ('BZ=F', 'US$ per barrel (front-month future)'),
    'wti': ('CL=F', 'US$ per barrel (front-month future)'),
    'copper': ('HG=F', 'US$ per pound (front-month future)'),
}
FIELDS = ['series', 'ticker', 'date', 'value', 'unit', 'source']
SOURCE = 'Yahoo Finance via yfinance (not for redistribution)'


class MarketUnavailable(RuntimeError):
    pass


def fx_series(currencies):
    """{'fx_ARS': ('ARS=X', 'ARS per US$'), ...} for ISO 4217 currency codes."""
    return {f'fx_{c}': (f'{c}=X', f'{c} per US$') for c in currencies}


def _yf():
    try:
        import yfinance
    except ImportError as e:
        raise MarketUnavailable('market prices need the yfinance package: pip install yfinance '
                                '(or pip install -e .[data])') from e
    return yfinance


def close_rows(name, ticker, unit, history):
    """A yfinance history DataFrame (index = dates, a Close column) -> rows for market_prices.csv; blanks dropped."""
    import math
    out = []
    for when, v in history['Close'].items():
        if v is None or (isinstance(v, float) and math.isnan(v)):
            continue
        out.append({'series': name, 'ticker': ticker, 'date': str(when)[:10], 'value': round(float(v), 6),
                    'unit': unit, 'source': SOURCE})
    return out


def fetch(series, start, end, interval='1mo', yf=None):
    """Closing prices for each series {name: (ticker, unit)} between start and end (YYYY-MM-DD). A ticker that fails
    or returns nothing stops the run with an error naming it; nothing is filled in."""
    yf = yf or _yf()
    rows = []
    for name, (ticker, unit) in series.items():
        try:
            hist = yf.Ticker(ticker).history(start=start, end=end, interval=interval, auto_adjust=False)
        except Exception as e:  # network refusal, HTTP error, or an unknown ticker
            raise MarketUnavailable(f'could not fetch {ticker} ({name}) from Yahoo Finance: {type(e).__name__}: {e}. '
                                    'If the host is blocked, run where Yahoo Finance is reachable; no data was '
                                    'written.') from e
        got = close_rows(name, ticker, unit, hist) if hist is not None and len(hist) else []
        if not got:
            raise MarketUnavailable(f'Yahoo Finance returned no prices for {ticker} ({name}) between {start} and '
                                    f'{end}; check the ticker. No data was written.')
        rows += got
    return rows


def write(rows, root=ROOT):
    path = Path(root) / 'data' / 'market_prices.csv'
    with open(path, 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)
    return path
