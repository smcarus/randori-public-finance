"""Present-value engine of the LIC DSF template: the PV sheets.

- PV_Base: one block per creditor of new external borrowing (IMF, the IDA windows, other multilaterals, Paris
  Club, non-Paris Club, commercial, FX bonds issued locally). Each block takes the creditor's terms (grace,
  maturity, interest and discount rate from 'Input 4 - External Financing') and
  1. builds the debt service of a loan of 100 disbursed in the first year (straight-line amortization after the
     grace period, or IDA's own repayment schedule), its PV and grant element, year by year;
  2. applies it to the creditor's actual disbursements (Ext_Debt_Data rows 72:118): cumulative disbursements,
     amortization from the grace/maturity lags (CHOOSE over the cumulative row), interest, stock and PV.
- PV_LC_NR1-3: locally-issued local-currency bonds held by non-residents (1-3, 4-7, 7+ years): one vintage block
  per issuance year, in local currency and converted to USD, summed into PV, stock and debt-service lines.
- PV_Base-add.cost.mkt, PV_baseline_com, PV_stress_com: see the docstrings of their compute functions.
Year columns: D = 2024 (the first projection year), one column per year.
"""
from sovrisk.srdsf.book import ci

from .macrodebt import AVERAGE, CHOOSE, CONCAT, IF, MIN, NPV, SUM, G, X, val

SHEETS = ['PV_Base', 'PV_LC_NR1', 'PV_LC_NR2', 'PV_LC_NR3', 'PV_Base-add.cost.mkt', 'PV_baseline_com',
          'PV_stress_com']

QUIRKS = [
    "PV_Base: the IDA block names (column A of rows 49/75/100/124/148/172/196) replace the Input 4 name by "
    "Input 4 column D when it equals the IDA-regular name (Input 4 B74), but the row of column D read is not "
    "always the block's own: block 49 reads D15, block 196 reads D96, and block 172 compares with its own "
    "name (B16) instead of B74.",
    "PV_Base: the index and year rows of the IDA blocks are copies of other blocks' rows, sometimes from odd "
    "source rows (block 172 copies rows 146/147 for columns AJ:BD and row 149 for AT:BA), and their extents "
    "differ block by block (AC, AL, AR, BB, BD, BL, BM); the port reproduces each extent.",
    "PV_Base: the NPV of the loan of 100 in the last columns reads a range running past the block end (e.g. "
    "block 49: BE:BF, BF:BG, ...; blocks 308/334: BD:BE; block 196: BL:BM) because the formulas were filled "
    "with an anchored end column; the blank cells beyond are skipped by NPV.",
    "PV_Base: the CHOOSE list of the grace lag runs to column AF (one past the block) except block 672 column "
    "AE, which stops at AE; block 196 reads its disbursements from Ext_Debt_Data 17 columns right (not 2) "
    "from column AX on.",
    "PV_Base: J799 and J877 are stray cells, the PV of new debt five rows up times 1.05.",
    "PV_LC_NR1-3: the first vintage's PV label (C29) reads A40, the next vintage's name, not its own A21; "
    "the stock in LC is computed in column D only for the first vintage.",
    "PV_Base-add.cost.mkt: E10 tests D5 instead of C5 for zero (the formula in D10 was copied right without "
    "anchoring C5).",
    "PV_Base-add.cost.mkt: the Eurobond block's amortization in AR:BD was copied from D, so every reference "
    "drifts with the column (AR reads E/C columns, BD reads Q/O); the other blocks stop at AQ.",
    "PV_Base-add.cost.mkt: the lag rows of COM4 and COM5 read the Eurobond and commercial-bank lag rows (29 "
    "and 55) as the year index instead of row 1, and their PV of new borrowing discounts at COM3's rate "
    "($B$75); the commercial bank's maturity row copies the Eurobond's years (row 21).",
    "PV_Base-add.cost.mkt: A3 is a note typed with a leading '=' (stored as a formula cell).",
    "PV_Base-add.cost.mkt, PV_baseline_com, PV_stress_com: Excel returns exactly 0 when a subtraction cancels "
    "to within a couple of units in the last place, which makes the straight-line stock of a loan reach 0 at "
    "maturity and the grant element 0; a cancellation of ~10 ulps (commercial bank block, 100/9 a year) stays "
    "-1.8e-14 and gives a grant element of ~41. Reproduced with xl_sub (threshold 2^-50 of the operands).",
    "PV_stress_com: COM5's loan of 100 charges interest on the average of this and last year's stock (half "
    "the first year's), unlike the other creditors' last-year stock.",
    "PV_stress_com: the interest rate shock is added as (B4/100)% i.e. B4 basis points.",
]

I4 = 'Input 4 - External Financing'
D_ = ci('D')


def TEXT(v):
    """TEXT(v, "#"): text unchanged, a number rounded to a whole number (0 shows as empty text)."""
    v = val(v)
    if isinstance(v, str) or v is None:
        return X('' if v is None else v)
    n = int(abs(v) + 0.5) * (1 if v >= 0 else -1)
    return X('' if n == 0 else str(n))


def xl_sub(a, b):
    """a-b as Excel ends a formula with it: a difference within a few ulps of the operands (cancellation noise)
    comes out as exactly 0, so the straight-line stock of a loan reaches 0 at maturity."""
    r = a - b
    x, y, z = val(a), val(b), val(r)
    if all(isinstance(v, float) or isinstance(v, int) and not isinstance(v, bool) for v in (x, y, z)):
        if z != 0 and abs(z) <= max(abs(x), abs(y)) * 2.0 ** -50:
            return X(0)
    return r


def col_range(a, b):
    a = ci(a) if isinstance(a, str) else a
    b = ci(b) if isinstance(b, str) else b
    return range(a, b + 1)


# ====================================================================== PV_Base
# Every creditor block has the same rows, counted from its debt-stock row t (the name row n is t-3, t-2 for the
# IMF): t stock, t+1 amortization, t+2 interest, t+3 debt service, t+4 PV, t+5 grant element of a loan of 100;
# t+6/t+7 grace lag and the cumulative disbursement it picks, t+8/t+9 the same for maturity; t+11 years,
# t+12 disbursements, t+13 cumulative, t+14 stock, t+15 PV, t+16 debt service, t+17 interest, t+18 amortization.
GENERIC = dict(base='AQ', intr='BD', pv_end='BD', amort='linear', lag_end='AE', ch_g='AF', ch_m='AE',
               yr_end='AE', new_end='AE', out_end='AE', pv_new='generic', hdr_end='BD', year_end='BD')
