"""sovrisk.market: Yahoo Finance prices through yfinance. No network: a fake yfinance returns hand-made prices."""
import pandas as pd
import pytest

from sovrisk import market


class FakeTicker:
    def __init__(self, ticker, table):
        self.ticker, self.table = ticker, table

    def history(self, start, end, interval, auto_adjust):
        self.table.calls.append((self.ticker, start, end, interval))
        return self.table.prices.get(self.ticker, pd.DataFrame({'Close': []}))


class FakeYF:
    def __init__(self, prices):
        self.prices, self.calls = prices, []

    def Ticker(self, ticker):
        return FakeTicker(ticker, self)


def frame(values):
    return pd.DataFrame({'Close': values}, index=pd.to_datetime(['2024-01-01', '2024-02-01', '2024-03-01'][:len(values)]))


def test_fetch_writes_one_row_per_period_and_drops_blanks():
    yf = FakeYF({'^FVX': frame([4.0, float('nan'), 4.2]), 'ARS=X': frame([800.0])})
    series = {'ust_5y': market.SERIES['ust_5y'], **market.fx_series(['ARS'])}
    rows = market.fetch(series, '2024-01-01', '2024-03-31', yf=yf)
    assert [(r['series'], r['date'], r['value']) for r in rows] == [
        ('ust_5y', '2024-01-01', 4.0), ('ust_5y', '2024-03-01', 4.2), ('fx_ARS', '2024-01-01', 800.0)]
    assert rows[-1]['unit'] == 'ARS per US$' and 'not for redistribution' in rows[0]['source']
    assert yf.calls[0] == ('^FVX', '2024-01-01', '2024-03-31', '1mo')


def test_an_empty_or_failing_ticker_stops_the_run():
    with pytest.raises(market.MarketUnavailable, match='no prices for HG=F'):
        market.fetch({'copper': market.SERIES['copper']}, '2024-01-01', '2024-03-31', yf=FakeYF({}))

    class Refusing:
        def Ticker(self, t):
            raise OSError('Tunnel connection failed: 403 Forbidden')
    with pytest.raises(market.MarketUnavailable, match='Yahoo Finance'):
        market.fetch({'copper': market.SERIES['copper']}, '2024-01-01', '2024-03-31', yf=Refusing())


def test_output_file_is_kept_out_of_git():
    from pathlib import Path
    ignore = (Path(__file__).parents[1] / '.gitignore').read_text().split()
    assert 'data/market_prices.csv' in ignore
