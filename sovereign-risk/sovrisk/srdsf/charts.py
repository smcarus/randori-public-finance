"""Charts sheet: the data behind every chart of the SRDSF output pages. Each block pulls a few series from the
model sheets (BaseDB, Macrofw, NewMacrofw, GFN, FAN, STOps, IdentFin/ResidFin, Signals, Questions) for a window of
years around the first projection year and shapes them for one chart:

  rows    6-20   debt-creating flows over ProjYr-10 .. ProjYr+10 (stacked bars, max/min bar heights, cumulative)
  rows   39-48   public debt by currency                     rows   67-76   public debt by holder
  rows   86-97   public debt by residual maturity            rows  109-116   public debt by governing law
  rows  130-142  marketable / nonmarketable debt             rows  148-158   debt-creating flows, 5-year sums
  rows  164-201  realism: 3-year debt reduction against the cross-country distribution (histogram, percentile)
  rows  207-263  realism: 3-year CAPB adjustment against the cross-country distribution
  rows  293-301  realism: forecast track record of real GDP growth, output gap
  rows  311-458  fiscal multiplier paths: growth impact of the fiscal adjustment for multipliers 0.5 / 1 / 1.5
  rows  465-487  bond spreads: new local-currency market issuance by maturity, inflation, Laubach (2009) rule
  rows  495-501  GFN (baseline vs GFN module)                rows  515-545  fanchart with stress-test paths
  rows  550-567  gross financing needs with stress tests     rows 3598-3603  medium-term index vs thresholds
  rows 3615-4533 cross-country comparison of the medium-term tool indices (rank, percentile by peer group)
  rows 4538-5541 missed-crisis / false-alarm probabilities for the MT index (ROC table) and the near-term LSP

The constant tables of the sheet (the cross-country distributions, ROC tables) are inputs and are only read.
"""
import math

from .book import ci
from .gfn import IF, _key, criterion, matches, rmax, rmin
from .residfin import AND, OR, Engine, X, cat, cmp, iferror, text, truth, val
from .xl import NA, VALUE, average, err, iserr, isnumber, match as _match, xround, xsum

SHEETS = ['Charts']

QUIRKS = [
    'Rows 42-44 (debt by currency) and 70-74 (debt by holder) take their BaseDB column from row 6 (the debt-flows '
    'block) instead of their own column-reference rows 39 / 67; the years are the same, so the values are too.',
    'Row 14 of the debt-flows legend (Y14/Z14) shows "Real interest rate and relative inflation" from row 18, '
    'not row 14; row 16 (relative inflation) has no legend entry.',
    'H470:M470 (local market issuance, 1-5 years): the ResidFin SUMIFS pair the ResidFin sum range with the '
    'criterion IdentFin!F:F "<=5" (row-aligned with the other sheet), not ResidFin!F:F; reproduced.',
    'Row 500 (GFN module line) looks up $A499 rather than its own $A500 (same code GFN_GDP); row 556 looks up '
    '$A555 (same code).',
    'Rows 390-404 (and 417-431, 444-458): the growth-impact triangle beyond column J multiplies by the #REF! '
    'constants left in K382:R382 (K409:R409, K436:R436), so those cells are "" via IFERROR; the multiplier row '
    'they point at is also shifted (row 329+k instead of 329+k-i). Only six years of adjustment enter the sums.',
    'E4538/F4538 use SWITCH on a TRUE/FALSE value with cases 0 and 1; SWITCH does not convert logicals to numbers, '
    'so the cases never match and the result is always the ROC-table lookup (the "above max / below min" '
    'branches are dead). In the sample the MT index is #N/A, so all are #N/A.',
    'B4538 reads column 10 of SignalsTable ("Transformed index") for SIG-MT and O4538 for SIG-NT: both #N/A in '
    'the sample, so the missed-crisis / false-alarm texts on Output are #N/A too.',
    'Array formulas: only the anchor cell of TRANSPOSE(...) (H318, H319, H320, C353) is a formula cell; the rest '
    'of each spilled range is stored as values in the template and is not recomputed here.',
    'C315:M315 fall back, when Macrofw has no CAPB, to the derived CAPB of row 222 sixteen columns to the right '
    '(S222 for C315), a different year.',
    'E169/E170 and E226/E227 (the "Row Number" of the country value in the histogram) are array formulas: '
    'the bin nearest to the value, or the last bin when the value is above the second-last bin edge.',
]

# --------------------------------------------------------------------------------------------------------------
# Excel helpers (shared with output.py)
# --------------------------------------------------------------------------------------------------------------


def cols(a, b):
    """Column range 'C'..'W' as indexes."""
    return range(ci(a), ci(b) + 1)


