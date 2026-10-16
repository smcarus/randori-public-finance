"""LIC DSF input and support sheets.

- START: the working language (English / French / Portuguese / Spanish) and its column offset LANG, used by every
  translated label in the template, plus the start page's texts in that language.
- translation: the label table in the four languages. Its formula cells build labels that carry the country
  name, the unit scale, projection years or creditor names from Input 4.
- lookup: the country list (codes, ISO codes, HIPC / MDRI status) and drop-down lists; looks up the ISO code and
  counts the countries.
- Input-INSTRUCTIONS: the step-by-step instructions in the working language, and the sheet names they point to.
- Input 1 - Basics: country attributes looked up from the country code (IFS / ISO code, HIPC and MDRI status),
  past DSA vintages for the realism tools and the translated labels of the sheet.
- Input 2 - Debt Coverage: the public-debt coverage table and the default contingent-liability shock it implies.
- Input 3 - Macro-Debt data(DMX): year headers, translated labels and the derived lines of the macro and debt
  input (totals over creditors, scaled sums).
- Input 4 - External Financing: lending terms by creditor (maturity, grace, interest, grant element) including the
  locally-issued debt classified as external, with year headers and labels.
- BLEND floating calculations WB: the IBRD / IDA blend floating rate from the swap curve, interpolated linearly
  between the quoted maturities (CSE array formulas).
- Input 6(optional)-Standard Test, Input 6 - Tailored Tests: default and user-overridden settings of the standard
  and tailored stress tests (commodity exporter and market-financing flags from Trigger / Imported data).
- Input 7 - Residual Financing: terms of the marginal borrowing that fills financing gaps under stress tests.
- Input 8 - SDR: interest on the net use of SDRs and its present value.
- Imported data: the country's data for the composite indicator and realism tools, pulled from the data sheets
  (CPIA, remittances, GDP, commodity prices, previous DSA vintages).
- CI Summary: the composite indicator, its components and the debt-carrying-capacity thresholds.
- Trigger: look-ups of the imported trigger data (PPP contingent liabilities, market financing, commodities).
- Dom_Debt_Indicators, Output - Summary, Output - Submit: summary fields copied for the database and submission.

How the port works: these sheets are mostly labels, look-ups and lightly transformed copies of user input,
written as ~2,000 distinct one-off formula patterns. They are ported as the workbook's own formulas, one entry per
block of cells sharing a pattern (the formula is written for the block's first cell and filled right / down over
the block, as Excel copies it), and run by the small Excel evaluator in this module (`evaluate`). The blocks are
listed by row with the row's label. localdebt.py and realism.py use the same evaluator.
"""
import datetime
import math
import re
import sys

from openpyxl.formula.tokenizer import Token, Tokenizer

from sovrisk.srdsf.book import ci, cl


QUIRKS = [
    "translation!C1061 / D1061 and C1097 (chart titles) print TEXT('Macro-Debt_Data'!U6 / AE6) - nominal GDP of "
    "rows 6, not the years in row 5 - so the titles read '23337-35253' instead of '2024-2034'.",
    "translation!C784, C785 and C1327 refer to deleted cells ('Customized Scenario-External'!#REF!, #REF!) and "
    "return #REF!; the language switches C827, C1067, C1079:C1082, C1092, C1094 and C1349:C1353 have #REF! in "
    "some non-English branches (only reached when another language is chosen). C1079 / C1092 point the "
    "Portuguese branch at F (Spanish) cells.",
    "Input-INSTRUCTIONS!B8 takes the English text from translation row 9 but the French / Portuguese / Spanish "
    "texts from row 10 (the next instruction); B43 and B44 point the non-English branches at rows 36-37.",
    "translation!D (French) builds \"L'Ghana est-il un cas limite?\" (no elision rule), and the English label "
    "reads 'boderline'.",
    "Trigger!I9, I30, I49 (and the ratio / flag columns J, L, M of those rows) are #VALUE! and I58 is #N/A: the "
    "PPP-to-GDP column of the imported table holds those errors (Burundi has '-' for PPP capital stock, the "
    "'Utopia' test row has #N/A), and Trigger's IF(OR(G=0,H=0),..) does not guard against them.",
    "Input 4 - External Financing!D74 looks 'IDA NEW Blend fixed' up in $B$83:$D$84, which is empty (#N/A).",
    "Imported data!C88 (=DSF__COMMODITY_LATEST) is a date-formatted serial number; it is returned as the ISO "
    "date-time text the golden extraction stores for date cells.",
    "Formula cells that return \"\" are stored with an empty value in the golden book; a reference to such a "
    "cell is read back as \"\" (not as a blank, which would read as 0), e.g. Trigger!AC5:AD72 via "
    "IMPORTED_TRIGGER.",
]

SHEETS = ['START', 'translation', 'lookup', 'Input-INSTRUCTIONS', 'Input 1 - Basics', 'Input 2 - Debt Coverage', 'Input 3 - Macro-Debt data(DMX)', 'Input 4 - External Financing', 'BLEND floating calculations WB', 'Input 6(optional)-Standard Test', 'Input 6 - Tailored Tests', 'Input 7 - Residual Financing', 'Input 8 - SDR', 'Imported data', 'CI Summary', 'Trigger', 'Dom_Debt_Indicators', 'Output - Summary', 'Output - Submit']


# ====================================================================== formula engine
# The sheets ported here are mostly labels, look-ups and lightly transformed copies of user input, written as
# thousands of one-off formulas. They are ported as the workbook's own formulas (one entry per block of cells
# sharing a formula pattern, written for the block's first cell and filled right/down as Excel fills them), run by
# the small Excel evaluator below. It keeps Excel's semantics: blank = 0 / "", case-insensitive text compare,
# implicit intersection outside array formulas, array evaluation inside SUMPRODUCT / INDEX / MATCH / LOOKUP
# arguments and CSE formulas, lazy IF / IFERROR, error propagation and ROUND half away from zero.
ERRORS = ('#NULL!', '#DIV/0!', '#VALUE!', '#REF!', '#NAME?', '#NUM!', '#N/A', '#SPILL!', '#CALC!')
NA, DIV0, VALUE, REF, NUM = '#N/A', '#DIV/0!', '#VALUE!', '#REF!', '#NUM!'
MAXR, MAXC = 1048576, 16384


def is_err(v):
    return isinstance(v, str) and v in ERRORS


class XlError(Exception):
    """Raised inside scalar helpers to return an Excel error from the formula."""

    def __init__(self, e):
        self.e = e


class Ref:
    """A rectangular reference sheet!r0c0:r1c1 (1-based, inclusive)."""
    __slots__ = ('sheet', 'r0', 'c0', 'r1', 'c1')

    def __init__(self, sheet, r0, c0, r1, c1):
        self.sheet, self.r0, self.c0, self.r1, self.c1 = sheet, r0, c0, r1, c1

    @property
    def h(self):
        return self.r1 - self.r0 + 1

    @property
    def w(self):
        return self.c1 - self.c0 + 1


class Arr(list):
    """A 2-D array value (list of rows)."""


# ---------------------------------------------------------------- scalar semantics
def to_num(v):
    """A value as arithmetic sees it (numbers stored as text convert, other text is #VALUE!)."""
    if v is None:
        return 0.0
    if isinstance(v, bool):
        return 1.0 if v else 0.0
    if isinstance(v, (int, float)):
        return v
    if is_err(v):
        raise XlError(v)
    try:
        return float(v.strip().replace(',', '')) if v.strip() else _raise(VALUE)
    except ValueError:
        raise XlError(VALUE)


def _raise(e):
    raise XlError(e)


def to_bool(v):
    if v is None:
        return False
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return v != 0
    if is_err(v):
        raise XlError(v)
    if v.upper() == 'TRUE':
        return True
    if v.upper() == 'FALSE':
        return False
    raise XlError(VALUE)


def to_text(v):
    """A value as Excel's & operator writes it (General format, 15 significant digits)."""
    if v is None:
        return ''
    if isinstance(v, bool):
        return 'TRUE' if v else 'FALSE'
    if isinstance(v, (int, float)):
        if v == int(v) and abs(v) < 1e15:
            return str(int(v))
        s = format(v, '.15g')
        if 'e' in s:
            m, e = s.split('e')
            s = f'{m}E{e[0]}{e[1:].zfill(2)}'
        return s
    if is_err(v):
        raise XlError(v)
    return v


def _rank(v):
    if isinstance(v, bool):
        return 2
    if isinstance(v, str):
        return 1
    return 0


def compare(a, b):
    """-1/0/1 as Excel's comparison operators order two values."""
    if a is None:
        a = '' if isinstance(b, str) else (False if isinstance(b, bool) else 0)
    if b is None:
        b = '' if isinstance(a, str) else (False if isinstance(a, bool) else 0)
    ra, rb = _rank(a), _rank(b)
    if ra != rb:
        return -1 if ra < rb else 1
    if ra == 1:
        a, b = a.lower(), b.lower()
    return (a > b) - (a < b)


def xl_eq(a, b):
    return compare(a, b) == 0


def xl_round(x, d=0):
    d = int(d)
    m = 10.0 ** d
    y = abs(x) * m
    r = math.floor(y + 0.5)
    if abs(y + 0.5 - r) < 1e-9 * max(1, y):          # Excel rounds on the displayed 15-digit value
        r = math.floor(float(format(y, '.15g')) + 0.5)
    return math.copysign(r / m, x)


def xl_rounddown(x, d=0):
    m = 10.0 ** int(d)
    return math.copysign(math.floor(float(format(abs(x) * m, '.15g'))) / m, x)


def fmt_text(v, f):
    """TEXT(v, f) for the formats the template uses."""
    if isinstance(v, str) and v != '':
        try:
            v = float(v)
        except ValueError:
            return v
    x = to_num(v)
    if f == '#':
        r = xl_round(x, 0)
        return '' if r == 0 else str(int(r))
    if f in ('0', '#,##0'):
        r = int(xl_round(x, 0))
        return format(r, ',') if ',' in f else str(r)
    m = re.fullmatch(r'0\.(0+)', f)
    if m:
        return format(xl_round(x, len(m.group(1))), f'.{len(m.group(1))}f')
    raise NotImplementedError(f'TEXT format {f!r}')


# ---------------------------------------------------------------- parser
_A1 = re.compile(r"^(\$?)([A-Z]{1,3})(\$?)(\d+)$")
_COL = re.compile(r"^(\$?)([A-Z]{1,3})$")
_ROW = re.compile(r"^(\$?)(\d+)$")


def _split_sheet(s):
    if '!' in s:
        sh, a = s.rsplit('!', 1)
        if sh.startswith("'"):
            sh = sh[1:-1].replace("''", "'")
        return sh, a
    return None, s


def _parse_corner(x):
    """One end of an A1 reference -> (row, rowabs, col, colabs); whole rows/columns use None for the open part."""
    m = _A1.match(x)
    if m:
        return int(m.group(4)), bool(m.group(3)), ci(m.group(2)), bool(m.group(1))
    m = _COL.match(x)
    if m:
        return None, True, ci(m.group(2)), bool(m.group(1))
    m = _ROW.match(x)
    if m:
        return int(m.group(2)), bool(m.group(1)), None, True
    return None


class Parser:
    def __init__(self, text):
        self.toks = [t for t in Tokenizer(text).items if t.type != Token.WSPACE]
        self.i = 0

    def peek(self):
        return self.toks[self.i] if self.i < len(self.toks) else None

    def next(self):
        t = self.toks[self.i]
        self.i += 1
        return t

    def parse(self):
        n = self.expr()
        if self.peek() is not None:
            raise SyntaxError(f'trailing token {self.peek().value!r}')
        return n

    _LEVELS = [('=', '<>', '<', '>', '<=', '>='), ('&',), ('+', '-'), ('*', '/'), ('^',)]

    def expr(self, lvl=0):
        if lvl == len(self._LEVELS):
            return self.unary()
        n = self.expr(lvl + 1)
        while True:
            t = self.peek()
            if t is not None and t.type == Token.OP_IN and t.value in self._LEVELS[lvl]:
                self.next()
                n = ('op', t.value, n, self.expr(lvl + 1))
            else:
                return n

    def unary(self):
        t = self.peek()
        if t is not None and t.type == Token.OP_PRE:
            self.next()
            n = self.unary()
            return ('neg', n) if t.value == '-' else ('pos', n)
        n = self.primary()
        while self.peek() is not None and self.peek().type == Token.OP_POST:
            self.next()
            n = ('pct', n)
        return n

    def primary(self):
        t = self.next()
        if t.type == Token.OPERAND:
            if t.subtype == Token.NUMBER:
                n = ('const', float(t.value))
            elif t.subtype == Token.TEXT:
                n = ('const', t.value[1:-1].replace('""', '"'))
            elif t.subtype == Token.LOGICAL:
                n = ('const', t.value.upper() == 'TRUE')
            elif t.subtype == Token.ERROR:
                n = ('const', t.value)
            else:
                n = self.reference(t.value)
        elif t.type == Token.FUNC and t.subtype == Token.OPEN:
            name = t.value[:-1].upper().replace('_XLFN.', '').replace('_XLWS.', '')
            args = []
            if self.peek().type == Token.FUNC and self.peek().subtype == Token.CLOSE:
                self.next()
            else:
                while True:
                    p = self.peek()
                    if p.type == Token.SEP or (p.type == Token.FUNC and p.subtype == Token.CLOSE):
                        args.append(None)                     # omitted argument
                    else:
                        args.append(self.expr())
                    s = self.next()
                    if s.type == Token.FUNC and s.subtype == Token.CLOSE:
                        break
            n = ('func', name, args)
        elif t.type == Token.PAREN and t.subtype == Token.OPEN:
            n = self.expr()
            self.next()
        elif t.type == Token.ARRAY:
            rows, row = [], []
            while True:
                p = self.next()
                if p.type == Token.ARRAY:
                    rows.append(row)
                    break
                if p.type == Token.SEP:
                    if p.subtype == Token.ROW:
                        rows.append(row)
                        row = []
                    continue
                v = p.value
                row.append(float(v) if p.subtype == Token.NUMBER else
                           v[1:-1] if p.subtype == Token.TEXT else v.upper() == 'TRUE' if p.subtype == Token.LOGICAL
                           else v)
            n = ('array', rows)
        else:
            raise SyntaxError(f'unexpected token {t.value!r}')
        # range operator between two references (INDEX(..):INDEX(..))
        p = self.peek()
        if p is not None and p.type == Token.OP_IN and p.value == ':':
            self.next()
            n = ('range', n, self.primary())
        return n

    def reference(self, v):
        if v.endswith('#REF!'):                    # 'Sheet'!#REF! (the '!' of #REF! would split the sheet name)
            return ('const', REF)
        sheet, a = _split_sheet(v)
        if a.endswith('#REF!'):
            return ('const', REF)
        parts = a.split(':')
        corners = [_parse_corner(p) for p in parts]
        if len(parts) == 1 and corners[0] is not None and None in (corners[0][0], corners[0][2]):
            corners = [None]                       # 'ISO', 'LANG': a name, not a whole column / row
        if all(c is not None for c in corners):
            if len(corners) == 1:
                corners = corners * 2
            return ('ref', sheet, corners[0], corners[1])
        return ('name', a if sheet is None else v)


# ---------------------------------------------------------------- evaluator
class Ctx:
    """Where a formula is being evaluated: its sheet, cell and offset from the pattern's anchor cell."""
    __slots__ = ('sheet', 'row', 'col', 'dr', 'dc')

    def __init__(self, sheet, row, col, dr, dc):
        self.sheet, self.row, self.col, self.dr, self.dc = sheet, row, col, dr, dc


