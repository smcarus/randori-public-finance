"""Debt data sheets of the LIC DSF template, plus the Excel helpers the LIC debt modules share.

- Macro-Debt_Data: the macro and debt database the DSA runs on. Historical years (H:T, 2011-2023) are read from
  'Input 3 - Macro-Debt data(DMX)' (non-numbers become 0); projection years (U:AO) take public external debt,
  debt service and new borrowing from Ext_Debt_Data and domestic debt from 'Input 5 - Local-debt Financing'.
  Below the data block come the derived indicators (growth rates, ratios to GDP or exports, implicit interest
  rates, residuals) and the translated labels of column E.
- Dom_Debt_Data: worksheet for the domestic debt indicators (domestic debt / GDP, domestic debt service /
  revenue, net domestic issuance), looked up by variable name in the two baseline sheets and Macro-Debt_Data.
- DMX_OUT: the sheet that saves DSA-generated series to DMX: year header, period codes and straight copies of
  the interest rates, maturities and domestic-debt projections of 'Input 5 - Local-debt Financing'.

The helper section (class X and the function-style helpers) gives formulas Excel's own arithmetic: blanks are 0,
errors propagate left to right, text in arithmetic is #VALUE!, text comparisons ignore case. extdebt.py and pv.py
import them from here.
"""
import math

from sovrisk.srdsf.book import ci, cl
from sovrisk.srdsf.xl import DIV0, NA, VALUE, iserr

SHEETS = ['Macro-Debt_Data', 'Dom_Debt_Data', 'DMX_OUT']

QUIRKS = [
    "Macro-Debt_Data!T9 (2023 PPG MLT external debt) adds 'Input 3'!W209 where every other historical year adds "
    "row 208 (the PPG external debt of private-sector-held domestic issuance): T9 picks up row 209 instead.",
    "Macro-Debt_Data!B4 reads the French label from translation!D194 although the other languages use row 193; "
    "E15 reads row 212 in English but 213 in the other languages.",
    "Macro-Debt_Data!E85 always shows the English label (translation!C400), whatever the language.",
    "Macro-Debt_Data!H74, H75, H97, H109, H111 and H114 (the first historical year) refer three columns back to "
    "E74, E11, E13, E96, E108, E110 and E113 (the label/descriptor columns) instead of the previous year, so they "
    "show '...' or text-arithmetic errors; H71 drops the previous-year short-term term.",
    "Macro-Debt_Data uses both '...' (three dots) and the single ellipsis character '…' as the not-available "
    "marker, depending on the row.",
    "Dom_Debt_Data!D2 and F6 use CELL(\"filename\") / INDIRECT on the file name: the template's own cached value "
    "is #VALUE!, which is reproduced.",
    "DMX_OUT!P58 copies 'Input 5'!H76 (the 2023 column, a different row) while Q58:AK58 copy row 77 from column "
    "I on: the first projection year comes from another row.",
]


# ====================================================================== Excel helpers shared by the LIC modules
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
    try:                                   # numbers stored as text are coerced; other text is #VALUE!
        return float(v)
    except (TypeError, ValueError):
        return VALUE


def _kind(v):
    """Excel's ordering of types in comparisons: numbers < text < logicals."""
    return 2 if isinstance(v, bool) else 1 if isinstance(v, str) else 0


def _cmp(a, b):
    """-1/0/1 comparing two non-error values as Excel does (blank is 0, '' or FALSE as the other side needs)."""
    if a is None:
        a = '' if isinstance(b, str) else False if isinstance(b, bool) else 0
    if b is None:
        b = '' if isinstance(a, str) else False if isinstance(a, bool) else 0
    ka, kb = _kind(a), _kind(b)
    if ka != kb:
        return -1 if ka < kb else 1
    if ka == 1:
        a, b = a.lower(), b.lower()
    return (a > b) - (a < b)


