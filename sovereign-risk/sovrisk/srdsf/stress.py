"""STDesign and STOps sheets: the medium-term stress tests.

* STDesign activates and calibrates the shocks of the five stress tests (banking crisis, exchange rate, natural
  disaster, contingent liabilities, commodity prices). Each test is a block of shock rows; a row's shock applies
  in year t when the test is activated (Signals), the row is switched on (column F) and t lies between the row's
  start and end years (G, H). The macro shocks are combined into a scenario path for nominal GDP relative to the
  baseline (the "interactions" and "nominal GDP in percent of baseline" rows), which in turn scales the
  revenue, expenditure and interest-rate shocks of some tests.

* STOps runs the debt dynamics of the baseline and of each stress scenario. The baseline block (rows 7-140)
  takes the baseline fiscal and macro paths from BaseDB, the effective interest rates and amortization
  schedules of new debt (by vintage) from IdentFin/ResidFin, and recomputes gross financing needs, debt
  issuance (solving for the issuance that also finances its own interest and amortization) and the debt stock
  by currency (local, foreign, two index-linked). Each scenario block (135 rows each: ER, ND, CL, BC, CP) adds
  the STDesign shocks to the baseline paths and repeats the calculation. Columns AL:AR hold checks against
  BaseDB (baseline) or differences from the baseline (scenarios).
"""
import math

from .xl import NA, VALUE, calc, iserr, isnumber, num

SHEETS = ['STDesign', 'STOps']

QUIRKS = [
    # STDesign
    "STDesign row 48/70/91/113/134 (scenario nominal GDP relative to baseline): the expansion of the product of "
    "(1+shock/(1+g)) terms keeps the single and pairwise terms, but for 4+ years only adds the product of all "
    "terms; triple (and other higher-order) terms are omitted, so it is not the exact cumulative product.",
    "STDesign banking-crisis economic-slack row 43 applies the parameter to the real GDP shock itself (I43*K40), "
    "whereas the other tests apply it to the shocked growth minus baseline growth (I*(K_g-K19)).",
    "STDesign I31 (banking-crisis expenditure shock) is SWITCH(AEEM,...) times NGDP of year 1 (L4), whatever the "
    "start year; with AEEM an error it is #N/A, but the row is only used when the test is active.",
    # STOps
    "STOps L75 (and the same cell in every scenario block) reads the vintage year from E90 (2028) while G75:K75 "
    "read E92:E96 and the other currencies E85:E90; the years agree so the value is unaffected.",
    "STOps baseline AF134:AJ139 (new local-linked-2 debt, interest base) multiply by the local-linked-1 issuance "
    "($W120..) instead of the local-linked-2 issuance ($AE120..); the scenario blocks use the right column.",
    "STOps scenario blocks: existing index-linked interest (row k=10, e.g. F287:L287) is BaseDB GGEICI_H divided "
    "by the baseline foreign exchange rate (N60) and multiplied by the scenario foreign depreciation RATE (N331), "
    "not an exchange-rate level or the index ratios used in the baseline.",
    "STOps scenario blocks: new foreign-currency amortization (row k=23, e.g. G300:L300) multiplies by the "
    "exchange rate one column to the left (N330 for year G, i.e. the previous year) instead of the same year.",
    "STOps scenario blocks: existing index-linked amortization in column F (rows k=19..21, e.g. F296:F298) is "
    "BaseDB value / N60 * N331 (foreign depreciation rate), unlike G:L which use the index ratios.",
    "STOps scenario blocks: index-linked depreciation (W:AB, AE:AJ of the depreciation rows) is shocked with the "
    "inflation shock (key SHK_NGDP_DPCH_<scenario> via U column), not an exchange-rate shock.",
    "STOps ER block: AB223 tests the issuance flag of column Y instead of Z (vintage 2026, local-linked 1).",
    "STOps ER block: the local-linked-2 'share outstanding for interest' rows (AE227:AJ232) sum the "
    "'Local-Linked 1' rows of IdentFin/ResidFin instead of 'Local-Linked 2'.",
    "STOps scenario blocks: the check column B (k=92..94, 99..101, 106..108) compares column I with a different "
    "block: ND with the baseline, CL with ER, BC with ND, CP with CL.",
    "STOps AL43:AR43 compare issuance with BaseDB 'GADL' (the issuance share series, not an amount); AL43 is "
    "#VALUE! because that lookup returns text for year -1.",
]

# ---------------------------------------------------------------------------------------------------------------
# Excel helpers


def _key(v):
    """Lookup key with Excel equality: text case-insensitive, numbers by value, booleans apart."""
    if isinstance(v, bool):
        return ('b', v)
    if isinstance(v, (int, float)):
        return ('n', float(v))
    if v is None:
        return None
    return ('s', str(v).lower())


def xcmp(a, b):
    """Excel comparison a ? b: -1/0/1, or the error. Numbers < text < booleans; blank is 0 or ''."""
    for v in (a, b):
        if iserr(v):
            return v
    if a is None:
        a = '' if isinstance(b, str) else (False if isinstance(b, bool) else 0)
    if b is None:
        b = '' if isinstance(a, str) else (False if isinstance(a, bool) else 0)

    def rank(v):
        return 2 if isinstance(v, bool) else (1 if isinstance(v, str) else 0)
    ra, rb = rank(a), rank(b)
    if ra != rb:
        return -1 if ra < rb else 1
    if ra == 1:
        a, b = a.lower(), b.lower()
    return (a > b) - (a < b)


def lt(a, b):
    c = xcmp(a, b)
    return c if iserr(c) else c < 0


def le(a, b):
    c = xcmp(a, b)
    return c if iserr(c) else c <= 0