class Engine:
    """Evaluates formula patterns over a Book. Cells registered with add() are computed on first read, so the
    order in which blocks are listed does not matter."""

    def __init__(self, book):
        self.book = book
        self.pending = {}            # (sheet, r, c) -> (fn, anchor_r, anchor_c, array)
        self.names = {}
        self.extent = {}
        self.dates = set()           # date-formatted cells: stored as ISO text, read back as the serial number
        self.serial = {}

    # ---- registration
    def add(self, sheet, cells, formula, kind=None):
        array = kind == 'array'
        fn = self.compile(formula, array)
        ranges = cells.split()
        r0, c0 = _cell(ranges[0].split(':')[0])
        for rg in ranges:
            a, b = (rg.split(':') + [rg])[:2]
            (ra, ca), (rb, cb) = _cell(a), _cell(b)
            for r in range(ra, rb + 1):
                for c in range(ca, cb + 1):
                    self.pending[(sheet, r, c)] = (fn, r0, c0, array)
                    if kind == 'date':
                        self.dates.add((sheet, r, c))

    def run(self):
        sys.setrecursionlimit(max(sys.getrecursionlimit(), 200000))
        for key in sorted(self.pending, key=lambda k: (k[1], k[2])):
            if key in self.pending:
                self.compute(key)

    def compute(self, key):
        fn, ar, ac, array = self.pending.pop(key)
        sheet, r, c = key
        ctx = Ctx(sheet, r, c, r - ar, c - ac)
        try:
            v = fn(ctx)
        except XlError as e:
            v = e.e
        v = self.final(v, ctx, array)
        if key in self.dates and isinstance(v, (int, float)) and not isinstance(v, bool):
            self.serial[key] = v
            self.book[sheet].set(r, c, (datetime.datetime(1899, 12, 30) + datetime.timedelta(days=v)).isoformat())
            return v
        self.book[sheet].set(r, c, v)
        return v

    def final(self, v, ctx, array):
        if isinstance(v, Ref):
            v = self.cell(v.sheet, v.r0, v.c0) if array or (v.h == 1 and v.w == 1) else self.intersect(v, ctx)
        elif isinstance(v, Arr):
            v = v[0][0]
        if v is None:
            return 0
        if isinstance(v, float) and v == int(v) and abs(v) < 2 ** 53:
            return int(v)
        return v

    # ---- cell access
    def cell(self, sheet, r, c):
        key = (sheet, r, c)
        if key in self.pending:
            return self.compute(key)
        if key in self.serial:
            return self.serial[key]
        cells = self.book[sheet].cells
        v = cells.get((r, c))
        if v is None and (r, c) in cells:
            return ''                # a formula cell whose cached result is "" (stored as an empty value)
        return v

    def bounds(self, sheet):
        if sheet not in self.extent:
            ks = list(self.book[sheet].cells) + [(r, c) for s, r, c in self.pending if s == sheet]
            self.extent[sheet] = (max((k[0] for k in ks), default=1), max((k[1] for k in ks), default=1))
        return self.extent[sheet]

    def values(self, ref):
        """2-D list of a reference's values (whole rows / columns clipped to the sheet's used area)."""
        r1, c1 = ref.r1, ref.c1
        if r1 == MAXR or c1 == MAXC:
            mr, mc = self.bounds(ref.sheet)
            r1, c1 = min(r1, mr), min(c1, mc)
        return Arr([self.cell(ref.sheet, r, c) for c in range(ref.c0, c1 + 1)] for r in range(ref.r0, r1 + 1))

    def intersect(self, ref, ctx):
        if ref.h == 1 and ref.w == 1:
            return self.cell(ref.sheet, ref.r0, ref.c0)
        if ref.w == 1 and ref.r0 <= ctx.row <= ref.r1:
            return self.cell(ref.sheet, ctx.row, ref.c0)
        if ref.h == 1 and ref.c0 <= ctx.col <= ref.c1:
            return self.cell(ref.sheet, ref.r0, ctx.col)
        return VALUE

    # ---- compile
    def compile(self, formula, array=False):
        node = Parser(formula).parse()
        return self.node(node, array)

    def node(self, n, arr):
        kind = n[0]
        if kind == 'const':
            v = n[1]
            return lambda ctx: v
        if kind == 'array':
            v = Arr(n[1])
            return lambda ctx: v
        if kind == 'ref':
            return self.ref_node(n)
        if kind == 'name':
            return self.name_node(n[1])
        if kind == 'range':
            fa, fb = self.node(n[1], arr), self.node(n[2], arr)

            def rng(ctx):
                a, b = fa(ctx), fb(ctx)
                if not isinstance(a, Ref) or not isinstance(b, Ref):
                    return VALUE
                return Ref(a.sheet, min(a.r0, b.r0), min(a.c0, b.c0), max(a.r1, b.r1), max(a.c1, b.c1))
            return rng
        if kind in ('neg', 'pos', 'pct'):
            f = self.scalar(n[1], arr)
            if kind == 'pos':
                return f
            g = (lambda x: -to_num(x)) if kind == 'neg' else (lambda x: to_num(x) / 100)
            return lambda ctx: lift1(g, f(ctx))
        if kind == 'op':
            return self.op_node(n[1], self.scalar(n[2], arr), self.scalar(n[3], arr))
        if kind == 'func':
            return self.func_node(n[1], n[2], arr)
        raise ValueError(kind)

    def ref_node(self, n):
        _, sheet, (ra, raa, ca, caa), (rb, rba, cb, cba) = n
        whole_col = ra is None
        whole_row = ca is None

        def f(ctx):
            sh = sheet or ctx.sheet
            if whole_col:
                c0 = ca if caa else ca + ctx.dc
                c1 = cb if cba else cb + ctx.dc
                return Ref(sh, 1, c0, MAXR, c1) if c0 >= 1 and c1 >= 1 else REF
            if whole_row:
                r0 = ra if raa else ra + ctx.dr
                r1 = rb if rba else rb + ctx.dr
                return Ref(sh, r0, 1, r1, MAXC) if r0 >= 1 and r1 >= 1 else REF
            r0 = ra if raa else ra + ctx.dr
            r1 = rb if rba else rb + ctx.dr
            c0 = ca if caa else ca + ctx.dc
            c1 = cb if cba else cb + ctx.dc
            if min(r0, r1, c0, c1) < 1:
                return REF
            return Ref(sh, min(r0, r1), min(c0, c1), max(r0, r1), max(c0, c1))
        return f

    def name_node(self, name):
        def f(ctx):
            key = name.lower()
            if key not in self.names:
                txt = self.book.names.get(key)
                if txt is None:
                    self.names[key] = lambda c: '#NAME?'
                else:
                    self.names[key] = self.compile('=' + txt)
            return self.names[key](Ctx(ctx.sheet, ctx.row, ctx.col, 0, 0))
        return f

    def scalar(self, n, arr):
        """Compile n for use as an operand: references become values (arrays in array mode, else the cell
        that intersects the formula's row or column)."""
        f = self.node(n, arr)

        def g(ctx):
            v = f(ctx)
            if isinstance(v, Ref):
                if arr and (v.h > 1 or v.w > 1):
                    return self.values(v)
                return self.intersect(v, ctx)
            return v
        return g

    def as_array(self, n):
        """Compile n as an array argument: a reference stays a reference; expressions run in array mode."""
        return self.node(n, True)

    def op_node(self, op, fa, fb):
        if op == '&':
            g = lambda a, b: to_text(a) + to_text(b)
        elif op in ('=', '<>', '<', '>', '<=', '>='):
            def g(a, b, op=op):
                if is_err(a):
                    raise XlError(a)
                if is_err(b):
                    raise XlError(b)
                c = compare(a, b)
                return {'=': c == 0, '<>': c != 0, '<': c < 0, '>': c > 0, '<=': c <= 0, '>=': c >= 0}[op]
        else:
            def g(a, b, op=op):
                x, y = to_num(a), to_num(b)
                if op == '+':
                    return x + y
                if op == '-':
                    return x - y
                if op == '*':
                    return x * y
                if op == '/':
                    if y == 0:
                        raise XlError(DIV0)
                    return x / y
                try:
                    return x ** y
                except (OverflowError, ZeroDivisionError):
                    raise XlError(NUM)
        return lambda ctx: lift2(g, fa(ctx), fb(ctx))

    def func_node(self, name, args, arr):
        h = getattr(self, 'f_' + name, None)
        if h is None:
            raise NotImplementedError(name)
        return h(args, arr)

    # ---- argument helpers
    def flat(self, v):
        """Values of a range / array argument as a flat list (row-major)."""
        if isinstance(v, Ref):
            return [x for row in self.values(v) for x in row]
        if isinstance(v, Arr):
            return [x for row in v for x in row]
        return [v]

    def grid(self, v):
        if isinstance(v, Ref):
            return self.values(v)
        if isinstance(v, Arr):
            return v
        return Arr([[v]])

    def _opt(self, args, i, arr, default):
        if i < len(args) and args[i] is not None:
            return self.scalar(args[i], arr)
        return lambda ctx: default

    # ---- logical
    def f_IF(self, args, arr):
        c = self.scalar(args[0], arr)
        a = self.scalar(args[1], arr) if len(args) > 1 and args[1] is not None else (lambda ctx: 0)
        b = self.scalar(args[2], arr) if len(args) > 2 and args[2] is not None else \
            ((lambda ctx: 0) if len(args) > 2 else (lambda ctx: False))

        def f(ctx):
            v = c(ctx)
            if isinstance(v, Arr):
                av, bv = a(ctx), b(ctx)
                h, w = (max(x) for x in zip(_shape(v), _shape(av), _shape(bv)))

                def pick(x, p, q):
                    try:
                        return x if is_err(x) else (p if to_bool(x) else q)
                    except XlError as e:
                        return e.e
                return Arr([[pick(_at(v, i, j), _at(av, i, j), _at(bv, i, j)) for j in range(w)] for i in range(h)])
            return a(ctx) if to_bool(v) else b(ctx)
        return f

    def _andor(self, args, arr, isand):
        fs = [self.as_array(a) for a in args]

        def f(ctx):
            seen = []
            for g in fs:
                v = g(ctx)
                if isinstance(v, (Ref, Arr)):
                    for x in self.flat(v):
                        if is_err(x):
                            return x
                        if isinstance(x, (bool, int, float)):
                            seen.append(bool(x))
                else:
                    if v is None:
                        seen.append(False)
                    else:
                        seen.append(to_bool(v))
            if not seen:
                return VALUE
            return all(seen) if isand else any(seen)
        return f

    def f_AND(self, args, arr):
        return self._andor(args, arr, True)

    def f_OR(self, args, arr):
        return self._andor(args, arr, False)

    def f_IFERROR(self, args, arr):
        a, b = self.scalar(args[0], arr), self.scalar(args[1], arr) if args[1] is not None else (lambda ctx: 0)

        def f(ctx):
            try:
                v = a(ctx)
            except XlError as e:
                v = e.e
            if isinstance(v, Arr):
                return lift1(lambda x: x, v, err_ok=True, fn_err=lambda x: b(ctx) if is_err(x) else x)
            return b(ctx) if is_err(v) else v
        return f

    def f_IFNA(self, args, arr):
        a, b = self.scalar(args[0], arr), self.scalar(args[1], arr)

        def f(ctx):
            try:
                v = a(ctx)
            except XlError as e:
                v = e.e
            return b(ctx) if v == NA else v
        return f

    def _is(self, args, arr, test):
        f0 = self.node(args[0], arr)

        def f(ctx):
            try:
                v = f0(ctx)
            except XlError as e:
                v = e.e
            if isinstance(v, Ref):
                v = self.values(v) if arr and (v.h > 1 or v.w > 1) else self.intersect(v, ctx)
            if isinstance(v, Arr):
                return Arr([[test(x) for x in row] for row in v])
            return test(v)
        return f

    def f_ISNUMBER(self, args, arr):
        return self._is(args, arr, lambda v: isinstance(v, (int, float)) and not isinstance(v, bool))

    def f_ISBLANK(self, args, arr):
        return self._is(args, arr, lambda v: v is None)

    def f_ISERROR(self, args, arr):
        return self._is(args, arr, is_err)

    def f_ISNA(self, args, arr):
        return self._is(args, arr, lambda v: v == NA)

    # ---- reference functions
    def f_ROW(self, args, arr):
        if not args:
            return lambda ctx: ctx.row
        g = self.node(args[0], arr)

        def f(ctx):
            r = g(ctx)
            if not isinstance(r, Ref):
                return r if is_err(r) else VALUE
            if arr and r.h > 1:
                return Arr([[float(i)] for i in range(r.r0, r.r1 + 1)])
            return r.r0
        return f

    def f_COLUMN(self, args, arr):
        if not args:
            return lambda ctx: ctx.col
        g = self.node(args[0], arr)

        def f(ctx):
            r = g(ctx)
            if not isinstance(r, Ref):
                return r if is_err(r) else VALUE
            return r.c0
        return f

    def f_COLUMNS(self, args, arr):
        g = self.as_array(args[0])

        def f(ctx):
            v = g(ctx)
            if isinstance(v, Ref):
                return v.w
            if isinstance(v, Arr):
                return len(v[0])
            return 1
        return f

    def f_OFFSET(self, args, arr):
        g = self.node(args[0], arr)
        rs, cs = self._opt(args, 1, arr, 0), self._opt(args, 2, arr, 0)
        hs, ws = self._opt(args, 3, arr, None), self._opt(args, 4, arr, None)

        def f(ctx):
            r = g(ctx)
            if not isinstance(r, Ref):
                return r if is_err(r) else VALUE
            dr, dc = int(to_num(rs(ctx))), int(to_num(cs(ctx)))
            h, w = hs(ctx), ws(ctx)
            h = r.h if h is None else int(to_num(h))
            w = r.w if w is None else int(to_num(w))
            r0, c0 = r.r0 + dr, r.c0 + dc
            if r0 < 1 or c0 < 1 or h < 1 or w < 1:
                return REF
            return Ref(r.sheet, r0, c0, r0 + h - 1, c0 + w - 1)
        return f

    def f_INDEX(self, args, arr):
        g = self.as_array(args[0])
        rs = self._opt(args, 1, arr, None)
        cs = self._opt(args, 2, arr, None)
        two = len(args) > 2

        def f(ctx):
            a = g(ctx)
            if is_err(a):
                return a
            ri, cj = rs(ctx), cs(ctx)
            ri = 0 if ri is None else int(to_num(ri))
            cj = 0 if cj is None else int(to_num(cj))
            if isinstance(a, Ref):
                h, w = a.h, a.w
                if a.r1 == MAXR or a.c1 == MAXC:
                    mr, mc = self.bounds(a.sheet)
                    h = min(a.r1, max(mr, a.r0)) - a.r0 + 1 if a.r1 == MAXR else h
                    w = min(a.c1, max(mc, a.c0)) - a.c0 + 1 if a.c1 == MAXC else w
            else:
                a = self.grid(a)
                h, w = len(a), len(a[0])
            if not two and h == 1 and w > 1:          # INDEX(row, n): n-th column
                ri, cj = 1, ri
            if ri < 0 or cj < 0 or ri > h or cj > w:
                return REF
            if isinstance(a, Ref):
                r0, r1 = (a.r0, a.r1) if ri == 0 else (a.r0 + ri - 1,) * 2
                c0, c1 = (a.c0, a.c1) if cj == 0 else (a.c0 + cj - 1,) * 2
                return Ref(a.sheet, r0, c0, r1, c1)
            if ri == 0 and cj == 0:
                return a
            if ri == 0:
                return Arr([[row[cj - 1]] for row in a])
            if cj == 0:
                return Arr([a[ri - 1]])
            return a[ri - 1][cj - 1]
        return f

    def f_CELL(self, args, arr):
        what, g = self.scalar(args[0], arr), self.node(args[1], arr)

        def f(ctx):
            r = g(ctx)
            if str(what(ctx)).lower() != 'address' or not isinstance(r, Ref):
                return VALUE
            return f'${cl(r.c0)}${r.r0}'
        return f

    def f_ADDRESS(self, args, arr):
        r, c = self.scalar(args[0], arr), self.scalar(args[1], arr)
        return lambda ctx: f'${cl(int(to_num(c(ctx))))}${int(to_num(r(ctx)))}'

    # ---- look-ups
    def f_MATCH(self, args, arr):
        x, g = self.scalar(args[0], arr), self.as_array(args[1])
        kind = self._opt(args, 2, arr, 1)

        def f(ctx):
            v = x(ctx)
            if is_err(v):
                return v
            seq = self.flat(g(ctx))
            return xl_match(v, seq, int(to_num(kind(ctx))))
        return f

    def f_VLOOKUP(self, args, arr):
        x, g, col = self.scalar(args[0], arr), self.as_array(args[1]), self.scalar(args[2], arr)
        approx = self._opt(args, 3, arr, True)

        def f(ctx):
            v = x(ctx)
            if is_err(v):
                return v
            t = g(ctx)
            if is_err(t):
                return t
            k = int(to_num(col(ctx)))
            if isinstance(t, Ref):
                first = [self.cell(t.sheet, r, t.c0) for r in range(t.r0, min(t.r1, self.bounds(t.sheet)[0]) + 1)]
                i = xl_match(v, first, 1 if to_bool(approx(ctx)) else 0)
                if is_err(i):
                    return i
                if k < 1 or k > t.w:
                    return REF
                return self.cell(t.sheet, t.r0 + i - 1, t.c0 + k - 1)
            t = self.grid(t)
            i = xl_match(v, [row[0] for row in t], 1 if to_bool(approx(ctx)) else 0)
            return i if is_err(i) else t[i - 1][k - 1]
        return f

    def f_XLOOKUP(self, args, arr):
        x, la, ra = self.scalar(args[0], arr), self.as_array(args[1]), self.as_array(args[2])
        nf = self.scalar(args[3], arr) if len(args) > 3 and args[3] is not None else None

        def f(ctx):
            v = x(ctx)
            if isinstance(v, Arr):
                v = v[0][0]
            if is_err(v):
                return v
            i = xl_match(v, self.flat(la(ctx)), 0)
            if is_err(i):
                return nf(ctx) if nf is not None else NA
            r = ra(ctx)
            if isinstance(r, Ref):
                if r.w == 1:
                    return Ref(r.sheet, r.r0 + i - 1, r.c0, r.r0 + i - 1, r.c0)
                return Ref(r.sheet, r.r0, r.c0 + i - 1, r.r0, r.c0 + i - 1)
            g = self.grid(r)
            return g[i - 1][0] if len(g[0]) == 1 else g[0][i - 1]
        return f

    def f_LOOKUP(self, args, arr):
        x, la = self.scalar(args[0], arr), self.as_array(args[1])
        ra = self.as_array(args[2]) if len(args) > 2 else la

        def f(ctx):
            v = x(ctx)
            seq = self.flat(la(ctx))
            best = NA
            for i, s in enumerate(seq):
                if s is None or is_err(s) or _rank(s) != _rank(v):
                    continue
                if compare(s, v) <= 0:
                    best = i + 1
            if is_err(best):
                return best
            return self.flat(ra(ctx))[best - 1]
        return f

    # ---- aggregates
    def _nums(self, fs, ctx, count_text=False):
        out = []
        for g in fs:
            v = g(ctx)
            if isinstance(v, (Ref, Arr)):
                for x in self.flat(v):
                    if is_err(x):
                        raise XlError(x)
                    if isinstance(x, (int, float)) and not isinstance(x, bool):
                        out.append(x)
            elif v is not None:
                out.append(to_num(v))
        return out

    def _agg(self, args, fn):
        fs = [self.as_array(a) for a in args]

        def f(ctx):
            return fn(self._nums(fs, ctx))
        return f

    def f_SUM(self, args, arr):
        return self._agg(args, lambda xs: sum(xs))

    def f_MAX(self, args, arr):
        return self._agg(args, lambda xs: max(xs) if xs else 0)

    def f_AVERAGE(self, args, arr):
        return self._agg(args, lambda xs: sum(xs) / len(xs) if xs else DIV0)

    def f_COUNT(self, args, arr):
        fs = [self.as_array(a) for a in args]

        def f(ctx):
            n = 0
            for g in fs:
                v = g(ctx)
                for x in (self.flat(v) if isinstance(v, (Ref, Arr)) else [v]):
                    if isinstance(x, (int, float)) and not isinstance(x, bool):
                        n += 1
            return n
        return f

    def f_COUNTA(self, args, arr):
        fs = [self.as_array(a) for a in args]
        return lambda ctx: sum(1 for g in fs for x in self.flat(g(ctx)) if x is not None)

    def f_SUMPRODUCT(self, args, arr):
        fs = [self.as_array(a) for a in args]

        def f(ctx):
            gs = [self.grid(g(ctx)) for g in fs]
            h, w = len(gs[0]), len(gs[0][0])
            if any(len(g) != h or len(g[0]) != w for g in gs):
                return VALUE
            t = 0.0
            for i in range(h):
                for j in range(w):
                    p = 1.0
                    for g in gs:
                        x = g[i][j]
                        if is_err(x):
                            return x
                        p *= x if isinstance(x, (int, float)) and not isinstance(x, bool) else 0.0
                    t += p
            return t
        return f

    def f_NPV(self, args, arr):
        rate = self.scalar(args[0], arr)
        fs = [self.as_array(a) for a in args[1:]]

        def f(ctx):
            r = to_num(rate(ctx))
            xs = self._nums(fs, ctx)
            return sum(x / (1 + r) ** (i + 1) for i, x in enumerate(xs))
        return f

    # ---- maths / text
    def _scalar_fn(self, args, arr, fn, n):
        fs = [self.scalar(a, arr) if a is not None else (lambda ctx: None) for a in args]

        def f(ctx):
            vals = [g(ctx) for g in fs]
            if any(isinstance(v, Arr) for v in vals):
                return liftn(fn, vals)
            for v in vals:
                if is_err(v):
                    return v
            return fn(*vals)
        return f

    def f_ROUND(self, args, arr):
        return self._scalar_fn(args, arr, lambda x, d=0: xl_round(to_num(x), to_num(d)), 2)

    def f_ROUNDDOWN(self, args, arr):
        return self._scalar_fn(args, arr, lambda x, d=0: xl_rounddown(to_num(x), to_num(d)), 2)

    def f_TEXT(self, args, arr):
        return self._scalar_fn(args, arr, lambda v, fm: fmt_text(v, to_text(fm)), 2)

    def f_VALUE(self, args, arr):
        def value(v):
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                return v
            if v is None:
                return 0
            s = to_text(v).strip().replace(',', '')
            try:
                return float(s[:-1]) / 100 if s.endswith('%') else float(s)
            except ValueError:
                return VALUE
        return self._scalar_fn(args, arr, value, 1)

    def f_NUMBERVALUE(self, args, arr):
        def value(v, *_):
            s = to_text(v).strip()
            if s == '':
                return 0
            try:
                return float(s.replace(',', ''))
            except ValueError:
                return VALUE
        return self._scalar_fn(args, arr, value, 1)

    def f_LEFT(self, args, arr):
        return self._scalar_fn(args, arr, lambda s, n=1: to_text(s)[:int(to_num(1 if n is None else n))], 2)

    def f_RIGHT(self, args, arr):
        def right(s, n=1):
            n = int(to_num(1 if n is None else n))
            return to_text(s)[-n:] if n > 0 else ''
        return self._scalar_fn(args, arr, right, 2)

    def f_MID(self, args, arr):
        return self._scalar_fn(args, arr,
                               lambda s, a, n: to_text(s)[int(to_num(a)) - 1:int(to_num(a)) - 1 + int(to_num(n))], 3)

    def f_CONCATENATE(self, args, arr):
        return self._scalar_fn(args, arr, lambda *vs: ''.join(to_text(v) for v in vs), len(args))


def _cell(a):
    m = _A1.match(a)
    return int(m.group(4)), ci(m.group(2))


def xl_match(x, seq, kind=0):
    """MATCH(x, seq, kind): exact (0) or the last position of the ascending run with value <= x (1) / >= x (-1)."""
    if kind == 0:
        if isinstance(x, str) and any(ch in x for ch in '*?'):
            pat = re.compile('^' + re.escape(x).replace(r'\*', '.*').replace(r'\?', '.') + '$', re.I | re.S)
            for i, v in enumerate(seq):
                if isinstance(v, str) and pat.match(v):
                    return i + 1
            return NA
        for i, v in enumerate(seq):
            if v is not None and _rank(v) == _rank(x) and compare(v, x) == 0:
                return i + 1
        return NA
    # approximate match: binary search as Excel does it
    lo, hi, best = 0, len(seq) - 1, NA
    while lo <= hi:
        mid = (lo + hi) // 2
        j = mid
        while j >= lo and (seq[j] is None or _rank(seq[j]) != _rank(x) or is_err(seq[j])):
            j -= 1
        if j < lo:
            lo = mid + 1
            continue
        c = compare(seq[j], x)
        if (c <= 0) if kind == 1 else (c >= 0):
            best = j + 1
            lo = mid + 1
        else:
            hi = j - 1
    return best


# ---------------------------------------------------------------- array lifting
def _shape(v):
    return (len(v), len(v[0])) if isinstance(v, Arr) else (1, 1)


def _at(v, i, j):
    if not isinstance(v, Arr):
        return v
    h, w = len(v), len(v[0])
    if i >= h and h != 1 or j >= w and w != 1:
        return NA
    return v[0 if h == 1 else i][0 if w == 1 else j]


def _safe(fn, *a):
    for x in a:
        if is_err(x):
            return x
    try:
        return fn(*a)
    except XlError as e:
        return e.e