class Look:
    """VLOOKUP / HLOOKUP / MATCH over the workbook's named areas, with the areas and lookup indexes kept for one
    compute call only (make a new one per call)."""

    def __init__(self, book):
        self.book = book
        self._areas, self._idx, self._rows = {}, {}, {}

    def area(self, name):
        if name not in self._areas:
            self._areas[name] = self.book.area(name)
        return self._areas[name]

    def hrow(self, name):
        """The values of a one-row or one-column area (what MATCH searches)."""
        if name not in self._rows:
            sh, c0, r0, c1, r1 = self.area(name)
            S = self.book[sh]
            self._rows[name] = ([S.get(r, c0) for r in range(r0, r1 + 1)] if r1 > r0 and c1 == c0
                                else [S.get(r0, c) for c in range(c0, c1 + 1)])
        return self._rows[name]

    def match(self, x, name):
        """MATCH(x, area, 0)."""
        x = val(x)
        if iserr(x):
            return x
        if x is None:
            return NA
        return _match(x, self.hrow(name))

    def vlraw(self, key, name, col):
        """VLOOKUP(key, area, col, FALSE) returning a blank target as None (as a comparison sees it)."""
        key, col = val(key), val(col)
        e = err(key, col)
        if e:
            return e
        if isinstance(col, str):
            return VALUE
        sh, c0, r0, c1, r1 = self.area(name)
        col = int(num0(col))
        if col < 1:
            return VALUE
        if col > c1 - c0 + 1:
            return '#REF!'
        if name not in self._idx:
            S, idx = self.book[sh], {}
            for r in range(r0, r1 + 1):
                v = S.get(r, c0)
                if v is not None and not iserr(v):
                    idx.setdefault(_key(v), r)
            self._idx[name] = idx
        r = self._idx[name].get(_key(0 if key is None else key))
        return NA if r is None else self.book[sh].get(r, c0 + col - 1)

    def vl(self, key, name, col):
        """VLOOKUP as a cell shows it: a blank target reads 0."""
        v = self.vlraw(key, name, col)
        return 0 if v is None else v


def num0(v):
    if v is None:
        return 0
    return float(v) if isinstance(v, bool) else v


def own_lookup(e, r0, r1, c0):
    """VLOOKUP(key, <own-sheet area rows r0..r1 starting at column c0>, col, FALSE) on the sheet the Engine `e`
    fills: the key column is computed on first use and indexed for the rest of the call."""
    idx = {}

    def look(key, col):
        key = val(key)
        if iserr(key):
            return key
        if not idx:
            for r in range(r0, r1 + 1):
                v = e(r, c0)
                if v is not None and not iserr(v):
                    idx.setdefault(_key(v), r)
            idx['built'] = True
        r = idx.get(_key(0 if key is None else key))
        if r is None:
            return NA
        v = e(r, c0 + col - 1)
        return 0 if v is None else v
    return look


def roundup(v, d=0):
    """ROUNDUP: away from zero."""
    v = val(v)
    if iserr(v):
        return v
    if isinstance(v, str):
        return VALUE
    m = 10 ** d
    a = float(f'{abs(num0(v)) * m:.15g}')              # Excel works on 15 significant digits
    return math.copysign(math.ceil(a) / m, v)


def xround_(v, d=0):
    """ROUND with error / text propagation."""
    v = val(v)
    if iserr(v):
        return v
    if isinstance(v, str):
        return VALUE
    return xround(num0(v), d)


def xtext(v, fmt):
    """TEXT(v, fmt) for the number formats the sheets use: "0.000", "0.0" and "0.#"."""
    v = val(v)
    if iserr(v):
        return v
    if isinstance(v, str):
        return v
    v = num0(v)
    whole, dec = fmt.split('.')
    d = len(dec)
    r = xround(v, d)
    s = f'{r:.{d}f}'
    if '#' in dec:                                       # optional digits: drop trailing zeros, keep the point
        s = s.rstrip('0')
    return s


def lower(v):
    v = val(v)
    return v if iserr(v) else text(v).lower()


def mx0(v):
    """MAX(cell, 0): a referenced text or blank cell is ignored."""
    v = val(v)
    if iserr(v):
        return v
    return max(v, 0) if isnumber(v) else 0


def mn0(v):
    v = val(v)
    if iserr(v):
        return v
    return min(v, 0) if isnumber(v) else 0


def sumif(keys, crit, values):
    """SUMIF(keys, crit, values) over two aligned lists."""
    op, k = criterion(crit)
    t = 0.0
    for a, b in zip(keys, values):
        if matches(a, op, k):
            if iserr(b):
                return b
            if isnumber(b):
                t += b
    return t


def nearest_bin(c, bins, last):
    """IF(c > last edge, last row number, MATCH(MIN(ABS(bins - c)), ABS(bins - c), 0)) (array formula)."""
    t = truth(cmp(c, '>', bins[-1]))
    if iserr(t):
        return t
    if t:
        return last
    d = [val(abs_(X(b) - c)) for b in bins]
    e = err(*d)
    if e:
        return e
    return d.index(min(d)) + 1


def abs_(x):
    v = val(x)
    return v if iserr(v) else abs(v)


def xswitch(x, cases, default):
    """SWITCH(x, v1, r1, v2, r2, default): exact-type match (TRUE never equals 1); results are callables."""
    x = val(x)
    if iserr(x):
        return x
    for k, r in cases:
        if type(x) is type(k) or (isnumber(x) and isnumber(k)):
            if cmp(x, '=', k) is True:
                return r()
    return default()


def xnot(v):
    t = truth(v)
    return t if iserr(t) else (not t)


class Sumifs:
    """SUMIFS over whole columns of IdentFin / ResidFin. Each criterion names its own sheet, so a criterion range
    on another sheet (row-aligned) is possible, as H470:M470 do. Matching rows are kept for one compute call."""

    def __init__(self, book):
        self.book, self._rows = book, {}

    def __call__(self, sheet, col, crits):
        """crits: tuple of (sheet, column letters, criterion)."""
        e = err(*(k for _, _, k in crits))
        if e:
            return e
        key = (sheet, crits)
        if key not in self._rows:
            sheets = {sheet} | {s for s, _, _ in crits}
            maxr = max(max((r for r, _ in self.book[s].cells), default=0) for s in sheets)
            parsed = [(self.book[s], ci(c)) + criterion(k) for s, c, k in crits]
            self._rows[key] = [r for r in range(1, maxr + 1)
                               if all(matches(S.get(r, c), op, v) for S, c, op, v in parsed)]
        S = self.book[sheet]
        return xsum(S.get(r, col) for r in self._rows[key])