class X:
    """One Excel value inside a formula. Arithmetic and comparisons follow Excel; .v is the raw value."""
    __slots__ = ('v',)

    def __init__(self, v):
        self.v = v.v if isinstance(v, X) else v

    def __repr__(self):
        return f'X({self.v!r})'

    def _op(self, o, f):
        a = _num(self.v)
        b = _num(o.v if isinstance(o, X) else o)
        if isinstance(a, str):
            return X(a)
        if isinstance(b, str):
            return X(b)
        try:
            return X(f(a, b))
        except ZeroDivisionError:
            return X(DIV0)
        except (OverflowError, ValueError):
            return X('#NUM!')

    def __add__(self, o): return self._op(o, lambda a, b: a + b)
    def __radd__(self, o): return X(o)._op(self, lambda a, b: a + b)
    def __sub__(self, o): return self._op(o, lambda a, b: a - b)
    def __rsub__(self, o): return X(o)._op(self, lambda a, b: a - b)
    def __mul__(self, o): return self._op(o, lambda a, b: a * b)
    def __rmul__(self, o): return X(o)._op(self, lambda a, b: a * b)
    def __truediv__(self, o): return self._op(o, lambda a, b: a / b)
    def __rtruediv__(self, o): return X(o)._op(self, lambda a, b: a / b)
    def __pow__(self, o): return self._op(o, _pow)
    def __rpow__(self, o): return X(o)._op(self, _pow)
    def __neg__(self): return X(0)._op(self, lambda a, b: -b)
    def __pos__(self): return self

    def _rel(self, o, test):
        a, b = self.v, (o.v if isinstance(o, X) else o)
        if iserr(a):
            return X(a)
        if iserr(b):
            return X(b)
        return X(test(_cmp(a, b)))

    def __lt__(self, o): return self._rel(o, lambda c: c < 0)
    def __le__(self, o): return self._rel(o, lambda c: c <= 0)
    def __gt__(self, o): return self._rel(o, lambda c: c > 0)
    def __ge__(self, o): return self._rel(o, lambda c: c >= 0)
    def __eq__(self, o): return self._rel(o, lambda c: c == 0)
    def __ne__(self, o): return self._rel(o, lambda c: c != 0)
    __hash__ = None

    def __bool__(self):
        raise TypeError('use IF()/truth() on an Excel value')

    @property
    def err(self):
        return iserr(self.v)


def _pow(a, b):
    if a == 0 and b < 0:
        raise ZeroDivisionError
    r = a ** b
    if isinstance(r, complex):
        raise ValueError
    return r


def val(x):
    """Raw value of an X (or of a plain value)."""
    return x.v if isinstance(x, X) else x


def out(x):
    """What a formula cell holds: a reference to a blank cell shows 0."""
    v = val(x)
    return 0 if v is None else v


def truth(c):
    """IF's view of a condition: True/False, or the error it carries (as a string)."""
    v = val(c)
    if iserr(v):
        return v
    if v is None:
        return False
    if isinstance(v, str):
        if v.upper() in ('TRUE', 'FALSE'):
            return v.upper() == 'TRUE'
        return VALUE
    return bool(v)


def IF(c, a, b=False):
    t = truth(c)
    if isinstance(t, str):
        return X(t)
    return X(a if t else b)


def IFL(c, fa, fb=lambda: False):
    """IF with lazily evaluated branches (pass functions)."""
    t = truth(c)
    if isinstance(t, str):
        return X(t)
    return X(fa() if t else fb())


def ISNUMBER(x):
    v = val(x)
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def ISERROR(x):
    return iserr(val(x))


def ISNA(x):
    return val(x) == NA


def ISBLANK(x):
    return val(x) is None


def IFERROR(x, alt):
    return X(alt) if iserr(val(x)) else X(x)


def NOT(x):
    t = truth(x)
    return X(t) if isinstance(t, str) else X(not t)


def AND(*cs):
    for c in cs:
        t = truth(c)
        if isinstance(t, str):
            return X(t)
    return X(all(truth(c) for c in cs))


def OR(*cs):
    for c in cs:
        t = truth(c)
        if isinstance(t, str):
            return X(t)
    return X(any(truth(c) for c in cs))


def _flat(vals):
    for v in vals:
        if isinstance(v, (list, tuple)):
            yield from _flat(v)
        else:
            yield val(v)


def _rangenums(vals):
    """Numbers of range arguments (text, blanks and logicals in ranges are skipped), or the first error."""
    xs = []
    for v in _flat(vals):
        if iserr(v):
            return v
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            xs.append(v)
    return xs


def SUM(*vals):
    xs = _rangenums(vals)
    return X(xs) if isinstance(xs, str) else X(sum(xs, 0.0))


def AVERAGE(*vals):
    xs = _rangenums(vals)
    if isinstance(xs, str):
        return X(xs)
    return X(sum(xs) / len(xs)) if xs else X(DIV0)


def MAX(*vals):
    xs = _rangenums(vals)
    return X(xs) if isinstance(xs, str) else X(max(xs) if xs else 0)


def MIN(*vals):
    xs = _rangenums(vals)
    return X(xs) if isinstance(xs, str) else X(min(xs) if xs else 0)


def NPV(rate, vals):
    """NPV(rate, range): values discounted from one period ahead; blanks, text and logicals in the range are
    skipped and do not count as periods."""
    r = _num(val(rate))
    if isinstance(r, str):
        return X(r)
    t, i = 0.0, 0
    for v in _flat(vals):
        if iserr(v):
            return X(v)
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            i += 1
            t += v / (1 + r) ** i
    return X(t)


def ROUND(x, d=0):
    v = _num(val(x))
    if isinstance(v, str):
        return X(v)
    m = 10 ** d
    return X(math.copysign(math.floor(abs(v) * m + 0.5) / m, v))


def ABS(x):
    v = _num(val(x))
    return X(v) if isinstance(v, str) else X(abs(v))


def CHOOSE(i, *opts):
    k = _num(val(i))
    if isinstance(k, str):
        return X(k)
    k = int(k)
    if k < 1 or k > len(opts):
        return X(VALUE)
    return X(opts[k - 1])


