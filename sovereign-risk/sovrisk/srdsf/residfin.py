"""ResidFin sheet: residual financing. Works out the gross financing need left after identified financing
(primary deficit, interest and amortization of existing and identified debt, other flows), issues new debt to
cover it, and tracks each year's issuance ("vintage") of each residual instrument through its interest rate,
amortization, outstanding stock, interest bill, effective interest rate and holder breakdown.

The new issuance is circular in the workbook's logic only through earlier vintages: the debt issued in year t has
to cover the interest and amortization that the issues of years before t fall due for in year t, so issuance is
solved column by column (row 27).

The module also holds the small lazy evaluator that BaseDB shares (`Engine`, `X`): each formula cell is a rule,
and reading a cell computes it on demand, so cells are filled in dependency order whatever order the rules were
declared in.
"""
import math
import operator
import sys

from .book import ci
from .xl import DIV0, NA, VALUE, average, err, iserr, isnumber, match, num, xsum

SHEETS = ['ResidFin']

QUIRKS = [
    'Row 84 (GGDR_PCT, first vintage): from column AJ on the remaining-principal share is 1-SUM($U65:AJ65), '
    'i.e. it includes the current year, while columns V:AI (and all later vintages) stop one year before; '
    'reproduced.',
    'Row 58 ("price re-set for linked") tests $R48="Local-Linked", which no currency choice produces '
    '("Local-Linked 1"/"Local-Linked 2"), and its VLOOKUP column is #REF!; reproduced (0, or #REF! if matched).',
    'Column P ("Zero" label): a zero-coupon instrument is labelled "Zero", but the amortization SWITCH in row 65 '
    'looks for "Zero-coupon", so a zero-coupon instrument amortizes as #N/A; reproduced.',
    'Column P of the GGEI, EFF_IR and INT_BASE vintage rows compares E/F of the GGFA vintage rows (152+k) rather '
    'than its own row (same values); reproduced.  P64 compares E65=F65.',
    'A49 builds its key from C48 instead of C49 (same value); reproduced.',
    'Holder breakdown blocks: the last block (GN:HC, external private creditors) starts 21 columns after FS '
    'rather than 22 like the others; layout reproduced.',
]

# --------------------------------------------------------------------------------------------------------------
# Excel value semantics for arithmetic, shared with basedb.py
# --------------------------------------------------------------------------------------------------------------


def _arith(a, b, f):
    if iserr(a):
        return a
    if iserr(b):
        return b
    if isinstance(a, str) or isinstance(b, str):
        a, b = _numtext(a), _numtext(b)
        if a is None or b is None:
            return VALUE
    try:
        r = f(num(a), num(b))
    except ZeroDivisionError:
        return DIV0
    except (OverflowError, ValueError):
        return '#NUM!'
    if isinstance(r, complex) or (isinstance(r, float) and (math.isinf(r) or math.isnan(r))):
        return '#NUM!'
    return r


def _numtext(v):
    """Text in arithmetic: a number stored as text converts, anything else (including "") is #VALUE!."""
    if not isinstance(v, str):
        return v
    try:
        return float(v)
    except ValueError:
        return None


class X:
    """An Excel value with Excel arithmetic: blank -> 0, errors propagate left to right, x/0 -> #DIV/0!."""
    __slots__ = ('v',)

    def __init__(self, v):
        self.v = v.v if isinstance(v, X) else v

    @staticmethod
    def _v(o):
        return o.v if isinstance(o, X) else o

    def __add__(self, o): return X(_arith(self.v, X._v(o), operator.add))
    def __radd__(self, o): return X(_arith(X._v(o), self.v, operator.add))
    def __sub__(self, o): return X(_arith(self.v, X._v(o), operator.sub))
    def __rsub__(self, o): return X(_arith(X._v(o), self.v, operator.sub))
    def __mul__(self, o): return X(_arith(self.v, X._v(o), operator.mul))
    def __rmul__(self, o): return X(_arith(X._v(o), self.v, operator.mul))
    def __truediv__(self, o): return X(_arith(self.v, X._v(o), operator.truediv))
    def __rtruediv__(self, o): return X(_arith(X._v(o), self.v, operator.truediv))
    def __pow__(self, o): return X(_arith(self.v, X._v(o), operator.pow))
    def __neg__(self): return X(_arith(0, self.v, operator.sub)) if not iserr(self.v) else self

    def __repr__(self):
        return f'X({self.v!r})'