def gt(a, b):
    c = xcmp(a, b)
    return c if iserr(c) else c > 0


def ge(a, b):
    c = xcmp(a, b)
    return c if iserr(c) else c >= 0


def xeq(a, b):
    c = xcmp(a, b)
    return c if iserr(c) else c == 0


def _logicals(vals):
    out = []
    for v in vals:
        if iserr(v):
            return v
        if isinstance(v, bool):
            out.append(v)
        elif isinstance(v, (int, float)):
            out.append(v != 0)
        # text and blanks in references are ignored
    return out


def xand(*vals):
    xs = _logicals(vals)
    if isinstance(xs, str):
        return xs
    return all(xs) if xs else VALUE


def xor(*vals):
    xs = _logicals(vals)
    if isinstance(xs, str):
        return xs
    return any(xs) if xs else VALUE


def truth(v):
    """IF condition: error -> the error, text -> #VALUE!, else bool."""
    if iserr(v):
        return v
    if isinstance(v, str):
        return VALUE
    return bool(num(v))


def xnot(v):
    t = truth(v)
    return t if isinstance(t, str) else not t


def xmatch(x, seq):
    """MATCH(x, seq, 0)."""
    if iserr(x):
        return x
    k = _key(x)
    for i, v in enumerate(seq):
        if v is not None and _key(v) == k:
            return i + 1
    return NA


class Table:
    """VLOOKUP(key, area, col, FALSE) over a defined name, indexed once (first match wins)."""

    def __init__(self, book, name):
        sh, c0, r0, c1, r1 = book.area(name)
        self.S, self.c0, self.width = book[sh], c0, c1 - c0 + 1
        self.rows = {}
        for r in range(r1, r0 - 1, -1):
            k = _key(self.S.get(r, c0))
            if k is not None:
                self.rows[k] = r

    def __call__(self, key, col):
        if iserr(key):
            return key
        if iserr(col):
            return col
        if not isnumber(col) or col < 1:
            return VALUE
        if col > self.width:
            return '#REF!'
        r = self.rows.get(_key(key))
        if r is None:
            return NA
        v = self.S.get(r, self.c0 + int(col) - 1)
        return 0 if v is None else v


def add(*v):
    return calc(lambda *x: sum(x), *v)


def sub(a, b):
    return calc(lambda x, y: x - y, a, b)


def mul(*v):
    return calc(lambda *x: math.prod(x), *v)


def div(a, b):
    return calc(lambda x, y: x / y, a, b)


def xsum(vals):
    t = 0.0
    for v in vals:
        if iserr(v):
            return v
        if isnumber(v):
            t += v
    return t


# ---------------------------------------------------------------------------------------------------------------
# STDesign

DYRS = range(10, 17)            # J..P: years -1..5
SYRS = range(11, 17)            # K..P: shock years 0..5

# Row layout of each stress-test block: header (activation), shock rows, interactions and GDP ratio rows.
FIELDS = ('rev', 'exp', 'cl', 'ropi', 'odcta', 'odctl', 'odctp', 'fi', 'g', 'pi', 'pt', 'slack', 'oth', 'enda',
          'ende', 'inter', 'ratio')
BLOCKS = {
    'BC': (28, (30, 31, 33, 34, 35, 36, 37, 38, 40, 41, 42, 43, 44, 45, 46, 47, 48)),
    'ER': (49, (52, 53, 55, 56, 57, 58, 59, 60, 62, 63, 64, 65, 66, 67, 68, 69, 70)),
    'ND': (71, (73, 74, 76, 77, 78, 79, 80, 81, 83, 84, 85, 86, 87, 88, 89, 90, 91)),
    'CL': (93, (95, 96, 98, 99, 100, 101, 102, 103, 105, 106, 107, 108, 109, 110, 111, 112, 113)),
    'CP': (114, (116, 117, 119, 120, 121, 122, 123, 124, 126, 127, 128, 129, 130, 131, 132, 133, 134)),
}


def _gdp_ratio(S, r_inter, c):
    """Scenario nominal GDP in percent of baseline: 1 + sum of x_i/g_i + pairwise products (+ product of all
    terms from the 4th year on), x = interaction row, g = 1 + baseline nominal growth (row 27)."""
    cols = list(range(11, c + 1))
    xs = [S.get(r_inter, k) for k in cols]
    gs = [S.get(27, k) for k in cols]

    def f(*v):
        n = len(cols)
        x, g = v[:n], v[n:]
        t = 1 + sum(x[i] / g[i] for i in range(n))
        t += sum(x[i] * x[j] / (g[i] * g[j]) for i in range(n) for j in range(i + 1, n))
        if n >= 4:
            t += math.prod(x) / math.prod(g)
        return t
    return calc(f, *xs, *gs)