WIDE = dict(GENERIC, base='BD')
# generic blocks: name row -> (Input 4 row, Ext_Debt_Data disbursement row, overrides)
GENERIC_BLOCKS = [
    (230, 18, 80, WIDE), (256, 19, 81, WIDE), (282, 21, 83, WIDE),
    (308, 22, 84, dict(WIDE, pv_tail={'BD': 'BE'})), (334, 23, 85, dict(WIDE, pv_tail={'BD': 'BE'})),
    (360, 26, 88, {}), (386, 27, 89, {}), (412, 28, 90, {}), (438, 29, 91, {}), (464, 30, 92, {}),
    (490, 32, 94, {}), (516, 33, 95, {}), (542, 34, 96, dict(year_end='BA')), (568, 35, 97, {}),
    (594, 36, 98, {}), (620, 38, 100, {}), (646, 39, 101, {}), (672, 40, 102, dict(year_end='BA', ch_g_at={'AE': 'AE'})),
    (698, 41, 103, {}), (724, 42, 104, {}), (750, 54, 111, {}), (776, 55, 112, {}), (802, 56, 113, {}),
    (828, 59, 116, {}), (854, 60, 117, {}), (880, 61, 118, {}),
]
# IDA windows: name row -> spec. 'hdr'/'year' are the index and year rows (n, n+1) as copied segments
# (source row, first column, last column); 'sched' the repayment-schedule row read by the amortization.
IDA_BLOCKS = [
    dict(n=49, i4=11, ext=73, name_cmp=74, name_d=15, base='BM', intr='BM', pv_end='BD',
         pv_tail={'BE': 'BF', 'BF': 'BG', 'BH': 'BI', 'BI': 'BJ', 'BK': 'BL', 'BL': 'BM'},
         amort='sched', sched=48, lag_end='AV', ch_g='AZ', ch_m='AZ', g_idx=[(49, 'D', 'AV')],
         m_idx=[(49, 'D', 'AV')], yr_end='BM', new_end='AV', out_end='AP', pv_new='ida'),
    dict(n=75, i4=12, ext=74, name_cmp=74, name_d=12, hdr=[(49, 'D', 'BB')], year=[(50, 'D', 'BB')],
         base='BB', intr='BB', pv_end='BD', amort='sched', sched=74, lag_end='BB', ch_g='BL', ch_m='BL',
         g_idx=[(49, 'D', 'BB')], m_idx=[(49, 'D', 'BB')], yr_end='BB', new_end='BB', out_end='BB', pv_new='ida'),
    dict(n=100, i4=13, ext=75, name_cmp=74, name_d=13, hdr=[(75, 'D', 'BD')], year=[(76, 'D', 'BD')],
         base='BD', intr='BD', pv_end='BD', amort='linear', lag_end='AE', ch_g='AF', ch_m='AE',
         g_idx=[(49, 'D', 'AE')], m_idx=[(49, 'D', 'AE')], yr_end='AE', new_end='AE', out_end='AE',
         pv_new='generic'),
    dict(n=124, i4=14, ext=76, name_cmp=74, name_d=14, hdr=[(100, 'D', 'BD')], year=[(101, 'D', 'BD')],
         base='AR', intr='AR', pv_end='BD', amort='sched', sched=123, lag_end='AR', ch_g='BL', ch_m='BL',
         g_idx=[(124, 'D', 'AR')], m_idx=[(100, 'D', 'AR')], yr_end='AR', new_end='AR', out_end='AR',
         pv_new='ida'),
    dict(n=148, i4=15, ext=77, name_cmp=74, name_d=15, hdr=[(124, 'D', 'AL')], year=[(125, 'D', 'AL')],
         base='AL', intr='AL', pv_end='BD', amort='sched', sched=147, lag_end='AL', ch_g='BL', ch_m='BL',
         g_idx=[(148, 'D', 'AL')], m_idx=[(148, 'D', 'D'), (124, 'E', 'AL')], yr_end='AL', new_end='AL',
         out_end='AL', pv_new='ida'),
    dict(n=172, i4=16, ext=78, name_cmp=16, name_d=16, hdr=[(148, 'D', 'AI'), (146, 'AJ', 'BD')],
         year=[(149, 'D', 'AC'), (149, 'AT', 'BA'), (147, 'BB', 'BD')],
         base='AC', intr='AC', pv_end='BD', amort='linear', lag_end='AC', ch_g='BL', ch_m='BL',
         g_idx=[(172, 'D', 'AC')], m_idx=[(148, 'D', 'AC')], yr_end='AS', new_end='AC', out_end='AC',
         pv_new='ida'),
    dict(n=196, i4=17, ext=79, name_cmp=74, name_d=96, hdr=[(49, 'D', 'BL')], year=[(50, 'D', 'BL')],
         base='BL', intr='BL', pv_end='BL', pv_tail={'BL': 'BM'}, amort='sched', sched=195, lag_end='BL',
         ch_g='BZ', ch_m='BZ', g_idx=[(196, 'D', 'BL')], m_idx=[(172, 'D', 'BL')], yr_end='BL',
         new_end='BL', new_split='AX', out_end='BL', pv_new='ida'),
]
IMF_BLOCK = dict(n=8, t=10, i4=10, ext=72, base='BD', intr='BD', pv_end='BD', amort='linear', idx_row=6,
                 lag_end='AE', ch_g='AF', ch_m='AE', g_idx=[(49, 'D', 'AE')], m_idx=[(49, 'D', 'AE')],
                 yr_end='AE', new_end='AE', out_end='AE', pv_new='ida', imf=True)
# IDA repayment schedules: row -> (row of the key in column A, last column, last row of the schedule table,
# its last column)
SCHEDULES = {48: (49, 'BD', 39, 'BD'), 74: (75, 'BD', 39, 'BD'), 123: (123, 'AR', 44, 'BD'),
             147: (147, 'AI', 44, 'BD'), 195: (195, 'BL', 44, 'BL')}
