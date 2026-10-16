"""Input-processing sheets of the MAC SRDSF template.

- Questions:  the settings questionnaire. Only its formula cells are ported: country attributes looked up from the
  Config country table, the debt-coverage "normal settings", cross-holding totals, year headers, shock defaults and
  the contingent-liability calibration.
- Macrofw:    the macro-framework input sheet. Year header and lookup row, series codes (IFS code & mnemonic) and the
  derived lines (deflator, growth rates, balances, interest/debt sums, ratios to GDP, extrapolated exchange rates,
  debt-holder shares).
- NewMacrofw: re-lays Macrofw out on the template's own year grid (J = first year), with units text, the first/last
  year each series is needed (from Config's dictionary), growth rates and a few derived lines (REER gap, bank
  assets).
- Config:     the parameter sheet. Only its formula cells are ported: department counters and fanchart groups of the
  country list, the three fanchart histogram blocks (centre on median, rank, sort), fanchart and GFN settings, the
  GFN shocks table (historical growth, exchange rate, deflator), the GFN convergence test, banking-crisis cut-offs
  and the dictionary's first/last year columns.
"""
import math
from bisect import bisect_left

from .book import ci
from .xl import NA, VALUE, calc, eq, err, iserr, isnumber, match, num, xsum

SHEETS = ['Questions', 'Macrofw', 'NewMacrofw', 'Config']

QUIRKS = [
    "Config!G83 counts its department over F$5:F177 instead of F$5:F83 (the formula was mis-copied), so the "
    "'Non-MAC' running counter jumps at Nauru (Non-MAC-10).",
    "Config!DD49 and DD50 hold no value in the template: the cell shows its own formula text "
    "('=Signals!$A$2:$J$2', '=Signals!$A$3:$J$18'), which is reproduced as that text.",
    "Config!L (fanchart group) falls back to EM-DIVERSIFIED for an EM country in neither the diversified nor the "
    "commodity sample; Config!AH19 likewise falls back to the 'BN' histogram, but AH20 returns #N/A.",
    "Config!AT581:AU1141 (a fourth histogram block) has no data, so MEDIAN of an empty range gives #NUM! in all "
    "1,122 cells.",
    "Config!AD47 keeps the literal weights of the template (15*1+8.4*0 for EM, 30*1+12.2*0 otherwise).",
    "Questions!E4:E9 look the sample country ('*** MAC DSA sample ***') up in CtryTab, which starts one row below "
    "it, so every country attribute (IFS code, currency union, AE/EM, ...) is #N/A and that #N/A flows into all "
    "IFScode&mnemonic series codes of Macrofw and the units labels of NewMacrofw.",
    "Macrofw!107:111 (debt-holder shares) divide by row 99 in every year, although the holder rows carry the "
    "text 'N.A.' in years without Arslanalp-Tsuda data, so those years (G, U:AA and AD on) are #VALUE!.",
    "NewMacrofw!G3 uses a nested IF with no final else branch (it cannot be reached).",
]


# ---------------------------------------------------------------- Excel helpers
def ref(v):
    """A cell reference as a formula's result: a blank cell reads as 0."""
    return 0 if v is None else v


def xtext(v):
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


def concat(*vals):
    for v in vals:
        if iserr(v):
            return v
    return ''.join(xtext(v) for v in vals)


def is_(a, b):
    """Excel a=b with error propagation: an error, else True/False."""
    if iserr(a):
        return a
    if iserr(b):
        return b
    return eq(a, b)


def nums(vals):
    """The numbers of a range (text, blanks, booleans skipped); an error in it is returned as a string."""
    out = []
    for v in vals:
        if iserr(v):
            return v
        if isnumber(v):
            out.append(v)
    return out


def xmax(vals):
    xs = nums(vals)
    return xs if isinstance(xs, str) else (max(xs) if xs else 0)


def xmin(vals):
    xs = nums(vals)
    return xs if isinstance(xs, str) else (min(xs) if xs else 0)


