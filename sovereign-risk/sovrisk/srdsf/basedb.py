"""BaseDB sheet: the baseline database. Collects, year by year (columns H:AH = ProjYr-11 .. ProjYr+15), the
public debt stock split into pre-existing debt (history from NewMacrofw, then run off with its amortization) and
debt issued in the projection period (summed from IdentFin and ResidFin), by currency, maturity, holder and
instrument type, in levels, percent of GDP and percent of total; the debt-dynamics decomposition; gross financing
by type of transaction; new-issuance shares; effective and marginal interest rates; and the macro series the
near- and medium-term tools read. LOGIT, FAN, GFN and the stress tests look rows up by their key in column A
(named range BaseDBData = rows 9-333, BaseDBdates = row 4)."""
from .book import ci, cl
from .residfin import IF, Engine, X, cat, cmp, iferror, text, val, vlookup
from .xl import NA, err, iserr, isnumber, match, xsum

SHEETS = ['BaseDB']

QUIRKS = [
    'Row 307 (deflator, 111NGDP_D): when Macrofw has no value the fallback is the value two columns back '
    '(F307 from H307), not the previous year.',
    'Rows 202 and 208 (projected FX / local-linked market amortization, first year): with the override switch '
    'on, the cell returns the switch itself (TRUE) instead of the override amount OverrideAmortFX/LL.',
    'Row 41 (pre-existing short-term debt) reads the next year\'s amortization (T197+T201+T205 in column S); in '
    'AH this reads the blank AI column as 0.',
    'Rows 61-78 convert foreign-currency issuance at the end-of-period rate (row 297) and linked debt with rows '
    '328/330, while rows 183-244 use the period-average rate (row 296) and rows 327/329; reproduced as is.',
    'Row 183/184 (first projection year) criteria "Market"/"Nonmarket" lack the "=" the other columns use; '
    'same meaning in SUMIFS.',
    'Text headers in C9, C32, C57, C170, D288, D289 are #N/A because CurrencyName is #N/A in the sample.',
]

H, R, S, T, AH = ci('H'), ci('R'), ci('S'), ci('T'), ci('AH')
ALLY = range(H, AH + 1)            # ProjYr-11 .. ProjYr+15
HIST = range(H, R + 1)             # history (ProjYr-11 .. ProjYr-1)
PROJ = range(S, AH + 1)            # projection (ProjYr .. ProjYr+15)
FROM2 = range(H + 1, AH + 1)       # columns that need the year before
OFF = ci('U') - S                  # IdentFin/ResidFin year columns sit two columns to the right
# holder columns in IdentFin/ResidFin (first projection year): central bank, banks, other domestic, official, private
HOLD = {'DC': 'DE', 'DB': 'EA', 'DN': 'EW', 'XO': 'FS', 'XP': 'GN'}


