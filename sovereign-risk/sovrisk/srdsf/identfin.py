"""IdentFin sheet: identified financing, projected instrument by instrument.

The sheet holds one block of 175 rows per financing instrument (six in the template, each starting where column D
holds an 'X': rows 7, 182, 357, ...). Each block reads the instrument's assumptions from the financing part of
Macrofw (amount issued per year, interest rate, currency, frequency, grace, maturity, creditor shares) and then works
issuance vintage by vintage: for each of the 16 issuance years U..AJ one row in each of nine triangles (applicable
interest rate, share still outstanding, issuance-equation terms, debt stock, amortization, interest, contribution to
the effective interest rate, interest base) over the 83 projection years U..CY, plus the debt stock split by creditor
(columns DD..HC). Totals across instruments come from ResidFin and from the other IdentFin blocks (SUMIF/SUMIFS
over whole columns), so the blocks are filled in three passes.

All array formulas on this sheet are single-cell SWITCH formulas over scalars, so array semantics change nothing.
"""
from .xl import NA, VALUE, DIV0, average, eq, err, iserr, isnumber, xsum

SHEETS = ['IdentFin']

QUIRKS = [
    "Row 'share of debt still outstanding' (block row 38, e.g. AJ45:CY45) for the first vintage sums the "
    "amortization schedule up to the CURRENT column from AJ onwards (=1-SUM($U26:AJ26)), while V45:AI45 and all "
    "other vintages stop one column before (=1-SUM($U26:U26) in V45). Reproduced.",
    "The interest part of the issuance equation for the last vintage (block row 70, e.g. AJ77:CY77) uses the "
    "issuance amount and exchange rate of the previous year ($AI8, $AI10) instead of its own ($AJ8, $AJ10). "
    "Reproduced.",
    "A9 builds its label from C8 instead of C9 (same value, as only block heads carry the 'X').",
    "The fifth creditor group of the debt-stock split sits at GM (one column closer than the 22-column stride "
    "of DD, DZ, EV, FR); harmless, reproduced by listing the label columns.",
    "Issuance after AJ (AK:CY of the issuance row) is set to 0.000001 when blank/zero so the share-of-issuance "
    "row never divides by zero.",
]

U, CY, AJ = 21, 103, 36                 # year columns: U..CY all projection years, U..AJ the 16 issuance years
YEARS = range(U, CY + 1)
NV = 16                                 # vintages per triangle
STRIDE = 175                            # rows per instrument block
CRED_COLS = [108, 130, 152, 174, 195]   # DD, DZ, EV, FR, GM: creditor share column, then 16 years of stock
CRED_ROWS = range(5, 10)                # block rows 5-9 (rows 12-16): creditor shares from Macrofw

# block-relative rows (block head = 0)
CURR, IRATE, ERATE, FREQ, GRACE, MAT, PERIM, LINK = 1, 2, 3, 4, 5, 6, 7, 8
CUSTOM, ISS, ISHARE, CONT_IRT, CONT_IRC, YRS = 10, 12, 13, 14, 15, 16
SEMI_INT, SEMI_AMORT, AMORT = 17, 18, 19
FI, GGDR_PCT, ISS_INT, ISS_AMT, GGD, GGFA, GGEI, EFF_IR, INT_BASE = 21, 38, 55, 72, 89, 106, 123, 140, 157
TRIANGLES = (FI, GGDR_PCT, ISS_INT, ISS_AMT, GGD, GGFA, GGEI, EFF_IR, INT_BASE)
END = 173
HEAD_SUFFIX = ['-HEAD', '-CURR_IS', '-ITYP-IR', '-MKTY-ER', '-FQ-X1', '-GP-SHDC', '-MY-SHDB', '-PR-SHDN',
               '-LRSHXO', '-X2-SHXP', '-X3-CA', '-X4-PJ', '-ISSUANCE', '-ISHARE', '-CONT_IRT', '-CONT_IRC',
               '-YRSPOST', '-SEMIANN_INT', '-SEMIANN_AMORT', '-AMORT_SCH']


