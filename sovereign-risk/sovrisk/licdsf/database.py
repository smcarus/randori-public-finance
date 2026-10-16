"""Output Database sheet of the LIC DSF template: the flat table submitted to the IMF/WB DSA database.

Every row is one series: the country identifiers (IFS code, HIPC status, CPIA, final and mechanical ratings) repeated
down columns B..P, and the series values by year across AB..BG (2013..2044; the year header runs back to U = 2006; AM = first
projection year). It copies
the external and public baseline tables (scaled to billions where the series is in US dollars), the stress-test
paths of Tables 3-4 and Chart Data, the thresholds, the coverage and tailored-test settings and a few DMX lines.
Several rows point at deleted cells and hold #REF! in the template; they are reproduced as such.
"""
from sovrisk.srdsf.book import ci
from sovrisk.srdsf.xl import eq, isnumber

from .outputs import arith, iif, is_, links, ref

SHEETS = ['Output Database']

QUIRKS = [
    "Rows 72, 78, 81, 87, 90, 96, 99, 105, 108 (external stress tests no longer in the template), 153-154, 157, "
    "162-163, 164-168 (except AM164:AM167), 171-172, 174-175, 180-181, 183-184 and 189 refer to deleted cells and "
    "are #REF! in every year.",
    "Rows 158/159, 176/177 and 185/186 (public B5/B6 and B4/B5) are swapped relative to their labels: they read "
    "Table 4 rows 23/22, 71/70 and 94/92.",
    "AM164:AM167 hold single cells (D43, D44, D50, D49 of Table 4) while the rest of rows 164-167 is #REF!.",
    "H2 (Board_Date) is time-formatted; with no board date it shows 0 as the time 00:00:00.",
    "AM319 (CPIA classification code) is FALSE for a classification other than Weak/Medium/Strong (IF without "
    "else).",
]

DB = 'Output Database'
YEARS = range(ci('AB'), ci('BG') + 1)


def _scaled(v, unit):
    """IF(ISNUMBER(v), IF(unit="Million", v/1000, IF(unit="Billion", v, "Check scale")), "…")."""
    if not isnumber(v):
        return '…'
    if eq(unit, 'Million'):
        return v / 1000
    return v if eq(unit, 'Billion') else 'Check scale'


def _as_time(v):
    """A time-formatted cell as the golden values carry it ('HH:MM:SS' for a fraction of a day)."""
    if isnumber(v) and 0 <= v < 1:
        sec = int(round(v * 86400))
        return f'{sec // 3600:02d}:{sec // 60 % 60:02d}:{sec % 60:02d}'
    return v


