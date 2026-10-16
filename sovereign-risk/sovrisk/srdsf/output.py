"""Output sheet: the SRDSF summary pages as the report shows them. Titles, the risk-signal summary table, the debt
coverage questionnaire, the baseline table, the near-term (logit) and medium-term (fanchart, GFN, stress test)
panels and the realism notes, all read from Signals, Questions, BaseDB, LOGIT, FAN, GFN, Config and the chart
data on Charts. The charts themselves are drawn from Charts; this sheet holds the numbers and labels around
them.

Blocks (top-left cell, what it holds):
  L16  "Risk of sovereign stress" table: mechanical signal and final assessment per horizon (rows 19-39)
  Z58  debt coverage and disclosures: perimeter answers (AL/AM 61-72) and the coverage matrix (AG84:AO92)
  AS110 public debt structure chart titles and perimeter notes (AS/AX 110-153)
  BG160 baseline table: debt, GFN, flows and macro series for ProjYr-1, ProjYr..+5 and ProjYr+6..+10 (164-190)
  CC212 near-term: logit probability and its drivers for four years (CG:CJ 213-222), missed-crisis text
  CY238 realism: comparator group labels and footnotes
  DZ293 medium-term: fanchart and GFN module values and indices (EO/EP 298-327), the MT index (EP332:EQ336),
        missed-crisis texts, stress-test activation flags (row 350) and the peer percentile matrix (FE292:FJ393)
"""
from .book import ci
from .charts import Look, cols, lower, xtext
from .gfn import IF
from .residfin import AND, Engine, X, cat, cmp, iferror
from .xl import NA, iserr, isnumber

SHEETS = ['Output']

QUIRKS = [
    'P39 (debt stabilization, "Yes"/"No") looks up $J38 (SIG-STAB) with the column number in N13 (mechanical '
    'signal), one row above its own row.',
    'A blank cell returned by VLOOKUP on Signals (N30, N36) shows as "" here: the golden values store a formula '
    'result of "" and a blank alike, and the Signals cells looked up are formula "" results.',
    'The baseline table rows 174/175 cover BN:BX and BY only; BT (a spacer column with no year in row 158) '
    'gives "n.a." through IFERROR.',
    'CH218:CJ222 are #VALUE! because the LOGIT cells they look up (contributions to the change in the logit '
    'probability) are #VALUE! in the sample; passed through.',
    'FE292:FJ292 look up the peer group in Charts!F3617:CE3620 with Charts!B3622, which is #N/A in the sample '
    '(AEEM is #N/A), so the whole percentile matrix FE293:FJ393 is #N/A.',
    'The missed-crisis / false-alarm texts (CC224, CC225, EL338, EL339) use Charts row 4538, #N/A in the sample.',
]

BL, BN, BS, BU, BX, BY, BE = (ci(c) for c in ('BL', 'BN', 'BS', 'BU', 'BX', 'BY', 'BE'))
J, N, O, P, X_ = ci('J'), ci('N'), ci('O'), ci('P'), ci('X')
EO, EP, EQ, ET, EW, FD = (ci(c) for c in ('EO', 'EP', 'EQ', 'ET', 'EW', 'FD'))
YEARS_MAIN = [BL] + list(range(BN, BS + 1)) + list(range(BU, BY + 1))   # ProjYr-1 | ProjYr..+5 | ProjYr+6..+10
BASELINE_COLS = {174: [BL] + list(range(BN, BX + 1)), 175: [BL, BY]}