# ---- Excel helpers local to this sheet ---------------------------------------------------------------------------

def ref(v):
    """A formula that just points at a cell: blank comes back as 0."""
    return 0 if v is None else v


def text(v):
    """Value as the & operator renders it."""
    if v is None:
        return ''
    if isinstance(v, bool):
        return 'TRUE' if v else 'FALSE'
    if isinstance(v, float):
        if v == int(v) and abs(v) < 1e15:
            return str(int(v))
        return f'{v:.15g}'
    return str(v)


def cat(*vals):
    e = err(*vals)
    return e if e else ''.join(text(v) for v in vals)


def n(v):
    """Operand of arithmetic: blank -> 0, bool -> 0/1, text -> None (#VALUE!), errors returned as they are."""
    if v is None:
        return 0
    if isinstance(v, bool):
        return int(v)
    if isinstance(v, str):
        return v if iserr(v) else None
    return v


def mul(*vals):
    p = 1
    for v in vals:
        x = n(v)
        if x is None:
            return VALUE
        if isinstance(x, str):
            return x
        p *= x
    return p


def ar(f, *vals):
    """f over numeric operands with Excel error propagation."""
    xs = []
    for v in vals:
        x = n(v)
        if x is None:
            return VALUE
        if isinstance(x, str):
            return x
        xs.append(x)
    try:
        return f(*xs)
    except ZeroDivisionError:
        return DIV0


def xdiv(a, b):
    return ar(lambda a, b: a / b, a, b)


def _rank(v):
    return 0 if isinstance(v, (int, float)) and not isinstance(v, bool) else (1 if isinstance(v, str) else 2)


def cmp(a, b):
    """Excel comparison: -1/0/1, or the error. Blank compares as 0 or ''."""
    e = err(a, b)
    if e:
        return e
    if a is None:
        a = '' if isinstance(b, str) else 0
    if b is None:
        b = '' if isinstance(a, str) else 0
    ra, rb = _rank(a), _rank(b)
    if ra != rb:
        return -1 if ra < rb else 1
    if ra == 1:
        a, b = a.lower(), b.lower()
    return (a > b) - (a < b)


def xeq(a, b):
    e = err(a, b)
    return e if e else eq(a, b)


def le(a, b):
    c = cmp(a, b)
    return c if isinstance(c, str) else c <= 0


def gt(a, b):
    c = cmp(a, b)
    return c if isinstance(c, str) else c > 0


def truth(v):
    """IF/AND/OR condition: True/False, or an error string."""
    if iserr(v):
        return v
    if isinstance(v, str):
        return VALUE
    return bool(n(v))


def xand(*vals):
    t = [truth(v) for v in vals]
    e = err(*t)
    return e if e else all(t)


def xor_(*vals):
    t = [truth(v) for v in vals]
    e = err(*t)
    return e if e else any(t)


def xif(cond, yes, no):
    """IF with lazy branches (yes/no are thunks)."""
    t = truth(cond)
    if isinstance(t, str):
        return t
    return yes() if t else no()


def switch(v, *pairs):
    """SWITCH(v, k1, r1, k2, r2, ...[, default]); results are thunks, no match and no default -> #N/A."""
    if iserr(v):
        return v
    for i in range(0, len(pairs) - 1, 2):
        if eq(v, pairs[i]):
            return pairs[i + 1]()
    return pairs[-1]() if len(pairs) % 2 else NA


class Lookup:
    """VLOOKUP(key, <whole-row range of a sheet>, col, FALSE), keys indexed once per compute."""

    def __init__(self, sheet, r0, r1):
        self.S = sheet
        self.rows = {}
        for r in range(r1, r0 - 1, -1):           # first match wins
            k = sheet.get(r, 1)
            if k is not None:
                self.rows[k.lower() if isinstance(k, str) else k] = r

    def __call__(self, key, col):
        e = err(key, col)
        if e:
            return e
        if not isnumber(col) or col < 1:
            return VALUE
        r = self.rows.get(key.lower() if isinstance(key, str) else key)
        if r is None:
            return NA
        return ref(self.S.get(r, int(col)))