def compute(book, sheet=DB):
    S = book[DB]
    unit = book['Input 1 - Basics']['C19']
    be, bp, dmx = book['Baseline - external'], book['Baseline - public'], book['Input 3 - Macro-Debt data(DMX)']

    # --- year header: AM = first projection year, back to 2006 and forward to 2044
    S.set(1, ci('AM'), ref(book['Macro-Debt_Data']['U4']))
    for c in range(ci('AL'), ci('U') - 1, -1):
        S.set(1, c, arith(lambda y: y - 1, S.get(1, c + 1)))
    for c in range(ci('AN'), ci('BG') + 1):
        S.set(1, c, arith(lambda y: y + 1, S.get(1, c - 1)))

    # --- identifiers (row 2), repeated down each row of the database
    o7 = book['Output 7 - Risk rating summary']
    for col, nm in (('B', 'IFSCode'), ('C', 'Document_ID'), ('D', 'EDMS'), ('E', 'Publication_Status'),
                    ('F', 'HIPCStatus'), ('G', 'RGCountry1'), ('H', 'Board_Date'), ('I', 'FirstYear_of_Projection'),
                    ('J', 'CPIAValue'), ('N', 'Public_Debt'), ('O', 'Private_Debt')):
        S.set(2, ci(col), ref(book.name(nm)))
    S['H2'] = _as_time(S['H2'])
    S['K2'] = ref(o7['E49'])                                        # final external rating
    S['L2'] = ref(o7['E48'])                                        # mechanical external rating
    S['P2'] = ref(o7['E55'])                                        # final overall rating
    for r in range(3, 192):
        for col in 'BCDEFGHIK':
            S.set(r, ci(col), S.get(2, ci(col)))
        S.set(r, ci('J'), S.get(r - 1, ci('J')))
        for col in 'NOP':
            S.set(r, ci(col), S.get(r - 1, ci(col)))
    for r in [193] + list(range(199, 331)):
        for c in range(ci('B'), ci('P') + 1):
            S.set(r, c, ref(S.get(2, c)))

    # --- external baseline table (AB = 2013 reads 'Baseline - external' column C)
    links(book, DB, """
        AB2:BG21 'Baseline - external'!C12
        AB22:BG29 'Baseline - external'!C33
        AB31:BG31 'Baseline - external'!C42
        AB33:BG33 'Baseline - external'!C49
        AB35:BG44 'Baseline - external'!C51
        AB48:BG49 'Baseline - external'!C64""")
    for r, src in ((30, 41), (32, 48), (34, 50), (45, 61), (46, 62), (47, 63)):    # US dollar amounts
        for c in YEARS:
            S.set(r, c, _scaled(be.get(src, c - 25), unit))
    for i, r in enumerate(range(50, 62)):                          # historical / projected averages
        S.set(r, ci('AL'), ref(be.get(70 + i // 2, ci('N') if i % 2 == 0 else ci('P'))))
    edd = book['Ext_Debt_Data']
    for c in range(ci('AM'), ci('BG') + 1):
        for r, src in ((62, 122), (63, 407), (65, 409)):
            S.set(r, c, _scaled(edd.get(src, c - 33), unit))
        S.set(64, c, ref(edd.get(408, c - 33)))
        S.set(66, c, ref(edd.get(410, c - 33)))

    # --- external stress tests by indicator (PV/GDP, PV/exports, PV/revenue, DS/exports, DS/revenue)
    for r0, src in ((67, 35), (76, 36), (85, 37), (94, 39), (103, 40)):
        tests = [('Baseline - external', 'N'), ('A1_historical_ext', 'D'), None, ('B1_GDP_ext', 'D'),
                 ('B3_Exports_ext', 'D'), None, ('B4_other flows_ext', 'D'), ('B6_Combo_non-mkt_ext', 'D'),
                 ('B5_depreciation_ext', 'D')]                      # None: a deleted test, #REF!
        if r0 == 67:                                                # PV/GDP: row 69 is blank, not #REF!
            tests[2] = 'skip'
        for i, t in enumerate(tests):
            if t == 'skip':
                continue
            spec = '#REF!' if t is None else f"'{t[0]}'!{t[1]}{src}"
            links(book, DB, f"AM{r0 + i}:BG{r0 + i} {spec}")

    # --- public baseline table
    links(book, DB, """
        AB112:BG112 'Baseline - public'!D12
        AB113:BG113 'Baseline - public'!D14
        AB114:BG131 'Baseline - public'!D21
        AB132:BG132 'Baseline - public'!D42
        AB133:BG133 'Baseline - public'!D47
        AB135:BG135 'Baseline - public'!D43
        AB137:BG150 'Baseline - public'!D54
        AB193:BG193 'Baseline - public'!D20""")
    for r, src in ((134, 48), (136, 52)):
        for c in YEARS:
            S.set(r, c, _scaled(bp.get(src, c - 24), unit))

    # --- public stress tests (Table 4), thresholds
    t4 = "'Output 3-2 Stress-public'!"
    links(book, DB, f"""
        AM151:BG151 {t4}D12
        AM152:BG152 {t4}D15
        AM153:BG154 #REF!
        AM155:BG156 {t4}D19
        AM157:BG157 #REF!
        AM158:BG158 {t4}D23
        AM159:BG159 {t4}D22
        AM160:BG160 {t4}D36
        AM161:BG161 {t4}D43
        AM162:BG163 #REF!
        AM164:AM165 {t4}D43
        AN164:BG167 #REF!
        AM166 {t4}D50
        AM167 {t4}D49
        AM168:BG168 #REF!
        AM169:BG169 {t4}D60
        AM170:BG170 {t4}D63
        AM171:BG172 #REF!
        AM173:BG173 {t4}D67
        AM174:BG175 #REF!
        AM176:BG176 {t4}D71
        AM177:BG177 {t4}D70
        AM178:BG178 {t4}D82
        AM179:BG179 {t4}D85
        AM180:BG181 #REF!
        AM182:BG182 {t4}D89
        AM183:BG184 #REF!
        AM185:BG185 {t4}D94
        AM186:BG186 {t4}D92
        AM187:BG187 'CI Summary'!$I11
        AM188:BG188 'CI Summary'!$I10
        AM189:BG189 #REF!
        AM190:BG190 'CI Summary'!$I13
        AM191:BG191 'CI Summary'!$I14""")

    # --- Chart Data: thresholds and every indicator path (baseline, A1, B1-B6, C1, then C2-C4 when numeric)
    cd = book['Chart Data']
    for r, cell in ((199, 'D66'), (200, 'D108'), (201, 'D150'), (202, 'D192'), (203, 'D267')):
        links(book, DB, f"AM{r}:BG{r} 'Chart Data'!${cell[0]}${cell[1:]}")
    for r0, src in ((204, 38), (217, 80), (230, 122), (243, 164), (256, 239), (269, 281), (282, 318)):
        links(book, DB, f"""
            AM{r0}:BG{r0 + 7} 'Chart Data'!D{src}
            AM{r0 + 8}:BG{r0 + 8} 'Chart Data'!D{src + 9}""")
        for i in range(4):
            for c in range(ci('AM'), ci('BG') + 1):
                v = cd.get(src + 10 + i, c - 35)
                S.set(r0 + 9 + i, c, v if isnumber(v) else '')

    # --- settings: definitions, debt coverage, tailored tests, debt-carrying capacity
    bas, dc, tt, cis = (book['Input 1 - Basics'], book['Input 2 - Debt Coverage'], book['Input 6 - Tailored Tests'],
                        book['CI Summary'])
    am = ci('AM')
    S.set(296, am, 1 if eq(bas['C27'], 'YES') else 0)
    S.set(297, am, 1 if eq(bas['C28'], 'YES') else 0)
    S.set(298, am, bas['C29'] if isnumber(bas['C29']) else '')
    S.set(299, am, iif(is_(ref(book.name('RES_CUR_BASED')), ref(book['lookup']['X4'])), 1, 0))
    S.set(300, am, 1 if eq(bas['C34'], 'YES') else 0)
    for i in range(8):                                              # sub-sectors covered
        S.set(301 + i, am, 1 if eq(dc.get(8 + i, 5), 'X') else 0)
    links(book, DB, """
        AM309:AM313 'Input 2 - Debt Coverage'!F21
        AM314:AM315 'Input 2 - Debt Coverage'!E32
        AM323 'Output 7 - Risk rating summary'!E16
        AM324 'CI Summary'!C10""")
    for i in range(3):
        S.set(316 + i, am, 1 if eq(tt.get(9 + i, 3), 'YES') else 0)
    b9 = cis['B9']
    S.set(319, am, 1 if eq(b9, 'Weak') else 2 if eq(b9, 'Medium') else 3 if eq(b9, 'Strong') else False)

    # --- DMX lines (Z = 2011 reads DMX column K)
    for c in range(ci('Z'), ci('BG') + 1):
        k = c - 15
        S.set(327, c, _scaled(dmx.get(14, k), unit))
        S.set(328, c, _scaled(dmx.get(15, k), unit))
        S.set(329, c, arith(lambda a, b: a / b * 100, dmx.get(14, k), dmx.get(13, k)))
        S.set(330, c, arith(lambda a, b: a / b * 100, dmx.get(15, k), dmx.get(13, k)))