# section labels between blocks: row -> Ext_Debt_Data row of the label
SECTION_LABELS = {3: 11, 280: 18, 358: 22, 359: 23, 488: 29, 618: 99}


def pv_base(book):
    """PV_Base: header rows, the IDA repayment schedules, then the IMF, IDA and other creditor blocks."""
    S = G(book, 'PV_Base')
    In4, Ext = G(book, I4), G(book, 'Ext_Debt_Data')

    # ---- header rows: year index (row 49, counted from its input in D49) and calendar years (row 63, the
    # years of the IDA-regular output block, counted from ProjectionYear); every block copies them
    for c in col_range('E', 'BM'):
        S.set(49, c, S(49, c - 1) + 1)
    S.set(7, 'D', book.name('ProjectionYear'))
    S.set(63, 'D', S(7, 'D'))
    for c in col_range('E', 'BM'):
        S.set(63, c, S(63, c - 1) + 1)
    for c in col_range('D', 'BM'):
        S.set(50, c, S(63, c))
    for c in col_range('D', 'BL'):
        S.set(6, c, S(49, c))
        if c > D_:
            S.set(7, c, S(50, c))
    # IDA repayment-schedule table (Input 4 rows 67:75) and its year counter
    for c in col_range('D', 'BL'):
        S.set(33, c, S(6, c))
        S.set(34, c, S(7, c))
        for r in (41, 42, 43, 44):
            S.set(r, c, In4(r + 31, c + 4))
    for r in range(35, 40):
        for c in col_range('D', 'BD'):
            S.set(r, c, In4(r + 32, c + 4))
    for c in col_range('E', 'BL'):
        S.set(40, c, S(40, c - 1) + 1)

    for r, e in SECTION_LABELS.items():
        S.set(r, 'A', Ext(e, 'A'))
    I5 = G(book, 'Input 5 - Local-debt Financing')
    S.set(748, 'A', CONCAT('Locally-issued debt held by non-residents - ', I5(34, 'A')))
    S.set(826, 'A', CONCAT('Locally-issued debt held by residents - ', I5(19, 'A')))

    # ---- IMF block
    loan_block(book, S, In4, Ext, IMF_BLOCK)
    # ---- IDA windows: schedule rows, names, then the block itself
    for spec in IDA_BLOCKS:
        n = spec['n']
        S.set(n - 1, 'A', In4(spec['i4'], 'B'))
        S.set(n, 'A', IF(S(n - 1, 'A') == In4(spec['name_cmp'], 'B'), In4(spec['name_d'], 'D'), S(n - 1, 'A')))
    S.set(47, 'D', CONCAT(S(49, 'A'), ' repayment schedule'))
    S.set(73, 'D', CONCAT(S(75, 'A'), ' repayment schedule'))
    for r, (key, end, last, lastc) in SCHEDULES.items():
        tab = [[S.raw(rr, c) for c in col_range('B', lastc)] for rr in range(35, last + 1)]
        k = S(key, 'A')
        hit = next((row for row in tab if row[0] is not None and (X(row[0]) == k).v is True), None)
        for c in col_range('D', end):
            j = val(S(40, c))
            if hit is None:
                v = '#N/A'
            elif not isinstance(j, (int, float)) or j < 1 or j > len(hit):
                v = '#REF!'
            else:
                v = hit[int(j) - 1]
            S.set(r, c, v)
    # header rows of the IDA blocks
    for spec in IDA_BLOCKS[1:]:
        n = spec['n']
        for row, segs in ((n, spec['hdr']), (n + 1, spec['year'])):
            for src, c0, c1 in segs:
                for c in col_range(c0, c1):
                    S.set(row, c, S(src, c))
    for spec in IDA_BLOCKS:
        loan_block(book, S, In4, Ext, dict(spec, t=spec['n'] + 3))

    # ---- other creditors
    for n, i4, ext, over in GENERIC_BLOCKS:
        spec = dict(GENERIC, n=n, t=n + 3, i4=i4, ext=ext, g_idx=[(n, 'D', 'AE')], m_idx=[(n, 'D', 'AE')])
        spec.update(over)
        for c in col_range('D', spec['hdr_end']):
            S.set(n, c, S(49, c))
        for c in col_range('D', spec['year_end']):
            S.set(n + 1, c, S(50, c))
        loan_block(book, S, In4, Ext, spec)
    for r in (799, 877):                                   # stray cells: PV of new debt plus 5%
        S.set(r, 'J', S(r - 5, 'I') * 1.05)