# --------------------------------------------------------------------------------------------------------------
# The sheet
# --------------------------------------------------------------------------------------------------------------

B, C, D, E, F, G, H = (ci(c) for c in 'BCDEFGH')
I, J, K, L, M, N, O = (ci(c) for c in 'IJKLMNO')
P, Q, R_, T, U, Y, Z = (ci(c) for c in 'PQRTUYZ')
A_ = 1
HIST_BLOCKS = [ci(c) for c in ('F', 'N', 'V', 'AD', 'AL', 'AT', 'BB', 'BJ', 'BR', 'BZ')]   # MT-tool comparisons


def compute(book, sheet='Charts'):
    e = Engine(book, sheet)
    x = e.x
    lk = Look(book)
    vl, mt = lk.vl, lk.match
    Qn = book.name
    proj = lambda: Qn('ProjYr')
    sig_act = lambda k: vl(k, 'SignalsTable', mt('Activated', 'SignalsHeaders'))

    def years(yr, cs):                                   # Years row: previous column + 1
        e.let(yr, cs, lambda c: x(yr, c - 1) + 1)

    def colref(row, yr, cs, dates):                      # Column ref row: MATCH(year, <dates>, 0)
        e.let(row, cs, lambda c: mt(e(yr, c), dates))

    def labels(row, yr, cs):                             # Horizontal labels: ProjYr + years
        e.let(row, cs, lambda c: X(proj()) + e(yr, c))

    def data(rows, cs, area, ref, scale=1, fallback=None):
        """Row r, column c: VLOOKUP($A r, area, <ref row> c, FALSE) [* scale] [IFERROR -> fallback]."""
        for r in rows:
            def f(c, r=r):
                v = vl(e(r, A_), area, e(ref, c))
                v = X(v) * scale if scale != 1 else v
                return v if fallback is None else iferror(v, lambda: fallback)
            e.let(r, cs, f)

    def rowvals(r, cs):
        return [e(r, c) for c in cs]

    # ---- Debt-creating flows, ProjYr-10 .. ProjYr+10 (rows 6-20) ---------------------------------------------
    CW = cols('C', 'W')
    colref(6, 7, CW, 'BaseDBdates')
    years(7, cols('D', 'W'))
    labels(8, 7, CW)
    data(range(9, 17), CW, 'BaseDBData', 6, 100, '')    # change in debt and its drivers (pct of GDP)
    for r, src in ((9, 9), (10, 10), (11, 11), (12, 12), (13, 13), (14, 18), (15, 15)):   # legend + cumulative
        e.let(r, Y, lambda c, src=src: e(src, B))
    for r, src in ((9, 9), (10, 10), (11, 11), (12, 12), (13, 13), (14, 18), (15, 15), (16, 16)):
        e.let(r, Z, lambda c, src=src: sumif(rowvals(7, CW), '>=0', rowvals(src, CW)))
    e.let(17, CW, lambda c: IF(cmp(e(7, c), '>=', 0),                   # projection shading
                               lambda: roundup(X(rmax(rowvals(19, CW))) + 2), lambda: NA))
    e.let(18, CW, lambda c: x(14, c) + e(16, c))                         # real interest rate + relative inflation
    e.let(19, CW, lambda c: sum_x(mx0(e(r, c)) for r in range(10, 16)))  # max / min bar heights
    e.let(20, CW, lambda c: sum_x(mn0(e(r, c)) for r in range(10, 16)))

    # ---- Public debt by currency (rows 39-48) ------------------------------------------------------------------
    colref(39, 40, CW, 'BaseDBdates')
    years(40, cols('D', 'W'))
    labels(41, 40, CW)
    data(range(42, 45), CW, 'BaseDBData', 6, 100, '')    # foreign, local, local-linked
    e.let(45, CW, lambda c: IF(cmp(e(40, c), '>=', 0),
                               lambda: roundup(X(rmax(rowvals(47, CW))) + 10), lambda: NA))
    e.let(47, CW, lambda c: X(mx0(e(43, c))) + mx0(e(42, c)))
    e.let(48, CW, lambda c: X(mn0(e(43, c))) + mn0(e(42, c)))

    # ---- Public debt by holder (rows 67-76) --------------------------------------------------------------------
    CL_ = cols('C', 'L')
    e.let(67, B, lambda c: mt('UNIT_OR_PERIMETER', 'NewMacrofwDates'))
    colref(67, 68, CL_, 'BaseDBdates')
    years(68, cols('D', 'L'))
    labels(69, 68, CL_)
    data(range(70, 75), CL_, 'BaseDBData', 6, 100, '')
    e.let(76, C, lambda c: cat(lower(vl(e(76, A_), 'NewMacrofwData', e(67, B))), '.'))   # perimeter note

    # ---- Public debt by residual maturity (rows 86-97) ---------------------------------------------------------
    CM = cols('C', 'M')
    e.let(86, B, lambda c: mt('UNIT_OR_PERIMETER', 'NewMacrofwDates'))
    colref(86, 87, CM, 'BaseDBdates')
    years(87, cols('E', 'M'))
    labels(88, 87, CM)
    data(range(89, 92), CM, 'BaseDBData', 86, 100)        # <=1 year, 1-5 years, >5 years
    e.let(92, CM, lambda c: IF(cmp(e(87, c), '>=', 0),
                               lambda: roundup(X(rmax(rowvals(94, CM))) + 2), lambda: NA))
    e.let(94, CM, lambda c: xsum(e(r, c) for r in range(89, 92)))
    e.let(96, C, lambda c: cat(lower(vl(e(96, A_), 'NewMacrofwData', e(86, B))), '.'))
    e.let(97, C, lambda c: cat('Residual maturity: ', xtext(Qn('ChartMaturityYears'), '0.#'), ' years'))

    # ---- Public debt by governing law, last historical year (rows 109-116) ------------------------------------
    e.let(109, B, lambda c: cat('Public debt by governing law, ', X(proj()) - 1))
    e.let(111, C, lambda c: mt(-1, 'NewMacrofwDates'))
    data(range(112, 115), [C], 'NewMacrofwData', 111)      # domestic law, foreign law, multilateral
    unit_col = lambda: mt('UNIT_OR_PERIMETER', 'NewMacrofwDates')
    e.let(116, C, lambda c: cat(lower(vl(e(116, A_), 'NewMacrofwData', unit_col())), '.'))

    # ---- Marketable / nonmarketable debt (rows 130-142) --------------------------------------------------------
    colref(130, 131, CM, 'BaseDBdates')
    years(131, cols('E', 'M'))
    labels(132, 131, CM)
    data(range(133, 135), CM, 'BaseDBData', 130, 100)
    tot_max = lambda: rmax(rowvals(136, CM))
    e.let(135, cols('C', 'G'), lambda c: IF(cmp(e(131, c), '>=', 0), lambda: roundup(X(tot_max()) + 2), lambda: NA))
    e.let(135, cols('H', 'M'), lambda c: IF(cmp(e(131, c), '>=', 0), lambda: roundup(X(tot_max()) + 10), lambda: NA))
    e.let(136, CM, lambda c: x(133, c) + e(134, c))
    e.let(138, cols('G', 'M'), lambda c: x(134, c) / e(136, c) * 100)  # nonmarketable share of total
    e.let(139, C, lambda c: cat(lower(vl(e(139, A_), 'NewMacrofwData', unit_col())), '.'))
    e.let(142, CM, lambda c: vl(e(142, A_), 'BaseDBData', mt(e(131, c), 'BaseDBdates')))   # exchange rate

    # ---- Debt-creating flows, ProjYr-5 .. ProjYr+5 and 5-year sums (rows 148-158) ------------------------------
    colref(148, 149, CM, 'BaseDBdates')
    years(149, cols('D', 'M'))
    labels(150, 149, CM)
    data([151, 152, 153, 154, 155, 157, 158], CM, 'BaseDBData', 148, 100, '')
    e.let(156, CM, lambda c: iferror(X(vl(e(156, A_), 'BaseDBData', e(148, c))) * 100 + e(158, c), lambda: ''))
    hsum = lambda r, a, b: xsum(rowvals(r, cols(a, b)))
    for r, src in ((151, 151), (153, 154), (154, 155), (155, 156), (156, 157)):
        e.let(r, P, lambda c, src=src: e(src, B))
        e.let(r, Q, lambda c, src=src: hsum(src, 'C', 'G'))          # history
        e.let(r, R_, lambda c, src=src: hsum(src, 'H', 'M'))         # projection
    e.let(152, Q, lambda c: X(hsum(152, 'C', 'G')) + hsum(153, 'C', 'G'))   # residual + other flows
    e.let(152, R_, lambda c: X(hsum(152, 'H', 'M')) + hsum(153, 'H', 'M'))

    # ---- Realism: 3-year debt reduction vs cross-country distribution (rows 164-201) --------------------------
    CS = cols('C', 'S')
    colref(164, 165, CS, 'BaseDBdates')
    years(165, cols('D', 'S'))
    labels(166, 165, CS)
    data([167], CS, 'BaseDBData', 164, 100, '')
    e.let(168, cols('F', 'S'), lambda c: x(167, c - 3) - e(167, c))   # 3-year reduction
    e.let(169, C, lambda c: -(x(167, P) - e(167, M)))                 # projected 3-year reduction
    e.let(170, C, lambda c: rmax(rowvals(168, CM)))                   # largest historical reduction
    histogram(e, x, 169, 170, 172, 201, with_cum=True)

    # ---- Realism: 3-year CAPB adjustment (rows 207-263) --------------------------------------------------------
    CAC = cols('C', 'AC')
    colref(207, 208, CAC, 'MacrofwDates')
    years(208, cols('D', 'AC'))
    labels(209, 208, CAC)
    data([210, 211, 212, 215, 216, 217, 218], CAC, 'MacrofwData', 207, 1, '')
    e.let(213, CAC, lambda c: x(211, c) - e(212, c))                 # primary balance
    e.let(214, CAC, lambda c: x(213, c) * 100 / e(215, c))           # primary balance to GDP
    e.let(219, CAC, lambda c: (x(217, c) / e(218, c) - 1) * 100)     # output gap
    e.let(222, CAC, lambda c: x(214, c) - x(216, c) * e(219, c) / 100)   # derived CAPB

    def capb_change(c):                                              # 3-year change: CAPB, else derived CAPB
        def inner():
            return IF(OR(cmp(e(210, c), '=', ''), cmp(e(210, c - 3), '=', '')),
                      lambda: x(222, c) - e(222, c - 3), lambda: x(210, c) - e(210, c - 3))
        v = val(inner())
        return '' if iserr(v) else v
    e.let(224, cols('F', 'AC'), capb_change)
    e.let(226, C, lambda c: e(224, Z))                               # change as of the projection year
    e.let(227, C, lambda c: rmax(rowvals(224, cols('F', 'W'))))       # largest historical change
    histogram(e, x, 226, 227, 232, 263, with_cum=False)

    # ---- Realism: forecast track record (rows 293-301) ---------------------------------------------------------
    CT = cols('C', 'T')
    colref(293, 294, CT, 'MacrofwDates')
    years(294, cols('D', 'T'))
    labels(295, 294, CT)
    data(range(296, 299), CT, 'MacrofwData', 293, 1, '')
    e.let(299, CT, lambda c: ((x(297, c) / e(298, c)) - 1) * 100)     # output gap
    e.let(300, cols('D', 'T'), lambda c: (x(298, c) / e(298, c - 1) - 1) * 100)   # potential growth
    e.let(301, cols('D', 'T'), lambda c: average(rowvals(296, cols('E', 'N'))))

    # ---- Fiscal adjustment and growth paths for three multipliers (rows 311-458) ------------------------------
    colref(311, 312, CM, 'MacrofwDates')
    years(312, cols('D', 'M'))
    labels(313, 312, CM)
    data([314], CM, 'MacrofwData', 311, 1, '')                        # real GDP growth
    e.let(315, CM, lambda c: iferror(vl(e(315, A_), 'MacrofwData', e(311, c)), lambda: e(222, c + 16)))   # CAPB
    e.let(316, cols('H', 'M'), lambda c: x(315, c) - e(315, c - 1))   # fiscal adjustment
    for r, mc in ((318, E), (319, F), (320, G)):
        e.let(r, B, lambda c, mc=mc: cat('Multiplier = ', e(323, mc)))
        e.let(r, G, lambda c: e(314, G))
        e.let(r, H, lambda c, mc=mc: e(358, mc + 6))                  # TRANSPOSE(K358:K363) anchor
    e.let(321, H, lambda c: X(roundup(X(rmax(rowvals(314, CM) + [e(r, cc) for r in (318, 319, 320) for cc in CM]))
                                      / 3)) * 3 - 0.01)               # chart axis max / min
    e.let(321, cols('I', 'M'), lambda c: e(321, H))
    e.let(322, H, lambda c: X(-9) + 0.01)
    e.let(322, cols('I', 'M'), lambda c: e(322, H))
    e.let(324, G, lambda c: e(324, E))
    e.let(328, B, lambda c: x(329, B) - 1)
    e.let(328, C, lambda c: x(329, C) - 1)
    e.let(329, B, lambda c: e(313, H))
    e.let(329, cols('E', 'G'), lambda c: impact(x, 329, c))
    for r in range(330, 350):                                          # growth impact decaying with persistence p
        e.let(r, B, lambda c, r=r: x(r - 1, B) + 1)
        e.let(r, C, lambda c, r=r: x(r - 1, C) + 1)
        e.let(r, cols('E', 'G'), lambda c, r=r: impact(x, r, c))
    e.let(352, cols('E', 'G'), lambda c: cat('Multiplier = ', e(323, c)))
    e.let(352, cols('K', 'M'), lambda c: cat('Multiplier = ', e(323, c - 6)))
    e.let(353, C, lambda c: e(314, C))                                 # TRANSPOSE(C314:M314) anchor
    for r in range(353, 358):
        e.let(r, B, lambda c, r=r: x(r + 1, B) - 1)
    e.let(358, B, lambda c: e(313, H))
    for r in range(359, 377):
        e.let(r, B, lambda c, r=r: x(r - 1, B) + 1)
    for r in range(353, 377):
        e.let(r, I, lambda c, r=r: e(r, B))
    e.let(357, J, lambda c: e(301, E))                                 # potential growth (average)
    e.let(357, cols('K', 'M'), lambda c: e(357, J))
    for r in range(358, 377):
        k = r - 358
        e.let(r, E, lambda c, k=k: e(384 + k, T))                      # impact by multiplier
        e.let(r, F, lambda c, k=k: e(411 + k, T))
        e.let(r, G, lambda c, k=k: e(438 + k, T))
        e.let(r, J, lambda c, r=r: e(r - 1, J))
        e.let(r, cols('K', 'M'), lambda c, r=r: x(r, J) + e(r, c - 6))  # growth path = potential + impact
    for base, mc in ((381, E), (408, F), (435, G)):
        multiplier_block(e, x, base, mc)

    # ---- Bond spreads: issuance by maturity, inflation, Laubach rule (rows 465-487) --------------------------
    colref(465, 467, CM, 'MacrofwDates')
    colref(466, 467, CM, 'NewMacrofwDates')
    years(467, cols('D', 'M'))
    labels(468, 467, CM)
    CG_, HM = cols('C', 'G'), cols('H', 'M')
    for r in range(469, 472):                                         # history: NewMacrofw, pct of GDP
        e.let(r, CG_, lambda c, r=r: X(vl(e(r, A_), 'NewMacrofwData', e(466, c))) * 100 / e(473, c))
    sumifs = Sumifs(book)
    terms = {469: [('F', '=1')], 470: [('F', '>1'), ('F', '<=5')], 471: [('F', '>5')]}
    for r, fcrit in terms.items():                                    # projection: local market issuance
        e.let(r, HM, lambda c, r=r, fcrit=fcrit: issuance(e, x, sumifs, r, c, fcrit))
    data(range(473, 477), CM, 'MacrofwData', 465)                     # NGDP, ENDE, LLIE1, LLIE2
    e.let(477, CG_, lambda c: book['Questions'].get(48, c))
    e.let(477, HM, lambda c: IF(cmp(e(470, O), '=', 'All'), lambda: bdb_mix(book, c + 11),
                                lambda: X(book['BaseDB'].get(281, c + 11)) * 100))
    e.let(478, CM, lambda c: vl(e(478, A_), 'MacrofwData', mt(e(467, c), 'MacrofwDates')))
    data([479], CM, 'MacrofwData', 465)
    e.let(480, CM, lambda c: (x(477, c) - e(478, c)) / 100)           # spreads
    e.let(482, HM, lambda c: e(468, c))
    for r in range(483, 486):
        e.let(r, G, lambda c, r=r: average(rowvals(r - 14, CG_)))
        e.let(r, HM, lambda c, r=r: e(r - 14, c))
    e.let(486, G, lambda c: average(rowvals(480, CG_)))
    e.let(486, HM, lambda c: (x(477, c) - e(478, c)) / 100)
    e.let(487, HM, lambda c: (x(479, c) - e(479, G)) * 0.04 / 100 + e(480, G))   # Laubach rule

    # ---- GFN: baseline vs GFN module (rows 495-501) ------------------------------------------------------------
    colref(495, 497, CM, 'BaseDBdates')
    colref(496, 497, HM, 'GFNDates')
    labels(498, 497, CM)
    e.let(499, CM, lambda c: X(vl(e(499, A_), 'BaseDBData', e(495, c))) * 100)
    e.let(500, HM, lambda c: X(iferror(vl(e(499, A_), 'GFNData', e(496, c)), lambda: NA)) * 100)
    e.let(501, HM, lambda c: X(iferror(vl(e(501, A_), 'GFNData', e(496, c)), lambda: NA)) * 100)

    # ---- Fanchart with stress-test paths (rows 515-545) --------------------------------------------------------
    years(516, cols('D', 'M'))
    years(517, cols('D', 'G'))
    colref(518, 516, CM, 'BaseDBdates')
    colref(519, 517, CM, 'FanDates')
    colref(520, 516, cols('G', 'M'), 'STOpsDates')
    labels(521, 516, CM)
    e.let(522, CM, lambda c: X(vl(e(522, A_), 'BaseDBData', e(518, c))) * 100)   # baseline debt
    data(range(523, 528), HM, 'FanDataOut', 519, 100)                  # fan percentiles
    e.let(533, CM, lambda c: e(521, c))
    e.let(534, CG_, lambda c: e(522, c))                               # actual
    e.let(535, G, lambda c: e(534, G))
    e.let(535, HM, lambda c: e(522, c))                                # baseline
    e.let(536, CG_, lambda c: e(534, c))
    e.let(536, HM, lambda c: e(523, c))                                # stacked bands: 0-5, then widths
    for r in range(537, 540):
        e.let(r, HM, lambda c, r=r: x(r - 13, c) - e(r - 14, c))
    e.let(540, G, lambda c: e(539, G))
    e.let(540, HM, lambda c: x(527, c) - e(526, c))
    for r, k in ((541, 'ST-BC'), (542, 'ST-CP'), (543, 'ST-CL'), (544, 'ST-ER'), (545, 'ST-ND')):
        e.let(r, O, lambda c, k=k: sig_act(k))                         # activated?
        if r < 545:
            e.let(r, G, lambda c: e(534, G))
        e.let(r, cols('G' if r == 545 else 'H', 'M'), lambda c, r=r: X(IF(
            e(r, O), lambda: X(vl(e(r, A_), 'STOpsData', e(520, c))) * 100, lambda: NA)) + e(535, c))

    # ---- Gross financing needs with stress tests (rows 550-567) ------------------------------------------------
    years(550, cols('D', 'M'))
    colref(551, 550, CM, 'BaseDBdates')
    colref(552, 550, CM, 'GFNDates')
    colref(553, 550, CM, 'STOpsDates')
    labels(554, 550, CM)
    e.let(555, CG_, lambda c: X(vl(e(555, A_), 'BaseDBData', e(551, c))) * 100)
    e.let(556, cols('G', 'M'), lambda c: X(vl(e(555, A_), 'BaseDBData', e(551, c))) * 100)
    e.let(557, G, lambda c: e(556, G))
    e.let(557, HM, lambda c: X(vl(e(557, A_), 'GFNData', e(552, c))) * 100)
    for r, k in ((558, 'ST-BC'), (559, 'ST-CP'), (560, 'ST-CL'), (561, 'ST-ER'), (562, 'ST-ND')):
        e.let(r, O, lambda c, k=k: sig_act(k))
        e.let(r, G, lambda c: e(555, G))
        e.let(r, HM, lambda c, r=r: X(IF(e(r, O), lambda: vl(e(r, A_), 'STOpsData', e(553, c)), lambda: NA)) * 100
              + e(556, c))
    e.let(563, HM, lambda c: IF(cmp(e(550, c), '>=', Qn('GFNshockyr')),
                                lambda: (x(565, c) - e(566, c)) / e(567, c) * 100, lambda: 0))
    e.let(565, HM, lambda c: vl(e(565, A_), 'GFNData', e(552, c)))
    e.let(566, HM, lambda c: vl(e(566, A_), 'BaseDBData', e(551, c)))
    e.let(567, HM, lambda c: vl(e(567, A_), 'GFNData', e(552, c)))

    # ---- Medium-term index against the risk thresholds (rows 3598-3603) ----------------------------------------
    CF = cols('C', 'F')
    colref(3598, 3599, CF, 'MacrofwDates')
    labels(3600, 3599, CF)

    def mti(c):
        v = vl(e(3601, A_), 'MacrofwData', e(3598, c))
        return v if isnumber(v) else NA
    e.let(3601, cols('C', 'E'), mti)
    e.let(3601, F, lambda c: book['Signals'].get(5, J))
    e.let(3602, CF, lambda c: book['Config']['CX4'])                  # low / high risk thresholds
    e.let(3603, CF, lambda c: book['Config']['CX5'])

    # ---- Cross-country comparison of the MT tool indices (rows 3615-4533) ---------------------------------------
    e.let(3618, B, lambda c: Qn('AEEM'))
    e.let(3619, B, lambda c: IF(cmp(Qn('Engagement'), '=', 'Surveillance'), 'Surveillance', 'Program'))
    e.let(3620, B, lambda c: isnumber(mt(Qn('IFScode'), 'STCommCtrys')))   # commodity exporter?
    e.let(3622, A_, lambda c: cat(IF(cmp(e(3618, B), '=', 'AE'), 'AEs',
                                     lambda: cat('EMs', '-', IF(e(3620, B), 'Comm', 'NoComm'))),
                                  '-', IF(cmp(e(3619, B), '=', 'Program'), 'Prgm', 'NoPrgm')))
    group = own_lookup(e, 3624, 3633, A_)
    e.let(3622, B, lambda c: group(e(3622, A_), 2))                     # peer-group number
    fan = lambda k: vl(k, 'FanSumTab', mt('Raw value', 'FanSumHeader'))
    gfn = lambda k: vl(k, 'GFNSumTab', mt('Value', 'GFNSumHeader'))
    for c0 in HIST_BLOCKS:
        bc = range(c0, c0 + 6)
        e.let(3617, bc, lambda c: cat(e(3615, c), '-', e(3616, c)))
        e.let(3618, bc, lambda c: rank(e(3623, c), [e(r, c) for r in range(3623, 4534)]))
        e.let(3619, bc, lambda c: sum(1 for r in range(3623, 4534) if isnumber(e(r, c))))
        e.let(3620, bc, lambda c: xround_(x(3618, c) / e(3619, c) * 100, 0))   # percentile
        e.let(3623, c0, lambda c: X(fan(e(3615, c))) * 100)             # debt fanchart width
        e.let(3623, c0 + 1, lambda c: fan(e(3615, c)))                  # probability of debt not stabilizing
        e.let(3623, c0 + 2, lambda c: X(fan(e(3615, c))) * 100)         # terminal debt level
        e.let(3623, range(c0 + 3, c0 + 6), lambda c: X(gfn(e(3615, c))) * 100)   # GFN indices

    # ---- Missed-crisis / false-alarm probabilities (rows 4538-5541) --------------------------------------------
    BR = range(4541, 4641)                                              # ROC table of the MT index
    e.let(4538, B, lambda c: xround_(vl('SIG-MT', 'SignalsTable', 10), 3))
    e.let(4538, C, lambda c: cmp(e(4538, B), '>', rmax([e(r, B) for r in BR])))   # above max / below min
    e.let(4538, D, lambda c: cmp(e(4538, B), '<', rmin([e(r, B) for r in BR])))
    roc = own_lookup(e, 4541, 5314, G)
    both = lambda: xnot(AND(e(4538, C), e(4538, D)))
    e.let(4538, E, lambda c: xswitch(e(4538, C), [(0, lambda: e(4538, D)), (1, both)],
                                     lambda: roc(e(4538, B), 5)))      # false positive rate
    e.let(4538, F, lambda c: xswitch(e(4538, C), [(1, lambda: e(4538, D)), (0, both)],
                                     lambda: roc(e(4538, B), 6)))      # missed crisis rate
    e.let(4538, O, lambda c: xround_(vl('SIG-NT', 'SignalsTable', 10), 3))
    e.let(4538, P, lambda c: xtext(e(4538, O), '0.000'))
    lsp = own_lookup(e, 4541, 5539, N)
    e.let(4538, Q, lambda c: lsp(e(4538, P), 3))                       # false alarm
    e.let(4538, R_, lambda c: lsp(e(4538, P), 4))                      # missed crisis
    for r in BR:
        e.let(r, A_, lambda c, r=r: xround_(e(r, B), 3))
        e.let(r, E, lambda c, r=r: 1 - x(r, D))
    cut = own_lookup(e, 4541, 4640, A_)
    for r in range(4541, 5315):                                        # cut points 0.816 down by 0.001
        if r > 4541:
            e.let(r, G, lambda c, r=r: xround_(x(r - 1, G) - 0.001, 3))
        e.let(r, H, lambda c, r=r: cut(e(r, G), 2))
        e.let(r, I, lambda c, r=r: cut(e(r, G), 3))
        e.let(r, J, lambda c, r=r: cut(e(r, G), 5))
        if r == 4541:
            e.let(r, K, lambda c, r=r: e(r, I))
            e.let(r, L, lambda c, r=r: e(r, J))
        else:                                                          # interpolate: carry the last value
            e.let(r, K, lambda c, r=r: iferror(e(r, I), lambda: e(r - 1, K)))
            e.let(r, L, lambda c, r=r: iferror(e(r, J), lambda: e(r - 1, L)))
    for r in range(4541, 5542):                                        # LSP grid 0.000 .. 1.000 as text keys
        if r > 4541:
            e.let(r, O, lambda c, r=r: x(r - 1, O) + 0.001)
        e.let(r, N, lambda c, r=r: xtext(e(r, O), '0.000'))

    e.run()