def lift1(fn, v, err_ok=False, fn_err=None):
    if isinstance(v, Arr):
        if fn_err is not None:
            return Arr([[fn_err(x) for x in row] for row in v])
        return Arr([[_safe(fn, x) for x in row] for row in v])
    if is_err(v):
        return v
    return fn(v)


def lift2(fn, a, b):
    if isinstance(a, Arr) or isinstance(b, Arr):
        (ha, wa), (hb, wb) = _shape(a), _shape(b)
        h, w = max(ha, hb), max(wa, wb)
        return Arr([[_safe(fn, _at(a, i, j), _at(b, i, j)) for j in range(w)] for i in range(h)])
    if is_err(a):
        return a
    if is_err(b):
        return b
    return fn(a, b)


def liftn(fn, vals):
    shapes = [_shape(v) for v in vals]
    h, w = max(s[0] for s in shapes), max(s[1] for s in shapes)
    return Arr([[_safe(fn, *[_at(v, i, j) for v in vals]) for j in range(w)] for i in range(h)])


def evaluate(book, sheet, blocks):
    """Compute the formula cells of `sheet`. blocks: (cells, formula[, kind]) where cells lists the block's
    ranges (the formula is written for the first cell and filled over the rest, as Excel copies it) and kind is
    'array' for a CSE formula or 'date' for a date-formatted cell."""
    eng = Engine(book)
    for b in blocks:
        eng.add(sheet, b[0], b[1], b[2] if len(b) > 2 else None)
    eng.run()
    return eng