def loan_block(book, S, In4, Ext, spec):
    """One creditor block of PV_Base (rows n..t+18), its column extents and variants given by spec."""
    n, t = spec['n'], spec['t']
    imf = spec.get('imf', False)
    # ---- labels and terms
    if imf or 'name_cmp' not in spec:                    # IDA windows set their own names first
        S.set(n, 'A', In4(spec['i4'], 'B'))
    for k, word in enumerate(('Grace ', 'Maturity ', 'Interest ', 'Discount ')):
        S.set(n + 1 + k, 'A', CONCAT(word, S(n, 'A'), ''))
        S.set(n + 1 + k, 'B', In4(spec['i4'], ('G', 'H', 'F', 'E')[k]))
    S.set(t + 11, 'A', CONCAT('Output ', S(n, 'A'), ''))
    if imf:
        R = G(book, 'PV_ResFin_pub')
        for k in range(0, 6):
            S.set(t + k, 'C', R(10 + k, 'C'))
        for k in (12, 13, 14, 16, 17, 18):
            S.set(t + k, 'C', R(24 + k, 'C'))
    else:
        for k in (-1, 0, 1, 2, 3, 4, 5, 6, 8, 12, 13, 14, 16, 17, 18):
            S.set(t + k, 'C', S(10 + k, 'C'))
    S.set(t + 15, 'C', CONCAT(TEXT(S(t + 4, 'C')), '   ', TEXT(S(n, 'A'))))
    g, m, i, d = S(n + 1, 'B'), S(n + 2, 'B'), S(n + 3, 'B'), S(n + 4, 'B')   # grace, maturity, rates

    # ---- loan of 100 disbursed in the first year
    base, D = col_range('D', spec['base']), D_
    idx_row = spec.get('idx_row', n)
    idx = lambda c: S(idx_row, c)
    for c in base:                                       # amortization
        if spec['amort'] == 'sched':
            lag = idx(c) - idx(D)
            S.set(t + 1, c, IF(lag < g, 0, IF(lag <= m, S(t - 1, D) * S(spec['sched'], c), 0)))
        else:
            lag = idx(c) - idx(D) - 1
            S.set(t + 1, c, IF(lag < g, 0, IF(lag < m, S(t - 1, D) / (m - g), 0)))
    S.set(t, D, S(t - 1, D) - S(t + 1, D))                # debt stock
    for c in col_range('E', spec['base']):
        S.set(t, c, S(t, c - 1) - S(t + 1, c))
    for c in col_range('E', spec['intr']):                # interest on last year's stock
        x = i * S(t, c - 1)
        S.set(t + 2, c, IF(S(7, c) <= 2018, 0, x) if imf else x)
    for c in base:
        S.set(t + 3, c, S(t + 1, c) + S(t + 2, c))        # debt service
    end = ci(spec['pv_end'])
    tail = {ci(a): ci(b) for a, b in spec.get('pv_tail', {}).items()}
    for c in base:                                       # PV at the creditor's discount rate
        if c < end:
            rng = S.row(t + 3, c + 1, end)
        else:
            hi = tail.get(c, c)
            rng = S.row(t + 3, min(end, hi), max(end, hi))
        S.set(t + 4, c, IF(i >= d, S(t, c), NPV(d, rng)))
    for c in base:                                       # grant element
        pv = S(t + 4, c)
        S.set(t + 5, c, IF(pv == 0, 0, (1 - pv / S(t, c)) * 100))

    # ---- actual disbursements
    S.set(t + 11, D, S(7, D))
    for c in col_range('E', spec['yr_end']):
        S.set(t + 11, c, S(t + 11, c - 1) + 1)
    split = ci(spec.get('new_split', 'ZZ'))
    for c in col_range('D', spec['new_end']):
        S.set(t + 12, c, Ext(spec['ext'], c + (17 if c >= split else 2)))
    S.set(t + 13, D, S(t + 12, D))
    for c in col_range('E', spec['out_end']):
        S.set(t + 13, c, SUM(S.row(t + 12, D, c)))      # cumulative disbursements
    # grace and maturity lags, and the cumulative disbursement they reach back to
    for k, (term, idxs, last) in enumerate(((g, spec['g_idx'], 'ch_g'), (m, spec['m_idx'], 'ch_m'))):
        cum = S.row(t + 13, D, ci(spec[last]))
        at = {ci(a): ci(b) for a, b in spec.get(last + '_at', {}).items()}
        for src, c0, c1 in idxs:
            for c in col_range(c0, c1):
                x = S(src, c) - term
                S.set(t + 6 + 2 * k, c, IF(x > 0, x, 0))
        for c in col_range('D', spec['lag_end']):
            lag = S(t + 6 + 2 * k, c)
            lst = cum if c not in at else S.row(t + 13, D, at[c])
            S.set(t + 7 + 2 * k, c, IF(lag == 0, 0, CHOOSE(lag, *lst)))
    out = col_range('D', spec['out_end'])
    for c in out:                                        # amortization: disbursed past grace less past maturity
        S.set(t + 18, c, (S(t + 7, c) - S(t + 9, c)) / (m - g))
    pvD = S(t + 4, D)
    for c in out:
        new = S(t + 12, c)
        if c > D:
            S.set(t + 17, c, i * S(t + 14, c - 1))        # interest
        S.set(t + 16, c, S(t + 17, c) + S(t + 18, c))     # debt service
        S.set(t + 14, c, (new if c == D else S(t + 14, c - 1) + new) - S(t + 18, c))   # stock
        if c == D:
            if spec['pv_new'] == 'generic':
                S.set(t + 15, c, IF(i >= d, new, new * pvD / 100))
            else:
                S.set(t + 15, c, new * pvD / 100)
        else:
            prev = S(t + 15, c - 1)
            rolled = prev * (1 + d) - S(t + 16, c)
            if spec['pv_new'] == 'generic':
                S.set(t + 15, c, IF(i >= d, prev - S(t + 18, c) + new, rolled + new * pvD / 100))
            else:
                S.set(t + 15, c, IF(rolled <= 0, new * pvD / 100, rolled + new * pvD / 100))



# ====================================================================== PV_LC_NR1-3
# sheet -> (row of the bond in Input 5 rows 31:33 / its terms in rows 16:18, Ext_Debt_Data row 107:109)
LC_NR = {'PV_LC_NR1': (31, 16, 107), 'PV_LC_NR2': (32, 17, 108), 'PV_LC_NR3': (33, 18, 109)}
VINTAGES = [21 + 19 * j for j in range(21)]                # one block per issuance year 2024-2044
# vintage-block rows summed into the sheet's totals: total row -> row offset in the block
LC_TOTALS = {14: 6, 15: 8, 16: 9, 17: 10, 18: 11}