def sum_x(vals):
    """a + b + ...: errors propagate."""
    t = X(0)
    for v in vals:
        t = t + v
    return t


def rank(v, values):
    """RANK(v, range, 1): 1 + count of numbers below v; #N/A when v is not in the range."""
    v = val(v)
    if iserr(v):
        return v
    if not isnumber(v):
        return VALUE
    nums = [w for w in values if isnumber(w)]
    if v not in nums:
        return NA
    return 1 + sum(1 for w in nums if w < v)


def histogram(e, x, r_val, r_max, r0, r1, with_cum):
    """Realism histogram: where the projected value (row r_val) and the historical maximum (row r_max) fall in
    the cross-country distribution (bins in B r0:r1, percent of sample in D, row numbers in G)."""
    bins = lambda: [e(r, B) for r in range(r0, r1)]
    look = own_lookup(e, r0, r1, G)
    for rr in (r_val, r_max):
        e.let(rr, E, lambda c, rr=rr: nearest_bin(e(rr, C), bins(), e(r1, G)))
    for rr in ((r_val,) if with_cum else (r_val, r_max)):             # percentile (no max cell in 164-201)
        e.let(rr, I, lambda c, rr=rr: look(e(rr, E), 2))
    for r in range(r0, r1 + 1):
        e.let(r, E, lambda c, r=r: IF(cmp(e(r, G), '=', e(r_val, E)), lambda: e(r, D), lambda: NA))
        e.let(r, F, lambda c, r=r: IF(cmp(e(r, G), '=', e(r_max, E)), lambda: e(r, D), lambda: NA))
        if with_cum:
            e.let(r, H, lambda c, r=r: xsum(e(k, D) for k in range(r0, r + 1)))