def stdesign(book):
    S = book['STDesign']
    proj = book.name('ProjYr')
    base = Table(book, 'BaseDBData')
    nmf = Table(book, 'NewMacrofwData')
    nmf_dates = book.hrow('NewMacrofwDates')
    dates = book.hrow('BaseDBdates')
    sig = Table(book, 'SignalsTable')
    act_col = xmatch('Activated', book.hrow('SignalsHeaders'))

    # Years, year offsets and BaseDB columns
    for c in DYRS:
        if c > 10:
            S.set(3, c, add(S.get(3, c - 1), 1))
        S.set(2, c, add(proj, S.get(3, c)))
        S.set(4, c, xmatch(S.get(3, c), dates))

    # Baseline: BaseDB paths (row 27 is 1 + nominal GDP growth), primary balance in percent of GDP
    for r in (9, 10, 12, 13, 14, 15, 16, 19, 20, 24, 25, 26, 27):
        for c in DYRS:
            v = base(S.get(r, 2), S.get(4, c))
            S.set(r, c, add(1, v) if r == 27 else v)
    for c in SYRS:
        S.set(8, c, div(sub(S.get(9, c), S.get(10, c)), S.get(26, c)))

    # Calibration cells in columns F, H and I
    stcl = book.name('STCLshock')
    aeem = book.name('AEEM')
    flex = book.name('BoolFlexER')
    nmf_mt = xmatch(book.name('MTHorizon'), nmf_dates)
    nmf_last = xmatch(-1, nmf_dates)
    sw = aeem if iserr(aeem) else {'ae': 0.068, 'em': 0.1}.get(str(aeem).lower(), NA)
    S['I31'] = mul(sw, base('NGDP', S['L4']))                       # BC expenditure: 6.8/10 pct of GDP
    S['I33'] = xsum([stcl])
    S['I40'] = calc(lambda v: -v, base(S['B40'], S['J4']))           # BC growth: -1 SD
    S['H50'] = S['G50']
    S['F64'] = flex
    S['I64'] = aeem if iserr(aeem) else (0.25 if xeq(aeem, 'EM') else 0.03)
    S['F66'] = xnot(flex)
    S['F67'] = flex
    S['F68'] = flex
    S['I67'] = nmf(S['B67'], nmf_mt)
    S['I68'] = nmf(S['B68'], nmf_mt)
    t = truth(S['F66'])
    S['I66'] = t if iserr(t) else (calc(lambda v: -v / 6, nmf(S['B67'], nmf_mt)) if t else 0)
    S['F63'] = xor(S['F64'], S['F65'], S['F66'])
    S['I98'] = stcl
    S['I116'] = calc(lambda x: ((x * 0.5) / 0.1) / 100, S['I136'])
    S['I119'] = xsum([stcl])
    S['I124'] = calc(lambda x: x * 0.25 * 100, S['I116'])
    S['I126'] = calc(lambda x: (x * 0.5 / 0.1) / 100, S['I136'])
    S['I130'] = mul(nmf(S['B130'], nmf_last), S['I136'])
    S['H137'] = add(S['G137'], S['I137'])
    S['I139'] = 1.5 * 25

    # Phase-out of the commodity price shock: 1 in the first two years, then linearly to 0
    g, h, n = S['G137'], S['H137'], S['I137']
    for c in SYRS:
        y = S.get(3, c)
        cond = xand(ge(y, g), le(y, h))
        if iserr(cond):
            v = cond
        elif cond:
            first = xor(xeq(y, g), xeq(y, add(g, 1)))
            v = first if iserr(first) else (1 if first else calc(lambda n, y, g: (n - (y - g)) / (n - 1), n, y, g))
        else:
            v = 0
        S.set(137, c, v)

    for name, (h, rows) in BLOCKS.items():
        R = dict(zip(FIELDS, rows))
        S.set(h, 6, sig(S.get(h, 2), act_col))                     # test activated (Signals)
        _block(S, name, h, R)


def _block(S, name, h, R):
    def shock(r, c, expr):
        """IF(AND($F<h>, $F<r>, year>=start, year<=end), expr, 0)."""
        y = S.get(3, c)
        cond = xand(S.get(h, 6), S.get(r, 6), ge(y, S.get(r, 7)), le(y, S.get(r, 8)))
        if iserr(cond):
            return cond
        return expr() if cond else 0

    def I(r):
        return S.get(r, 9)

    def at(r, c):
        return S.get(r, c)

    def put(field, expr):
        r = R[field]
        for c in SYRS:
            S.set(r, c, shock(r, c, lambda: expr(r, c)))

    plain = lambda r, c: I(r)
    # Macro shocks: growth, exchange rates, deflator components
    if name == 'CP':
        put('g', lambda r, c: mul(I(r), at(137, c)))                 # growth shock phased out
    else:
        put('g', plain)
    put('enda', plain)
    put('ende', plain)
    put('pt', lambda r, c: mul(I(r), at(R['enda'], c)))              # pass-through of depreciation
    if name == 'BC':
        put('slack', lambda r, c: mul(I(r), at(R['g'], c)))
    else:
        put('slack', lambda r, c: mul(I(r), sub(at(R['g'], c), at(19, c))))
    if name == 'CP':
        put('oth', lambda r, c: mul(I(r), at(20, c)))                # commodity prices x deflator
    else:
        put('oth', plain)
    for c in SYRS:
        S.set(R['pi'], c, add(at(R['pt'], c), at(R['slack'], c), at(R['oth'], c)))
        x, p = at(R['g'], c), at(R['pi'], c)
        S.set(R['inter'], c, calc(lambda x, p, g0, d0: x + p + g0 * p + d0 * x + x * p, x, p, at(19, c), at(20, c)))
    for c in SYRS:
        S.set(R['ratio'], c, _gdp_ratio(S, R['inter'], c))
    ratio = R['ratio']

    # Primary balance shocks
    if name == 'BC':
        put('rev', lambda r, c: mul(sub(at(ratio, c), 1), at(9, c)))     # revenue/GDP held at baseline
        put('exp', plain)
    elif name == 'CP':
        for c in SYRS:
            r = R['rev']
            if c == 11:
                f = lambda: mul(at(9, c), sub(at(ratio, c), 1))
            else:
                f = lambda: add(mul(at(9, c), sub(at(ratio, c), 1)), mul(I(r), at(26, c), at(ratio, c), at(137, c)))
            S.set(r, c, shock(r, c, f))
        put('exp', lambda r, c: mul(sub(at(ratio, c), 1), at(10, c)))
    else:
        put('rev', plain)
        put('exp', plain)
    # Other fiscal shocks
    if name == 'ND':
        put('cl', lambda r, c: mul(I(r), at(26, c), at(ratio, c)))
    else:
        put('cl', plain)
    for f in ('ropi', 'odcta', 'odctl', 'odctp'):
        put(f, plain)
    # Interest rate shock
    if name == 'BC':
        put('fi', lambda r, c: calc(lambda i, a, b, y, q: -i * (a - b) / (y * q),
                                    I(r), at(R['rev'], c), at(R['exp'], c), at(26, c), at(ratio, c)))
    elif name == 'CP':
        for c in SYRS:                                               # scenario primary balance, pct of GDP
            S.set(115, c, calc(lambda a, b, d, e, y, q: ((a + b) - (d + e)) / y * q, at(116, c), at(9, c),
                               at(117, c), at(10, c), at(26, c), at(ratio, c)))
        put('fi', lambda r, c: calc(lambda i, a, b: i * (a - b) * 100, I(r), at(115, c), at(8, c)))
    else:
        put('fi', plain)