def compute(book, sheet='BaseDB'):
    e = Engine(book, sheet)
    x = e.x
    Q = lambda nm: book.name(nm)

    def mf(r, c):                                         # VLOOKUP($Br, MacrofwData, col, FALSE)
        return vlookup(book, e(r, 2), 'MacrofwData', e(7, c))

    def nmf(key, c):                                      # VLOOKUP(key, NewMacrofwData, col, FALSE)
        return vlookup(book, key, 'NewMacrofwData', e(8, c))

    def ff(col, *crit):
        """Identified + residual financing: SUMIFS over IdentFin and ResidFin. col is a BaseDB year column
        (mapped to the financing sheets' year column) or a column letter there."""
        return e.both(col + OFF if isinstance(col, int) else col, *crit)

    def mix(c, col, fx, l1, l2, *crit):
        """Local + foreign * exchange rate + linked 1 * index 1 + linked 2 * index 2 of a financing SUMIFS."""
        cc = lambda cur: ff(col, *crit, 'K', '=' + cur)
        return (cc('Local') + cc('Foreign') * e(fx, c) + cc('Local-Linked 1') * e(l1, c)
                + cc('Local-Linked 2') * e(l2, c))

    def hcol(c, h):                                       # holder column of year c in IdentFin/ResidFin
        return cl(ci(HOLD[h]) + c - S)

    keyrow = {}

    def selflookup(key, col):
        """VLOOKUP(key, BaseDBData, col, FALSE) on this sheet: first row 9-333 whose column A matches."""
        col = val(col)
        if iserr(col):
            return col
        if key not in keyrow:
            keyrow[key] = next((r for r in range(9, 334) if cmp(e(r, 1), '=', key) is True), None)
        r = keyrow[key]
        return NA if r is None else (lambda v: 0 if v is None else v)(e(r, int(col)))

    # -- header rows: year, years from ProjYr, historical flag, columns in Macrofw / NewMacrofw --
    e.let(3, ALLY, lambda c: X(Q('ProjYr')) + e(4, c))
    e.let(4, FROM2, lambda c: x(4, c - 1) + 1)
    e.let(6, ALLY, lambda c: IF(cmp(e(4, c), '<', 0), lambda: True, lambda: False))
    e.let(7, ALLY, lambda c: match(e(4, c), book.hrow('MacrofwDates')))
    e.let(8, ALLY, lambda c: match(e(4, c), book.hrow('NewMacrofwDates')))
    unit = lambda: (lambda u: u if iserr(u) else text(u).lower())(Q('UnitScale'))
    for (r, col), lead, sep in (((9, 3), 'Total public debt (in ', ' '), ((32, 3), 'Pre-existing public debt (in ', ' '),
                                ((57, 3), 'Public debt issued in projection period (in ', ' '),
                                ((170, 3), 'Financing by type of transaction (in ', ' '),
                                ((288, 4), 'Nominal GDP level (', ' '), ((289, 4), 'Real GDP level (', ' ')):
        e.let(r, col, lambda c, lead=lead, sep=sep: cat(lead, unit(), sep, Q('CurrencyName'), ')'))

    # -- total public debt = pre-existing (rows 33-55) + issued in the projection period (rows 58-78) --
    pre = lambda r: r + 23 if r < 15 else r + 25                       # row of the same item in rows 33-55
    for r in (10, 12, 13, 14, 16, 17, 18, 19, 21, 22, 23, 24, 25, 26, 27, 29, 30):
        e.let(r, ALLY, lambda c, r=r: x(pre(r), c) + e(r + 48, c))

    # -- pre-existing debt: history from NewMacrofw, then the existing stock runs off --
    for r in (10, 12, 13, 14, 16, 17, 18, 19, 21, 22, 23, 24, 25, 26, 27, 29, 30):
        e.let(pre(r), 1, lambda c, r=r: cat(e(r, 1), '_H'))
    for r in (38, 39):
        e.let(r, 1, lambda c, r=r: e(r, 2))
    for r in (33, 35, 36, 37, 41, 43, 44, 54, 55):
        e.let(r, HIST, lambda c, r=r: nmf(e(r, 2), c))
    for r in (38, 39):                                                 # local-linked 1 and 2
        e.let(r, HIST, lambda c, r=r: mf(r, c))
    for r, pct in ((47, 116), (48, 117), (49, 118), (51, 120), (52, 121)):   # by holder: data, else share * total
        e.let(r, HIST, lambda c, r=r, pct=pct: iferror(X(nmf(e(r, 2), c)) * 1, lambda: x(pct, c) * e(33, c)))
        e.let(r, PROJ, lambda c, r=r, pct=pct: x(r, c - 1) - x(pct, R) * (x(197, c) + e(201, c) + e(205, c)))
    e.let(33, PROJ, lambda c: x(35, c) + e(36, c) + e(37, c))
    e.let(35, PROJ, lambda c: x(35, c - 1) - e(197, c))                 # local: less amortization
    e.let(36, PROJ, lambda c: (x(36, c - 1) / e(297, c - 1) - x(201, c) / e(296, c)) * e(297, c))   # foreign
    e.let(37, PROJ, lambda c: xsum([e(38, c), e(39, c)]))
    e.let(38, PROJ, lambda c: (x(38, c - 1) / e(328, c - 1) - x(206, c) / e(327, c)) * e(328, c))
    e.let(39, PROJ, lambda c: (x(39, c - 1) / e(330, c - 1) - x(207, c) / e(329, c)) * e(330, c))
    e.let(41, PROJ, lambda c: x(197, c + 1) + e(201, c + 1) + e(205, c + 1))     # short-term: next year's amort.
    e.let(43, PROJ, lambda c: xsum(e(r, j) for r in (197, 201, 205) for j in range(c + 2, c + 6)))
    e.let(44, PROJ, lambda c: x(33, c) - e(41, c) - e(43, c))
    e.let(46, ALLY, lambda c: x(47, c) + e(48, c) + e(49, c))
    e.let(50, ALLY, lambda c: x(51, c) + e(52, c))
    e.let(54, PROJ, lambda c: x(54, c - 1) - e(213, c))
    e.let(55, PROJ, lambda c: x(55, c - 1) - e(214, c))

    # -- debt issued in the projection period (IdentFin + ResidFin) --
    for r in (58, 60, 61, 62, 64, 65, 66, 69, 70, 71, 72, 73, 74, 75, 77, 78):
        e.let(r, 1, lambda c, r=r: cat(e(r - 48, 1), '_P'))
    gd = lambda c, cur, *crit: ff(c, 'Q', '=GGD', 'K', '=' + cur, *crit)
    e.let(58, PROJ, lambda c: x(60, c) + e(61, c) + e(62, c))
    e.let(60, PROJ, lambda c: gd(c, 'Local'))
    e.let(61, PROJ, lambda c: gd(c, 'Foreign') * e(297, c))
    e.let(62, PROJ, lambda c: gd(c, 'Local-Linked 1') * e(328, c) + gd(c, 'Local-Linked 2') * e(330, c))
    yr = lambda c, d: text(x(3, c) + d)
    e.let(64, PROJ, lambda c: mix(c, c, 297, 328, 330, 'Q', '=GGD', 'I', '=' + yr(c, 1)))       # matures in 1 yr
    e.let(66, PROJ, lambda c: mix(c, c, 297, 328, 330, 'Q', '=GGD', 'I', '>' + yr(c, 1), 'I', '<=' + yr(c, 5)))
    e.let(67, PROJ, lambda c: mix(c, c, 297, 328, 330, 'Q', '=GGD', 'I', '>' + yr(c, 5)))
    e.let(69, PROJ, lambda c: x(70, c) + e(71, c) + e(72, c))
    e.let(73, PROJ, lambda c: x(74, c) + e(75, c))
    for r, h in ((70, 'DC'), (71, 'DB'), (72, 'DN'), (74, 'XO'), (75, 'XP')):
        e.let(r, PROJ, lambda c, h=h: mix(c, hcol(c, h), 297, 328, 330, 'Q', '=GGD'))
    e.let(77, PROJ, lambda c: mix(c, c, 297, 328, 330, 'Q', '=GGD', 'L', '=Market'))
    e.let(78, PROJ, lambda c: mix(c, c, 297, 328, 330, 'Q', '=GGD', 'L', '=Nonmarket'))

    # -- in percent of GDP and percent of total debt --
    for r in (81, 83, 84, 85, 87, 89, 90, 92, 93, 94, 95, 96, 97, 98, 100, 101):
        e.let(r, 1, lambda c, r=r: cat(e(r - 71, 1), '_GDP'))
        e.let(r, ALLY, lambda c, r=r: x(r - 71, c) / e(288, c))
    for r in (104, 106, 107, 108, 110, 111, 112, 113, 115, 116, 117, 118, 119, 120, 121, 123, 124):
        e.let(r, 1, lambda c, r=r: cat(e(r - 94, 1), '_PCT'))
    for r in (104, 106, 107, 108, 110, 111, 112, 113, 123, 124):
        e.let(r, ALLY, lambda c, r=r: x(r - 94, c) / e(10, c))
    e.let(115, ALLY, lambda c: x(116, c) + e(117, c) + e(118, c))
    e.let(119, ALLY, lambda c: x(120, c) + e(121, c))
    for r in (116, 117, 118, 120, 121):                                # holder shares: data, else carried
        e.let(r, ALLY, lambda c, r=r: iferror(X(mf(r, c)) * 1, lambda: e(r, c - 1)))

    # -- debt dynamics (percent of GDP) --
    for r in list(range(127, 141)) + [142] + list(range(151, 166)) + list(range(268, 273)) \
            + [178, 179, 191, 192, 206, 207, 213, 214, 288, 289, 290, 291, 292, 294, 296, 297, 298, 299, 300, 301]:
        e.let(r, 1, lambda c, r=r: e(r, 2))
    e.let(127, FROM2, lambda c: x(81, c) - e(81, c - 1))                              # change in debt
    e.let(128, FROM2, lambda c: x(129, c) + e(132, c) + e(138, c))                    # identified flows
    for r, src in ((129, 177), (130, 178), (131, 179)):                               # primary deficit, rev., exp.
        e.let(r, FROM2, lambda c, src=src: x(src, c) / e(288, c))
    e.let(132, FROM2, lambda c: x(133, c) + e(136, c) + e(137, c))                    # automatic debt dynamics
    e.let(133, FROM2, lambda c: x(134, c) + e(135, c))                                # r - g differential
    e.let(134, FROM2, lambda c: x(278, c) * e(81, c - 1) / (1 + x(292, c)))           # real interest rate
    e.let(135, FROM2, lambda c: -x(292, c) * e(81, c - 1) / (1 + x(292, c)))          # real growth
    e.let(136, FROM2, lambda c: x(107, c - 1) * e(81, c - 1) * e(303, c)              # exchange rate
          / ((1 + x(292, c)) * (1 + x(308, c))))
    e.let(137, FROM2, lambda c: x(107, c - 1) * e(81, c - 1) * (x(294, c) - e(308, c))   # relative inflation
          / ((1 + x(292, c)) * (1 + x(294, c)) * (1 + x(308, c))))
    e.let(138, FROM2, lambda c: x(139, c) + e(140, c) + e(141, c))                    # other flows
    e.let(139, FROM2, lambda c: x(210, c) / e(288, c))
    e.let(140, FROM2, lambda c: (x(172, c) + e(173, c)) / e(288, c))
    e.let(141, FROM2, lambda c: -x(211, c) / e(288, c))
    e.let(142, FROM2, lambda c: x(127, c) - e(128, c))                                # residual
    e.let(143, FROM2, lambda c: x(127, c) - e(128, c))
    e.let(144, FROM2, lambda c: x(134, c) + e(137, c))
    e.let(145, FROM2, lambda c: IF(e(6, c), lambda: e(136, c), lambda: '…'))
    e.let(146, FROM2, lambda c: IF(e(6, c), lambda: e(142, c), lambda: x(142, c) + e(136, c)))
    e.let(147, FROM2, lambda c: IF(e(6, c), lambda: e(132, c), lambda: x(132, c) - e(136, c)))
    e.let(148, FROM2, lambda c: IF(e(6, c), lambda: e(128, c), lambda: x(128, c) - e(136, c)))
    # backward-looking decomposition
    e.let(151, FROM2, lambda c: x(81, c) - e(81, c - 1))
    e.let(152, FROM2, lambda c: x(153, c) + e(156, c) + e(161, c))
    for r, src in ((153, 177), (154, 178), (155, 179)):
        e.let(r, FROM2, lambda c, src=src: x(src, c) / e(288, c))
    e.let(156, FROM2, lambda c: x(157, c) + e(160, c))
    e.let(157, FROM2, lambda c: x(158, c) + e(159, c))
    e.let(158, FROM2, lambda c: x(81, c - 1) * (x(273, c) - x(294, c) * (1 + x(292, c))) / e(165, c))
    e.let(159, FROM2, lambda c: -x(81, c - 1) * e(292, c) / e(165, c))
    e.let(160, FROM2, lambda c: x(84, c - 1) * (x(300, c) * (1 + x(275, c))) / e(165, c))
    e.let(161, FROM2, lambda c: x(162, c) + e(163, c))
    e.let(162, FROM2, lambda c: x(210, c) / e(288, c))
    e.let(163, FROM2, lambda c: (x(172, c) + e(173, c)) / e(288, c))
    e.let(164, FROM2, lambda c: x(151, c) - e(152, c))
    e.let(165, FROM2, lambda c: (1 + x(292, c)) * (1 + x(294, c)))
    e.let(167, FROM2, lambda c: IF(e(6, c), lambda: e(160, c), lambda: '…'))
    e.let(168, FROM2, lambda c: IF(e(6, c), lambda: e(164, c), lambda: x(164, c) + e(160, c)))

    # -- financing by type of transaction --
    e.let(171, ALLY, lambda c: x(172, c) + e(173, c) + e(176, c))
    e.let(173, ALLY, lambda c: x(174, c) + e(175, c))
    for r in (172, 174, 175, 306, 311, 312, 313, 314, 316, 317, 318, 319, 320, 321, 326):
        e.let(r, ALLY, lambda c, r=r: mf(r, c))
    e.let(176, ALLY, lambda c: x(177, c) + e(180, c) + e(195, c) + e(210, c) - e(211, c))   # gross financing need
    e.let(177, ALLY, lambda c: x(179, c) - e(178, c))                                       # primary deficit
    for r in (178, 179, 210, 211, 288, 289, 290, 291, 292, 294, 296, 297, 298):
        e.let(r, ALLY, lambda c, r=r: nmf(e(r, 2), c))
    hist_key = lambda r, c: IF(e(6, c), lambda: _left(e(r, 2), _len(e(r, 2)) - 2), lambda: e(r, 2))
    for r in (182, 186, 190, 197, 201, 205):                         # existing debt: drop "_H" for history
        e.let(r, ALLY, lambda c, r=r: nmf(hist_key(r, c), c))
    for r, n in ((191, '01'), (192, '02'), (206, '01'), (207, '02')):   # linked: series 1/2 code in projection
        e.let(r, ALLY, lambda c, r=r, n=n: vlookup(book, IF(e(6, c), lambda: e(r, 2),
                                                          lambda: cat(_left(e(r, 2), _len(e(r, 2)) - 1), n)),
                                                   'MacrofwData', e(7, c)))
    for r, parts in ((180, (181, 185, 189)), (181, (182, 183, 184)), (185, (186, 187, 188)),
                     (189, (190, 193, 194)), (196, (197, 198, 199)), (200, (201, 202, 203)),
                     (204, (205, 208, 209))):
        e.let(r, ALLY, lambda c, p=parts: x(p[0], c) + e(p[1], c) + e(p[2], c))
    e.let(195, HIST, lambda c: iferror(x(196, c) + e(200, c) + e(204, c), lambda: mf(195, c)))
    e.let(195, PROJ, lambda c: x(196, c) + e(200, c) + e(204, c))

    # interest (GGEI) and amortization (GGFA) of new debt, by currency and marketability; first projection year
    # can be overridden on the Questions sheet
    def newdebt(r, item, cur, mkt, fx=None, l1=None, l2=None, switch=None, override=None):
        def flow(c):
            sf = lambda k: ff(c, 'Q', '=' + item, 'K', '=' + k, 'L', '=' + mkt)
            if cur == 'Local':
                return sf('Local')
            if cur == 'Foreign':
                return sf('Foreign') * e(fx, c)
            return sf('Local-Linked 1') * e(l1, c) + sf('Local-Linked 2') * e(l2, c)
        e.let(r, S, lambda c: IF(Q(switch), lambda: Q(override) if isinstance(override, str) else override,
                                 lambda: flow(c)))
        e.let(r, range(T, AH + 1), flow)
    newdebt(183, 'GGEI', 'Local', 'Market', switch='SwitchOverrideLC', override='OverrideIntLC')
    newdebt(184, 'GGEI', 'Local', 'Nonmarket', switch='SwitchOverrideLC', override=0)
    newdebt(187, 'GGEI', 'Foreign', 'Market', 296, switch='SwitchOverrideFX', override='OverrideIntFX')
    newdebt(188, 'GGEI', 'Foreign', 'Nonmarket', 296, switch='SwitchOverrideFX', override=0)
    newdebt(193, 'GGEI', 'Linked', 'Market', l1=327, l2=329, switch='SwitchOverrideLL', override='OverrideIntLL')
    newdebt(194, 'GGEI', 'Linked', 'Nonmarket', l1=327, l2=329, switch='SwitchOverrideLL', override=0)
    newdebt(198, 'GGFA', 'Local', 'Market', switch='SwitchOverrideLC', override='OverrideAmortLC')
    newdebt(199, 'GGFA', 'Local', 'Nonmarket', switch='SwitchOverrideLC', override=0)
    newdebt(202, 'GGFA', 'Foreign', 'Market', 296, switch='SwitchOverrideFX', override='SwitchOverrideFX')
    newdebt(203, 'GGFA', 'Foreign', 'Nonmarket', 296, switch='SwitchOverrideFX', override=0)
    newdebt(208, 'GGFA', 'Linked', 'Market', l1=327, l2=329, switch='SwitchOverrideLL', override='SwitchOverrideLL')
    newdebt(209, 'GGFA', 'Linked', 'Nonmarket', l1=327, l2=329, switch='SwitchOverrideLL', override=0)
    for r in (213, 214):                                              # amortization by instrument type
        e.let(r, ALLY, lambda c, r=r: iferror(nmf(e(r, 2), c), lambda: NA))
    for r, (a, b) in zip(range(215, 221), ((183, 184), (187, 188), (193, 194), (198, 199), (202, 203), (208, 209))):
        e.let(r, PROJ, lambda c, a=a, b=b: x(a, c) + e(b, c))

    # -- new issuance (gross, by issue year) by holder, maturity and currency, and its shares --
    yeq = lambda c: '=' + text(e(3, c))
    e.let(223, PROJ, lambda c: mix(c, c, 296, 327, 329, 'Q', '=GGD', 'G', yeq(c)))
    for r, h in ((225, 'DC'), (226, 'DB'), (227, 'DN'), (228, 'XO'), (229, 'XP')):
        e.let(r, PROJ, lambda c, h=h: mix(c, hcol(c, h), 296, 327, 329, 'G', yeq(c), 'Q', '=GGD'))
    for top, mat in ((231, '<=1'), (235, '>1')):                      # short-term / medium and long-term
        e.let(top, PROJ, lambda c, t=top: x(t + 1, c) + e(t + 2, c) + e(t + 3, c))
        iss = lambda c, cur, mat=mat: ff(c, 'Q', '=GGD', 'G', yeq(c), 'K', '=' + cur, 'F', mat)
        e.let(top + 1, PROJ, lambda c, iss=iss: iss(c, 'Local'))
        e.let(top + 2, PROJ, lambda c, iss=iss: iss(c, 'Foreign') * e(296, c))
        e.let(top + 3, PROJ, lambda c, iss=iss: iss(c, 'Local-Linked 1') * e(327, c)
              + iss(c, 'Local-Linked 2') * e(329, c))
    byc = lambda c, cur: ff(c, 'Q', '=GGD', 'G', yeq(c), 'K', '=' + cur)
    e.let(240, PROJ, lambda c: byc(c, 'Local'))
    e.let(241, PROJ, lambda c: x(296, c) * byc(c, 'Foreign'))
    e.let(242, PROJ, lambda c: x(327, c) * byc(c, 'Local-Linked 1') + x(329, c) * byc(c, 'Local-Linked 2'))
    e.let(243, PROJ, lambda c: x(327, c) * byc(c, 'Local-Linked 1'))
    e.let(244, PROJ, lambda c: x(329, c) * byc(c, 'Local-Linked 2'))
    for r in range(248, 253):
        e.let(r, PROJ, lambda c, r=r: x(r - 23, c) / xsum(e(j, c) for j in range(225, 230)))
    for r in range(254, 262):
        e.let(r, PROJ, lambda c, r=r: x(r - 23, c) / xsum(e(j, c) for j in (232, 233, 234, 236, 237, 238)))
    for r in range(263, 266):
        e.let(r, PROJ, lambda c, r=r: x(r - 23, c) / xsum(e(j, c) for j in range(240, 243)))

    # -- gross financing need, debt service, interest rates (percent) --
    e.let(268, ALLY, lambda c: x(176, c) / e(288, c))
    for r, (a, b) in ((269, (180, 195)), (270, (181, 196)), (271, (185, 200)), (272, (189, 204))):
        e.let(r, ALLY, lambda c, a=a, b=b: (x(a, c) + e(b, c)) / e(288, c))
    e.let(273, FROM2, lambda c: (x(274, c) * e(12, c - 1) + x(275, c) * e(13, c - 1) + x(276, c) * e(14, c - 1))
          / e(10, c - 1))                                             # effective interest rate
    e.let(274, FROM2, lambda c: x(181, c) / e(12, c - 1))
    e.let(275, FROM2, lambda c: iferror(x(185, c) / e(13, c - 1), lambda: 0))
    e.let(276, FROM2, lambda c: iferror(x(189, c) / e(14, c - 1), lambda: 0))
    e.let(277, FROM2, lambda c: x(180, c) / e(10, c - 1))
    e.let(278, FROM2, lambda c: (1 + x(277, c)) / (1 + x(294, c)) - 1)   # real effective rate

    # marginal rates on new issuance: contributions from IdentFin/ResidFin, #N/A when nothing is issued
    def marginal(c, gadl, *crit):
        return IF(cmp(selflookup(gadl, e(5, c)), '<=', 0), lambda: NA, lambda: ff(c, *crit))
    e.let(279, PROJ, lambda c: marginal(c, 'GADL', 'Q', '=IRContribT'))
    e.let(280, PROJ, lambda c: marginal(c, 'GADL_CL', 'Q', '=IRContribC', 'K', '=Local'))
    for r, k, gadl in ((281, 'Foreign', 'GADL_CF'), (283, 'Local-Linked 1', 'GADL_CI1'),
                       (284, 'Local-Linked 2', 'GADL_CI2')):
        e.let(r, PROJ, lambda c, k=k, gadl=gadl: NA if iserr(ff(c, 'Q', '=IRContribC', 'K', '=' + k).v)
              else marginal(c, gadl, 'Q', '=IRContribC', 'K', '=' + k))
    e.let(282, PROJ, lambda c: x(283, c) * (x(243, c) / e(242, c)) + x(284, c) * (x(244, c) / e(242, c)))

    # -- macro series --
    e.let(293, range(ci('Q'), AH + 1), lambda c: _stdev([e(292, j) for j in range(c - 9, c + 1)]))
    e.let(299, range(H + 2, AH + 1), lambda c: (x(296, c) / e(296, c - 1)) - 1)
    e.let(300, range(H + 2, AH + 1), lambda c: (x(297, c) / e(297, c - 1)) - 1)
    e.let(301, range(H + 2, ci('W') + 1), lambda c: x(298, c) / e(298, c - 1) - 1)
    e.let(302, ALLY, lambda c: x(296, c) * e(307, c) / e(290, c))
    e.let(303, FROM2, lambda c: (x(302, c) / e(302, c - 1)) - 1)
    e.let(305, ALLY, lambda c: iferror(X(mf(305, c)) * 1, lambda: x(305, c - 1) * (1 + x(291, c))))
    e.let(307, ALLY, lambda c: iferror(X(mf(307, c)) * 1, lambda: e(307, c - 2)))
    e.let(308, ALLY, lambda c: X(mf(308, c)) / 100)
    e.let(309, ALLY, lambda c: X(mf(309, c)) / 100)
    e.let(310, ALLY, lambda c: -x(177, c) / e(288, c))
    e.let(315, ALLY, lambda c: (-x(312, c) - e(313, c)) / e(314, c))
    e.let(322, ALLY, lambda c: x(10, c) / (x(178, c) + e(211, c)))
    e.let(324, ALLY, lambda c: x(211, c) / e(288, c))
    for r in (327, 328, 329, 330):
        e.let(r, ALLY, lambda c, r=r: iferror(mf(r, c), lambda: 1))
    e.run()


def _len(s):
    s = val(s)
    return s if iserr(s) else len(text(s))


def _left(s, n):
    s, n = val(s), val(n)
    return err(s, n) or text(s)[:max(int(n), 0)]


def _stdev(vs):
    e = err(*vs)
    if e:
        return e
    xs = [v for v in vs if isnumber(v)]
    if len(xs) < 2:
        return '#DIV/0!'
    m = sum(xs) / len(xs)
    return (sum((v - m) ** 2 for v in xs) / (len(xs) - 1)) ** 0.5
