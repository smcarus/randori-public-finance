"""GFN sheet: the gross financing needs (GFN) financeability module.

The sheet builds a two-year stress scenario on top of the baseline (growth, exchange-rate, deflator and interest-rate
shocks, a shift to short-term debt), works out the stressed gross financing need and how it is financed by each
creditor group, and tracks bank claims on the government in percent of banking-system assets. The top block turns
the baseline GFN/GDP ratio, initial bank claims and the largest stress increase in bank claims into the GFN
financeability index and its Low/Moderate/High signal.

New market debt issued in the scenario is costed on the hidden Triangles sheet (triangles.py), which reads back
the financing this sheet hands over through Config!GFNConvergeOut. The workbook closes that loop with the
`converge` macro (ModGFN.bas), ported here as simulate(book).

Shared Excel helpers used by triangles.py and charts.py (criteria matching, SUMIFS/COUNTIF, comparisons, number-to-text) live
here too.
"""
import math
import re
import struct

from .xl import NA, VALUE, average, calc, err, isnumber, iserr, match, num

SHEETS = ['GFN']

QUIRKS = [
    'Rows 18-23 (change in bank claims relative to each year): the first column of every row looks one column to '
    'the right (I18 = J265-J265, ...), so each row starts with a zero and the comparison is shifted by one year.',
    'Rows 226 and 246 (pre-existing non-bank / other domestic holdings) add only the local- and foreign-currency '
    'lines (227+228, 247+248) and leave out the local-linked line (229, 249).',
    'Rows 230 and 250 (new non-bank / other domestic holdings) add only local and foreign currency (231+235, '
    '251+255) and leave out the local-linked block (239, 259).',
    'Rows 232-241 and 252-261 sum IdentFin column EW.. (offset +143) but ResidFin column EA.. (offset +121) for '
    'the same quantity.',
    'Row 194 converts foreign-currency stress issuance with the end-of-period exchange rate (row 51) in J:O but '
    'with the period-average rate (row 50) from P on; rows 238/258 use row 50 throughout.',
    'Row 148 (By source) repeats row 166 from column K only; J148 is left blank.',
    'Rows 159-161 use the ProjYr-1 holder shares ($I$32) for J:O and the year\'s own column from P on.',
    'K9 compares the index with thresholds and falls through to #N/A only when the index is itself an error.',
    'Q13/U13 add the non-bank assets/claims under the mitigator option by MATCHing "Claims on GG:" / '
    '"Total Assets:" in the one-row GFNNoBank range and taking the next cell.',
    'converge macro: it reads GFNConvergeChk into a VBA Single, so when the check is an Excel error (as in the '
    'template\'s sample state, where GFNinCU is #N/A) the macro stops with a type-mismatch error after clearing '
    'GFNConvergeOut. simulate() raises MacroError at the same point. The check is SUM of signed differences, so '
    'gaps of opposite sign can cancel.',
]

YRS = range(10, 26)            # J..Y: years ProjYr+0 .. ProjYr+15
ALL = range(9, 26)             # I..Y: from ProjYr-1


# ---------------------------------------------------------------------------------------------------------------
# Excel helpers shared with triangles.py and charts.py
# ---------------------------------------------------------------------------------------------------------------

def ref(v):
    """A plain reference to a cell: blank reads as 0."""
    return 0 if v is None else v


def txt(v):
    """Value as the & operator turns it into text."""
    if v is None:
        return ''
    if isinstance(v, bool):
        return 'TRUE' if v else 'FALSE'
    if isinstance(v, (int, float)):
        if float(v).is_integer():
            return str(int(v))
        return format(v, '.15g')
    return v


def cat(*vals):
    """A & B & ...: the first error wins."""
    e = err(*vals)
    return e if e else ''.join(txt(v) for v in vals)


def cmp(a, op, b):
    """Excel comparison operators. Errors propagate; blank is 0 or "" as the other side needs; numbers < text <
    logicals; text compares case-insensitively."""
    e = err(a, b)
    if e:
        return e
    if a is None:
        a = '' if isinstance(b, str) else 0
    if b is None:
        b = '' if isinstance(a, str) else 0
    rank = lambda v: 2 if isinstance(v, bool) else 1 if isinstance(v, str) else 0
    ra, rb = rank(a), rank(b)
    if ra != rb:
        a, b = ra, rb
    elif ra == 1:
        a, b = a.lower(), b.lower()
    return {'=': a == b, '<>': a != b, '<': a < b, '<=': a <= b, '>': a > b, '>=': a >= b}[op]


def truth(v):
    """IF/AND/OR condition: error passes through, number nonzero is TRUE, text is #VALUE!."""
    if iserr(v):
        return v
    if isinstance(v, str):
        return VALUE
    return bool(num(v))


