"""LOGIT sheet: near-term risk. The logit stress probability (LSP) from 12 regressors, its year-on-year change and
the contribution of each regressor group to that change, and the low/high risk cut-offs."""
import math

from .xl import NA, calc, isnumber, iserr, match

SHEETS = ['LOGIT']
COLS = range(6, 11)                    # F..J: years ProjYr-5 .. ProjYr-1
REG = range(9, 21)                     # regressor rows 9-20


def compute(book, sheet='LOGIT'):
    L, Q = book['LOGIT'], book['Questions']
    proj = book.name('ProjYr')
    cu = book.name('LogitCU')
    hdr = book.hrow('Config!$Y$3:$AE$3')
    coef_col = match('NoCU-Coef' if str(cu) == 'No' else 'WithCU-Coef', hdr)
    sig_col = match('NoCU-Sig' if str(cu) == 'No' else 'WithCU-Sig', hdr)
    L.set(5, 4, coef_col)
    L.set(5, 5, sig_col)
    dates = book.hrow('BaseDBdates')
    for c in COLS:
        L.set(3, c, proj + L.get(4, c))
        L.set(5, c, match(L.get(4, c), dates))
    for r in REG:
        key = L.get(r, 1)
        L.set(r, 4, book.vlookup(key, 'LogitTab', coef_col))
        s = book.vlookup(key, 'LogitTab', sig_col)
        L.set(r, 5, '' if s == 0 or s is None else s)       # IF(VLOOKUP(..)=0,"",..): blank equals 0
        if r in (9, 20):                                     # constant and currency-union share: input rows
            continue
        for c in COLS:
            k = L.get(5, c)
            if r == 14:                                      # credit gap: fall back to the _SR series, floored at 0
                v = book.vlookup(key, 'BaseDBData', k)
                v = v if isnumber(v) else book.vlookup(key + '_SR', 'BaseDBData', k)
                v = v if iserr(v) else max(v, 0)
            elif r in (15, 16, 17):
                v = book.vlookup(key, 'BaseDBData', k)
                v = v if iserr(v) else v * 100
            elif r == 19 and c == 10:                        # latest VIX: next column when available
                v = book.vlookup(key, 'BaseDBData', k + 1)
                v = book.vlookup(key, 'BaseDBData', k) if iserr(v) else v
            else:
                v = book.vlookup(key, 'BaseDBData', k)
            L.set(r, c, v)
    D = [L.get(r, 4) for r in REG]
    for c in COLS:
        ok = all(isnumber(L.get(r, c)) for r in REG)
        L.set(22, c, ok)
        if ok:
            L.set(23, c, 1 / (1 + math.exp(-sum(d * L.get(r, c) for d, r in zip(D, REG)))))
        else:
            L.set(23, c, 'n.a.' if c <= 8 else NA)
    for c in COLS[1:]:
        a, b = L.get(23, c), L.get(23, c - 1)
        L.set(25, c, a - b if isnumber(a) and isnumber(b) else NA)
        for i, r in enumerate(REG):
            d = L.get(r, 4)
            L.set(29 + i, c, calc(lambda d, x, y: (d * x + d * y) / 2, d, L.get(r, c - 1), L.get(r, c)))
            L.set(43 + i, c, calc(lambda x, y: x - y, L.get(r, c), L.get(r, c - 1)))
        avg = [L.get(29 + i, c) for i in range(12)]
        L.set(57, c, calc(lambda *v: math.exp(-sum(v)), *avg))
        L.set(58, c, calc(lambda e: 1 / (1 + e), L.get(57, c)))
        for i, r in enumerate(REG):
            L.set(60 + i, c, calc(lambda d, e, p: d * e * p ** 2, L.get(r, 4), L.get(57, c), L.get(58, c)))
            L.set(74 + i, c, calc(lambda x, y: x * y, L.get(43 + i, c), L.get(60 + i, c)))
        g = lambda *rows: calc(lambda *v: sum(v), *(L.get(r, c) for r in rows))
        L.set(87, c, L.get(75, c))
        L.set(88, c, L.get(76, c))
        L.set(89, c, g(77, 78, 79))
        L.set(90, c, g(80, 81, 82, 83))
        L.set(91, c, g(84, 85))
        L.set(94, c, coef_col)
        L.set(95, c, calc(lambda v: v / 100, book.vlookup(L.get(95, 1), 'LogitTab', coef_col)))
        L.set(96, c, calc(lambda v: v / 100, book.vlookup(L.get(96, 1), 'LogitTab', coef_col)))
    j = 10                                                   # signal for the latest year
    p, ok = L.get(23, j), L.get(22, j)
    if iserr(p):
        L.set(24, j, p if ok else (NA if iserr(p) else 0))
    elif ok and p >= L.get(96, j):
        L.set(24, j, 'High')
    elif ok and p <= L.get(95, j):
        L.set(24, j, 'Low')
    elif ok:
        L.set(24, j, 'Moderate')
    else:
        L.set(24, j, 0)
