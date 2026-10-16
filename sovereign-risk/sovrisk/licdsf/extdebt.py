"""Ext_Debt_Data sheet of the LIC DSF template: the public external debt database of the DSA.

It gathers, by creditor (IMF, IDA windows, other multilaterals, Paris Club, non-Paris Club, commercial, locally
issued debt held by non-residents):
1. the debt service on existing (old) MLT debt from 'Input 3' (2023-2068), its stock path and PV;
2. new MLT disbursements from 'Input 4 - External Financing' and locally-issued debt from 'Input 5';
3. the shares and average terms (interest, grace, maturity) of new borrowing;
4. the interest, amortization, PV and nominal stock of new debt, creditor by creditor, from the PV sheets
   (PV_Base, PV_LC_NR1-3);
5. short-term debt, totals of debt service and stocks, the grant element of new borrowing and the concessional
   share.
Year columns: E = 2023 (last historical year), F = 2024 (first projection year) ... BN = 2084.
"""
from sovrisk.srdsf.book import ci

import math

from .macrodebt import (AVERAGE, CONCAT, IF, IFERROR, ISNUMBER, NPV, SUM, G, X, _num, cols, num_or, tr,
                        val)

SHEETS = ['Ext_Debt_Data']

QUIRKS = [
    "Ext_Debt_Data!F331 wraps the IMF stock in IFERROR, but G331:BN331 read PV_Base!E24:BL24 directly.",
    "Column D 'PV_Base line no.' counters: D238:D240 add $D$142 (the interest offset) where the rest of the "
    "amortization block adds $D$192, and D302 (a section label row) gets a counter (-2) of its own.",
    "Ext_Debt_Data!A236 repeats the non-resident label (A$49) where the matching rows of the other blocks show "
    "the residents' label.",
    "Rows 107:118 (locally-issued debt in USD) run to BN but divide by the exchange rate of row 403, which stops "
    "at Z: from AA on they are #DIV/0! (or 0 where the IF picks the zero branch).",
    "The grant element and discount rate of new borrowing (rows 408, 410) leave the four new IDA windows "
    "(rows 76:79) out of the weighted average while row 122 (the denominator) includes them.",
    "Row 383 (interest on short-term debt) reads Input 5 one column to the left of row 382 (the previous year).",
]

I3 = 'Input 3 - Macro-Debt data(DMX)'
I4 = 'Input 4 - External Financing'
I5 = 'Input 5 - Local-debt Financing'
E_, F_, Z_, AX, BN = ci('E'), ci('F'), ci('Z'), ci('AX'), ci('BN')

# old-debt creditor rows 12:40 -> Input 4 row of the creditor (labels, discount rates); Input 3 row = row + 53
OLD_ROWS = [12, 13, 14, 15, 16, 17, 19, 20, 21, 24, 25, 26, 27, 28, 30, 31, 32, 33, 34, 36, 37, 38, 39, 40]
OLD_I4 = {r: (r - 2 if r <= 15 else r + 2) for r in OLD_ROWS}
OLD_LABEL_ROWS = OLD_ROWS + [18, 23, 35]           # 18 / 23 / 35: group labels from Input 4 too
# new-disbursement creditor rows 72:104 = Input 4 rows 10:42 (+62)
NEW_ROWS = [r for r in range(72, 105) if r not in (82, 86, 87, 93, 99)]
NEW_LABEL_ROWS = [r for r in range(72, 105) if r not in (86, 93)]

# the four creditor-list blocks of new debt: header row -> (PV-sheet row offset from the "PV of debt" row,
# first column). Row h+k of a block is creditor k of LIST below.
BLOCKS = {142: (2, F_),                                 # interest
          192: (3, F_),                                 # amortization
          279: (0, F_),                                 # PV of new MLT debt
          329: (-1, F_)}                                # nominal stock of new debt
# creditor k (row offset within a block) -> (PV sheet, its "PV of debt" row)
LIST = {2: 25, 3: 67, 4: 93, 5: 118, 6: 142, 7: 166, 8: 190, 9: 214, 10: 248, 11: 274,
        13: 300, 14: 326, 15: 352, 18: 378, 19: 404, 20: 430, 21: 456, 22: 482,
        24: 508, 25: 534, 26: 560, 27: 586, 28: 612, 30: 638, 31: 664, 32: 690, 33: 716, 34: 742,
        41: 768, 42: 794, 43: 820, 46: 846, 47: 872, 48: 898}