# ---------------------------------------------------------------------------------------------------------------


def compute(book, sheet):
    if sheet == 'STDesign':
        stdesign(book)
    elif sheet == 'STOps':
        stops(book)
    else:
        raise KeyError(sheet)


# ---------------------------------------------------------------------------------------------------------------
# STOps

LOC, FOR, LL1, LL2 = 'Local', 'Foreign', 'Local-Linked 1', 'Local-Linked 2'
CURS = (LOC, FOR, LL1, LL2)
BASECOL = {LOC: 6, FOR: 14, LL1: 22, LL2: 30}      # column of year -1 in each currency group (F, N, V, AD)
YEARS = range(-1, 6)                                # year offsets -1..5 (F..L)
NEW = range(0, 6)                                   # years with new debt / vintages 0..5 (G..L)
SCENARIOS = {'ER': 142, 'ND': 277, 'CL': 412, 'BC': 547, 'CP': 682}
CHECK_REF = {'ND': 7, 'CL': 142, 'BC': 277, 'CP': 412}   # block whose column I the B-column checks compare with
FIN_COL0 = 21                                       # IdentFin/ResidFin column U = year 0

# Rows of the debt engine, as offsets from a block's first row (the same in the baseline and the scenarios)
K_ENDA, K_ENDA_PCH, K_ENDE, K_ENDE_PCH = 53, 54, 55, 56
K_SHARE, K_FLAG, K_FI, K_EFF, K_GGFA, K_INTB = 67, 68, 70, 71, 78, 85
K_INT, K_AMT, K_SUMIA, K_OUT, K_AMTP, K_INTP = 92, 99, 106, 113, 120, 127


def col(cur, t):
    return BASECOL[cur] + 1 + t


class Fin:
    """SUMIFS(<sheet>!<col>, Q, crit, G, "="&year, K, "="&currency) over IdentFin plus the same over ResidFin."""

    def __init__(self, book):
        self.idx = []
        for name in ('IdentFin', 'ResidFin'):
            S = book[name]
            groups = {}
            for r in sorted({r for r, _ in S.cells}):
                q, g, k = S.get(r, 17), S.get(r, 7), S.get(r, 11)
                if not isinstance(q, str) or not isinstance(k, str):
                    continue
                if isinstance(g, str):
                    try:
                        g = float(g)
                    except ValueError:
                        continue
                if not isnumber(g):
                    continue
                groups.setdefault((q.lower(), float(g), k.lower()), []).append(r)
            self.idx.append((S, groups))
        self.cache = {}

    def __call__(self, crit, c, year, cur):
        if iserr(year):
            return year
        if not isnumber(year):
            return 0.0
        key = (crit.lower(), c, float(year), cur.lower())
        if key not in self.cache:
            parts = []
            for S, groups in self.idx:
                vals = [S.get(r, c) for r in groups.get(key[:1] + key[2:], ())]
                parts.append(xsum(vals))
            self.cache[key] = add(*parts)
        return self.cache[key]


def _if(cond, a, b=0):
    """IF(cond, a(), b) with a lazily evaluated."""
    t = truth(cond)
    if iserr(t):
        return t
    return a() if t else b


def stops(book):
    S = book['STOps']
    proj = book.name('ProjYr')
    ctx = dict(base=Table(book, 'BaseDBData'), design=Table(book, 'STDesignData'), fin=Fin(book), proj=proj)
    dates = book.hrow('BaseDBdates')
    dyrs = book.hrow('STDesignYrs')

    # Header: years, BaseDB columns, STDesign columns
    for cur in CURS:
        for t in YEARS:
            c = col(cur, t)
            S.set(3, c, add(proj, S.get(4, c)))
            S.set(5, c, xmatch(S.get(4, c), dates))
            S.set(6, c, xmatch(S.get(4, c), dyrs))
    S.set(6, 13, xmatch(S.get(4, 13), dyrs))                    # M6 ('SHOCK' column)

    _baseline(S, ctx)
    for name, s in SCENARIOS.items():
        _scenario(S, ctx, name, s)


def _labels(S, s, rows):
    """Column A: series code + scenario suffix (B<row>&B<s>, or a literal prefix)."""
    for k, lit in rows:
        S.set(s + k, 1, calc_concat(lit if lit is not None else S.get(s + k, 2), S.get(s, 2)))


def calc_concat(*vals):
    e = next((v for v in vals if iserr(v)), None)
    if e:
        return e
    out = []
    for v in vals:
        if v is None:
            out.append('')
        elif isinstance(v, bool):
            out.append('TRUE' if v else 'FALSE')
        elif isinstance(v, float) and v.is_integer():
            out.append(str(int(v)))
        else:
            out.append(str(v))
    return ''.join(out)