def IF(c, a, b):
    """IF(c, a(), b()): only the chosen branch is evaluated (a and b are callables or values)."""
    t = truth(c)
    if iserr(t):
        return t
    x = a if t else b
    return x() if callable(x) else x


def AND(*cs):
    ts = [truth(c) for c in cs]
    e = err(*ts)
    return e if e else all(ts)


def OR(*cs):
    ts = [truth(c) for c in cs]
    e = err(*ts)
    return e if e else any(ts)


def rmax(values):
    """MAX over a range: numbers only, errors propagate, nothing -> 0."""
    e = err(*values)
    if e:
        return e
    xs = [v for v in values if isnumber(v)]
    return max(xs) if xs else 0


def rmin(values):
    e = err(*values)
    if e:
        return e
    xs = [v for v in values if isnumber(v)]
    return min(xs) if xs else 0


_OPS = ('>=', '<=', '<>', '=', '<', '>')


def criterion(c):
    """Parse a SUMIFS/COUNTIF criterion ("=Local", "<2024", ">="&1) into (op, value)."""
    if not isinstance(c, str):
        return '=', c
    for op in _OPS:
        if c.startswith(op):
            s = c[len(op):]
            break
    else:
        op, s = '=', c
    try:
        return op, float(s)
    except ValueError:
        return op, s


def _wild(s):
    return re.compile('^' + ''.join('.*' if ch == '*' else '.' if ch == '?' else re.escape(ch) for ch in s) + '$',
                      re.I | re.S)


def matches(v, op, val):
    """Does cell value v meet the parsed criterion? Numeric criteria only match numbers; text criteria compare
    case-insensitively with * and ? wildcards for = and <>; "=" with nothing after it matches blanks."""
    if iserr(v):
        return False
    if isinstance(val, float):
        if not isnumber(v):
            return op == '<>'
        return cmp(v, op, val)
    if op in ('=', '<>'):
        if val == '':
            hit = v is None or v == ''
        else:
            hit = isinstance(v, str) and bool(_wild(val).match(v)) if any(ch in val for ch in '*?') \
                else isinstance(v, str) and v.lower() == val.lower()
        return hit if op == '=' else not hit
    if not isinstance(v, str):
        return False
    return cmp(v, op, val)


def _key(v):
    """Lookup key with Excel's exact-match equality: text case-insensitive, numbers by value."""
    if isinstance(v, bool):
        return ('b', v)
    if isinstance(v, (int, float)):
        return ('n', float(v))
    return ('s', v.lower())


class Ctx:
    """Whole-column SUMIFS/COUNTIF and exact VLOOKUP for one compute call. Area extents, matching rows per set of
    criteria and lookup indexes are cached for the life of the instance only, so make a fresh one per call (and
    after writing any cells that its criteria or lookup columns read)."""

    def __init__(self, book):
        self.book = book
        self.rows_cache, self.maxr, self.areas, self.index = {}, {}, {}, {}

    def rows(self, sheet, crits):
        key = (sheet, crits)
        if key not in self.rows_cache:
            S = self.book[sheet]
            if sheet not in self.maxr:
                self.maxr[sheet] = max((r for r, _ in S.cells), default=0)
            parsed = [(c,) + criterion(k) for c, k in crits]
            self.rows_cache[key] = [r for r in range(1, self.maxr[sheet] + 1)
                                    if all(matches(S.get(r, c), op, val) for c, op, val in parsed)]
        return self.rows_cache[key]

    def sumifs(self, sheet, sumcol, *crits):
        """SUMIFS(sheet!sumcol, sheet!col1, crit1, ...): crits are (column index, criterion text) pairs."""
        e = err(*(k for _, k in crits))
        if e:
            return e
        S = self.book[sheet]
        t = 0.0
        for r in self.rows(sheet, tuple(crits)):
            v = S.get(r, sumcol)
            if iserr(v):
                return v
            if isnumber(v):
                t += v
        return t

    def countif(self, sheet, col, r0, r1, crit):
        """COUNTIF(sheet!col r0:r1, crit)."""
        if iserr(crit):
            return crit
        op, val = criterion(crit)
        S = self.book[sheet]
        return sum(1 for r in range(r0, r1 + 1) if matches(S.get(r, col), op, val))

    def vl(self, key, area, col):
        """VLOOKUP(key, area, col, FALSE); an error key or column index propagates, a blank result reads as 0."""
        if iserr(col):
            return col
        if iserr(key):
            return key
        if area not in self.areas:
            self.areas[area] = self.book.area(area)
            sh, c0, r0, c1, r1 = self.areas[area]
            S, idx = self.book[sh], {}
            for r in range(r0, r1 + 1):
                v = S.get(r, c0)
                if v is not None and not iserr(v):
                    idx.setdefault(_key(v), r)
            self.index[area] = idx
        sh, c0, r0, c1, r1 = self.areas[area]
        r = self.index[area].get(_key(ref(key)))
        if r is None:
            return NA
        col = int(col)
        if col < 1 or col > c1 - c0 + 1:
            return '#REF!' if col > 1 else VALUE
        v = self.book[sh].get(r, c0 + col - 1)
        return 0 if v is None else v