def val(v):
    return v.v if isinstance(v, X) else v


def text(v):
    """A value as Excel's & operator writes it."""
    v = val(v)
    if v is None:
        return ''
    if isinstance(v, bool):
        return 'TRUE' if v else 'FALSE'
    if isinstance(v, (int, float)):
        if float(v).is_integer():
            return str(int(v))
        return f'{v:.15g}'
    return v


def cat(*parts):
    """Excel '&': the first error among the parts, else the joined text."""
    parts = [val(p) for p in parts]
    return err(*parts) or ''.join(text(p) for p in parts)


def cmp(a, op, b):
    """Excel comparison: errors propagate, blank = 0 or "", text compares case-insensitively, text > numbers."""
    a, b = val(a), val(b)
    e = err(a, b)
    if e:
        return e
    if a is None:
        a = '' if isinstance(b, str) else 0
    if b is None:
        b = '' if isinstance(a, str) else 0
    if isinstance(a, bool):
        a = float(a)
    if isinstance(b, bool):
        b = float(b)
    if isinstance(a, str) != isinstance(b, str):
        ka, kb = (1 if isinstance(a, str) else 0), (1 if isinstance(b, str) else 0)
    elif isinstance(a, str):
        ka, kb = a.lower(), b.lower()
    else:
        ka, kb = a, b
    return {'=': ka == kb, '<>': ka != kb, '<': ka < kb, '<=': ka <= kb, '>': ka > kb, '>=': ka >= kb}[op]


def truth(v):
    """An IF condition: True/False, or the error that IF returns instead."""
    v = val(v)
    if iserr(v):
        return v
    if isinstance(v, str):
        if v.upper() in ('TRUE', 'FALSE'):
            return v.upper() == 'TRUE'
        return VALUE
    return bool(num(v))


def AND(*vals):
    ts = [truth(v) for v in vals]
    return err(*ts) or all(ts)


def OR(*vals):
    ts = [truth(v) for v in vals]
    return err(*ts) or any(ts)


def IF(cond, yes, no):
    """IF with lazy branches: yes/no are callables."""
    t = truth(cond)
    if iserr(t):
        return t
    return yes() if t else no()


def iferror(v, alt):
    v = val(v)
    return alt() if iserr(v) else v


def switch(x, *cases):
    """SWITCH(x, v1, r1, v2, r2, ...) without default (no match -> #N/A); results are callables."""
    x = val(x)
    if iserr(x):
        return x
    for k, r in zip(cases[::2], cases[1::2]):
        if cmp(x, '=', k) is True:
            return r()
    return NA


def vlookup(book, key, area, col):
    """VLOOKUP(key, area, col, FALSE) as a cell shows it: a blank target reads 0."""
    key, col = val(key), val(col)
    e = err(key, col)
    if e:
        return e
    v = book.vlookup(key, area, int(col))
    return 0 if v is None else v


# --------------------------------------------------------------------------------------------------------------
# Lazy evaluation of one sheet's formula cells
# --------------------------------------------------------------------------------------------------------------