def MATCH(x, seq, kind=1):
    """MATCH over a list of raw values; 1-based position or #N/A."""
    x = val(x)
    if iserr(x):
        return X(x)
    if kind == 0:
        for i, v in enumerate(seq):
            v = val(v)
            if v is not None and not iserr(v) and _kind(v) == _kind(x) and _cmp(v, x) == 0:
                return X(i + 1)
        return X(NA)
    best = NA                          # approximate match: binary-search semantics on sorted data
    lo, hi = 0, len(seq) - 1
    while lo <= hi:
        mid = (lo + hi) // 2
        v = val(seq[mid])
        if v is None or iserr(v) or _kind(v) != _kind(x):
            # Excel skips over mismatched types; fall back to a linear scan
            return X(_match_linear(x, seq, kind))
        c = _cmp(v, x)
        if (kind == 1 and c <= 0) or (kind == -1 and c >= 0):
            best = mid + 1
            lo = mid + 1
        else:
            hi = mid - 1
    return X(best)


def _match_linear(x, seq, kind):
    best = NA
    for i, v in enumerate(seq):
        v = val(v)
        if v is None or iserr(v) or _kind(v) != _kind(x):
            continue
        c = _cmp(v, x)
        if (kind == 1 and c <= 0) or (kind == -1 and c >= 0):
            best = i + 1
        else:
            break
    return best


def text(v):
    """A value as Excel's & operator writes it."""
    v = val(v)
    if v is None:
        return ''
    if isinstance(v, bool):
        return 'TRUE' if v else 'FALSE'
    if isinstance(v, (int, float)):
        if float(v).is_integer() and abs(v) < 1e15:
            return str(int(v))
        return format(v, '.15g')
    return v


def CONCAT(*vals):
    for v in vals:
        if iserr(val(v)):
            return X(val(v))
    return X(''.join(text(v) for v in vals))


class G:
    """Cell access to one sheet as X values: g(r, c) with c a column index or letters, g.raw(r, c) the raw value,
    g.row(r, c0, c1) a list of raw values, g.col(c, r0, r1) likewise down a column."""

    def __init__(self, book, name):
        self.S = book[name]

    def __call__(self, r, c):
        if isinstance(c, str):
            c = ci(c)
        return X(self.S.cells.get((r, c)))

    def raw(self, r, c):
        if isinstance(c, str):
            c = ci(c)
        return self.S.cells.get((r, c))

    def row(self, r, c0, c1):
        if isinstance(c0, str):
            c0, c1 = ci(c0), ci(c1)
        g = self.S.cells.get
        return [g((r, c)) for c in range(c0, c1 + 1)]

    def col(self, c, r0, r1):
        if isinstance(c, str):
            c = ci(c)
        g = self.S.cells.get
        return [g((r, c)) for r in range(r0, r1 + 1)]

    def set(self, r, c, x):
        if isinstance(c, str):
            c = ci(c)
        self.S.cells[(r, c)] = out(x)


def cols(a, b):
    """Column indices a..b inclusive, from letters or numbers."""
    a = ci(a) if isinstance(a, str) else a
    b = ci(b) if isinstance(b, str) else b
    return range(a, b + 1)


class Table:
    """Exact-match VLOOKUP / MATCH over a fixed area, indexed once (text keys case-insensitive)."""

    def __init__(self, sheet, c0, r0, c1, r1, by_row=False):
        self.S, self.c0, self.r0, self.c1, self.r1 = sheet, c0, r0, c1, r1
        self.idx = {}
        keys = ([sheet.cells.get((r0, c)) for c in range(c0, c1 + 1)] if by_row else
                [sheet.cells.get((r, c0)) for r in range(r0, r1 + 1)])
        for i, k in enumerate(keys):
            if k is None or iserr(k):
                continue
            kk = k.lower() if isinstance(k, str) else (float(k) if not isinstance(k, bool) else k)
            self.idx.setdefault((isinstance(k, str), kk), i)

    def pos(self, key):
        """0-based position of key, or None."""
        key = val(key)
        if key is None:
            return None
        kk = key.lower() if isinstance(key, str) else (float(key) if not isinstance(key, bool) else key)
        return self.idx.get((isinstance(key, str), kk))

    def match(self, key):
        if iserr(val(key)):
            return X(val(key))
        p = self.pos(key)
        return X(NA) if p is None else X(p + 1)

    def vlookup(self, key, col):
        if iserr(val(key)):
            return X(val(key))
        col = val(col)
        if iserr(col):
            return X(col)
        p = self.pos(key)
        if p is None:
            return X(NA)
        if col < 1 or col > self.c1 - self.c0 + 1:
            return X('#REF!')
        return X(out(self.S.cells.get((self.r0 + p, self.c0 + int(col) - 1))))


def table(book, ref, by_row=False):
    sh, c0, r0, c1, r1 = book.area(ref)
    return Table(book[sh], c0, r0, c1, r1, by_row)