def compute(book, sheet='Output'):
    e = Engine(book, sheet)
    x = e.x
    lk = Look(book)
    vl, mt = lk.vl, lk.match
    Qn = book.name
    Ch, Qs, Cf = book['Charts'], book['Questions'], book['Config']
    cname = lambda: Qn('Cname')
    proj = lambda: Qn('ProjYr')

    def title(r, c, s):
        e.let(r, c, lambda _: cat(cname(), s))

    def sig(key, col):
        """VLOOKUP(key, SignalsTable, col, FALSE); a "" result stays "" (see QUIRKS)."""
        v = lk.vlraw(key, 'SignalsTable', col)
        return '' if v is None else v

    # ---- Risk of sovereign stress table (rows 13-39) -----------------------------------------------------------
    e.let(13, [N, O], lambda c: mt(e(17, c), 'SignalsHeaders'))       # columns: mechanical signal, final
    title(16, ci('L'), ': Risk of sovereign stress')
    for r, cs in ((19, [O]), (23, [N, O]), (27, [N, O]), (28, [N]), (29, [N]), (30, [N]), (32, [O]), (36, [N, O])):
        e.let(r, cs, lambda c, r=r: sig(e(r, J), e(13, c)))
    e.let(39, P, lambda c: sig(e(38, J), e(13, N)))

    # ---- Debt coverage and disclosures (rows 58-106) -----------------------------------------------------------
    title(58, ci('Z'), ': Debt coverage and disclosures')
    AL, AM = ci('AL'), ci('AM')
    e.let(61, AL, lambda c: IF(cmp(Qs['C21'], '=', 'Central government'),
                               lambda: vl(e(61, X_), 'DebtMetadata', 3), 'n.a.'))
    for r in range(64, 72):
        e.let(r, AL, lambda c, r=r: vl(e(r, X_), 'DebtMetadata', 3))
    for r in [61] + list(range(64, 72)):                               # comment: "" when blank
        def note(c, r=r):
            v = lk.vlraw(e(r, X_), 'DebtMetadata', 5)
            return IF(cmp(v, '=', ''), '', lambda: 0 if v is None else v)
        e.let(r, AM, note)
    e.let(72, AM, lambda c: '' if Qs['E34'] is None else Qs['E34'])
    AGO = cols('AG', 'AO')
    e.let(106, AGO, lambda c: mt(e(105, c), 'Questions!$23:$23'))     # questionnaire column of each item

    def coverage(c, r):
        v = lk.vlraw(e(r, X_), 'DebtMetadata', e(106, c))
        return v if isnumber(v) else ''
    for r in range(84, 93):
        e.let(r, AGO, lambda c, r=r: coverage(c, r))

    # ---- Public debt structure: chart titles and perimeter notes (rows 110-153) --------------------------------
    AS, AX = ci('AS'), ci('AX')
    ch = lambda ref: 0 if Ch[ref] is None else Ch[ref]
    note = 'Note: The perimeter shown is '
    title(110, AS, ': Public debt structure indicators')
    e.let(111, AS, lambda c: cat(ch('B37'), ' (', ch('B38'), ')'))
    e.let(123, AS, lambda c: cat(note, lower(Qn('Perimeter')), '.'))
    e.let(125, AS, lambda c: cat(ch('B65'), ' (', ch('B66'), ')'))
    e.let(125, AX, lambda c: cat(ch('B109'), ' (', ch('B110'), ')'))
    e.let(138, AS, lambda c: cat(note, ch('C76')))
    e.let(138, AX, lambda c: cat(note, ch('C116')))
    e.let(140, AS, lambda c: ch('B128'))
    e.let(140, AX, lambda c: cat(ch('B84'), ' (', ch('B85'), ')'))
    e.let(153, AS, lambda c: cat(note, ch('C139')))
    e.let(153, AX, lambda c: cat(note, ch('C96')))

    # ---- Baseline scenario table (rows 157-190) ----------------------------------------------------------------
    title(160, ci('BG'), ': Baseline scenario')
    e.let(158, YEARS_MAIN, lambda c: mt(e(157, c), 'BaseDBdates'))
    e.let(163, YEARS_MAIN, lambda c: X(proj()) + e(157, c))
    rows = list(range(164, 181)) + list(range(182, 186)) + list(range(187, 191))
    for r in rows:
        e.let(r, BASELINE_COLS.get(r, YEARS_MAIN), lambda c, r=r: iferror(
            X(vl(e(r, BE), 'BaseDBData', e(158, c))) * 100, lambda: 'n.a.'))

    # ---- Near-term risk analysis (rows 209-225) ----------------------------------------------------------------
    CGJ = cols('CG', 'CJ')
    title(212, ci('CC'), ': Near-term risk analysis')
    e.let(209, CGJ, lambda c: mt(e(210, c), 'DatesNT'))
    e.let(213, CGJ, lambda c: X(proj()) + e(210, c))
    e.let(214, CGJ, lambda c: cat(x(213, c) + 1, '-', x(213, c) - 1998))   # "2020-21"
    for r in (215, 216, 218, 219, 220, 221, 222):                     # LSP, its change and contributions
        e.let(r, CGJ, lambda c, r=r: vl(e(r, ci('CA')), 'DataNT', e(209, c)))
    pct = lambda ref: xtext(X(Ch[ref]) * 100, '0.0')
    e.let(224, ci('CC'), lambda c: cat('Prob. of missed crisis, ', proj(), '-', X(proj()) + 1,
                                       ' (if stress not predicted): ', pct('R4538'), ' pct.'))
    e.let(225, ci('CC'), lambda c: cat('Prob. of false alarm, ', proj(), '-', X(proj()) + 1,
                                       ' (if stress predicted): ', pct('Q4538'), ' pct.'))

    # ---- Realism of baseline assumptions (rows 238-287) --------------------------------------------------------
    CY, DP, DI = ci('CY'), ci('DP'), ci('DI')
    title(238, CY, ': Realism of Baseline Assumptions')
    e.let(238, DP, lambda c: IF(cmp(Qn('AEEM'), '=', 'EM'), 'Emerging Markets', 'Advanced Economies'))
    e.let(239, CY, lambda c: 'Forecast track Record 1/')
    e.let(239, DP, lambda c: IF(cmp(Ch['C597'], '=', 1), 'Commodity Exporter', 'Non-Commodity Exporter'))
    e.let(240, DP, lambda c: IF(cmp(Qn('Engagement'), '=', 'Surveillance'), 'Surveillance', 'Program'))
    e.let(240, DI, lambda c: cat(e(238, DP), ',  ', e(239, DP), ',  ', e(240, DP)))
    e.let(247, CY, lambda c: 'Public Debt Creating Flows')
    e.let(284, CY, lambda c: IF(cmp(Ch['J597'], '=', 0),
                                '1/ Projections made in the October and April WEO vintage.',
                                '1/ Projections made in the October and April WEO vintage. Program status not used '
                                'in creating comparator group due to lack of data.'))
    e.let(285, CY, lambda c: "2/ Calculated as the percentile rank of the country's output gap revisions (defined "
                             "as the difference between real time/period ahead estimates ")
    e.let(286, CY, lambda c: '3/ Data cover annual obervations from 1990 to 2019 for MAC advanced and emerging '
                             'economies. Percent of sample on vertical axis.')
    e.let(287, CY, lambda c: '4/ The Laubach (2009) rule is a linear rule assuming bond spreads increase by about '
                             '4 bps in response to a 1 ppt increase in the projected debt-to-GDP ratio.')

    # ---- Medium-term risk assessment (rows 292-393) ------------------------------------------------------------
    FEJ = cols('FE', 'FJ')
    DZ = ci('DZ')
    title(293, DZ, ': Medium-term risk assessment')

    def peer_pct(c):                                                   # HLOOKUP(tool-group, Charts!F3617:CE3620, 4)
        key = cat(e(290, c), '-', Ch['B3622'])
        if iserr(key):
            return key
        for cc in cols('F', 'CE'):
            if cmp(Ch.get(3617, cc), '=', key) is True:
                v = Ch.get(3620, cc)
                return 0 if v is None else v
        return NA
    e.let(292, FEJ, peer_pct)
    for r in range(293, 394):                                          # percentile matrix: 1 in the peer's cell
        e.let(r, FEJ, lambda c, r=r: IF(cmp(e(r, FD), '=', e(292, c)), 1, 0))
    fan = lambda k, h: vl(k, 'FanOutTab', mt(h, 'FanOutTabLabels'))
    gfn = lambda k, h: vl(k, 'GFNOutTab', mt(h, 'GFNOutTabLabels'))
    for r, k in ((298, 'DFIW'), (301, 'DFIP'), (304, 'DFID')):         # fanchart: raw value, index
        e.let(r, EO, lambda c, k=k: X(fan(k, 'Raw value')) * 100)
        e.let(r, EP, lambda c, k=k: fan(k, 'Index'))
    e.let(309, EP, lambda c: fan('DFI', 'Index'))
    e.let(311, EP, lambda c: fan('DFS', 'Index'))
    for r, k in ((314, 'GFIG'), (317, 'GFIB'), (320, 'GFIC')):         # GFN module: value, weighted value
        e.let(r, EO, lambda c, k=k: X(gfn(k, 'Value')) * 100)
        e.let(r, EP, lambda c, r=r, k=k: X(gfn(k, 'Weight')) * e(r, EO))
    e.let(325, EP, lambda c: gfn('GFI', 'Value'))
    e.let(327, EP, lambda c: gfn('GFS', 'Value'))
    e.let(332, EP, lambda c: e(309, EP))                               # MT index: fanchart + GFN
    e.let(332, EQ, lambda c: x(309, EP) / Cf['AH23'])
    e.let(332, EW, lambda c: x(332, EQ) * e(332, ET))
    e.let(333, EP, lambda c: e(325, EP))
    e.let(333, EQ, lambda c: x(325, EP) / Cf['CG8'])
    e.let(333, EW, lambda c: x(333, EQ) * e(333, ET))
    e.let(334, EQ, lambda c: x(332, EQ) * e(332, ET) + x(333, EQ) * e(333, ET))

    def mt_signal(c):
        v, lo, hi = e(334, EQ), Cf['CX4'], Cf['CX5']
        return IF(cmp(v, '>', hi), 'High', lambda: IF(cmp(v, '<', lo), 'Low', lambda: IF(
            AND(cmp(v, '<=', hi), cmp(v, '>=', lo)), 'Moderate', '…')))
    e.let(335, EQ, mt_signal)
    e.let(336, EQ, lambda c: vl('SIG-MT', 'SignalsTable', mt('Final assessment', 'SignalsHeaders')))
    EL = ci('EL')
    p5 = lambda: X(proj()) + 5
    e.let(338, EL, lambda c: cat('Prob. of missed crisis, ', proj(), '-', p5(), ', if stress not predicted: ',
                                 pct('F4538'), ' pct.'))
    e.let(339, EL, lambda c: cat('Prob. of false alarms, ', proj(), '-', p5(), ', if stress predicted: ',
                                 pct('E4538'), ' pct.'))
    e.let(345, DZ, lambda c: cat('2/ The comparison group is ', lower(e(238, ci('DP'))), ', ',
                                 lower(e(239, ci('DP'))), ', ', lower(e(240, ci('DP'))), '.'))
    act = lambda k: vl(k, 'SignalsTable', mt('Activated', 'SignalsHeaders'))
    for flag, src, k in (('EA', 'EB', 'ST-BC'), ('ED', 'EE', 'ST-CP'), ('EK', 'EL', 'ST-ER'),
                         ('EN', 'EO', 'ST-CL'), ('EQ', 'ER', 'ST-ND')):   # stress tests activated: flag 1/0
        e.let(350, ci(src), lambda c, k=k: act(k))
        e.let(350, ci(flag), lambda c, s=ci(src): IF(e(350, s), 1, 0))
    e.let(350, ci('ES'), lambda c: act('ST-ND'))

    e.run()