class Engine:
    """Formula rules of one sheet. `e(r, c)` returns a cell's value, computing its rule first if it has one;
    `e.x(r, c)` returns it wrapped for arithmetic. `run()` computes every rule and writes the values."""

    def __init__(self, book, sheet):
        self.book, self.name, self.S = book, sheet, book[sheet]
        self.rules, self.done, self.busy = {}, set(), set()
        self._rows, self._match = {}, {}

    def let(self, r, cols, fn):
        """Declare row r's formula over columns `cols` (an int or a range): fn(c) gives column c's value."""
        for c in ([cols] if isinstance(cols, int) else cols):
            self.rules[(r, c)] = fn

    def __call__(self, r, c):
        k = (r, c)
        fn = self.rules.get(k)
        if fn is None or k in self.done:
            return self.S.get(r, c)
        if k in self.busy:
            raise RuntimeError(f'{self.name}: circular reference at {r},{c}')
        self.busy.add(k)
        v = val(fn(c))
        if v is None:                     # a formula that only points at a blank cell shows 0
            v = 0
        self.busy.discard(k)
        self.S.set(r, c, v)
        self.done.add(k)
        return v

    def x(self, r, c):
        return X(self(r, c))

    def run(self):
        old = sys.getrecursionlimit()
        sys.setrecursionlimit(max(old, 20000))
        try:
            for (r, c) in list(self.rules):
                self(r, c)
        finally:
            sys.setrecursionlimit(old)

    # -- whole-column functions (SUMIFS / SUMIF / COUNTIF / MAX over sheet!X:X) --

    def _get(self, sheet):
        return self if sheet == self.name else self.book[sheet].get

    def _sheet_rows(self, sheet):
        if sheet not in self._rows:
            rows = {r for r, _ in self.book[sheet].cells}
            if sheet == self.name:
                rows |= {r for r, _ in self.rules}
            self._rows[sheet] = sorted(rows)
        return self._rows[sheet]

    def sumifs(self, sheet, col, *crit):
        """SUMIFS(sheet!col:col, sheet!c1:c1, k1, ...). crit alternates column letters and Excel criteria
        ("=GGD", ">2024", ...). Blank and text cells in the sum column are skipped; a matching error is
        returned."""
        crit = tuple(val(k) for k in crit)
        e = err(*crit[1::2])
        if e:
            return e
        get = self._get(sheet)
        key = (sheet, crit)
        if key not in self._match:
            rows = self._sheet_rows(sheet)
            for cc, k in zip(crit[::2], crit[1::2]):
                test, c = criterion(k), ci(cc)
                rows = [r for r in rows if test(get(r, c))]
            self._match[key] = rows
        c = ci(col) if isinstance(col, str) else col
        return xsum(get(r, c) for r in self._match[key])

    def both(self, col, *crit):
        """SUMIFS over IdentFin plus the same SUMIFS over ResidFin (identified + residual financing)."""
        return X(self.sumifs('IdentFin', col, *crit)) + self.sumifs('ResidFin', col, *crit)

    def countif(self, col, r0, r1, k):
        test = criterion(k)
        return sum(1 for r in range(r0, r1 + 1) if test(self(r, ci(col))))

    def colmax(self, sheet, col):
        get, c = self._get(sheet), ci(col)
        vs = [get(r, c) for r in self._sheet_rows(sheet)]
        return err(*vs) or max([v for v in vs if isnumber(v)], default=0)


def criterion(k):
    """An Excel SUMIFS/COUNTIF criterion ("=X", ">1", "<=2030", "Market") as a cell test."""
    k = text(k) if not isinstance(k, str) else k
    for op in ('<=', '>=', '<>', '<', '>', '='):
        if k.startswith(op):
            k = k[len(op):]
            break
    else:
        op = '='
    try:
        x = float(k)
    except ValueError:
        x = None
    if x is not None:                                    # numeric criterion: compares with numbers only
        f = {'=': operator.eq, '<>': operator.ne, '<': operator.lt, '<=': operator.le,
             '>': operator.gt, '>=': operator.ge}[op]
        if op == '<>':
            return lambda v: not (isnumber(v) and v == x)
        return lambda v: isnumber(v) and f(v, x)
    low = k.lower()
    if op == '=':
        if low == '':
            return lambda v: v is None or v == ''
        return lambda v: isinstance(v, str) and v.lower() == low
    if op == '<>':
        return lambda v: not (isinstance(v, str) and v.lower() == low) if low else v not in (None, '')
    f = {'<': operator.lt, '<=': operator.le, '>': operator.gt, '>=': operator.ge}[op]
    return lambda v: isinstance(v, str) and f(v.lower(), low)


# --------------------------------------------------------------------------------------------------------------
# ResidFin
# --------------------------------------------------------------------------------------------------------------