def ifna(v, alt):
    return alt if v == NA else v


# ---------------------------------------------------------------------------------------------------------------
# The GFN sheet
# ---------------------------------------------------------------------------------------------------------------

B_ = 2                                         # column B: the BaseDB code of each row
IDF, RSF = 'IdentFin', 'ResidFin'
# column letters of the criteria columns on IdentFin/ResidFin and Triangles
cB, cD, cG, cK, cL, cQ = 2, 4, 7, 11, 12, 17
tC, tD, tI, tM, tR = 3, 4, 9, 13, 18


def compute(book, sheet='GFN'):
    G = book['GFN']
    g = G.get
    s = G.set
    add = lambda *v: calc(lambda *x: sum(x), *v)
    mul = lambda *v: calc(lambda *x: math.prod(x), *v)
    sub = lambda a, b: calc(lambda x, y: x - y, a, b)
    dv = lambda a, b: calc(lambda x, y: x / y, a, b)

    proj = book.name('ProjYr')
    shk = book.name('GFNshockyr')
    incu = book.name('GFNinCU')
    mitig = book.name('GFNMitigatorBool')
    amp = book.name('GFNAmplifierBool')
    projshk = calc(lambda a, b: a + b, proj, shk)
    x = Ctx(book)
    base = lambda key, col: x.vl(key, 'BaseDBData', col)
    shock = lambda key: x.vl(key, 'GFNShocksTab', 4)
    macro = lambda key, col: x.vl(key, 'MacrofwData', col)
    sumifs = x.sumifs
    yo = lambda c: g(31, c)                       # years from ProjYr
    in_shock = lambda c: OR(cmp(yo(c), '=', shk), cmp(yo(c), '=', calc(lambda x: x + 1, shk)))

    def fin(sumcol_ident, sumcol_resid, *crits):
        """The same SUMIFS on IdentFin plus on ResidFin."""
        return add(sumifs(IDF, sumcol_ident, *crits), sumifs(RSF, sumcol_resid, *crits))

    def ll(sumcol_ident, sumcol_resid, c, idx, *crits):
        """Local-linked: instruments of kind 1 and 2 each times their Macrofw index (idx 'LLI' or 'LLIE')."""
        a = fin(sumcol_ident, sumcol_resid, *crits, (cK, '=Local-Linked 1'))
        b = fin(sumcol_ident, sumcol_resid, *crits, (cK, '=Local-Linked 2'))
        return add(mul(a, macro(idx + '1', g(33, c))), mul(b, macro(idx + '2', g(33, c))))

    # --- stress-scenario header rows 30-33
    for c in ALL:
        s(30, c, calc(lambda a, b: a + b, proj, yo(c)))
        s(32, c, match(yo(c), book.hrow('BaseDBdates')))
        s(33, c, match(yo(c), book.hrow('MacrofwDates')))
    col = lambda c: g(32, c)

    for c in YRS:
        # real GDP growth: baseline, default shock (two shock years), stress
        s(35, c, base(g(35, B_), col(c)))
        s(36, c, IF(in_shock(c), lambda: calc(lambda v: -v, shock(g(36, B_))), 0))
        s(38, c, add(g(35, c), g(36, c), g(37, c)))
        # exchange rate: baseline depreciation, shock in the shock year, stress depreciation
        s(42, c, base(g(42, B_), col(c)))
        s(43, c, base(g(43, B_), col(c)))
        s(44, c, IF(cmp(yo(c), '=', shk), lambda: shock(g(44, B_)), 0))
        s(47, c, add(g(42, c), g(44, c), g(45, c)))
        s(48, c, add(g(43, c), g(44, c), g(45, c)))
    # stress exchange-rate levels
    s(50, 9, base(g(50, B_), col(9)))
    s(51, 9, base(g(51, B_), col(9)))
    for c in YRS:
        s(50, c, mul(g(50, c - 1), add(1, g(47, c))))
        s(51, c, mul(g(51, c - 1), add(1, g(48, c))))
        s(52, c, base(g(52, B_), col(c)))           # memo: baseline exchange rate
        # GDP deflator: baseline; shocks from economic slack and depreciation, or a direct deflator shock
        s(55, c, base(g(55, B_), col(c)))
        s(58, c, mul(sub(g(38, c), g(35, c)), shock(g(58, B_))))
        s(59, c, mul(sub(g(47, c), g(42, c)), shock(g(59, B_))))
        s(57, c, add(g(58, c), g(59, c)))
        s(56, c, add(g(57, c), g(60, c)))
        s(62, c, IF(cmp(yo(c), '=', shk), lambda: shock(g(62, B_)), 0))
        s(61, c, add(g(62, c), g(63, c)))
        s(64, c, add(g(55, c), IF(incu, g(61, c), g(56, c))))
    # nominal GDP level and growth
    s(67, 9, base(g(67, B_), col(9)))
    for c in YRS:
        s(67, c, mul(g(67, c - 1), add(1, g(38, c)), add(1, g(64, c))))
        s(68, c, sub(dv(g(67, c), g(67, c - 1)), 1))
    # primary balance: noninterest revenue and expenditure (expenditure kept at its pre-shock level in GDP terms
    # through the shock years when that is higher)
    for c in ALL:
        s(73, c, base(g(73, B_), col(c)))
        s(72, c, mul(g(73, c), g(67, c)))
        lev = lambda c=c: mul(base(g(76, B_), col(c)), g(67, c))
        s(75, c, IF(in_shock(c), lambda c=c: calc(max, base(g(75, B_), col(c)), lev()), lev))
        s(76, c, dv(g(75, c), g(67, c)))
    # marginal interest rates: baseline + shock fading out over five years + adjustment
    s(80, 9, base(g(80, B_), col(9)))
    s(85, 9, base(g(85, B_), col(9)))
    for c in YRS:
        for r0 in (80, 85):
            s(r0, c, ifna(base(g(r0, B_), col(c)), 0))
            s(r0 + 1, c, IF(cmp(yo(c), '>=', shk),
                            lambda c=c, r0=r0: calc(lambda y, v: max((6 - y) / 5 * v, 0), yo(c), shock(g(r0 + 1, B_))),
                            0))
            s(r0 + 3, c, add(g(r0, c), g(r0 + 1, c), g(r0 + 2, c)))
    # debt shares: short-term share jumps to DIST_SHK in the shock year, then falls 5 points a year to 30%
    for r0 in (95, 96, 97):
        s(r0, 9, base(g(r0, B_), col(9)))
    for c in YRS:
        st = lambda c=c: calc(lambda v, y, k: max(0.3, v - 0.05 * (y - k)), shock('DIST_SHK'), yo(c), shk)
        ll25 = mul(0.25, g(97, 9))
        for r0, tot, short in ((91, 95, True), (92, 96, True), (93, 95, False), (94, 96, False)):
            part = IF(cmp(yo(c), '>=', shk),
                      lambda tot=tot, short=short: mul(st() if short else calc(lambda x: 1 - x, st()), g(tot, 9)), 0)
            s(r0, c, add(part, ll25))

    # --- gross financing need
    for c in YRS:
        t11 = c + 11                                  # J -> Triangles/IdentFin/ResidFin column U
        before = (cG, cat('<', projshk))              # instruments issued before the shock
        # issuance outside the GFN and below-the-line items
        s(100, c, base(g(100, B_), col(c)))
        s(102, c, base(g(102, B_), col(c)))
        s(103, c, base(g(103, B_), col(c)))
        s(101, c, add(g(102, c), g(103, c)))
        s(105, c, calc(lambda a, b: -(a - b), g(72, c), g(75, c)))       # primary deficit
        # interest: pre-existing, new market debt (Triangles), new debt not subject to shocks
        tri = lambda item, cur, c=c, t11=t11: sumifs('Triangles', t11, (tC, '=' + item), (tI, '=' + cur),
                                                     (tR, '=Stress'))
        s(108, c, base(g(108, B_), col(c)))
        s(109, c, tri('Interest', 'Local'))
        s(110, c, fin(t11, t11, (cQ, '=GGEI'), (cK, '=Local'), before))
        s(107, c, add(g(108, c), g(109, c), g(110, c)))
        s(112, c, mul(dv(base(g(112, B_), col(c)), g(52, c)), g(50, c)))
        s(113, c, mul(tri('Interest', 'Foreign'), g(50, c)))
        s(114, c, mul(fin(t11, t11, (cQ, '=GGEI'), (cK, '=Foreign'), before), g(50, c)))
        s(111, c, add(g(112, c), g(113, c), g(114, c)))
        s(116, c, base(g(116, B_), col(c)))
        s(118, c, ll(t11, t11, c, 'LLI', (cQ, '=GGEI'), before))
        s(115, c, add(g(116, c), g(117, c), g(118, c)))
        s(106, c, add(g(107, c), g(111, c), g(115, c)))
        # amortization: same split
        s(121, c, base(g(121, B_), col(c)))
        s(122, c, tri('Amortization', 'Local'))
        s(123, c, fin(t11, t11, (cQ, '=GGFA'), (cK, '=Local'), before))
        s(120, c, add(g(121, c), g(122, c), g(123, c)))
        s(125, c, mul(dv(base(g(125, B_), col(c)), g(52, c)), g(50, c)))
        s(126, c, mul(tri('Amortization', 'Foreign'), g(50, c)))
        s(127, c, mul(fin(t11, t11, (cQ, '=GGFA'), (cK, '=Foreign'), before), g(50, c)))
        s(124, c, add(g(125, c), g(126, c), g(127, c)))
        s(129, c, base(g(129, B_), col(c)))
        s(131, c, ll(t11, t11, c, 'LLI', (cQ, '=GGFA'), before))
        s(128, c, add(g(129, c), g(130, c), g(131, c)))
        s(119, c, add(g(120, c), g(124, c), g(128, c)))
        # contingent liabilities, interest revenue, total GFN and total issuance
        s(132, c, mul(dv(base(g(132, B_), col(c)), g(52, c)), g(50, c)))
        s(133, c, base(g(133, B_), col(c)))
        s(104, c, sub(add(g(105, c), g(106, c), g(119, c), g(132, c)), g(133, c)))
        s(99, c, add(g(100, c), g(101, c), g(104, c)))
        s(134, c, dv(g(104, c), g(67, c)))            # memo: GFN/GDP
        # financing not subject to shocks: debt issued before the shock, and committed nonmarket debt
        yr = cat('=', yo(c))
        pre = (cD, cat('<', shk))
        nm = ((cL, '=Nonmarket'), (cB, '=Committed'))
        s(138, c, fin(t11, t11, (cQ, '=GGD'), (cD, yr), pre, (cK, '=Local')))
        s(139, c, mul(fin(t11, t11, (cQ, '=GGD'), (cD, yr), pre, (cK, '=Foreign')), g(50, c)))
        s(140, c, ll(t11, t11, c, 'LLI', (cQ, '=GGD'), (cD, yr), pre))
        s(141, c, fin(t11, t11, (cQ, '=GGD'), (cD, yr), (cK, '=Local'), *nm))
        s(142, c, mul(fin(t11, t11, (cQ, '=GGD'), (cD, yr), (cK, '=Foreign'), *nm), g(50, c)))
        s(143, c, ll(t11, t11, c, 'LLI', (cQ, '=GGD'), (cD, yr), *nm))
        s(137, c, add(*(g(r, c) for r in range(138, 144))))
        s(136, c, sub(g(99, c), g(137, c)))           # total financing in the stress scenario (GFNConvergeIn)

    # --- new financing in the stress scenario (as last copied by the converge macro) and who provides it
    _, oc0, orow, oc1, _ = book.area('GFNConvergeOut')
    conv = [book['Config'].get(orow, k) for k in range(oc0, oc1 + 1)]
    for c in YRS:
        k = yo(c) + 1
        s(144, c, ref(conv[int(k) - 1]) if 1 <= k <= len(conv) else '#REF!')
        after = cmp(yo(c), '>=', shk)
        s(146, c, IF(after, lambda c=c: add(g(121, c), g(125, c)), 0))       # for rollover of existing debt
        s(147, c, IF(after, lambda c=c: sub(g(144, c), g(146, c)), 0))       # for all other purposes
        # rollover rates: external private creditors in the shock years; domestic others under the amplifier
        s(170, c, IF(AND(amp, in_shock(c)), lambda: shock(g(170, B_)), 1))
        s(179, c, IF(in_shock(c), lambda: shock(g(179, B_)), 1))
    s(207, 9, base(g(207, B_), col(9)))
    for c in YRS:
        own = col(9) if c <= 15 else col(c)           # J:O use the ProjYr-1 holder shares
        # domestic central bank
        s(154, c, mul(base(g(154, B_), col(9)), g(146, c)))
        s(155, c, mul(base(g(155, B_), col(c)), g(147, c)))
        s(153, c, add(g(154, c), g(155, c)))
        # domestic commercial banks: own share plus reallocations
        s(159, c, mul(base(g(159, B_), own), g(146, c)))
        s(160, c, mul(base(g(160, B_), own), sub(1, g(179, c)), g(146, c)))
        s(161, c, mul(base(g(161, B_), own), sub(1, g(170, c)), g(146, c)))
        s(158, c, add(g(159, c), g(160, c), g(161, c)))
        s(163, c, mul(base(g(163, B_), col(c)), g(147, c)))
        s(164, c, mul(base(g(164, B_), col(c)), g(147, c)))
        s(165, c, IF(amp, lambda c=c: mul(base(g(165, B_), col(9)), g(147, c)), 0))
        s(162, c, add(g(163, c), g(164, c), g(165, c)))
        s(157, c, add(g(158, c), g(162, c)))
        # use of government assets, capped by the remaining stock of financial assets
        s(166, c, calc(lambda a, b: max(min(a, b), 0), g(164, c), g(207, c - 1)))
        s(207, c, sub(g(207, c - 1), g(166, c)))
        if c > 10:
            s(148, c, ref(g(166, c)))
        s(149, c, ref(g(166, c)))
        s(150, c, sub(g(144, c), g(149, c)))          # market-based debt
        # domestic other creditors
        s(169, c, mul(base(g(169, B_), col(9)), g(146, c), g(170, c)))
        s(171, c, IF(amp, 0, lambda c=c: mul(base(g(171, B_), col(c)), g(147, c))))
        s(168, c, add(g(169, c), g(171, c)))
        # external official creditors
        s(174, c, mul(base(g(174, B_), col(9)), g(146, c)))
        s(175, c, mul(base(g(175, B_), col(c)), g(147, c)))
        s(173, c, add(g(174, c), g(175, c)))
        # external private creditors
        s(178, c, mul(base(g(178, B_), col(9)), g(179, c), g(146, c)))
        s(177, c, add(g(178, c), g(180, c)))
        s(152, c, add(g(153, c), g(157, c), g(168, c), g(173, c), g(177, c)))
        # memo: rollover of bank debt before the shock
        s(202, c, IF(cmp(yo(c), '<', shk),
                     lambda c=c: mul(base(g(202, B_), col(9)), add(g(121, c), g(125, c), g(129, c))), 0))

    # --- bank claims on the general government
    newdebt = {}                                      # per year: new holdings split out for rows 232-261
    for r0 in (216, 217):
        s(r0, 9, base(g(r0, B_), col(9)))
    s(184, 9, mul(base(g(184, B_), col(9)), sub(1, g(217, 9))))
    s(185, 9, mul(base(g(185, B_), col(9)), g(217, 9)))
    s(204, 9, base(g(204, B_), col(9)))
    for c in YRS:
        t66, t88 = c + 66, c + 88                     # Triangles commercial-bank (BX..) / domestic-other (CT..) blocks
        t121 = c + 121                                # IdentFin/ResidFin EA..: commercial-bank holdings
        rb = g(159, c), g(202, c)
        s(184, c, sub(g(184, c - 1), mul(add(*rb), g(95, 9))))
        s(185, c, sub(mul(dv(g(185, c - 1), g(51, c - 1)), g(51, c)), mul(add(*rb), g(96, 9))))
        before = (cG, cat('<', projshk))
        after = (cG, cat('>=', projshk))
        nm = ((cL, '=Nonmarket'), (cB, '=Committed'))
        stress = lambda cur, tc: sumifs('Triangles', tc, (tC, '=Stock'), (tD, cat('>=', shk)), (tI, '=' + cur),
                                        (tM, '=Market'), (tR, '=Stress'))
        s(188, c, fin(t121, t121, (cQ, '=GGD'), (cK, '=Local'), before))
        s(189, c, fin(t121, t121, (cQ, '=GGD'), after, (cK, '=Local'), *nm))
        s(190, c, stress('Local', t66))
        s(192, c, mul(fin(t121, t121, (cQ, '=GGD'), (cK, '=Foreign'), before), g(51, c)))
        s(193, c, mul(fin(t121, t121, (cQ, '=GGD'), after, (cK, '=Foreign'), *nm), g(51, c)))
        s(194, c, mul(stress('foreign', t66), g(51 if c <= 15 else 50, c)))
        s(196, c, ll(t121, t121, c, 'LLIE', (cQ, '=GGD'), before))
        s(197, c, ll(t121, t121, c, 'LLIE', (cQ, '=GGD'), after, *nm))
        # non-bank financial sector (customization) and remaining other domestic creditors: new holdings
        t143 = c + 143                                # IdentFin EW.. (ResidFin stays on EA..)
        newdebt[c] = {
            'pre_l': fin(t143, t121, (cQ, '=GGD'), (cK, '=Local'), before),
            'nm_l': fin(t143, t121, (cQ, '=GGD'), after, (cK, '=Local'), *nm),
            'pre_f': fin(t143, t121, (cQ, '=GGD'), (cK, '=Foreign'), before),
            'nm_f': fin(t143, t121, (cQ, '=GGD'), after, (cK, '=Foreign'), *nm),
            'pre_ll': ll(t143, t121, c, 'LLIE', (cQ, '=GGD'), before),
            'nm_ll': ll(t143, t121, c, 'LLIE', (cQ, '=GGD'), after, *nm),
            'sc_l': stress('Local', t88),
            'sc_f': stress('foreign', t88),
        }
    for c in ALL:
        for r0 in (187, 191, 195):
            s(r0, c, add(g(r0 + 1, c), g(r0 + 2, c), g(r0 + 3, c)))
        s(186, c, add(g(187, c), g(191, c), g(195, c)))
        s(183, c, add(g(184, c), g(185, c)))
        s(182, c, add(g(183, c), g(186, c)))
        if c > 9:
            s(204, c, mul(g(204, c - 1), add(1, g(68, c))))   # banking-system assets grow with nominal GDP
        s(205, c, dv(g(204, c), g(67, c)))
        s(199, c, dv(g(182, c), g(204, c)))
        if c > 10:
            s(200, c, sub(g(199, c), g(199, 10)))
    # implied holder shares of new market financing
    for c in YRS:
        net = sub(g(144, c), g(166, c))
        s(210, c, dv(g(153, c), net))
        s(211, c, dv(sub(g(157, c), g(166, c)), net))
        s(212, c, dv(g(168, c), net))
        s(213, c, dv(g(173, c), net))
        s(214, c, dv(g(177, c), net))

    # --- customization: non-bank financial sector as a risk mitigator, and the remaining other domestic creditors
    nobank = book.hrow('GFNNoBank')
    pick = lambda label: (lambda i: i if iserr(i) else ref(nobank[i]) if i < len(nobank) else '#REF!')(
        match(label, nobank))
    s(220, 9, pick('Total assets:'))
    s(223, 9, pick('Claims on GG:'))
    s(224, 9, dv(g(223, 9), base(g(224, B_), col(9))))
    s(226, 9, ref(g(223, 9)))
    s(246, 9, sub(base(g(246, B_), col(9)), g(226, 9)))
    for k, r0 in enumerate((95, 96, 97)):
        s(227 + k, 9, mul(g(226, 9), g(r0, 9)))
        s(247 + k, 9, mul(g(246, 9), g(r0, 9)))
    share = g(224, 9)
    rest = sub(1, share)
    for c in YRS:
        st = newdebt[c]
        s(220, c, mul(g(220, c - 1), add(1, g(68, c))))
        for k, amort in enumerate((121, 125, 129)):
            s(227 + k, c, sub(g(227 + k, c - 1), mul(g(amort, c), base(g(227 + k, B_), col(c)), share)))
            s(247 + k, c, sub(g(247 + k, c - 1), mul(g(amort, c), base(g(247 + k, B_), col(c)), rest)))
        s(226, c, add(g(227, c), g(228, c)))
        s(246, c, add(g(247, c), g(248, c)))
        for base_r, f in ((232, share), (252, rest)):
            s(base_r, c, mul(f, st['pre_l']))
            s(base_r + 1, c, mul(f, st['nm_l']))
            s(base_r + 2, c, mul(st['sc_l'], f))
            s(base_r + 4, c, mul(f, mul(st['pre_f'], g(51, c))))
            s(base_r + 5, c, mul(f, mul(st['nm_f'], g(51, c))))
            s(base_r + 6, c, mul(st['sc_f'], g(50, c), f))
            s(base_r + 8, c, mul(f, st['pre_ll']))
            s(base_r + 9, c, mul(f, st['nm_ll']))
            for r0 in (base_r - 1, base_r + 3, base_r + 7):
                s(r0, c, add(g(r0 + 1, c), g(r0 + 2, c), g(r0 + 3, c)))
            s(base_r - 2, c, add(g(base_r - 1, c), g(base_r + 3, c)))
        s(223, c, add(g(226, c), g(230, c)))
    for c in ALL:
        s(245, c, add(g(246, c), g(250, c)))
        s(264, c, add(g(223, c), g(182, c)))
        s(265, c, dv(g(264, c), add(g(220, c), g(204, c))))

    # --- change in bank claims in stress (rows 17-24): each row compares later years with one base year
    for c in range(9, 15):
        s(17, c, calc(lambda a, b: a + b, proj, g(16, c)))
    for i, r in enumerate(range(18, 24)):
        b0 = 10 + i                                   # base column J, K, ...
        for c in range(9 + i, 15):
            s(r, c, IF(mitig, lambda c=c, b0=b0: sub(g(265, c + 1), g(265, b0)),
                       lambda c=c, b0=b0: sub(g(199, c + 1), g(199, b0))))
    s(24, 14, rmax([g(r, c) for r in range(18, 24) for c in range(9, 15)]))

    # --- initial bank claims (rows 12-13)
    unit = cat(book.name('UnitScale'), ' ', book.name('CurrencyName'))
    s(12, 16, unit)
    s(12, 21, unit)
    s(72, 6, unit)
    s(75, 7, unit)
    s(13, 13, calc(lambda p: p - 1, proj))
    mcol = match(-1, book.hrow('MacrofwDates'))
    nb = lambda label: IF(mitig, lambda: pick(label), 0)
    s(13, 17, add(macro('FOSAGG', mcol), nb('Claims on GG:')))
    s(13, 21, add(macro('FODA', mcol), nb('Total Assets:')))
    s(13, 19, dv(g(13, 21), macro('NGDP', mcol)))
    s(13, 15, dv(g(13, 17), g(13, 21)))

    # --- the financeability index and signal (rows 5-9)
    for c in range(16, 22):
        s(5, c, match(g(4, c), book.hrow('BaseDBdates')))
        s(7, c, calc(lambda a, b: a + b, proj, g(4, c)))
        s(8, c, base(g(7, B_), g(5, c)))
    s(8, 14, average([g(8, c) for c in range(16, 22)]))
    s(6, 14, cat('Avg ', '\n', g(7, 16), '-', (lambda t: t if iserr(t) else t[-2:])(cat(g(7, 21)))))
    s(5, 11, ref(g(8, 14)))
    s(6, 11, ref(g(13, 15)))
    s(7, 11, ref(g(24, 14)))
    s(8, 11, calc(lambda a, b, c_, wa, wb, wc: (a * wa + b * wb + c_ * wc) * 100,
                  g(5, 11), g(6, 11), g(7, 11), g(5, 10), g(6, 10), g(7, 10)))
    k8, hi, lo = g(8, 11), g(12, 11), g(13, 11)
    s(9, 11, IF(cmp(k8, '>', hi), 'High',
                lambda: IF(cmp(k8, '<', lo), 'Low',
                           lambda: IF(AND(cmp(k8, '<=', hi), cmp(k8, '>=', lo)), 'Moderate', NA))))