def impact(x, r, c):
    """-m * p ^ t: growth impact of a 1 pp fiscal adjustment t years on (multiplier m, persistence p)."""
    return -x(323, c) * (x(324, c) ** x(r, C))


def multiplier_block(e, x, base, mc):
    """Growth impact of the fiscal adjustment path for one multiplier (column mc of rows 329-349): each year's
    adjustment (row base+1) times the impact profile, summed by year in column T."""
    e.let(base - 2, B, lambda c: e(352, mc))
    e.let(base, D, lambda c: x(base, E) - 1)
    e.let(base, E, lambda c: e(313, H))
    e.let(base, cols('F', 'R'), lambda c: x(base, c - 1) + 1)
    e.let(base + 1, cols('E', 'J'), lambda c: e(316, c + 3))           # adjustment in year i
    e.let(base + 2, C, lambda c: x(base + 3, C) - 1)
    e.let(base + 2, U, lambda c: e(base + 2, C))
    for k in range(21):
        r = base + 3 + k
        if k == 0:
            e.let(r, C, lambda c: e(313, H))
        else:
            e.let(r, C, lambda c, r=r: x(r - 1, C) + 1)
        e.let(r, U, lambda c, r=r: e(r, C))
        for i in range(min(k, 13) + 1):
            ref = 329 + (k - i if i < 6 else k)                        # beyond J the template keeps row 329+k
            e.let(r, E + i, lambda c, r=r, ref=ref: iferror(x(base + 1, c) * e(ref, mc), lambda: ''))
        e.let(r, T, lambda c, r=r: xsum(e(r, cc) for cc in cols('E', 'R')))