U, AJ, CY = ci('U'), ci('AJ'), ci('CY')        # year 0, year 15 (last issuance year), year 82
YEARS = range(U, AJ + 1)                         # the 16 issuance years
ALL = range(U, CY + 1)                           # every year the vintages run through
# holder breakdown of each vintage's stock: (share column, first year column, share row in the instrument block)
HOLDERS = [('DD', 'DE', 5), ('DZ', 'EA', 6), ('EV', 'EW', 7), ('FR', 'FS', 8), ('GM', 'GN', 9)]
BLOCK = 173                                      # rows from an instrument's header (D = "X") to its end line
VINT = 16                                        # vintages (issuance years) per instrument


def compute(book, sheet='ResidFin'):
    e = Engine(book, sheet)
    proj = lambda: book.name('ProjYr')
    x = e.x

    # -- header rows: years, columns in Macrofw and BaseDB --
    e.let(3, ALL, lambda c: X(proj()) + e(4, c))
    for _, first, _ in HOLDERS:                                       # year labels over the holder blocks
        e.let(3, range(ci(first), ci(first) + VINT), lambda c, f=ci(first): e(3, U + c - f))
    e.let(5, ALL, lambda c: _match(e(4, c), book.hrow('MacrofwDates')))
    e.let(6, ALL, lambda c: _match(e(4, c), book.hrow('BaseDBdates')))
    e.let(6, ci('C'), lambda c: e.colmax('IdentFin', 'C'))           # last instrument number in IdentFin

    # -- determination of total debt issuance --
    for r in range(8, 19):                                            # deficit, flows, existing debt service
        e.let(r, YEARS, lambda c, r=r: vlookup(book, e(r, 2), 'BaseDBData', e(6, c)))
    ident = lambda c, item, cur: e.sumifs('IdentFin', c, 'Q', '=' + item, 'K', '=' + cur)
    lli = lambda c, code: vlookup(book, code, 'MacrofwData', e(5, c))
    for r, item in ((19, 'GGEI'), (22, 'GGFA')):                      # identified debt: interest, amortization
        e.let(r, YEARS, lambda c, item=item: ident(c, item, 'Local'))
        e.let(r + 1, YEARS, lambda c, item=item: X(ident(c, item, 'Foreign')) * e(45, c))
        e.let(r + 2, YEARS, lambda c, item=item: X(ident(c, item, 'Local-Linked 1')) * lli(c, 'LLI1')
              + X(ident(c, item, 'Local-Linked 2')) * lli(c, 'LLI2'))
    # financing need = primary deficit + other items + debt service - interest revenue
    e.let(25, YEARS, lambda c: x(8, c) + xsum(e(r, c) for r in range(10, 25)) - e(9, c))
    e.let(26, YEARS, lambda c: e.sumifs('IdentFin', c, 'B', '=Issuance'))   # identified issuance

    def issuance(c):
        """Residual issuance: covers the need net of identified issuance, plus the interest and amortization
        that this year's and earlier years' residual issues fall due for (rows 28+, per unit issued)."""
        i = c - U
        t = x(25, c)
        for j in range(i):
            t = t + x(27, U + j) * e(28 + j, c)
        return t / (1 - x(28 + i, c)) - e(26, c)
    e.let(27, YEARS, issuance)
    for k in range(VINT):                                             # debt service per unit issued in year k
        r = 28 + k
        e.let(r, ci('K'), lambda c, k=k: e(27, U + k))
        e.let(r, ci('T'), lambda c, r=r: X(proj()) + e(r, 4))
        e.let(r, range(U + k, AJ + 1), lambda c, r=r: X(
            e.sumifs('ResidFin', c, 'Q', '=ISS_CALC_INT', 'G', '=' + text(e(r, 20))))
            + e.sumifs('ResidFin', c, 'Q', '=ISS_CALC_AMT', 'G', '=' + text(e(r, 20))))
    e.let(44, YEARS, lambda c: x(26, c) + e(27, c))                   # total debt issuance
    e.let(45, YEARS, lambda c: vlookup(book, e(45, 2), 'BaseDBData', e(6, c)))   # memo: exchange rate

    # -- instruments: each starts on a row whose column D holds "X" --
    for b in [r for r in range(47, max(r for r, _ in e.S.cells) + 1) if e.S.get(r, 4) == 'X']:
        _instrument(e, book, b)
    e.run()


