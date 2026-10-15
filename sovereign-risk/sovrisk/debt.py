"""Debt-to-GDP stress paths (port of the Debt Scenarios tab)."""

YEARS = list(range(2015, 2032))


def _n(x):
    return 0 if x is None else x


def stress_paths(baseline, ds):
    """Return {'baseline', 'macro', 'combined'} year -> value for one country.

    Countries with no WEO projection for 2026 have no stress rows (None). Each year from 2027 the
    stress path keeps the previous year's gap to baseline, adds the primary balance shock and the
    growth shock's effect (2027 and 2028 only); the combined path also revalues FX debt in 2027.
    """
    base = {y: baseline.get(y) for y in YEARS}
    if base[2026] is None:
        return {'baseline': base, 'macro': None, 'combined': None}
    out = {'baseline': base}
    for name, fx in (('macro', 0), ('combined', _n(baseline.get('fx_share')))):
        s = {2026: base[2026]}
        for y in range(2027, 2032):
            g = ds['growth_shock'] if y in (2027, 2028) else 0
            v = _n(base[y]) + (s[y - 1] - _n(base[y - 1])) + ds['pb_shock'] + s[y - 1] * (g / 100) / (1 + ds['nominal_growth'])
            if name == 'combined' and y == 2027:
                v += s[y - 1] * fx * ds['depreciation']
            s[y] = v
        out[name] = s
    return out
