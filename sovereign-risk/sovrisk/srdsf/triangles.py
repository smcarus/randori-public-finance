"""Triangles sheet (hidden): debt "triangles" for the market debt issued in the GFN stress scenario.

Four instruments (short- and long-term, local and foreign currency; Config!CG44:CN47 sets their grace, maturity,
payment frequency and coupon type) are issued each year in the amounts the GFN sheet's stress scenario needs
(GFN rows 91-94 times the market-based financing in row 150, foreign currency converted at the stress exchange
rate). For each instrument and each issue year (vintage) the sheet tracks, year by year: the interest rate, the
outstanding stock, the amortization and the interest bill, and splits each of them across five creditor groups
with the implied holder shares from GFN rows 210-214. GFN reads the interest, amortization and stock lines back
with SUMIFS.
"""
import math

from .gfn import AND, IF, OR, Ctx, cat, cmp, ref
from .xl import NA, average, calc, eq, iserr, match

SHEETS = ['Triangles']

QUIRKS = [
    'Interest on semiannual instruments: between the first and the final year of an instrument the interest '
    'formula tests "year issued + maturity < year" instead of ">", so a semiannual instrument maturing after more '
    'than one year pays no interest in its intermediate years (only half a coupon in the issue year and the '
    'maturity year).',
    'Column H ("ER") looks up a name BaseFinData that the workbook does not define, so it is #NAME? everywhere.',
    'Row 5 (I:O, S, U:AU) MATCHes against a deleted range and is #REF! everywhere.',
    'H87 (second instrument only) holds a stray IF without an else branch: the next year\'s short-term '
    'foreign-currency share, or FALSE beyond the medium-term horizon.',
    'The zero-coupon branch of the interest-rate rows compounds the GFN rate of the issue year over the maturity, '
    'and the "Scenario" column of each section copies a cell in the middle of the previous section rather than the '
    'header (same value).',
    'The stock rows read the very first column of the year before (T33 = 0, an input) when computing interest on '
    'the first vintage.',
]

KEYS = ['DICLMS', 'DICFMS', 'DICLML', 'DICFML']     # GFN debt-share rows for the four instruments
RATE_ROW = [83, 88, 83, 88]                         # GFN stress marginal rate: local / foreign currency
FIRST, SIZE = 9, 77                                 # block of the first instrument, rows per block
U = 21                                              # column U: first projection year
YEARS = 16                                          # U..AJ
CRED = [53, 75, 97, 119, 141]                       # BA, BW, CS, DO, EK: creditor share columns
# offsets of the sections within a block
ISS, IRT, IRC, MC, RGFN, RATE, STOCK, AMORT, INT = 1, 2, 3, 4, 5, 6, 24, 42, 60
cA, cB, cC, cD, cE, cF, cG, cH, cI, cJ, cK, cL, cM, cN, cO, cP, cQ, cR, cT = (
    1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 20)