class ColSums:
    """SUMIF/SUMIFS over whole columns of IdentFin and ResidFin: rows grouped once by the criteria columns."""

    def __init__(self, sheets, key):
        self.groups = []                              # per sheet: {criteria key: [rows]}
        for S in sheets:
            g = {}
            for r in sorted({r for (r, _c) in S.cells}):
                k = key(S, r)
                if k is not None:
                    g.setdefault(k, []).append(r)
            self.groups.append((S, g))

    def total(self, k, col):
        t = 0.0
        for S, g in self.groups:
            for r in g.get(k, ()):
                v = S.get(r, col)
                if iserr(v):
                    return v
                if isnumber(v):
                    t += v
        return t


def _crit(v):
    """Criterion key for "="&v as SUMIFS matches it (text case-insensitive, numbers by value)."""
    if isinstance(v, bool):
        return ('b', v)
    if isinstance(v, (int, float)):
        return ('n', float(v))
    if v is None:
        return ('t', '')
    return ('t', v.lower())


# ---- the sheet ---------------------------------------------------------------------------------------------------

def compute(book, sheet='IdentFin'):
    S = book['IdentFin']
    R = book['ResidFin']
    M = book['Macrofw']
    proj = book.name('ProjYr')
    fin = Lookup(M, 157, 313)                     # FinancingIn = Macrofw!$157:$313
    mdata = Lookup(M, 5, 134)                     # MacrofwData = Macrofw!$5:$134
    dates = {}                                    # MacrofwDates = Macrofw!$5:$5
    for (r, c), v in M.cells.items():
        if r == 5 and v is not None and not isinstance(v, str):
            if v not in dates or c < dates[v]:
                dates[v] = c

    # header: years, Macrofw column of each year
    for c in YEARS:
        S.set(3, c, ar(lambda p, y: p + y, proj, S.get(4, c)))
        y = S.get(4, c)
        S.set(5, c, dates.get(y, NA) if not iserr(y) else y)
    for lc in CRED_COLS:
        for i in range(NV):
            S.set(3, lc + 1 + i, ref(S.get(3, U + i)))

    # instrument blocks: column D has an 'X' at each block head; C counts them (COUNTIF(D$1:Dr,"=X")+$C$6)
    maxr = max(r for r, _ in S.cells)
    heads = [r for r in range(1, maxr + 1) if eq(S.get(r, 4), 'X')]
    c6 = n(S.get(6, 3))
    for i, b in enumerate(heads):
        for r in range(b, b + END + 1):
            S.set(r, 3, i + 1 + c6)
    ccount = sum(1 for (r, c), v in S.cells.items() if c == 3 and isnumber(v))
    in_first = sum(1 for r in range(7, 181) if isnumber(S.get(r, 3)))
    S.set(5, 14, xdiv(ccount, in_first))                                  # number of instruments
    S.set(5, 15, ar(lambda a, b, d: (a + 1) * b / d + 7, in_first, ccount, in_first))  # next instrument start

    for b in heads:
        _assumptions(S, b, fin, mdata)
    iss = ColSums([S, R], lambda X, r: 'iss' if eq(X.get(r, 2), 'Issuance') else None)
    iss_cur = ColSums([S, R], lambda X, r: _crit(X.get(r, 11)) if eq(X.get(r, 2), 'Issuance') else None)
    for b in heads:
        _shares(S, b, iss, iss_cur)
        _schedule(S, b, proj)
        _triangles(S, b)
    base = ColSums([S, R], lambda X, r: (_crit(X.get(r, 7)), _crit(X.get(r, 11)))
                   if eq(X.get(r, 17), 'INT_BASE') else None)
    for b in heads:
        _effective_rate(S, b, base)