def _years_col_e(S, s, ctx):
    """Column E of the vintage tables: ProjYr + D."""
    for k0 in (K_EFF, K_GGFA, K_INTB, K_INT, K_AMT, K_SUMIA, K_OUT, K_AMTP, K_INTP):
        for v in NEW:
            r = s + k0 + v
            S.set(r, 5, add(ctx['proj'], S.get(r, 4)))


def _engine(S, ctx, s, k_iss, eff, ll2_int_col=LL2, quirks=()):
    """Debt engine shared by all blocks (rows s+67 .. s+132): issuance flags, shares of each vintage still to be
    amortized / bearing interest, interest and amortization per unit of issuance, and, once issuance is known,
    debt outstanding, amortization and interest payments by vintage. eff(v, cur, t) gives the effective interest
    rate of vintage v in year t."""
    fin = ctx['fin']
    E = lambda r: S.get(r, 5)

    def year_row_flag(cur, t):
        if cur == LOC:
            return s + K_INTB + t if t < 5 else s + K_GGFA + 5
        return s + K_GGFA + t

    # Debt issuance > 0, by currency and year
    for cur in CURS:
        for t in NEW:
            v = fin('GGD', FIN_COL0 + t, E(year_row_flag(cur, t)), cur)
            S.set(s + K_FLAG, col(cur, t), v if iserr(v) else v != 0)
    # Effective interest rates (vintage v, year t >= v)
    for cur in CURS:
        for v in NEW:
            for t in range(v, 6):
                S.set(s + K_EFF + v, col(cur, t), eff(v, cur, t))
    # Shares of vintage v outstanding: for amortization (GGFA) and for interest (INT_BASE)
    for k0, crit in ((K_GGFA, 'GGFA'), (K_INTB, 'INT_BASE')):
        for cur in CURS:
            for v in NEW:
                r = s + k0 + v
                for t in range(v, 6):
                    fcur, fcol = cur, col(cur, v)
                    if ('ll2_int_as_ll1' in quirks and k0 == K_INTB and cur == LL2):
                        fcur = LL1
                    if ('ab81' in quirks and k0 == K_GGFA and cur == LL1 and v == 3 and t == 5):
                        fcol = col(LL1, 2)
                    S.set(r, col(cur, t), _if(S.get(s + K_FLAG, fcol),
                                              lambda: div(fin(crit, FIN_COL0 + t, E(r), fcur),
                                                          fin('GGD', FIN_COL0 + v, E(r), fcur))))
    # Interest and amortization per unit of issuance (in local currency)
    for cur in CURS:
        for v in NEW:
            for t in range(v, 6):
                c, cv = col(cur, t), col(cur, v)
                share, fx, fxv = S.get(s + K_SHARE, cv), S.get(s + K_ENDA, c), S.get(s + K_ENDA, cv)
                S.set(s + K_INT + v, c, calc(lambda a, b, i, q, d: a * b * i * q / d, share, fx,
                                             S.get(s + K_EFF + v, c), S.get(s + K_INTB + v, c), fxv))
                S.set(s + K_AMT + v, c, calc(lambda a, b, q, d: a * b * q / d, share, fx,
                                             S.get(s + K_GGFA + v, c), fxv))
    # Sum over currencies (local columns only)
    for v in NEW:
        for t in range(v, 6):
            c = col(LOC, t)
            S.set(s + K_SUMIA + v, c, add(S.get(s + K_INT + v, c), S.get(s + K_INT + v, c + 8),
                                          S.get(s + K_INT + v, c + 16), S.get(s + K_AMT + v, c),
                                          S.get(s + K_AMT + v, c + 8), S.get(s + K_AMT + v, c + 16),
                                          S.get(s + K_INT + v, c + 24), S.get(s + K_AMT + v, c + 24)))
    # Total debt to be issued: issuance also finances interest/amortization falling due on itself
    r_xd, r_iss = s + k_iss - 1, s + k_iss
    for t in NEW:
        c = col(LOC, t)
        terms = [S.get(r_xd, c)]
        for i in range(t):
            terms += [S.get(r_iss, col(LOC, i)), S.get(s + K_SUMIA + i, c)]
        terms.append(S.get(s + K_SUMIA + t, c))

        def f(*x):
            acc = x[0]
            for j in range(t):
                acc += x[1 + 2 * j] * x[2 + 2 * j]
            return acc / (1 - x[-1])
        S.set(r_iss, c, calc(f, *terms))
    # Debt outstanding, amortization and interest payments by vintage
    for cur in CURS:
        for v in NEW:
            cv = col(cur, v)
            ro, ra, ri = s + K_OUT + v, s + K_AMTP + v, s + K_INTP + v
            S.set(ro, cv, calc(lambda a, b, d: a * b / d, S.get(r_iss, col(LOC, v)), S.get(s + K_SHARE, cv),
                               S.get(s + K_ENDA, cv)))
            for t in range(v, 6):
                c = col(cur, t)
                S.set(ra, c, mul(S.get(s + K_GGFA + v, c), S.get(ro, cv)))
                if t > v:
                    S.set(ro, c, sub(S.get(ro, c - 1), S.get(ra, c)))
            ocol = col(ll2_int_col, v) if cur == LL2 else cv
            for t in range(v, 6):
                c = col(cur, t)
                if t == v:
                    S.set(ri, c, mul(S.get(s + K_EFF + v, c), S.get(ro, c)))
                else:
                    S.set(ri, c, mul(S.get(s + K_EFF + v, c), S.get(s + K_INTB + v, c), S.get(ro, ocol)))