# ---------------------------------------------------------------------------------------------------------------
# The converge macro (ModGFN.bas)
# ---------------------------------------------------------------------------------------------------------------

class MacroError(Exception):
    """The VBA macro stopped with a run-time error."""


def _single(x):
    """A VBA Single (32-bit float)."""
    return struct.unpack('f', struct.pack('f', x))[0]


def _recalc(book):
    from . import triangles
    compute(book, 'GFN')              # GFN with the current Triangles
    triangles.compute(book, 'Triangles')
    compute(book, 'GFN')              # and once more with Triangles caught up (Triangles does not read GFN!136)


def _check(book):
    """Config!CJ41:CY41 (gap between GFNConvergeOut and GFN!J136:Y136 within the medium-term horizon) and
    GFNConvergeChk = SUM of the gaps; written back to Config as Excel would recalculate them."""
    Cf, G = book['Config'], book['GFN']
    _, c0, r0, c1, _ = book.area('GFNConvergeOut')
    hor = book.name('MTHorizon')
    gaps = []
    for k, c in enumerate(range(c0, c1 + 1)):
        gap = IF(cmp(Cf.get(r0 - 2, c), '<=', hor),
                 lambda c=c, k=k: calc(lambda a, b: a - b, Cf.get(r0, c), G.get(136, 10 + k)), 0)
        Cf.set(r0 + 1, c, gap)
        gaps.append(gap)
    e = err(*gaps)
    chk = e if e else sum(v for v in gaps if isnumber(v))
    sh, cell = book.name_ref('GFNConvergeChk')
    book[sh][cell] = chk
    return chk