def pv_lc_nr(book, sheet):
    """PV_LC_NR1-3: exchange rates and the bond's issuance, then one 19-row block per issuance year (years since
    2024, issuance, cumulative issuance, stock in LC and USD, PV, debt service, interest, amortization, lags) and
    the sums over vintages in rows 14:18."""
    S = G(book, sheet)
    NR1 = G(book, 'PV_LC_NR1')
    In5, MD, Ext = G(book, 'Input 5 - Local-debt Financing'), G(book, 'Macro-Debt_Data'), G(book, 'Ext_Debt_Data')
    bond, terms, ext = LC_NR[sheet]
    first = sheet == 'PV_LC_NR1'
    X_, AE = ci('X'), ci('AE')
    S.set(3, 'A', In5(bond, 'A'))
    S.set(3, 'D', book.name('ProjectionYear'))
    for c in col_range('E', 'BB' if first else 'BD'):
        S.set(3, c, S(3, c - 1) + 1)
    if first:
        # exchange rates (period average, end of period), extrapolated at the 2040-44 average depreciation
        for c in col_range('D', 'X'):
            S.set(4, c, MD(60, c + 17))
            S.set(5, c, MD(59, c + 17))
        for c in col_range('T', 'X'):
            S.set(1, c, S(4, c) / S(4, c - 1) - 1)
        S.set(1, 'Y', AVERAGE(S.row(1, 'T', 'X')))
        for c in col_range('Y', 'BB'):
            S.set(4, c, S(4, c - 1) * (1 + S(1, 'Y')))
            S.set(5, c, S(5, c - 1) * (1 + S(1, 'Y')))
    else:
        S.set(1, 'A', NR1(1, 'A'))
        S.set(2, 'A', NR1(2, 'A'))
        for c in col_range('D', 'BD'):
            S.set(4, c, NR1(4, c))
            S.set(5, c, NR1(5, c))
    for c in col_range('D', 'X'):
        S.set(6, c, Ext(ext, c + 2) * S(4, c))           # new borrowing in local currency
        S.set(7, c, In5(bond, c + 5))                    # interest rate
        S.set(9, c, NR1(9, c) if sheet == 'PV_LC_NR3' else MD(56, c + 17))   # GDP in USD
    S.set(8, 'D', AVERAGE(S.row(7, 'D', 'X')))
    S.set(16, 'B', In5(terms, 'C'))                      # grace
    S.set(17, 'B', In5(terms, 'D'))                      # maturity
    S.set(19, 'B', book.name('Discount_Rate_GE'))
    S.set(11, 'D', S(3, 'D'))
    for c in col_range('E', AE):
        S.set(11, c, S(11, c - 1) + 1)
    for c in col_range('D', AE):
        S.set(12, c, S(6, c))
    S.set(13, 'D', S(12, 'D'))
    for c in col_range('E', AE):
        S.set(13, c, SUM(S.row(12, D_, c)))

    g, m, dr = S(16, 'B'), S(17, 'B'), S(19, 'B')
    for s in VINTAGES:
        S.set(s, 'A', S(3, 'A'))
    for j, s in enumerate(VINTAGES):
        S.set(s, 'C', S(3, 'D') if j == 0 else S(s - 19, 'C') + 1)          # issuance year
        S.set(s + 1, 'A', CONCAT('Output ', S(s, 'C')))
        S.set(s + 4, 'C', S(12, 'C'))
        S.set(s + 8, 'C', CONCAT(TEXT('PV of debt'), ' - ', TEXT(S(40 if j == 0 else s, 'A')), TEXT(' (in USD)')))
        for k, src in ((9, 16), (10, 17), (11, 18), (12, 19)):
            S.set(s + k, 'A', S(src, 'A'))
        for k, src in ((9, 16), (10, 17), (12, 19)):
            S.set(s + k, 'B', S(src, 'B'))
        hl = S.row(3, D_, ci('BD'))                         # HLOOKUP(year, $D$3:$BD$7, 5, FALSE)
        yr = S(s, 'C')
        pos = next((p for p, v in enumerate(hl) if v is not None and (X(v) == yr).v is True), None)
        S.set(s + 11, 'B', '#N/A' if pos is None else S(7, D_ + pos))
        iv = S(s + 11, 'B')
        for c in col_range('E', 'BD'):
            S.set(s + 2, c, S(s + 2, c - 1) + 1)                            # years since 2024
        S.set(s + 3, 'D', S(3, 'D'))
        for c in col_range('E', 'BD'):
            S.set(s + 3, c, S(s + 3, c - 1) + 1)
        for c in col_range('D', AE):                                         # issuance in this year only
            S.set(s + 4, c, IF(S(s + 3, c) == yr, S(6, c), 0))
        S.set(s + 5, 'D', S(s + 4, 'D'))
        for c in col_range('E', AE):
            S.set(s + 5, c, SUM(S.row(s + 4, D_, c)))
        for k, term, last in ((13, g, 'AF'), (15, m, 'AE')):                 # grace / maturity lags
            cum = S.row(s + 5, D_, ci(last))
            for c in col_range('D', AE):
                x = S(s + 2, c) - term
                S.set(s + k, c, IF(x > 0, x, 0))
                lag = S(s + k, c)
                S.set(s + k + 1, c, IF(lag == 0, 0, CHOOSE(lag, *cum)))
        for c in col_range('D', AE):
            S.set(s + 12, c, (S(s + 14, c) - S(s + 16, c)) / (S(s + 10, 'B') - S(s + 9, 'B')))  # amortization (LC)
            S.set(s + 11, c, S(s + 12, c) / S(4, c))                         # amortization (USD)
            if c > D_ or j == 0:                                             # stock (LC)
                S.set(s + 7, c, IF(S(s + 3, c) == yr, S(s + 4, c), S(s + 7, c - 1) - S(s + 12, c)))
            v = S(s + 7, c)
            S.set(s + 6, c, IF(v == 0, 0, v / S(5, c)))                      # stock (USD)
            if c > D_:
                S.set(s + 10, c, iv * S(s + 7, c - 1) / S(4, c))             # interest (USD)
            S.set(s + 9, c, S(s + 10, c) + S(s + 11, c))                     # debt service (USD)
        for c in col_range('D', AE):                                         # PV, capped at face value
            pv = NPV(dr, S.row(s + 9, c + 1, ci('BB')))
            S.set(s + 8, c, IF(yr > S(s + 3, c), 0, IF(pv > S(s + 6, c), S(s + 6, c), pv)))
            S.set(s + 17, c, IF(S(s + 6, c) == 0, 0, 1 - S(s + 8, c) / S(s + 6, c)))
    for r, k in LC_TOTALS.items():
        for c in col_range('D', AE):
            S.set(r, c, _plus([S(s + k, c) for s in VINTAGES]))
    S.set(15, 'C', CONCAT(TEXT('PV of debt'), ' - ', TEXT(S(21, 'A')), TEXT(' (in USD)')))
    S.set(19, 'C', CONCAT(TEXT('PV to GDP'), ' - ', TEXT(S(21, 'A'))))
    for c in col_range('D', X_):
        S.set(19, c, S(15, c) / S(9, c) * 100)


def _plus(xs):
    """a+b+c+... as a formula adds cells (blank = 0, errors propagate)."""
    t = X(0)
    for x in xs:
        t = t + x
    return t