def _assumptions(S, b, fin, mdata):
    """Block rows 0-19: labels, the instrument's assumptions from FinancingIn / MacrofwData, issuance."""
    g = S.get
    c_ = g(b, 3)
    S.set(b, 2, cat('INST', c_))                                            # B: instrument code
    S.set(b + 1, 2, cat(g(b, 2), '_A'))
    S.set(b + 2, 2, cat(g(b, 2), '_I'))
    for o, suf in enumerate(HEAD_SUFFIX):                                   # A: row keys
        S.set(b + o, 1, cat(g(b + (o if o != IRATE else CURR), 3), suf))   # A9 uses C8
    code = g(b, 2)
    S.set(b, 17, cat('Instrument ', code[4:] if not iserr(code) else code))  # RIGHT(B,LEN(B)-4)
    S.set(b + FREQ, 19, cat('Percent of ', g(b, 17), ' allocated to:'))

    col_r = g(5, U)                                                         # U$5 seen from column R
    cur = fin(cat(code, '_C'), col_r)
    S.set(b + CURR, 18, xif(xeq(cur, 1), lambda: 'Local', lambda: xif(xeq(cur, 2), lambda: 'Foreign',
          lambda: xif(xeq(cur, 3), lambda: 'Local-Linked 1', lambda: 'Local-Linked 2'))))
    fq = fin(cat(code, '_F'), col_r)
    S.set(b + FREQ, 18, xif(xeq(fq, 0.5), lambda: 'Semiannual', lambda: 'Annual'))
    S.set(b + GRACE, 18, fin(cat(code, '_G'), col_r))
    S.set(b + MAT, 18, fin(cat(code, '_M'), col_r))
    cr = g(b + CURR, 18)
    S.set(b + LINK, 18, xif(xeq(cr, 'Local-Linked 1'), lambda: 'LLI1',
                            lambda: xif(xeq(cr, 'Local-Linked 2'), lambda: 'LLI2', lambda: 'n.a.')))

    for c in range(U, AJ + 1):
        k = g(5, c)
        S.set(b + CURR, c, fin(g(b + CURR, 2), k))                          # amount of debt issued
        S.set(b + IRATE, c, fin(g(b + IRATE, 2), k))                        # interest rate
        # applicable exchange rate
        S.set(b + ERATE, c, xif(xeq(cr, 'Local'), lambda: 1, lambda: xif(xeq(cr, 'Foreign'),
              lambda: mdata('ENDA', k), lambda: xif(xor_(xeq(cr, 'Local-Linked 1'), xeq(cr, 'Local-Linked 2')),
                                                    lambda: mdata(g(b + LINK, 18), k), lambda: NA))))
    for c in range(AJ + 1, CY + 1):
        S.set(b + ERATE, c, ref(g(b + ERATE, c - 1)))
    for o in CRED_ROWS:                                                     # creditor shares, issuance year
        S.set(b + o, U, mdata(g(b + o, 2), ar(lambda k: k - 1, g(5, U))))
        for c in range(U + 1, AJ + 1):
            S.set(b + o, c, ref(g(b + o, c - 1)))

    # debt issued (tiny placeholder after AJ so shares never divide by zero)
    S.set(b + ISS, 11, ref(cr))
    S.set(b + CONT_IRC, 11, ref(cr))
    for c in range(U, AJ + 1):
        S.set(b + ISS, c, ref(g(b + CURR, c)))
    for c in range(AJ + 1, CY + 1):
        a = g(b + CURR, c)
        S.set(b + ISS, c, xif(xeq(a, 0), lambda: 0.000001, lambda: ref(a)))


def _shares(S, b, iss, iss_cur):
    """Block rows 13-15: share of total issuance, contributions to the marginal effective interest rate."""
    g = S.get
    k_cur = _crit(g(b + CONT_IRC, 11))
    for c in YEARS:
        S.set(b + ISHARE, c, ar(lambda a, t: a / t, g(b + ISS, c), iss.total('iss', c)))
    for c in range(U, AJ + 1):
        S.set(b + CONT_IRT, c, mul(g(b + IRATE, c), g(b + ISHARE, c)))
        S.set(b + CONT_IRC, c, ar(lambda i, a, t: i * a / t, g(b + IRATE, c), g(b + ISS, c),
                                  iss_cur.total(k_cur, c)))