def tr(book, row, rows=None):
    """The template's language switch: translation!C/D/E/F<row> for English/French/Portuguese/other
    (START!L10). rows=(en, fr, pt, other) when the four languages read different rows."""
    lang = book['START'].get(10, ci('L'))
    en, fr, pt, ot = rows or (row, row, row, row)
    T = book['translation']
    if _eqs(lang, 'English'):
        v = T.get(en, 3)
    elif _eqs(lang, 'French'):
        v = T.get(fr, 4)
    elif _eqs(lang, 'Portuguese'):
        v = T.get(pt, 5)
    else:
        v = T.get(ot, 6)
    return 0 if v is None else v


def _eqs(a, b):
    return isinstance(a, str) and a.lower() == b.lower()


def num_or(x, alt):
    """IF(ISNUMBER(x), x, alt)."""
    return X(x) if ISNUMBER(x) else X(alt)


# ====================================================================== Macro-Debt_Data
H, T, U, AO = ci('H'), ci('T'), ci('U'), ci('AO')      # H:T historical 2011-2023, U:AO projections 2024-2044
I3 = 'Input 3 - Macro-Debt data(DMX)'                # column K holds 2011 (H + 3)
I5 = 'Input 5 - Local-debt Financing'                # column I holds 2024 (U - 12)

# column E labels from the translation sheet: row -> translation row (or (en, fr, pt, other) rows)
MD_LABELS = {
    6: 345, 7: 337, 8: 339, 9: 213, 10: 214, 11: 338, 14: 341, 15: (212, 213, 213, 213), 17: 350, 18: 351,
    19: 353, 20: 355, 21: 356, 22: 358, 23: 359, 24: 361, 25: 363, 26: 364, 28: 366, 29: 367, 30: 368, 31: 369,
    32: 370, 34: 371, 35: 372, 36: 373, 44: 374, 45: 375, 46: 376, 47: 377, 48: 378, 49: 379, 50: 380, 51: 381,
    52: 382, 53: 383, 54: 384, 56: 386, 57: 387, 58: 388, 59: 389, 60: 390, 66: 392, 68: 394, 69: 395, 70: 396,
    71: 397, 72: 410, 73: 411, 74: 412, 75: 413, 76: 414, 77: 424, 79: 398, 80: 340, 81: 343, 83: 344, 84: 399,
    86: 401, 87: 402, 88: 403, 89: 346, 90: 406, 91: 407, 92: 408, 95: 417, 96: 418, 97: 419, 98: 421, 99: 422,
    100: 423, 101: 415, 104: 420, 106: 425, 107: 426, 108: 427, 109: 428, 110: 429, 111: 430, 112: 431,
    113: 432, 114: 433,
}
# other translated labels: cell -> translation row
MD_OTHER_LABELS = {'B2': 67, 'B4': (193, 194, 193, 193), 'B5': 218, 'C5': 220, 'D5': 80, 'E5': 336, 'C6': 221,
                   'C14': 222, 'D58': 333, 'F116': 435}

# rows read straight from Input 3 in every year (IF(ISNUMBER(x), x, 0)): Macro-Debt_Data row -> Input 3 row
MD_INPUT3 = {12: 57, 13: 58, 20: 59, 25: 60, 28: 34, 29: 35, 30: 38, 31: 41, 32: 42, 34: 43, 35: 44, 36: 46,
             45: 22, 46: 23, 47: 27, 48: 24, 50: 25, 51: 28, 52: 30, 53: 29, 56: 12, 57: 13, 58: 18, 59: 19,
             60: 20, 61: 14, 62: 15, 63: 16, 64: 17, 91: 31}
# Input 3 ratios over all years (IF(ISNUMBER(a/b), a/b, 0)): row -> (numerator row, denominator row)
MD_RATIOS = {37: (36, 35), 38: (37, 35), 39: (39, 38), 40: (40, 38), 41: (39, 35), 42: (40, 35)}
# C/D unit labels: rows copying the US-dollar units (C6/D6) and the national-currency ones (C14/D6)
MD_USD_ROWS = [7, 8, 9, 10, 11, 12, 13, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 28, 29, 30, 31, 32, 34, 35, 36]
MD_LCU_ROWS = [15, 16, 44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 59, 60, 61, 62, 80, 81, 82, 83, 91]