# ====================================================================== commercial blocks (shared)
def _lag_rows(S, r_lag, r_pick, year_row, term, cum_row, last_at):
    """t-g / t-m lag rows: lag = max(year - term, 0) and the cumulative disbursement it picks,
    IF(lag=0, 0, CHOOSE(lag, D<cum>, ..., <last><cum>)); last_at(c) is the last column of the CHOOSE list."""
    for c in col_range('D', 'AE'):
        x = S(year_row, c) - term
        S.set(r_lag, c, IF(x > 0, x, 0))
        lag = S(r_lag, c)
        S.set(r_pick, c, IF(lag == 0, 0, CHOOSE(lag, *S.row(cum_row, D_, ci(last_at(c))))))


# ====================================================================== PV_Base-add.cost.mkt
# Five commercial creditors (Eurobond, commercial bank, COM3-5: Ext_Debt_Data rows 100:104, Input 4 rows 38:42),
# each a block of 26 rows from its name row n: n+1..n+4 grace / maturity / interest / discount, the loan of 100
# in rows n+4..n+9 (stock, amortization, interest, debt service, PV, grant element), lags n+10..n+13, then the
# new borrowing n+15..n+22 (years, disbursements, cumulative, stock, PV, debt service, interest, amortization).
# The interest rate of every creditor is the shock D11 in basis points.
MKT_BLOCKS = [19, 45, 71, 97, 123]
MKT_NOTE = '=> Used for the combo shock for external DSA only. '
# per block: (row read as the year index by the lag rows, discount-rate row used by the PV of new borrowing)
MKT_LAG_YEAR = {19: 1, 45: 1, 71: 1, 97: 29, 123: 55}
MKT_DISC = {19: 23, 45: 49, 71: 75, 97: 75, 123: 75}
# block-0 labels in column C from PV_ResFin_pub: block row offset -> PV_ResFin_pub row
MKT_RESFIN_LABELS = {4: 10, 5: 11, 6: 12, 7: 13, 8: 14, 9: 15, 12: 46,
                     16: 36, 17: 37, 18: 38, 20: 40, 21: 41, 22: 42}


def pv_add_cost_mkt(book):
    """PV_Base-add.cost.mkt: the commercial-creditor blocks of PV_Base re-run with the interest rate set to the
    market-financing shock (the combo shock of the external DSA). The shock D11 is the average over 2024-25 of
    the lower of the B6 combo-shock primary-balance gap against the baseline times D5 and the cap D6 (400 bp),
    per the setting in C5 (read from B2_PB_mkt_pub)."""
    S = G(book, 'PV_Base-add.cost.mkt')
    S.set(3, 'A', MKT_NOTE)                                             # a note typed with a leading '='
    In4, Ext, RF = G(book, I4), G(book, 'Ext_Debt_Data'), G(book, 'PV_ResFin_pub')
    BP, B6, In6 = G(book, 'Baseline - public'), G(book, 'B6_combo_mkt_pub'), G(book, 'Input 6 - Tailored Tests')
    for c in col_range('E', 'BD'):
        S.set(1, c, S(1, c - 1) + 1)                                    # year index
    S.set(2, 'D', book.name('ProjectionYear'))
    for c in col_range('E', 'BD'):
        S.set(2, c, S(2, c - 1) + 1)
    S.set(5, 'C', G(book, 'B2_PB_mkt_pub')(67, 'AA'))
    S.set(6, 'D', In6(52, 'H'))
    for c in col_range('D', 'E'):
        S.set(7, c, BP(23, c + 12))                                     # baseline primary balance (P:Q)
        S.set(8, c, B6(17, c + 2))                                      # combo-shock primary balance (F:G)
        S.set(9, c, S(8, c) - S(7, c))
        # the zero test reads the cell left of C5 for E (the formula was copied without anchoring C5)
        gap = S(5, 'D') * S(9, c)
        S.set(10, c, IF(S(5, c - 1) == 0, 0, IF(S(5, 'C') == 'Whichever is lower', MIN(gap, S(6, 'D')),
                                                 IF(S(5, 'C') == 400, S(6, 'D'), gap))))
    S.set(11, 'D', AVERAGE(S.row(10, 'D', 'E')))

    for i, n in enumerate(MKT_BLOCKS):
        first = i == 0
        b_g, b_m, b_i, b_d = n + 1, n + 2, n + 3, n + 4
        S.set(n, 'A', Ext(100 + i, 'A'))
        for k, word in ((1, 'Grace '), (2, 'Maturity '), (3, 'Interest '), (4, 'Discount ')):
            S.set(n + k, 'A', CONCAT(word, S(n, 'A'), ''))
        S.set(b_g, 'B', In4(38 + i, 'G'))
        S.set(b_m, 'B', In4(38 + i, 'H'))
        S.set(b_i, 'B', S(11, 'D') / 10000)
        S.set(b_d, 'B', In4(38 + i, 'E'))
        # labels: block 0 from PV_ResFin_pub, the others copy block 0's
        if first:
            for k, src in MKT_RESFIN_LABELS.items():
                S.set(n + k, 'C', RF(src, 'C'))
        else:
            for k in (3, 4, 5, 6, 7, 8, 9, 10, 12, 16, 17, 18, 20, 21, 22):
                S.set(n + k, 'C', S(19 + k, 'C'))
        # n+1 year index, n+2 calendar years (block 1 reads block 0's years; blocks 2+ stop at BA)
        for c in col_range('D', 'BD'):
            S.set(b_g, c, S(1, c))
        for c in col_range('D', 'BD' if i < 2 else 'BA'):
            S.set(b_m, c, S(21 if i == 1 else 2, c))

        # loan of 100: stock, amortization, interest, debt service, PV, grant element
        wide = 'BD' if first else 'AQ'
        for c in col_range('D', 'BD'):
            if c <= ci('AQ'):
                t = S(b_g, c) - S(b_g, 'D') - 1
                am = IF(t < S(b_g, 'B'), 0, IF(t < S(b_m, 'B'), S(b_i, 'D') / (S(b_m, 'B') - S(b_g, 'B')), 0))
            elif first:
                # AR:BD were copied across from D, so every reference moves with the column
                k = c - ci('AR')
                d, b = ci('E') + k, ci('C') + k
                t = S(b_g, c) - S(b_g, d) - 1
                am = IF(t < S(b_g, b), 0, IF(t < S(b_m, b), S(b_i, d) / (S(b_m, b) - S(b_g, b)), 0))
            else:
                am = None
            if am is not None:
                S.set(n + 5, c, am)
            if c == D_:
                S.set(b_d, c, xl_sub(S(b_i, c), S(n + 5, c)))
            elif c <= ci(wide):
                S.set(b_d, c, xl_sub(S(b_d, c - 1), S(n + 5, c)))
            if c > D_:
                S.set(n + 6, c, S(b_i, 'B') * S(b_d, c - 1))
            if c <= ci(wide):
                S.set(n + 7, c, S(n + 5, c) + S(n + 6, c))
        last = ci('BD')
        for c in col_range('D', 'BD'):
            tail = S.row(n + 7, c + 1, last) if c < last else S.row(n + 7, last, last + 1)
            S.set(n + 8, c, IF(S(b_i, 'B') > S(b_d, 'B'), S(b_d, c), NPV(S(b_d, 'B'), tail)))
            if c <= ci(wide):
                S.set(n + 9, c, IF(S(n + 8, c) == 0, 0, (1 - S(n + 8, c) / S(b_d, c)) * 100))

        # new borrowing
        S.set(n + 15, 'A', CONCAT('Output ', S(n, 'A'), ''))
        S.set(n + 15, 'D', S(b_m, 'D'))
        for c in col_range('E', 'AE'):
            S.set(n + 15, c, S(n + 15, c - 1) + 1)
        for c in col_range('E', 'F'):
            S.set(n + 16, c, Ext(100 + i, c + 2))
        S.set(n + 17, 'D', S(n + 16, 'D'))
        for c in col_range('E', 'AE'):
            S.set(n + 17, c, SUM(S.row(n + 16, D_, c)))
        yr = MKT_LAG_YEAR[n]
        _lag_rows(S, n + 10, n + 11, yr, S(b_g, 'B'), n + 17, lambda c: 'AE' if i >= 2 and c == ci('AE') else 'AF')
        _lag_rows(S, n + 12, n + 13, yr, S(b_m, 'B'), n + 17, lambda c: 'AE')
        span = S(b_m, 'B') - S(b_g, 'B')
        for c in col_range('D', 'AE'):
            S.set(n + 22, c, (S(n + 11, c) - S(n + 13, c)) / span)                       # amortization
            S.set(n + 18, c, S(n + 16, c) - S(n + 22, c) if c == D_ else
                  S(n + 18, c - 1) + S(n + 16, c) - S(n + 22, c))                         # stock
            if c > D_:
                S.set(n + 21, c, S(b_i, 'B') * S(n + 18, c - 1))                          # interest
            S.set(n + 20, c, S(n + 21, c) + S(n + 22, c))                                 # debt service
        S.set(n + 19, 'C', CONCAT(TEXT(S(n + 8, 'C')), ' ', TEXT(S(n, 'A'))))
        S.set(n + 19, 'D', S(n + 16, 'D') * S(n + 8, 'D') / 100)
        disc, ae = S(MKT_DISC[n], 'B'), ci('AE')
        for c in col_range('E', 'AE'):
            tail = S.row(n + 21, c + 1, ae) if c < ae else S.row(n + 21, ae, ae + 1)
            S.set(n + 19, c, NPV(disc, tail))                                              # PV
    for c in col_range('D', 'AE'):
        S.set(13, c, _plus([S(n + 21, c) for n in MKT_BLOCKS]))         # interest, all creditors
        S.set(14, c, _plus([S(n + 19, c) for n in MKT_BLOCKS]))         # PV, all creditors