def _schedule(S, b, proj):
    """Block rows 17-19: semiannual adjustments and the amortization schedule; E..P labels of each vintage row."""
    g = S.get
    freq = g(b + FREQ, 18)
    for o in [SEMI_INT, SEMI_AMORT, AMORT] + [t + k for t in TRIANGLES for k in range(NV)]:
        r = b + o
        S.set(r, 5, ref(g(b + GRACE, 18)))                                  # E grace
        S.set(r, 6, ref(g(b + MAT, 18)))                                    # F maturity
        S.set(r, 15, switch(freq, 'Semiannual', lambda: 0.5, 'Annual', lambda: 1, 'Custom', lambda: 1))
        e_, f_ = g(r, 5), g(r, 6)
        S.set(r, 16, xif(xeq(freq, 'Custom'), lambda: 'Custom', lambda: xif(
            xeq(g(b + IRATE, 18), 'Zero-coupon'), lambda: 'Zero-coupon',
            lambda: xif(xeq(e_, f_), lambda: 'Bullet', lambda: 'Amortizing'))))
    E, F, O, P = (g(b + SEMI_INT, c) for c in (5, 6, 15, 16))
    for c in YEARS:
        y = g(b + YRS, c)
        # semiannual adjustment, interest
        S.set(b + SEMI_INT, c, xif(xand(xeq(O, 0.5), xeq(y, 0)), lambda: 0.5,
                                   lambda: xif(xand(gt(y, 0), le(y, F)), lambda: 1, lambda: 0)))
        # semiannual adjustment, amortization
        S.set(b + SEMI_AMORT, c, xif(xand(xeq(O, 0.5), xor_(xeq(y, E), xeq(y, F))), lambda: 0.5,
                                     lambda: xif(xand(gt(y, E), le(y, F)), lambda: 1, lambda: 0)))
        # amortization schedule
        t = g(4, c)
        S.set(b + AMORT, c, switch(
            P, 'Bullet', lambda: xif(xeq(F, t), lambda: 1, lambda: 0),
            'Amortizing', lambda: ar(lambda f, e, s: 1 / (f - e) * s, F, E, g(b + SEMI_AMORT, c)),
            'Zero-coupon', lambda: xif(xeq(t, F), lambda: 1, lambda: 0),
            'Custom', lambda: ref(g(b + CUSTOM, c))))

    # per-vintage labels (columns A, B, G..N) of the nine triangles
    committed = switch(g(b + CUSTOM, 18), 'Yes', lambda: 'Committed', 'No', lambda: 'Uncommitted',
                       lambda: 'Not given')
    for t in TRIANGLES:
        for k in range(NV):
            r = b + t + k
            S.set(r, 2, committed)
            S.set(r, 7, ar(lambda p, d: p + d, proj, g(r, 4)))             # G issuance year
            S.set(r, 8, ar(lambda a, e: a + e, g(r, 7), g(r, 5)))           # H end of grace
            S.set(r, 9, ar(lambda a, f: a + f, g(r, 7), g(r, 6)))           # I maturity year
            S.set(r, 10, ref(g(b + ERATE, U + k)))                          # J exchange rate at issuance
            S.set(r, 11, ref(g(b + CURR, 18)))                              # K currency
            S.set(r, 12, ref(g(b + ERATE, 18)))                             # L marketability
            S.set(r, 13, ref(g(b + IRATE, 18)))                             # M interest type
            S.set(r, 14, ref(g(b + PERIM, 18)))                             # N perimeter
    S.set(b + END, 17, cat('End of instrument ', g(b + END, 3)))
    for o in range(FI - 1, END + 1):
        r = b + o
        S.set(r, 1, cat(g(r, 17), '_', g(r, 3), '_', g(r, 4)))


