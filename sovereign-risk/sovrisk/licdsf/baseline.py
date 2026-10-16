"""LIC DSF baseline sheets, and the formula runtime the LIC baseline/stress/PV-stress ports share.

- Baseline - public:            the public-debt baseline: debt dynamics, debt-creating flows, PV of debt, gross
  financing need and the macro/fiscal assumptions (historical years from Macro-Debt_Data, projections from the
  inputs), plus historical and projection averages and standard deviations.
- Baseline - external:          the same for external PPG debt: current account, FDI, exports, debt service,
  PV of external debt and the external ratios, with their historical statistics.
- Customized Scenario - public: a user-tailored version of the public baseline (shocks entered on the sheet),
  with its own residual financing block (new external/domestic borrowing, its interest, amortization and PV).
- Customized Scenario-External: the external counterpart of the customized scenario.

Each sheet is a list of rules, one per run of cells that share a formula (see the runtime below); rows carry the
row label of the template as a comment.
"""
# ===================================================================== formula runtime
# The sheets below are written as one rule per run of cells that share a formula: s.put(row, 'F:Y', lambda c: ...)
# for a run over year columns (c is the column number), s.cell('C11', lambda: ...) for a single cell. Rules are
# evaluated lazily, so a cell may use any other cell of its sheet regardless of where it sits. Values are wrapped
# in X so that Excel's arithmetic (errors propagate, blank = 0, text -> #VALUE!) reads like ordinary operators.
import math
import sys
import threading

from sovrisk.srdsf.book import ci, cl
from sovrisk.srdsf.xl import DIV0, NA, VALUE, eq, iserr, isnumber

NUM = '#NUM!'
REF = '#REF!'


def _col(c):
    return ci(c) if isinstance(c, str) else c


def _num(v):
    """A value as arithmetic sees it: a number, or an error string."""
    if v is None:
        return 0.0
    if isinstance(v, bool):
        return 1.0 if v else 0.0
    if isinstance(v, (int, float)):
        return v
    if iserr(v):
        return v
    try:
        return float(v)                     # numbers stored as text
    except ValueError:
        return VALUE


def _text(v):
    """A value as Excel's & operator writes it."""
    if v is None:
        return ''
    if isinstance(v, bool):
        return 'TRUE' if v else 'FALSE'
    if isinstance(v, (int, float)):
        if float(v).is_integer() and abs(v) < 1e15:
            return str(int(v))
        return format(v, '.15g')
    return v


def _rank(v):
    """Excel's comparison order: numbers < text < logicals."""
    if isinstance(v, bool):
        return 2
    if isinstance(v, str):
        return 1
    return 0


def _cmp(a, b):
    """-1/0/1 comparing two values as Excel does, or an error string."""
    if iserr(a):
        return a
    if iserr(b):
        return b
    if a is None:
        a = '' if isinstance(b, str) else (False if isinstance(b, bool) else 0)
    if b is None:
        b = '' if isinstance(a, str) else (False if isinstance(a, bool) else 0)
    ra, rb = _rank(a), _rank(b)
    if ra != rb:
        return -1 if ra < rb else 1
    if ra == 1:
        a, b = a.lower(), b.lower()
    elif ra == 0 and a != b and abs(a - b) <= 1e-15 * max(abs(a), abs(b)):
        return 0                            # Excel compares numbers to about 15 significant digits
    return (a > b) - (a < b)


def _arith(f, a, b):
    a, b = _num(a), _num(b)
    if isinstance(a, str):
        return X(a)
    if isinstance(b, str):
        return X(b)
    try:
        r = f(a, b)
    except ZeroDivisionError:
        return X(DIV0)
    except (OverflowError, ValueError):
        return X(NUM)
    if isinstance(r, complex) or (isinstance(r, float) and (math.isinf(r) or math.isnan(r))):
        return X(NUM)
    return X(r)


def _pow(a, b):
    if a == 0 and b < 0:
        raise ZeroDivisionError
    return a ** b


def _v(x):
    return x.v if isinstance(x, X) else x


class X:
    """One Excel value (number, text, bool, error string or None for blank) with Excel's operators:
    + - * / ** and unary -, & for text concatenation, and the six comparisons."""
    __slots__ = ('v',)
    __hash__ = None

    def __init__(self, v):
        self.v = v.v if isinstance(v, X) else v

    def __repr__(self):
        return f'X({self.v!r})'

    def __add__(self, o): return _arith(lambda a, b: a + b, self.v, _v(o))
    def __radd__(self, o): return _arith(lambda a, b: a + b, _v(o), self.v)
    def __sub__(self, o): return _arith(lambda a, b: a - b, self.v, _v(o))
    def __rsub__(self, o): return _arith(lambda a, b: a - b, _v(o), self.v)
    def __mul__(self, o): return _arith(lambda a, b: a * b, self.v, _v(o))
    def __rmul__(self, o): return _arith(lambda a, b: a * b, _v(o), self.v)
    def __truediv__(self, o): return _arith(lambda a, b: a / b, self.v, _v(o))
    def __rtruediv__(self, o): return _arith(lambda a, b: a / b, _v(o), self.v)
    def __pow__(self, o): return _arith(_pow, self.v, _v(o))
    def __rpow__(self, o): return _arith(_pow, _v(o), self.v)

    def __neg__(self):
        return _arith(lambda a, b: -b, 0, self.v)

    def __pos__(self):
        return self

    def __and__(self, o):
        return CONCATENATE(self, o)

    def __rand__(self, o):
        return CONCATENATE(o, self)

    def _c(self, o, test):
        r = _cmp(self.v, _v(o))
        return X(r) if isinstance(r, str) else X(test(r))

    def __eq__(self, o): return self._c(o, lambda r: r == 0)
    def __ne__(self, o): return self._c(o, lambda r: r != 0)
    def __lt__(self, o): return self._c(o, lambda r: r < 0)
    def __le__(self, o): return self._c(o, lambda r: r <= 0)
    def __gt__(self, o): return self._c(o, lambda r: r > 0)
    def __ge__(self, o): return self._c(o, lambda r: r >= 0)

    def __bool__(self):
        raise TypeError('use IF() to test an Excel value')


class Cell(X):
    """A cell of the sheet being computed, read only when its value is used. So IF and CHOOSE evaluate just the
    branch they return, as Excel does (the template has cells whose untaken branch would be circular)."""
    __slots__ = ('calc', 'r', 'c')

    def __init__(self, calc, r, c):
        self.calc, self.r, self.c = calc, r, c

    @property
    def v(self):
        return self.calc.value(self.r, self.c)

    def __repr__(self):
        return f'Cell({cl(self.c)}{self.r})'


def _x(v):
    return v if isinstance(v, X) else X(v)


class Rng:
    """The values of a rectangular range, row by row."""
    __slots__ = ('rows',)

    def __init__(self, rows):
        self.rows = rows

    def values(self):
        return [v for row in self.rows for v in row]


def _flat(args):
    """Values of the arguments of SUM-like functions: (value, came_from_range)."""
    for a in args:
        if isinstance(a, Rng):
            for v in a.values():
                yield v, True
        else:
            yield _v(a), False


def _numbers(args):
    """The numbers SUM/AVERAGE/MIN/MAX/STDEV use: in ranges only numbers count, direct arguments are converted;
    an error anywhere is returned as a string."""
    out = []
    for v, inrange in _flat(args):
        if iserr(v):
            return v
        if inrange:
            if isnumber(v):
                out.append(v)
        else:
            n = _num(v)
            if isinstance(n, str):
                return n
            out.append(n)
    return out


def _truth(v):
    """IF's test: True/False, or an error string."""
    if iserr(v):
        return v
    if v is None:
        return False
    if isinstance(v, str):
        if v.lower() in ('true', 'false'):
            return v.lower() == 'true'
        return VALUE
    return bool(v)


def IF(test, yes, no=False):
    t = _truth(_v(test))
    if isinstance(t, str):
        return X(t)
    return _x(yes if t else no)


def AND(*args):
    out = True
    for v, inrange in _flat(args):
        if iserr(v):
            return X(v)
        if v is None or (isinstance(v, str) and inrange):
            continue
        t = _truth(v)
        if isinstance(t, str):
            return X(t)
        out = out and t
    return X(out)


def CHOOSE(i, *options):
    i = _num(_v(i))
    if isinstance(i, str):
        return X(i)
    i = int(i)
    if i < 1 or i > len(options):
        return X(VALUE)
    return _x(options[i - 1])


def ISNUMBER(x):
    return X(isnumber(_v(x)))


def ISTEXT(x):
    v = _v(x)
    return X(isinstance(v, str) and not iserr(v))


def SUM(*args):
    xs = _numbers(args)
    return X(xs if isinstance(xs, str) else sum(xs))


def AVERAGE(*args):
    xs = _numbers(args)
    if isinstance(xs, str):
        return X(xs)
    return X(sum(xs) / len(xs)) if xs else X(DIV0)


def MIN(*args):
    xs = _numbers(args)
    return X(xs if isinstance(xs, str) else (min(xs) if xs else 0))


def MAX(*args):
    xs = _numbers(args)
    return X(xs if isinstance(xs, str) else (max(xs) if xs else 0))


def STDEV(*args):
    xs = _numbers(args)
    if isinstance(xs, str):
        return X(xs)
    if len(xs) < 2:
        return X(DIV0)
    m = sum(xs) / len(xs)
    return X(math.sqrt(sum((x - m) ** 2 for x in xs) / (len(xs) - 1)))


def NPV(rate, *args):
    """NPV(rate, values...): numbers in ranges count (blanks and text are skipped and take no period)."""
    r = _num(_v(rate))
    if isinstance(r, str):
        return X(r)
    xs = _numbers(args)
    if isinstance(xs, str):
        return X(xs)
    if r == -1:
        return X(DIV0)
    return X(sum(x / (1 + r) ** (i + 1) for i, x in enumerate(xs)))


def ROUNDDOWN(x, d=0):
    x, d = _num(_v(x)), _num(_v(d))
    if isinstance(x, str):
        return X(x)
    if isinstance(d, str):
        return X(d)
    m = 10 ** int(d)
    return X(math.copysign(math.floor(abs(x) * m) / m, x))


def CONCATENATE(*args):
    vs = [_v(a) for a in args]
    for v in vs:
        if iserr(v):
            return X(v)
    return X(''.join(_text(v) for v in vs))


def TEXT(x, fmt):
    """TEXT for the formats the template uses: '#' (whole number); text passes through unchanged."""
    v, f = _v(x), _v(fmt)
    if iserr(v):
        return X(v)
    if isinstance(v, str) or v is None:
        return X('' if v is None else v)
    if f == '#':
        n = math.floor(abs(v) + 0.5)
        return X(('-' if v < 0 and n else '') + (str(n) if n else ''))
    raise NotImplementedError(f'TEXT format {f!r}')


class Ref:
    """A sheet as formulas see it: S[row, col] (col a number or letters) and S['B7'] give one cell's X,
    S.rng(r0, c0, r1, c1) a range. For the sheet being computed, reading a formula cell computes it first."""

    def __init__(self, calc, name):
        self.calc, self.name = calc, name
        self.own = name == calc.name
        self.S = calc.book[name]

    def __getitem__(self, k):
        if isinstance(k, str):
            from sovrisk.srdsf.book import split
            c, r = split(k)
        else:
            r, c = k
            c = _col(c)
        if self.own:
            return Cell(self.calc, r, c)
        return X(self.S.get(r, c))

    def rng(self, r0, c0, r1, c1):
        c0, c1 = _col(c0), _col(c1)
        get = self.calc.value if self.own else self.S.get
        return Rng([[get(r, c) for c in range(c0, c1 + 1)] for r in range(r0, r1 + 1)])

    def cells(self, r, c0, c1):
        """The cells r!c0..r!c1 one by one (for CHOOSE)."""
        return [self[r, c] for c in range(_col(c0), _col(c1) + 1)]

    def ii(self, r0, c0, r1, c1, r, c):
        c = _col(c)
        """A range used where one value is expected: Excel takes the cell in the formula's own row or column."""
        c0, c1 = _col(c0), _col(c1)
        if r0 == r1 and c0 <= c <= c1:
            return self[r0, c]
        if c0 == c1 and r0 <= r <= r1:
            return self[r, c0]
        return X(VALUE)

    def offset(self, r, c, dr, dc):
        """OFFSET(cell, dr, dc) of a single cell."""
        dr, dc = _num(_v(dr)), _num(_v(dc))
        for d in (dr, dc):
            if isinstance(d, str):
                return X(d)
        return self[r + int(dr), _col(c) + int(dc)]


class Calc:
    """Rules of one sheet and their lazy evaluation into book[sheet]."""

    def __init__(self, book, name):
        self.book, self.name = book, name
        self.S = book[name]
        self.rules = {}
        self.busy = set()
        self.stack = []
        self.done = set()
        self.refs = {}

    def sheet(self, name):
        if name not in self.refs:
            self.refs[name] = Ref(self, name)
        return self.refs[name]

    def name_(self, nm):
        return X(self.book.name(nm))

    def put(self, row, cols, fn):
        """fn(c) computes each cell of row `row` in the columns 'F:Y' (or 'F')."""
        a, _, b = cols.partition(':')
        for c in range(ci(a), ci(b or a) + 1):
            self.rules[(row, c)] = (fn, c)

    def cell(self, ref, fn):
        from sovrisk.srdsf.book import split
        c, r = split(ref)
        self.rules[(r, c)] = (fn, None)

    def same(self, ref, col, rows):
        """Each of these rows shows the same cell (column col) of the sheet ref."""
        for r in rows:
            self.rules[(r, ci(col))] = (lambda r=r: ref[r, col], None)

    def drop(self, row, cols):
        """No formula in these cells on this sheet (they are inputs or blank)."""
        a, _, b = cols.partition(':')
        for c in range(ci(a), ci(b or a) + 1):
            self.rules.pop((row, c), None)

    def value(self, r, c):
        k = (r, c)
        if k in self.rules and k not in self.done:
            if k in self.busy:
                raise RuntimeError(f'circular reference at {self.name}!{cl(c)}{r}: ' + ' '.join(f'{cl(b)}{a}' for a, b in self.stack))
            self.busy.add(k)
            self.stack.append(k)
            fn, col = self.rules[k]
            v = _v(fn() if col is None else fn(col))
            self.S.set(r, c, 0 if v is None else v)
            self.busy.discard(k)
            self.stack.pop()
            self.done.add(k)
        return self.S.get(r, c)

    def run(self):
        """Evaluate every rule. Chains of cells (year after year, row after row) recurse deeply, so this runs in
        a thread with a large stack."""
        out = []

        def work():
            try:
                for r, c in sorted(self.rules):
                    self.value(r, c)
            except BaseException as e:          # re-raised in the caller's thread
                out.append(e)
        old_limit, old_stack = sys.getrecursionlimit(), threading.stack_size()
        sys.setrecursionlimit(max(old_limit, 200000))
        threading.stack_size(512 * 1024 * 1024)
        try:
            t = threading.Thread(target=work)
            t.start()
            t.join()
        finally:
            threading.stack_size(old_stack)
            sys.setrecursionlimit(old_limit)
        if out:
            raise out[0]


def TR(s, row):
    """The template's language switch: translation!C<row> (English), D (French), E (Portuguese) or F."""
    lang, T = s.sheet('START')['L10'], s.sheet('translation')
    return IF(lang == 'English', T[row, 'C'], IF(lang == 'French', T[row, 'D'],
              IF(lang == 'Portuguese', T[row, 'E'], T[row, 'F'])))

SHEETS = ['Baseline - public', 'Baseline - external', 'Customized Scenario - public', 'Customized Scenario-External']

QUIRKS = [
    'Baseline - public!O24 and X24 (revenue and grants, historical years) test ISNUMBER of the ratio with Macro-Debt_Data row 60 where every other year tests it with row 59 (all years divide by row 60).',
    'Baseline - public!AN54, AN62, AN63 and AN66 average T:AH (one year early) where the other projection averages of column AN use U:AI.',
    'Baseline - external!N46 multiplies row 35 (PV of PPG external debt-to-GDP) by row 48, where O46 onwards use row 19 (exports).',
    "Baseline - external!C31 and D50, H50:L50 refer to deleted cells (#REF!) of Macro-Debt_Data / Ext_Debt_Data; their ISNUMBER tests fail, so they show '...' / '…'.",
    "Customized Scenario - public rows 91, 93, 104 and 106 (amortization by CHOOSE over the disbursement row) have a #REF! as the 22nd option, so that year's disbursement can never be picked (and the options after it are shifted by one year).",
    'Excel compares numbers to about 15 significant digits: two values that differ only in the last bits are equal for =, <, > (this matters in C4_Market_financing!E98, see stress.QUIRKS).',
]