LIST = {k: ('PV_Base', r) for k, r in LIST.items()}
LIST.update({37: ('PV_LC_NR1', 15), 38: ('PV_LC_NR2', 15), 39: ('PV_LC_NR3', 15)})
# subtotals within a block: offset -> offsets summed (SUM over a range, or a plain sum of two subtotals)
BLOCK_SUMS = [(1, range(2, 12)), (12, range(13, 16)), (17, range(18, 23)), (23, range(24, 29)),
              (29, range(30, 35)), (36, range(37, 40)), (40, range(41, 44)), (45, range(46, 49))]
# labels in column A of each block: offset -> Input 4 row (creditors), or a same-sheet row ('A$49' etc.)
BLOCK_I4_LABELS = {k: k + 8 for k in list(range(2, 16)) + list(range(17, 35)) if k != 23}
BLOCK_A_LABELS = {35: 49, 36: 106, 37: 107, 38: 108, 39: 109, 40: 110, 41: 111, 42: 112, 43: 113,
                  45: 115, 46: 116, 47: 117, 48: 118}
BLOCK_A44 = {142: 52, 192: 49, 279: 114, 329: 114}     # 'held by residents' label row (quirk in 192)
# 'PV_Base line no.' counters in column D: row -> (row it adds to, row of the offset)
D_COUNTERS = {
    155: (153, 142), 156: (155, 142), 157: (156, 142), 160: (157, 142), 161: (160, 142), 162: (161, 142),
    163: (162, 142), 164: (163, 142), 166: (164, 142), 167: (166, 142), 168: (167, 142), 169: (168, 142),
    170: (169, 142), 172: (170, 142), 173: (172, 142), 174: (173, 142), 175: (174, 142), 176: (175, 142),
    183: (176, 142), 184: (183, 142), 185: (184, 142), 188: (185, 142), 189: (188, 142), 190: (189, 142),
    238: (235, 142), 239: (238, 142), 240: (239, 142)}
D_COUNTERS.update({r: (r - 50, 192) for r in (202, 203, 205, 206, 207, 210, 211, 212, 213, 214, 216, 217, 218,
                                             219, 220, 222, 223, 224, 225, 226, 233, 234, 235)})
D_COUNTERS.update({r: (r - 137, 278) for r in (289, 290, 292, 293, 294, 297, 298, 299, 300, 301, 302, 303, 304,
                                              305, 306, 307, 309, 310, 311, 312, 313, 320, 321, 322, 325,
                                              326, 327)})
D_COUNTERS.update({r: (r - 137, 329) for r in (331, 332, 333, 334, 339, 340, 342, 343, 344, 347, 348, 349,
                                              350, 351, 353, 354, 355, 356, 357, 359, 360, 361, 362, 363,
                                              370, 371, 372, 375, 376, 377)})
# translated labels in column A: row -> translation row
TR_LABELS = {2: 614, 8: 615, 11: 617, 22: 623, 29: 628, 42: 637, 43: 639, 44: 640, 54: 636, 61: 638, 62: 639,
             63: 640, 65: 642, 67: 644, 70: 647, 71: 617, 86: 623, 93: 628, 122: 648, 130: 649, 131: 650,
             132: 651, 133: 652, 135: 654, 136: 655, 138: 659, 140: 661, 142: 663, 192: 664, 242: 665,
             244: 617, 255: 623, 262: 628, 277: 666, 279: 668, 329: 669, 379: 670, 380: 671, 382: 672,
             391: 673, 393: 675, 394: 676, 395: 677, 396: 678, 405: 681, 407: 683, 408: 684, 409: 685,
             410: 686, 413: 689, 414: 690, 418: 617, 425: 623, 432: 628}
for _h in BLOCKS:
    TR_LABELS.update({_h + 1: 617, _h + 16: 623, _h + 23: 628})
# rows 419:443, new disbursements on concessional terms: row -> new-disbursement row (Input 4 row = it - 62)
CONC_ROWS = {419: 72, 420: 73, 421: 74, 422: 75, 423: 80, 424: 81, 427: 88, 428: 89, 429: 90, 430: 91,
             431: 92, 433: 94, 434: 95, 435: 96, 436: 97, 437: 98, 439: 100, 440: 101, 441: 102, 442: 103,
             443: 104}