# ====================================================================== the sheets
BLOCKS = {
    'START': [
        # row 2
        ('B2', '=+IF(L10="English",B50,IF(L10="French",B51,IF(L10="Portuguese",B52,IF(L10="Spanish",B53," "))))'),
        # row 10
        ('B10', '=+IF(L10="English",A26,IF(L10="French",A27,IF(L10="Portuguese",A28,IF(L10="Spanish",A29," "))))'),
        ('L10', '=VLOOKUP(K10, lookup!$BB$4:$BC$7, 2, FALSE)'),
        ('M10', '=IF(L10="English",0,IF(L10="French",1,IF(L10="Portuguese",2,3)))'),
        # row 19
        ('B19', '=+IF(L10="English",B55,IF(L10="French",B56,IF(L10="Portuguese",B57,IF(L10="Spanish",B58," "))))'),
        ('I19', '=+IF(L10="English",I50,IF(L10="French",I51,IF(L10="Portuguese",I52,IF(L10="Spanish",I53," "))))'),
        # row 21
        ('B21', '=+IF(L10="English",B60,IF(L10="French",B61,IF(L10="Portuguese",B62,IF(L10="Spanish",B63," "))))'),
        # row 22
        ('B22', '=+IF(L10="English",B65,IF(L10="French",B66,IF(L10="Portuguese",B67,IF(L10="Spanish",B68," "))))'),
    ],
    'translation': [
        # row 9: Confirm the past DSA vintages used for the realism tools - the previou...
        ('I9 I15 I48 I99 I107 I227:I228 I230 I280 I293 I295 I549', '=Int_Ext'),
        # row 439: Summary
        ('C439', '=C440&" "&C441&" "&C442&" "&C443&" "&C444'),
        # row 441: get dynamic col. Name
        ('C441', "=MID(ADDRESS(ROW(), COLUMN('Input 4 - External Financing'!B10)), 2,1)"),
        ('D441 D443', '=C441'),
        # row 443: get dynamic col. Name
        ('C443', "=MID(ADDRESS(ROW(), COLUMN('Input 3 - Macro-Debt data(DMX)'!B100)), 2,1)"),
        # row 497
        ('C497:F497', '=C402'),
        # row 499
        ('C499:F499', '=C824'),
        # row 525
        ('C525:F525', '=C636'),
        # row 617: Multilaterals
        ('E617:F617', '=+E294'),
        # row 618: FMI
        ('F618:F619', '=F455'),
        # row 620
        ('D620:D621', '=+IF(\'Input 4 - External Financing\'!B12="Intitulé","…",\'Input 4 - External Financing\'!B12)'),
        ('E620:E621', '=+IF(\'Input 4 - External Financing\'!B12="Descritor","…",\'Input 4 - External Financing\'!B12)'),
        ('F620:F621', '=+IF(\'Input 4 - External Financing\'!B12="Descriptor","…",\'Input 4 - External Financing\'!B12)'),
        # row 622: Autres multilatéraux
        ('E622:F623 D627:F627 E628:F628', '=+E459'),
        # row 624: CP
        ('E624:F624', '=+E462'),
        # row 625
        ('D625:D626', '=+IF(\'Input 4 - External Financing\'!B26="Intitulé","…",\'Input 4 - External Financing\'!B26)'),
        ('E625:E626', '=+IF(\'Input 4 - External Financing\'!B26="Descritor","…",\'Input 4 - External Financing\'!B26)'),
        ('F625:F626', '=+IF(\'Input 4 - External Financing\'!B26="Descriptor","…",\'Input 4 - External Financing\'!B26)'),
        # row 629
        ('D629:D630', '=+IF(\'Input 4 - External Financing\'!B32="Intitulé","…",\'Input 4 - External Financing\'!B32)'),
        ('E629:E630', '=+IF(\'Input 4 - External Financing\'!B32="Descritor","…",\'Input 4 - External Financing\'!B32)'),
        ('F629:F630', '=+IF(\'Input 4 - External Financing\'!B32="Descriptor","…",\'Input 4 - External Financing\'!B32)'),
        # row 631
        ('D631:F631 E632:F632 D635:F635', '=+D478'),
        # row 633
        ('D633', '=+IF(\'Input 4 - External Financing\'!B38="Intitulé","…",\'Input 4 - External Financing\'!B38)'),
        ('E633', '=+IF(\'Input 4 - External Financing\'!B38="Descritor","…",\'Input 4 - External Financing\'!B38)'),
        ('F633', '=+IF(\'Input 4 - External Financing\'!B38="Descriptor","…",\'Input 4 - External Financing\'!B38)'),
        # row 634
        ('D634', '=+IF(\'Input 4 - External Financing\'!B40="Intitulé","…",\'Input 4 - External Financing\'!B40)'),
        ('E634', '=+IF(\'Input 4 - External Financing\'!B40="Descritor","…",\'Input 4 - External Financing\'!B40)'),
        ('F634', '=+IF(\'Input 4 - External Financing\'!B40="Descriptor","…",\'Input 4 - External Financing\'!B40)'),
        # row 774
        ('D774 D778', "=+'Customized Scenario-External'!B129"),
        # row 784: Profile du Choc (PC) d'une variation des prix des produits de base sur...
        ('C784', '=+"Shock Profile (SP) for Commodity Prices\' Impact on "&\'Customized Scenario-External\'!#REF!&" (Change in "&\'Customized Scenario-External\'!#REF!&" = SP*Change in Commodity prices)"'),
        # row 785: Elasticité des exportations/ PIB
        ('C785', '=+"Elasticity of real GDP to "&\'Customized Scenario-External\'!#REF!&""'),
        # row 827: Cette feuille permet à l'utilisateur de définir des chocs personnalisé...
        ('C827', '=++IF(START!L10="English",C832,IF(START!L10="French",D832,IF(START!L10="Portuguese",F831,\'Customized Scenario-External\'!#REF!)))'),
        # row 842
        ('C842', '="Is "& \'Input 1 - Basics\'!C7&" a boderline case?"'),
        ('D842', '="L\'"&\'Input 1 - Basics\'!C7&" est-il un cas limite?"'),
        ('E842', '="O "&\'Input 1 - Basics\'!C7&" é um caso limítrofe?"'),
        # row 843: Borderline Bandwidth
        ('F843', '="¿Es "& \'Input 1 - Basics\'!C7&" un caso dudoso?"'),
        # row 931: Total des besoins de financement bruts (milliards de dollars EU)
        ('C931', '="Gross external financing need ("&TEXT(\'Input 1 - Basics\'!C19,"#")&" of U.S. dollars)"'),
        # row 943: Flux d'aide (en milliards de dollars)
        ('C943', '="Aid flows (in "&TEXT(\'Input 1 - Basics\'!C19,"#")&" of US dollars)"'),
        # row 950: PIB nominal (milliards de dollars EU)
        ('C950', '="Nominal GDP ("&TEXT(\'Input 1 - Basics\'!C19,"#")&" of US dollars)  "'),
        # row 952: VA de la dette extérieure CGE (milliards de dollars EU)
        ('C952', '="PV of PPG external debt (in "&TEXT(\'Input 1 - Basics\'!C19,"#")&" of US dollars)"'),
        # row 954: Envois de fonds bruts des travailleurs (milliards de dollars EU)
        ('C954', '="Gross workers\' remittances ("&TEXT(\'Input 1 - Basics\'!C19,"#")&" of US dollars)  "'),
        # row 1042
        ('C1042:F1042', '=C963'),
        # row 1061
        ('C1061', '="Figure XXX."&\'Input 1 - Basics\'!C7&": Indicators of Public Debt Under Alternative Scenarios, "&TEXT(\'Macro-Debt_Data\'!U6,"#")&"-"&TEXT(\'Macro-Debt_Data\'!AE6,"#")&" 1/"'),
        ('D1061', '="Graphique XXX."&\'Input 1 - Basics\'!C7&" : Indicateurs d\'endettement public selon divers scénarios, "&TEXT(\'Macro-Debt_Data\'!U6,"#")&"-"&TEXT(\'Macro-Debt_Data\'!AE6,"#")&" 1/"'),
        # row 1067
        ('C1067', '=+IF(START!L10="English",C1061,IF(START!L10="French",D1061,IF(START!L10="Portuguese",#REF!,#REF!)))'),
        # row 1068: Ref.
        ('C1068:F1068', '=C1540'),
        # row 1079
        ('C1079', '=+IF(START!L10="English",C1097,IF(START!L10="French",#REF!,IF(START!L10="Portuguese",F1092,#REF!)))'),
        # row 1080
        ('C1080', '=+IF(START!L10="English",C1098,IF(START!L10="French",#REF!,IF(START!L10="Portuguese",F1093,#REF!)))'),
        # row 1081
        ('C1081', '=+IF(START!L10="English",C1085,IF(START!L10="French",#REF!,IF(START!L10="Portuguese",E1085,#REF!)))'),
        # row 1082
        ('C1082', '=+IF(START!L10="English",C1086,IF(START!L10="French",#REF!,IF(START!L10="Portuguese",E1086,#REF!)))'),
        # row 1087
        ('C1087', '=TEXT(\'Output 3-1 Stress-external\'!A9,"#")'),
        # row 1088
        ('C1088', '=TEXT(\'Output 3-1 Stress-external\'!A33,"#")'),
        # row 1089
        ('C1089', '=TEXT(\'Output 3-1 Stress-external\'!A67,"#")'),
        # row 1090
        ('C1090', '=TEXT(\'Output 3-1 Stress-external\'!A81,"#")'),
        # row 1092: O teste de stress mais extremo é o que produz o rácio mais elevado em ...
        ('C1092', '=+IF(START!L10="English",C1097,IF(START!L10="French",D1097,IF(START!L10="Portuguese",F1092,#REF!)))'),
        # row 1094
        ('C1094', '=+IF(START!L10="English",C1100,IF(START!L10="French",D1100,IF(START!L10="Portuguese",F1094,#REF!)))'),
        # row 1097: 1/ Le test de résistance le plus extrême est celui qui produit le rati...
        ('C1097', '="1/ The most extreme stress test is the test that yields the highest ratio in or before "&TEXT(\'Macro-Debt_Data\'!AE6,"#")&". Stress tests with one-off breaches is also presented."'),
        # row 1100: Graphique XX. Ghana : Indicateurs de la dette extérieure contractée ou...
        ('C1100', '=+"Figure XX. "&\'Input 1 - Basics\'!C7&": Indicators of Public and Publicly Guaranteed External Debt under Alternatives Scenarios, "&TEXT(\'Macro-Debt_Data\'!U5,"#")&"-"&TEXT(\'Macro-Debt_Data\'!AO5,"#")&" 1/"'),
        # row 1139
        ('C1139', '="Table 3. "&\'Input 1 - Basics\'!C7&": Sensitivity Analysis for Key Indicators of Public and Publicly Guaranteed External Debt, "&TEXT(\'Macro-Debt_Data\'!U5,"#")&"-"&TEXT(\'Macro-Debt_Data\'!AE5,"#")&" (continued)"'),
        ('D1139', '="Tableau xx. "&\'Input 1 - Basics\'!C7&" : Analyse de sensibilité des principaux indicateurs de dette extérieure contractée ou garantie par l\'État, "&TEXT(\'Macro-Debt_Data\'!U5,"#")&"-"&TEXT(\'Macro-Debt_Data\'!AE5,"#")&" (continued)"'),
        ('E1139', '="Tabela xx. "&\'Input 1 - Basics\'!C7&": Análise de Sensibilidade dos Principais Indicadores da Dívida Externa Pública e com Garantia Pública, "&TEXT(\'Macro-Debt_Data\'!U5,"#")&"-"&TEXT(\'Macro-Debt_Data\'!AE5,"#")&" (continuação)"'),
        ('F1139', '="Cuadro xx. "&\'Input 1 - Basics\'!C7&": Análisis de sensibilidad de indicadores clave de deuda externa pública y con garantía pública, "&TEXT(\'Macro-Debt_Data\'!U5,"#")&"-"&TEXT(\'Macro-Debt_Data\'!AE5,"#")&" (continuación)"'),
        # row 1140: (In percent)
        ('E1140', '=+E1105'),
        # row 1183: A2. Solde primaire inchangé par rapport à son niveau de 2013
        ('C1183', '="A2. Primary balance is unchanged from "&TEXT(\'Macro-Debt_Data\'!U5,"#")'),
        # row 1188: B1. Croissance du PIB réel à sa moyenne historique moins un écart-type...
        ('C1188', '="B1. Real GDP growth is at historical average minus one standard deviations in "&TEXT(\'Macro-Debt_Data\'!V5,"#")&"-"&TEXT(\'Macro-Debt_Data\'!W5,"#")'),
        # row 1189: B2. Solde primaire à sa moyenne historique moins un écart-type en 2014...
        ('C1189', '="B2. Primary balance is at historical average minus one standard deviations in "&TEXT(\'Macro-Debt_Data\'!V5,"#")&"-"&TEXT(\'Macro-Debt_Data\'!W5,"#")'),
        # row 1191: B4. Dépréciation réelle ponctuelle de 30 % en 2014
        ('C1191', '="B4. One-time 30 percent real depreciation in "&TEXT(\'Macro-Debt_Data\'!V5,"#")'),
        # row 1192: B5. Augmentation de 10 % du PIB des autres flux générateurs d'endettem...
        ('C1192', '="B5. 10 percent of GDP increase in other debt-creating flows in "&TEXT(\'Macro-Debt_Data\'!V5,"#")'),
        # row 1202: Reference
        ('C1202:F1202', '=C697'),
        # row 1242: Ref.
        ('C1242:F1242', '=C697'),
        # row 1249: Reference
        ('C1249:F1249', '=C1232'),
        # row 1255
        ('C1255:F1255', '=C$1113'),
        # row 1280: Ref.
        ('C1280:F1280', '=C697'),
        # row 1282
        ('C1282', '=+IF(START!L10="English",C1300,IF(START!L10="French",D1300,IF(START!L10="Portuguese",E1300,F1300)))'),
        # row 1283
        ('C1283', '=+IF(START!L10="English",C1301,IF(START!L10="French",D1301,IF(START!L10="Portuguese",E1301,F1301)))'),
        # row 1284
        ('C1284', '=+IF(START!L10="English",C1302,IF(START!L10="French",D1302,IF(START!L10="Portuguese",E1302,F1302)))'),
        # row 1285
        ('C1285', '=+IF(START!L10="English",C1303,IF(START!L10="French",D1303,IF(START!L10="Portuguese",E1303,F1303)))'),
        # row 1286
        ('C1286', '="b."&TEXT(\'Output 3-1 Stress-external\'!A9,"#")'),
        # row 1287
        ('C1287', '="c."&TEXT(\'Output 3-1 Stress-external\'!A33,"#")'),
        # row 1289
        ('C1289', '="d."&TEXT(\'Output 3-1 Stress-external\'!A57,"#")'),
        # row 1290
        ('C1290', '="e."&TEXT(\'Output 3-1 Stress-external\'!A81,"#")'),
        # row 1292
        ('C1292', '=+IF(START!L10="English",C1310,IF(START!L10="French",D1310,IF(START!L10="Portuguese",E1310,F1310)))'),
        # row 1293
        ('C1293', '=+IF(START!L10="English",C1311,IF(START!L10="French",D1311,IF(START!L10="Portuguese",E1311,F1311)))'),
        # row 1294
        ('C1294', '=+IF(START!L10="English",C1312,IF(START!L10="French",D1312,IF(START!L10="Portuguese",E1312,F1312)))'),
        # row 1311
        ('C1311', '="1/ The most extreme stress test is the test that yields the highest ratio in "&TEXT(\'Macro-Debt_Data\'!AE5,"#")&". "'),
        ('D1311', '="1/ Le test de résistance le plus extrême est celui qui produit le ratio le plus élevé en "&TEXT(\'Macro-Debt_Data\'!AE5,"#")&". "'),
        ('E1311', '="1/ O teste de estresse mais extremo é o que produz o rácio mais elevado em "&TEXT(\'Macro-Debt_Data\'!AE5,"#")&". "'),
        ('F1311', '="1/ La prueba de tensión más severa es la que arroja la mayor relación en "&TEXT(\'Macro-Debt_Data\'!AE5,"#")&" o antes. "'),
        # row 1312
        ('C1312', '="Figure XXX."&\'Input 1 - Basics\'!C7&": Indicators of Public Debt Under Alternative Scenarios, "&TEXT(\'Macro-Debt_Data\'!U5,"#")&"-"&TEXT(\'Macro-Debt_Data\'!AE5,"#")&" 1/"'),
        ('D1312', '="Graphique XXX."&\'Input 1 - Basics\'!C7&" : Indicateurs d\'endettement public selon divers scénarios, "&TEXT(\'Macro-Debt_Data\'!U5,"#")&"-"&TEXT(\'Macro-Debt_Data\'!AE5,"#")&" 1/"'),
        ('E1312', '="Figura XXX. "&\'Input 1 - Basics\'!C7&": Indicadores da Dívida Pública em Cenários Alternativos, "&TEXT(\'Macro-Debt_Data\'!U5,"#")&"-"&TEXT(\'Macro-Debt_Data\'!AE5,"#")&" 1/"'),
        ('F1312', '="Gráfico XXX. "&\'Input 1 - Basics\'!C7&": Indicadores de deuda pública en escenarios alternativos, "&TEXT(\'Macro-Debt_Data\'!U5,"#")&"-"&TEXT(\'Macro-Debt_Data\'!AE5,"#")&" 1/"'),
        # row 1321
        ('C1321', '=+IF(START!L10="English",C1338,IF(START!L10="French",D1338,IF(START!L10="Portuguese",E1338,F1338)))'),
        # row 1322
        ('C1322', '=+IF(START!L10="English",C1339,IF(START!L10="French",D1339,IF(START!L10="Portuguese",E1339,F1339)))'),
        # row 1323
        ('C1323', '=+IF(START!L10="English",C1340,IF(START!L10="French",D1340,IF(START!L10="Portuguese",E1340,F1340)))'),
        # row 1324
        ('C1324', '=+IF(START!L10="English",C1341,IF(START!L10="French",D1341,IF(START!L10="Portuguese",E1341,F1341)))'),
        # row 1325
        ('C1325', '="b."&TEXT(\'Output 3-1 Stress-external\'!A9,"#")'),
        # row 1326
        ('C1326', '="c."&TEXT(\'Output 3-1 Stress-external\'!A33,"#")'),
        # row 1327
        ('C1327', '="d."&TEXT(#REF!,"#")'),
        # row 1328
        ('C1328', '="d."&TEXT(\'Output 3-1 Stress-external\'!A57,"#")'),
        # row 1329
        ('C1329', '="e."&TEXT(\'Output 3-1 Stress-external\'!A81,"#")'),
        # row 1331
        ('C1331', '=+IF(START!L10="English",C1342,IF(START!L10="French",D1342,IF(START!L10="Portuguese",E1342,F1342)))'),
        # row 1332: Summary
        ('C1332', '=+IF(START!L10="English",C1335,IF(START!L10="French",D1335,IF(START!L10="Portuguese",E1335,F1335)))'),
        # row 1333: Summary
        ('C1333', '=+IF(START!L10="English",C1336,IF(START!L10="French",D1336,IF(START!L10="Portuguese",E1336,F1336)))'),
        # row 1334: Summary
        ('C1334', '=+IF(START!L10="English",C1337,IF(START!L10="French",D1337,IF(START!L10="Portuguese",E1337,F1337)))'),
        # row 1335: 1/ Le test de résistance le plus extrême est celui qui produit le rati...
        ('C1335', '="1/ The most extreme stress test is the test that yields the highest ratio in "&TEXT(\'Macro-Debt_Data\'!AE5,"#")&". "'),
        ('E1335', '="1/ O teste de estresse mais extremo é o que produz o rácio mais elevado em "&TEXT(\'Macro-Debt_Data\'!AE5,"#")&". "'),
        ('F1335', '="1/ La prueba de tensión más severa es la que arroja la mayor relación en "&TEXT(\'Macro-Debt_Data\'!AE5,"#")&" o antes. "'),
        # row 1336: Graphique XXX.Ghana : Indicateurs d'endettement public selon divers sc...
        ('C1336', '="Figure XXX."&\'Input 1 - Basics\'!C7&": Indicators of Public Debt Under Alternative Scenarios, "&TEXT(\'Macro-Debt_Data\'!U5,"#")&"-"&TEXT(\'Macro-Debt_Data\'!AE5,"#")&" 1/"'),
        ('E1336', '="Figura XXX. "&\'Input 1 - Basics\'!C7&": Indicadores da Dívida Pública em Cenários Alternativos, "&TEXT(\'Macro-Debt_Data\'!U5,"#")&"-"&TEXT(\'Macro-Debt_Data\'!AE5,"#")&" 1/"'),
        ('F1336', '="Gráfico XXX. "&\'Input 1 - Basics\'!C7&": Indicadores de deuda pública en escenarios alternativos, "&TEXT(\'Macro-Debt_Data\'!U5,"#")&"-"&TEXT(\'Macro-Debt_Data\'!AE5,"#")&" 1/"'),
        # row 1337: Graphique XXX. Ghana : Indicateurs d'endettement extérieur contracté o...
        ('C1337', '=+"Figure XXX. "&\'Input 1 - Basics\'!C7&": Indicators of Public and Publicly Guaranteed External Debt under Tailored Scenarios, "&TEXT(\'Macro-Debt_Data\'!U5,"#")&"-"&TEXT(\'Macro-Debt_Data\'!AE5,"#")&" 1/"'),
        ('E1337', '=+"Figura XXX. "&\'Input 1 - Basics\'!C7&": Indicadores da Dívida Externa Pública e com Garantia Pública em Cenários Alternativos, "&TEXT(\'Macro-Debt_Data\'!U5,"#")&"-"&TEXT(\'Macro-Debt_Data\'!AE5,"#")&" 1/"'),
        ('F1337', '="Gráfico XXX. "&\'Input 1 - Basics\'!C7&": Indicadores de deuda externa pública y con garantía pública en escenarios alterantivos, "&TEXT(\'Macro-Debt_Data\'!U5,"#")&"-"&TEXT(\'Macro-Debt_Data\'!AE5,"#")&" 1/"'),
        # row 1345
        ('C1345', '=+IF(START!L10="English",C1362,IF(START!L10="French",D1362,IF(START!L10="Portuguese",E1362,F1362)))'),
        # row 1346
        ('C1346', '=+IF(START!L10="English",C1363,IF(START!L10="French",D1363,IF(START!L10="Portuguese",E1363,F1363)))'),
        # row 1347
        ('C1347', '=+IF(START!L10="English",C1364,IF(START!L10="French",D1364,IF(START!L10="Portuguese",E1364,F1364)))'),
        # row 1348
        ('C1348', '=+IF(START!L10="English",C1365,IF(START!L10="French",D1365,IF(START!L10="Portuguese",E1365,F1365)))'),
        # row 1349
        ('C1349:C1353', '=+IF(START!$L$10="English",C1366,IF(START!$L$10="French",D1366,IF(START!$L$10="Portuguese",E1366,#REF!)))'),
        # row 1354
        ('C1354', '=+IF(START!L10="English",C1373,IF(START!L10="French",D1373,IF(START!L10="Portuguese",E1373,F1373)))'),
        # row 1355
        ('C1355', '=+IF(START!L10="English",C1374,IF(START!L10="French",D1374,IF(START!L10="Portuguese",E1374,F1374)))'),
        # row 1373: 1/ Le test de résilience le plus extrême est celui qui génère le ratio...
        ('C1373', '="1/ The most extreme stress test is the test that yields the highest ratio in "&TEXT(\'Macro-Debt_Data\'!AE5,"#")&". "'),
        ('E1373', '="1/ O estresse teste com a razão mais alta em "&TEXT(translation!AF386,"#")&""'),
        ('F1373', '="1/ La prueba de tensión más extrema es la que arroja el coeficiente más alto en "&TEXT(\'Macro-Debt_Data\'!AE5,"#")&""'),
        # row 1374: Graphique XX.Ghana: Indicateurs d'endettement public selon divers scén...
        ('C1374', '="Figure XX."&\'Input 1 - Basics\'!C7&": Indicators of Public Debt Under Alternative Scenarios, "&TEXT(\'Macro-Debt_Data\'!U5,"#")&"-"&TEXT(\'Macro-Debt_Data\'!AO5,"#")&" 1/"'),
        ('E1374', '="Figura XX. "&\'Input 1 - Basics\'!C7&": Indicadores da Dívida Pública em Cenários Alternativos, "&TEXT(\'Macro-Debt_Data\'!U5,"#")&"-"&TEXT(\'Macro-Debt_Data\'!AO5,"#")&" 1/"'),
        ('F1374', '="Gráfico XX. "&\'Input 1 - Basics\'!C7&": Indicadores de la deuda pública en escenarios alternativos, "&TEXT(\'Macro-Debt_Data\'!U5,"#")&"-"&TEXT(\'Macro-Debt_Data\'!AO5,"#")&" 1/"'),
        # row 1794: Updated
        ('C1794 C1804', "='Macro-Debt_Data'!E82"),
        # row 1795: Updated
        ('C1795', "='Macro-Debt_Data'!E81"),
        # row 1813
        ('C1813:F1813', '=C898'),
        # row 1838
        ('C1838', '="Appendix Table XX. "&\'Input 1 - Basics\'!C7&": External Debt Sustainability Framework,"&TEXT(\'Baseline - external\'!C8,"#")&"-"&TEXT(\'Baseline - external\'!AH8,"#")&" 1/"'),
        ('D1838', '="Tableau XX de l\'appendice. "&\'Input 1 - Basics\'!C7&" : Cadre de viabilité de la dette extérieure,"&TEXT(\'Baseline - external\'!C8,"#")&"-"&TEXT(\'Baseline - external\'!AH8,"#")&" 1/"'),
        ('E1838', '="Tabela XX do Apêndice. "&\'Input 1 - Basics\'!C7&": Quadro de Sustentabilidade da Dívida Externa, "&TEXT(\'Baseline - external\'!C8,"#")&"-"&TEXT(\'Baseline - external\'!AH8,"#")&" 1/"'),
        ('F1838', '="Cuadro del apéndice XX."&\'Input 1 - Basics\'!C7&": Marco de sostenbilidad de la deuda externa,"&TEXT(\'Baseline - external\'!C8,"#")&"-"&TEXT(\'Baseline - external\'!AH8,"#")&" 1/"'),
        # row 1876
        ('C1876', '=+"Bound Test 1: Real GDP growth at historical average minus one standard deviation in  "&TEXT(\'Macro-Debt_Data\'!V5,"#")&"-"&TEXT(\'Macro-Debt_Data\'!W5,"#")'),
        ('D1876', '=+"Test paramétré  1 : Croissance du PIB réel à moyenne historique moins un écart type en "&TEXT(\'Macro-Debt_Data\'!V5,"#")&"-"&TEXT(\'Macro-Debt_Data\'!W5,"#")'),
        ('E1876', '=+"Teste-Limite 1: Crescimento do PIB Real à Média Histórica Menos Um Desvio-Padrão em  "&TEXT(\'Macro-Debt_Data\'!V5,"#")&"-"&TEXT(\'Macro-Debt_Data\'!W5,"#")'),
        ('F1876', '=+"Prueba de tensión 1: Crecimiento del PIB real según promedio histórico menos una desviación estándar en "&TEXT(\'Macro-Debt_Data\'!V5,"#")&"-"&TEXT(\'Macro-Debt_Data\'!W5,"#")'),
        # row 1880: Bound Test 2: Exports Shock
        ('D1880', '=+"Test de Réaction 2: Les Exportations Croissant à leur Moyenne Historique moins un écart-type "&TEXT(\'Macro-Debt_Data\'!V5,"#")&"-"&TEXT(\'Macro-Debt_Data\'!W5,"#")&" a/"'),
        ('E1880', '=+"Teste-Limite 2: Crescimento do Valor das Exportações à Média Histórica Menos um Desvio-Padrão em "&TEXT(\'Macro-Debt_Data\'!V5,"#")&"-"&TEXT(\'Macro-Debt_Data\'!W5,"#")&" a/"'),
        ('F1880', '=+"Estrés Test 2 : Valor de las Exportaciones su Promedio Histórico menos un desvío estandar en  "&TEXT(\'Macro-Debt_Data\'!V5,"#")&"-"&TEXT(\'Macro-Debt_Data\'!W5,"#")&" a/"'),
        # row 1882: B4_other flows_ext'!A1
        ('D1882', '=+"Test paramétré 4 : Transferts officiels nets et IDE net à moyenne historique moins un écart type en "&TEXT(\'Macro-Debt_Data\'!V5,"#")&"-"&TEXT(\'Macro-Debt_Data\'!W5,"#")'),
        ('E1882', '=+"Teste-Limite 4: Transferências Oficiais Líquidas e IDE Líquido às Médias Históricas Menos um Desvio-Padrão em "&TEXT(\'Macro-Debt_Data\'!V5,"#")&"-"&TEXT(\'Macro-Debt_Data\'!W5,"#")'),
        ('F1882', '=+"Prueba de tensión 4: Transferencias oficiales netas e IED neta según promedio histórico menos una desviación estándar en "&TEXT(\'Macro-Debt_Data\'!V5,"#")&"-"&TEXT(\'Macro-Debt_Data\'!W5,"#")'),
        # row 1890
        ('C1890', '=+"Stress Tests 5: 10 percent of GDP increase in other debt-creating flows in "&TEXT( \'C2_Natural disaster\'!F7,"#") & "   7/"'),
        ('D1890', '="Test de résistance 5 : Augmentation de 10% du PIB des autres flux générateurs d\'endettement en " &TEXT( \'C2_Natural disaster\'!F7,"#")'),
        ('E1890', '="Teste de Estresse 5: Aumento de 10% do PIB nos outros fluxos geradores de dívida em " &TEXT( \'C2_Natural disaster\'!F7,"#")'),
        ('F1890', '="Prueba de tensión 5: Aumento de otros flujos generadores de deuda equivalente a 10% del PIB en " &TEXT( \'C2_Natural disaster\'!F7,"#")'),
        # row 1977: Chart data
        ('C1977:F1977', '=C204'),
        # row 1997: Choc le plus extrême
        ('C1997', '="Most extreme shock"'),
        # row 2010: JMS: replace french in line 991
        ('C2010 E2010:F2010', '=C1004'),
        # row 2011: JMS: replace french in line 968
        ('C2011 E2011:F2011', '=C981'),
        # row 2013: Translate PRT and ESP if the verb used in line 982 has a different con...
        ('C2013 E2013:F2013', '=C982'),
    ],
    'lookup': [
        # row 2
        ('H2', '=VLOOKUP(Code, G4:H73,2, FALSE)'),
        # row 4: AFG
        ('W4', '=IF(\'Input 1 - Basics\'!$C$33=lookup!$X$4,"",n.a.)'),
        ('X4:X5', '=translation!C90'),
        ('AP4:AP5', '=++OFFSET(translation!C297, 0,LANG)'),
        # row 5: BGD
        ('AY5:AY106', '=IFERROR(INDEX(Country_list,ROW()-ROW(INDEX(Country_list,1,1)),1),"")'),
        # row 7: BTN
        ('AP7:AP8 AP29:AP30', '=++OFFSET(translation!C489, 0,LANG)'),
        # row 10: KHM
        ('AP10:AP11', '="("&++OFFSET(translation!C491, 0,LANG)&")"'),
        # row 12: CPV
        ('J12:J13', '=++OFFSET(translation!C81, 0,LANG)'),
        ('AP12', '="("&++OFFSET(translation!C515, 0,LANG)&")"'),
        # row 75
        ('A75', '=COUNTA(A4:A73)'),
    ],
    'Input-INSTRUCTIONS': [
        # row 2
        ('B2', '=IF(START!L10="English",translation!C4,IF(START!L10="French",translation!D4,IF(START!L10="Portuguese",translation!E4,translation!F4)))'),
        # row 4
        ('B4', '="1. "&IF(START!$L$10="English",translation!C5,IF(START!$L$10="French",translation!D5,IF(START!$L$10="Portuguese",translation!E5,translation!F5)))&" 1/"'),
        ('J4', '=translation!C46'),
        # row 5: 1.1.
        ('B5:B7 B9:B10 B12:B13 B15:B16 B18:B19 B21:B25 B27 B29 B31:B33 B35 B37:B38 B40', '=A5&" "&IF(START!$L$10="English",translation!C6,IF(START!$L$10="French",translation!D6,IF(START!$L$10="Portuguese",translation!E6,translation!F6)))'),
        # row 8: 1.4.
        ('B8', '=A8&" "&IF(START!$L$10="English",translation!C9,IF(START!$L$10="French",translation!D10,IF(START!$L$10="Portuguese",translation!E10,translation!F10)))'),
        # row 11
        ('B11', '="2. "&IF(START!$L$10="English",translation!C12,IF(START!$L$10="French",translation!D12,IF(START!$L$10="Portuguese",translation!E12,translation!F12)))'),
        ('J11', '=translation!C47'),
        # row 14
        ('B14', '="3. "&IF(START!$L$10="English",translation!C15,IF(START!$L$10="French",translation!D15,IF(START!$L$10="Portuguese",translation!E15,translation!F15)))'),
        ('J14', '=translation!C48'),
        # row 17
        ('B17', '="4. "&IF(START!$L$10="English",translation!C18,IF(START!$L$10="French",translation!D18,IF(START!$L$10="Portuguese",translation!E18,translation!F18)))'),
        ('J17', '=translation!C49'),
        # row 20
        ('B20', '="5. "&IF(START!$L$10="English",translation!C21,IF(START!$L$10="French",translation!D21,IF(START!$L$10="Portuguese",translation!E21,translation!F21)))'),
        ('J20', '=translation!C50'),
        # row 26
        ('B26', '="6. "&IF(START!$L$10="English",translation!C27,IF(START!$L$10="French",translation!D27,IF(START!$L$10="Portuguese",translation!E27,translation!F27)))'),
        ('J26', '=translation!C51'),
        # row 28
        ('B28', '="7. "&IF(START!$L$10="English",translation!C29,IF(START!$L$10="French",translation!D29,IF(START!$L$10="Portuguese",translation!E29,translation!F29)))'),
        ('J28', '=translation!C52'),
        # row 30
        ('B30', '="8. " &IF(START!$L$10="English",translation!C31,IF(START!$L$10="French",translation!D31,IF(START!$L$10="Portuguese",translation!E31,translation!F31)))'),
        ('J30', '=translation!C53'),
        # row 34
        ('B34', '="9. "&IF(START!$L$10="English",translation!C35,IF(START!$L$10="French",translation!D35,IF(START!$L$10="Portuguese",translation!E35,translation!F35)))'),
        ('J34', '=translation!C54'),
        # row 36
        ('B36', '="10. "&IF(START!$L$10="English",translation!C37,IF(START!$L$10="French",translation!D37,IF(START!$L$10="Portuguese",translation!E37,translation!F37)))'),
        ('I36', '=translation!C56'),
        ('J36', '=translation!C55'),
        # row 39
        ('B39', '="11. "&IF(START!$L$10="English",translation!C40,IF(START!$L$10="French",translation!D40,IF(START!$L$10="Portuguese",translation!E40,translation!F40)))'),
        ('J39', '=translation!C57'),
        # row 42
        ('B42', '=IF(START!$L$10="English",translation!C42,IF(START!$L$10="French",translation!D42,IF(START!$L$10="Portuguese",translation!E42,translation!F42)))'),
        # row 43
        ('B43', '=IF(START!$L$10="English",translation!C58,IF(START!$L$10="French",translation!D36,IF(START!$L$10="Portuguese",translation!E36,translation!F36)))'),
        # row 44
        ('B44', '="1/ "&IF(START!$L$10="English",translation!C59,IF(START!$L$10="French",translation!D37,IF(START!$L$10="Portuguese",translation!E37,translation!F37)))'),
        ('E44', '=translation!C60'),
    ],
    'Input 1 - Basics': [
        # row 1
        ('B1 B3:B5', '=++OFFSET(translation!C62, 0,LANG)'),
        # row 2
        ('B2', "=IF('Input-INSTRUCTIONS'!D1=0, ++OFFSET(translation!C99, 0,LANG), translation!J99)"),
        ('E2:E4', '=++OFFSET(translation!C100, 0,LANG)'),
        # row 7: Ghana
        ('B7', '=++IF(START!L10="English",translation!C69,IF(START!L10="French",translation!D69,IF(START!L10="Portuguese",translation!E69,translation!F69)))'),
        ('E7', '=++OFFSET(translation!C103, 0,LANG)&" -->"'),
        # row 8
        ('B8', '=++IF(START!L10="English",translation!C70,IF(START!L10="French",translation!D70,IF(START!L10="Portuguese",translation!E70,translation!F70)))'),
        ('C8', '=VLOOKUP(C7,lookup!C$4:G$73,5,FALSE)'),
        # row 10: Yes
        ('B10', '=++IF(START!L10="English",translation!C76,IF(START!L10="French",translation!D76,IF(START!L10="Portuguese",translation!E76,translation!F76)))'),
        # row 11: Yes
        ('B11', '=++IF(START!L10="English",translation!C77,IF(START!L10="French",translation!D77,IF(START!L10="Portuguese",translation!E77,translation!F77)))'),
        # row 12: Blend
        ('B12', '=++IF(START!L10="English",translation!C78,IF(START!L10="French",translation!D78,IF(START!L10="Portuguese",translation!E78,translation!F78)))'),
        ('E12', '=++OFFSET(translation!C104, 0,LANG)'),
        # row 13
        ('B13', '=++IF(START!L10="English",translation!C74,IF(START!L10="French",translation!D74,IF(START!L10="Portuguese",translation!E74,translation!F74)))'),
        ('C13', '=VLOOKUP(Code,lookup!B4:F73,COLUMN(HIPC_Column)-1,FALSE)'),
        # row 14
        ('B14', '=++IF(START!L10="English",translation!C75,IF(START!L10="French",translation!D75,IF(START!L10="Portuguese",translation!E75,translation!F75)))'),
        ('C14', '=VLOOKUP(Code, lookup!$B$3:$AR$83, COLUMN(MDRI_Column)-1, FALSE)'),
        # row 15
        ('B15', '=++IF(START!L10="English",translation!C79,IF(START!L10="French",translation!D79,IF(START!L10="Portuguese",translation!E79,translation!F79)))'),
        # row 17
        ('B17', '=++OFFSET(translation!C86, 0,LANG)'),
        ('E17:E18', '=++OFFSET(translation!C105, 0,LANG)'),
        # row 18
        ('B18', '=++OFFSET(translation!C216, 0,LANG)'),
        # row 19: Million
        ('B19', '=++IF(START!L10="English",translation!C80,IF(START!L10="French",translation!D80,IF(START!L10="Portuguese",translation!E80,translation!F80)))'),
        ('E19', '=IF(Int_Ext=0, ++OFFSET(translation!C107, 0,LANG), translation!J107)'),
        # row 21
        ('B21:B23', '=++OFFSET(translation!C83, 0,LANG)'),
        ('E21', '=++OFFSET(translation!C108, 0,LANG)'),
        # row 22
        ('C22:C23', '=VLOOKUP(MID(\'Realism 1 - Forecast Error\'!E6,6,2),Vintage_display_lookup,2,FALSE)&", "&LEFT(\'Realism 1 - Forecast Error\'!E6,4)'),
        # row 25
        ('B25', '=++IF(START!L10="English",translation!C72,IF(START!L10="French",translation!D72,IF(START!L10="Portuguese",translation!E72,translation!F72)))'),
        # row 27
        ('B27:B29', '=++OFFSET(translation!C87, 0,LANG)'),
        ('C27', "='Input 6 - Tailored Tests'!C11"),
        # row 28: Yes
        ('E28', '=++OFFSET(translation!C109, 0,LANG)'),
        # row 31
        ('B31', '=++OFFSET(translation!C97, 0,LANG)'),
        # row 33: Residency-based
        ('B33:B34', '=++OFFSET(translation!C92, 0,LANG)'),
        # row 35
        ('B35', '=++OFFSET(translation!C98, 0,LANG)'),
    ],
    'Input 2 - Debt Coverage': [
        # row 1
        ('B1', '=IF(START!$L$10="English",translation!C114,IF(START!$L$10="French",translation!D114,IF(START!$L$10="Portuguese",translation!E114,translation!F114)))'),
        # row 2
        ('C2:C4', '=++OFFSET(translation!C64, 0,LANG)'),
        # row 5
        ('B5', '=IF(START!$L$10="English",translation!C115,IF(START!$L$10="French",translation!D115,IF(START!$L$10="Portuguese",translation!E115,translation!F115)))'),
        # row 6
        ('B6', '=IF(START!$L$10="English",translation!C137,IF(START!$L$10="French",translation!D137,IF(START!$L$10="Portuguese",translation!E137,translation!F137)))'),
        # row 7
        ('C7', '=IF(START!$L$10="English",translation!C138,IF(START!$L$10="French",translation!D138,IF(START!$L$10="Portuguese",translation!E138,translation!F138)))'),
        ('E7', '=IF(START!$L$10="English",translation!C149,IF(START!$L$10="French",translation!D149,IF(START!$L$10="Portuguese",translation!E149,translation!F149)))'),
        # row 8: X
        ('C8:C15', '=IF(START!$L$10="English",translation!C140,IF(START!$L$10="French",translation!D140,IF(START!$L$10="Portuguese",translation!E140,translation!F140)))'),
        ('L8', '=U8'),
        ('N8', '=IF(AND($E$8=K8,$E$9=K8,$E$10=K8),U9,IF(AND($E$8=K8,$E$9=K8,$E$10=""),U10&N9,U11&N9))'),
        ('U8:U11 U13:U17 U19:U20 U22:U24 U26:U27', '=++OFFSET(translation!C116, 0,LANG)'),
        # row 9
        ('L9', '=U13'),
        ('N9', '=IF(AND(E11=K8,E12=K8)," "&U14&" "&U15&" "&U16&" "&U17,IF(AND(E11=K8,E12="")," "&U14&" "&U15,IF(AND(E11="",E12=K8)," "&U14&" "&U17,"")))'),
        # row 10
        ('E10', '=IF(AND(E11=$K$8, E12=$K$8), $K$8, "")'),
        ('L10', '=U19'),
        ('N10', '=IF($E$14=K8,N8&U20,N8)'),
        # row 11: X
        ('L11', '=U22'),
        ('N11', '=IF($E$13=K8,N10&U23,N10)'),
        # row 12
        ('L12', '=U26'),
        ('N12', '=IF(AND($E$8=K8,$E$9=K8,$E$10=K8,$E$13=K8,$E$14=K8,$E$15=K8),U27,IF($E$15=K8,N11&U24,N11))'),
        # row 17
        ('B17', '=IF(START!$L$10="English",translation!C151,IF(START!$L$10="French",translation!D151,IF(START!$L$10="Portuguese",translation!E151,translation!F151)))'),
        # row 18
        ('B18', '=++OFFSET(translation!C153, 0,LANG)'),
        # row 19
        ('C19', '=++IF(START!$L$10="English",translation!C155,IF(START!$L$10="French",translation!D155,IF(START!$L$10="Portuguese",translation!E155,translation!F155)))'),
        ('D19', '=N12'),
        # row 20
        ('D20', '=++IF(START!$L$10="English",translation!C162,IF(START!$L$10="French",translation!D162,IF(START!$L$10="Portuguese",translation!E162,translation!F162)))'),
        ('F20', '=++IF(START!$L$10="English",translation!C163,IF(START!$L$10="French",translation!D163,IF(START!$L$10="Portuguese",translation!E163,translation!F163)))'),
        ('G20', '=++IF(START!$L$10="English",translation!C164,IF(START!$L$10="French",translation!D164,IF(START!$L$10="Portuguese",translation!E164,translation!F164)))'),
        # row 21
        ('B21', '=B19+1'),
        ('C21:C25', '=++IF(START!$L$10="English",translation!C156,IF(START!$L$10="French",translation!D156,IF(START!$L$10="Portuguese",translation!E156,translation!F156)))'),
        ('E21', '=++OFFSET(translation!C165, 0,LANG)'),
        ('F21:F22', '=D21'),
        # row 22
        ('B22:B24', '=B21+1'),
        ('E22:E23', '=++OFFSET(translation!C165, 0,LANG)'),
        # row 23
        ('F23', '=IF(E32>3,E34,0)'),
        # row 24
        ('E24', '=++OFFSET(translation!C165, 0,LANG)'),
        # row 25
        ('F25', '=SUM(F21:F24)'),
        # row 26
        ('B26', '=++IF(START!$L$10="English",translation!C161,IF(START!$L$10="French",translation!D161,IF(START!$L$10="Portuguese",translation!E161,translation!F161)))'),
        # row 31
        ('B31', '=++OFFSET(translation!C167, 0,LANG)'),
        # row 32
        ('C32', '=++OFFSET(translation!C168, 0,LANG)'),
        ('E32', '=IF(ISERROR(VLOOKUP(Code, Trigger!$A$4:$J$58, 10, FALSE)), 0, VLOOKUP(Code, Trigger!$A$4:$J$58, 10, FALSE)*100)'),
        ('F32', '=IF(E32>3,++OFFSET(translation!C176, 0,LANG), ++OFFSET(translation!C177, 0,LANG))'),
        ('G32:G33', '=++OFFSET(translation!C178, 0,LANG)'),
        # row 33
        ('C33:C34', '=++IF(START!$L$10="English",translation!C169,IF(START!$L$10="French",translation!D169,IF(START!$L$10="Portuguese",I44,J44)))'),
        # row 34
        ('E34', '=E33*E32'),
        # row 35
        ('K35', '=K7'),
        # row 36
        ('B36:B40', '=++OFFSET(translation!C180, 0,LANG)'),
        ('M36:M40', '=++OFFSET(translation!C185, 0,LANG)'),
        # row 37
        ('E37', "=IF('Input 2 - Debt Coverage'!F21=$D$21, $M$36, $M$37)"),
        # row 38
        ('E38', '=IF(F22=0,$M$38,IF(F22>$D$22,$M$37,IF(F22=$D$22,$M$36,$M$39)))'),
        # row 39
        ('E39', '=IF(AND(E32>3,E33=35%),$M$36,IF(AND(E32>3,E33>35%),$M$37, IF(AND(E32>3,E33<35%),$M$39,$M$40)))'),
        # row 40
        ('E40', '=IF(F24=$D$24,$M$36,IF(F24>$D$24,$M$37))'),
    ],
    'Input 3 - Macro-Debt data(DMX)': [
        # row 2
        ('A2', '=IF(Int_Ext=0, ++OFFSET(translation!C227, 0,LANG), OFFSET(translation!J227, 0,LANG))'),
        # row 5: [insert filepath]
        ('A5', '=IF(Int_Ext=0, ++OFFSET(translation!C228, 0,LANG), OFFSET(translation!C228, 0,LANG))'),
        ('X5', "='Input 1 - Basics'!B18"),
        # row 7: Database
        ('K7:W7', '=L7-1'),
        ('X7', '=ProjectionYear'),
        ('Y7:BP7', '=X7+1'),
        # row 9
        ('A9 A11 A21 A33', '=++OFFSET(translation!C229, 0,LANG)'),
        # row 10
        ('A10', '=IF(Int_Ext=0,++OFFSET(translation!C230, 0,LANG), OFFSET(translation!J230, 0,LANG))'),
        # row 12: n.a.
        ('A12:A20 A22:A32 A34:A46 A51:A55 A57:A60 A65:A70 A72:A74 A77:A81 A83:A87 A89:A93 A95 A100:A109 A111:A113 A116:A120 A122:A126 A128:A132 A136:A139 A141:A144 A147 A149:A150 A152:A157 A161:A164 A166:A169 A172:A173 A175:A180 A183:A184', '=$B$5'),
        ('B12:B20 B22:B32 B34:B44', '=++OFFSET(translation!C232, 0,LANG)'),
        ('C12:C20 H16:H20 C22:C32 C34:C46 C51:C55 C57:C60 C65:C70 C72:C74 C77:C81 C83:C87 C89:C93 C95 C100:C103 C108:C109 C111:C113 C116:C120 C122:C126 C128:C132 C136:C139 C141:C144 C147 C149:C150 C152:C157 C161:C164 C166:C169 C172:C173 C175:C180 C183:C184', '=B12'),
        ('D12:D20 D22:D32 D34:D44 D46 D51:D54 D57:D60', "='Input 1 - Basics'!$C$8&J12"),
        ('H12:H15 H22:H32 H34:H46 H51:H55 H57:H60 H65:H70 H72:H74 H77:H81 H83:H87 H89:H93 H95 H100:H109 H111:H113 H116:H120 H122:H126 H128:H132 H136:H139 H141:H144 H147 H149:H150 H152:H157 H161:H164 H166:H169 H172:H173 H175:H180 H184', "='Input 1 - Basics'!$C$19"),
        # row 45: n.a.
        ('B45', '=++OFFSET(translation!C328, 0,LANG)'),
        ('D45 D55 D65:D70 D72:D74 D77:D81 D83:D87 D89:D93 D95 D100:D109 D111:D113 D116:D120 D122:D126 D128:D132 D136:D139 D141:D144 D147 D149:D150 D152:D157 D161:D164 D166:D169 D172:D173 D175:D180 D184', '=Code&J45'),
        # row 46: n.a.
        ('B46', '=++OFFSET(translation!C265, 0,LANG)'),
        # row 48
        ('A48:A50 A56', '=++OFFSET(translation!C266, 0,LANG)'),
        # row 51: n.a.
        ('B51:B55 B57:B60', '=++OFFSET(translation!C269, 0,LANG)'),
        # row 62
        ('A62', '=++OFFSET(translation!C279, 0,LANG)'),
        # row 63
        ('A63', "=IF('Input-INSTRUCTIONS'!D1=0, ++OFFSET(translation!C280, 0,LANG), ++OFFSET(translation!J280, 0,LANG))"),
        # row 64
        ('A64', "='Input 4 - External Financing'!B9"),
        # row 65: IMF
        ('J65:J68', '=CONCATENATE("OLD_",\'Input 4 - External Financing\'!J10)'),
        # row 69: Multilateral2
        ('J69:J70 J72:J74 J77:J81 J83:J87 J89:J93', '=CONCATENATE("OLD_",\'Input 4 - External Financing\'!J18)'),
        # row 71
        ('A71 A75:A76 A82 A88', "='Input 4 - External Financing'!B20"),
        # row 97
        ('A97', '=++OFFSET(translation!C290, 0,LANG)&" "&X7&" "&OFFSET(translation!C292, 0,LANG)'),
        # row 98
        ('A98', '=IF(Int_Ext=0, ++OFFSET(translation!C293, 0,LANG), OFFSET(translation!J293, 0,LANG))'),
        # row 99
        ('A99', '=++IF(START!L10="English",translation!C294,IF(START!L10="French",translation!D294,IF(START!L10="Portuguese",translation!E294,translation!F294)))'),
        # row 100: IMF
        ('J100:J109 J111:J113 J116:J120 J122:J126 J128:J132', '=CONCATENATE("NEW_",\'Input 4 - External Financing\'!J10)'),
        # row 110
        ('A110 A114:A115 A121 A127', "='Input 4 - External Financing'!B20"),
        # row 133
        ('A133', '=IF(Int_Ext=0,++OFFSET(translation!C295, 0,LANG), OFFSET(translation!J295, 0,LANG))'),
        # row 134
        ('A134', '=++OFFSET(translation!C296, 0,LANG)'),
        ('B134', '=IF(\'Input 1 - Basics\'!C33=lookup!$X$4, "- "&lookup!AP4,"")'),
        # row 135
        ('A135 A145 A159', '=++OFFSET(translation!C299, 0,LANG)'),
        # row 136: n.a.
        ('B136:B138 B140:B144', '=++OFFSET(translation!C300, 0,LANG)'),
        # row 139: n.a.
        ('B139', '=B137'),
        # row 140
        ('A140', '=++OFFSET(translation!C303, 0,LANG)'),
        # row 145
        ('B145', '=IF(Int_Ext=0,++OFFSET(translation!C310, 0,LANG), OFFSET(translation!J310, 0,LANG))'),
        # row 146
        ('A146 A148 A151', '=++OFFSET(translation!C311, 0,LANG)'),
        # row 147: n.a.
        ('B147 B149:B150 B152:B157 B159', '=++OFFSET(translation!C312, 0,LANG)'),
        # row 160
        ('A160 B161 B163:B164 A165:B165 B166:B169 A170:B170', '=A135'),
        # row 162: n.a.
        ('B162 A171 B172:B173 A174 B175:B180', '=B139'),
        # row 182
        ('A182 A187', '=++OFFSET(translation!C325, 0,LANG)'),
        # row 183: 001NGDP_RPCH.A
        ('B183', '=++OFFSET(translation!C329, 0,LANG)'),
        # row 184: n.a.
        ('B184', '=++OFFSET(translation!C327, 0,LANG)'),
        # row 190
        ('L190:W190', "=IF('Input 1 - Basics'!$C$33=lookup!$X$4,IF(ISNUMBER(L136),L136,0)+IF(ISNUMBER(L138),L138,0)*L$19,IF(ISNUMBER(L136),L136,0))"),
        # row 191
        ('L191:W191 M195:W195 L200:W200 M204:W204 L209:W209', '=L190-L192'),
        # row 192
        ('L192:W192', "=IF('Input 1 - Basics'!$C$33=lookup!$X$4,IF(ISNUMBER(L137),L137,0)+IF(ISNUMBER(L139),L139,0)*L$19,IF(ISNUMBER(L137),L137,0))"),
        # row 193
        ('L193:W193', "=IF('Input 1 - Basics'!$C$33=lookup!$X$4,IF(ISNUMBER(L141),L141,0)+IF(ISNUMBER(L142),L142,0)*L$20,IF(ISNUMBER(L141),L141,0))"),
        # row 194
        ('L194:W194', "=IF('Input 1 - Basics'!$C$33=lookup!$X$4,IF(ISNUMBER(L143),L143,0)+IF(ISNUMBER(L144),L144,0)*L$20,IF(ISNUMBER(L143),L143,0))"),
        # row 196
        ('M196:W196', "=IF('Input 1 - Basics'!$C$33=lookup!$X$4,IF(ISNUMBER(L137),L137,0)+IF(ISNUMBER(L139),L139,0)*M$20,IF(ISNUMBER(L137),L137,0))"),
        # row 199
        ('L199:W199', "=IF('Input 1 - Basics'!$C$33=lookup!$X$4,IF(ISNUMBER(L136),L136,0)/L$19+IF(ISNUMBER(L138),L138,0),IF(ISNUMBER(L136),L136,0)/L$19)"),
        ('X199:X201', '=W190/W$19'),
        # row 201
        ('L201:W201', "=IF('Input 1 - Basics'!$C$33=lookup!$X$4,IF(ISNUMBER(L137),L137,0)/L$19+IF(ISNUMBER(L139),L139,0),IF(ISNUMBER(L137),L137,0)/L$19)"),
        # row 202
        ('L202:W202', "=IF('Input 1 - Basics'!$C$33=lookup!$X$4,IF(ISNUMBER(L141),L141,0)/L$20+IF(ISNUMBER(L142),L142,0),IF(ISNUMBER(L141),L141,0)/L$20)"),
        ('X202:X205', '=W193/W$20'),
        # row 203
        ('L203:W203', "=IF('Input 1 - Basics'!$C$33=lookup!$X$4,IF(ISNUMBER(L143),L143,0)/L$20+IF(ISNUMBER(L144),L144,0),IF(ISNUMBER(L143),L143,0)/L$20)"),
        # row 205
        ('M205:W205', "=IF('Input 1 - Basics'!$C$33=lookup!$X$4,IF(ISNUMBER(L137),L137,0)/M$20+IF(ISNUMBER(L139),L139,0),IF(ISNUMBER(L137),L137,0)/M$20)"),
        # row 208
        ('L208:W208', "=IF('Input 1 - Basics'!$C$33=lookup!$X$4,IF(ISNUMBER(L161),L161,0)/L$19+IF(ISNUMBER(L163),L163,0),IF(ISNUMBER(L138),L138,0))"),
        # row 210
        ('L210:W210', "=IF('Input 1 - Basics'!$C$33=lookup!$X$4,IF(ISNUMBER(L162),L162,0)/L$19+IF(ISNUMBER(L164),L164,0),IF(ISNUMBER(L139),L139,0))"),
        # row 211
        ('L211:W211', "=IF('Input 1 - Basics'!$C$33=lookup!$X$4,IF(ISNUMBER(L166),L166,0)/L$20+IF(ISNUMBER(L167),L167,0),IF(ISNUMBER(L142),L142,0))"),
        # row 212
        ('L212:W212', "=IF('Input 1 - Basics'!$C$33=lookup!$X$4,IF(ISNUMBER(L168),L168,0)/L$20+IF(ISNUMBER(L169),L169,0),IF(ISNUMBER(L144),L144,0))"),
        # row 214
        ('L214:W214', '=IF(ISNUMBER(L51),L51,0)+IF(ISNUMBER(L52),L52,0)+IF(ISNUMBER(L138),L138,0)+IF(ISNUMBER(L163),L163,0)'),
    ],
    'Input 4 - External Financing': [
        # row 1
        ('B1', '=++IF(START!L10="English",translation!C438,IF(START!L10="French",translation!D438,IF(START!L10="Portuguese",translation!E438,translation!F438)))'),
        # row 2
        ('B2', '=++OFFSET(translation!C439, 0,LANG)'),
        # row 3
        ('B3', '=++OFFSET(translation!C445, 0,LANG)'),
        # row 4
        ('B4', '=++OFFSET(translation!C447, 0,LANG)'),
        # row 5
        ('L5', "='Input 1 - Basics'!B18"),
        # row 6
        ('E6', '=++IF(START!L10="English",translation!C449,IF(START!L10="French",translation!F449,IF(START!L10="Portuguese",translation!E449,translation!D449)))'),
        ('F6', '=++IF(START!L10="English",translation!C450,IF(START!L10="French",translation!F450,IF(START!L10="Portuguese",translation!E450,translation!D450)))'),
        ('G6', '=++IF(START!L10="English",translation!C451,IF(START!L10="French",translation!F451,IF(START!L10="Portuguese",translation!E451,translation!D451)))'),
        ('H6', '=++IF(START!L10="English",translation!C452,IF(START!L10="French",translation!F452,IF(START!L10="Portuguese",translation!E452,translation!D452)))'),
        ('I6', '=++IF(START!L10="English",translation!C453,IF(START!L10="French",translation!F453,IF(START!L10="Portuguese",translation!E453,translation!D453)))'),
        ('L6', "=+'Macro-Debt_Data'!U5"),
        ('M6:AF6 I66:BP66', '=L6+1'),
        # row 8: For IDA NEW Blend the team needs to choose floating or fixed (cell D16...
        ('K8', '=++OFFSET(translation!C482, 0,LANG)'),
        ('L8:AF8', '=SUM(L10:L42)'),
        # row 9
        ('B9', '=++IF(START!L10="English",translation!C294,IF(START!L10="French",translation!D294,IF(START!L10="Portuguese",translation!E294,translation!F294)))'),
        # row 10
        ('B10', "='Input 3 - Macro-Debt data(DMX)'!B100"),
        ('E10', "='Input 1 - Basics'!C25"),
        ('I10', '=+PV_Base!D15'),
        ('O10:AF10 L11 N11:AF11 L12:AF13 L14:M15 O14:AF15 L16:L17 P16:AF17 R18:AF18 L19:AF19 L21:AF23 L26:AF30 L32:AF36 L38:AF42', "=IF(ISNUMBER('Input 3 - Macro-Debt data(DMX)'!AA100), 'Input 3 - Macro-Debt data(DMX)'!AA100, 0)"),
        # row 11: IDA - regular
        ('D11', '=++OFFSET(translation!C446, 0,LANG)'),
        ('E11:E19', '=+E$10'),
        ('F11:F15 F17', "=IF(B11=$B$74,VLOOKUP($D11,$B$83:$D$85,3,FALSE),VLOOKUP($B11,'Input 4 - External Financing'!$B$67:$F$75,3,FALSE))"),
        ('G11:G17', "=VLOOKUP($B11,'Input 4 - External Financing'!$B$67:$F$75,4,FALSE)"),
        ('H11:H17', "=VLOOKUP($B11,'Input 4 - External Financing'!$B$67:$F$75,5,FALSE)"),
        ('I11', '=+PV_Base!D57'),
        # row 12: IDA - 50Y loans
        ('I12', '=+PV_Base!D83'),
        # row 13: IDA - SML
        ('I13', '=+PV_Base!D108'),
        # row 14: IDA NEW 40-year credits
        ('I14', '=PV_Base!D132'),
        # row 15: IDA NEW Regular
        ('I15', '=PV_Base!D156'),
        # row 16: IDA NEW Blend (also enter) -->
        ('F16', "=VLOOKUP($D16,'BLEND floating calculations WB'!$B$5:$D$6,3,FALSE)"),
        ('I16', '=PV_Base!D180'),
        # row 17: IDA NEW 60-year credits
        ('I17', '=PV_Base!D204'),
        # row 18: MULTI1
        ('I18', '=+PV_Base!D238'),
        # row 19: MULTI2
        ('I19', '=PV_Base!D264'),
        # row 20
        ('B20', '=++OFFSET(translation!C459, 0,LANG)'),
        # row 21: OTH_MULTI1
        ('E21:E23 E26:E30 E32:E36 E38:E42', '=+$E$10'),
        ('I21', '=+PV_Base!D290'),
        # row 22: OTH_MULTI2
        ('I22', '=+PV_Base!D316'),
        # row 23: OTH_MULTI3
        ('I23', '=+PV_Base!D342'),
        # row 24
        ('B24', '=++IF(START!L10="English",translation!C460,IF(START!L10="French",translation!D460,IF(START!L10="Portuguese",translation!E460,translation!F460)))'),
        # row 25
        ('B25', '=++IF(START!L10="English",translation!C461,IF(START!L10="French",translation!D461,IF(START!L10="Portuguese",translation!E461,translation!F461)))'),
        # row 26: Export Credit Agencies
        ('I26', '=+PV_Base!D368'),
        # row 27: PC2
        ('I27', '=+PV_Base!D394'),
        # row 28: PC3
        ('I28', '=+PV_Base!D420'),
        # row 29: PC4
        ('I29', '=PV_Base!D446'),
        # row 30: PC5
        ('I30', '=PV_Base!D472'),
        # row 31
        ('B31', '=++IF(START!L10="English",translation!C465,IF(START!L10="French",translation!D465,IF(START!L10="Portuguese",translation!E465,translation!F465)))'),
        # row 32: Export Import Bank of NPC
        ('I32', '=+PV_Base!D498'),
        # row 33: NPC2
        ('I33', '=+PV_Base!D524'),
        # row 34: NPC3
        ('I34', '=+PV_Base!D550'),
        # row 35: NPC4
        ('I35', '=PV_Base!D576'),
        # row 36: NPC5
        ('I36', '=PV_Base!D602'),
        # row 37
        ('B37', '=++IF(START!L10="English",translation!C469,IF(START!L10="French",translation!D469,IF(START!L10="Portuguese",translation!E469,translation!F469)))'),
        # row 38: Eurobond
        ('I38', '=+PV_Base!D628'),
        # row 39: Commecial Bank
        ('I39', '=+PV_Base!D654'),
        # row 40: COM3
        ('I40', '=+PV_Base!D680'),
        # row 41: COM4
        ('I41', '=PV_Base!D706'),
        # row 42: COM5
        ('I42', '=PV_Base!D732'),
        # row 44
        ('B44:B45', '=++OFFSET(translation!C473, 0,LANG)'),
        ('L44', '=++OFFSET(translation!C481, 0,LANG)'),
        # row 47
        ('B47', '=++OFFSET(translation!C475, 0,LANG)'),
        # row 48: -
        ('B48', "='Input 5 - Local-debt Financing'!A27"),
        ('F48', "=AVERAGE('Input 5 - Local-debt Financing'!I27:S27)"),
        # row 49
        ('B49:B51', "='Input 5 - Local-debt Financing'!A31"),
        ('E49:E51 E54:E56 E59:E61', "=+'Input 4 - External Financing'!E$10"),
        ('F49:F51', "=AVERAGE('Input 5 - Local-debt Financing'!I31:S31)"),
        ('G49:H51', "='Input 5 - Local-debt Financing'!C31"),
        # row 52
        ('B52', '=++OFFSET(translation!C476, 0,LANG)'),
        # row 53: -
        ('B53', "='Input 5 - Local-debt Financing'!A28"),
        ('F53', "=AVERAGE('Input 5 - Local-debt Financing'!I28:S28)"),
        # row 54
        ('B54:B56', "='Input 5 - Local-debt Financing'!A35"),
        ('F54:F56', "=AVERAGE('Input 5 - Local-debt Financing'!I35:S35)"),
        ('G54:H56', "='Input 5 - Local-debt Financing'!C35"),
        ('I54', '=PV_Base!D758'),
        # row 55
        ('I55', '=PV_Base!D784'),
        # row 56
        ('I56', '=PV_Base!D810'),
        # row 57
        ('B57', '=++OFFSET(translation!C477, 0,LANG)'),
        # row 58: -
        ('B58', "='Input 5 - Local-debt Financing'!A13"),
        ('F58', "=AVERAGE('Input 5 - Local-debt Financing'!I13:S13)"),
        # row 59
        ('B59:B61', "='Input 5 - Local-debt Financing'!A20"),
        ('F59:F61', "=AVERAGE('Input 5 - Local-debt Financing'!I20:S20)"),
        ('G59:H61', "='Input 5 - Local-debt Financing'!C20"),
        ('I59', '=PV_Base!D836'),
        # row 60
        ('I60', '=PV_Base!D862'),
        # row 61
        ('I61', '=PV_Base!D888'),
        # row 64
        ('B64', '=++OFFSET(translation!C478, 0,LANG)'),
        # row 65: As of April 2018
        ('D65', '=++OFFSET(translation!C479, 0,LANG)'),
        ('E65:F65', '=G6'),
        ('H65', '=++OFFSET(translation!C480, 0,LANG)'),
        # row 68: IDA - regular
        ('P68:AT68', '=$O$68'),
        # row 69: IDA - blend
        ('O69:AG69', '=$N$69'),
        ('AI69:AL69', '=$AH$69'),
        # row 70: IDA - SML
        ('P70:T70 V71:BF71', '=+O70'),
        # row 72: IDA21
        ('T72:AV72', '=100%/29'),
        # row 74: IDA NEW Blend (also enter) -->
        ('D74', '=VLOOKUP(C74,$B$83:$D$84,3,FALSE)'),
    ],
    'BLEND floating calculations WB': [
        # row 4: Terms
        ('L4', '=$L$5+$L$6-2.5%'),
        # row 5: IDA NEW Blend fixed
        ('J5', '=_xlfn.XLOOKUP(C6,$A$45:$A$48,B45:$B$48)', 'array'),
        ('L5', '=_xlfn.XLOOKUP(F6,$M$10:$M$39,$O$10:$O$39)'),
        # row 6: IDA NEW Blend floating
        ('D6', '=IF($L$4<=0.75%,0.75%,IF($L$4>=5%,5%,$L$4))'),
        # row 8: II.
        ('J8', '=J5&" swap rates"'),
        # row 9: below aimed at computing the applicable interest rate. These calculati...
        ('N9', '=J5&" Swap rate"'),
        # row 10: i = Swap rate (e.g., SOFR swap rate) + IBRD group A pricing - 2.5%, wi...
        ('I10:I14', '=_xlfn.NUMBERVALUE(LEFT(J10,1))'),
        ('N10:N19 N21 N24 N29 N39', '=_xlfn.IFNA(_xlfn.XLOOKUP(M10,$I$10:$I$39,$K$10:$K$39),"")'),
        ('O10', '=IF(N10="",O9+(INDEX(N11:N$39,MATCH(TRUE,INDEX((N11:N$39<>0),0),0))-LOOKUP(2,1/(N9:N$10<>0),N9:N$10))/(_xlfn.XLOOKUP(INDEX(N11:N$39,MATCH(TRUE,INDEX((N11:N$39<>0),0),0)),N11:$N$39,M11:$M$39)-_xlfn.XLOOKUP(LOOKUP(2,1/(N9:N$10<>0),N9:N$10),$N9:N$10,$M9:M$10)),N10)', 'array'),
        # row 11
        ('O11:O38', '=IF(N11="",O10+(INDEX(N12:N$39,MATCH(TRUE,INDEX((N12:N$39<>0),0),0))-LOOKUP(2,1/(N$10:N10<>0),N$10:N10))/(_xlfn.XLOOKUP(INDEX(N12:N$39,MATCH(TRUE,INDEX((N12:N$39<>0),0),0)),N12:$N$39,M12:$M$39)-_xlfn.XLOOKUP(LOOKUP(2,1/(N$10:N10<>0),N$10:N10),$N$10:N10,$M$10:M10)),N11)', 'array'),
        # row 13
        ('B13', '="Find "&J5&" swap rate"'),
        # row 14
        ('B14', '="1. Find the applicable "&J5&" swap rate from the link below, and update the data in cells "&CELL("address",K10)&"-"&CELL("address",K24)', 'array'),
        # row 15
        ('B15', '=_xlfn.XLOOKUP($C$6,$A$45:$A$49,$C$45:$C$49)'),
        ('I15:I24', '=_xlfn.NUMBERVALUE(LEFT(J15,2))'),
        # row 17
        ('B17', '="2. Ensure that cell "&CELL("address",L5)&" is selecting the corresponding applicable swap rate to the respective maturity"', 'array'),
        # row 20
        ('B20', '="3. Find the IBRD group A pricing in the link below, and update if needed in cell "&CELL("address",L6)&""', 'array'),
        # row 26
        ('B26', '="Finally, cell "&CELL("address",L4)&" adds both of the inputs above and deducts 2.5 percent"', 'array'),
        # row 34
        ('N34', '=_xlfn.IFNA(_xlfn.XLOOKUP(M34,$I$10:$I$39,$K$10:$K$39),"")+0.0000000001'),
        # row 39
        ('O39', '=IF(N39="",O38+(INDEX(N$39:N39,MATCH(TRUE,INDEX((N$39:N39<>0),0),0))-LOOKUP(2,1/(N$10:N38<>0),N$10:N38))/(_xlfn.XLOOKUP(INDEX(N$39:N39,MATCH(TRUE,INDEX((N$39:N39<>0),0),0)),N$39:$N39,M$39:$M39)-_xlfn.XLOOKUP(LOOKUP(2,1/(N$10:N38<>0),N$10:N38),$N$10:N38,$M$10:M38)),N39)', 'array'),
    ],
    'Input 6(optional)-Standard Test': [
        # row 1
        ('A1:A2', '=++OFFSET(translation!C1541, 0,LANG)'),
        # row 3
        ('H3', "=IF(AND($C$4=lookup!$AF$5,$C$8=lookup!$AH$5,'Input 6 - Tailored Tests'!$C$6=lookup!$AH$5),0,1)"),
        # row 4: New
        ('A4', '=++OFFSET(translation!C1538, 0,LANG)'),
        ('B4', '=++OFFSET(translation!C1539, 0,LANG)'),
        # row 5: Historical average only
        ('A5', '=++OFFSET(translation!C66, 0,LANG)'),
        # row 8: On
        ('B8', '=++OFFSET(translation!C1573, 0,LANG)'),
        # row 11
        ('A11', '=++OFFSET(translation!C1570, 0,LANG)'),
        # row 13
        ('A13 A21', '=++OFFSET(translation!C1540, 0,LANG)'),
        ('B13', '=++OFFSET(translation!C1571, 0,LANG)'),
        ('F13', '=++OFFSET(translation!C1573, 0,LANG)'),
        # row 14
        ('C14', '=++OFFSET(translation!C162, 0,LANG)'),
        ('D14', '=++OFFSET(translation!C1572, 0,LANG)'),
        ('G14', '=++OFFSET(translation!C162, 0,LANG)'),
        ('H14', '=++OFFSET(translation!C1572, 0,LANG)'),
        # row 16
        ('A16', '=++OFFSET(translation!C1121, 0,LANG)'),
        # row 17
        ('A17', '=++OFFSET(translation!C1546, 0,LANG)'),
        ('B17:B18', '=++OFFSET(translation!C1561, 0,LANG)'),
        ('D17 H17 D21 H21 D25 H25 D29 D32 H36:H38', '=C17'),
        ('F17', '=++OFFSET(translation!C1574, 0,LANG)'),
        ('G17', '=IF(\'Input 6(optional)-Standard Test\'!$C$8="On", 0.6, 0)'),
        # row 18: Whichever is lower
        ('C18 C22 C26 C30 C33 C42 C45 C48 C51 C54', '=IF(\'Input 6(optional)-Standard Test\'!$C$4="New", \'Input 6(optional)-Standard Test\'!$C$7, \'Input 6(optional)-Standard Test\'!$C$5)'),
        # row 20
        ('A20', '=++OFFSET(translation!C1122, 0,LANG)'),
        # row 21
        ('B21', '=++OFFSET(translation!C1563, 0,LANG)'),
        ('F21:F22', '=++OFFSET(translation!C1575, 0,LANG)'),
        ('G21', '=IF(\'Input 6(optional)-Standard Test\'!$C$8="On", 25,0)'),
        # row 22: Whichever is lower
        ('B22', '=++OFFSET(translation!C1562, 0,LANG)'),
        ('G22', '=IF(\'Input 6(optional)-Standard Test\'!$C$8="On", C7, 0)'),
        # row 24
        ('A24', '=++OFFSET(translation!C1125, 0,LANG)'),
        # row 25
        ('A25', '=++OFFSET(translation!C1550, 0,LANG)'),
        ('B25', '=++OFFSET(translation!C1564, 0,LANG)'),
        ('F25', '=++OFFSET(translation!C1577, 0,LANG)'),
        ('G25', '=IF(\'Input 6(optional)-Standard Test\'!$C$8="On", 0.8, 0)'),
        # row 26: Whichever is lower
        ('B26 B29', '=++OFFSET(translation!C1562, 0,LANG)'),
        # row 28
        ('A28', '=++OFFSET(translation!C1136, 0,LANG)'),
        # row 29
        ('A29', '=++OFFSET(translation!C1552, 0,LANG)'),
        # row 30: Whichever is lower
        ('B30', '=++OFFSET(translation!C1562, 0,LANG)'),
        # row 32
        ('B32', '=++OFFSET(translation!C1566, 0,LANG)'),
        # row 33: Whichever is lower
        ('B33', '=++OFFSET(translation!C1562, 0,LANG)'),
        # row 35
        ('A35', '=++OFFSET(translation!C1127, 0,LANG)'),
        # row 36
        ('A36', '=++OFFSET(translation!C1557, 0,LANG)'),
        ('B36:B38', '=++OFFSET(translation!C1567, 0,LANG)'),
        ('C36', '=IF(C4="NEW",\'Input 1 - Basics\'!C31,0)'),
        ('F36:F38', '=++OFFSET(translation!C1578, 0,LANG)'),
        ('G36', '=IF(\'Input 6(optional)-Standard Test\'!$C$8="On", 0.3, 0)'),
        # row 37
        ('C37', '=IF(C4="NEW",C36+\'Baseline - public\'!P65-$G$38,0)'),
        ('D37', "=C36+'Baseline - public'!P65-$H$38"),
        ('G37', '=IF(\'Input 6(optional)-Standard Test\'!$C$8="On", 0.15, 0)'),
        # row 38
        ('C38', '=IF(\'Input 6(optional)-Standard Test\'!$C$4="New", MAX(30,C37), 30+\'Baseline - external\'!O59)'),
        ('D38', '=MAX(30,D37)'),
        ('G38', '=IF(\'Input 6(optional)-Standard Test\'!$C$8="On", \'Baseline - public\'!P66, 0)'),
        # row 40
        ('A40', '=++OFFSET(translation!C1137, 0,LANG)'),
        # row 41
        ('A41', '=++OFFSET(translation!C1560, 0,LANG)'),
        ('B41:B42 B44', '=++OFFSET(translation!C1561, 0,LANG)'),
        ('C41:D41', '=C17/2'),
        ('F41 F44', '=++OFFSET(translation!C1574, 0,LANG)'),
        ('G41:H41', '=G17'),
        # row 44
        ('C44:D44', '=C25/2'),
        ('G44:H44', '=G25'),
        # row 45: Whichever is lower
        ('B45', '=++OFFSET(translation!C1562, 0,LANG)'),
        # row 47
        ('B47', '=++OFFSET(translation!C1563, 0,LANG)'),
        ('C47:D47', '=C21/2'),
        ('F47:F48', '=++OFFSET(translation!C1575, 0,LANG)'),
        ('G47:H48', '=G21'),
        # row 48: Whichever is lower
        ('B48', '=++OFFSET(translation!C1562, 0,LANG)'),
        # row 50
        ('B50', '=++OFFSET(translation!C1565, 0,LANG)'),
        ('C50:D50 C53:D53', '=C29/2'),
        # row 51: Whichever is lower
        ('B51 B56:B58', '=++OFFSET(translation!C1562, 0,LANG)'),
        # row 53
        ('B53', '=++OFFSET(translation!C1566, 0,LANG)'),
        # row 54: Whichever is lower
        ('B54', '=++OFFSET(translation!C1562, 0,LANG)'),
        # row 56
        ('C56:C58', '=IF(\'Input 6(optional)-Standard Test\'!$C$4="New",C36/2,0)'),
        ('F56:F57', '=++OFFSET(translation!C1578, 0,LANG)'),
        ('G56:G57', '=IF(\'Input 6(optional)-Standard Test\'!$C$8="On",G36,0)'),
        ('H56:H57', '=H36'),
        # row 57
        ('D57:D58', '=D37/2'),
    ],
    'Input 6 - Tailored Tests': [
        # row 1
        ('A1', '=++OFFSET(translation!C1618, 0,LANG)'),
        # row 2
        ('A2', '=++OFFSET(translation!C1617, 0,LANG)'),
        # row 4
        ('A4', '=++OFFSET(translation!C64, 0,LANG)'),
        # row 5: On
        ('A5', '=++OFFSET(translation!C66, 0,LANG)'),
        # row 6: Off
        ('A6', '=++OFFSET(translation!C1618, 0,LANG)'),
        # row 9
        ('A9:A11', '=++OFFSET(translation!C1620, 0,LANG)'),
        ('C9', '=IF(IF(ISNA(MATCH(Country,Trigger!$W$5:$W$27,0)),0,MATCH(Country,Trigger!$W$5:$W$27,0))>0,"Yes","No")'),
        # row 10
        ('C10', '=IF(C6="On", IF(H29>0.5,"Yes","No"), "No")'),
        # row 11
        ('C11', '=IF($C$6="On", IFERROR(IF(INDEX(MktFin, MATCH(Country_Code, INDEX(MktFin,,1),0), COLUMNS(MktFin))=1, "Yes", "No"),"No"),"No")'),
        # row 13
        ('A13', '=++OFFSET(translation!C1618, 0,LANG)'),
        # row 15
        ('A15', '=++OFFSET(translation!C1540, 0,LANG)'),
        ('C15', '=++OFFSET(translation!C1571, 0,LANG)'),
        ('J15', '=++OFFSET(translation!C1573, 0,LANG)'),
        # row 16
        ('G16', '=++OFFSET(translation!C162, 0,LANG)'),
        ('H16', '=++OFFSET(translation!C1572, 0,LANG)'),
        ('K16', '=++OFFSET(translation!C162, 0,LANG)'),
        ('L16', '=++OFFSET(translation!C1572, 0,LANG)'),
        # row 20
        ('A20', '=++OFFSET(translation!C1620, 0,LANG)'),
        # row 21
        ('A21', '=++OFFSET(translation!C1628, 0,LANG)'),
        ('C21', '=++OFFSET(translation!C1631, 0,LANG)'),
        ('G21', '=IF(\'Input 6 - Tailored Tests\'!$C$6="On", 10, 0)'),
        ('H21 L21:L22 H26 L26:L27 H32:H33 H38:H41 H43 H46 H49:H50 H52 H54:H56 H58 L58', '=G21'),
        ('J21:J22', '=++OFFSET(translation!C1662, 0,LANG)'),
        ('K21', '=IF(\'Input 6 - Tailored Tests\'!$C$6="On", 1.5,0)'),
        # row 22
        ('K22', '=IF(\'Input 6 - Tailored Tests\'!$C$6="On", 3.5, 0)'),
        # row 25
        ('A25', '=++OFFSET(translation!C1621, 0,LANG)'),
        # row 26
        ('A26', '=++OFFSET(translation!C1629, 0,LANG)'),
        ('C26', '=++OFFSET(translation!C1632, 0,LANG)'),
        ('G26', '=IF(\'Input 6 - Tailored Tests\'!$C$6="On", 6, 0)'),
        ('J26', '=++OFFSET(translation!C1662, 0,LANG)'),
        ('K26', '=IF(\'Input 6 - Tailored Tests\'!$C$6="On",G46*0.5/-10%,0)'),
        # row 27
        ('J27', '=++OFFSET(translation!C1664, 0,LANG)'),
        ('K27', '=IF(\'Input 6 - Tailored Tests\'!$C$6="On", G46*0.75/-10%, 0)'),
        # row 29
        ('C29:C30', '=++OFFSET(translation!C1633, 0,LANG)'),
        ('G29:H30', '=G33+G43'),
        # row 32
        ('C32:C34 C36:C41 C43:C44 C46 C48:C50 C52:C56 C58', '=++OFFSET(translation!C1635, 0,LANG)'),
        ('G32', "='Imported data'!H92"),
        # row 33
        ('G33', '=IF(ISNUMBER(AVERAGE(\'Macro-Debt_Data\'!R37:T37)),AVERAGE(\'Macro-Debt_Data\'!R37:T37),"")'),
        # row 34
        ('G34:H34', '=MAX(0, G33-G49)'),
        # row 36
        ('G36:H36', '=IF(AND(G38="",G39="",G40="",G41=""),0,AVERAGE(G38:G41))'),
        # row 38: No
        ('G38:G41', '=IF(E38="Yes",\'Imported data\'!H93,"")'),
        # row 43
        ('G43', '=IF(ISNUMBER(AVERAGE(\'Macro-Debt_Data\'!R38:T38)),AVERAGE(\'Macro-Debt_Data\'!R38:T38),"")'),
        # row 44
        ('G44:H44', '=MAX(0, G43-G50)'),
        # row 46
        ('G46', '=IF(\'Input 6 - Tailored Tests\'!$C$6="On", IF(ISNUMBER((G32*G34+G36*G44)/(G34+G44)),(G32*G34+G36*G44)/(G34+G44), 0), 0)'),
        # row 49
        ('G49:G50', '=IF(ISNUMBER(AVERAGE(\'Macro-Debt_Data\'!R41:T41)),AVERAGE(\'Macro-Debt_Data\'!R41:T41),"")'),
        # row 51
        ('A51', '=++OFFSET(translation!C1622, 0,LANG)'),
        # row 52
        ('A52', '=++OFFSET(translation!C1630, 0,LANG)'),
        ('G52', '=IF(\'Input 6 - Tailored Tests\'!$C$6="On", 400,0)'),
        # row 54
        ('G54', '=IF(\'Input 6 - Tailored Tests\'!$C$6="On", 5, 0)'),
        # row 55
        ('G55:G56', '=IF(\'Input 6 - Tailored Tests\'!$C$6="On", 2/3, 0)'),
        # row 58
        ('G58', '=IF(\'Input 6 - Tailored Tests\'!$C$6="On", 15, 0)'),
        ('J58', '=++OFFSET(translation!C1665, 0,LANG)'),
        ('K58', '=IF(\'Input 6 - Tailored Tests\'!$C$6="On", 0.3, 0)'),
    ],
    'Input 7 - Residual Financing': [
        # row 1
        ('B1', '=CONCATENATE(IF(START!L10="English",translation!C592,IF(START!L10="French",D579,IF(START!L10="Portuguese",E579,F579))))'),
        # row 2
        ('B2:B3', '=++OFFSET(translation!C64, 0,LANG)'),
        ('C2:C3', '=++OFFSET(translation!C590,0,LANG)'),
        # row 5
        ('B5', '=++IF(START!L10="English",translation!C592,IF(START!L10="French",translation!D592,IF(START!L10="Portuguese",translation!D592,translation!D592)))'),
        # row 7
        ('B7', '=++OFFSET(translation!C2006,0,LANG)&"*"'),
        ('C7', '=++IF(START!$L$10="English",translation!C162,IF(START!$L$10="French",translation!D162,IF(START!$L$10="Portuguese",translation!E162,translation!F162)))'),
        ('D7', '=++OFFSET(translation!C1572,0,LANG)'),
        ('E7', '=++OFFSET(translation!C593,0,LANG)'),
        ('G7', '=++OFFSET(translation!C2007,0,LANG)&"*"'),
        ('H7', '=++IF(START!$L$10="English",translation!C162,IF(START!$L$10="French",translation!D162,IF(START!$L$10="Portuguese",translation!E162,translation!F162)))'),
        ('I7', '=++OFFSET(translation!C1572,0,LANG)'),
        ('J7', '=++OFFSET(translation!C593,0,LANG)'),
        # row 8
        ('B8 B12:B17', '=G8'),
        ('G8', '=++IF(START!L10="English",translation!C594,IF(START!L10="French",translation!D594,IF(START!L10="Portuguese",translation!E594,translation!FD593)))'),
        # row 9: External PPG MLT debt
        ('D9 I9:I10 D14:D17 I14:I17 I19:I21 I23', '=C9'),
        ('E9 J9:J11 E14:E17 J14:J17 J19:J21 J23', '=IF(ISNUMBER(D9), D9, C9)'),
        ('G9:G23', '=++IF(START!$L$10="English",translation!C595,IF(START!$L$10="French",translation!D595,IF(START!$L$10="Portuguese",translation!E595,translation!F595)))'),
        ('H9:H11', '=Ext_Debt_Data!C126'),
        # row 11
        ('I11', '=1-I9-I10'),
        # row 14
        ('C14', '=Ext_Debt_Data!C131/100'),
        ('H14:H17', '=C14'),
        # row 15
        ('C15', "='Input 1 - Basics'!C25"),
        # row 16
        ('C16', '=IF(Ext_Debt_Data!C133=Ext_Debt_Data!C132,Ext_Debt_Data!C133+1,Ext_Debt_Data!C133)'),
        # row 17
        ('C17', '=Ext_Debt_Data!C132'),
        # row 18
        ('B18', '="* "&++OFFSET(translation!C610, 0,LANG)'),
        # row 19
        ('H19', "='Input 5 - Local-debt Financing'!C130/100"),
        # row 20
        ('H20', "='Input 5 - Local-debt Financing'!C132"),
        # row 21
        ('H21', "='Input 5 - Local-debt Financing'!C131"),
        # row 23
        ('H23', "='Input 5 - Local-debt Financing'!C137/100"),
        # row 24
        ('G24', '="* "&IF(START!L$10="English",translation!C611,IF(START!L$10="French",translation!D611,IF(START!L$10="Portuguese",translation!E611,translation!F611)))'),
    ],
    'Input 8 - SDR': [
        # row 2
        ('A2', "='Input 1 - Basics'!B3"),
        # row 3
        ('A3', "='Input 1 - Basics'!B5"),
        # row 6: *Total stock, including increased SDR allocation
        ('A6', '=CONCATENATE("SDR allocation (in ",\'Input 1 - Basics\'!C19," of USD)")'),
        # row 7
        ('A7', '=CONCATENATE("SDR holdings (in ",\'Input 1 - Basics\'!C19," of USD)")'),
        # row 9
        ('C9', "='Macro-Debt_Data'!U4"),
        ('D9:W9 C22:X22', '=C9+1'),
        # row 11
        ('A11', '=CONCATENATE("Expected drawdown of SDR holdings (in ",\'Macro-Debt_Data\'!D6," of USD)")'),
        # row 12
        ('A12', '=CONCATENATE("Possible reconsitution of SDR holdings (in ",\'Macro-Debt_Data\'!D7," of USD)")'),
        # row 16
        ('A16', '=CONCATENATE("SDR allocation - holdings (in ",\'Macro-Debt_Data\'!D11," of USD)")'),
        ('C16', '=IF(B6-SUM(C12:C12)-(B7-SUM(C11:C11))<0,0,(B6-SUM(C12:C12)-(B7-SUM(C11:C11))))'),
        ('D16', '=IF(B6-SUM(C12:D12)-(B7-SUM(C11:D11))<0,0,(B6-SUM(C12:D12)-(B7-SUM(C11:D11))))'),
        ('E16', '=IF(B6-SUM(C12:E12)-(B7-SUM(C11:E11))<0,0,(B6-SUM(C12:E12)-(B7-SUM(C11:E11))))'),
        ('F16', '=IF(B6-SUM(C12:F12)-(B7-SUM(C11:F11))<0,0,(B6-SUM(C12:F12)-(B7-SUM(C11:F11))))'),
        ('G16', '=IF(B6-SUM(C12:G12)-(B7-SUM(C11:G11))<0,0,(B6-SUM(C12:G12)-(B7-SUM(C11:G11))))'),
        ('H16', '=IF(B6-SUM(C12:H12)-(B7-SUM(C11:H11))<0,0,(B6-SUM(C12:H12)-(B7-SUM(C11:H11))))'),
        ('I16', '=IF(B6-SUM(C12:I12)-(B7-SUM(C11:I11))<0,0,(B6-SUM(C12:I12)-(B7-SUM(C11:I11))))'),
        ('J16', '=IF(B6-SUM(C12:J12)-(B7-SUM(C11:J11))<0,0,(B6-SUM(C12:J12)-(B7-SUM(C11:J11))))'),
        ('K16', '=IF(B6-SUM(C12:K12)-(B7-SUM(C11:K11))<0,0,(B6-SUM(C12:K12)-(B7-SUM(C11:K11))))'),
        ('L16', '=IF(B6-SUM(C12:L12)-(B7-SUM(C11:L11))<0,0,(B6-SUM(C12:L12)-(B7-SUM(C11:L11))))'),
        ('M16', '=IF(B6-SUM(C12:M12)-(B7-SUM(C11:M11))<0,0,(B6-SUM(C12:M12)-(B7-SUM(C11:M11))))'),
        ('N16', '=IF(B6-SUM(C12:N12)-(B7-SUM(C11:N11))<0,0,(B6-SUM(C12:N12)-(B7-SUM(C11:N11))))'),
        ('O16', '=IF(B6-SUM(C12:O12)-(B7-SUM(C11:O11))<0,0,(B6-SUM(C12:O12)-(B7-SUM(C11:O11))))'),
        ('P16', '=IF(B6-SUM(C12:P12)-(B7-SUM(C11:P11))<0,0,(B6-SUM(C12:P12)-(B7-SUM(C11:P11))))'),
        ('Q16', '=IF(B6-SUM(C12:Q12)-(B7-SUM(C11:Q11))<0,0,(B6-SUM(C12:Q12)-(B7-SUM(C11:Q11))))'),
        ('R16', '=IF(B6-SUM(C12:R12)-(B7-SUM(C11:R11))<0,0,(B6-SUM(C12:R12)-(B7-SUM(C11:R11))))'),
        ('S16', '=IF(B6-SUM(C12:S12)-(B7-SUM(C11:S11))<0,0,(B6-SUM(C12:S12)-(B7-SUM(C11:S11))))'),
        ('T16', '=IF(B6-SUM(C12:T12)-(B7-SUM(C11:T11))<0,0,(B6-SUM(C12:T12)-(B7-SUM(C11:T11))))'),
        ('U16', '=IF(B6-SUM(C12:U12)-(B7-SUM(C11:U11))<0,0,(B6-SUM(C12:U12)-(B7-SUM(C11:U11))))'),
        ('V16', '=IF(B6-SUM(C12:V12)-(B7-SUM(C11:V11))<0,0,(B6-SUM(C12:V12)-(B7-SUM(C11:V11))))'),
        ('W16', '=IF(B6-SUM(C12:W12)-(B7-SUM(C11:W11))<0,0,(B6-SUM(C12:W12)-(B7-SUM(C11:W11))))'),
        # row 17
        ('A17', '=CONCATENATE("Interest payments (in ",\'Macro-Debt_Data\'!D12," of USD)")'),
        ('C17', '=IF(B7<=B6,(B6-B7)*C14,0)'),
        ('D17', '=IF(C16<=B6,C16*D14,0)'),
        ('E17', '=IF(D16<=B6,D16*E14,0)'),
        ('F17', '=IF(E16<=B6,E16*F14,0)'),
        ('G17', '=IF(F16<=B6,F16*G14,0)'),
        ('H17', '=IF(G16<=B6,G16*H14,0)'),
        ('I17', '=IF(H16<=B6,H16*I14,0)'),
        ('J17', '=IF(I16<=B6,I16*J14,0)'),
        ('K17', '=IF(J16<=B6,J16*K14,0)'),
        ('L17', '=IF(K16<=B6,K16*L14,0)'),
        ('M17', '=IF(L16<=B6,L16*M14,0)'),
        ('N17', '=IF(M16<=B6,M16*N14,0)'),
        ('O17', '=IF(N16<=B6,N16*O14,0)'),
        ('P17', '=IF(O16<=B6,O16*P14,0)'),
        ('Q17', '=IF(P16<=B6,P16*Q14,0)'),
        ('R17', '=IF(Q16<=B6,Q16*R14,0)'),
        ('S17', '=IF(R16<=B6,R16*S14,0)'),
        ('T17', '=IF(S16<=B6,S16*T14,0)'),
        ('U17', '=IF(T16<=B6,T16*U14,0)'),
        ('V17', '=IF(U16<=B6,U16*V14,0)'),
        ('W17', '=IF(V16<=B6,V16*W14,0)'),
        # row 22
        ('B22', '=C9-1'),
        # row 24
        ('A24', '=CONCATENATE("PV of interest payments (in ",\'Macro-Debt_Data\'!D19," of USD)")'),
        ('B24', "=NPV('Input 1 - Basics'!C25,'Input 8 - SDR'!C26:W26)"),
        ('C24', "=NPV('Input 1 - Basics'!C25,'Input 8 - SDR'!D27:X27)"),
        ('D24', "=NPV('Input 1 - Basics'!C25,'Input 8 - SDR'!E28:Y28)"),
        ('E24', "=NPV('Input 1 - Basics'!C25,'Input 8 - SDR'!F29:Z29)"),
        ('F24', "=NPV('Input 1 - Basics'!C25,'Input 8 - SDR'!G30:AA30)"),
        ('G24', "=NPV('Input 1 - Basics'!C25,'Input 8 - SDR'!H31:AA31)"),
        ('H24', "=NPV('Input 1 - Basics'!C25,'Input 8 - SDR'!I32:AB32)"),
        ('I24', "=NPV('Input 1 - Basics'!C25,'Input 8 - SDR'!J33:AC33)"),
        ('J24', "=NPV('Input 1 - Basics'!C25,'Input 8 - SDR'!K34:AD34)"),
        ('K24', "=NPV('Input 1 - Basics'!C25,'Input 8 - SDR'!L35:AE35)"),
        ('L24', "=NPV('Input 1 - Basics'!C25,'Input 8 - SDR'!M36:AF36)"),
        ('M24', "=NPV('Input 1 - Basics'!C25,'Input 8 - SDR'!N37:AG37)"),
        ('N24', "=NPV('Input 1 - Basics'!C25,'Input 8 - SDR'!O38:AH38)"),
        ('O24', "=NPV('Input 1 - Basics'!C25,'Input 8 - SDR'!P39:AI39)"),
        ('P24', "=NPV('Input 1 - Basics'!C25,'Input 8 - SDR'!Q40:AJ40)"),
        ('Q24', "=NPV('Input 1 - Basics'!C25,'Input 8 - SDR'!R41:AK41)"),
        ('R24', "=NPV('Input 1 - Basics'!C25,'Input 8 - SDR'!S42:AL42)"),
        ('S24', "=NPV('Input 1 - Basics'!C25,'Input 8 - SDR'!T43:AM43)"),
        ('T24', "=NPV('Input 1 - Basics'!C25,'Input 8 - SDR'!U44:AN44)"),
        ('U24', "=NPV('Input 1 - Basics'!C25,'Input 8 - SDR'!V45:AO45)"),
        ('V24', "=NPV('Input 1 - Basics'!C25,'Input 8 - SDR'!W46:AP46)"),
        ('W24', "=NPV('Input 1 - Basics'!C25,'Input 8 - SDR'!X47:AQ47)"),
        # row 26
        ('A26', '=CONCATENATE("as of end","-",C9-1)'),
        ('C26', '=IF(B7<B6,(B6-B7)*C14,0)'),
        ('D26', '=IF(B7<B6,(B6-B7)*D14,0)'),
        ('E26', '=IF(B7<B6,(B6-B7)*E14,0)'),
        ('F26', '=IF(B7<B6,(B6-B7)*F14,0)'),
        ('G26', '=IF(B7<B6,(B6-B7)*G14,0)'),
        ('H26', "=IF(B7<B6,(B6-B7)*H14+(B6-B7)*H14/('Input 1 - Basics'!C25),0)"),
        # row 27
        ('A27', '=CONCATENATE("as of end","-",C9)'),
        ('D27', '=IF(C16>0,C16*D14,0)'),
        ('E27', '=IF(D16>0,C16*E14,0)'),
        ('F27', '=IF(E16>0,C16*F14,0)'),
        ('G27', '=IF(F16>0,C16*G14,0)'),
        ('H27', "=IF(C16>0,C16*H14+C16*H14/('Input 1 - Basics'!C25),0)"),
        # row 28
        ('A28', '=CONCATENATE("as of end","-",D9)'),
        ('E28', '=IF(D16>0,D16*E14,0)'),
        ('F28', '=IF(E16>0,D16*F14,0)'),
        ('G28', '=IF(F16>0,D16*G14,0)'),
        ('H28', "=IF(D16>0,D16*H14+D16*H14/('Input 1 - Basics'!C25),0)"),
        # row 29
        ('A29', '=CONCATENATE("as of end","-",E9)'),
        ('F29', '=IF(E16>0,E16*F14,0)'),
        ('G29', '=IF(F16>0,E16*G14,0)'),
        ('H29', "=IF(E16>0,E16*H14+E16*H14/('Input 1 - Basics'!C25),0)"),
        # row 30
        ('A30', '=CONCATENATE("as of end","-",F9)'),
        ('G30', '=IF(F16>0,F16*G14,0)'),
        ('H30', "=IF(F16>0,F16*H14+F16*H14/('Input 1 - Basics'!C25),0)"),
        # row 31
        ('A31', '=CONCATENATE("as of end","-",G9)'),
        ('H31', "=IF(G16>0,G16*H14+G16*H14/('Input 1 - Basics'!C25),0)"),
        # row 32
        ('A32', '=CONCATENATE("as of end","-",H9)'),
        ('I32', "=IF(H16>0,H16*I14+H16*I14/('Input 1 - Basics'!C25),0)"),
        # row 33
        ('A33', '=CONCATENATE("as of end","-",I9)'),
        ('J33', "=IF(I16>0,I16*J14+I16*J14/('Input 1 - Basics'!C25),0)"),
        # row 34
        ('A34', '=CONCATENATE("as of end","-",J9)'),
        ('K34', "=IF(J16>0,J16*K14+J16*K14/('Input 1 - Basics'!C25),0)"),
        # row 35
        ('A35', '=CONCATENATE("as of end","-",K9)'),
        ('L35', "=IF(K16>0,K16*L14+K16*L14/('Input 1 - Basics'!C25),0)"),
        # row 36
        ('A36', '=CONCATENATE("as of end","-",L9)'),
        ('M36', "=IF(L16>0,L16*M14+L16*M14/('Input 1 - Basics'!C25),0)"),
        # row 37
        ('A37', '=CONCATENATE("as of end","-",M9)'),
        ('N37', "=IF(M16>0,M16*N14+M16*N14/('Input 1 - Basics'!C25),0)"),
        # row 38
        ('A38', '=CONCATENATE("as of end","-",N9)'),
        ('O38', "=IF(N16>0,N16*O14+N16*O14/('Input 1 - Basics'!C25),0)"),
        # row 39
        ('A39', '=CONCATENATE("as of end","-",O9)'),
        ('P39', "=IF(O16>0,O16*P14+O16*P14/('Input 1 - Basics'!C25),0)"),
        # row 40
        ('A40', '=CONCATENATE("as of end","-",P9)'),
        ('Q40', "=IF(P16>0,P16*Q14+P16*Q14/('Input 1 - Basics'!C25),0)"),
        # row 41
        ('A41', '=CONCATENATE("as of end","-",Q9)'),
        ('R41', "=IF(Q16>0,Q16*R14+Q16*R14/('Input 1 - Basics'!C25),0)"),
        # row 42
        ('A42', '=CONCATENATE("as of end","-",R9)'),
        ('S42', "=IF(R16>0,R16*S14+R16*S14/('Input 1 - Basics'!C25),0)"),
        # row 43
        ('A43', '=CONCATENATE("as of end","-",S9)'),
        ('T43', "=IF(S16>0,S16*T14+S16*T14/('Input 1 - Basics'!C25),0)"),
        # row 44
        ('A44', '=CONCATENATE("as of end","-",T9)'),
        ('U44', "=IF(T16>0,T16*U14+T16*U14/('Input 1 - Basics'!C25),0)"),
        # row 45
        ('A45', '=CONCATENATE("as of end","-",U9)'),
        ('V45', "=IF(U16>0,U16*V14+U16*V14/('Input 1 - Basics'!C25),0)"),
        # row 46
        ('A46', '=CONCATENATE("as of end","-",V9)'),
        ('W46', "=IF(V16>0,V16*W14+V16*W14/('Input 1 - Basics'!C25),0)"),
        # row 47
        ('A47', '=CONCATENATE("as of end","-",W9)'),
        ('X47', "=IF(W16>0,W16*W14+W16*W14/('Input 1 - Basics'!C25),0)"),
    ],
    'Imported data': [
        # row 2: Country
        ('D2:D3', "='Input 1 - Basics'!C7"),
        # row 5: Current vintage
        ('D5', "='Input 1 - Basics'!C17"),
        # row 6: The latest vintage
        ('C6', '=D3&"."&1'),
        ('D6:D7', '=LEFT(E6, 4)'),
        ('E6:E7', "=INDEX(DSF__LIST_DSA, MATCH('Imported data'!C6,INDEX(DSF__LIST_DSA,,1), 0), MATCH('Imported data'!$E$4,INDEX(DSF__LIST_DSA,1,), 0))"),
        # row 7: 5 years ago
        ('C7', '=D3&"."&5'),
        # row 10
        ('J10:P10 J37:P37 L68:P68 K81:P81', '=K10-1'),
        ('Q10', "='Realism 1 - Forecast Error'!O11"),
        ('R10:AA10 R37:AA37 M67:U67 R68:U68 R81:V81', '=Q10+1'),
        # row 14
        ('B14:B16 B18:B21 B23:B26 B40 B42:B48', '=$D$7'),
        ('C14:C16 E14:E16 C18:C21 E18:E21 C23:C26 E23:E26', "='Realism 1 - Forecast Error'!C15"),
        ('D14:D16 D18:D21 D23:D26 D40 D42:D48', '=$D$3&"."&C14&"."&$E$7&".A"'),
        ('J14:AA16 J18:AA21 J23:AA26 J30:AA30 J32:AA32 J40:AA40 J42:AA48 J51:AA51 J53:AA53', '=INDEX(DSF__PREV_DSA_DATA, MATCH($D14, INDEX(DSF__PREV_DSA_DATA,,2), 0), MATCH(J$10,INDEX(DSF__PREV_DSA_DATA,1,), 0))/$AC14'),
        # row 30
        ('B30 B32 B51 B53 B60 B62:B63', '=$D$6'),
        ('C30 E30 C32 E32', '=C14'),
        ('D30 D32 D51 D53 D60 D62:D63', '=$D$3&"."&C30&"."&$E$6&".A"'),
        # row 37: Public debt
        ('Q37', '=Q10'),
        # row 40
        ('C40 E40 C42:C48 E42:E48', "='Realism 1 - Forecast Error'!C115"),
        # row 49: Residual
        ('K49:V49', '=K47-K44-K45-K46-K48-K43'),
        # row 51
        ('C51 E51 C53 E53', '=C40'),
        # row 59
        ('G59:V59', "='Realism 3 - Invest-Growth'!C49"),
        # row 60: NGDP_R_PCH
        ('G60:V60', '=INDEX(DSF__PREV_DSA_DATA, MATCH($D60, INDEX(DSF__PREV_DSA_DATA,,2), 0), MATCH(G$59,INDEX(DSF__PREV_DSA_DATA,1,), 0))/$AC60'),
        # row 61: Capital stock/GDP
        ('D61', "='Realism 3 - Invest-Growth'!A70"),
        ('G61:V61', '=IF(ISNUMBER(INDEX(DSF__FAD_DATA,MATCH(VALUE($D$3&G59),INDEX(DSF__FAD_DATA,,MATCH("DSA Template ID",INDEX(DSF__FAD_DATA,1,),0)),0),MATCH($C$61,INDEX(DSF__FAD_DATA,1,),0))),INDEX(DSF__FAD_DATA,MATCH(VALUE($D$3&G59),INDEX(DSF__FAD_DATA,,MATCH("DSA Template ID",INDEX(DSF__FAD_DATA,1,),0)),0),MATCH($C$61,INDEX(DSF__FAD_DATA,1,),0)),"")'),
        # row 62: NFIG_R_GDP
        ('G62:AA63', '=IFERROR(INDEX(DSF__PREV_DSA_DATA, MATCH($D62, INDEX(DSF__PREV_DSA_DATA,,2), 0), MATCH(G$59,INDEX(DSF__PREV_DSA_DATA,1,), 0))/$AC62,"")'),
        # row 68: Components
        ('Q68', '=DSF__CLASSIFICATION_PROJECTION_YEAR'),
        ('AG68:AP68', '=L68'),
        # row 69: CPIA
        ('L69:U71 L73:U74', '=INDEX(DSF__CLASSIFICATION_BIG_TABLE, MATCH($D$3,INDEX(DSF__CLASSIFICATION_BIG_TABLE,,1), 0), MATCH(AG69, INDEX(DSF__CLASSIFICATION_BIG_TABLE,1,), 0))'),
        ('AG69:AP71 AG73:AP74', '=$AF69&AG$68'),
        # row 75: Remittances
        ('L75:U75', '=INDEX(DSF__DATA_REMGDP, MATCH($D$3,INDEX(DSF__DATA_REMGDP,,3), 0), MATCH(L$68, INDEX(DSF__DATA_REMGDP,1,), 0))'),
        # row 76: GDP (USD, billions)
        ('L76:U76', '=INDEX(DSF__DATA_GDPUSD, MATCH($D$3,INDEX(DSF__DATA_GDPUSD,,3), 0), MATCH(L$68, INDEX(DSF__DATA_GDPUSD,1,), 0))'),
        # row 77: CPIA 3-yr avg
        ('Q77:R78', '=INDEX(DSF__CLASSIFICATION_BIG_TABLE, MATCH($D$3,INDEX(DSF__CLASSIFICATION_BIG_TABLE,,1), 0), MATCH(AF77, INDEX(DSF__CLASSIFICATION_BIG_TABLE,1,), 0))'),
        # row 79
        ('Q79:R79', '=VLOOKUP(Q78, $AI$77:$AJ$79, 2, FALSE)'),
        # row 81
        ('Q81', "='Probability approach'!H24"),
        # row 82: CPIA
        ('K82:V82', '=IFERROR(INDEX(DSF__DATA_CPIA, MATCH($D$3,INDEX(DSF__DATA_CPIA,,3), 0), MATCH(K$81, INDEX(DSF__DATA_CPIA,1,), 0)),J82)'),
        # row 88: As of:
        ('C88', '=DSF__COMMODITY_LATEST', 'date'),
        # row 92: Brent
        ('C92:C96', '=$C$88&D92'),
        ('E92:G96', '=IF(ISNUMBER(INDEX(DSF__COMMODITY_TABLE, MATCH($C92, INDEX(DSF__COMMODITY_TABLE,,2), 0), MATCH(E$91, INDEX(DSF__COMMODITY_TABLE,1,), 0))), INDEX(DSF__COMMODITY_TABLE, MATCH($C92, INDEX(DSF__COMMODITY_TABLE,,2), 0), MATCH(E$91, INDEX(DSF__COMMODITY_TABLE,1,), 0)), 0)'),
        ('H92:H96', '=(F92-E92)/E92'),
        # row 105: PRGT market access
        ('C105', '=Trigger!AC4'),
        # row 106
        ('A106:A200', '=IFERROR(IF(ISBLANK(OFFSET(INDEX(Country_list,ROW()-ROW($B$106)+1,1),0,-1)),"",OFFSET(INDEX(Country_list,ROW()-ROW($B$106)+1,1),0,-1)),"")'),
        ('B106:B200', '=IFERROR(IF(ISBLANK(OFFSET(INDEX(Country_list,ROW()-ROW($B$106)+1,1),0,0)),"",OFFSET(INDEX(Country_list,ROW()-ROW($B$106)+1,1),0,0)),"")'),
        ('C106:D200', '=IFERROR(IF(INDEX(DSF__Country_Info,MATCH($A106,INDEX(DSF__Country_Info,,1),0),MATCH(C$105,INDEX(DSF__Country_Info,1,),0))="Yes","Yes",""),"")'),
    ],
    'CI Summary': [
        # row 3
        ('B3 B4:C4', "='Input 1 - Basics'!B7"),
        ('C3', '=Country'),
        # row 6: Debt Carrying Capacity
        ('C6', "=IF('Input 6(optional)-Standard Test'!C4=lookup!$AF$4, 'CI Summary'!B9, 'CI Summary'!F68)"),
        ('K6', '=H6'),
        # row 8: Final
        ('H8', '=++IF(START!L10="English",translation!C196,IF(START!L10="French",translation!D196,IF(START!L10="Portuguese",translation!E196,translation!F196)))'),
        ('K8', '=IF(START!L10="English",translation!C204,IF(START!L10="French",translation!D204,IF(START!L10="Portuguese",translation!E204,translation!F204)))'),
        # row 9
        ('B9', '=IF(C9=D9, C9, E9)'),
        ('C9', '=IF(\'Input 6(optional)-Standard Test\'!C4="New", \'CI Summary\'!E27, \'CI Summary\'!F68)'),
        ('D9:E9', "='Imported data'!Q79"),
        ('H9', '=++IF(START!L10="English",translation!C197,IF(START!L10="French",translation!D197,IF(START!L10="Portuguese",translation!E197,translation!F197)))'),
        ('K9', '=IF(START!L10="English",translation!C205,IF(START!L10="French",translation!D205,IF(START!L10="Portuguese",translation!E205,translation!F205)))'),
        ('L9', "=IF('Input 6(optional)-Standard Test'!$C$4=lookup!$AF$4, INDEX($H$32:$M$33, MATCH(K9, $H$32:$H$33, 0), MATCH($C$6, $H$32:$M$32, 0)), S67)"),
        # row 10
        ('C10', '=IF(\'Input 6(optional)-Standard Test\'!C4="New", E25, F67)'),
        ('D10:E10', "='Imported data'!Q77"),
        ('H10', '=++IF(START!L10="English",translation!C198,IF(START!L10="French",translation!D198,IF(START!L10="Portuguese",translation!E198,translation!F198)))'),
        ('I10:I11', "=IF('Input 6(optional)-Standard Test'!$C$4=lookup!$AF$4, INDEX($B$32:$E$35, MATCH($H10, $B$32:$B$35, 0), MATCH($C$6, $B$32:$E$32, 0)), P68)"),
        # row 11
        ('H11', '=++IF(START!L10="English",translation!C199,IF(START!L10="French",translation!D199,IF(START!L10="Portuguese",translation!E199,translation!F199)))'),
        # row 12
        ('B12', "='Imported data'!C83"),
        ('H12', '=++IF(START!L10="English",translation!C201,IF(START!L10="French",translation!D201,IF(START!L10="Portuguese",translation!E201,translation!F201)))'),
        # row 13
        ('H13', '=++IF(START!L10="English",translation!C202,IF(START!L10="French",translation!D202,IF(START!L10="Portuguese",translation!E202,translation!F202)))'),
        ('I13:I14', "=IF('Input 6(optional)-Standard Test'!$C$4=lookup!$AF$4, INDEX($B$36:$E$38, MATCH($H13, $B$36:$B$38, 0), MATCH($C$6, $B$32:$E$32, 0)), P71)"),
        # row 14
        ('H14', '=++IF(START!L10="English",translation!C203,IF(START!L10="French",translation!D203,IF(START!L10="Portuguese",translation!E203,translation!F203)))'),
        # row 17
        ('B17', '=++OFFSET(translation!C1703, 0,LANG)'),
        ('C17', '=++OFFSET(translation!C1705, 0,LANG)'),
        ('D17', '=++OFFSET(translation!C1706, 0,LANG)'),
        ('E17', '=++OFFSET(translation!C1707, 0,LANG)'),
        ('F17', '=++OFFSET(translation!C1708, 0,LANG)'),
        # row 18
        ('B18', '=++OFFSET(translation!C1709, 0,LANG)'),
        ('C18:C23', "=ROUND(-AVERAGE('CI Summary'!C88:F88), 3)"),
        ('D18:D20 D22:D23', '=AVERAGE(C46:L46)'),
        ('E18 O46', '=C18*D18'),
        ('F18:F23', '=E18/$E$25'),
        # row 19
        ('B19', '=++OFFSET(translation!C1710, 0,LANG)&" "&++OFFSET(translation!C1714, 0,LANG)'),
        ('E19:E23 O47:O51', '=C19%*D19'),
        # row 20
        ('B20', '=++OFFSET(translation!C1711, 0,LANG)&" "&++OFFSET(translation!C1714, 0,LANG)'),
        ('I20', '=J19'),
        ('K20', '=J21'),
        # row 21
        ('B21', '=++OFFSET(translation!C1711, 0,LANG)&"^2"&"  "&++OFFSET(translation!C1714, 0,LANG)'),
        ('D21', '=AVERAGE(C48:L48)^2/100'),
        # row 22
        ('B22', '=++OFFSET(translation!C1712, 0,LANG)&" "&++OFFSET(translation!C1714, 0,LANG)'),
        # row 23
        ('B23', '=++OFFSET(translation!C1713, 0,LANG)&" "&++OFFSET(translation!C1714, 0,LANG)'),
        # row 25: CI Score
        ('E25:F25 O53:P53', '=SUM(E18:E23)'),
        # row 27
        ('B27', '=IF(START!$L$10="English",translation!C195,IF(START!$L$10="French",translation!D195,IF(START!$L$10="Portuguese",translation!E195,translation!F195)))'),
        ('E27', '=IF(E25<J19,H19,IF(E25>J21,H21,H20))'),
        # row 30
        ('B30', '=++OFFSET(translation!C1758, 0,LANG)'),
        # row 32: Weak
        ('B32:B35 B37:B38', '=H8'),
        ('H32:H33', '=K8'),
        ('K32:M32', '=C32'),
        # row 42
        ('B42', '=++OFFSET(translation!C1759, 0,LANG)'),
        # row 45: Components
        ('C45:G45', '=D45-1'),
        ('H45 C46:L48 C51:L51', "='Imported data'!Q68"),
        ('I45:L45', '=H45+1'),
        # row 46: CPIA
        ('M46:M48 M50:M51', '=AVERAGE(C46:L46)'),
        ('N46:N51', "=ROUND(-AVERAGE('CI Summary'!C88:F88), 3)"),
        ('P46:P51', '=O46/$O$53'),
        # row 49: Import coverage of reserves^2 (in percent)
        ('C49:L49', '=C48^2/100'),
        ('M49', '=AVERAGE(C48:L48)^2/100'),
        # row 50: Remittances (in percent)
        ('C50:L50', '=IF((C56/C57*100)>$C$58, $C$58, C56/C57*100)'),
        # row 55
        ('B55', '=IF(Int_Ext=0, ++OFFSET(translation!C1904, 0,LANG), translation!J1904)'),
        # row 56: Remittances (Gross, US dollars, billions)
        ('C56:L57', "='Imported data'!L75"),
        # row 65
        ('I65', '="CPIA  ≤  "&3.25'),
        # row 67: CPIA Rating
        ('F67', "='Imported data'!R77"),
        ('S67', '=INDEX($H$72:$M$73, MATCH($R$67, $H$72:$H$73, 0), MATCH($F$68, $H$72:$M$72, 0))'),
        # row 68: Performance Policy
        ('F68', "='Imported data'!R79"),
        ('P68:P69', '=INDEX($B$72:$E$79, MATCH(O68, $B$72:$B$75, 0), MATCH($F$68, $B$72:$E$72, 0))'),
        # row 71
        ('P71:P72', '=INDEX($B$77:$E$79, MATCH(O71, $B$77:$B$79, 0), MATCH($F$68, $B$72:$E$72, 0))'),
        # row 72
        ('B72:E72 H72:H73 K72:M72 B73:B75', '=B32'),
        # row 77
        ('B77:B79', '=B36'),
    ],
    'Trigger': [
        # row 3: Note: Per FAD database manual, source is World Bank Private Participat...
        ('B3', '=lookup!A3'),
        ('C3', '=lookup!C3'),
        # row 5
        ('A5:A57', "='Imported data'!B216"),
        ('B5:C58', '=INDEX(lookup!$A$3:$D$73, MATCH(Trigger!$A5, lookup!$B$3:$B$73, 0), MATCH(Trigger!B$3, lookup!$A$3:$F$3, 0))'),
        ('D5:D57 G5:I57 I58', "=INDEX('Imported data'!$B$215:$I$270, MATCH('Imported data'!$B216, 'Imported data'!$B$215:$B$270, 0), MATCH(Trigger!D$4, 'Imported data'!$B$215:$I$215, 0))"),
        ('J5:J58', '=IF(OR(G5=0, H5=0), 0, G5/H5)'),
        ('L5:L7 L9:L58', '=IF(J5>$L$4,A5,"")'),
        ('M5:M9 M11:M30 M32:M45 M47:M48 M50:M58', '=IF(L5=A5,C5,"")'),
        ('N5:N58', '=IF(ISERROR(J5*$N$4), 0, (J5*$N$4))*100'),
        ('AA5:AA74', '=VLOOKUP(AB5, lookup!$C$4:$G$73, 5, FALSE)'),
        ('AC5:AD74', '=INDEX(IMPORTED_TRIGGER, MATCH(Trigger!$AA5, INDEX(IMPORTED_TRIGGER,,1), 0), MATCH(Trigger!AC$4,INDEX(IMPORTED_TRIGGER,1,), 0))'),
        ('AE5:AE74', '=IF(OR(AC5="Yes", AD5="Yes"), 1, 0)'),
        # row 58
        ('A58', "='Imported data'!B270"),
        ('D58 G58:H58', "=INDEX('Imported data'!$B$215:$I$270, MATCH('Imported data'!$B270, 'Imported data'!$B$215:$B$270, 0), MATCH(Trigger!D$4, 'Imported data'!$B$215:$I$215, 0))"),
    ],
    'Dom_Debt_Indicators': [
        # row 3
        ('B3', '=++OFFSET(translation!C1071,0,LANG)&" 6. "&Country&++OFFSET(translation!C1072,0,LANG)&" "&\'Macro-Debt_Data\'!U5&"-"&\'Macro-Debt_Data\'!AE5'),
        # row 22: Medium and long-term
        ('F22', "='Input 7 - Residual Financing'!H10/('Input 7 - Residual Financing'!H10+'Input 7 - Residual Financing'!H11)"),
        # row 23: Short-term
        ('F23', "='Input 7 - Residual Financing'!H11/('Input 7 - Residual Financing'!H10+'Input 7 - Residual Financing'!H11)"),
        # row 25
        ('B25:B30', "='Input 7 - Residual Financing'!G18"),
        # row 26
        ('F26:F28 F30', "='Input 7 - Residual Financing'!H19"),
        # row 32
        ('B32', "='Output 3-2 Stress-public'!B102"),
    ],
    'Output - Summary': [
        # row 5: Country
        ('C5', '=Country'),
        # row 6: IFS Code
        ('C6', '=Code'),
        # row 7: ISO Code
        ('C7', '=ISO'),
        # row 8: HIPC Status
        ('C8', "='Input 1 - Basics'!C13"),
        # row 9: First Year of Projection
        ('C9', '=ProjectionYear'),
        # row 10: IMF program
        ('C10:C12', "='Input 1 - Basics'!C10"),
    ],
    'Output - Submit': [
        # row 5: Country
        ('C5', '=Country'),
        # row 6: IFS Code
        ('C6', '=Code'),
        # row 7: ISO Code
        ('C7', '=ISO'),
        # row 8: HIPC Status
        ('C8', "='Input 1 - Basics'!C13"),
        # row 9: First Year of Projection
        ('C9', '=ProjectionYear'),
        # row 10: Composite Indicator
        ('C10', "='CI Summary'!C10"),
        # row 11: Debt Carrying Capacity
        ('C11', "='CI Summary'!B9"),
    ],
}


def compute(book, sheet):
    """Fill every formula cell of `sheet` from the book's current values."""
    evaluate(book, sheet, BLOCKS[sheet])