def _baseline_public(s):
    """Baseline - public"""
    B3E = s.sheet('B3_Exports_ext')
    B4E = s.sheet('B4_other flows_ext')
    BE = s.sheet('Baseline - external')
    C4E = s.sheet('C4_Market_financing')
    IN1 = s.sheet('Input 1 - Basics')
    LK = s.sheet('lookup')
    MD = s.sheet('Macro-Debt_Data')
    O12 = s.sheet('Output 1-2 - Public DSA')
    START = s.sheet('START')
    TRS = s.sheet('translation')
    S = s.sheet(s.name)
    LANG = s.name_('LANG')
    # 2 Baseline Scenario
    s.cell('B2', lambda: TR(s, 1765))
    # 3 (In percent of GDP, unless otherwise indicated)
    s.cell('B3', lambda: O12['B3'])
    # 6
    s.cell('F6', lambda: O12['E5'])
    # 7
    s.put(7, 'D:N', lambda c: S[7, c+1] - 1)
    s.cell('O7', lambda: MD['U4'])
    s.put(7, 'P:AI', lambda c: S[7, c-1] + 1)
    s.cell('AP7', lambda: CONCATENATE(S['O7'], ' - ', S['AI7']))
    # 9
    s.put(9, 'C:AI', lambda c: S[9, c-1] + 1)
    # 10
    s.cell('O10', lambda: IF(START['L10'] == 'English', TRS['C1764'], IF(START['L10'] == 'French', TRS['D1765'], IF(START['L10'] == 'Portuguese', TRS['E1764'], TRS['F1764']))))
    # 12 Public sector debt 1/
    s.cell('B12', lambda: O12['B8'])
    s.put(12, 'D:L', lambda c: IF(ISNUMBER(MD[80, c+6] / S[52, c]), 100 * MD[80, c+6] / S[52, c], '...'))
    s.put(12, 'M:AI', lambda c: IF(ISNUMBER(MD[80, c+6]), 100 * MD[80, c+6] / S[52, c], '...'))
    # 14 of which: foreign-currency denominated
    s.cell('B14', lambda: TRS.offset(2010, 'C', 0, LANG))
    s.put(14, 'D:R', lambda c: IF(ISNUMBER(MD[83, c+6] / S[52, c]), 100 * MD[83, c+6] / S[52, c], '...'))
    s.put(14, 'S:AI', lambda c: IF(ISNUMBER(MD[83, c+6]), 100 * MD[83, c+6] / S[52, c], '...'))
    # 15 of which: local-currency denominated
    s.cell('B15', lambda: TRS.offset(2011, 'C', 0, LANG))
    s.put(15, 'D:AI', lambda c: S[12, c] - S[14, c])
    # 18 of which: held by non-residents
    s.cell('B18', lambda: TRS.offset(2013, 'C', 0, LANG))
    s.put(18, 'D:AI', lambda c: IF(IN1['C33'] == LK['X4'], BE[13, c-1], ''))
    # 19 of which: held by residents
    s.cell('B19', lambda: TRS.offset(2014, 'C', 0, LANG))
    s.put(19, 'D:AI', lambda c: IF(IN1['C33'] == LK['X4'], S[12, c] - S[18, c], ''))
    # 20 of which: PPG external debt
    s.put(20, 'D:AI', lambda c: MD[81, c+6] / S[52, c] * 100)
    # 21 Change in public sector debt
    s.cell('B21', lambda: O12['B11'])
    s.put(21, 'E:N', lambda c: IF(ISNUMBER(S[12, c] - S[12, c-1]), S[12, c] - S[12, c-1], '…'))
    s.put(21, 'O:AI', lambda c: S[12, c] - S[12, c-1])
    # 22 Identified debt-creating flows
    s.cell('B22', lambda: O12['B12'])
    s.put(22, 'E:N', lambda c: IF(ISNUMBER(S[23, c] + S[27, c] + S[33, c]), S[23, c] + S[27, c] + S[33, c], '…'))
    s.put(22, 'O:AI', lambda c: S[23, c] + S[27, c] + S[33, c])
    # 23 Primary deficit
    s.cell('B23', lambda: O12['B13'])
    s.put(23, 'D:F', lambda c: IF(ISNUMBER(S[26, c] - S[24, c]), S[26, c] - S[24, c], '…'))
    s.put(23, 'G:AI', lambda c: S[26, c] - S[24, c])
    s.cell('AK23', lambda: STDEV(S.rng(23, 'E', 23, 'N')))
    s.cell('AL23', lambda: AVERAGE(S.rng(23, 'E', 23, 'N')))
    s.cell('AM23', lambda: AVERAGE(S.rng(23, 'O', 23, 'T')))
    s.cell('AN23', lambda: AVERAGE(S.rng(23, 'U', 23, 'AI')))
    s.cell('AP23', lambda: AVERAGE(S.rng(23, 'O', 23, 'AI')))
    # 24 Revenue and grants
    s.cell('B24', lambda: O12['B14'])
    s.put(24, 'D:N', lambda c: IF(ISNUMBER(MD[45, c+6] / (MD[56, c+6] * MD[59, c+6])), 100 * MD[45, c+6] / (MD[56, c+6] * MD[60, c+6]), '...'))
    s.cell('O24', lambda: IF(ISNUMBER(MD['U45'] / (MD['U56'] * MD['U60'])), 100 * MD['U45'] / (MD['U56'] * MD['U60']), '...'))
    s.put(24, 'P:W', lambda c: IF(ISNUMBER(MD[45, c+6] / (MD[56, c+6] * MD[59, c+6])), 100 * MD[45, c+6] / (MD[56, c+6] * MD[60, c+6]), '...'))
    s.cell('X24', lambda: IF(ISNUMBER(MD['AD45'] / (MD['AD56'] * MD['AD60'])), 100 * MD['AD45'] / (MD['AD56'] * MD['AD60']), '...'))
    s.put(24, 'Y:AI', lambda c: IF(ISNUMBER(MD[45, c+6] / (MD[56, c+6] * MD[59, c+6])), 100 * MD[45, c+6] / (MD[56, c+6] * MD[60, c+6]), '...'))
    s.cell('AK24', lambda: STDEV(S.rng(24, 'E', 24, 'N')))
    s.cell('AL24', lambda: AVERAGE(S.rng(24, 'E', 24, 'N')))
    s.cell('AM24', lambda: AVERAGE(S.rng(24, 'O', 24, 'T')))
    s.cell('AN24', lambda: AVERAGE(S.rng(24, 'U', 24, 'AI')))
    s.cell('AP24', lambda: AVERAGE(S.rng(24, 'O', 24, 'AI')))
    # 25 of which: grants
    s.cell('B25', lambda: O12['B15'])
    s.put(25, 'D:F', lambda c: IF(ISNUMBER(MD[46, c+6] / S[52, c]), MD[46, c+6] / S[52, c] * 100, '...'))
    s.put(25, 'G:AI', lambda c: IF(ISNUMBER(MD[46, c+6]), MD[46, c+6] / S[52, c] * 100, '...'))
    s.cell('AK25', lambda: STDEV(S.rng(25, 'E', 25, 'N')))
    s.cell('AL25', lambda: AVERAGE(S.rng(25, 'E', 25, 'N')))
    s.cell('AM25', lambda: AVERAGE(S.rng(25, 'O', 25, 'T')))
    s.cell('AN25', lambda: AVERAGE(S.rng(25, 'U', 25, 'AI')))
    s.cell('AP25', lambda: AVERAGE(S.rng(25, 'O', 25, 'AI')))
    # 26 Primary (noninterest) expenditure
    s.cell('B26', lambda: O12['B16'])
    s.put(26, 'D:AI', lambda c: IF(ISNUMBER(MD[48, c+6] / S[52, c]), 100 * (MD[48, c+6] / S[52, c]), '...'))
    s.cell('AK26', lambda: STDEV(S.rng(26, 'E', 26, 'N')))
    s.cell('AL26', lambda: AVERAGE(S.rng(26, 'E', 26, 'N')))
    s.cell('AM26', lambda: AVERAGE(S.rng(26, 'O', 26, 'T')))
    s.cell('AN26', lambda: AVERAGE(S.rng(26, 'U', 26, 'AI')))
    s.cell('AP26', lambda: AVERAGE(S.rng(26, 'O', 26, 'AI')))
    # 27 Automatic debt dynamics
    s.cell('B27', lambda: O12['B17'])
    s.put(27, 'E:G', lambda c: IF(ISNUMBER(S[28, c] + S[31, c]), S[28, c] + S[31, c], '…'))
    s.put(27, 'H:AI', lambda c: S[28, c] + S[31, c])
    # 28 Contribution from interest rate/growth differential
    s.cell('B28', lambda: O12['B18'])
    s.put(28, 'E:AI', lambda c: IF(ISNUMBER(S[29, c] + S[30, c]), S[29, c] + S[30, c], '…'))
    # 29 of which: contribution from average real interest rate
    s.cell('B29', lambda: O12['B19'])
    s.put(29, 'E:N', lambda c: IF(ISNUMBER(S[57, c] / 100 * S[12, c-1] / S[32, c]), S[57, c] / 100 * S[12, c-1] / S[32, c], '…'))
    s.put(29, 'O:AI', lambda c: S[57, c] / 100 * S[12, c-1] / S[32, c])
    # 30 of which: contribution from real GDP growth
    s.cell('B30', lambda: O12['B20'])
    s.put(30, 'E:N', lambda c: IF(ISNUMBER(-(S[53, c] / 100) * (S[12, c-1] / S[32, c])), -(S[53, c] / 100) * (S[12, c-1] / S[32, c]), '…'))
    s.put(30, 'O:AI', lambda c: -(S[53, c] / 100) * (S[12, c-1] / S[32, c]))
    # 31 Contribution from real exchange rate depreciation
    s.cell('B31', lambda: O12['B21'])
    s.put(31, 'E:N', lambda c: IF(ISNUMBER(S[64, c] / 100 * S[14, c-1] * (1 + S[59, c] / 100) / S[32, c]), S[64, c] / 100 * S[14, c-1] * (1 + S[59, c] / 100) / S[32, c], '…'))
    s.put(31, 'O:AI', lambda c: S[64, c] / 100 * S[14, c-1] * (1 + S[59, c] / 100) / S[32, c])
    # 32 Denominator = 1+g
    s.cell('B32', lambda: O12['B22'])
    s.put(32, 'E:AI', lambda c: IF(ISNUMBER(S[53, c]), 1 + S[53, c] / 100, '…'))
    # 33 Other identified debt-creating flows
    s.cell('B33', lambda: O12['B23'])
    s.put(33, 'E:AI', lambda c: SUM(S.rng(34, c, 37, c)))
    # 34 Privatization receipts (negative)
    s.cell('B34', lambda: O12['B24'])
    s.put(34, 'D:AI', lambda c: IF(ISNUMBER(-MD[47, c+6] / S[52, c] * 100), -MD[47, c+6] / S[52, c] * 100, '…'))
    # 35 Recognition of contingent liabilities (e.g., bank recapitalization)
    s.cell('B35', lambda: O12['B25'])
    s.put(35, 'D:AI', lambda c: IF(ISNUMBER(MD[51, c+6] / S[52, c] * 100), MD[51, c+6] / S[52, c] * 100, '…'))
    # 36 Debt relief (HIPC and other)
    s.cell('B36', lambda: O12['B26'])
    s.put(36, 'D:AI', lambda c: IF(ISNUMBER(MD[53, c+6] / S[52, c] * 100), -MD[53, c+6] / S[52, c] * 100, '…'))
    # 37 Other debt creating or reducing flow (please specify)
    s.cell('B37', lambda: O12['B27'])
    s.put(37, 'D:N', lambda c: IF(ISNUMBER(MD[52, c+6] / S[52, c] * 100), MD[52, c+6] / S[52, c] * 100, ' ...'))
    s.put(37, 'O:AI', lambda c: IF(ISNUMBER(MD[52, c+6] / S[52, c] * 100), MD[52, c+6] / S[52, c] * 100, ' ..'))
    # 38 Residual
    s.cell('B38', lambda: O12['B28'])
    s.put(38, 'E:N', lambda c: IF(ISNUMBER(S[21, c] - S[22, c]), S[21, c] - S[22, c], '…'))
    s.put(38, 'O:AI', lambda c: S[21, c] - S[22, c])
    # 40 Public sector debt-to-revenue-and-grants ratio (in percent)
    s.cell('B40', lambda: TRS.offset(1766, 'C', 0, LANG))
    s.put(40, 'D:AI', lambda c: S[12, c] / S[24, c] * 100)
    # 41 Sustainability indicators
    s.cell('B41', lambda: O12['B30'])
    # 42 PV of public debt-to-GDP ratio 2/
    s.cell('B42', lambda: O12['B31'])
    s.put(42, 'D:M', lambda c: IF(ISNUMBER(MD[92, c+6]), (MD[92, c+6] + MD[82, c+6]) / S[52, c] * 100, '...'))
    s.put(42, 'N:AH', lambda c: IF(IF(ISNUMBER(MD[92, c+6]), (MD[92, c+6] + MD[82, c+6]) / S[52, c] * 100, '...') < 0, 0, IF(ISNUMBER(MD[92, c+6]), (MD[92, c+6] + MD[82, c+6]) / S[52, c] * 100, '...')))
    s.cell('AI42', lambda: IF(ISNUMBER(MD['AO92']), (MD['AO92'] + MD['AO82']) / S['AI52'] * 100, '...'))
    # 43 PV of public debt-to-revenue and grants ratio
    s.cell('B43', lambda: O12['B32'])
    s.put(43, 'D:AI', lambda c: IF(ISNUMBER(S[42, c]), S[42, c] / S[24, c] * 100, '…'))
    # 44 PV of public debt-to-revenue ratio
    s.cell('B44', lambda: O12['B33'])
    s.put(44, 'D:AI', lambda c: IF(ISNUMBER(S[42, c]), S[42, c] / (S[24, c] - S[25, c]) * 100, '…'))
    # 45 Debt service-to-revenue and grants ratio 3/
    s.cell('B45', lambda: O12['B35'])
    s.put(45, 'E:AI', lambda c: IF((MD[49, c+6] + MD[16, c+5] + (MD[26, c+6] + MD[24, c+6]) * MD[60, c+6]) / MD[45, c+6] * 100 < 0, 0, (MD[49, c+6] + MD[16, c+5] + (MD[26, c+6] + MD[24, c+6]) * MD[60, c+6]) / MD[45, c+6] * 100))
    # 46 Debt service-to-revenue ratio 3/
    s.cell('B46', lambda: O12['B36'])
    s.put(46, 'E:AI', lambda c: IF((MD[49, c+6] + MD[16, c+5] + (MD[26, c+6] + MD[24, c+6]) * MD[60, c+6]) / (MD[45, c+6] - MD[46, c+6]) * 100 < 0, 0, (MD[49, c+6] + MD[16, c+5] + (MD[26, c+6] + MD[24, c+6]) * MD[60, c+6]) / (MD[45, c+6] - MD[46, c+6]) * 100))
    # 47 Gross financing need 4/
    s.cell('B47', lambda: O12['B37'])
    s.put(47, 'D:AI', lambda c: IF(ISNUMBER(MD[101, c+6] / S[52, c] * 100), MD[101, c+6] / S[52, c] * 100, '…'))
    # 48 in billions of U.S. dollars
    s.cell('B48', lambda: O12['B38'])
    s.put(48, 'D:AI', lambda c: MD[101, c+6] / MD[60, c+6])
    # 51 Key macroeconomic and fiscal assumptions
    s.cell('B51', lambda: O12['B40'])
    # 52 Nominal GDP (local currency)
    s.cell('B52', lambda: O12['B41'])
    s.put(52, 'D:AI', lambda c: MD[56, c+6] * MD[60, c+6])
    # 53 Real GDP growth (in percent)
    s.cell('B53', lambda: O12['B42'])
    s.put(53, 'D:AI', lambda c: IF(ISNUMBER(MD[107, c+6]), MD[107, c+6], '…'))
    s.cell('AK53', lambda: STDEV(S.rng(53, 'E', 53, 'N')))
    s.cell('AL53', lambda: AVERAGE(S.rng(53, 'E', 53, 'N')))
    s.cell('AM53', lambda: AVERAGE(S.rng(53, 'O', 53, 'T')))
    s.cell('AN53', lambda: AVERAGE(S.rng(53, 'U', 53, 'AI')))
    s.cell('AP53', lambda: AVERAGE(S.rng(53, 'O', 53, 'AI')))
    # 54 Average nominal interest rate on public debt (in percent)
    s.cell('B54', lambda: O12['B43'])
    s.put(54, 'E:AI', lambda c: IF(ISNUMBER(100 * MD[49, c+6] / MD[80, c+5]), 100 * MD[49, c+6] / MD[80, c+5], '...'))
    s.cell('AK54', lambda: STDEV(S.rng(54, 'E', 54, 'N')))
    s.cell('AL54', lambda: AVERAGE(S.rng(54, 'E', 54, 'N')))
    s.cell('AM54', lambda: AVERAGE(S.rng(54, 'O', 54, 'T')))
    s.cell('AN54', lambda: AVERAGE(S.rng(54, 'T', 54, 'AH')))
    s.cell('AP54', lambda: AVERAGE(S.rng(54, 'O', 54, 'AI')))
    # 55 Average nominal interest rate on external debt (in percent)
    s.cell('B55', lambda: O12['B44'])
    s.put(55, 'E:AI', lambda c: IF(MD[86, c+6] == 0, S[54, c], MD[86, c+6]))
    s.cell('AK55', lambda: STDEV(S.rng(55, 'E', 55, 'N')))
    s.cell('AL55', lambda: AVERAGE(S.rng(55, 'E', 55, 'N')))
    s.cell('AM55', lambda: AVERAGE(S.rng(55, 'O', 55, 'T')))
    s.cell('AN55', lambda: AVERAGE(S.rng(55, 'U', 55, 'AI')))
    s.cell('AP55', lambda: AVERAGE(S.rng(55, 'O', 55, 'AI')))
    # 56 Average nominal interest rate on domestic debt (in percent)
    s.cell('B56', lambda: O12['B45'])
    s.put(56, 'E:AI', lambda c: IF(ISNUMBER(MD[87, c+6]), MD[87, c+6], S[54, c]))
    s.cell('AK56', lambda: STDEV(S.rng(56, 'E', 56, 'N')))
    s.cell('AL56', lambda: AVERAGE(S.rng(56, 'E', 56, 'N')))
    s.cell('AM56', lambda: AVERAGE(S.rng(56, 'O', 56, 'T')))
    s.cell('AN56', lambda: AVERAGE(S.rng(56, 'U', 56, 'AI')))
    s.cell('AP56', lambda: AVERAGE(S.rng(56, 'O', 56, 'AI')))
    # 57 Average real interest rate (in percent)
    s.cell('B57', lambda: O12['B46'])
    s.put(57, 'E:AI', lambda c: IF(ISNUMBER(S[58, c]), S[14, c-1] / S[12, c-1] * S[59, c] + (1 - S[14, c-1] / S[12, c-1]) * S[58, c], '...'))
    s.cell('AK57', lambda: STDEV(S.rng(57, 'E', 57, 'N')))
    s.cell('AL57', lambda: AVERAGE(S.rng(57, 'E', 57, 'N')))
    s.cell('AM57', lambda: AVERAGE(S.rng(57, 'O', 57, 'T')))
    s.cell('AN57', lambda: AVERAGE(S.rng(57, 'U', 57, 'AI')))
    s.cell('AP57', lambda: AVERAGE(S.rng(57, 'O', 57, 'AJ')))
    # 58 Average real interest rate on domestic debt (in percent)
    s.cell('B58', lambda: O12['B47'])
    s.put(58, 'E:M', lambda c: IF(ISNUMBER((S[56, c] - S[65, c]) / (1 + S[65, c] / 100)), (S[56, c] - S[65, c]) / (1 + S[65, c] / 100), '...'))
    s.put(58, 'N:AI', lambda c: IF(ISNUMBER(S[56, c]), (S[56, c] - S[65, c]) / (1 + S[65, c] / 100), '...'))
    s.cell('AK58', lambda: STDEV(S.rng(58, 'E', 58, 'N')))
    s.cell('AL58', lambda: AVERAGE(S.rng(58, 'E', 58, 'N')))
    s.cell('AM58', lambda: AVERAGE(S.rng(58, 'O', 58, 'T')))
    s.cell('AN58', lambda: AVERAGE(S.rng(58, 'U', 58, 'AI')))
    s.cell('AP58', lambda: AVERAGE(S.rng(58, 'O', 58, 'AJ')))
    # 59 Average real interest rate on external debt (in percent)
    s.cell('B59', lambda: O12['B48'])
    s.put(59, 'E:AI', lambda c: IF(ISNUMBER(S[55, c]), (S[55, c] - S[66, c]) / (1 + S[66, c] / 100), '...'))
    s.cell('AK59', lambda: STDEV(S.rng(59, 'E', 59, 'N')))
    s.cell('AL59', lambda: AVERAGE(S.rng(59, 'E', 59, 'N')))
    s.cell('AM59', lambda: AVERAGE(S.rng(59, 'O', 59, 'T')))
    s.cell('AN59', lambda: AVERAGE(S.rng(59, 'U', 59, 'AI')))
    s.cell('AP59', lambda: AVERAGE(S.rng(59, 'O', 59, 'AJ')))
    # 60 Exchange rate (LC per US dollar)
    s.cell('B60', lambda: O12['B49'])
    s.put(60, 'D:AI', lambda c: IF(ISNUMBER(MD[59, c+6]), MD[59, c+6], '…'))
    s.cell('AP60', lambda: AVERAGE(S.rng(60, 'O', 60, 'AJ')))
    # 61 Nominal depreciation of local currency (percentage change in LC per dollar)
    s.cell('B61', lambda: O12['B50'])
    s.put(61, 'E:AI', lambda c: (S[60, c] / S[60, c-1] - 1) * 100)
    s.cell('AM61', lambda: AVERAGE(S.rng(61, 'O', 61, 'T')))
    s.cell('AN61', lambda: AVERAGE(S.rng(61, 'U', 61, 'AI')))
    s.cell('AP61', lambda: AVERAGE(S.rng(61, 'O', 61, 'AJ')))
    # 62 Exchange rate (US dollar per LC)
    s.cell('B62', lambda: O12['B51'])
    s.put(62, 'D:AI', lambda c: 1 / S[60, c])
    s.cell('AK62', lambda: STDEV(S.rng(62, 'E', 62, 'N')))
    s.cell('AL62', lambda: AVERAGE(S.rng(62, 'E', 62, 'N')))
    s.cell('AM62', lambda: AVERAGE(S.rng(62, 'O', 62, 'T')))
    s.cell('AN62', lambda: AVERAGE(S.rng(62, 'T', 62, 'AH')))
    s.cell('AP62', lambda: AVERAGE(S.rng(62, 'O', 62, 'AJ')))
    # 63 Nominal appreciation (increase in US dollar value of local currency, in percent)
    s.cell('B63', lambda: O12['B52'])
    s.put(63, 'E:AI', lambda c: (S[62, c] / S[62, c-1] - 1) * 100)
    s.cell('AK63', lambda: STDEV(S.rng(63, 'E', 63, 'N')))
    s.cell('AL63', lambda: AVERAGE(S.rng(63, 'E', 63, 'N')))
    s.cell('AM63', lambda: AVERAGE(S.rng(63, 'O', 63, 'T')))
    s.cell('AN63', lambda: AVERAGE(S.rng(63, 'T', 63, 'AH')))
    s.cell('AP63', lambda: AVERAGE(S.rng(63, 'O', 63, 'AJ')))
    # 64 Real exchange rate depreciation (in percent, + indicates depreciation)
    s.cell('B64', lambda: O12['B53'])
    s.put(64, 'E:N', lambda c: IF(ISNUMBER((100 + S[61, c]) * (1 + S[66, c] / 100) / (1 + S[65, c] / 100) - 100), (100 + S[61, c]) * (1 + S[66, c] / 100) / (1 + S[65, c] / 100) - 100, '…'))
    s.put(64, 'O:AI', lambda c: (100 + S[61, c]) * (1 + S[66, c] / 100) / (1 + S[65, c] / 100) - 100)
    s.cell('AM64', lambda: AVERAGE(S.rng(64, 'O', 64, 'T')))
    s.cell('AN64', lambda: AVERAGE(S.rng(64, 'U', 64, 'AI')))
    s.cell('AP64', lambda: AVERAGE(S.rng(64, 'O', 64, 'AJ')))
    # 65 Inflation rate (GDP deflator, in percent)
    s.cell('B65', lambda: O12['B54'])
    s.put(65, 'D:AI', lambda c: IF(ISNUMBER(MD[109, c+6]), MD[109, c+6], '...'))
    s.cell('AK65', lambda: STDEV(S.rng(65, 'E', 65, 'N')))
    s.cell('AL65', lambda: AVERAGE(S.rng(65, 'E', 65, 'N')))
    s.cell('AM65', lambda: AVERAGE(S.rng(65, 'O', 65, 'T')))
    s.cell('AN65', lambda: AVERAGE(S.rng(65, 'U', 65, 'AI')))
    s.cell('AP65', lambda: AVERAGE(S.rng(65, 'O', 65, 'AJ')))
    # 66 US Inflation rate (GDP deflator, in percent)
    s.cell('B66', lambda: O12['B55'])
    s.put(66, 'D:AI', lambda c: IF(ISNUMBER(MD[112, c+6]), MD[112, c+6], '...'))
    s.cell('AK66', lambda: STDEV(S.rng(66, 'E', 66, 'N')))
    s.cell('AL66', lambda: AVERAGE(S.rng(66, 'E', 66, 'N')))
    s.cell('AM66', lambda: AVERAGE(S.rng(66, 'O', 66, 'T')))
    s.cell('AN66', lambda: AVERAGE(S.rng(66, 'T', 66, 'AH')))
    s.cell('AP66', lambda: AVERAGE(S.rng(66, 'O', 66, 'AJ')))
    # 67 Growth of real primary spending (deflated by GDP deflator, in percent)
    s.cell('B67', lambda: O12['B56'])
    s.put(67, 'D:AI', lambda c: IF(ISNUMBER(MD[100, c+6]), MD[100, c+6], '…'))
    s.cell('AK67', lambda: STDEV(S.rng(67, 'E', 67, 'N')))
    s.cell('AL67', lambda: AVERAGE(S.rng(67, 'E', 67, 'N')))
    s.cell('AM67', lambda: AVERAGE(S.rng(67, 'O', 67, 'T')))
    s.cell('AN67', lambda: AVERAGE(S.rng(67, 'U', 67, 'AI')))
    s.cell('AP67', lambda: AVERAGE(S.rng(67, 'O', 67, 'AJ')))
    # 68 Primary deficit that stabilizes the debt-to-GDP ratio 5/
    s.cell('B68', lambda: O12['B57'])
    # 69 PV of contingent liabilities (not included in public sector debt)
    s.cell('B69', lambda: O12['B58'])
    s.put(69, 'D:AI', lambda c: IF(ISNUMBER(MD[91, c+6]), MD[91, c+6] / S[52, c] * 100, '...'))
    # 72 1/ Coverage of debt: The central government plus social security, central bank, governm...
    s.cell('B72', lambda: O12['B62'])
    # 73 4/ Gross financing need is defined as the primary deficit plus debt service plus the st...
    s.cell('B73', lambda: O12['B65'])
    # 76 National Currency
    s.cell('B76', lambda: MD['C80'])
    # 77 Nominal Debt
    s.cell('B77', lambda: TR(s, 1767))
    s.put(77, 'M:AI', lambda c: S[12, c] / 100 * S[52, c])
    # 78 Gross financing need 4/
    s.cell('B78', lambda: S['B47'])
    s.put(78, 'M:AI', lambda c: S[47, c] / 100 * S[52, c])
    # 82 (GFNs > 14 percent of GDP)
    s.put(82, 'M:W', lambda c: IF(S[47, c+2] > 14, 1, 0))
    s.put(82, 'X:Y', lambda c: IF(S[47, c+2] > S['B82'], 1, 0))
    # 83
    s.cell('O83', lambda: IF(MAX(S.rng(82, 'O', 82, 'Q')) == 1, 'YES', 'NO'))
    # 87 Debt service in LCU baseline
    s.put(87, 'O:AI', lambda c: MD[49, c+6] + MD[16, c+5] + (MD[26, c+6] + MD[24, c+6]) * MD[60, c+6])
    # 88 PV of public debt (level) in LCU baseline
    s.put(88, 'O:AI', lambda c: S[42, c] * S[52, c] / 100)
    # 90 PV of public debt-to-GDP ratio (Baseline)
    s.put(90, 'O:AI', lambda c: S[88, c] / S[52, c] * 100)
    # 91 PV of public debt-to-GDP ratio (B3 - Exports)
    s.put(91, 'O:AI', lambda c: (S[88, c] + B3E[89, c-11] * S[60, c]) / S[52, c] * 100)
    # 92 PV of public debt-to-GDP ratio (B4 - Other flows)
    s.put(92, 'O:AI', lambda c: (S[88, c] + B4E[89, c-11] * S[60, c]) / S[52, c] * 100)
    # 93 PV of public debt-to-GDP ratio (C4 - Mkt Fin)
    s.put(93, 'O:AI', lambda c: (S[88, c] + C4E[77, c-11] * S[60, c]) / S[52, c] * 100)
    # 95 PV of public debt-to-revenue and grants ratio (Baseline)
    s.put(95, 'O:AI', lambda c: S[90, c] / S[24, c] * 100)
    # 96 PV of public debt-to-revenue and grants ratio (B3 - Exports)
    s.put(96, 'O:AI', lambda c: S[91, c] / S[24, c] * 100)
    # 97 PV of public debt-to-revenue and grants ratio (B4 - Other flows)
    s.put(97, 'O:AI', lambda c: S[92, c] / S[24, c] * 100)
    # 98 PV of public debt-to-revenue and grants ratio (C4 - Mkt Fin)
    s.put(98, 'O:AI', lambda c: S[93, c] / S[24, c] * 100)
    # 100 Debt service in LCU B3 (Export stress test)
    s.put(100, 'O:AI', lambda c: S[87, c] + B3E[98, c-11] * S[114, c])
    # 101 Debt service in LCU B4 (Other flows stress test)
    s.put(101, 'O:AI', lambda c: S[87, c] + B4E[98, c-11] * S[114, c])
    # 102 Debt service in LCU C4 (Market stress test)
    s.put(102, 'O:AI', lambda c: S[87, c] + C4E[89, c-11] * S[114, c])
    # 104 Debt service-to-revenue and grants ratio (Bseline)
    s.put(104, 'O:AI', lambda c: S[87, c] / MD[45, c+6] * 100)
    # 105 Debt service-to-revenue and grants ratio (B3 - Exports)
    s.put(105, 'O:AI', lambda c: S[100, c] / MD[45, c+6] * 100)
    # 106 Debt service-to-revenue and grants ratio (B4 - Other flows)
    s.put(106, 'O:AI', lambda c: S[101, c] / MD[45, c+6] * 100)
    # 107 Debt service-to-revenue and grants ratio (C4 - Mkt Fin)
    s.put(107, 'O:AI', lambda c: S[102, c] / MD[45, c+6] * 100)
    # 109 Debt service-to-GDP ratio (Baseline)
    s.put(109, 'O:AI', lambda c: S[104, c] * S[24, c] / 100)
    # 110 Debt service-to-GDP ratio (B3 - Exports)
    s.put(110, 'O:AI', lambda c: S[105, c] * S[24, c] / 100)
    # 111 Debt service-to-GDP ratio (B4 - Other flows)
    s.put(111, 'O:AI', lambda c: S[106, c] * S[24, c] / 100)
    # 112 Debt service-to-GDP ratio (C4 - Mkt Fin)
    s.put(112, 'O:AI', lambda c: S[107, c] * S[24, c] / 100)
    # 114
    s.put(114, 'O:AI', lambda c: MD[60, c+6])