def macro_debt_data(book):
    M = G(book, 'Macro-Debt_Data')
    In3, In5, E = G(book, I3), G(book, I5), G(book, 'Ext_Debt_Data')
    In1 = G(book, 'Input 1 - Basics')
    YEARS = cols(H, AO)
    i3 = lambda r, c: In3(r, c + 3)                   # Input 3, same year
    i5 = lambda r, c: In5(r, c - 12)                  # Input 5, same year (projections)
    ext = lambda r, c: E(r, c - 15)                   # Ext_Debt_Data, same year (projections)
    i3n = lambda r, c: num_or(i3(r, c), 0)            # IF(ISNUMBER(Input 3), Input 3, 0)

    # ---- labels
    for ref, row in MD_OTHER_LABELS.items():
        M.S[ref] = tr(book, row, row if isinstance(row, tuple) else None)
    for r, row in MD_LABELS.items():
        M.set(r, 'E', tr(book, row, row if isinstance(row, tuple) else None))
    M.set(85, 'E', book['translation'].get(400, 3))   # English only
    M.set(12, 'E', M(9, 'E'))
    M.set(13, 'E', M(10, 'E'))
    M.set(16, 'E', M(13, 'E'))
    M.set(105, 'E', M(54, 'E'))
    for r in (61, 62, 63, 64):                       # investment labels straight from Input 3
        M.set(r, 'E', In3(r - 47, 'B'))
    M.set(6, 'D', In1(19, 'C'))
    for r in MD_USD_ROWS:
        M.set(r, 'C', M(6, 'C'))
        M.set(r, 'D', M(6, 'D'))
    for r in MD_LCU_ROWS:
        M.set(r, 'C', M(14, 'C'))
        M.set(r, 'D', M(58 if r in (59, 60) else 6, 'D'))
    M.set(14, 'D', M(6, 'D'))
    for r in (54, 89, 95, 103):
        M.set(r, 'C', M(6, 'C'))
        M.set(r, 'D', M(6, 'D'))
    M.set(56, 'C', M(54, 'C'))
    M.set(56, 'D', M(6, 'D'))
    M.set(57, 'C', M(14, 'C'))
    M.set(57, 'D', M(6, 'D'))
    for r in (63, 64):
        M.set(r, 'C', In3(r - 47, 'F'))
        M.set(r, 'D', In3(r - 47, 'G'))
    M.set(66, 'C', M(5, 'C'))
    M.set(66, 'D', M(5, 'D'))

    # ---- year header: projection start year from Input 1, counted back and forward
    M.set(4, U, In1(18, 'C'))
    M.set(5, U, M(4, U))
    for c in range(U - 1, H - 1, -1):
        M.set(5, c, M(5, c + 1) - 1)
    for c in range(U + 1, AO + 1):
        M.set(5, c, M(5, c - 1) + 1)
    for c in YEARS:
        M.set(1, c, M(5, c))
        M.set(66, c, M(5, c))

    # ---- data read from Input 3 in all years
    for r, src in MD_INPUT3.items():
        for c in YEARS:
            M.set(r, c, i3n(src, c))
    for r, (a, b) in MD_RATIOS.items():
        for c in YEARS:
            M.set(r, c, num_or(i3(a, c) / i3(b, c), 0))

    for c in YEARS:
        hist = c <= T
        # PPG MLT external debt; historical years add the external debt of locally-issued debt (Input 3 row 208)
        if c < T:
            M.set(9, c, i3n(51, c) + i3(208, c))
        elif c == T:
            M.set(9, c, i3n(51, c) + i3(209, c))      # quirk: row 209
        else:
            M.set(9, c, ext(67, c) + ext(65, c) + ext(329, c))
        # PPG short-term external debt
        M.set(10, c, i3n(52, c) + i3(210, c) if hist else ext(386, c))
        # domestic debt (MLT, ST)
        M.set(15, c, i3n(191, c) if hist else i5(212, c))
        M.set(16, c, i3n(192, c) if hist else i5(213, c))
        # external debt service: interest on PPG external MLT
        M.set(19, c, i3n(53, c) + i3(211, c) if hist else ext(396, c))
        M.set(21, c, num_or(i3(193, c) / M(60, c), 0) if hist else i5(214, c) / M(60, c))
        # amortization
        M.set(24, c, i3n(54, c) + i3(212, c) if hist else ext(395, c))
        M.set(26, c, num_or(i3(195, c) / M(60, c), 0) if hist else (i5(215, c) - M(16, c - 1)) / M(60, c))
        # concessional loans
        M.set(54, c, i3n(32, c) if hist else ext(417, c))

    for c in YEARS:
        M.set(8, c, SUM(M(9, c), M(10, c)))                       # PPG external debt
        M.set(11, c, SUM(M(12, c), M(13, c)))                     # private external debt
        M.set(6, c, M(8, c) + M(11, c))                           # total external debt
        M.set(7, c, M(12, c) + M(9, c))                           # total MLT external debt
        M.set(14, c, M(15, c) + M(16, c))                         # domestic debt
        M.set(18, c, M(19, c) + M(20, c))                         # external interest
        M.set(23, c, M(24, c) + M(25, c))                         # external amortization
        M.set(44, c, M(45, c) - M(48, c))                         # primary balance
        M.set(49, c, (M(19, c) + M(21, c)) * M(60, c))            # interest in national currency
        M.set(81, c, M(8, c) * M(59, c))
        M.set(82, c, num_or(M(14, c), 0))
        M.set(80, c, num_or(M(81, c) + M(82, c), 0))              # public debt in national currency
        M.set(83, c, i3(214, c) * M(59, c) if c <= T else ext(399, c) * M(59, c))
        M.set(89, c, M(10, c) + M(13, c))                         # short-term external debt
        M.set(93, c, M(80, c) - M(50, c))
        M.set(95, c, num_or((M(45, c) - M(46, c)) / M(60, c), '…'))
        M.set(104, c, M(46, c) / M(60, c))
        M.set(105, c, M(54, c))
        M.set(103, c, SUM(M(104, c), M(105, c)))
        M.set(108, c, IF(ISNUMBER(M(56, c) * M(60, c) / M(57, c)), M(56, c) * M(60, c) / M(57, c) * 100, '…'))
        M.set(110, c, IF(ISNUMBER(M(56, c) / M(57, c)), M(56, c) / M(57, c) * 100, '…'))
        M.set(113, c, 1 / M(60, c))
        if c >= U:
            M.set(90, c, ext(408, c))
            M.set(101, c, i5(56, c))
        if c >= T:
            M.set(92, c, ext(391, c) * M(59, c))
        # PPG external debt of locally-issued debt held by non-residents, % of total external debt
        if eq_text(In1(33, 'C'), book['lookup'].get(4, ci('X'))):
            v = (i3(208, c) / M(6, c) * 100 if c <= T else
                 (((i5(166, c) + i5(203, c)) / M(59, c)) / M(6, c)) * 100)
        else:
            v = 0
        M.set(85, c, v)

    # ---- indicators
    for c in YEARS:
        p = c - 1                                                  # previous year (G is blank before 2011)
        M.set(70, c, num_or(M(11, c) / M(56, c) * 100, '…'))
        M.set(72, c, num_or((M(28, c) + M(18, c)) / M(56, c) * 100, '…'))
        M.set(73, c, num_or(M(32, c) / M(56, c) * 100, '…'))
        M.set(84, c, num_or(M(83, p) / (M(14, p) + M(8, p) * M(59, p)), '…'))
        M.set(86, c, IF(ISNUMBER(M(19, c) / M(8, p)), M(19, c) / M(8, p) * 100, '...'))
        M.set(87, c, IF(ISNUMBER(M(21, c) / M(14, p)), M(21, c) / M(14, p) * M(60, c) * 100, '...'))
        M.set(88, c, num_or((M(14, c) / M(59, c) + M(8, c)) /
                            (M(26, c) + M(24, c) + M(10, p) + M(16, p) / M(59, c)), '…'))
        M.set(96, c, num_or(M(45, c) / M(108, c) * 100, '…'))
        M.set(98, c, num_or(M(95, c) / M(56, c) * 100, '…'))
        M.set(99, c, num_or(M(48, c) / M(108, c) * 100, '…'))
        if c == H:                                                 # 2011: refers back to column E (labels)
            e = ci('E')
            M.set(71, c, num_or((M(25, c) + M(20, c)) / M(29, c) * 100, '…'))
            M.set(74, c, num_or(-M(28, c) - M(34, c) + M(23, c) + M(89, e), '...'))
            M.set(75, c, num_or(M(12, c) - M(11, e) + M(25, c) + M(13, e), '...'))
            p = e
        else:
            M.set(69, c, num_or(M(18, c) / (M(8, p) + M(11, p)) * 100, '...'))
            M.set(71, c, num_or((M(25, c) + M(20, c) + M(13, p)) / M(29, c) * 100, '…'))
            M.set(74, c, num_or(-M(28, c) - M(34, c) + M(23, c) + M(89, p), '...'))
            M.set(75, c, num_or(M(12, c) - M(12, p) + M(25, c) + M(13, c), '...'))
            M.set(100, c, IF(ISNUMBER(M(99, c) / M(99, p) - 1), (M(99, c) / M(99, p) - 1) * 100, '…'))
            M.set(107, c, num_or((M(57, c) / M(57, p) - 1) * 100, '…'))
            M.set(112, c, IF(ISNUMBER(M(58, p)), (M(58, c) / M(58, p) - 1) * 100, '...'))
            if c <= T:
                M.set(101, c, num_or(-M(44, c) + (M(19, c) + M(21, c) + M(26, c) + M(10, p) + M(24, c)) * M(60, c)
                                     + M(16, p) + (M(51, c) + M(52, c)) - (M(47, c) + M(53, c)), '…'))
        # growth rates against the previous year (2011: against column E)
        M.set(97, c, IF(ISNUMBER(M(96, p)), (M(96, c) / M(96, p) - 1) * 100, '...'))
        M.set(109, c, IF(ISNUMBER(M(108, p)), (M(108, c) / M(108, p) - 1) * 100, '...'))
        M.set(111, c, IF(ISNUMBER(M(110, p)), (M(110, c) / M(110, p) - 1) * 100, '...'))
        M.set(114, c, num_or(-100 * (M(113, c) / M(113, p) - 1), '...'))
        M.set(76, c, num_or(M(74, c) - M(75, c), '...'))
        if c >= U:
            M.set(77, c, M(76, c) - M(10, c) - ext(122, c))