def _new_debt(S, s, cur, t, k_from, k_fx, fx_shift=0):
    """SUM(<rows k_from .. k_from+t> in year t) * exchange rate: payments (or stock) on all vintages to date."""
    c = col(cur, t)
    return mul(xsum([S.get(s + k_from + v, c) for v in range(0, t + 1)]), S.get(s + k_fx, c + fx_shift))


def _baseline(S, ctx):
    s = 7
    base = ctx['base']
    B = lambda r: S.get(r, 2)
    look = lambda r, c: base(B(r), S.get(5, c))
    _labels(S, s, [(1, None), (2, 'GFN_GDP'), (4, None), (5, None), (7, None), (8, None), (9, None), (12, None),
                   (13, None), (14, None), (18, None), (19, None), (20, None), (23, None), (24, None), (25, None),
                   (28, None), (29, None), (30, None), (31, None), (32, None), (35, 'ISS_XD'), (36, 'ISS'),
                   (38, 'GGXWDG'), (39, 'GGXWDG_GDP'), (40, None), (41, None), (45, 'GGXWDGCL_F'),
                   (46, 'GGXWDGCF_F'), (53, None), (54, None), (55, None), (56, None), (58, None), (59, None),
                   (60, None), (61, None), (62, None), (67, None)])
    _years_col_e(S, s, ctx)
    loc = [col(LOC, t) for t in YEARS]

    # Exchange rates: foreign from BaseDB, index-linked ratios from the LLI series
    for r in (60, 62):
        for t in YEARS:
            S.set(r, col(FOR, t), look(r, col(FOR, t)))
            S.set(r, col(LL1, t), base(S.get(r, 21), S.get(5, col(LL1, t))))
            S.set(r, col(LL2, t), base(S.get(r, 29), S.get(5, col(LL2, t))))
        for t in YEARS:
            S.set(r + 1, col(FOR, t), look(r + 1, col(FOR, t)))
            for cur in (LL1, LL2):
                if t >= 0:
                    c = col(cur, t)
                    S.set(r + 1, c, calc(lambda a, b: (a / b) - 1, S.get(r, c), S.get(r, c - 1)))
    # Growth, deflator and GDP levels
    for c in loc:
        S.set(65, c, look(65, c))
        S.set(66, c, look(66, c))
    for r in (67, 68, 69):
        S.set(r, 6, look(r, 6))
    for c in loc[1:]:
        S.set(67, c, calc(lambda p, g: p * (1 + g), S.get(67, c - 1), S.get(65, c)))
        S.set(68, c, calc(lambda p, g: p * (1 + g), S.get(68, c - 1), S.get(66, c)))
        S.set(69, c, calc(lambda p, g, d: p * (1 + g) * (1 + d), S.get(69, c - 1), S.get(65, c), S.get(66, c)))

    # Fiscal paths from BaseDB
    for r in (11, 12, 14, 25, 35, 36, 37, 38, 39):
        for c in loc:
            S.set(r, c, look(r, c))
    for c in loc:
        for r in (15, 26):                                       # existing foreign currency, in local currency
            S.set(r, c, calc(lambda x, a, b: x / a * b, look(r, c), S.get(60, c + 8), S.get(60, c + 8)))
        for r, cur in ((17, LL1), (18, LL2), (28, LL1), (29, LL2)):   # existing index-linked
            S.set(r, c, calc(lambda x, a, b: x / a * b, look(r, c), S.get(60, col(cur, -1) + (c - 6)),
                             S.get(61, col(cur, -1) + (c - 6))))
        S.set(16, c, xsum([S.get(17, c), S.get(18, c)]))
        S.set(27, c, xsum([S.get(28, c), S.get(29, c)]))
    # Existing debt stocks
    for r in (47, 48, 49, 50, 51):
        S.set(r, 6, look(r, 6))
    for t in NEW:
        c = col(LOC, t)
        S.set(42, c, add(calc(lambda a, b: -(a + b), S.get(11, c), S.get(35, c)),
                         xsum([S.get(r, c) for r in (12, 14, 15, 16, 25, 26, 27, 36, 37, 38, 39)])))
        S.set(47, c, sub(S.get(47, c - 1), S.get(25, c)))
        for r, ra, cur in ((48, 26, FOR), (50, 28, LL1), (51, 29, LL2)):
            cc = col(cur, t)
            S.set(r, c, calc(lambda p, e0, a, x1, e1: (p / e0 - a / x1) * e1, S.get(r, c - 1), S.get(62, cc - 1),
                             S.get(ra, c), S.get(60, cc), S.get(62, cc)))
        S.set(49, c, xsum([S.get(50, c), S.get(51, c)]))

    # Debt issuance shares and the debt engine
    for cur, suffix in ((LOC, 'L'), (FOR, 'F'), (LL1, 'I1'), (LL2, 'I2')):
        for t in NEW:
            c = col(cur, t)
            S.set(73, c, base(calc_concat(B(73), suffix), S.get(5, c)))
            S.set(74, c, div(S.get(73, c), base(B(74), S.get(5, c))))
    fin = ctx['fin']
    _engine(S, ctx, s, 36, lambda v, cur, t: fin('EFF_IR', FIN_COL0 + t, S.get(s + K_EFF + v, 5), cur),
            ll2_int_col=LL1)

    # New debt: interest, amortization and stocks by currency
    for t in NEW:
        c = col(LOC, t)
        for r, cur in ((19, LOC), (20, FOR), (22, LL1), (23, LL2)):
            S.set(r, c, _new_debt(S, s, cur, t, K_INTP, K_ENDA))
        for r, cur in ((30, LOC), (31, FOR), (33, LL1), (34, LL2)):
            S.set(r, c, _new_debt(S, s, cur, t, K_AMTP, K_ENDA))
        for r, cur in ((52, LOC), (53, FOR), (55, LL1), (56, LL2)):
            S.set(r, c, _new_debt(S, s, cur, t, K_OUT, K_ENDE))
        S.set(21, c, xsum([S.get(22, c), S.get(23, c)]))
        S.set(32, c, xsum([S.get(33, c), S.get(34, c)]))
        S.set(54, c, xsum([S.get(55, c), S.get(56, c)]))
    # Gross financing need and total debt
    for c in loc:
        S.set(8, c, add(calc(lambda a, b: -(a + b), S.get(11, c), S.get(35, c)),
                        xsum([S.get(r, c) for r in (12, 14, 15, 16, 19, 20, 21, 25, 26, 27, 30, 31, 32, 36)])))
        S.set(9, c, div(S.get(8, c), S.get(69, c)))
        S.set(45, c, xsum([S.get(r, c) for r in (47, 48, 49, 52, 53, 54)]))
        S.set(46, c, div(S.get(45, c), S.get(69, c)))

    # Checks against BaseDB (AL:AR = year -1..5)
    for r in (8, 11, 12, 14, 15, 16, 19, 20, 25, 26, 30, 31, 35, 36, 37, 38, 39, 43, 47, 48, 49, 52, 53, 54,
              60, 61, 62, 63, 65, 66, 67, 68, 69):
        key = 'GADL' if r == 43 else B(r)
        src = 14 if r in (60, 61, 62, 63) else 6                 # N:T for exchange rates, else F:L
        for i, t in enumerate(YEARS):
            S.set(r, 38 + i, sub(base(key, S.get(5, 14 + i)), S.get(r, src + i)))


