"""sovrisk.imf: IMF data through sdmx.Client('IMF_DATA'). No network: a fake client returns a hand-made SDMX-ML
message (tests/fixtures/imf_imts_sample.xml, hypothetical countries AAA, BBB and CCC, not real data)."""
from pathlib import Path

import pytest

sdmx = pytest.importorskip('sdmx')

from sovrisk import connectors, imf, spillover_data  # noqa: E402

SAMPLE = Path(__file__).parent / 'fixtures' / 'imf_imts_sample.xml'


class FakeIMF:
    """Stands in for sdmx.Client('IMF_DATA'): records each call and returns the sample message."""
    def __init__(self, path=SAMPLE):
        self.msg, self.calls = sdmx.read_sdmx(path), []

    def data(self, flow, key, params):
        self.calls.append((flow, key, params))
        return self.msg


def test_rows_drop_blanks_and_keep_attributes():
    out = imf.rows(sdmx.to_pandas(FakeIMF().msg, attributes='o'))
    assert [(d['COUNTERPART_COUNTRY'], p, v) for d, p, v, _ in out] == [('BBB', '2023', 6000.5), ('CCC', '2023', 8000.0)]
    assert out[0][3]['UNIT_MULT'] == '6'


def test_rows_from_a_plain_series():
    out = imf.rows(sdmx.to_pandas(FakeIMF().msg))
    assert len(out) == 2 and out[0][3] == {} and out[0][0]['COUNTRY'] == 'AAA'


def test_imts_key_and_scaling():
    fake = FakeIMF()
    out = imf.imts_exports('AAA', ['BBB', 'CCC'], 2023, 2024, imf=fake)
    assert fake.calls == [('IMTS', 'AAA.XG_FOB_USD.BBB+CCC.A', {'startPeriod': 2023, 'endPeriod': 2024})]
    # BBB carries UNIT_MULT 6; CCC has none, so the IMTS default (US$ millions) applies: both end in US$
    assert out == [('AAA', 'BBB', 2023, 6000.5e6), ('AAA', 'CCC', 2023, 8000e6)]


def test_weo_key_for_all_countries_and_a_list():
    fake = FakeIMF()
    imf.weo_series('PCPIPCH', imf=fake)
    imf.weo_series('PCPIPCH', ('AAA', 'BBB'), 2000, 2024, imf=fake)
    assert fake.calls == [('WEO', '.PCPIPCH.A', {}),
                          ('WEO', 'AAA+BBB.PCPIPCH.A', {'startPeriod': 2000, 'endPeriod': 2024})]


class Refusing:
    def data(self, *a, **k):
        raise OSError('Tunnel connection failed: 403 Forbidden')


def test_blocked_host_raises_and_writes_nothing(monkeypatch):
    with pytest.raises(imf.IMFUnavailable, match='api.imf.org'):
        imf.weo_series('PCPIPCH', imf=Refusing())
    monkeypatch.setattr(imf, 'client', lambda: Refusing())
    with pytest.raises(spillover_data.DataUnavailable, match='IMTS'):
        spillover_data.fetch_imf_exports('AAA', ['BBB'], 2023, 2023)
    with pytest.raises(imf.IMFUnavailable):
        connectors.imf_series('PCPIPCH')