def compute(book, sheet='Triangles'):
    T = book['Triangles']
    g, s = T.get, T.set
    add = lambda *v: calc(lambda *x: sum(x), *v)
    sub = lambda a, b: calc(lambda p, q: p - q, a, b)
    mul = lambda *v: calc(lambda *x: math.prod(x), *v)
    dv = lambda a, b: calc(lambda p, q: p / q, a, b)
    proj = book.name('ProjYr')
    hor = book.name('MTHorizon')
    x = Ctx(book)
    scen = lambda key, col: x.vl(key, 'GFNStressScen', col)
    Cf = book['Config']

    # --- header rows: years, columns in GFN
    for c in range(U, U + 27):                      # U..AU
        s(3, c, calc(lambda a, b: a + b, proj, g(4, c)))
        s(5, c, '#REF!')
        s(6, c, match(g(4, c), book.hrow('GFNStressScenDates')))
    for c in list(range(cI, cO + 1)) + [19]:
        s(5, c, '#REF!')
    for lab in CRED:                                # creditor blocks repeat the years
        for k in range(YEARS):
            s(3, lab + 1 + k, ref(g(3, U + k)))
    row3 = [g(3, c) for c in range(1, max(c for _, c in T.cells) + 1)]
    for k in range(YEARS):
        s(1, U + k, match(g(3, U + k), row3))
    yr = lambda c: g(3, c)

    def pq(r):
        """Payment type and maturity bucket from grace (J) and maturity (K)."""
        s(r, cP, IF(cmp(g(r, cJ), '=', g(r, cK)), 'Bullet', 'Amortizing'))
        k = g(r, cK)
        s(r, cQ, IF(cmp(k, '<=', 1), 'ST', lambda: IF(AND(cmp(k, '>', 1), cmp(k, '<=', 5)), 'MT', 'LT')))

    def copy(r, src, c0, c1):
        for c in range(c0, c1 + 1):
            s(r, c, ref(g(src, c)))

    def countif_a(r1, crit):
        return x.countif('Triangles', cA, 1, r1, crit)

    cfg = Cf.rng('CG43:CN43')[0]
    # --- per instrument: description, issuance and the GFN interest rate
    for b in range(4):
        r0 = FIRST + SIZE * b
        ri = r0 + ISS
        s(r0, cT, x.vl(g(r0, cA), 'ScenarioCodes', 2))
        s(ri, cA, cat(countif_a(r0, '=X'), '-M$-SH'))
        s(ri, cB, countif_a(r0, cat('=', g(r0, cA))))
        s(r0, cB, cat(g(r0, cT), ' instrument ', g(ri, cB)))
        for c in range(cI, cO + 1):                 # instrument characteristics from Config
            s(ri, c, x.vl(cat(g(r0, cA), g(ri, cB)), 'Config!$CG$44:$CN$47', match(g(3, c), cfg)))
        pq(ri)
        s(ri, cR, ref(g(r0, cT)))
        # issuance: debt share times market-based stress financing, in foreign currency for FX instruments
        for k in range(YEARS):
            c = U + k
            col = g(6, c)
            amt = IF(cmp(g(4, c), '<=', hor), lambda: mul(scen(KEYS[b], col), scen('STRESS_FIN', col)), 0)
            fx = IF(cmp(g(ri, cI), '=', 'Foreign'), lambda: scen('ENDA_GST', col), 1)
            s(ri, c, dv(amt, fx))
        if b == 1:                                  # stray cell H87
            s(ri, cH, IF(cmp(g(4, U + 1), '<=', hor), lambda: scen('DICFMS', g(6, U + 1)), False))
        # contribution rows: characteristics carried down
        for off in (IRT, IRC, MC):
            s(r0 + off, cB, ref(g(ri, cB)))
        copy(r0 + IRT, ri, cI, cR)
        copy(r0 + IRC, r0 + IRT, cI, cR)
        copy(r0 + MC, r0 + IRC, cI, cO)
        pq(r0 + MC)
        s(r0 + MC, cR, ref(g(r0, cT)))
        # interest rate from GFN
        rg = r0 + RGFN
        s(rg, cA, cat(countif_a(rg - 1, '=X'), '-M%-IR'))
        for k in range(YEARS):
            s(rg, U + k, ref(book['GFN'].get(RATE_ROW[b], 10 + k)))
        for d in range(YEARS):                      # vintage rows of the four sections: labels and characteristics
            for sec in (RATE, STOCK, AMORT, INT):
                r = r0 + sec + d
                if sec != RATE:
                    s(r, cA, ref(g(6, U + d)))
                s(r, cB, ref(g(ri, cB)))
                if d:
                    s(r, cC, ref(g(r - 1, cC)))
                s(r, cE, calc(lambda a, b_: a + b_, proj, g(r, cD)))
                copy(r, ri if d == 0 else r - 1, cI, cO)
                s(r, cF, add(g(r, cE), g(r, cJ)))
                s(r, cG, add(g(r, cE), g(r, cK)))
                s(r, cH, '#NAME?')
                pq(r)
        # scenario column: each section copies one row of the section before it
        for sec, src in ((RATE, (r0, cT)), (STOCK, (r0 + RATE + 7, cR)), (AMORT, (r0 + STOCK + 6, cR)),
                         (INT, (r0 + AMORT + 6, cR))):
            for d in range(YEARS):
                s(r0 + sec + d, cR, ref(g(*src)))
        s(r0 + 23, cC, cat('Debt stock, ', g(r0, cB)))
        s(r0 + 41, cC, cat('Amortization, ', g(r0, cB)))
        s(r0 + 59, cC, cat('Interest, ', g(r0, cB)))

    # --- contributions of each instrument to issuance-weighted rates and maturity (SUMIFS over all instruments)
    x = Ctx(book)
    for b in range(4):
        r0 = FIRST + SIZE * b
        ri = r0 + ISS
        for k in range(YEARS):
            c = U + k
            m, sc, cur = cat('=', g(ri, cM)), cat('=', g(ri, cR)), cat('=', g(ri, cI))
            tot_t = x.sumifs('Triangles', c, (cC, '=Issuance'), (cM, m), (cR, sc))
            tot_c = x.sumifs('Triangles', c, (cC, '=Issuance'), (cI, cur), (cM, m), (cR, sc))
            s(r0 + IRT, c, dv(mul(g(r0 + RGFN, c), g(ri, c)), tot_t))
            s(r0 + IRC, c, dv(mul(g(r0 + RGFN, c), g(ri, c)), tot_c))
            s(r0 + MC, c, dv(mul(g(r0 + RATE, cK), g(ri, c)), tot_c))

    for b in range(4):
        r0 = FIRST + SIZE * b
        ri, rg = r0 + ISS, r0 + RGFN
        for d in range(YEARS):
            rr, rs, ra, rn = r0 + RATE + d, r0 + STOCK + d, r0 + AMORT + d, r0 + INT + d
            first = U + d                               # column of the issue year
            # interest rate on the vintage: fixed at issue, floating with GFN, or zero-coupon paid at maturity
            o = g(rr, cO)
            s(rr, first, IF(cmp(o, '=', 'Zero-coupon'), 0, lambda: ref(g(rg, first))))
            for c in range(first + 1, U + YEARS):
                if iserr(o):
                    v = o
                elif eq(o, 'Fixed'):
                    v = ref(g(rr, c - 1))
                elif eq(o, 'Floating'):
                    v = ref(g(rg, c))
                elif eq(o, 'Zero-coupon'):
                    v = IF(cmp(yr(c), '=', g(rr, cG)),
                           lambda: calc(lambda r_, k_: (1 + r_) ** k_ - 1, g(rg, first), g(rr, cK)), 0)
                else:
                    v = NA
                s(rr, c, v)
            # amortization from the amount issued
            s(rs, first, ref(g(ri, first)))
            s0 = g(rs, first)
            L, P, E, J, K = (g(ra, cc) for cc in (cL, cP, cE, cJ, cK))
            EJ, EK, KJ = add(E, J), add(E, K), sub(K, J)
            for c in range(first, U + YEARS):
                y = yr(c)
                s(ra, c, IF(OR(cmp(L, '=', 'Annual'), cmp(P, '=', 'Bullet')),
                            lambda: IF(AND(cmp(P, '=', 'Bullet'), cmp(EK, '=', y)), s0,
                                       lambda: IF(AND(cmp(P, '=', 'Amortizing'), cmp(EJ, '<', y), cmp(EK, '>=', y)),
                                                  lambda: dv(s0, KJ), 0)),
                            lambda: IF(OR(cmp(EJ, '=', y), cmp(EK, '=', y)), lambda: dv(s0, mul(KJ, 2)),
                                       lambda: IF(AND(cmp(EJ, '<', y), cmp(EK, '>=', y)),
                                                  lambda: dv(s0, KJ), 0))))
            # outstanding stock
            for c in range(first + 1, U + YEARS):
                s(rs, c, sub(g(rs, c - 1), g(ra, c)))
            # interest bill
            L, E, K = g(rn, cL), g(rn, cE), g(rn, cK)
            EK = add(E, K)
            for c in range(first, U + YEARS):
                y, rate = yr(c), g(rr, c)
                prev, cur = g(rs, c - 1), g(rs, c)
                s(rn, c, IF(cmp(L, '=', 'Annual'),
                            lambda: IF(cmp(E, '=', y), 0, lambda: mul(rate, ref(prev))),
                            lambda: IF(cmp(E, '=', y), lambda: dv(mul(rate, ref(cur)), 2),
                                       lambda: IF(cmp(EK, '<', y), lambda: mul(rate, average([prev, cur])),
                                                  lambda: IF(cmp(EK, '=', y),
                                                             lambda: dv(mul(rate, ref(prev)), 2), 0)))))
            # split by creditor with the implied holder shares of the year
            for r, hdr in ((rs, r0 + STOCK - 1), (ra, r0 + AMORT - 1), (rn, r0 + INT - 1)):
                for lab in CRED:
                    share = scen(g(hdr, lab), g(r, cA))
                    s(r, lab, share)
                    for c in range(first, U + YEARS):     # central bank: value*share, others share*value
                        v = g(r, c)
                        s(r, lab + 1 + (c - U), mul(v, share) if lab == CRED[0] else mul(share, v))