def eq_text(a, b):
    """Excel a=b on two raw cell values (True/False; errors count as not equal)."""
    t = X(val(a)) == X(val(b))
    return t.v is True


# ====================================================================== Dom_Debt_Data
D_, O_, AI_ = ci('D'), ci('O'), ci('AI')               # D:AI years 2013-2044, O = first projection year
DOM_MSG = ('Can not find required variable. Please check and change variable name in ""{}"" sheet.'
           .replace('""', '"'))
# variable rows: row -> (source sheet, lookup area, header row of the area)
DOM_LOOKUPS = {
    11: ('Baseline - public', 'B', 'CZ', 7), 12: ('Baseline - public', 'B', 'CZ', 7),
    17: ('Baseline - public', 'B', 'CZ', 7), 18: ('Baseline - external', 'B', 'CZ', 8),
    19: ('Macro-Debt_Data', 'E', 'CZ', 5), 20: ('Macro-Debt_Data', 'E', 'CZ', 5),
    26: ('Macro-Debt_Data', 'E', 'AO', 5), 29: ('Macro-Debt_Data', 'E', 'AO', 5),
    31: ('Macro-Debt_Data', 'E', 'AO', 5), 32: ('Macro-Debt_Data', 'E', 'AO', 5),
}


def dom_debt_data(book):
    D = G(book, 'Dom_Debt_Data')
    YEARS = cols(D_, AI_)
    D.set(2, 'D', VALUE)                     # file name from CELL("filename"): #VALUE! in the template
    D.set(6, 'F', VALUE)                     # INDIRECT into the file by name: #VALUE! in the template
    # year header
    D.set(7, O_, G(book, 'Input 1 - Basics')(18, 'C'))
    for c in range(O_ - 1, D_ - 1, -1):
        D.set(7, c, D(7, c + 1) - 1)
    for c in range(O_ + 1, AI_ + 1):
        D.set(7, c, D(7, c - 1) + 1)
    D.set(7, 'AP', CONCAT(D(7, O_), ' - ', D(7, AI_)))

    # variables looked up by name (column C) in the baseline sheets and Macro-Debt_Data; the interest due
    # (row 29) is converted at the exchange rate of row 32, so row 32 is looked up first
    tables = {}
    for r in sorted(DOM_LOOKUPS, key=lambda r: r == 29):
        sh, a, b, hdr = DOM_LOOKUPS[r]
        if (sh, a, b) not in tables:
            tables[(sh, a, b)] = table(book, f"'{sh}'!${a}$1:${b}$1000")
        tab = tables[(sh, a, b)]
        name = D(r, 'C')
        D.set(r, 'A', IFERROR(tab.vlookup(name, 1), DOM_MSG.format(sh)))
        heads = G(book, sh).row(hdr, a, b)
        for c in YEARS:
            v = tab.vlookup(name, MATCH(D(7, c), heads, 0))
            D.set(r, c, IFERROR(v * D(32, c) if r == 29 else v, NA))
    for c in YEARS:
        D.set(33, c, D(31, c) * D(32, c))                    # nominal GDP in national currency
        # domestic debt / GDP: public debt less PPG external, floored at 0
        x = D(11, c) - D(12, c)
        D.set(10, c, IFERROR(IF(x < 0, 0, x), NA))
        # domestic debt service / revenue incl. grants
        x = D(17, c) - D(18, c) * (D(19, c) - D(20, c)) / D(19, c)
        D.set(16, c, IFERROR(IF(x < 0, 0, x), NA))
    for c in range(D_ + 1, AI_ + 1):
        D.set(14, c, D(14, c - 1))                           # LIC DSF medians, carried across
        D.set(22, c, D(22, c - 1))
        D.set(28, c, D(26, c) + D(27, c) - D(26, c - 1) - D(27, c - 1))   # change in domestic debt
        x = 100 * (D(28, c) - D(29, c) - D(30, c)) / D(33, c)
        D.set(25, c, NA if ISERROR(x) else x)                # net domestic issuance / GDP
    for c in range(D_ + 1, AI_ + 1):
        x = 100 * D(25, c) / D(10, c - 1)
        D.set(34, c, NA if ISERROR(x) else x)                # net issuance / previous domestic debt
    for r in (10, 16):                                       # period averages
        D.set(r, 'AL', AVERAGE(D.row(r, 'E', 'N')))
        D.set(r, 'AM', AVERAGE(D.row(r, 'O', 'S')))
        D.set(r, 'AN', AVERAGE(D.row(r, 'T', 'AI')))
        D.set(r, 'AP', AVERAGE(D.row(r, 'O', 'AI')))