def _baseline_external(s):
    """Baseline - external"""
    A1E = s.sheet('A1_historical_ext')
    EDD = s.sheet('Ext_Debt_Data')
    MD = s.sheet('Macro-Debt_Data')
    O11 = s.sheet('Output 1-1 - External DSA')
    TRS = s.sheet('translation')
    S = s.sheet(s.name)
    LANG = s.name_('LANG')
    # 3 Baseline Scenario
    s.cell('B3', lambda: TR(s, 1765))
    # 4 (In percent of GDP, unless otherwise indicated)
    s.cell('B4', lambda: O11.ii(4, 'B', 4, 'AN', 4, 'B'))
    # 7 Actual
    s.cell('C7', lambda: O11['E5'])
    s.cell('N7', lambda: O11['P5'])
    # 8
    s.put(8, 'C:M', lambda c: S[8, c+1] - 1)
    s.cell('N8', lambda: MD['U4'])
    s.put(8, 'O:AH', lambda c: S[8, c-1] + 1)
    # 10 I. Baseline Medium Term Projections
    s.cell('B10', lambda: TRS.offset(1764, 'C', 0, LANG))
    # 12 External debt (nominal) 1/
    s.cell('B12', lambda: O11['B8'])
    s.put(12, 'C:AH', lambda c: IF(AND(ISNUMBER(S[13, c]), ISNUMBER(S[14, c])), S[13, c] + S[14, c], '…'))
    # 13 of which: public and publicly guaranteed (PPG)
    s.cell('B13', lambda: O11['B9'])
    s.put(13, 'C:AH', lambda c: IF(ISNUMBER(MD[81, c+7] / (MD[56, c+7] * MD[60, c+7])), 100 * MD[81, c+7] / (MD[56, c+7] * MD[60, c+7]), '…'))
    # 14 of which: Private
    s.cell('B14', lambda: TR(s, 1842))
    s.put(14, 'C:AH', lambda c: MD[70, c+7])
    # 15 Change in external debt
    s.cell('B15', lambda: O11['B11'])
    s.put(15, 'C:M', lambda c: IF(ISNUMBER(S[12, c] - S[12, c-1]), S[12, c] - S[12, c-1], '…'))
    s.put(15, 'N:AH', lambda c: S[12, c] - S[12, c-1])
    s.cell('AI15', lambda: S['AI16'] + S['AI30'])
    # 16 Identified net debt-creating flows
    s.cell('B16', lambda: O11['B12'])
    s.put(16, 'C:M', lambda c: IF(ISNUMBER(S[17, c] + S[24, c] + S[25, c]), S[17, c] + S[24, c] + S[25, c], '…'))
    s.put(16, 'N:AI', lambda c: S[17, c] + S[24, c] + S[25, c])
    # 17 Non-interest current account deficit
    s.cell('B17', lambda: O11['B13'])
    s.put(17, 'C:M', lambda c: IF(ISNUMBER((MD[28, c+7] + MD[18, c+7]) / S[48, c]), -(MD[28, c+7] + MD[18, c+7]) / S[48, c] * 100, '...'))
    s.put(17, 'N:AH', lambda c: -(MD[28, c+7] + MD[18, c+7]) / S[48, c] * 100)
    s.cell('AI17', lambda: -(S['AI24'] + S['AI25']))
    # 18 Deficit in balance of goods and services
    s.cell('B18', lambda: O11['B14'])
    s.put(18, 'C:M', lambda c: IF(ISNUMBER(S[20, c] - S[19, c]), S[20, c] - S[19, c], '…'))
    s.put(18, 'N:AH', lambda c: S[20, c] - S[19, c])
    # 19 Exports
    s.cell('B19', lambda: O11['B15'])
    s.put(19, 'C:M', lambda c: IF(ISNUMBER(MD[29, c+7] / S[48, c] * 100), MD[29, c+7] / S[48, c] * 100, '…'))
    s.put(19, 'N:AH', lambda c: MD[29, c+7] / S[48, c] * 100)
    # 20 Imports
    s.cell('B20', lambda: O11['B16'])
    s.put(20, 'C:M', lambda c: IF(ISNUMBER(MD[30, c+7] / S[48, c] * 100), MD[30, c+7] / S[48, c] * 100, '…'))
    s.put(20, 'N:AH', lambda c: MD[30, c+7] / S[48, c] * 100)
    # 21 Net current transfers (negative = inflow)
    s.cell('B21', lambda: O11['B17'])
    s.put(21, 'C:M', lambda c: IF(ISNUMBER(MD[31, c+7] / MD[56, c+7]), -MD[31, c+7] / MD[56, c+7] * 100, '...'))
    s.put(21, 'N:AH', lambda c: -MD[31, c+7] / MD[56, c+7] * 100)
    # 22 of which: official
    s.cell('B22', lambda: O11['B18'])
    s.put(22, 'C:M', lambda c: IF(ISNUMBER(MD[32, c+7] / MD[56, c+7]), -MD[32, c+7] / MD[56, c+7] * 100, '...'))
    s.put(22, 'N:AH', lambda c: -MD[32, c+7] / MD[56, c+7] * 100)
    # 23 Other current account flows (negative = net inflow)
    s.cell('B23', lambda: O11['B19'])
    s.put(23, 'C:M', lambda c: IF(ISNUMBER(S[17, c] - S[18, c] - S[21, c]), S[17, c] - S[18, c] - S[21, c], '…'))
    s.put(23, 'N:AH', lambda c: S[17, c] - S[18, c] - S[21, c])
    # 24 Net FDI (negative = inflow)
    s.cell('B24', lambda: O11['B20'])
    s.put(24, 'C:M', lambda c: IF(ISNUMBER(MD[34, c+7] / S[48, c]), -MD[34, c+7] / S[48, c] * 100, '…'))
    s.put(24, 'N:AH', lambda c: -MD[34, c+7] / S[48, c] * 100)
    s.cell('AI24', lambda: S['AH24'])
    # 25 Endogenous debt dynamics 2/
    s.cell('B25', lambda: O11['B21'])
    s.put(25, 'C:M', lambda c: IF(ISNUMBER(S[27, c] + S[28, c] + S[29, c]), S[27, c] + S[28, c] + S[29, c], '…'))
    s.put(25, 'N:AI', lambda c: S[27, c] + S[28, c] + S[29, c])
    # 26 Denominator: 1+g+ρ+gρ
    s.cell('B26', lambda: O11['B22'])
    s.put(26, 'C:M', lambda c: IF(ISNUMBER(1 + S[52, c] / 100 + S[53, c] / 100 + S[52, c] / 100 * S[53, c] / 100), 1 + S[52, c] / 100 + S[53, c] / 100 + S[52, c] / 100 * S[53, c] / 100, '…'))
    s.put(26, 'N:AI', lambda c: 1 + S[52, c] / 100 + S[53, c] / 100 + S[52, c] / 100 * S[53, c] / 100)
    # 27 Contribution from nominal interest rate
    s.cell('B27', lambda: O11['B23'])
    s.put(27, 'C:M', lambda c: IF(ISNUMBER(S[54, c] / 100 * S[12, c-1] / S[26, c]), S[54, c] / 100 * S[12, c-1] / S[26, c], '…'))
    s.put(27, 'N:AI', lambda c: S[54, c] / 100 * S[12, c-1] / S[26, c])
    # 28 Contribution from real GDP growth
    s.cell('B28', lambda: O11['B24'])
    s.put(28, 'C:M', lambda c: IF(ISNUMBER(-(S[52, c] / 100) * S[12, c-1] / S[26, c]), -(S[52, c] / 100) * S[12, c-1] / S[26, c], '…'))
    s.put(28, 'N:AI', lambda c: -(S[52, c] / 100) * S[12, c-1] / S[26, c])
    # 29 Contribution from price and exchange rate changes
    s.cell('B29', lambda: O11['B25'])
    s.put(29, 'C:M', lambda c: IF(ISNUMBER(-(S[53, c] / 100 * (1 + S[52, c] / 100)) * S[12, c-1] / S[26, c] + S[43, c-1] * (-S[59, c] / 100) * (1 + S[54, c] / 100) * S[12, c-1] / S[26, c]), -(S[53, c] / 100 * (1 + S[52, c] / 100)) * S[12, c-1] / S[26, c] + S[43, c-1] * (-S[59, c] / 100) * (1 + S[54, c] / 100) * S[12, c-1] / S[26, c], '…'))
    s.put(29, 'N:AH', lambda c: -(S[53, c] / 100 * (1 + S[52, c] / 100)) * S[12, c-1] / S[26, c] + S[43, c-1] * (-S[59, c] / 100) * (1 + S[54, c] / 100) * S[12, c-1] / S[26, c])
    s.cell('AI29', lambda: -(S['AI53'] / 100 * (1 + S['AI52'] / 100)) * S['AH12'] / S['AI26'])
    # 30 Residual 3/
    s.cell('B30', lambda: O11['B26'])
    s.put(30, 'C:M', lambda c: IF(ISNUMBER(S[15, c] - S[16, c]), S[15, c] - S[16, c], '…'))
    s.put(30, 'N:AH', lambda c: S[15, c] - S[16, c])
    # 31 of which: exceptional financing
    s.cell('B31', lambda: O11['B27'])
    s.cell('C31', lambda: IF(ISNUMBER(S['C30']), IF(ISNUMBER(X('#REF!') / MD['J56']), -X('#REF!') / MD['J56'] * 100, '...'), '...'))
    s.put(31, 'D:AH', lambda c: IF(ISNUMBER(S[30, c]), IF(ISNUMBER(MD[35, c+7] / MD[56, c+7]), -MD[35, c+7] / MD[56, c+7] * 100, '...'), '...'))
    # 33 PV of external debt 7/
    s.cell('B33', lambda: O11['B54'])
    s.put(33, 'M:AH', lambda c: S[35, c] + MD[70, c+7])
    # 34 In percent of exports
    s.cell('B34', lambda: O11['B55'])
    s.put(34, 'M:AH', lambda c: S[33, c] / S[19, c] * 100)
    # 35 PV of PPG external debt-to-GDP ratio
    s.cell('B35', lambda: O11['B30'])
    s.put(35, 'M:AH', lambda c: IF(EDD[391, c-8] / S[48, c] * 100 < 0, 0, EDD[391, c-8] / S[48, c] * 100))
    # 36 PV of PPG external debt-to-exports ratio
    s.cell('B36', lambda: O11['B31'])
    s.put(36, 'M:AH', lambda c: S[35, c] / S[19, c] * 100)
    # 37 PV of PPG external debt-to-revenue ratio
    s.cell('B37', lambda: O11['B32'])
    s.put(37, 'M:AH', lambda c: S[35, c] / S[60, c] * 100)
    # 38 Total external debt service-to-exports ratio
    s.cell('B38', lambda: O11['B56'])
    s.put(38, 'C:AH', lambda c: IF(ISNUMBER((MD[13, c+6] + MD[18, c+7] + MD[23, c+7]) / MD[29, c+7]), (MD[13, c+6] + MD[18, c+7] + MD[23, c+7]) * 100 / MD[29, c+7], '...'))
    # 39 PPG debt service-to-exports ratio
    s.cell('B39', lambda: O11['B33'])
    s.put(39, 'C:L', lambda c: IF(ISNUMBER(S[38, c] - MD[71, c+7]), S[38, c] - MD[71, c+7], '...'))
    s.put(39, 'M:AH', lambda c: IF(IF(ISNUMBER(S[38, c] - MD[71, c+7]), S[38, c] - MD[71, c+7], '...') < 0, 0, IF(ISNUMBER(S[38, c] - MD[71, c+7]), S[38, c] - MD[71, c+7], '...')))
    # 40 PPG debt service-to-revenue ratio
    s.cell('B40', lambda: O11['B34'])
    s.put(40, 'C:L', lambda c: IF(ISNUMBER(S[39, c] * MD[29, c+7] / MD[95, c+7]), S[39, c] * MD[29, c+7] / MD[95, c+7], '…'))
    s.put(40, 'M:AH', lambda c: IF(IF(ISNUMBER(S[39, c] * MD[29, c+7] / MD[95, c+7]), S[39, c] * MD[29, c+7] / MD[95, c+7], '…') < 0, 0, IF(ISNUMBER(S[39, c] * MD[29, c+7] / MD[95, c+7]), S[39, c] * MD[29, c+7] / MD[95, c+7], '…')))
    # 41 Gross external financing need (Million of U.S. dollars)
    s.cell('B41', lambda: O11['B35'])
    s.put(41, 'G:AH', lambda c: MD[74, c+7])
    # 42 Non-interest current account deficit that stabilizes debt ratio
    s.cell('B42', lambda: O11['B59'])
    s.put(42, 'C:M', lambda c: IF(ISNUMBER(-S[15, c] + S[17, c]), -S[15, c] + S[17, c], '…'))
    s.put(42, 'N:AH', lambda c: -S[15, c] + S[17, c])
    # 43 Share of local-currency denominated external debt to total external debt
    s.put(43, 'C:AH', lambda c: MD[85, c+7] / 100)
    # 44 Potential gaps under the BoP (GFNs - external financing)
    s.put(44, 'N:AH', lambda c: -MD[77, c+7] / MD[56, c+7])
    # 46 II. Key macroeconomic assumptions
    s.cell('B46', lambda: 'II.  ' & TEXT(O11['B37'], '3'))
    s.cell('N46', lambda: S['N35'] * S['N48'] / 100)
    s.put(46, 'O:AH', lambda c: S[19, c] * S[48, c] / 100)
    # 48 Nominal GDP (Million of US dollars)
    s.cell('B48', lambda: O11['B50'])
    s.put(48, 'C:AH', lambda c: IF(ISNUMBER(MD[56, c+7]), MD[56, c+7], '...'))
    # 49 Nominal dollar GDP growth
    s.cell('B49', lambda: O11['B51'])
    s.put(49, 'D:M', lambda c: IF(ISNUMBER((S[48, c] / S[48, c-1] - 1) * 100), (S[48, c] / S[48, c-1] - 1) * 100, '…'))
    s.put(49, 'N:AH', lambda c: (S[48, c] / S[48, c-1] - 1) * 100)
    # 50 PV of PPG external debt (in Million of US dollars)
    s.cell('B50', lambda: O11['B57'])
    s.cell('D50', lambda: IF(ISNUMBER(X('#REF!')), X('#REF!'), '…'))
    s.put(50, 'E:F', lambda c: IF(ISNUMBER(EDD[391, c-4]), EDD[391, c-4], '…'))
    s.cell('G50', lambda: IF(ISNUMBER(EDD['D391']), EDD['D391'], '…'))
    s.put(50, 'H:L', lambda c: IF(ISNUMBER(X('#REF!')), X('#REF!'), '…'))
    s.put(50, 'M:AH', lambda c: IF(ISNUMBER(EDD[391, c-8]), EDD[391, c-8], '…'))
    # 51 (PVt-PVt-1)/GDPt-1 (in percent)
    s.cell('B51', lambda: O11['B58'])
    s.put(51, 'N:AH', lambda c: (S[50, c] - S[50, c-1]) / S[48, c-1] * 100)
    # 52 Real GDP growth (in percent)
    s.cell('B52', lambda: O11['B38'])
    s.put(52, 'C:M', lambda c: IF(ISNUMBER(MD[57, c+7] / MD[57, c+6] - 1), (MD[57, c+7] / MD[57, c+6] - 1) * 100, '...'))
    s.put(52, 'N:AH', lambda c: IF(ISNUMBER(MD[57, c+6]), (MD[57, c+7] / MD[57, c+6] - 1) * 100, '...'))
    s.cell('AI52', lambda: S['AH52'])
    # 53 GDP deflator in US dollar terms (change in percent)
    s.cell('B53', lambda: O11['B39'])
    s.put(53, 'C:AH', lambda c: IF(ISNUMBER(MD[111, c+7]), MD[111, c+7], '...'))
    s.cell('AI53', lambda: S['AH53'])
    # 54 Effective interest rate (percent) 4/
    s.cell('B54', lambda: O11['B40'])
    s.put(54, 'D:AH', lambda c: IF(ISNUMBER(MD[18, c+7]), MD[18, c+7] / (S[12, c-1] / 100 * S[48, c-1]) * 100, '...'))
    s.cell('AI54', lambda: S['AH54'])
    # 55 Growth of exports of G&S (US dollar terms, in percent)
    s.cell('B55', lambda: O11['B41'])
    s.put(55, 'C:M', lambda c: IF(ISNUMBER(MD[29, c+7] / MD[29, c+6] - 1), (MD[29, c+7] / MD[29, c+6] - 1) * 100, '...'))
    s.put(55, 'N:AH', lambda c: IF(ISNUMBER(MD[29, c+6]), (MD[29, c+7] / MD[29, c+6] - 1) * 100, '...'))
    # 56 Growth of imports of G&S (US dollar terms, in percent)
    s.cell('B56', lambda: O11['B42'])
    s.put(56, 'C:M', lambda c: IF(ISNUMBER(MD[30, c+7] / MD[30, c+6] - 1), (MD[30, c+7] / MD[30, c+6] - 1) * 100, '...'))
    s.put(56, 'N:AH', lambda c: IF(ISNUMBER(MD[30, c+6]), (MD[30, c+7] / MD[30, c+6] - 1) * 100, '...'))
    # 57 Current transfers, net total
    s.cell('B57', lambda: MD['E31'])
    s.put(57, 'C:AH', lambda c: IF(ISNUMBER(S[21, c]), -S[21, c], '...'))
    # 58 Net foreign direct investment, excluding debt-creating liabilities
    s.cell('B58', lambda: MD['E34'])
    s.put(58, 'C:AH', lambda c: IF(ISNUMBER(S[24, c]), -S[24, c], '...'))
    # 59 Depreciation of NC (+: depreciation)
    s.cell('B59', lambda: MD['E114'])
    s.put(59, 'C:AH', lambda c: IF(ISNUMBER(MD[114, c+7]), MD[114, c+7], '...'))
    # 60 Government revenues (excluding grants, in percent of GDP)
    s.cell('B60', lambda: O11['B44'])
    s.put(60, 'C:AH', lambda c: IF(ISNUMBER(MD[98, c+7]), MD[98, c+7], '...'))
    # 61 Aid flows (in Million of US dollars) 5/
    s.cell('B61', lambda: O11['B45'])
    s.put(61, 'C:AH', lambda c: MD[103, c+7])
    # 62 of which: Grants
    s.cell('B62', lambda: O11['B46'])
    s.put(62, 'C:AH', lambda c: MD[104, c+7])
    # 63 of which: Concessional loans
    s.cell('B63', lambda: O11['B47'])
    s.put(63, 'C:AH', lambda c: MD[105, c+7])
    # 64 Grant-equivalent financing (in percent of GDP) 6/
    s.cell('B64', lambda: O11['B48'])
    s.put(64, 'N:AH', lambda c: (MD[104, c+7] + (EDD[122, c-8] - EDD[407, c-8])) / MD[56, c+7] * 100)
    # 65 Grant-equivalent financing (in percent of external financing) 6/
    s.cell('B65', lambda: O11['B49'])
    s.put(65, 'N:AH', lambda c: (MD[104, c+7] + (EDD[122, c-8] - EDD[407, c-8])) / (MD[104, c+7] + EDD[122, c-8]) * 100)
    # 67
    s.cell('N67', lambda: A1E['D61'])
    s.cell('P67', lambda: A1E['F61'])
    s.cell('S67', lambda: S['N68'])
    s.cell('U67', lambda: S['N68'])
    s.cell('W67', lambda: S['N68'])
    # 68 III. Averages and Standard Deviations 9/
    s.cell('B68', lambda: TR(s, 1840) & ' 9/')
    s.cell('N68', lambda: A1E['D62'])
    s.cell('P68', lambda: A1E['F62'])
    s.cell('S68', lambda: ' ' & TEXT(S['N8'], '#') & '-' & TEXT(S['S8'], '#') & ' ')
    s.cell('U68', lambda: ' ' & TEXT(S['T8'], '#') & '-' & TEXT(S['AH8'], '#') & ' ')
    s.cell('W68', lambda: ' ' & TEXT(S['N8'], '#') & '-' & TEXT(S['AH8'], '#') & ' ')
    s.cell('Y68', lambda: S['W68'])
    # 70 Non-interest current account in percent of GDP
    s.cell('B70', lambda: MD['E72'])
    s.cell('N70', lambda: -AVERAGE(S.rng(17, 'D', 17, 'M')))
    s.cell('P70', lambda: STDEV(S.rng(17, 'D', 17, 'M')))
    s.cell('S70', lambda: -AVERAGE(S.rng(17, 'N', 17, 'S')))
    s.cell('U70', lambda: -AVERAGE(S.rng(17, 'T', 17, 'AH')))
    s.cell('W70', lambda: -AVERAGE(S.rng(17, 'N', 17, 'AH')))
    s.cell('Y70', lambda: STDEV(S.rng(17, 'N', 17, 'AH')))
    # 71 Real GDP growth (in percent)
    s.cell('B71', lambda: S['B52'])
    s.cell('N71', lambda: AVERAGE(S.rng(52, 'D', 52, 'M')))
    s.cell('P71', lambda: STDEV(S.rng(52, 'D', 52, 'M')))
    s.cell('S71', lambda: AVERAGE(S.rng(52, 'N', 52, 'S')))
    s.cell('U71', lambda: AVERAGE(S.rng(52, 'T', 52, 'AH')))
    s.cell('W71', lambda: AVERAGE(S.rng(52, 'N', 52, 'AH')))
    s.cell('Y71', lambda: STDEV(S.rng(52, 'N', 52, 'AH')))
    # 72 US GDP Deflator (percent change)
    s.cell('B72', lambda: MD['E112'])
    s.cell('N72', lambda: AVERAGE(S.rng(53, 'D', 53, 'M')))
    s.cell('P72', lambda: STDEV(S.rng(53, 'D', 53, 'M')))
    s.cell('S72', lambda: AVERAGE(S.rng(53, 'N', 53, 'S')))
    s.cell('U72', lambda: AVERAGE(S.rng(53, 'T', 53, 'AH')))
    s.cell('W72', lambda: AVERAGE(S.rng(53, 'N', 53, 'AH')))
    s.cell('Y72', lambda: STDEV(S.rng(53, 'N', 53, 'AH')))
    # 73 Growth of exports of G&S (US dollar terms, in percent)
    s.cell('B73', lambda: O11['B41'])
    s.cell('N73', lambda: AVERAGE(S.rng(55, 'D', 55, 'M')))
    s.cell('P73', lambda: STDEV(S.rng(55, 'D', 55, 'M')))
    s.cell('S73', lambda: AVERAGE(S.rng(55, 'N', 55, 'S')))
    s.cell('U73', lambda: AVERAGE(S.rng(55, 'T', 55, 'AH')))
    s.cell('W73', lambda: AVERAGE(S.rng(55, 'N', 55, 'AH')))
    s.cell('Y73', lambda: STDEV(S.rng(55, 'N', 55, 'AH')))
    # 74 Current official transfers in percent of GDP
    s.cell('B74', lambda: MD['E73'])
    s.cell('N74', lambda: -AVERAGE(S.rng(21, 'D', 21, 'M')))
    s.cell('P74', lambda: STDEV(S.rng(21, 'D', 21, 'M')))
    s.cell('S74', lambda: -AVERAGE(S.rng(21, 'N', 21, 'S')))
    s.cell('U74', lambda: -AVERAGE(S.rng(21, 'T', 21, 'AH')))
    s.cell('W74', lambda: -AVERAGE(S.rng(21, 'N', 21, 'AH')))
    s.cell('Y74', lambda: STDEV(S.rng(21, 'N', 21, 'AH')))
    # 75 Net non-debt creating flows (FDI) to GDP ratio
    s.cell('B75', lambda: TR(s, 1841))
    s.cell('N75', lambda: -AVERAGE(S.rng(24, 'D', 24, 'M')))
    s.cell('P75', lambda: STDEV(S.rng(24, 'D', 24, 'M')))
    s.cell('S75', lambda: -AVERAGE(S.rng(24, 'N', 24, 'S')))
    s.cell('U75', lambda: -AVERAGE(S.rng(24, 'T', 24, 'AH')))
    s.cell('W75', lambda: -AVERAGE(S.rng(24, 'N', 24, 'AH')))
    s.cell('Y75', lambda: STDEV(S.rng(24, 'N', 24, 'AH')))
    # 77 Sources: Country authorities; and staff estimates and projections.
    s.cell('B77', lambda: O11['B64'])
    # 79 1/ Includes both public and private sector external debt.
    s.cell('B79', lambda: O11['B66'])
    # 80 2/ Derived as [r - g - ρ(1+g) + Ɛα (1+r)]/(1+g+ρ+gρ) times previous period debt ratio, ...
    s.cell('B80', lambda: O11['B67'])
    # 81 3/ Includes exceptional financing (i.e., changes in arrears and debt relief); changes i...
    s.cell('B81', lambda: O11['B68'])
    # 82 4/ Current-year interest payments divided by previous period debt stock.
    s.cell('B82', lambda: O11['B69'])
    # 83 5/ Defined as grants, concessional loans, and debt relief.
    s.cell('B83', lambda: O11['B70'])
    # 84 6/ Grant-equivalent financing includes grants provided directly to the government and t...
    s.cell('B84', lambda: O11['B71'])
    # 85 7/ Assumes that PV of private sector debt is equivalent to its face value.
    s.cell('B85', lambda: O11['B72'])
    # 86 8/ Historical averages are generally derived over the past 10 years, subject to data av...
    s.cell('B86', lambda: O11['B73'])