# ====================================================================== PV_baseline_com / PV_stress_com
# The five commercial creditors of PV_Base (rows 620:724) again, 26 rows per block from the name row n:
# n year index, n+1 calendar years, B(n+1..n+4) grace / maturity / interest / discount; the loan of 100 in
# n+3..n+8 (stock, amortization, interest, debt service, PV, grant element; the PV is the face value when the
# interest rate is at least the discount rate); lags n+9..n+12; the new borrowing n+14..n+21 (years,
# disbursements, cumulative, stock, PV, debt service, interest, amortization). The PV of new borrowing is rolled
# forward: last year's PV grown at the discount rate, less this year's debt service, plus this year's
# disbursement at the loan's PV per 100 of the first year.
COM = {
    # first block row, header year-index row, header calendar-year row; totals: row -> (block row offset,
    # columns); total_labels: row -> block row whose column-C label it shows
    'PV_baseline_com': dict(n0=17, idx=7, yr=8,
                            totals={r: (k, 'D', 'BD') for r, k in {9: 17, 10: 18, 11: 19, 12: 20, 13: 21}.items()},
                            total_labels={9: 17, 10: 7, 11: 19, 12: 20, 13: 21}),
    'PV_stress_com': dict(n0=21, idx=9, yr=10,
                          totals={11: (15, 'E', 'G'), 12: (17, 'E', 'BD'), 13: (18, 'E', 'BD'), 14: (19, 'E', 'BD'),
                                  15: (20, 'E', 'BD'), 16: (21, 'E', 'BD')},
                          total_labels={12: 17, 13: 7, 14: 19, 15: 20, 16: 21}),
}
COM_PV_BASE = 620          # PV_Base name row of the first commercial creditor
COM_LABEL_ROWS = (2, 3, 4, 5, 6, 7, 8, 9, 11, 15, 16, 17, 18, 19, 20, 21)   # block rows labelled in column C