CONC_LABELS = {r: r - 409 for r in range(419, 423)}
CONC_LABELS.update({423: 18, 424: 19})
CONC_LABELS.update({r: r - 401 for r in list(range(426, 432)) + list(range(433, 444))})
# Input 4 rows weighted in the average terms of new debt (rows 131:133), as (Input 4 rows, Ext rows)
TERMS_GROUPS = [(range(10, 20), range(72, 82)), (range(21, 24), range(83, 86)), (range(26, 31), range(88, 93)),
                (range(32, 37), range(94, 99)), (range(38, 43), range(100, 105)), (range(49, 52), range(107, 110)),
                (range(54, 57), range(111, 114)), (range(59, 62), range(116, 119))]
# rows weighted in the grant element / discount rate (rows 408, 410): external creditors without new IDA
GE_ROWS = [72, 73, 74, 75, 80, 81, 83, 84, 85, 88, 89, 90, 91, 92, 94, 95, 96, 97, 98, 100, 101, 102, 103, 104]


def compute(book, sheet='Ext_Debt_Data'):
    E = G(book, 'Ext_Debt_Data')
    In1, In3, In4, In5 = G(book, 'Input 1 - Basics'), G(book, I3), G(book, I4), G(book, I5)
    MD = G(book, 'Macro-Debt_Data')
    PV = {s: G(book, s) for s in ('PV_Base', 'PV_LC_NR1', 'PV_LC_NR2', 'PV_LC_NR3')}
    i3 = lambda r, c: In3(r, c + 18)                  # Input 3: column W = 2023 = Ext column E
    i5 = lambda r, c: In5(r, c + 3)                   # Input 5: column H = 2023 = Ext column E
    md = lambda r, c: MD(r, c + 15)                   # Macro-Debt_Data: column T = 2023
    rows = lambda c, r0, r1: [E.raw(r, c) for r in range(r0, r1 + 1)]

    # ---- labels
    for r, t in TR_LABELS.items():
        E.set(r, 'A', tr(book, t))
    E.set(5, 'A', In1(5, 'B'))
    for r in OLD_LABEL_ROWS:
        E.set(r, 'A', In4(OLD_I4.get(r, r + 2), 'B'))
        if r in OLD_ROWS:
            E.set(r, 'BO', CONCAT('OLD_', In4(OLD_I4[r], 'J')))
    for r in NEW_LABEL_ROWS:
        E.set(r, 'A', In4(r - 62, 'B'))
    for r in OLD_LABEL_ROWS:                           # PV of existing debt, by creditor
        E.set(r + 233, 'A', In4(OLD_I4.get(r, r + 2), 'B'))
    E.set(120, 'A', In1(33, 'B'))
    E.set(120, 'C', In1(33, 'C'))
    rb = X(E.raw(120, 'C')) == X(book['lookup'].get(4, ci('X')))        # residency-based debt definition
    E.set(49, 'A', IF(rb, 'Locally-issued debt held by non-residents',
                      'Locally-issued debt held by non-residents - please ignore on a currency basis'))
    E.set(52, 'A', IF(rb, 'Locally-issued debt held by residents', 'Locally-issued debt'))
    E.set(50, 'A', In5(103, 'A'))
    E.set(51, 'A', In5(34, 'A'))
    E.set(53, 'A', In5(92, 'A'))
    E.set(56, 'A', E(43, 'A'))
    E.set(57, 'A', E(44, 'A'))
    E.set(105, 'A', E(49, 'A'))
    for r in range(106, 114):
        E.set(r, 'A', In5(r - 76, 'A'))
    E.set(114, 'A', E(52, 'A'))
    for r in range(115, 119):
        E.set(r, 'A', In5(r - 96, 'A'))
    for r in range(125, 129):
        E.set(r, 'A', G(book, 'Input 7 - Residual Financing')(r - 117, 'G'))
    E.set(274, 'A', E(48, 'A'))
    E.set(384, 'A', E(380, 'A'))
    E.set(388, 'A', E(380, 'A'))
    E.set(417, 'A', MD(54, 'E'))
    E.set(417, 'B', In1(15, 'B'))
    E.set(417, 'D', IF(ISNUMBER(In1(15, 'C')), In1(15, 'C'), 0.35))
    for r, i in CONC_LABELS.items():
        E.set(r, 'A', In4(i, 'B'))
    for h in BLOCKS:
        for k, i in BLOCK_I4_LABELS.items():
            E.set(h + k, 'A', In4(i, 'B'))
        for k, src in BLOCK_A_LABELS.items():
            E.set(h + k, 'A', E(src, 'A'))
        E.set(h + 44, 'A', E(BLOCK_A44[h], 'A'))
    for r in sorted(D_COUNTERS):
        a, b = D_COUNTERS[r]
        E.set(r, 'D', E(a, 'D') + E(b, 'D'))

    # ---- year header
    for c in cols('D', 'Z'):
        E.set(9, c, MD(5, c + 15))
    for c in cols('AA', 'BN'):
        E.set(9, c, E(9, c - 1) + 1)
    for c in cols(E_, BN):
        E.set(1, c, E(9, c))
    E.set(46, 'A', CONCAT('check (outstanding as of end-', E(9, E_), ' - total debt services)'))
    E.set(381, 'E', CONCAT('Note: interest associated with ', E(1, E_) - 1,
                           ' ST debt should be included in aggregate data.'))
    E.set(385, 'E', CONCAT('Note: Debt service associated with ', E(1, E_) - 1, ' and ', E(1, E_),
                           ' ST debt  is captured in aggregate data on existing debt.'))

    # ---- 1. existing MLT debt: debt service by creditor (2023-2068)
    OLD = cols(E_, AX)
    for c in OLD:
        for r in OLD_ROWS:
            E.set(r, c, num_or(i3(r + 53, c), 0))
        E.set(11, c, SUM(rows(c, 12, 17)))                      # multilaterals
        E.set(18, c, SUM(rows(c, 19, 21)))                      # other multilaterals
        E.set(23, c, SUM(rows(c, 24, 28)))                      # Paris Club
        E.set(29, c, SUM(rows(c, 30, 34)))                      # non-Paris Club
        E.set(22, c, E(23, c) + E(29, c))                       # official bilaterals
        E.set(35, c, SUM(rows(c, 36, 40)))                      # commercial
        E.set(42, c, E(11, c) + E(18, c) + E(22, c) + E(35, c))   # total debt service
        E.set(43, c, num_or(i3(95, c), 0))                      # of which principal
        E.set(44, c, E(42, c) - E(43, c))                       # of which interest
        E.set(65, c, num_or(i3(55, c), 0))                      # arrears
    E.set(45, E_, i3(51, E_))                                   # evolution of the stock
    for c in cols(F_, AX):
        E.set(45, c, E(45, c - 1) - E(43, c))
    E.set(46, E_, i3(51, E_) - SUM(E.row(43, F_, AX)))

    # ---- exchange rates (memorandum) and locally-issued debt (2023-2044), in USD
    SHORT = cols(E_, Z_)
    for c in SHORT:
        E.set(402, c, md(59, c))                                # exchange rate, end of period
        E.set(403, c, md(60, c))                                # exchange rate, period average
    for c in SHORT:
        if c == E_:
            E.set(50, c, IF(rb, (i3(166, c) + i3(168, c)) / i3(20, c), 0))
        else:
            E.set(50, c, IF(rb, (i5(147, c) + i5(156, c)) / E(403, c), 0))   # held by non-residents, LC
        E.set(51, c, IF(rb, (i5(148, c) + i5(157, c)) / E(403, c), 0))       # held by non-residents, FX
        E.set(49, c, E(50, c) + E(51, c))
        E.set(53, c, IF(rb, 0, (i5(145, c) + i5(153, c)) / E(403, c)))      # held by residents, FX
        E.set(55, c, E(49, c) + E(53, c))                                    # total debt service
        E.set(56, c, IF(rb, (i5(156, c) + i5(157, c)) / E(403, c), i5(153, c) / E(403, c)))   # principal
        E.set(57, c, E(55, c) - E(56, c))                                    # interest
        E.set(58, c, IF(rb, (i5(166, c) + i5(167, c)) / E(402, c), i5(163, c) / E(402, c)))   # stock
    for c in OLD:                                               # total incl. locally-issued debt
        E.set(61, c, E(42, c) + E(55, c))
        E.set(62, c, E(43, c) + E(56, c))
        E.set(63, c, E(61, c) - E(62, c))
    E.set(67, E_, md(9, E_) - E(65, E_))                        # old MLT debt stock, excluding arrears
    for c in cols(F_, AX):
        E.set(67, c, E(67, c - 1) - E(43, c) - (E(58, c - 1) - E(58, c)))

    # ---- 3. new MLT disbursements (2024-2084)
    NEW = cols(F_, BN)
    for c in NEW:
        for r in NEW_ROWS:
            E.set(r, c, In4(r - 62, c + 6))                     # Input 4: column L = 2024
        E.set(71, c, SUM(rows(c, 72, 81)))
        E.set(82, c, SUM(rows(c, 83, 85)))
        E.set(87, c, SUM(rows(c, 88, 92)))
        E.set(93, c, SUM(rows(c, 94, 98)))
        E.set(86, c, E(87, c) + E(93, c))
        E.set(99, c, SUM(rows(c, 100, 104)))
        for r in (107, 108, 109):                               # locally-issued, non-residents, LC
            E.set(r, c, IF(rb, i5(r - 3, c) / E(403, c), 0))
        for r in (111, 112, 113):                               # locally-issued, non-residents, FX
            E.set(r, c, i5(r - 3, c) / E(403, c))
        for r in (116, 117, 118):                               # locally-issued, residents, FX
            E.set(r, c, IF(rb, 0, i5(r - 23, c) / E(403, c)))
        E.set(106, c, SUM(rows(c, 107, 109)))
        E.set(110, c, SUM(rows(c, 111, 113)))
        E.set(105, c, E(106, c) + E(110, c))
        E.set(115, c, SUM(rows(c, 116, 118)))
        E.set(122, c, E(71, c) + E(82, c) + E(86, c) + E(99, c) + E(105, c) + E(115, c))

    # ---- 4. new debt service, PV and stock by creditor, from the PV sheets
    for h, (off, c0) in BLOCKS.items():
        for k, (sh, base) in LIST.items():
            for c in cols(c0, BN):
                v = PV[sh](base + off, c - 2)                    # PV sheets: column D = 2024
                if h == 329 and k == 2 and c > F_:
                    E.set(h + k, c, v)                           # quirk: no IFERROR after F331
                else:
                    E.set(h + k, c, IFERROR(v, 0))
        for c in NEW:
            for k, ks in BLOCK_SUMS:
                E.set(h + k, c, SUM(rows(c, h + ks[0], h + ks[-1])))
            E.set(h + 16, c, E(h + 17, c) + E(h + 23, c))
            E.set(h + 35, c, E(h + 36, c) + E(h + 40, c))
            E.set(h, c, E(h + 1, c) + E(h + 12, c) + E(h + 16, c) + E(h + 29, c) + E(h + 35, c) + E(h + 45, c))
    for c in NEW:
        E.set(140, c, E(142, c) + E(192, c))                    # total new debt service

    # ---- PV of existing debt (2023-2044), discounted at each creditor's rate
    for c in SHORT:
        for r in OLD_ROWS:
            E.set(r + 233, c, NPV(In4(OLD_I4[r], 'E'), E.row(r, c + 1, AX)))
        E.set(244, c, SUM(rows(c, 245, 250)))
        E.set(251, c, SUM(rows(c, 252, 254)))
        E.set(256, c, SUM(rows(c, 257, 261)))
        E.set(262, c, SUM(rows(c, 263, 267)))
        E.set(255, c, E(256, c) + E(262, c))
        E.set(268, c, SUM(rows(c, 269, 273)))
        E.set(274, c, E(58, c))                                 # locally-issued debt (nominal)
        E.set(277, c, E(65, c))                                 # arrears
    for c in OLD:
        E.set(242, c, E(244, c) + E(251, c) + E(255, c) + E(268, c) + E(274, c))

    # ---- 5. short-term debt and totals (2023-2044)
    for c in SHORT:
        E.set(379, c, i3(52, c))                                # short-term debt stock
    for c in SHORT:
        if c > E_:
            E.set(380, c, E(379, c - 1) * In4(45, 'F'))         # interest on last year's stock
            E.set(382, c, IF(rb, (i5(191, c + 1) + i5(193, c + 1)) / E(402, c), i5(188, c + 1) / E(402, c)))
        if c > F_:
            E.set(383, c, IF(rb, (i5(191, c) + i5(193, c)) / E(403, c), i5(188, c) / E(403, c)))
            E.set(384, c, IF(rb, (i5(180, c) + i5(182, c)) / E(403, c), i5(177, c) / E(403, c)))
        E.set(386, c, E(379, c) + E(382, c))
        E.set(387, c, E(379, c - 1) + E(383, c))
        E.set(388, c, E(380, c) + E(384, c))
        E.set(390, c, G(book, 'Input 8 - SDR')(24, c - 3))      # SDR allocation
    for c in NEW:
        E.set(123, c, E(122, c) + E(386, c) + (i5(124, c) / E(403, c)))   # total new public debt
        E.set(126, c, E(122, c) / E(123, c))                    # shares of marginal debt
        E.set(127, c, (i5(123, c) / E(403, c)) / E(123, c))
        E.set(128, c, (i5(122, c) / E(403, c)) / E(123, c))
        # average terms of new debt, weighted by disbursements (Input 4 columns F, G, H)
        for r, col in ((131, 'F'), (132, 'G'), (133, 'H')):   # interest, grace, maturity
            if truth_eq0(E(122, c)):
                E.set(r, c, '')
                continue
            t = X(0)
            for i4rows, erows in TERMS_GROUPS:
                t = t + sumproduct([In4(i, col) for i in i4rows], [E(e, c) for e in erows])
            E.set(r, c, t / E(122, c) * 100 if r == 131 else t / E(122, c))
        E.set(135, c, rounddown(E(132, c)))
        E.set(136, c, rounddown(E(133, c)))
    for r in (126, 127, 128, 131, 132, 133):
        E.set(r, 'D', AVERAGE(E.row(r, F_, ci('P'))))
    for r in (126, 127, 128, 131):
        E.set(r, 'C', E(r, 'D'))
    E.set(135, 'D', rounddown(E(132, 'D')))
    E.set(136, 'D', rounddown(E(133, 'D')))
    E.set(132, 'C', E(135, 'D'))
    E.set(133, 'C', E(136, 'D'))

    sdr = G(book, 'Input 8 - SDR')
    for c in SHORT:
        E.set(391, c, E(242, c) + E(277, c) + E(279, c) + E(386, c) + E(390, c))   # PV of total debt
        E.set(393, c, md(8, c) - E(329, c) - E(67, c) - E(379, c) - E(65, c))       # check
        E.set(395, c, E(62, c) + E(192, c) + E(387, c))         # principal
        E.set(396, c, E(63, c) + E(142, c) + E(388, c) + sdr(17, c - 3))   # interest
        E.set(394, c, E(395, c) + E(396, c))                    # total debt service
        E.set(398, c, E(329, c) + E(65, c) + E(67, c))          # nominal stock
        if c == E_:
            E.set(399, c, IF(rb, E(45, c) + i5(164, c) + i5(168, c) + E(330, c) + E(341, c) + E(345, c)
                             + E(358, c) + E(369, c) + E(379, c) + i5(200, c) / E(402, c), E(398, c)))
        else:
            E.set(399, c, IF(rb, (E(45, c) - (E(65, c) - E(65, c - 1))) + i5(164, c) + i5(168, c) + E(330, c)
                             + E(341, c) + E(345, c) + E(358, c) + E(369, c) + E(379, c)
                             + i5(200, c) / E(402, c), E(398, c)))

    # ---- grant element of new borrowing, discount rate, concessional loans (2024-2044)
    def weighted(col):
        t = X(0)
        for r in GE_ROWS:
            t = t + In4(r - 62, col) * E(r, c)
        lc = IF(rb, sum_terms([(49, 107), (50, 108), (51, 109), (54, 111), (55, 112), (56, 113)], col, c),
                sum_terms([(54, 111), (55, 112), (56, 113), (59, 116), (60, 117), (61, 118)], col, c))
        return t + lc

    def sum_terms(pairs, col, c):
        t = None
        for i, e in pairs:
            x = In4(i, col) * E(e, c)
            t = x if t is None else t + x
        return t

    for c in cols(F_, Z_):
        E.set(408, c, weighted('I') / E(122, c))                # grant element (percent)
        E.set(407, c, E(122, c) * (1 - E(408, c) / 100))        # PV of new disbursements
        E.set(409, c, E(408, c) * E(122, c) / 100)              # grant implicit in new disbursements
        E.set(410, c, weighted('E') / E(122, c) * 100)          # average discount rate
        for r, e in CONC_ROWS.items():
            E.set(r, c, IF(In4(e - 62, 'I') / 100 >= E(417, 'D'), E(e, c), 0))
        E.set(417, c, SUM(rows(c, 419, 443)))


def truth_eq0(x):
    """x=0 as IF sees it (an error counts as not equal: the formula then errors in its other branch)."""
    t = (X(x) == 0).v
    return t is True


def sumproduct(a, b):
    """SUMPRODUCT of two equal ranges: non-numbers count as 0, an error anywhere is returned."""
    t = 0.0
    for x, y in zip(a, b):
        x, y = val(x), val(y)
        for v in (x, y):
            if isinstance(v, str) and v.startswith('#'):
                return X(v)
        if isinstance(x, (int, float)) and not isinstance(x, bool) and \
                isinstance(y, (int, float)) and not isinstance(y, bool):
            t += x * y
    return X(t)


def rounddown(x):
    v = _num(val(x))
    if isinstance(v, str):
        return X(v)
    return X(math.trunc(v))