# ====================================================================== DMX_OUT
# rows copied from Input 5 over P:AK: DMX_OUT row -> (Input 5 row, Input 5 column for P)
DMX_COPIES = {8: (10, 'I'), 10: (12, 'I'), 11: (13, 'I'), 14: (16, 'I'), 15: (17, 'I'), 16: (18, 'I'),
              18: (20, 'I'), 19: (21, 'I'), 20: (22, 'I'), 24: (27, 'I'), 25: (28, 'I'), 28: (31, 'I'),
              29: (32, 'I'), 30: (33, 'I'), 32: (35, 'I'), 33: (36, 'I'), 34: (37, 'I')}
DMX_COPIES.update({r: (src, 'H') for r, src in {
    36: 40, 38: 42, 39: 43, 40: 44, 42: 47, 43: 48, 44: 49, 46: 52, 48: 54, 50: 56, 51: 58, 52: 60, 53: 61,
    54: 64, 60: 79, 62: 81, 64: 83, 65: 84, 66: 85, 67: 86, 68: 87, 69: 88, 70: 89, 71: 90, 72: 91, 73: 92,
    74: 93, 75: 94, 76: 95, 78: 97, 80: 99, 81: 100, 82: 101, 83: 102, 84: 103, 85: 104, 86: 105, 87: 106,
    88: 107, 89: 108, 90: 109, 91: 110, 93: 112, 95: 117, 96: 118, 97: 119, 102: 128, 103: 129, 104: 130,
    105: 131, 106: 132, 109: 135, 110: 136, 111: 137, 113: 139, 114: 140, 116: 142, 117: 143, 118: 144,
    119: 145, 121: 147, 122: 148, 124: 150, 125: 151, 126: 152, 127: 153, 130: 156, 131: 157, 132: 158,
    133: 159, 134: 160, 135: 161, 136: 162, 137: 163, 140: 166, 141: 167, 144: 170, 145: 171, 147: 173,
    148: 174, 149: 175, 150: 176, 151: 177, 153: 179, 154: 180, 155: 181, 156: 182, 158: 184, 159: 185,
    160: 186, 161: 187, 163: 190, 164: 192, 166: 195, 167: 196, 168: 197, 169: 198, 170: 199, 171: 200,
    173: 203, 174: 205, 176: 208, 177: 209, 178: 210, 179: 211, 180: 212, 181: 213, 182: 214, 183: 215,
    185: 217, 186: 218, 187: 219, 188: 220}.items()})