def _scenario(S, ctx, name, s):
    """One stress scenario block starting at row s: baseline paths (rows of the baseline block) plus STDesign
    shocks, then the same debt engine."""
    base, design = ctx['base'], ctx['design']
    k = lambda i: s + i
    B = lambda r: S.get(r, 2)
    sfx = S.get(s, 2)                                            # scenario suffix, e.g. '_ND'

    def shock(r, c, key_col=2):
        return design(calc_concat('SHK_', S.get(r, key_col), sfx), S.get(6, c))

    _labels(S, s, [(1, None), (3, 'GFN_GDP'), (5, None), (6, None), (8, None), (9, None), (10, None), (11, None),
                   (12, None), (13, None), (17, None), (18, None), (19, None), (22, None), (23, None), (24, None),
                   (27, None), (28, None), (29, None), (30, None), (31, None), (34, 'ISS_XD'), (35, 'ISS'),
                   (37, 'GGXWDG'), (39, 'GGXWDG_GDP'), (40, None), (41, None), (45, 'GGXWDGCL_F'),
                   (46, 'GGXWDGCF_F'), (53, None), (54, None), (55, None), (56, None), (58, None), (59, None),
                   (60, None), (61, None), (62, None), (67, None)])
    _years_col_e(S, s, ctx)
    loc = [col(LOC, t) for t in YEARS]

    # Exchange rates: depreciation = baseline + shock (index-linked series shocked with the inflation shock)
    for kr, kp, base_r in ((K_ENDA, K_ENDA_PCH, 60), (K_ENDE, K_ENDE_PCH, 62)):
        rl, rp = k(kr), k(kp)
        S.set(rp, 21, B(k(59)))                                  # U: 'NGDP_DPCH'
        for t in YEARS:
            c = col(FOR, t)
            S.set(rp, c, add(shock(rp, c), S.get(base_r + 1, c)))
        for cur in (LL1, LL2):
            for t in NEW:
                c = col(cur, t)
                S.set(rp, c, add(shock(rp, c, 21), S.get(base_r + 1, c)))
        S.set(rl, col(FOR, -1), base(B(rl), S.get(5, col(FOR, -1))))
        S.set(rl, col(LL1, -1), S.get(base_r, col(LL1, -1)))
        S.set(rl, col(LL2, -1), S.get(base_r, col(LL2, -1)))
        for cur in (FOR, LL1, LL2):
            for t in NEW:
                c = col(cur, t)
                S.set(rl, c, calc(lambda p, d: p * (1 + d), S.get(rl, c - 1), S.get(rp, c)))
    # Growth, deflator and GDP levels
    for c in loc:
        S.set(k(58), c, add(shock(k(58), c), S.get(65, c)))
        S.set(k(59), c, add(shock(k(59), c), S.get(66, c)))
    for i in (60, 61, 62):
        S.set(k(i), 6, base(B(k(i)), S.get(5, 6)))
    for c in loc[1:]:
        g, d = S.get(k(58), c), S.get(k(59), c)
        S.set(k(60), c, calc(lambda p, g: p * (1 + g), S.get(k(60), c - 1), g))
        S.set(k(61), c, calc(lambda p, d: p * (1 + d), S.get(k(61), c - 1), d))
        S.set(k(62), c, calc(lambda p, g, d: p * (1 + g) * (1 + d), S.get(k(62), c - 1), g, d))

    # Fiscal paths: baseline + shocks
    for c in loc:
        for i, base_r in ((5, 11), (6, 12), (27, 35), (28, 36), (29, 37), (30, 38), (31, 39)):
            S.set(k(i), c, add(shock(k(i), c), S.get(base_r, c)))
        S.set(k(8), c, S.get(14, c))                                     # existing local: as baseline
        S.set(k(17), c, S.get(25, c))
        fc = c + 8                                                       # foreign currency column
        S.set(k(9), c, calc(lambda x, a, b: x / a * b, S.get(15, c), S.get(60, fc), S.get(k(K_ENDA), fc)))
        S.set(k(18), c, calc(lambda x, a, b: x / a * b, S.get(26, c), S.get(60, fc), S.get(k(K_ENDA), fc)))
        S.set(k(10), c, calc(lambda x, a, b: x / a * b, base(B(k(10)), S.get(5, c)), S.get(60, fc),
                             S.get(k(K_ENDA_PCH), fc)))
    S.set(k(19), 6, calc(lambda x, a, b: x / a * b, base(B(k(19)), S.get(5, 6)), S.get(60, 14),
                         S.get(k(K_ENDA_PCH), 14)))
    for i in (20, 21):
        S.set(k(i), 6, calc(lambda x, a, b: x / a * b, base(B(k(i)), S.get(5, 6)), S.get(60, 14),
                            S.get(k(K_ENDA_PCH), 14)))
    for t in NEW:
        c = col(LOC, t)
        for i, cur in ((20, LL1), (21, LL2)):
            cc = col(cur, t)
            S.set(k(i), c, calc(lambda x, a, b: x / a * b, base(B(k(i)), S.get(5, c)), S.get(60, cc),
                                S.get(k(K_ENDA), cc)))
        S.set(k(19), c, xsum([S.get(k(20), c), S.get(k(21), c)]))
    # Existing debt stocks
    for i in (40, 41, 42, 43, 44):
        S.set(k(i), 6, base(B(k(i)), S.get(5, 6)))
    for t in NEW:
        c = col(LOC, t)
        S.set(k(34), c, add(calc(lambda a, b: -(a + b), S.get(k(5), c), S.get(k(27), c)),
                            xsum([S.get(k(i), c) for i in (6, 8, 9, 10, 17, 18, 19, 28, 29, 30, 31)])))
        S.set(k(40), c, sub(S.get(k(40), c - 1), S.get(k(17), c)))
        for i, ia, cur in ((41, 18, FOR), (43, 20, LL1), (44, 21, LL2)):
            cc = col(cur, t)
            S.set(k(i), c, calc(lambda p, e0, a, x1, e1: (p / e0 - a / x1) * e1, S.get(k(i), c - 1),
                                S.get(k(K_ENDE), cc - 1), S.get(k(ia), c), S.get(k(K_ENDA), cc),
                                S.get(k(K_ENDE), cc)))
        S.set(k(42), c, xsum([S.get(k(43), c), S.get(k(44), c)]))

    # Debt engine: issuance shares as in the baseline, effective rates = baseline + interest rate shock (bps)
    for cur in CURS:
        for t in NEW:
            c = col(cur, t)
            S.set(k(K_SHARE), c, S.get(74, c))
            S.set(k(K_FI), c, shock(k(K_FI), c))
    eff = lambda v, cur, t: add(div(S.get(k(K_FI), col(cur, v)), 100), S.get(78 + v, col(cur, t)))
    quirks = ('ll2_int_as_ll1', 'ab81') if name == 'ER' else ()
    _engine(S, ctx, s, 35, eff, quirks=quirks)

    # New debt: interest, amortization and stocks by currency
    for t in NEW:
        c = col(LOC, t)
        for i, cur in ((11, LOC), (12, FOR), (14, LL1), (15, LL2)):
            S.set(k(i), c, _new_debt(S, s, cur, t, K_INTP, K_ENDA))
        for i, cur in ((22, LOC), (23, FOR), (25, LL1), (26, LL2)):
            S.set(k(i), c, _new_debt(S, s, cur, t, K_AMTP, K_ENDA, fx_shift=-1 if cur == FOR else 0))
        for i, cur in ((45, LOC), (46, FOR), (48, LL1), (49, LL2)):
            S.set(k(i), c, _new_debt(S, s, cur, t, K_OUT, K_ENDE))
        S.set(k(13), c, xsum([S.get(k(14), c), S.get(k(15), c)]))
        S.set(k(24), c, xsum([S.get(k(25), c), S.get(k(26), c)]))
        S.set(k(47), c, xsum([S.get(k(48), c), S.get(k(49), c)]))
    # Gross financing need and total debt, and differences from the baseline
    for c in loc:
        S.set(k(1), c, add(calc(lambda a, b: -(a + b), S.get(k(5), c), S.get(k(27), c)),
                           xsum([S.get(k(i), c) for i in (6, 8, 9, 10, 11, 12, 13, 17, 18, 19, 22, 23, 24, 28)])))
        S.set(k(2), c, div(S.get(k(1), c), S.get(k(62), c)))
        S.set(k(3), c, sub(S.get(k(2), c), S.get(9, c)))
        S.set(k(37), c, xsum([S.get(k(i), c) for i in (40, 41, 42, 45, 46, 47)]))
        S.set(k(38), c, div(S.get(k(37), c), S.get(k(62), c)))
        S.set(k(39), c, sub(S.get(k(38), c), S.get(46, c)))
    for i, base_r in ((1, 8), (5, 11), (6, 12), (8, 14), (9, 15), (10, 16), (11, 19), (12, 20), (13, 21),
                      (17, 25), (18, 26), (19, 27), (22, 30), (23, 31), (24, 32), (27, 35), (28, 36), (29, 37),
                      (30, 38), (31, 39), (37, 45), (40, 47), (41, 48), (42, 49), (45, 52), (46, 53), (47, 54)):
        for j in range(7):
            S.set(k(i), 38 + j, sub(S.get(k(i), 6 + j), S.get(base_r, 6 + j)))
    # Checks: column I equal to the same row of another block
    if name in CHECK_REF:
        ref = CHECK_REF[name]
        for i in (92, 93, 94, 99, 100, 101, 106, 107, 108):
            S.set(k(i), 2, xeq(S.get(k(i), 9), S.get(ref + i, 9)))