def simulate(book):
    """Run the GFN `converge` macro: clear GFNConvergeOut, then up to GFNMaxiters+1 times copy GFNConvergeIn
    (GFN!J136:Y136) into GFNConvergeOut and recalculate, until |GFNConvergeChk| <= |GFNtoler|.
    Returns (converged, iterations, check). Raises MacroError where the VBA would stop with a run-time error."""
    maxiter = int(book.name('GFNMaxiters'))
    tol = _single(num(book.name('GFNtoler')))
    Cf, G = book['Config'], book['GFN']
    _, c0, r0, c1, _ = book.area('GFNConvergeOut')
    for c in range(c0, c1 + 1):                      # ClearContents
        Cf.cells.pop((r0, c), None)
    _recalc(book)
    chk = _check(book)
    if not isnumber(chk):
        raise MacroError(f'Type mismatch: GFNConvergeChk is {chk!r}')
    chk = _single(chk)
    i = 0
    while i <= maxiter and abs(tol) < abs(chk):
        for k, c in enumerate(range(c0, c1 + 1)):
            Cf.set(r0, c, G.get(136, 10 + k))
        _recalc(book)
        chk = _check(book)
        if not isnumber(chk):
            raise MacroError(f'Type mismatch: GFNConvergeChk is {chk!r}')
        chk = _single(chk)
        i += 1
    return abs(chk) < abs(tol), i, chk