def _customized_scenario_public(s):
    """Customized Scenario - public"""
    A1P = s.sheet('A1_Historical_pub')
    BE = s.sheet('Baseline - external')
    BP = s.sheet('Baseline - public')
    IN7 = s.sheet('Input 7 - Residual Financing')
    MD = s.sheet('Macro-Debt_Data')
    PVR = s.sheet('PV_ResFin_pub')
    START = s.sheet('START')
    TRS = s.sheet('translation')
    TT = s.sheet('Input 6 - Tailored Tests')
    S = s.sheet(s.name)
    # 1 Please do not change these numbers:
    s.put(1, 'F:Y', lambda c: S[1, c-1] + 1)
    # 3 To include the fiscal customized scenario in charts and tables?
    s.cell('B3', lambda: IF(START['L10'] == 'English', S['A195'], IF(START['L10'] == 'French', S['A196'], IF(START['L10'] == 'Portuguese', S['A197'], S['A198']))))
    # 4 Customized public scenarios: INSTRUCTIONS
    s.cell('A4', lambda: IF(START['L10'] == 'English', S['C195'], IF(START['L10'] == 'French', S['C196'], IF(START['L10'] == 'Portuguese', S['C197'], S['C198']))))
    # 5 This sheet allows the user to model customized shocks to the main fiscal and external v...
    s.cell('B5', lambda: S['A201'])
    # 6 The user can enter alternative data in rows labeled “Delta” for any, a few, or all of t...
    s.cell('B6', lambda: S['A213'])
    # 7 A2. Alternative Scenario :[Customize, enter title]
    s.cell('B7', lambda: TR(s, 725))
    s.put(7, 'C:D', lambda c: MD[5, c+16])
    s.put(7, 'E:Y', lambda c: S[78, c])
    # 10 Revenue and grants
    s.cell('B10', lambda: S['B128'])
    s.put(10, 'E:Y', lambda c: BP[24, c+10] + S[11, c])
    # 12 Primary (noninterest) expenditure
    s.cell('B12', lambda: S['B130'])
    s.put(12, 'E:Y', lambda c: BP[26, c+10] + S[13, c])
    # 14 Grants
    s.put(14, 'E:Y', lambda c: BP[25, c+10] + S[15, c])
    # 16 Public Sector Assets (e.g. Deposits)
    s.cell('B16', lambda: '' & MD['E50'])
    s.put(16, 'C:D', lambda c: MD[50, c+16])
    s.put(16, 'E:Y', lambda c: MD[50, c+16] + S[17, c])
    # 18 Checkline (= 0)
    s.put(18, 'E:Y', lambda c: S[127, c] - (S[130, c] - S[128, c]))
    # 19 Real GDP growth (in percent)
    s.cell('B19', lambda: S['B152'])
    s.put(19, 'E:Y', lambda c: BP[53, c+10] + S[20, c])
    # 21 Inflation rate (GDP deflator, in percent)
    s.cell('B21', lambda: S['B164'])
    s.put(21, 'E:Y', lambda c: BP[65, c+10] + S[22, c])
    # 23 Nominal depreciation of local currency (percentage change in LC per dollar)
    s.cell('B23', lambda: S['B160'])
    s.cell('D23', lambda: BP['N61'])
    s.put(23, 'E:Y', lambda c: BP[61, c+10] + S[24, c])
    # 27 Exports
    s.put(27, 'E:Y', lambda c: BE[19, c+9] + S[28, c])
    # 29 Imports
    s.put(29, 'E:Y', lambda c: BE[20, c+9] + S[30, c])
    # 31 Net Current Transfers, Official
    s.put(31, 'E:Y', lambda c: BE[22, c+9] + S[32, c])
    # 33 Net Current Transfers, Private
    s.put(33, 'E:Y', lambda c: BE[21, c+9] - BE[22, c+9] + S[34, c])
    # 35 Net FDI (negative = inflow)
    s.put(35, 'E:Y', lambda c: BE[24, c+9] + S[36, c])
    # 37 GDP deflator in US dollar terms (change in percent)
    s.put(37, 'E:Y', lambda c: BE[53, c+9] + S[38, c])
    # 46 Size of shock
    s.cell('C46', lambda: S['D46'])
    s.cell('D46', lambda: TT['H21'])
    # 49 Size of associated real GDP growth shock
    s.cell('C49', lambda: S['D49'])
    s.cell('D49', lambda: TT['L21'])
    # 50 Size of associated exports growth shock
    s.cell('C50', lambda: S['D50'])
    s.cell('D50', lambda: TT['L22'])
    # 53 Assumptions
    s.cell('B53', lambda: PVR['A2'])
    # 54 [Short Name]
    s.cell('B54', lambda: TR(s, 726))
    # 55 Shares of marginal debt
    s.cell('B55', lambda: PVR['A3'])
    # 56 External PPG medium and long-term
    s.cell('A56', lambda: IN7['J9'])
    s.cell('B56', lambda: PVR['A4'])
    # 57 Domestic medium and long-term
    s.cell('A57', lambda: IN7['J10'])
    s.cell('B57', lambda: PVR['A5'])
    # 58 Domestic short-term
    s.cell('A58', lambda: IN7['J11'])
    s.cell('B58', lambda: PVR['A6'])
    # 59 Period
    s.put(59, 'D:BO', lambda c: PVR[7, c-1])
    # 60 External MLT debt
    s.cell('B60', lambda: PVR['A8'])
    s.cell('D60', lambda: PVR['C8'])
    s.cell('E60', lambda: MD['U5'])
    s.put(60, 'F:BO', lambda c: S[60, c-1] + 1)
    # 61 Avg. nominal interest rate on new borrowing in USD
    s.cell('A61', lambda: IN7['J14'])
    s.cell('B61', lambda: PVR['A9'])
    s.cell('D61', lambda: PVR['C9'])
    # 62 USD Discount rate
    s.cell('A62', lambda: IN7['J15'])
    s.cell('B62', lambda: PVR['A10'])
    s.cell('D62', lambda: PVR['C10'])
    s.cell('E62', lambda: S['E61'] - S['E63'])
    s.put(62, 'F:BB', lambda c: S[62, c-1] - S[63, c])
    # 63 Avg. maturity (incl. grace period)
    s.cell('A63', lambda: IN7['J16'])
    s.cell('B63', lambda: PVR['A11'])
    s.cell('D63', lambda: PVR['C11'])
    s.put(63, 'E:BB', lambda c: IF(S[59, c] - S['E59'] - 1 < S['A64'], 0, IF(S[59, c] - S['E59'] - 1 < S['A63'], S['E61'] / (S['A63'] - S['A64']), 0)))
    # 64 Avg. grace period
    s.cell('A64', lambda: IN7['J17'])
    s.cell('B64', lambda: PVR['A12'])
    s.cell('D64', lambda: PVR['C12'])
    s.put(64, 'F:BB', lambda c: S[62, c-1] * S['A61'])
    # 65 Total debt service
    s.cell('D65', lambda: PVR['C13'])
    s.put(65, 'E:BB', lambda c: S[63, c] + S[64, c])
    # 66 PV of debt
    s.cell('D66', lambda: PVR['C14'])
    s.put(66, 'E:BA', lambda c: IF(S['A61'] > S['A62'], S[62, c], NPV(S['A62'], S.rng(65, c+1, 65, 'BB'))))
    s.cell('BB66', lambda: IF(S['A61'] > S['A62'], S['BB62'], NPV(S['A62'], S.rng(65, 'BB', 65, 'BB'))))
    # 67 Grant element
    s.cell('D67', lambda: PVR['C15'])
    s.cell('E67', lambda: (1 - S['E66'] / S['E62']) * 100)
    # 68 Domestic MLT debt
    s.cell('B68', lambda: PVR['A16'])
    s.put(68, 'F:Y', lambda c: S[69, c] + S[76, c])
    # 69 Avg. real interest rate on new borrowing
    s.cell('A69', lambda: IN7['J19'])
    s.cell('B69', lambda: PVR['A17'])
    s.put(69, 'F:Y', lambda c: S['A69'])
    # 70 Avg. maturity (incl. grace period)
    s.cell('A70', lambda: IN7['J20'])
    s.cell('B70', lambda: PVR['A18'])
    # 71 Avg. grace period
    s.cell('A71', lambda: IN7['J21'])
    s.cell('B71', lambda: PVR['A19'])
    # 73 Domestic short-term debt
    s.cell('B73', lambda: PVR['A21'])
    # 74 Avg. interest rate
    s.cell('B74', lambda: PVR['A22'])
    s.put(74, 'F:Y', lambda c: S[75, c] + S[76, c])
    # 75 Avg. real interest rate
    s.cell('A75', lambda: IN7['J23'])
    s.cell('B75', lambda: PVR['A23'])
    s.cell('F75', lambda: S['A75'])
    s.put(75, 'G:Y', lambda c: S[75, c-1])
    # 76 Inflation (GDP deflator)
    s.cell('B76', lambda: PVR['A24'])
    s.put(76, 'F:Y', lambda c: S[164, c-1] / 100)
    # 78 A2. Alternative Scenario :[Customize, enter title]
    s.cell('A78', lambda: S['B7'])
    s.put(78, 'E:Y', lambda c: S[60, c])
    # 80 New borrowing (gross, in LCU)
    s.cell('B80', lambda: PVR['C31'])
    s.put(80, 'E:Y', lambda c: S[187, c] - BP[78, c+10] + IF(S[1, c] == S['C42'], S['C46'] / 100 * S[151, c], 0))
    # 82 New forex borrowing (gross, USD)
    s.cell('B82', lambda: PVR['C36'])
    s.put(82, 'E:Y', lambda c: S[80, c] * S['A56'] * (S[161, c-1] + S[161, c]) / 2)
    # 83 cumulative
    s.cell('B83', lambda: PVR['C37'])
    s.put(83, 'E:Y', lambda c: SUM(S.rng(82, 'E', 82, c)))
    # 84 Stock of new forex debt (in USD)
    s.cell('B84', lambda: PVR['C38'])
    s.cell('E84', lambda: S['E82'] - S['E88'])
    s.put(84, 'F:Y', lambda c: S[82, c] + S[84, c-1] - S[88, c])
    # 85 PV of new forex debt (in USD)
    s.cell('B85', lambda: PVR['C39'])
    s.cell('E85', lambda: S['E82'] * S['E66'] / 100)
    s.put(85, 'F:Y', lambda c: IF(S['A61'] > S['A62'], S[85, c-1] - S[88, c] + S[82, c], S[85, c-1] * (1 + S['A62']) - S[86, c] + S[82, c] * S['E66'] / 100))
    # 86 Total debt service (in USD)
    s.cell('B86', lambda: PVR['C40'])
    s.put(86, 'E:Y', lambda c: S[87, c] + S[88, c])
    # 87 Interest
    s.cell('B87', lambda: PVR['C41'])
    s.put(87, 'E:Y', lambda c: S[84, c-1] * S['A61'])
    # 88 Amortization
    s.cell('B88', lambda: PVR['C42'])
    s.put(88, 'E:Y', lambda c: (S[91, c] - S[93, c]) / (S['A63'] - S['A64']))
    # 90 t-g>0
    s.cell('B90', lambda: PVR['C44'])
    s.put(90, 'E:Y', lambda c: IF(S[59, c] - S['A64'] > 0, S[59, c] - S['A64'], 0))
    # 91
    s.put(91, 'E:Y', lambda c: IF(S[90, c] == 0, 0, CHOOSE(S[90, c], *S.cells(83, 'E', 'Y'), X('#REF!'), *S.cells(83, 'Z', 'AF'))))
    # 92 t-m condition
    s.cell('B92', lambda: PVR['C46'])
    s.put(92, 'E:Y', lambda c: IF(S[59, c] - S['A63'] > 0, S[59, c] - S['A63'], 0))
    # 93
    s.put(93, 'E:Y', lambda c: IF(S[92, c] == 0, 0, CHOOSE(S[92, c], *S.cells(83, 'E', 'Y'), X('#REF!'), *S.cells(83, 'Z', 'AC'), *S.cells(142, 'AD', 'AF'))))
    # 95 New domestic MLT borrowing (gross)
    s.cell('B95', lambda: PVR['C49'])
    s.put(95, 'E:Y', lambda c: S[80, c] * S['A57'])
    # 96 cumulative
    s.cell('B96', lambda: PVR['C50'])
    s.put(96, 'E:Y', lambda c: SUM(S.rng(95, 'E', 95, c)))
    # 97 Stock of new domestic MLT debt
    s.cell('B97', lambda: PVR['C51'])
    s.cell('E97', lambda: S['E95'] - S['E101'])
    s.put(97, 'F:Y', lambda c: S[95, c] + S[97, c-1] - S[101, c])
    # 99 Total debt service
    s.cell('B99', lambda: PVR['C53'])
    s.put(99, 'E:Y', lambda c: S[100, c] + S[101, c])
    # 100 Interest
    s.cell('B100', lambda: PVR['C54'])
    s.put(100, 'F:Y', lambda c: S[97, c-1] * S[68, c])
    # 101 Amortization
    s.cell('B101', lambda: PVR['C55'])
    s.put(101, 'E:Y', lambda c: (S[104, c] - S[106, c]) / (S['A70'] - S['A71']))
    # 103 t-g>0
    s.cell('B103', lambda: PVR['C57'])
    s.put(103, 'E:Y', lambda c: IF(S[59, c] - S['A71'] > 0, S[59, c] - S['A71'], 0))
    # 104
    s.put(104, 'E:Y', lambda c: IF(S[103, c] == 0, 0, CHOOSE(S[103, c], *S.cells(96, 'E', 'Y'), X('#REF!'), *S.cells(96, 'Z', 'AF'))))
    # 105 t-m condition
    s.cell('B105', lambda: PVR['C59'])
    s.put(105, 'E:Y', lambda c: IF(S[59, c] - S['A70'] > 0, S[59, c] - S['A70'], 0))
    # 106
    s.put(106, 'E:Y', lambda c: IF(S[105, c] == 0, 0, CHOOSE(S[105, c], *S.cells(96, 'E', 'Y'), X('#REF!'), *S.cells(96, 'Z', 'AC'), *S.cells(142, 'AD', 'AF'))))
    # 108 New domestic short-term borrowing (gross; also stock of debt)
    s.cell('B108', lambda: PVR['C62'])
    s.put(108, 'E:Y', lambda c: S[80, c] * S['A58'])
    # 109 Interest
    s.cell('B109', lambda: PVR['C63'])
    s.put(109, 'F:Y', lambda c: S[108, c-1] * S[74, c])
    # 112 A2. Alternative Scenario :[Customize, enter title]
    s.cell('B112', lambda: S['B7'])
    # 113 (In percent of GDP, unless otherwise indicated)
    s.cell('B113', lambda: BP['B3'])
    # 116 First year of proj.
    s.cell('E116', lambda: BP['O6'])
    # 117
    s.cell('C117', lambda: MD['S5'])
    s.put(117, 'D:Y', lambda c: S[117, c-1] + 1)
    # 121 Public sector debt 1/
    s.cell('B121', lambda: BP['B12'])
    s.put(121, 'C:D', lambda c: IF(ISNUMBER(MD[80, c+16] / (MD[56, c+16] * MD[60, c+16])), 100 * (MD[80, c+16] + (MD[50, c+16] - S[16, c])) / (MD[56, c+16] * MD[60, c+16]), '.'))
    s.put(121, 'E:Y', lambda c: S[121, c-1] + S[125, c] + (MD[50, c+16] - S[16, c]) / S[151, c])
    # 122 of which: foreign-currency denominated
    s.cell('B122', lambda: BP['B14'])
    s.cell('C122', lambda: IF(ISNUMBER(MD['S83']), MD['S83'] / S['C151'] * 100, '...'))
    s.put(122, 'D:Y', lambda c: S[180, c] / S[151, c] * 100)
    # 123 PV of public debt-to-GDP ratio 2/
    s.cell('B123', lambda: BP['B42'])
    s.put(123, 'C:Y', lambda c: (S[188, c] + S[178, c]) / S[151, c] * 100)
    # 125 Change in public sector debt
    s.cell('B125', lambda: BP['B21'])
    s.put(125, 'D:Y', lambda c: S[126, c] + S[142, c])
    # 126 Identified debt-creating flows
    s.cell('B126', lambda: BP['B22'])
    s.put(126, 'D:Y', lambda c: S[127, c] + S[131, c] + S[137, c])
    # 127 Primary deficit
    s.cell('B127', lambda: BP['B23'])
    s.put(127, 'C:Y', lambda c: S[130, c] - S[128, c])
    # 128 Revenue and grants
    s.cell('B128', lambda: BP['B24'])
    s.put(128, 'C:D', lambda c: IF(ISNUMBER(MD[45, c+16] / S[151, c]), 100 * MD[45, c+16] / S[151, c], '.'))
    s.put(128, 'E:Y', lambda c: S[10, c] - S[14, c] + S[129, c])
    # 129 of which: grants
    s.cell('B129', lambda: BP['B25'])
    s.put(129, 'C:D', lambda c: IF(ISNUMBER(MD[46, c+16]), MD['T46'] / S[151, c] * 100, '...'))
    s.put(129, 'E:Y', lambda c: S[14, c] / 100 * S[194, c] / S[151, c] * 100)
    # 130 Primary (noninterest) expenditure
    s.cell('B130', lambda: BP['B26'])
    s.cell('C130', lambda: IF(ISNUMBER((MD['S48'] - MD['S49']) / S['C151']), 100 * ((MD['S48'] - MD['S49']) / S['C151']), '.'))
    s.cell('D130', lambda: BP['N26'])
    s.put(130, 'E:Y', lambda c: S[12, c] / 100 * S[194, c] / S[151, c] * 100)
    # 131 Automatic debt dynamics
    s.cell('B131', lambda: BP['B27'])
    s.put(131, 'D:Y', lambda c: S[132, c] + S[135, c])
    # 132 Contribution from interest rate/growth differential
    s.cell('B132', lambda: BP['B28'])
    s.put(132, 'D:Y', lambda c: S[133, c] + S[134, c])
    # 133 of which: contribution from average real interest rate
    s.cell('B133', lambda: BP['B29'])
    s.put(133, 'D:Y', lambda c: S[156, c] / 100 * S[121, c-1] / S[136, c])
    # 134 of which: contribution from real GDP growth
    s.cell('B134', lambda: BP['B30'])
    s.put(134, 'D:Y', lambda c: -(S[152, c] / 100) * (S[121, c-1] / S[136, c]))
    # 135 Contribution from real exchange rate depreciation
    s.cell('B135', lambda: BP['B31'])
    s.put(135, 'D:Y', lambda c: S[163, c] / 100 * S[122, c-1] * (1 + S[158, c] / 100) / S[136, c])
    # 136 Denominator = 1+g
    s.cell('B136', lambda: BP['B32'])
    s.put(136, 'D:Y', lambda c: 1 + S[152, c] / 100)
    # 137 Other identified debt-creating flows
    s.cell('B137', lambda: BP['B33'])
    s.put(137, 'C:Y', lambda c: SUM(S.rng(138, c, 141, c)))
    # 138 Privatization receipts (negative)
    s.cell('B138', lambda: BP['B34'])
    s.put(138, 'C:Y', lambda c: BP[34, c+10] / BP[52, c+10] * S[151, c])
    # 139 Recognition of contingent liabilities (e.g., bank recapitalization)
    s.cell('B139', lambda: BP['B35'])
    s.put(139, 'C:Y', lambda c: BP[35, c+10] / BP[52, c+10] * S[151, c])
    # 140 Debt relief (HIPC and other)
    s.cell('B140', lambda: BP['B36'])
    s.put(140, 'C:Y', lambda c: BP[36, c+10] / BP[52, c+10] * S[151, c])
    # 141 Other debt creating or reducing flow (please specify)
    s.cell('B141', lambda: BP['B37'])
    s.put(141, 'C:D', lambda c: BP[37, c+10] / BP[52, c+10] * S[151, c])
    s.put(141, 'E:Y', lambda c: BP[37, c+10] / BP[52, c+10] * S[151, c] + IF(S[1, c] == S['C42'], S['C46'], 0))
    # 142 Residual
    s.cell('B142', lambda: BP['B38'])
    s.put(142, 'C:Y', lambda c: BP[38, c+10] * BP[52, c+10] / S[151, c])
    # 144 Public sector debt-to-revenue-and-grants ratio (in percent)
    s.cell('B144', lambda: TRS['C1766'])
    s.put(144, 'C:Y', lambda c: S[121, c] / S[128, c] * 100)
    # 146 Gross financing need 4/
    s.cell('B146', lambda: BP['B47'])
    s.put(146, 'C:D', lambda c: MD[101, c+16] / (MD[56, c+16] * MD[60, c+16]) * 100)
    s.put(146, 'E:Y', lambda c: S[187, c] / S[151, c] * 100)
    # 147 in billions of U.S. dollars
    s.cell('B147', lambda: BP['B48'])
    s.cell('C147', lambda: MD['S101'] / MD['S60'])
    s.put(147, 'D:Y', lambda c: S[187, c] / S[159, c])
    # 149 Key macroeconomic and fiscal assumptions
    s.cell('B149', lambda: BP['B51'])
    # 151 Nominal GDP (local currency)
    s.cell('B151', lambda: BP['B52'])
    s.put(151, 'C:D', lambda c: MD[56, c+16] * MD[60, c+16])
    s.put(151, 'E:Y', lambda c: S[151, c-1] * (1 + S[152, c] / 100) * (1 + S[164, c] / 100))
    # 152 Real GDP growth (in percent)
    s.cell('B152', lambda: BP['B53'])
    s.put(152, 'C:D', lambda c: MD[107, c+16])
    s.put(152, 'E:Y', lambda c: S[19, c] - IF(S[1, c] == S['C42'], S['C49'], 0))
    # 153 Average nominal interest rate on public debt (in percent)
    s.cell('B153', lambda: BP['B54'])
    s.cell('C153', lambda: IF(ISNUMBER(100 * MD['S49'] / MD['R80']), 100 * MD['S49'] / MD['R80'], '.'))
    s.cell('D153', lambda: BP['N54'])
    s.put(153, 'E:Y', lambda c: S[183, c] / S[177, c-1] * 100)
    # 154 Average nominal interest rate on external debt (in percent)
    s.cell('B154', lambda: BP['B55'])
    s.put(154, 'C:D', lambda c: BP[55, c+10])
    s.put(154, 'E:Y', lambda c: S[185, c] / S[180, c-1] * 100 * MD[59, c+15] / MD[60, c+16])
    # 155 Average nominal interest rate on domestic debt (in percent)
    s.cell('B155', lambda: BP['B56'])
    s.put(155, 'C:D', lambda c: BP[56, c+10])
    s.put(155, 'E:Y', lambda c: IF(S[178, c-1] == 0, PVR[25, c-1] * 100, S[184, c] / S[178, c-1] * 100))
    # 156 Average real interest rate (in percent)
    s.cell('B156', lambda: BP['B57'])
    s.put(156, 'D:Y', lambda c: S[122, c-1] / S[121, c-1] * S[158, c] + (1 - S[122, c-1] / S[121, c-1]) * S[157, c])
    # 157 Average real interest rate on domestic debt (in percent)
    s.cell('B157', lambda: BP['B58'])
    s.put(157, 'C:D', lambda c: BP[58, c+10])
    s.put(157, 'E:Y', lambda c: (S[155, c] - S[164, c]) / (1 + S[164, c] / 100))
    # 158 Average real interest rate on external debt (in percent)
    s.cell('B158', lambda: BP['B59'])
    s.put(158, 'D:Y', lambda c: IF(ISNUMBER(S[154, c]), (S[154, c] - S[165, c]) / (1 + S[165, c] / 100), '...'))
    # 159 Exchange rate (LC per US dollar)
    s.cell('B159', lambda: BP['B60'])
    s.put(159, 'C:D', lambda c: MD[59, c+16])
    s.put(159, 'E:Y', lambda c: S[159, c-1] * (1 + S[160, c] / 100))
    # 160 Nominal depreciation of local currency (percentage change in LC per dollar)
    s.cell('B160', lambda: BP['B61'])
    s.cell('D160', lambda: (S['D159'] / S['C159'] - 1) * 100)
    s.put(160, 'E:Y', lambda c: S[23, c])
    # 161 Exchange rate (US dollar per LC)
    s.cell('B161', lambda: BP['B62'])
    s.put(161, 'C:Y', lambda c: 1 / S[159, c])
    # 162 Nominal appreciation (increase in US dollar value of local currency, in percent)
    s.cell('B162', lambda: BP['B63'])
    s.put(162, 'D:Y', lambda c: (S[161, c] / S[161, c-1] - 1) * 100)
    # 163 Real exchange rate depreciation (in percent, + indicates depreciation)
    s.cell('B163', lambda: BP['B64'])
    s.put(163, 'D:Y', lambda c: (100 + S[160, c]) * (1 + S[165, c] / 100) / (1 + S[164, c] / 100) - 100)
    # 164 Inflation rate (GDP deflator, in percent)
    s.cell('B164', lambda: BP['B65'])
    s.put(164, 'C:D', lambda c: IF(ISNUMBER(MD[109, c+16]), MD[109, c+16], '.'))
    s.put(164, 'E:Y', lambda c: S[21, c])
    # 165 US Inflation rate (GDP deflator, in percent)
    s.cell('B165', lambda: BP['B66'])
    s.put(165, 'C:Y', lambda c: MD[112, c+16])
    # 166 Growth of real primary spending (deflated by GDP deflator, in percent)
    s.cell('B166', lambda: BP['B67'])
    s.cell('C166', lambda: MD['S100'])
    s.put(166, 'D:Y', lambda c: S[172, c])
    # 170 Nominal spending
    s.cell('B170', lambda: TR(s, 744))
    s.put(170, 'C:Y', lambda c: S[130, c] / 100 * S[151, c])
    # 171 Increase in percent
    s.cell('B171', lambda: TR(s, 745))
    s.put(171, 'D:Y', lambda c: (S[170, c] / S[170, c-1] - 1) * 100)
    # 172 Increase in real spending in percent
    s.cell('B172', lambda: TR(s, 746))
    s.put(172, 'D:Y', lambda c: ((1 + S[171, c] / 100) / (1 + S[164, c] / 100) - 1) * 100)
    # 176 In billions of local currency
    s.cell('B176', lambda: A1P['B78'])
    # 177 Nominal debt
    s.cell('B177', lambda: A1P['B79'])
    s.put(177, 'C:Y', lambda c: S[121, c] / 100 * S[151, c])
    # 178 Total public domestic debt
    s.cell('B178', lambda: A1P['B80'])
    s.put(178, 'C:Y', lambda c: S[177, c] - S[180, c])
    # 179 of which: Short term
    s.cell('B179', lambda: A1P['B81'])
    s.put(179, 'C:D', lambda c: MD[16, c+16])
    s.put(179, 'E:Y', lambda c: S[108, c] + MD[16, c+16])
    # 180 Total public external debt
    s.cell('B180', lambda: A1P['B82'])
    s.put(180, 'C:D', lambda c: MD[81, c+16] / MD[59, c+16] * S[159, c])
    s.put(180, 'E:Y', lambda c: (MD[81, c+16] / MD[59, c+16] + S[84, c]) * S[159, c])
    # 181 Debt service
    s.cell('B181', lambda: A1P['B83'])
    # 182 Amortization (excluding ST domestic debt)
    s.cell('B182', lambda: A1P['B84'])
    s.put(182, 'C:D', lambda c: (MD[26, c+16] + MD[24, c+16]) * MD[60, c+16])
    s.put(182, 'E:Y', lambda c: (MD[24, c+16] + MD[26, c+16] + S[88, c]) * MD[60, c+16] + S[101, c])
    # 183 Interest Expenditure
    s.cell('B183', lambda: A1P['B85'])
    s.put(183, 'C:Y', lambda c: S[184, c] + S[185, c])
    # 184 Domestic debt
    s.cell('B184', lambda: A1P['B86'])
    s.put(184, 'C:D', lambda c: MD[21, c+16] * MD[60, c+16])
    s.put(184, 'E:Y', lambda c: MD[21, c+16] * MD[60, c+16] + S[109, c] + S[100, c])
    # 185 External debt
    s.cell('B185', lambda: A1P['B87'])
    s.put(185, 'C:D', lambda c: MD[19, c+16] * MD[60, c+16])
    s.put(185, 'E:Y', lambda c: (MD[19, c+16] + S[87, c]) * MD[60, c+16])
    # 186 Primary deficit
    s.cell('B186', lambda: A1P['B88'])
    s.put(186, 'D:Y', lambda c: S[127, c] / 100 * S[151, c])
    # 187 Gross financing need (in local currency)
    s.cell('B187', lambda: A1P['B90'])
    s.put(187, 'D:Y', lambda c: S[186, c] + S[183, c] + S[182, c] + S[179, c-1] + S[189, c])
    # 188 PV of public sector external debt (end of period)
    s.cell('B188', lambda: A1P['B91'])
    s.cell('D188', lambda: MD['T92'] * S['D159'] / BP['N60'])
    s.put(188, 'E:Y', lambda c: (MD[92, c+16] / BP[60, c+10] + S[85, c]) * S[159, c])
    # 189 Other debt creating flows
    s.put(189, 'D:Y', lambda c: BP[33, c+10] / 100 * BP[52, c+10])
    # 190 Debt service-to-revenue-and-grants ratio (in percent)
    s.cell('B190', lambda: A1P['B93'])
    s.put(190, 'D:Y', lambda c: 10000 * (S[182, c] + S[183, c] + S[179, c-1]) / (S[128, c] * S[151, c]))
    # 191 Debt service-to-GDP ratio (in percent)
    s.cell('B191', lambda: A1P['B94'])
    s.put(191, 'D:Y', lambda c: 100 * (S[182, c] + S[183, c] + S[179, c-1]) / S[151, c])
    # 192 PV of public debt-to-revenue and grants ratio
    s.cell('B192', lambda: A1P['B95'])
    s.put(192, 'D:Y', lambda c: S[123, c] / S[128, c] * 100)
    # 194 Nominal GDP (local currency) - Custom
    s.cell('E194', lambda: S['D151'] * (1 + S['E19'] / 100) * (1 + S['E164'] / 100))
    s.put(194, 'F:Y', lambda c: S[194, c-1] * (1 + S[19, c] / 100) * (1 + S[164, c] / 100))
    # 201 This sheet allows the user to model customized shocks to the main fiscal and external v...
    s.cell('A201', lambda: IF(START['L10'] == 'English', S['A211'], IF(START['L10'] == 'French', S['A218'], IF(START['L10'] == 'Portuguese', S['A225'], S['A232']))))
    # 203 The user can enter alternative data in rows labeled “Delta” for any, a few, or all of t...
    s.cell('A203', lambda: IF(START['L10'] == 'English', S['A213'], IF(START['L10'] == 'French', S['A220'], IF(START['L10'] == 'Portuguese', S['A227'], S['A234']))))