# descriptor (column D) copied from Input 5 column A: DMX_OUT row -> Input 5 row
DMX_DESCR = {8: 10, 10: 12, 11: 13, 14: 16, 15: 17, 16: 18, 18: 20, 19: 21, 20: 22, 24: 27, 25: 28, 28: 31,
             29: 32, 30: 33, 32: 35, 33: 36, 34: 37, 62: 81, 78: 97, 114: 140, 117: 143, 125: 151, 135: 161,
             145: 171, 148: 174, 159: 185, 168: 197, 177: 209}
DMX_NO_PATH = {133}                                       # rows without the file-path copy in column C


def dmx_out(book):
    X_ = G(book, 'DMX_OUT')
    In5 = G(book, I5)
    P, AK = ci('P'), ci('AK')
    # year header and DMX period codes
    X_.set(5, P, In5(5, 'H'))
    for c in range(P - 1, ci('E') - 1, -1):
        X_.set(5, c, X_(5, c + 1) - 1)
    for c in range(P + 1, AK + 1):
        X_.set(5, c, X_(5, c - 1) + 1)
    for c in cols('E', 'AK'):
        X_.set(6, c, CONCAT(X_(5, c), 'A1'))
    # series copied from Input 5
    for r, (src, c0) in DMX_COPIES.items():
        if r not in DMX_NO_PATH:
            X_.set(r, 'C', X_(4, 'B'))
        off = ci(c0) - P
        for c in range(P, AK + 1):
            X_.set(r, c, In5(src, c + off))
    for r, src in DMX_DESCR.items():
        X_.set(r, 'D', In5(src, 'A'))
    # domestic debt stock: 2023 from row 76, projections from row 77
    X_.set(58, 'C', X_(4, 'B'))
    X_.set(58, P, In5(76, 'H'))
    for c in range(P + 1, AK + 1):
        X_.set(58, c, In5(77, c - P + ci('H')))
    # section labels in column A
    X_.set(59, 'A', In5(78, 'A'))
    for r in range(62, 77):
        if r != 63:
            X_.set(r, 'A', X_(59, 'A'))
    X_.set(78, 'A', In5(98, 'A'))
    for r in range(80, 92):
        X_.set(r, 'A', X_(78, 'A'))
    X_.set(94, 'A', In5(116, 'B'))
    for r in (102, 103, 104, 105, 106):
        X_.set(r, 'A', X_(101, 'A'))
    for r in (109, 110, 111):
        X_.set(r, 'A', X_(108, 'A'))


def compute(book, sheet):
    {'Macro-Debt_Data': macro_debt_data, 'Dom_Debt_Data': dom_debt_data, 'DMX_OUT': dmx_out}[sheet](book)