def pv_com(book, sheet):
    """PV_baseline_com: the commercial blocks of PV_Base on the Input 4 terms. PV_stress_com: the same under the
    market-financing shock of C4_Market_financing (its grace and maturity, the interest rate raised by B4 basis
    points)."""
    spec = COM[sheet]
    stress = sheet == 'PV_stress_com'
    S, PB = G(book, sheet), G(book, 'PV_Base')
    In4, Ext, C4 = G(book, I4), G(book, 'Ext_Debt_Data'), G(book, 'C4_Market_financing')
    n0, idx, yr = spec['n0'], spec['idx'], spec['yr']
    if stress:
        S.set(1, 'A', G(book, 'Output 1-1 - External DSA')(1, 'B'))
        S.set(4, 'B', C4(25, 'AB'))                                     # interest shock, basis points
    S.set(idx - 2, 'A', Ext(99, 'A'))
    for c in col_range('E', 'BD'):
        S.set(idx, c, S(idx, c - 1) + 1)
    for c in col_range('D', 'BD'):
        S.set(yr, c, PB(7, c) if c <= ci('H') else S(yr, c - 1) + 1)

    blocks = [n0 + 26 * i for i in range(5)]
    for i, n in enumerate(blocks):
        b_g, b_m, b_i, b_d = n + 1, n + 2, n + 3, n + 4
        S.set(n, 'A', PB(COM_PV_BASE + 26 * i, 'A'))
        for k, word in ((1, 'Grace '), (2, 'Maturity '), (3, 'Interest '), (4, 'Discount ')):
            S.set(n + k, 'A', CONCAT(word, S(n, 'A'), ''))
        for k in COM_LABEL_ROWS:
            if stress and k == 15 and i > 0:
                S.set(n + k, 'C', S(36, 'C'))
            else:
                S.set(n + k, 'C', PB(n + k + COM_PV_BASE - n0, 'C'))
        if stress:
            S.set(b_g, 'B', C4(35 + i, 'I'))
            S.set(b_m, 'B', C4(35 + i, 'H'))
            S.set(b_i, 'B', In4(38 + i, 'F') + S(4, 'B') / 100 / 100)
        else:
            S.set(b_g, 'B', In4(38 + i, 'G'))
            S.set(b_m, 'B', In4(38 + i, 'H'))
            S.set(b_i, 'B', In4(38 + i, 'F'))
        S.set(b_d, 'B', In4(38 + i, 'E'))
        # year index and calendar years (baseline: block 0 reads PV_Base's years, the others block 0's index)
        for c in col_range('D', 'BD'):
            if not stress and i > 0:
                S.set(n, c, S(n0, c))
            else:
                S.set(n, c, S(idx, c) if c == D_ else S(n, c - 1) + 1)
            if c == D_:
                S.set(b_g, c, S(yr, c))
            else:
                S.set(b_g, c, PB(7, c) if not stress and i == 0 else S(b_g, c - 1) + 1)

        # loan of 100
        aq = ci('AQ')
        g, m, r, d = S(b_g, 'B'), S(b_m, 'B'), S(b_i, 'B'), S(b_d, 'B')
        for c in col_range('D', 'AQ'):
            t = S(n, c) - S(n, 'D') - 1
            S.set(b_d, c, IF(t < g, 0, IF(t < m, S(b_m, 'D') / (m - g), 0)))           # amortization
            S.set(b_i, c, xl_sub(S(b_m, c) if c == D_ else S(b_i, c - 1), S(b_d, c)))  # stock
            if stress and i == 4:                                                       # interest on the
                S.set(n + 5, c, r * S(b_i, c) * 0.5 if c == D_ else                   # average stock
                      r * AVERAGE(S.row(b_i, c - 1, c)))
            elif c > D_:
                S.set(n + 5, c, r * S(b_i, c - 1))
            S.set(n + 6, c, S(b_d, c) + S(n + 5, c))                                  # debt service
        for c in col_range('D', 'AQ'):
            S.set(n + 7, c, IF(r >= d, S(b_i, c), NPV(d, S.row(n + 6, c + 1, ci('BD')))))
            S.set(n + 8, c, IF(S(n + 7, c) == 0, 0, (1 - S(n + 7, c) / S(b_i, c)) * 100))

        # new borrowing
        S.set(n + 14, 'A', CONCAT('Output - ', S(n, 'A')) if stress else
              CONCAT('Output ', PB(COM_PV_BASE + 26 * i, 'A'), ''))
        S.set(n + 14, 'D', S(yr, 'D'))
        for c in col_range('E', 'AE'):
            S.set(n + 14, c, S(n + 14, c - 1) + 1)
        for c in col_range('E', 'G'):
            S.set(n + 15, c, Ext(100 + i, c + 2))
        S.set(n + 16, 'D', S(n + 15, 'D'))
        for c in col_range('E', 'AE'):
            S.set(n + 16, c, SUM(S.row(n + 15, D_, c)))
        last_g = (lambda c: 'AE' if c == ci('AE') else 'AF') if not stress and i == 2 else (lambda c: 'AF')
        _lag_rows(S, n + 9, n + 10, n, g, n + 16, last_g)
        _lag_rows(S, n + 11, n + 12, n, m, n + 16, lambda c: 'AE')
        pv100 = S(n + 7, 'D')
        for c in col_range('D', 'AE'):
            S.set(n + 21, c, (S(n + 10, c) - S(n + 12, c)) / (m - g))                  # amortization
            if c == D_:
                S.set(n + 17, c, S(n + 15, c) - S(n + 21, c))                           # stock
            else:
                S.set(n + 17, c, S(n + 17, c - 1) + S(n + 15, c) - S(n + 21, c))
                S.set(n + 20, c, r * S(n + 17, c - 1))                                  # interest
            S.set(n + 19, c, S(n + 20, c) + S(n + 21, c))                               # debt service
            new = S(n + 15, c)
            if c == D_:                                                                 # PV
                S.set(n + 18, c, IF(r >= d, new, new * S(n + 7, c) / 100))
            else:
                prev = S(n + 18, c - 1)
                S.set(n + 18, c, IF(r >= d, prev - S(n + 21, c) + new,
                                    prev * (1 + d) - S(n + 19, c) + new * pv100 / 100))

    for t, (k, c0, c1) in spec['totals'].items():
        for c in col_range(c0, c1):
            S.set(t, c, _plus([S(n + k, c) for n in blocks]))
    for t, k in spec['total_labels'].items():
        S.set(t, 'A', S(n0 + k, 'C'))


def compute(book, sheet):
    if sheet == 'PV_Base':
        pv_base(book)
    elif sheet in LC_NR:
        pv_lc_nr(book, sheet)
    elif sheet == 'PV_Base-add.cost.mkt':
        pv_add_cost_mkt(book)
    elif sheet in COM:
        pv_com(book, sheet)