def _customized_scenario_external(s):
    """Customized Scenario-External"""
    BE = s.sheet('Baseline - external')
    CSP = s.sheet('Customized Scenario - public')
    EDD = s.sheet('Ext_Debt_Data')
    IN7 = s.sheet('Input 7 - Residual Financing')
    MD = s.sheet('Macro-Debt_Data')
    PVR = s.sheet('PV_ResFin_pub')
    TRS = s.sheet('translation')
    S = s.sheet(s.name)
    # 3 To include the external customized scenario in charts and tables?
    s.cell('B3', lambda: TR(s, 830))
    s.cell('D3', lambda: CSP['C3'])
    # 5 Customized external scenarios: INSTRUCTIONS
    s.cell('A5', lambda: TR(s, 831))
    # 6 This sheet displays results for the external debt dynamics based on variables entered i...
    s.cell('B6', lambda: TRS['C827'])
    # 8 A2. Alternative Scenario :[Customize, enter title]
    s.cell('B8', lambda: CSP['B7'])
    s.put(8, 'D:X', lambda c: S[55, c])
    # 9 Exports, Imports are set to account for shocks to commodity prices. For any other shock...
    s.cell('B9', lambda: TR(s, 772))
    # 10 Exports
    s.cell('B10', lambda: S['B66'])
    s.put(10, 'D:X', lambda c: CSP[27, c+1])
    # 11 Imports
    s.cell('B11', lambda: S['B67'])
    s.put(11, 'D:X', lambda c: CSP[29, c+1])
    # 12 Net Current Transfers, Official
    s.cell('B12', lambda: TR(s, 775))
    s.put(12, 'D:X', lambda c: CSP[31, c+1])
    # 13 Net Current Transfers, Private
    s.cell('B13', lambda: TR(s, 776))
    s.put(13, 'D:X', lambda c: CSP[33, c+1])
    # 14 Checkline (= 0)
    s.put(14, 'D:X', lambda c: S[64, c] - S[65, c] - S[68, c] - S[70, c])
    # 15 Net FDI (negative = inflow)
    s.cell('B15', lambda: S['B71'])
    s.put(15, 'D:X', lambda c: CSP[35, c+1])
    # 16 Real GDP growth (in percent)
    s.cell('B16', lambda: S['B97'])
    s.put(16, 'D:X', lambda c: CSP[19, c+1])
    # 17 GDP deflator in US dollar terms (change in percent)
    s.cell('B17', lambda: S['B98'])
    s.put(17, 'D:X', lambda c: CSP[37, c+1])
    # 19 Assumptions
    s.cell('B19', lambda: CSP['B53'])
    # 20 [Short Name]
    s.cell('B20', lambda: CSP['B54'])
    # 21 Average interest rate on new debt
    s.cell('B21', lambda: EDD['A131'])
    s.cell('C21', lambda: IN7['J14'])
    # 22 USD Discount rate
    s.cell('B22', lambda: IN7['G15'])
    s.cell('C22', lambda: IN7['J15'])
    # 23 Average grace period on new debt
    s.cell('B23', lambda: EDD['A132'])
    s.cell('C23', lambda: IN7['J17'])
    # 24 Average maturity of new debt
    s.cell('B24', lambda: EDD['A133'])
    s.cell('C24', lambda: IN7['J16'])
    # 26 Period
    s.cell('B26', lambda: PVR['C7'])
    s.put(26, 'E:BB', lambda c: S[26, c-1] + 1)
    # 27 First year of projections
    s.cell('B27', lambda: PVR['C8'])
    s.cell('D27', lambda: MD['U5'])
    s.put(27, 'E:BB', lambda c: S[27, c-1] + 1)
    # 28 Disbursement
    s.cell('B28', lambda: PVR['C9'])
    # 29 Debt stock
    s.cell('B29', lambda: PVR['C10'])
    s.cell('D29', lambda: S['D28'] - S['D30'])
    s.put(29, 'E:BB', lambda c: S[29, c-1] - S[30, c])
    # 30 Amortization
    s.cell('B30', lambda: PVR['C11'])
    s.put(30, 'D:BB', lambda c: IF(S[26, c] - S['D26'] - 1 < S['C23'], 0, IF(S[26, c] - S['D26'] - 1 < S['C24'], S['D28'] / (S['C24'] - S['C23']), 0)))
    # 31 Interest
    s.cell('B31', lambda: PVR['C12'])
    s.put(31, 'E:BB', lambda c: S[29, c-1] * S['C21'])
    # 32 Total debt service
    s.cell('B32', lambda: PVR['C13'])
    s.put(32, 'D:BB', lambda c: S[30, c] + S[31, c])
    # 33 PV of debt
    s.cell('B33', lambda: PVR['C14'])
    s.put(33, 'D:BA', lambda c: IF(S['C21'] > S['C22'], S[29, c], NPV(S['C22'], S.rng(32, c+1, 32, 'BB'))))
    s.cell('BB33', lambda: IF(S['C21'] > S['C22'], S['BB29'], NPV(S['C22'], S.rng(32, 'BB', 32, 'BB'))))
    # 34 Grant element
    s.cell('B34', lambda: PVR['C15'])
    s.put(34, 'D:BB', lambda c: IF(S[33, c] < 0.01, 0, (1 - S[33, c] / S[29, c]) * 100))
    # 36 New forex borrowing (gross, USD)
    s.cell('B36', lambda: PVR['C36'])
    s.put(36, 'D:X', lambda c: S[149, c] + CSP[88, c+1])
    # 37 cumulative
    s.cell('B37', lambda: PVR['C37'])
    s.cell('D37', lambda: S['D36'])
    s.put(37, 'E:X', lambda c: SUM(S.rng(36, 'D', 36, c)))
    # 38 Stock of new forex debt (in USD)
    s.cell('B38', lambda: PVR['C38'])
    s.cell('D38', lambda: S['D36'] - S['D43'])
    s.put(38, 'E:X', lambda c: S[38, c-1] + S[36, c] - S[43, c])
    # 39 PV of new forex debt (in USD)
    s.cell('B39', lambda: PVR['C39'])
    s.cell('D39', lambda: S['D36'] * S['D33'] / 100)
    s.put(39, 'E:X', lambda c: IF(S['C21'] > S['C22'], S[39, c-1] - S[43, c] + S[36, c], S[39, c-1] * (1 + S['C22']) - S[41, c] + S[36, c] * S['D33'] / 100))
    # 41 Total debt service (in USD)
    s.cell('B41', lambda: PVR['C40'])
    s.put(41, 'D:X', lambda c: S[42, c] + S[43, c])
    # 42 Interest
    s.cell('B42', lambda: PVR['C41'])
    s.cell('D42', lambda: S['D36'] * S['C21'] * 0.5)
    s.put(42, 'E:X', lambda c: S[38, c-1] * S['C21'])
    # 43 Amortization
    s.cell('B43', lambda: PVR['C42'])
    s.put(43, 'D:X', lambda c: (S[46, c] - S[48, c]) / (S['C24'] - S['C23']))
    # 45 t-g>0
    s.put(45, 'D:X', lambda c: IF(S[26, c] - S['C23'] > 0, S[26, c] - S['C23'], 0))
    # 46
    s.put(46, 'D:X', lambda c: IF(S[45, c] == 0, 0, CHOOSE(S[45, c], *S.cells(37, 'D', 'AF'))))
    # 47 t-m condition
    s.cell('B47', lambda: PVR['C46'])
    s.put(47, 'D:X', lambda c: IF(S[26, c] - S['C24'] > 0, S[26, c] - S['C24'], 0))
    # 48
    s.put(48, 'D:X', lambda c: IF(S[47, c] == 0, 0, CHOOSE(S[47, c], *S.cells(37, 'D', 'X'))))
    # 50 A2. Alternative Scenario :[Customize, enter title]
    s.cell('B50', lambda: S['B8'])
    # 51 (In percent of GDP, unless otherwise indicated)
    s.cell('B51', lambda: BE['B4'])
    # 54 Projections
    s.cell('D54', lambda: BE['N7'])
    # 55
    s.cell('C55', lambda: S['D55'] - 1)
    s.cell('D55', lambda: MD['U4'])
    s.put(55, 'E:X', lambda c: S[55, c-1] + 1)
    # 57 I. Baseline Medium Term Projections
    s.cell('B57', lambda: BE['B10'])
    # 59 External debt (nominal) 1/
    s.cell('B59', lambda: BE['B12'])
    s.cell('C59', lambda: BE['M12'])
    s.put(59, 'D:X', lambda c: S[59, c-1] + S[62, c])
    # 60 of which: public and publicly guaranteed (PPG)
    s.cell('B60', lambda: BE['B13'])
    s.put(60, 'C:X', lambda c: CSP[122, c+1])
    # 61 of which: Private
    s.cell('B61', lambda: BE['B14'])
    s.cell('C61', lambda: BE['M12'] - BE['M13'])
    s.put(61, 'D:X', lambda c: S[59, c] - S[60, c])
    # 62 Change in external debt
    s.cell('B62', lambda: BE['B15'])
    s.put(62, 'C:Y', lambda c: S[63, c] + S[77, c])
    # 63 Identified net debt-creating flows
    s.cell('B63', lambda: BE['B16'])
    s.put(63, 'C:Y', lambda c: S[64, c] + S[71, c] + S[72, c])
    # 64 Non-interest current account deficit
    s.cell('B64', lambda: BE['B17'])
    s.put(64, 'C:X', lambda c: S[65, c] + S[68, c] + S[70, c])
    s.cell('Y64', lambda: -(S['Y71'] + S['Y72']))
    # 65 Deficit in balance of goods and services
    s.cell('B65', lambda: BE['B18'])
    s.put(65, 'C:X', lambda c: S[67, c] - S[66, c])
    # 66 Exports
    s.cell('B66', lambda: BE['B19'])
    s.cell('C66', lambda: BE['M19'])
    s.put(66, 'D:X', lambda c: S[154, c])
    # 67 Imports
    s.cell('B67', lambda: BE['B20'])
    s.cell('C67', lambda: BE['M20'])
    s.put(67, 'D:X', lambda c: S[11, c])
    # 68 Net current transfers (negative = inflow)
    s.cell('B68', lambda: BE['B21'])
    s.cell('C68', lambda: BE['M21'])
    s.put(68, 'D:X', lambda c: S[12, c] + S[13, c])
    # 69 of which: official
    s.cell('B69', lambda: BE['B22'])
    s.cell('C69', lambda: BE['M22'])
    s.put(69, 'D:X', lambda c: S[12, c])
    # 70 Other current account flows (negative = net inflow)
    s.cell('B70', lambda: BE['B23'])
    s.put(70, 'C:X', lambda c: BE[23, c+10])
    # 71 Net FDI (negative = inflow)
    s.cell('B71', lambda: BE['B24'])
    s.cell('C71', lambda: BE['M24'])
    s.put(71, 'D:X', lambda c: S[15, c])
    s.cell('Y71', lambda: S['X71'])
    # 72 Endogenous debt dynamics 2/
    s.cell('B72', lambda: BE['B25'])
    s.cell('C72', lambda: BE['M25'])
    s.put(72, 'D:Y', lambda c: S[74, c] + S[75, c] + S[76, c])
    # 73 Denominator: 1+g+ρ+gρ
    s.cell('B73', lambda: BE['B26'])
    s.cell('C73', lambda: BE['M26'])
    s.put(73, 'D:Y', lambda c: 1 + S[97, c] / 100 + S[98, c] / 100 + S[97, c] / 100 * S[98, c] / 100)
    # 74 Contribution from nominal interest rate
    s.cell('B74', lambda: BE['B27'])
    s.cell('C74', lambda: BE['M27'])
    s.put(74, 'D:Y', lambda c: S[99, c] / 100 * S[59, c-1] / S[73, c])
    # 75 Contribution from real GDP growth
    s.cell('B75', lambda: BE['B28'])
    s.cell('C75', lambda: BE['M28'])
    s.put(75, 'D:Y', lambda c: -(S[97, c] / 100) * S[59, c-1] / S[73, c])
    # 76 Contribution from price and exchange rate changes
    s.cell('B76', lambda: BE['B29'])
    s.cell('C76', lambda: BE['M29'])
    s.put(76, 'D:Y', lambda c: -(S[98, c] / 100 * (1 + S[97, c] / 100)) * S[59, c-1] / S[73, c])
    # 77 Residual 3/
    s.cell('B77', lambda: BE['B30'])
    s.cell('C77', lambda: BE['M30'])
    s.put(77, 'D:X', lambda c: BE[30, c+10] + IF(CSP[1, c+1] == CSP['C42'], CSP['C46'] * CSP['A56'], 0))
    # 80 PV of external debt 7/
    s.cell('B80', lambda: BE['B33'])
    s.cell('C80', lambda: BE['M33'])
    s.put(80, 'D:X', lambda c: S[128, c] / S[93, c] * 100)
    # 81 In percent of exports
    s.cell('B81', lambda: BE['B34'])
    s.cell('C81', lambda: BE['M34'])
    s.put(81, 'D:X', lambda c: S[80, c] / S[66, c] * 100)
    # 82 PV of PPG external debt-to-GDP ratio
    s.cell('B82', lambda: BE['B35'])
    s.cell('C82', lambda: BE['M35'])
    s.put(82, 'D:X', lambda c: S[126, c] / S[93, c] * 100)
    # 83 PV of PPG external debt-to-exports ratio
    s.cell('B83', lambda: BE['B36'])
    s.cell('C83', lambda: BE['M36'])
    s.put(83, 'D:X', lambda c: S[82, c] / S[66, c] * 100)
    # 84 PV of PPG external debt-to-revenue ratio
    s.cell('B84', lambda: BE['B37'])
    s.put(84, 'C:X', lambda c: S[82, c] * S[93, c] / S[142, c])
    # 85 Total external debt service-to-exports ratio
    s.cell('B85', lambda: BE['B38'])
    s.cell('C85', lambda: BE['M38'])
    s.put(85, 'D:X', lambda c: S[136, c] / S[141, c] * 100)
    # 86 PPG debt service-to-exports ratio
    s.cell('B86', lambda: BE['B39'])
    s.cell('C86', lambda: BE['M39'])
    s.put(86, 'D:X', lambda c: S[137, c] / S[141, c] * 100)
    # 87 PPG debt service-to-revenue ratio
    s.cell('B87', lambda: BE['B40'])
    s.cell('C87', lambda: BE['M40'])
    s.put(87, 'D:X', lambda c: S[137, c] / S[142, c] * 100)
    # 88 Gross external financing need (Million of U.S. dollars)
    s.cell('B88', lambda: BE['B41'])
    s.cell('C88', lambda: BE['M41'])
    s.put(88, 'D:X', lambda c: (S[64, c] + S[71, c]) / 100 * S[93, c] + S[136, c] + S[143, c-1])
    # 91 II. Key macroeconomic assumptions
    s.cell('B91', lambda: BE['B46'])
    # 93 Nominal GDP (Million of US dollars)
    s.cell('B93', lambda: BE['B48'])
    s.cell('C93', lambda: BE['M48'])
    s.put(93, 'D:X', lambda c: S[93, c-1] * (1 + S[97, c] / 100) * (1 + S[98, c] / 100))
    # 94 Nominal dollar GDP growth
    s.cell('B94', lambda: BE['B49'])
    s.put(94, 'D:X', lambda c: (S[93, c] / S[93, c-1] - 1) * 100)
    # 95 PV of PPG external debt (in Million of US dollars)
    s.cell('B95', lambda: BE['B50'])
    s.cell('C95', lambda: S['C124'])
    s.put(95, 'D:X', lambda c: S[126, c])
    # 96 (PVt-PVt-1)/GDPt-1 (in percent)
    s.cell('B96', lambda: BE['B51'])
    s.put(96, 'D:X', lambda c: (S[95, c] - S[95, c-1]) / S[93, c-1] * 100)
    # 97 Real GDP growth (in percent)
    s.cell('B97', lambda: BE['B52'])
    s.cell('C97', lambda: BE['M52'])
    s.put(97, 'D:X', lambda c: S[16, c] - IF(CSP[1, c+1] == CSP['C42'], CSP['C49'], 0))
    # 98 GDP deflator in US dollar terms (change in percent)
    s.cell('B98', lambda: BE['B53'])
    s.cell('C98', lambda: BE['M53'])
    s.put(98, 'D:X', lambda c: S[17, c])
    # 99 Effective interest rate (percent) 4/
    s.cell('B99', lambda: BE['B54'])
    s.cell('C99', lambda: BE['M54'])
    s.put(99, 'D:X', lambda c: S[140, c])
    # 100 Growth of exports of G&S (US dollar terms, in percent)
    s.cell('B100', lambda: BE['B55'])
    s.cell('C100', lambda: BE['M55'])
    s.put(100, 'D:X', lambda c: S[152, c])
    # 101 Growth of imports of G&S (US dollar terms, in percent)
    s.cell('B101', lambda: BE['B56'])
    s.cell('C101', lambda: BE['M56'])
    s.put(101, 'D:X', lambda c: S[160, c])
    # 102 Current transfers, net total
    s.cell('B102', lambda: BE['B57'])
    s.cell('C102', lambda: BE['M57'])
    s.put(102, 'D:X', lambda c: S[68, c])
    # 104 Depreciation of NC (+: depreciation)
    s.cell('B104', lambda: BE['B59'])
    s.cell('C104', lambda: BE['M59'])
    s.put(104, 'D:X', lambda c: -CSP[162, c+1])
    # 105 Government revenues (excluding grants, in percent of GDP)
    s.cell('B105', lambda: BE['B60'])
    s.put(105, 'C:X', lambda c: S[142, c] / S[93, c] * 100)
    # 107 Sources: Country authorities; and staff estimates and projections.
    s.cell('B107', lambda: BE['B77'])
    # 109 1/ Includes both public and private sector external debt.
    s.cell('B109', lambda: BE['B79'])
    # 110 2/ Derived as [r - g - ρ(1+g) + Ɛα (1+r)]/(1+g+ρ+gρ) times previous period debt ratio, ...
    s.cell('B110', lambda: BE['B80'])
    # 111 3/ Includes exceptional financing (i.e., changes in arrears and debt relief); changes i...
    s.cell('B111', lambda: BE['B81'])
    # 112 7/ Assumes that PV of private sector debt is equivalent to its face value.
    s.cell('B112', lambda: BE['B85'])
    # 113 4/ Current-year interest payments divided by previous period debt stock.
    s.cell('B113', lambda: BE['B82'])
    # 114 8/ Historical averages are generally derived over the past 10 years, subject to data av...
    s.cell('B114', lambda: BE['B86'])
    # 115 7/ Long-run, constant balance that stabilizes the debt ratio assuming that key variable...
    s.cell('B115', lambda: TR(s, 796))
    # 116
    s.cell('B116', lambda: TR(s, 797))
    # 118 Nominal debt baseline
    s.cell('B118', lambda: TR(s, 799))
    s.put(118, 'C:X', lambda c: BE[12, c+10] / 100 * BE[48, c+10])
    # 119 Increase
    s.cell('B119', lambda: TR(s, 800))
    s.put(119, 'D:X', lambda c: S[118, c] - S[118, c-1])
    # 120 Nominal debt stress
    s.cell('B120', lambda: TR(s, 801))
    s.put(120, 'C:X', lambda c: S[59, c] / 100 * S[93, c])
    # 121 Increase
    s.cell('B121', lambda: TR(s, 802))
    s.put(121, 'D:X', lambda c: S[120, c] - S[120, c-1])
    # 122 Residual gross borrowing
    s.cell('B122', lambda: TR(s, 803))
    s.put(122, 'D:X', lambda c: S[121, c] - S[119, c])
    # 124 PV PPG baseline
    s.cell('B124', lambda: TR(s, 805))
    s.put(124, 'C:X', lambda c: EDD[391, c+2])
    # 125 PV of additional borrowing
    s.cell('B125', lambda: TR(s, 806))
    s.put(125, 'D:X', lambda c: S[39, c])
    # 126 PV PPG stress
    s.cell('B126', lambda: TR(s, 807))
    s.put(126, 'D:X', lambda c: S[124, c] + S[125, c])
    # 127 Private debt (=PV)
    s.cell('B127', lambda: TR(s, 808))
    s.put(127, 'D:X', lambda c: S[61, c] / 100 * S[93, c])
    # 128 PV total
    s.cell('B128', lambda: TR(s, 809))
    s.put(128, 'D:X', lambda c: S[126, c] + S[127, c])
    # 130 Debt service baseline
    s.cell('B130', lambda: TR(s, 811))
    s.put(130, 'D:X', lambda c: MD[18, c+17] + MD[23, c+17])
    # 131 o/w interest
    s.cell('B131', lambda: TR(s, 812))
    s.put(131, 'D:X', lambda c: MD[18, c+17])
    # 132 Debt service PPG baseline
    s.cell('B132', lambda: TR(s, 813))
    s.put(132, 'D:X', lambda c: EDD[394, c+2])
    # 134 Additional debt service stress
    s.cell('B134', lambda: TR(s, 815))
    s.put(134, 'D:X', lambda c: S[41, c])
    # 135 o/w interest
    s.cell('B135', lambda: TR(s, 816))
    s.put(135, 'D:X', lambda c: S[42, c])
    # 136 Total debt service stress
    s.cell('B136', lambda: TR(s, 817))
    s.put(136, 'D:X', lambda c: S[134, c] + S[130, c])
    # 137 PPG debt service stress
    s.cell('B137', lambda: TR(s, 818))
    s.put(137, 'D:X', lambda c: S[132, c] + S[134, c])
    # 139 New interest payments
    s.cell('B139', lambda: TR(s, 820))
    s.put(139, 'D:X', lambda c: S[131, c] + S[135, c])
    # 140 Effective rate
    s.cell('B140', lambda: TR(s, 821))
    s.put(140, 'D:X', lambda c: S[139, c] / S[120, c-1] * 100)
    # 141 Exports
    s.cell('B141', lambda: TR(s, 822))
    s.put(141, 'D:X', lambda c: S[66, c] / 100 * S[93, c])
    # 142 Revenue
    s.cell('B142', lambda: TR(s, 823))
    s.cell('C142', lambda: BE['M60'] / 100 * BE['M48'])
    s.put(142, 'D:X', lambda c: (CSP[10, c+1] - CSP[14, c+1]) / 100 * S[93, c])
    # 143 Short-term debt
    s.cell('B143', lambda: TR(s, 824))
    s.put(143, 'C:X', lambda c: MD[89, c+17])
    # 145 PPG nominal debt baseline
    s.put(145, 'C:X', lambda c: BE[13, c+10] / 100 * BE[48, c+10])
    # 146 Increase
    s.put(146, 'D:X', lambda c: S[145, c] - S[145, c-1])
    # 147 PPG nominal debt stress
    s.put(147, 'C:X', lambda c: S[60, c] / 100 * S[93, c])
    # 148 Increase
    s.put(148, 'D:X', lambda c: S[147, c] - S[147, c-1])
    # 149 Residual gross borrowing
    s.put(149, 'D:X', lambda c: S[148, c] - S[146, c])
    # 151 Exports in USD
    s.cell('C151', lambda: S['C66'] / 100 * S['C93'])
    s.put(151, 'D:X', lambda c: S[10, c] / 100 * S[156, c])
    # 152 Exports growth
    s.put(152, 'D:X', lambda c: (S[151, c] / S[151, c-1] - 1) * 100 - IF(CSP[1, c+1] == CSP['C42'], CSP['C50'], 0))
    # 153 Exports in USD stress
    s.cell('D153', lambda: S['C151'] * (1 + S['D152'] / 100))
    s.put(153, 'E:X', lambda c: S[153, c-1] * (1 + S[152, c] / 100))
    # 154 Exports in % of GDP stress
    s.put(154, 'D:X', lambda c: S[153, c] / S[93, c] * 100)
    # 156 Nominal GDP (Million of US dollars)
    s.cell('C156', lambda: S['C93'])
    s.put(156, 'D:X', lambda c: S[156, c-1] * (1 + S[16, c] / 100) * (1 + S[98, c] / 100))
    # 157
    s.put(157, 'D:X', lambda c: S[156, c] - S[93, c])
    # 159 Imports in USD
    s.put(159, 'C:X', lambda c: S[67, c] / 100 * S[93, c])
    # 160 Imports growth
    s.put(160, 'D:X', lambda c: (S[159, c] / S[159, c-1] - 1) * 100)


RULES = {
    'Baseline - public': _baseline_public,
    'Baseline - external': _baseline_external,
    'Customized Scenario - public': _customized_scenario_public,
    'Customized Scenario-External': _customized_scenario_external,
}



def compute(book, sheet):
    s = Calc(book, sheet)
    RULES[sheet](s)
    s.run()