def _match(v, row):
    v = val(v)
    return v if iserr(v) else match(v, row)


def _instrument(e, book, b):
    """One residual-financing instrument whose header is row b (row 47 for the sample's instrument 7)."""
    x = e.x
    # setting rows: currency (and share by year), interest type (and rate), marketability (and exchange
    # rate), frequency, grace, maturity, perimeter, linked-index code, committed
    cur, ityp, mkt, freq, grace, mat, perim, link, commit = b + 1, b + 2, b + 3, b + 4, b + 5, b + 6, b + 7, \
        b + 8, b + 10
    R = ci('R')
    par = lambda r: e(r, R)                                           # the instrument's settings in column R

    # labels
    for r in range(b, b + BLOCK):
        e.let(r, 3, lambda c, r=r: e.countif('D', 1, r, '=X') + X(e(6, 3)))   # instrument number
    e.let(b, 2, lambda c: cat('INST', e(b, 3)))
    e.let(b, 17, lambda c: cat('Instrument ', _right(e(b, 2), _len(e(b, 2)) - 4)))
    e.let(b + 1, 2, lambda c: cat(e(b, 2), '_A'))
    e.let(b + 2, 2, lambda c: cat(e(b, 2), '_I'))
    keys = [(1, 1, '-CURR_IS'), (2, 1, '-ITYP-IR'), (3, 3, '-MKTY-ER'), (4, 4, '-FQ-X1'), (5, 5, '-GP-SHDC'),
            (6, 6, '-MY-SHDB'), (7, 7, '-PR-SHDN'), (8, 8, '-LRSHXO'), (9, 9, '-X2-SHXP'), (10, 10, '-X3-CA'),
            (11, 11, '-X4-PJ')]
    for i, j, suffix in keys:                                         # A49 takes C48: same number
        e.let(b + i, 1, lambda c, j=j, s=suffix: cat(e(b + j, 3), s))
    e.let(b + 4, ci('S'), lambda c: cat('Percent of ', e(b, 17), ' allocated to:'))
    e.let(link, R, lambda c: 'LLI1' if cmp(par(cur), '=', 'Local-Linked 1') is True
          else 'LLI2' if cmp(par(cur), '=', 'Local-Linked 2') is True else 'n.a.')
    e.let(b + 12, 11, lambda c: par(cur))
    e.let(b + 15, 11, lambda c: par(cur))
    e.let(b + BLOCK - 1, 17, lambda c: cat('End of instrument ', e(b + BLOCK - 1, 3)))

    # settings by year
    e.let(ityp, YEARS, lambda c: vlookup(book, e(ityp, 2), 'FinancingIn', e(5, c)))        # interest rate
    def fx(c):                                                        # applicable exchange rate
        if cmp(par(cur), '=', 'Local') is True:
            return 1
        if cmp(par(cur), '=', 'Foreign') is True:
            return vlookup(book, 'ENDA', 'MacrofwData', e(5, c))
        if cmp(par(cur), '=', 'Local-Linked 1') is True or cmp(par(cur), '=', 'Local-Linked 2') is True:
            return vlookup(book, par(link), 'MacrofwData', e(5, c))
        return NA
    e.let(mkt, YEARS, fx)
    e.let(mkt, range(AJ + 1, CY + 1), lambda c: e(mkt, c - 1))
    for r in range(grace, grace + 5):                                 # holder shares: first year, then carried
        e.let(r, U, lambda c, r=r: vlookup(book, e(r, 2), 'MacrofwData', X(e(5, c)) - 1))
        e.let(r, range(U + 1, AJ + 1), lambda c, r=r: e(r, c - 1))
    e.let(b + 11, YEARS, lambda c: '#REF!' if cmp(par(cur), '=', 'Local-Linked') is True else 0)
    iss = b + 12
    e.let(iss, YEARS, lambda c: x(cur, c) * e(27, c))                 # debt issued
    e.let(b + 13, YEARS, lambda c: x(iss, c) / (                      # share of total debt issuance
        X(e.sumifs('IdentFin', c, 'B', '=Issuance')) + e.sumifs('ResidFin', c, 'B', '=Issuance')))
    e.let(b + 14, YEARS, lambda c: x(ityp, c) * e(b + 13, c))         # contribution to total marginal IR
    e.let(b + 15, YEARS, lambda c: x(ityp, c) * e(iss, c) / (         # contribution to currency marginal IR
        X(e.sumifs('IdentFin', c, 'B', '=Issuance', 'K', cat('=', e(b + 15, 11))))
        + e.sumifs('ResidFin', c, 'B', '=Issuance', 'K', cat('=', e(b + 15, 11)))))
    e.let(b + 16, YEARS, lambda c: cat('t', e(4, c)))

    semi, amort = b + 17, b + 18                                      # rows 64, 65

    def freq_of(c):
        return switch(par(freq), 'Semiannual', lambda: 0.5, 'Annual', lambda: 1, 'Custom', lambda: 1)

    def kind_of(r, rr):                                               # Bullet / Amortizing / Zero / Custom
        if cmp(par(freq), '=', 'Custom') is True:
            return 'Custom'
        if cmp(par(ityp), '=', 'Zero-coupon') is True:
            return 'Zero'
        t = cmp(e(rr, 5), '=', e(rr, 6))
        return t if iserr(t) else ('Bullet' if t else 'Amortizing')

    def labels(r, k, prow):
        """Columns E:P of a vintage row (k = vintage, prow = the row whose E/F the P label compares)."""
        e.let(r, 5, lambda c: par(grace))
        e.let(r, 6, lambda c: par(mat))
        e.let(r, 15, freq_of)
        e.let(r, 16, lambda c: kind_of(r, prow))
        if k is None:
            return
        e.let(r, 2, lambda c: switch(par(commit), 'Yes', lambda: 'Committed', 'No', lambda: 'Uncommitted',
                                     'Not given', lambda: 'Not given'))
        e.let(r, 1, lambda c: cat(e(r, 17), '_', e(r, 3), '_', e(r, 4)))
        e.let(r, 7, lambda c: X(book.name('ProjYr')) + e(r, 4))       # issue year
        e.let(r, 8, lambda c: x(r, 7) + e(r, 5))                      # first amortization year
        e.let(r, 9, lambda c: x(r, 7) + e(r, 6))                      # maturity year
        e.let(r, 10, lambda c: e(mkt, U + k))
        e.let(r, 11, lambda c: par(cur))
        e.let(r, 12, lambda c: par(mkt))
        e.let(r, 13, lambda c: par(ityp))
        e.let(r, 14, lambda c: par(perim))

    labels(semi, None, amort)
    labels(amort, None, amort)
    # semiannual adjustment for interest, and the amortization schedule per unit issued (by years since issue)
    e.let(semi, ALL, lambda c: IF(AND(cmp(e(semi, 15), '=', 0.5), cmp(e(4, c), '=', 0)), lambda: 0.5,
                                  lambda: IF(AND(cmp(e(4, c), '>', 0), cmp(e(4, c), '<=', e(semi, 6))),
                                             lambda: 1, lambda: 0)))

    def schedule(c):
        E, F, t = e(amort, 5), e(amort, 6), e(4, c)
        return switch(
            e(amort, 16),
            'Bullet', lambda: IF(cmp(F, '=', t), lambda: 1, lambda: 0),
            'Amortizing', lambda: 1 / (X(F) - E) * IF(
                AND(cmp(e(amort, 15), '=', 0.5), OR(cmp(t, '=', E), cmp(t, '=', F))), lambda: 0.5,
                lambda: IF(AND(cmp(t, '>', E), cmp(t, '<=', F)), lambda: 1, lambda: 0)),
            'Zero-coupon', lambda: IF(cmp(t, '=', F), lambda: 1, lambda: 0),
            'Custom', lambda: e(b + 10, c))
    e.let(amort, ALL, schedule)

    fi, rem, cint, camt, ggd, gfa, gei, eff, base = (b + 20 + 17 * i for i in range(9))   # rows 67, 84, ...
    for k in range(VINT):
        for blk in (fi, rem, cint, camt, ggd, gfa):
            labels(blk + k, k, blk + k)
        for blk in (gei, eff, base):
            labels(blk + k, k, gfa + k)
        y0 = U + k                                                    # issue-year column of vintage k
        later = range(y0 + 1, CY + 1)

        def rate(c, r=fi + k, y0=y0, k=k):                            # FI: interest rate of the vintage
            return X(switch(e(r, 13), 'Fixed', lambda: e(ityp, y0), 'Floating', lambda: e(ityp, c),
                            'Zero-coupon', lambda: IF(cmp(e(3, c), '=', e(r, 9)),
                                                      lambda: (1 + x(ityp, y0)) ** e(r, 6) - 1, lambda: 0))
                     ) * e(semi, c - k)
        e.let(fi + k, range(y0, CY + 1), rate)
        # GGDR_PCT: share of principal still outstanding
        if k == 0:
            e.let(rem, range(U + 1, AJ), lambda c: 1 - xsum(e(amort, j) for j in range(U, c)))
            e.let(rem, range(AJ, CY + 1), lambda c: 1 - xsum(e(amort, j) for j in range(U, c + 1)))
        else:
            e.let(rem + k, later, lambda c, k=k: 1 - xsum(e(amort, j) for j in range(U, c - k)))
        # ISS_CALC_INT / ISS_CALC_AMT: interest and amortization falling due per unit issued in year k
        e.let(cint + k, range(y0, CY + 1), lambda c, k=k, y0=y0: x(cur, y0) * e(mkt, c) * e(fi + k, c)
              * e(rem + k, c) / e(mkt, y0))
        e.let(camt + k, range(y0, CY + 1), lambda c, k=k, y0=y0: x(cur, y0) * e(mkt, c) * e(amort, c - k)
              / e(mkt, y0))
        # GGD: stock outstanding (issued, then less amortization), and its holder breakdown
        e.let(ggd + k, y0, lambda c: x(iss, c) / e(mkt, c))
        e.let(ggd + k, later, lambda c, r=ggd + k, k=k: x(r, c - 1) - e(gfa + k, c))
        for shcol, first, shrow in HOLDERS:
            s, f = ci(shcol), ci(first)
            e.let(ggd + k, s, lambda c, y0=y0, shrow=shrow: e(b + shrow, y0))
            e.let(ggd + k, range(f + k, f + VINT), lambda c, r=ggd + k, s=s, f=f: x(r, s) * e(r, U + c - f))
        # GGFA: amortization
        e.let(gfa + k, range(y0, CY + 1), lambda c, k=k, y0=y0: x(amort, c - k) * e(ggd + k, y0))
        # INT_BASE: stock interest is paid on (average of the year for semiannual payers)
        def ibase(c, r=base + k, s=ggd + k):
            return IF(cmp(e(r, 15), '=', 1), lambda: e(s, c - 1), lambda: average([e(s, c - 1), e(s, c)]))
        e.let(base + k, y0, lambda c, s=ggd + k: e(s, c))
        e.let(base + k, later, ibase)
        # GGEI: interest
        e.let(gei + k, y0, lambda c, k=k: x(fi + k, c) * e(ggd + k, c))
        e.let(gei + k, later, lambda c, k=k, r=gei + k: x(fi + k, c) * IF(
            cmp(e(r, 15), '=', 1), lambda: e(ggd + k, c - 1), lambda: average([e(ggd + k, c - 1), e(ggd + k, c)])))
        # EFF_IR: the vintage's contribution to the effective rate on same-year, same-currency debt

        def effir(c, r=eff + k, k=k):
            ib = e(base + k, c)
            return IF(cmp(ib, '=', 0), lambda: 0, lambda: x(fi + k, c) * ib / e.both(
                c, 'Q', '=INT_BASE', 'G', cat('=', e(r, 7)), 'K', cat('=', e(r, 11))))
        e.let(eff + k, range(y0, CY + 1), effir)


def _len(s):
    s = val(s)
    return s if iserr(s) else len(text(s))


def _right(s, n):
    s, n = val(s), val(n)
    e = err(s, n)
    if e:
        return e
    s, n = text(s), int(num(n))
    return s[len(s) - n:] if n > 0 else ''