def _triangles(S, b):
    """The vintage triangles: row k is debt issued in year U+k, followed over the projection years."""
    g = S.get
    row = lambda o, c: g(b + o, c)
    for k in range(NV):
        u = U + k                                                           # issuance column
        r_fi, r_pct, r_int, r_amt = b + FI + k, b + GGDR_PCT + k, b + ISS_INT + k, b + ISS_AMT + k
        r_ggd, r_fa, r_ei, r_base = b + GGD + k, b + GGFA + k, b + GGEI + k, b + INT_BASE + k
        mtype, mat_yr, mat = g(r_fi, 13), g(r_fi, 9), g(r_fi, 6)
        rate0 = row(IRATE, u)
        for c in range(u, CY + 1):
            # applicable interest rate x semiannual adjustment
            yr = g(3, c)
            rate = switch(mtype, 'Fixed', lambda: ref(rate0), 'Floating', lambda: ref(row(IRATE, c)),
                          'Zero-coupon', lambda: xif(xeq(yr, mat_yr),
                                                     lambda: ar(lambda i, m: (1 + i) ** m - 1, rate0, mat),
                                                     lambda: 0))
            S.set(r_fi, c, mul(rate, row(SEMI_INT, c - k)))
            # share of the vintage still outstanding at the start of the year (QUIRKS: first vintage from AJ)
            if c > u:
                end = c if (k == 0 and c >= AJ) else c - 1 - k
                S.set(r_pct, c, ar(lambda s: 1 - s, xsum(row(AMORT, j) for j in range(U, end + 1))))
            # issuance equation terms (QUIRKS: last vintage reads the previous year's amount and rate)
            ui = u - 1 if k == NV - 1 else u
            S.set(r_int, c, ar(lambda a, x, f, s, x0: a * x * f * s / x0, row(CURR, ui), row(ERATE, c),
                               g(r_fi, c), g(r_pct, c), row(ERATE, ui)))
            S.set(r_amt, c, ar(lambda a, x, m, x0: a * x * m / x0, row(CURR, u), row(ERATE, c),
                               row(AMORT, c - k), row(ERATE, u)))
        # debt stock: issued amount in instrument currency, less amortization
        S.set(r_ggd, u, xdiv(row(ISS, u), row(ERATE, u)))
        stock0 = g(r_ggd, u)
        for c in range(u, CY + 1):
            S.set(r_fa, c, mul(row(AMORT, c - k), stock0))
        for c in range(u + 1, CY + 1):
            S.set(r_ggd, c, ar(lambda p, a: p - a, g(r_ggd, c - 1), g(r_fa, c)))
        # interest: rate x issued amount in the issuance year, then x stock (start-of-year, or mid-year average)
        S.set(r_ei, u, mul(g(r_fi, u), g(r_ggd, u)))
        S.set(r_base, u, ref(g(r_ggd, u)))
        semi = g(r_ei, 15)
        for c in range(u + 1, CY + 1):
            prev, cur = g(r_ggd, c - 1), g(r_ggd, c)
            once = truth(xeq(semi, 1))
            if isinstance(once, str):
                b_ = once
            else:
                b_ = ref(prev) if once else average([prev, cur])
            S.set(r_ei, c, mul(g(r_fi, c), b_))
            S.set(r_base, c, b_)
        # debt stock by creditor (first 16 years)
        for i, lc in enumerate(CRED_COLS):
            share = ref(row(CRED_ROWS[i], u))
            S.set(r_ggd, lc, share)
            for j in range(k, NV):
                S.set(r_ggd, lc + 1 + j, mul(share, g(r_ggd, U + j)))


def _effective_rate(S, b, base):
    """Contribution of each vintage to the effective interest rate of its currency (needs every INT_BASE row)."""
    g = S.get
    for k in range(NV):
        r = b + EFF_IR + k
        key = (_crit(g(r, 7)), _crit(g(r, 11)))
        e = err(g(r, 7), g(r, 11))
        for c in range(U + k, CY + 1):
            ib = g(b + INT_BASE + k, c)
            S.set(r, c, xif(xeq(ib, 0), lambda: 0, lambda: e or ar(
                lambda f, x, t: f * x / t, g(b + FI + k, c), ib, base.total(key, c))))