def issuance(e, x, sumifs, r, c, fcrit):
    """New local-law market debt of one maturity bucket issued in year c (IdentFin + ResidFin), converted to
    local currency and taken in percent of GDP."""
    yc = c + 13                                                        # IdentFin/ResidFin year column (H -> U)
    year = e(468, c)

    def s(cur):
        def one(sheet):
            crits = [(sheet, 'Q', '=GGD'), (sheet, 'G', cat('=', year)), (sheet, 'K', '=' + cur),
                     (sheet, 'L', '=Market')]
            for i, (col, k) in enumerate(fcrit):
                # quirk: in the 1-5 year bucket the ResidFin "<=5" criterion range is IdentFin!F:F
                fs = 'IdentFin' if (sheet == 'ResidFin' and i == 1) else sheet
                crits.append((fs, col, k))
            return sumifs(sheet, yc, tuple(crits))
        return X(one('IdentFin')) + one('ResidFin')
    total = (s('Local') + s('Foreign') * e(474, c) + s('Local-Linked 1') * e(475, c)
             + s('Local-Linked 2') * e(476, c))
    return total / e(473, c) * 100


def bdb_mix(book, c):
    S = book['BaseDB']
    g = lambda r: X(S.get(r, c))
    return g(280) * g(263) * 100 + g(281) * g(264) * 100
