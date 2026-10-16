"""IMF data through the IMF's SDMX API (api.imf.org), using the sdmx1 package's IMF_DATA source.

    import sdmx
    IMF_DATA = sdmx.Client('IMF_DATA')
    data_msg = IMF_DATA.data('CPI', key='USA+CAN.CPI.CP01.IX.M', params={'startPeriod': 2018})
    cpi_df = sdmx.to_pandas(data_msg)

Every IMF series the models read goes through fetch() below, which does exactly that and returns plain rows. A key
is the dataflow's dimension values in order, separated by dots; '+' joins several values and an empty position
means all of them. The IMF portal keys countries by ISO3, the same codes the models use.

NOT YET RUN against a live response: api.imf.org is blocked in the build environment. The WEO and IMTS keys below
follow the IMF's published dimension order, but check them once with describe('WEO') and describe('IMTS')
(python scripts/fetch_country_data.py imf-describe WEO) before relying on them. Install the client with
pip install sdmx1, or pip install -e .[data].
"""

# dataflow id, key template (dimension order in the comment)
WEO = ('WEO', '{country}.{indicator}.A')                      # COUNTRY.INDICATOR.FREQUENCY
IMTS = ('IMTS', '{country}.{indicator}.{partner}.A')          # COUNTRY.INDICATOR.COUNTERPART_COUNTRY.FREQUENCY
IMTS_EXPORTS = 'XG_FOB_USD'        # goods exports, FOB, US dollars (legacy DOTS code TXG_FOB_USD); to verify
IMTS_DEFAULT_SCALE = 1e6           # IMTS values are in US$ millions unless the response carries UNIT_MULT


class IMFUnavailable(RuntimeError):
    pass


def client():
    try:
        import sdmx
    except ImportError as e:
        raise IMFUnavailable('IMF data needs the sdmx1 package: pip install sdmx1 (or pip install -e .[data])') from e
    return sdmx.Client('IMF_DATA')


def fetch(flow, key, start=None, end=None, imf=None):
    """Observations of one IMF dataflow as [(dimensions, period, value, attributes)]: dimensions and attributes are
    dicts keyed by their SDMX ids; period is the TIME_PERIOD text (2024, 2024-Q4, 2024-01). Blank values are
    dropped."""
    import sdmx
    params = {k: v for k, v in (('startPeriod', start), ('endPeriod', end)) if v is not None}
    imf = imf or client()
    try:
        msg = imf.data(flow, key=key, params=params)
    except Exception as e:  # network refusal, HTTP error, or a key the dataflow rejects
        raise IMFUnavailable(f'could not fetch IMF {flow} {key} from api.imf.org: {type(e).__name__}: {e}. If the host '
                             'is blocked, run where api.imf.org is reachable; no data was written.') from e
    return rows(sdmx.to_pandas(msg, attributes='o'))


def rows(table):
    """sdmx.to_pandas output (a Series, or a DataFrame with a 'value' column and attribute columns, or a list of
    either) -> [(dimensions, period, value, attributes)]."""
    import math
    if isinstance(table, (list, tuple)):
        return [r for t in table for r in rows(t)]
    names = list(table.index.names)
    if hasattr(table, 'columns'):
        attrs = [c for c in table.columns if c != 'value']
        items = ((i, r['value'], {a: r[a] for a in attrs}) for i, r in table.iterrows())
    else:
        items = ((i, v, {}) for i, v in table.items())
    out = []
    for idx, v, at in items:
        if v is None or (isinstance(v, float) and math.isnan(v)):
            continue
        dims = dict(zip(names, idx if isinstance(idx, tuple) else (idx,)))
        period = str(dims.pop('TIME_PERIOD'))
        out.append((dims, period, float(v), at))
    return out


def _first(dims, name):
    return dims.get(name, next(iter(dims.values())))


def weo_series(indicator, countries=(), y0=None, y1=None, imf=None):
    """One World Economic Outlook indicator (e.g. PCPIPCH, BCA_NGDPD) as [(iso3, year, value)]. countries: ISO3
    codes; empty means every country and group the WEO covers."""
    flow, tpl = WEO
    key = tpl.format(country='+'.join(countries), indicator=indicator)
    return [(_first(d, 'COUNTRY'), int(p[:4]), v) for d, p, v, _ in fetch(flow, key, y0, y1, imf)]


def imts_exports(reporter, partners, y0, y1, imf=None):
    """Annual goods exports from reporter to each partner (ISO3 codes) as [(reporter, partner, year, US$)]."""
    flow, tpl = IMTS
    key = tpl.format(country=reporter, indicator=IMTS_EXPORTS, partner='+'.join(partners))
    out = []
    for d, p, v, at in fetch(flow, key, y0, y1, imf):
        mult = at.get('UNIT_MULT')
        scale = 10 ** int(float(mult)) if mult not in (None, '') and str(mult) != 'nan' else IMTS_DEFAULT_SCALE
        out.append((_first(d, 'COUNTRY'), d.get('COUNTERPART_COUNTRY', list(d.values())[2]), int(p[:4]), v * scale))
    return out


def describe(flow, imf=None):
    """The dataflow's dimensions in key order, each with up to 12 of its codes, to check a key against."""
    imf = imf or client()
    try:
        msg = imf.dataflow(flow, params={'references': 'all'})
    except Exception as e:
        raise IMFUnavailable(f'could not fetch the IMF {flow} structure from api.imf.org: {type(e).__name__}: {e}') from e
    dsd = msg.dataflow[flow].structure
    out = []
    for dim in dsd.dimensions.components:
        rep = getattr(dim, 'local_representation', None)
        cl = getattr(rep, 'enumerated', None) if rep else None
        codes = [c.id for c in cl][:12] if cl is not None else []
        out.append((dim.id, codes))
    return out