def median(vals):
    xs = nums(vals)
    if isinstance(xs, str):
        return xs
    if not xs:
        return '#NUM!'
    xs.sort()
    n = len(xs)
    return xs[n // 2] if n % 2 else (xs[n // 2 - 1] + xs[n // 2]) / 2


def stdev(vals):
    xs = nums(vals)
    if isinstance(xs, str):
        return xs
    if len(xs) < 2:
        return '#DIV/0!'
    m = sum(xs) / len(xs)
    return math.sqrt(sum((x - m) ** 2 for x in xs) / (len(xs) - 1))


def ranks_asc(vals):
    """RANK(x, vals, 1) for every x of vals: 1 + number of values below x (ties share the lowest rank)."""
    xs = nums(vals)
    if isinstance(xs, str):
        return [xs] * len(vals)
    xs.sort()
    out = []
    for v in vals:
        if iserr(v):
            out.append(v)
        elif not isnumber(v):
            out.append(VALUE)
        else:
            out.append(bisect_left(xs, v) + 1)
    return out


def countif_eq(vals, x):
    """COUNTIF(range, "="&x)."""
    return sum(1 for v in vals if (v in (None, '') and x in (None, '')) or (v is not None and eq(v, x)))


def sumif_ne(keys, vals, x):
    """SUMIF(keys, "<>"&x, vals): numbers whose key differs from x (blank keys differ from any text)."""
    t = 0.0
    for k, v in zip(keys, vals):
        if k is not None and eq(k, x):
            continue
        if iserr(v):
            return v
        if isnumber(v):
            t += v
    return t


class Table:
    """A range read once per compute call, for VLOOKUP(key, range, col, FALSE) and MATCH over its rows."""

    def __init__(self, book, nm):
        sh, c0, r0, c1, r1 = book.area(nm)
        S = book[sh]
        self.rows = [[S.get(r, c) for c in range(c0, c1 + 1)] for r in range(r0, r1 + 1)]
        self.index = {}
        for row in self.rows:
            k = row[0]
            if k is None:
                continue
            k = k.lower() if isinstance(k, str) else k
            self.index.setdefault(k, row)

    def vlookup(self, key, col):
        """VLOOKUP(key, table, col, FALSE); a blank result reads as 0."""
        if iserr(key):
            return key
        if iserr(col):
            return col
        if isinstance(col, bool) or not isnumber(col):
            return VALUE
        col = int(col)
        if col < 1:
            return VALUE
        if col > len(self.rows[0]):
            return '#REF!'
        k = key.lower() if isinstance(key, str) else key
        row = self.index.get(k)
        return NA if row is None else ref(row[col - 1])


def rowvals(S, r, c0, c1):
    return [S.get(r, c) for c in range(c0, c1 + 1)]


def colvals(S, c, r0, r1):
    return [S.get(r, c) for r in range(r0, r1 + 1)]


def cols(a, b):
    return range(ci(a), ci(b) + 1)


# ---------------------------------------------------------------- Questions
def questions(book):
    Q = book['Questions']
    Cfg = book['Config']
    cname = book.name('Cname')
    ctry = Table(book, 'CtryTab')
    hdr = book.hrow('CtryTabID')
    # Section A: country attributes from the Config country list
    for r in range(4, 9):
        Q.set(r, 5, ctry.vlookup(cname, match(Q.get(r, 4), hdr)))
    Q.set(9, 5, Table(book, 'FlexERList').vlookup(Q.get(7, 5), 2))       # flexible arrangement?
    # Section B: current-year header
    proj = book.name('ProjYr')
    for c in (4, 5):
        Q.set(14, c, proj)
    # Section C: normal debt-coverage setting of each subsector for the chosen perimeter
    cov = Table(book, 'Config!$O$21:$W$26')
    cov_hdr = rowvals(Cfg, 21, ci('O'), ci('W'))
    for r in range(24, 32):
        Q.set(r, 4, cov.vlookup(Q.get(21, 3), match(Q.get(r, 2), cov_hdr)))
    # cross holdings: row totals excluding the own subsector, column totals likewise
    G, N = ci('G'), ci('N')
    hdr23 = rowvals(Q, 23, G, N)
    for r in range(24, 32):
        Q.set(r, ci('O'), sumif_ne(hdr23, rowvals(Q, r, G, N), Q.get(r, 6)))
    fcol = colvals(Q, 6, 24, 31)
    for c in range(G, N + 1):
        Q.set(32, c, sumif_ne(fcol, colvals(Q, c, 24, 31), Q.get(23, c)))
    Q.set(32, ci('O'), xsum(colvals(Q, ci('O'), 24, 31)))
    # Section D: years of the historical indicators; marginal effective rates not provided
    for i, c in enumerate(range(3, 8)):
        Q.set(46, c, calc(lambda p: p - 5 + i, proj))
        Q.set(48, c, NA)
    # REER: AE/EM classification text
    ae = is_(book.name('AEEM'), 'AE')
    Q.set(69, 3, ae if iserr(ae) else ('Advanced Economy' if ae else 'Emerging Market'))
    # natural disaster shock: defaults and user-defined copies
    Q.set(79, 4, ref(Q.get(79, 3)))
    on = is_(Q.get(76, 3), 'On')
    for r, size in ((82, -0.013), (83, -0.035)):
        Q.set(r, 3, on if iserr(on) else (size if on else 0))
        Q.set(r, 4, Q.get(r, 3))
    # contingent liabilities: subnational and SOE holdings from the macro framework, latest historical year
    mf = Table(book, 'MacrofwData')
    last = match(-1, book.hrow('MacrofwDates'))
    for r, c, code in ((90, 3, 'FASAOS'), (90, 4, 'FOSAOG'), (92, 3, 'FASAON'), (92, 4, 'FOSAON')):
        Q.set(r, c, mf.vlookup(code, last))
    soe = Q.get(94, 3)
    block = [Q.get(r, c) for r in range(90, 94 if soe else 92) for c in range(3, 8)]
    Q.set(94, 7, soe if iserr(soe) else xsum(block))


# ---------------------------------------------------------------- Macrofw
MF_YEARS = cols('G', 'AS')            # 2000 .. ProjYr+16 (data columns)
MF_CODE_ROWS = [(6, 60), (63, 72), (76, 89), (91, 96), (99, 111), (113, 116), (118, 126), (128, 131), (133, 133),
                (157, 181), (183, 207), (209, 233), (235, 259), (261, 285), (287, 311)]
MF_ANNUAL = {76, 77, 80, 81, 92, 116}  # IFScode & mnemonic & ".A"
MF_FIXED = {78: '', 79: '', 85: '001', 86: '001', 96: '111'}   # fixed country prefix instead of IFScode
MF_UNITS = [82, 83, 92, 99, 100, 101, 102, 103, 104, 105, 106, 114, 116, 122, 123, 124]
MF_FIN = [(158, 181), (183, 207), (209, 233), (235, 259), (261, 285), (287, 311)]   # financing rows


def macrofw(book):
    M = book['Macrofw']
    proj = book.name('ProjYr')
    g = lambda r, c: M.get(r, c)
    # year header and years relative to the projection year
    M.set(3, ci('G'), book.name('StartYrDataIn'))
    for c in range(ci('H'), ci('DH') + 1):
        M.set(3, c, calc(lambda y: y + 1, g(3, c - 1)))
    for c in MF_YEARS:
        M.set(5, c, calc(lambda y, p: y - p, g(3, c), proj))
    # GDP deflator and growth rates (nominal, real, deflator)
    for c in cols('G', 'AO'):
        M.set(8, c, calc(lambda n, r: n / r * 100, g(6, c), g(7, c)))
    for c in cols('H', 'AO'):
        for r, src in ((9, 6), (10, 7), (11, 8)):
            M.set(r, c, calc(lambda a, b: 100 * (a - b) / b, g(src, c), g(src, c - 1)))
    # exchange rates beyond the data: extrapolate the last change
    for r in (13, 14):
        for c in cols('AP', 'AS'):
            M.set(r, c, calc(lambda a, b: a / b * a, g(r, c - 1), g(r, c - 2)))
    for c in MF_YEARS:
        # interest by currency, interest by holder, revenue items, debt by currency, debt totals
        for r in (18, 23, 31, 36, 45):
            M.set(r, c, xsum(g(r + k, c) for k in range(1, 5)))
        M.set(17, c, calc(lambda e, i: e - i, g(16, c), g(18, c)))        # non-interest expenditure
        M.set(29, c, calc(lambda a, b: a - b, g(28, c), g(30, c)))        # non-interest revenue
        M.set(15, c, calc(lambda a, b: a - b, g(29, c), g(17, c)))        # primary balance
        M.set(51, c, calc(lambda a, y: 100 * a / y, g(16, c), g(6, c)))   # expenditure / GDP
        M.set(52, c, calc(lambda a, y: 100 * a / y, g(45, c), g(6, c)))   # debt / GDP
        M.set(53, c, calc(lambda a, d: 100 * a / d, g(47, c), g(45, c)))  # share of foreign-currency debt
        M.set(54, c, calc(lambda a, y: 100 * a / y, g(15, c), g(6, c)))   # primary balance / GDP
    # placeholders not provided
    for r, a, b in ((63, 'AC', 'AC'), (64, 'AC', 'AC'), (65, 'AC', 'AC'), (66, 'Y', 'AC'), (67, 'Y', 'AC'),
                    (68, 'Y', 'AC'), (69, 'Y', 'AC'), (70, 'Y', 'AC'), (71, 'AD', 'AI'), (72, 'AD', 'AI')):
        for c in cols(a, b):
            M.set(r, c, NA)
    # deflator inflation from the deflator index (central database)
    for c in cols('AH', 'AS'):
        M.set(78, c, calc(lambda a, b: a / b * 100 - 100, g(79, c), g(79, c - 1)))
    # debt by holder (Arslanalp-Tsuda), latest year scaled to the framework debt
    AC, AB = ci('AC'), ci('AB')
    M.set(99, AC, ref(g(45, AC)))
    for r in range(100, 107):
        M.set(r, AC, calc(lambda a, b, d: a / b * d, g(r, AB), g(99, AB), g(99, AC)))
    M.set(82, AC, ref(g(102, AC)))
    M.set(83, AC, calc(lambda y1, y0, x: y1 / y0 * x, g(6, AC), g(6, AB), g(83, AB)))
    for c in MF_YEARS:
        M.set(88, c, ref(g(89, c)))
        for r, src in ((107, 101), (108, 102), (109, 103), (110, 105), (111, 106)):   # holder shares
            M.set(r, c, calc(lambda a, d: a / d, g(src, c), g(99, c)))
    # series codes
    ifs = book.name('IFScode')
    for r0, r1 in MF_CODE_ROWS:
        for r in range(r0, r1 + 1):
            if r in MF_FIXED:
                M.set(r, 3, concat(MF_FIXED[r], g(r, 1), '.A' if r in (78, 79) else ''))
            else:
                M.set(r, 3, concat(ifs, g(r, 1), '.A' if r in MF_ANNUAL else ''))
    unit = book.name('UnitScale')
    for r in MF_UNITS:
        M.set(r, 6, ref(unit))
    # financing rows: database name when the row is flagged
    fdb = book.name('FrameDb')
    for r0, r1 in MF_FIN:
        for r in range(r0, r1 + 1):
            d = g(r, 4)
            if iserr(d) or isinstance(d, str) and d:
                M.set(r, 2, d if iserr(d) else VALUE)
            else:
                M.set(r, 2, ref(fdb) if num(d) else '')


# ---------------------------------------------------------------- NewMacrofw
NM_YEARS = cols('J', 'AV')            # FirstYr .. ProjYr+16; Macrofw column = this column - 3
# row: (first col, last col, Macrofw rows summed)
NM_COPY = [
    (8, 'J', 'AV', [7]),       # real GDP
    (11, 'J', 'AV', [8]),      # GDP deflator
    (14, 'J', 'AV', [6]),      # nominal GDP
    (18, 'T', 'AV', [28]),     # total revenues
    (19, 'T', 'AV', [29]),     # noninterest revenues
    (20, 'T', 'AV', [30]),     # interest revenues
    (22, 'T', 'AV', [16]),     # total expenditures
    (23, 'T', 'AV', [17]),     # noninterest expenditures
    (24, 'T', 'AF', [18]),     # interest expenditures
    (25, 'T', 'AF', [19]),     # interest on local currency debt
    (26, 'AE', 'AV', [24]),    # o/w existing local currency debt
    (27, 'T', 'AF', [20]),     # interest on foreign currency debt
    (28, 'AE', 'AV', [25]),    # o/w existing foreign currency debt
    (29, 'T', 'AV', [21, 22]),  # interest on local-linked debt
    (30, 'AE', 'AV', [26, 27]),  # o/w existing local-linked debt
    (32, 'J', 'AV', [15]),     # primary balance
    (36, 'J', 'AV', [45]),     # total public debt
    (39, 'J', 'AV', [46]),     # by currency: local
    (40, 'J', 'AV', [47]),     # foreign
    (41, 'J', 'AV', [48, 49]),  # local-linked
    (51, 'AE', 'AE', [46]),    # by law: domestic
    (51, 'AF', 'AF', [63]),
    (52, 'AF', 'AF', [64]),
    (53, 'AF', 'AF', [65]),
    (56, 'AB', 'AF', [66]),    # by maturity
    (57, 'AB', 'AF', [67]),
    (58, 'AB', 'AF', [68]),
    (61, 'AB', 'AF', [69]),    # by market
    (62, 'AB', 'AF', [70]),
    (64, 'T', 'AV', [31]),     # financial assets
    (65, 'T', 'AV', [32]),
    (66, 'T', 'AV', [33]),
    (67, 'T', 'AV', [34, 35]),
    (69, 'AE', 'AV', [37]),
    (70, 'AE', 'AV', [38]),
    (71, 'AE', 'AV', [39, 40]),
    (73, 'AG', 'AL', [71]),
    (74, 'AG', 'AL', [72]),
    (76, 'AE', 'AV', [41]),
    (78, 'AE', 'AV', [42]),    # other debt-creating flows
    (79, 'AE', 'AV', [43]),
    (80, 'AE', 'AV', [44]),
    (88, 'J', 'AV', [13]),     # exchange rate, average
    (90, 'J', 'AV', [14]),     # exchange rate, end of period
    (92, 'AE', 'AL', [56]),    # REER
    (97, 'AC', 'AE', [123]),   # bank assets
    (98, 'AC', 'AV', [124]),   # bank claims on government
    (99, 'AC', 'AE', [122]),   # tier 1 capital
    (100, 'AC', 'AE', [120]),  # loan-to-deposit
    (101, 'AC', 'AE', [119]),  # 3-year change in private credit
    (102, 'AC', 'AE', [118]),  # credit gap
    (103, 'AC', 'AE', [121]),  # mispricing index
]
NM_HOLDER = [(44, 101), (45, 102), (46, 103), (47, 105), (48, 106)]   # debt by holder: numbers only
NM_GROWTH = [(9, 8), (12, 11), (15, 14), (89, 88), (91, 90)]
NM_DICT_ROWS = [8, 9, 11, 12, 14, 15, 18, 19, 20, 22, 23, 24, 25, 26, 27, 28, 29, 30, 32, 33, 36, 39, 40, 41, 44,
                45, 46, 47, 48, 51, 52, 53, 56, 57, 58, 61, 62, 64, 65, 66, 67, 69, 70, 71, 73, 74, 76, 78, 79, 80,
                83, 84, 85, 88, 89, 90, 91, 92, 94, 97, 98, 99, 100, 101, 102, 103]
NM_UNIT_ROWS = [14, 18, 19, 20, 22, 23, 24, 25, 26, 27, 28, 29, 30, 32, 33, 36, 39, 40, 41, 44, 45, 46, 47, 48, 51,
                52, 53, 56, 57, 58, 61, 62, 64, 65, 66, 67, 69, 70, 71, 73, 74, 76, 78, 79, 80, 83, 84, 85, 97, 98,
                99]


def newmacrofw(book):
    N, M = book['NewMacrofw'], book['Macrofw']
    proj, mt = book.name('ProjYr'), book.name('MTHorizon')
    g = lambda r, c: N.get(r, c)
    # year header and years relative to the projection year
    N.set(4, ci('J'), book.name('FirstYr'))
    for c in NM_YEARS[1:]:
        N.set(4, c, calc(lambda y: y + 1, g(4, c - 1)))
    for c in NM_YEARS:
        N.set(6, c, calc(lambda y, p: y - p, g(4, c), proj))
    # horizon check
    top = xmax(rowvals(N, 4, 1, max((c for r, c in N.cells if r == 4), default=1)))
    end = calc(lambda p, m: p + m, proj, mt)
    e = iserr(top) and top or iserr(end) and end
    if e:
        N.set(3, ci('G'), e)
    elif top == end:
        N.set(3, ci('G'), 'Ok')
    elif top < end:
        N.set(3, ci('G'), 'Insufficient observations in MT horizon, extend dates')
    else:
        N.set(3, ci('G'), 'Years exceed MT horizon')
    # units labels
    unit, base, cur = book.name('UnitScale'), book.name('GDPBaseYr'), book.name('CurrencyName')
    N.set(8, ci('G'), concat(unit, ' ', base, ' ', cur))
    N.set(11, ci('G'), concat('Index, ', base, '=100'))
    for r in NM_UNIT_ROWS:
        N.set(r, ci('G'), concat(unit, ' ', cur))
    for r in (88, 90):
        N.set(r, ci('G'), concat(cur, ' per ', book.name('ERBase')))
    # first / last year each series is needed (Config dictionary)
    dic = Table(book, 'Dictionary')
    for r in NM_DICT_ROWS:
        for c in (ci('H'), ci('I')):
            N.set(r, c, dic.vlookup(N.get(r, 1), g(5, c)))
    # series copied from Macrofw (sums of sub-series where the framework splits them)
    for r, a, b, src in NM_COPY:
        for c in cols(a, b):
            vals = [M.get(s, c - 3) for s in src]
            N.set(r, c, ref(vals[0]) if len(vals) == 1 else calc(lambda *v: sum(v), *vals))
    for r, s in NM_HOLDER:
        for c in NM_YEARS:
            v = M.get(s, c - 3)
            N.set(r, c, v if isnumber(v) else NA)
    # growth rates
    for r, s in NM_GROWTH:
        for c in NM_YEARS[1:]:
            N.set(r, c, calc(lambda a, b: a / b - 1, g(s, c), g(s, c - 1)))
    # REER gap: team assessment, then moved with the REER
    AF = ci('AF')
    N.set(93, AF, ref(book['Questions'].get(68, 3)))
    for c in cols('AG', 'AJ'):
        N.set(93, c, calc(lambda p, a, b: p + (a / b - 1), g(93, c - 1), g(92, c), g(92, c - 1)))
    # bank assets grow with nominal GDP after the data
    for c in cols('AF', 'AV'):
        N.set(97, c, calc(lambda p, gr: p * (1 + gr), g(97, c - 1), g(15, c)))


# ---------------------------------------------------------------- Config
# fanchart histogram blocks: (t+5 column, rank column, centred value column, obs column, sorted value column, rows)
HIST = [('AS', 'AT', 'AU', 'AW', 'AX', 8, 568),     # advanced economies
        ('BI', 'BJ', 'BK', 'BM', 'BN', 8, 460),     # EM diversified exporters
        ('BY', 'BZ', 'CA', 'CC', 'CD', 8, 300)]     # EM commodity exporters
# dictionary first / last year (F = FirstYr, P = ProjYr, M = MTHorizon), by rows
DICT_YEARS = [(6, 6, 'F', 'P+M'), (7, 7, 'F+1', 'P+M'), (8, 8, 'F', 'P+M'), (9, 9, 'F+1', 'P+M'),
              (10, 10, 'F', 'P+M'), (11, 11, 'F+1', 'P+M'), (12, 16, 'P-11', 'P+M'), (17, 18, 'P-11', 'P-1'),
              (19, 19, 'P', 'P+M'), (20, 20, 'P-11', 'P-1'), (21, 21, 'P', 'P+M'), (22, 22, 'P-11', 'P-1'),
              (23, 23, 'P', 'P+M'), (24, 24, 'P-11', 'P+M'), (25, 25, 'F', 'P+M'), (26, 26, 'P-3', 'P+M'),
              (27, 30, 'F', 'P+M'), (31, 34, 'P-11', 'P+M'), (35, 41, 'P', 'P+M'), (42, 42, 'F', 'P+M'),
              (43, 43, 'F+1', 'P+M'), (44, 44, 'F', 'P+M'), (45, 45, 'F+1', 'P+M'), (46, 48, 'P-1', 'P+M'),
              (49, 54, 'P-1', 'P-1'), (55, 59, 'P-10', 'P-1'), (60, 62, 'P-1', 'P-1'), (63, 65, 'P-5', 'P-1'),
              (66, 67, 'P-5', 'P+5'), (68, 70, 'F', 'P-1'), (71, 72, 'P', 'P+5'), (73, 75, 'P-6', 'P-1')]


def _year(code, first, proj, mt):
    base = {'F': first, 'P': proj}[code[0]]
    rest = code[1:]
    if rest == '+M':
        return calc(lambda a, b: a + b, base, mt)
    return calc(lambda a: a + int(rest or 0), base)


def config(book):
    C, Q = book['Config'], book['Questions']
    proj, mt = book.name('ProjYr'), book.name('MTHorizon')
    g = lambda r, c: C.get(r, c)
    B, F, G, K, L = ci('B'), ci('F'), ci('G'), ci('K'), ci('L')
    # country list: running count by department, fanchart group
    for r in range(6, 205):
        last = 177 if r == 83 else r                     # quirk: G83 counts over F5:F177
        C.set(r, G, concat(g(r, F), '-', countif_eq(colvals(C, F, 5, last), g(r, F))))
    div = {v for v in colvals(C, ci('AZ'), 8, 421) if v is not None}
    com = {v for v in colvals(C, ci('BP'), 8, 284) if v is not None}
    for r in range(6, 205):
        k, ifs = g(r, K), g(r, 3)
        if iserr(k):
            C.set(r, L, k)
        elif eq(k, 'AE'):
            C.set(r, L, 'AE')
        elif eq(k, 'EM') and ifs in div:
            C.set(r, L, 'EM-DIVERSIFIED')
        elif eq(k, 'EM') and ifs in com:
            C.set(r, L, 'EM-COMMODITY')
        else:
            C.set(r, L, 'EM-DIVERSIFIED')
    # fanchart histograms: t+5 gap centred on its median, ranked, then read back in rank order
    for v, rk, val, obs, out, r0, r1 in HIST:
        v, rk, val, obs, out = ci(v), ci(rk), ci(val), ci(obs), ci(out)
        med = median(colvals(C, v, r0, r1))
        for r in range(r0, r1 + 1):
            C.set(r, val, calc(lambda x, m: x - m, g(r, v), med))
        centred = colvals(C, val, r0, r1)
        by_rank = {}
        for r, k in zip(range(r0, r1 + 1), ranks_asc(centred)):
            C.set(r, rk, k)
            if not iserr(k):
                by_rank.setdefault(k, ref(g(r, val)))
        C.set(4, out, xmax(colvals(C, obs, r0, r1)))
        for r in range(r0, r1 + 1):
            o = g(r, obs)
            C.set(r, out, o if iserr(o) else by_rank.get(o, NA))
    # empty fourth block (rows 581-1141): value first, then rank
    AS, AT, AU = ci('AS'), ci('AT'), ci('AU')
    med = median(colvals(C, AS, 581, 1141))
    for r in range(581, 1142):
        C.set(r, AT, calc(lambda x, m: x - m, g(r, AS), med))
    for r, k in zip(range(581, 1142), ranks_asc(colvals(C, AT, 581, 1141))):
        C.set(r, AU, k)
    # fanchart settings
    AH = ci('AH')
    C.set(8, AH, calc(lambda a, b: a * b, g(4, AH), g(7, AH)))          # draws
    C.set(9, AH, calc(lambda a, b: a / b, g(8, AH), g(5, AH)))          # blocks
    C.set(12, AH, calc(lambda p: p - 1, proj))                          # historical sample ends
    grp = Table(book, 'Config!$B$6:$L$204').vlookup(book.name('Cname'), 11)
    C.set(18, AH, grp)                                                  # fanchart group
    if iserr(grp):
        C.set(19, AH, grp)
        C.set(20, AH, grp)
    else:
        hist = {'AE': 'AX', 'EM-DIVERSIFIED': 'BN', 'EM-COMMODITY': 'CD'}
        key = next((h for h in hist if eq(grp, h)), None)
        C.set(19, AH, hist[key] if key else 'BN')
        C.set(20, AH, ref(g(4, ci(hist[key]))) if key else NA)
    C.set(27, AH, 26 * 4)                                               # random draws start column
    # banking-crisis stress test indicators and cut-offs
    for r in range(45, 49):
        C.set(r, ci('AA'), concat('LIM_', g(r, ci('AB'))))
    em = is_(Q.get(6, 5), 'EM')
    C.set(47, ci('AD'), em if iserr(em) else (15 * 1 + 8.4 * 0 if em else 30 * 1 + 12.2 * 0))
    C.set(48, ci('AD'), em if iserr(em) else (10 if em else 9))
    # natural-disaster countries: IFS code from the country list
    names = Table(book, 'Config!$B$6:$C$204')
    for r in range(45, 101):
        C.set(r, ci('V'), names.vlookup(g(r, ci('W')), 2))
    # GFN module switches
    CG = ci('CG')
    cu = is_(Q.get(5, 5), 'none')
    C.set(7, CG, cu if iserr(cu) else not cu)                           # country in a currency union
    nb = book.hrow('GFNNoBank')[2]
    for r, s in ((9, 'Mitigator'), (10, 'Amplifier')):
        x = is_(nb, s)
        C.set(r, CG, x)
    # GFN shocks table: last 12 historical years
    CJ, CU = ci('CJ'), ci('CU')
    mf = Table(book, 'MacrofwData')
    dates = book.hrow('MacrofwDates')
    for c in range(CJ + 1, CU + 1):
        C.set(12, c, calc(lambda y: y + 1, g(12, c - 1)))
    for c in range(CJ, CU + 1):
        C.set(11, c, calc(lambda p, k: p + k, proj, g(12, c)))
        k = g(12, c)
        C.set(13, c, k if iserr(k) else match(k, dates, 1))
        col = g(13, c)
        C.set(14, c, calc(lambda x: x / 100, mf.vlookup('NGDP_RPCH', col)))          # real GDP growth
        C.set(16, c, mf.vlookup('ENDA', col))                                          # exchange rate
        prev = calc(lambda x: x - 1, col)
        C.set(22, c, calc(lambda a, b: a / 100 - b / 100,                              # change in inflation
                          mf.vlookup('NGDP_DPCH', col), mf.vlookup('NGDP_DPCH', prev)))
    for c in range(CJ + 1, CU + 1):
        C.set(17, c, calc(lambda a, b: (a / b) - 1, g(16, c), g(16, c - 1)))           # depreciation
    CI, CK, CT = ci('CI'), ci('CK'), ci('CT')
    C.set(14, CI, stdev(rowvals(C, 14, CK, CT)))
    C.set(17, CI, xmax(rowvals(C, 17, CK, CT)))
    aeem = book.name('AEEM')                                                           # ER pass-through
    C.set(21, CI, aeem if iserr(aeem) else (0.03 if eq(aeem, 'AE') else 0.25 if eq(aeem, 'EM') else NA))
    mn = xmin(rowvals(C, 22, CK, CT))
    C.set(22, CI, calc(lambda x: x / 2, mn))
    # GFN convergence test: stress financing need vs the GFN sheet
    GFN = book['GFN']
    for c in range(CJ, ci('CY') + 1):
        e = err(g(38, c), mt)
        if e:
            C.set(41, c, e)
        elif num(g(38, c)) <= num(mt):
            C.set(41, c, calc(lambda a, b: a - b, g(40, c), GFN.get(136, c - 78)))
        else:
            C.set(41, c, 0)
    C.set(41, CI, xsum(rowvals(C, 41, CJ, ci('CY'))))
    # Signals ranges: no value in the template (see QUIRKS)
    C.set(49, ci('DD'), '=Signals!$A$2:$J$2')
    C.set(50, ci('DD'), '=Signals!$A$3:$J$18')
    # dictionary: first and last year of each series
    first = book.name('FirstYr')
    for r0, r1, a, b in DICT_YEARS:
        for r in range(r0, r1 + 1):
            C.set(r, ci('DG'), _year(a, first, proj, mt))
            C.set(r, ci('DH'), _year(b, first, proj, mt))


def compute(book, sheet):
    {'Questions': questions, 'Macrofw': macrofw, 'NewMacrofw': newmacrofw, 'Config': config}[sheet](book)
