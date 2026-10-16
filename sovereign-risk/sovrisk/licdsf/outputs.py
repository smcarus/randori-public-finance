"""Results sheets of the LIC DSF template: the thresholds, breach tests and risk ratings, and the output tables.

- Chart Data:       collects every debt-burden indicator path (baseline, historical scenario, B1-B6 bound tests,
                    C1-C4 tailored tests, the customised scenario) from the scenario sheets, finds the most extreme
                    shock of each indicator (the stress test with the highest 10-year maximum, ignoring shocks that
                    breach for one year only), tests baseline and shock paths against the thresholds (CI Summary),
                    and derives the mechanical external, public and overall risk signals (Low/Moderate/High) and the
                    "space to absorb shocks" of the moderate-risk tool.
- Probability approach: the optional borderline test (breach size against a +/- bandwidth around each threshold)
                    and the probit probabilities of debt distress.
- Output 1-1 / 1-2:  Tables 1 and 2 (external and public DSA tables) laid out from the baseline sheets.
- Output 2-1 / 2-2:  chart legends and the default-settings customisation summary of Figures 1-2.
- Output 3-1 / 3-2:  Tables 3 and 4: the stress-test paths of every indicator, looked up from Chart Data by label.
- Output 4-1 .. 6:   titles and footnotes of the realism, moderate-risk, market-module and probability figures;
                    5-2 also flags market-financing pressure (GFN and EMBI spread against their benchmarks).
- Output 7:          the risk rating summary: mechanical vs final external and overall ratings, judgement flags,
                    debt coverage and debt-carrying capacity.
"""
import math
import re

from sovrisk.srdsf.book import ci
from sovrisk.srdsf.xl import DIV0, NA, VALUE, eq, err, iserr, isnumber, match, num

SHEETS = ['Chart Data', 'Probability approach', 'Output 1-1 - External DSA', 'Output 1-2 - Public DSA',
          'Output 2-1 Stress_Charts_Ex', 'Output 2-2 Stress_Charts_Pub', 'Output 3-1 Stress-external',
          'Output 3-2 Stress-public', 'Output 4-1 - Forecast Error', 'Output 4-2 - Realism',
          'Output 5-1 Moderate risk', 'Output 5-2 Market module', 'Output 6 - Prob (if applicable)',
          'Output 7 - Risk rating summary']

QUIRKS = [
    "Chart Data: in the debt service-to-exports block the rank formulas of AI/AJ were filled one row too far, so the "
    "summary row 135 holds ranks (AI135, AJ135) instead of the SUMs that rows 51, 93, 177 and 252 hold.",
    "Chart Data: only the PV/GDP block ranks the tailored tests by their one-off maxima in column AM (row 65); the "
    "other blocks (rows 107, 149, 191, 266) MATCH $I$21 in the one-off rank column AI, which is 0 when no shock "
    "breaches once, so their 'MX shock Tailored' rows are #N/A. Public blocks 2-3 use column AC instead, block 3 "
    "matching 1 rather than $I$21 (rows 308, 345).",
    "Chart Data: rows 243-244, 285-286, 322-323 and 355-356 (B3/B4 for public debt) show the baseline (or 0 when "
    "Old_New_Scenario is 0) since those shocks do not apply to public debt.",
    "Probability approach K13: the 'near breach' test of PV/exports checks MAX >= threshold AND MAX < lower band "
    "(H38/H39 swapped), which can never hold; the other indicators check lower band <= MAX < threshold.",
    "Probability approach: several language branches point at the wrong translation cells (H6/H8/N10/I12 use row+1 "
    "in Spanish, J10 French uses D853, I12 French D846, A59/H62/A76/A78/N63 mix rows and columns, N63 Spanish and "
    "A76 French are #REF!); only the English branch is exercised here.",
    "Output 1-2 row 58 (contingent liabilities): L58:AC58 is one fill of ='Baseline - public'!L69, so the "
    "projection years T..AC read columns T..AC of the baseline (five years later) instead of O..X.",
    "Output 1-2 C42/C43 test ISNUMBER(x*100), so a blank source shows 0 rather than the ellipsis.",
    "Output 1-2 AD54 continues the T..AC run (='Baseline - public'!Y65), so the blank separator column AD carries "
    "the 2034 inflation rate.",
    "Output 1-2 T5 (Spanish) and Output 7 D48 (all but English) point at #REF! translation cells.",
    "Output 1-2 historical averages AR46, AR48:AR52 and AR55 average D..N, including the separator column K "
    "(blank, so harmless); the projection averages of rows 43, 45, 46, 48-52 and 55 leave out AE.",
    "Output 3-2 A45:B46 are #REF! (deleted rows), so Table 4 rows 45-46 of PV debt-to-revenue are #REF!.",
    "Output 2-1 AF150 compares 'Input 6(optional)-Standard Test'!G22 with I22 where every other pair is G/H.",
    "Output 5-1 CS36 reads '(1-Y)*&Threshold' (a stray & inside the text).",
]

CD = 'Chart Data'
YRS = range(4, 25)                     # D..X: the 21 projection years on Chart Data
TEN = range(5, 15)                     # E..N: the ten years after the first projection year (breach window)
REF_ERR = '#REF!'


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


def _key(v, other):
    if v is None:
        v = '' if isinstance(other, str) else 0
    if isinstance(v, bool):
        return (2, v)
    if isinstance(v, str):
        return (1, v.lower())
    return (0, v)


def cmp(a, b):
    """Excel's ordering of a and b (-1, 0, 1), or the error among them. Numbers < text < booleans."""
    e = err(a, b)
    if e:
        return e
    ka, kb = _key(a, b), _key(b, a)
    return (ka > kb) - (ka < kb)


def gt(a, b):
    c = cmp(a, b)
    return c if iserr(c) else c > 0


def ge(a, b):
    c = cmp(a, b)
    return c if iserr(c) else c >= 0


def lt(a, b):
    c = cmp(a, b)
    return c if iserr(c) else c < 0


def le(a, b):
    c = cmp(a, b)
    return c if iserr(c) else c <= 0


def is_(a, b):
    """Excel a=b with error propagation."""
    e = err(a, b)
    return e if e else eq(a, b)


def iif(cond, a, b=False):
    """IF(cond, a, b): an error condition propagates; numbers are true when non-zero; text is #VALUE!."""
    if iserr(cond):
        return cond
    if isinstance(cond, str):
        return VALUE
    return a if num(cond) else b


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


def xsum(vals):
    xs = nums(vals)
    return xs if isinstance(xs, str) else float(sum(xs))


def average(*ranges):
    xs = []
    for vals in ranges:
        x = nums(vals)
        if isinstance(x, str):
            return x
        xs += x
    return sum(xs) / len(xs) if xs else DIV0


def large(vals, k):
    xs = nums(vals)
    if isinstance(xs, str):
        return xs
    return sorted(xs, reverse=True)[k - 1] if len(xs) >= k else '#NUM!'


def rank(x, vals):
    """RANK(x, vals, 0): 1 + the number of values above x; #N/A when x is not among the numbers of vals."""
    if iserr(x):
        return x
    xs = nums(vals)
    if isinstance(xs, str):
        return xs
    if not isnumber(x) or x not in xs:
        return NA
    return 1 + sum(1 for v in xs if v > x)


def countif_gt(vals, x):
    """COUNTIF(range, ">"&x) for a number x."""
    return sum(1 for v in vals if isnumber(v) and v > x)


def arith(f, *vals):
    """f over numbers with Excel's error propagation, blank -> 0 and text -> #VALUE!."""
    e = err(*vals)
    if e:
        return e
    if any(isinstance(v, str) for v in vals):
        return VALUE
    try:
        return f(*(num(v) for v in vals))
    except ZeroDivisionError:
        return DIV0


def rowvals(S, r, c0, c1):
    return [S.get(r, c) for c in range(c0, c1 + 1)]


def colvals(S, c, r0, r1):
    return [S.get(r, c) for r in range(r0, r1 + 1)]


def block(S, r0, r1, c0, c1):
    return [S.get(r, c) for r in range(r0, r1 + 1) for c in range(c0, c1 + 1)]


def index2(S, r0, c0, i, j):
    """INDEX(range starting at (r0, c0), i, j) with MATCH results i, j (errors pass through)."""
    e = err(i, j)
    return e if e else ref(S.get(r0 + i - 1, c0 + j - 1))


# ---------------------------------------------------------------- translations and links
def lang(book):
    """The LANG name: START!M10 (0 English, 1 French, 2 Portuguese, 3 Spanish)."""
    return int(num(book['START'].get(10, 13)))


def tr(book, row):
    """++OFFSET(translation!C<row>, 0, LANG): the label in the selected language."""
    return ref(book['translation'].get(row, 3 + lang(book)))


def trl(book, row, cols='CDEF'):
    """IF(START!L10="English", translation!C<row>, IF(..="French", D<row>, IF(..="Portuguese", E<row>, F<row>))).
    `cols` may name other cells (a full ref such as 'D853', or '#REF!') where the template's branches disagree."""
    lg = str(book['START'].get(10, 12) or '').lower()
    k = {'english': 0, 'french': 1, 'portuguese': 2}.get(lg, 3)
    c = cols[k] if isinstance(cols, str) else cols[k]
    if c.startswith('#'):
        return c
    if len(c) == 1:
        return ref(book['translation'].get(row, ci(c)))
    m = re.match(r'([A-Z]+)(\d+)$', c)
    return ref(book['translation'].get(int(m.group(2)), ci(m.group(1))))


_REF = re.compile(r"^(?:'?([^'!]+)'?!)?(\$?)([A-Z]{1,3})(\$?)(\d+)$")


def _parse(s):
    m = _REF.match(s.strip())
    if not m:
        raise ValueError(s)
    sh, ca, c, ra, r = m.groups()
    return sh, ci(c), int(r), bool(ca), bool(ra)


def links(book, sheet, spec):
    """Plain references, one per line: `dst src`, where dst is a cell or a range and src a cell (optionally
    'Sheet'!-qualified; same sheet otherwise). Over a range, src moves with the cell unless $-anchored, as when a
    formula =src is filled across dst. A blank source reads as 0; '#REF!' as src writes that error."""
    S = book[sheet]
    for line in spec.strip().splitlines():
        line = line.strip()
        if not line:
            continue
        dst, src = line.split(None, 1)
        a, b = (dst.split(':') + [dst])[:2]
        _, c0, r0, _, _ = _parse(a)
        _, c1, r1, _, _ = _parse(b)
        if src.strip() == REF_ERR:
            for r in range(r0, r1 + 1):
                for c in range(c0, c1 + 1):
                    S.set(r, c, REF_ERR)
            continue
        sh, sc, sr, ca, ra = _parse(src)
        T = book[sh] if sh else S
        for r in range(r0, r1 + 1):
            for c in range(c0, c1 + 1):
                S.set(r, c, ref(T.get(sr if ra else sr + r - r0, sc if ca else sc + c - c0)))


def isnum_or(v, alt):
    """IF(ISNUMBER(v), v, alt)."""
    return v if isnumber(v) else alt


# ================================================================ Chart Data
# The four external indicator blocks (PV debt/GDP, PV debt/exports, debt service/exports, debt service/revenue) share
# one layout from their first row b. Per block: the row of the indicator on the baseline/standard stress sheets,
# the row on the sheets laid out like 'C1_Combined CL', the row of 'C4_Market_financing', the row of the
# customised scenario, and the threshold cell on CI Summary.
EXT = [  # b, std row, CL row, C4 row, custom row, threshold
    (38, 35, 101, 82, 82, 'I11'),
    (80, 36, 102, 95, 83, 'I10'),
    (122, 39, 103, 96, 86, 'I13'),
    (164, 40, 104, 99, 87, 'I14'),
]
# Offsets within a block: 0 baseline, 1 A1 historical, 2-7 B1-B6, 9 C1, 10-12 C2-C4, 13 A2 customised,
# 15-18 B2/B6 market and non-market variants, 20-22 C2-C4 sources, 23-24 baseline and A1 again, 25 most extreme
# shock (MX), 26 MX of a one-year-only breach (for the chart), 27 MX among tailored tests, 28 threshold,
# 29-30 baseline / MX breach flags, 31-35 labels, 36-37 number of baseline / shock breaches in the ten years.
STRESS = [2, 3, 4, 5, 6, 7, 9, 10, 11, 12]   # rows ranked for the most extreme shock


def _ranking(S, b, s, thr, am=False, odd_summary=False):
    """The most-extreme-shock machinery of one block (columns Z..AK). Rows b+2..b+12 are the stress tests, s the
    summary row, thr the threshold row. A shock "breaches once" when exactly one of the ten years E..N is above
    the threshold and the first projection year is not; such shocks are ranked separately so that a one-off
    breach does not set the risk rating."""
    rows = [b + o for o in STRESS]
    t_e, t_d = S.get(thr, 5), S.get(thr, 4)
    for r in rows:
        S.set(r, ci('Z'), countif_gt(rowvals(S, r, 5, 14), t_e))          # years above threshold, excl. 1st
        d = S.get(r, 4)
        S.set(r, ci('AA'), iif(gt(d, t_d), 1, 0) if isnumber(d) else 0)     # 1st-year breach
        S.set(r, ci('AB'), iif(is_(S.get(r, 26), 1), 1, 0))               # one-off breach excl. 1st year
        S.set(r, ci('AC'), iif(is_(S.get(r, 28), 1), iif(is_(S.get(r, 27), 1), 0, 1), 0))  # one-off incl. 1st
        S.set(r, ci('AD'), iif(is_(S.get(r, 29), 0), 1, 0))               # not a one-off breach
        S.set(r, ci('AE'), xmax(rowvals(S, r, 5, 14)))                     # 10-year maximum
    sum_ac = xsum(colvals(S, ci('AC'), b + 2, b + 12))
    sum_ad = xsum(colvals(S, ci('AD'), b + 2, b + 12))
    for r in rows:
        ae = S.get(r, ci('AE'))
        S.set(r, ci('AF'), iif(gt(sum_ac, 0), iif(is_(S.get(r, ci('AC')), 1), ae, 0), 0))   # max of one-offs
        S.set(r, ci('AG'), iif(gt(sum_ad, 0), iif(is_(S.get(r, ci('AD')), 1), ae, 0)))     # max of the others
        S.set(r, ci('AH'), iif(gt(S.get(r, ci('AF')), 0), large(rowvals(S, r, 5, 14), 2), ae)
              if isnumber(S.get(r, 5)) else 0)                                            # max excl. one-off year
    rk = lambda c: colvals(S, ci(c), b + 2, b + 12)
    S.set(s, ci('AF'), xmax(rk('AF')))
    S.set(s, ci('AG'), xmax(rk('AG')))
    for r in rows + ([s] if odd_summary else []):
        S.set(r, ci('AI'), iif(gt(sum_ac, 0), rank(S.get(r, ci('AF')), rk('AF')), 0))
        S.set(r, ci('AJ'), iif(is_(sum_ac, 0), rank(S.get(r, ci('AG')), rk('AG')),
                               rank(S.get(r, ci('AH')), rk('AH'))))
        if r == s:
            break
        S.set(r, ci('AK'), iif(iif(is_(S.get(r, ci('AI')), 1), is_(S.get(r, ci('AJ')), 1), False), 1, 0))
    if am:                                   # rank of the one-off maxima among the tailored tests
        for r in range(b + 9, b + 13):
            S.set(r, ci('AM'), rank(S.get(r, ci('AF')), colvals(S, ci('AF'), b + 9, b + 12)))
    # summary row
    S.set(s, ci('AC'), sum_ac)
    for c in (['AK'] if odd_summary else ['AI', 'AJ', 'AK']):
        S.set(s, ci(c), xsum(rk(c)))
    S.set(s + 3, ci('AF'), iif(gt(S.get(s, ci('AF')), S.get(s, ci('AG'))), 1, 0))


def _mx_rows(S, b, s, tail_col, tail_key):
    """Rows b+25..b+27: the path of the most extreme shock, of the one-off breach (shown only when it is the larger
    and not the MX itself) and of the tailored test ranked tail_key in column tail_col."""
    yrs = rowvals(S, 35, 4, 25)
    i_mx = match(1, colvals(S, ci('AJ'), b + 2, b + 12))
    i_one = match(1, colvals(S, ci('AI'), b + 2, b + 12))
    i_tail = match(tail_key, colvals(S, ci(tail_col), b + 9, b + 12))
    one_off = gt(S.get(s, ci('AF')), 0)
    one_off = iif(one_off, is_(S.get(s + 3, ci('AF')), 1), False)
    for c in YRS:
        j = match(S.get(35, c), yrs)
        S.set(b + 25, c, index2(S, b + 2, 4, i_mx, j))
        S.set(b + 26, c, iif(is_(S.get(s, ci('AK')), 1), NA, iif(one_off, index2(S, b + 2, 4, i_one, j), NA)))
        S.set(b + 27, c, index2(S, b + 9, 4, i_tail, j))


def _mx_labels(book, S, b, s):
    """Labels b+31..b+35: name of the MX shock, chart label, and the one-off shock's label when it differs."""
    S.set(b + 31, 3, index2(S, b + 2, 2, match(1, colvals(S, ci('AJ'), b + 2, b + 12)), 1))
    S.set(b + 32, 3, concat(S.get(b + 32, 1), ': ', S.get(b + 31, 3), ''))
    blank = iif(iif(is_(S.get(s, ci('AI')), 0), True, is_(S.get(s, ci('AK')), 1)), True, False)
    one_off = iif(gt(S.get(s, ci('AF')), 0), is_(S.get(s + 3, ci('AF')), 1), False)
    S.set(b + 33, 3, iif(blank, '', iif(one_off, index2(S, b + 2, 2, match(1, colvals(S, ci('AI'), b + 2, b + 12)),
                                                         1), '')))
    S.set(b + 34, 3, iif(is_(S.get(b + 31, 3), S.get(b + 33, 3)), '', S.get(b + 33, 3)))
    S.set(b + 35, 3, iif(blank, '', iif(one_off, concat(tr(book, 1978), ': ', S.get(b + 34, 3)), '')))


def _breaches(S, b):
    """Rows b+29/b+30: baseline and MX path above the threshold; b+36/b+37 their counts over D..N."""
    for c in YRS:
        S.set(b + 29, c, iif(gt(S.get(b + 23, c), S.get(b + 28, c)), 1, 0))
        S.set(b + 30, c, iif(gt(S.get(b + 25, c), S.get(b + 28, c)), 1, 0))
    S.set(b + 36, 4, xsum(rowvals(S, b + 29, 4, 14)))
    S.set(b + 37, 4, xsum(rowvals(S, b + 30, 4, 14)))


def _choose(S, r, alt1, alt2, old_new=None):
    """IF($I$21=$A<alt1>, D<alt1>, D<alt2>) over D..X: the market or non-market variant of B2/B6; with old_new
    given, wrapped in IF(Old_New_Scenario=0, 0, ...)."""
    for c in YRS:
        v = iif(is_(S.get(21, 9), S.get(alt1, 1)), ref(S.get(alt1, c)), ref(S.get(alt2, c)))
        S.set(r, c, iif(is_(old_new, 0), 0, v) if old_new is not None else v)


def _tailored(S, r0, src_off):
    """C2-C4 rows: IFERROR(IF($I$21=$A<r>, D<r+src_off>, " "), " "): the tailored test path when it applies."""
    for r in range(r0, r0 + 3):
        for c in YRS:
            v = iif(is_(S.get(21, 9), S.get(r, 1)), ref(S.get(r + src_off, c)), ' ')
            S.set(r, c, ' ' if iserr(v) else v)


def chart_data(book):
    S = book[CD]
    o31 = 'Output 3-1 Stress-external'
    o32 = 'Output 3-2 Stress-public'
    old_new = book.name('Old_New_Scenario')
    cse = book['Customized Scenario-External']
    csp = book['Customized Scenario - public']

    # --- header, years, tailored-test switches
    S.set(6, 4, ref(book.name('Country')))
    links(book, CD, "D35:X35 'Macro-Debt_Data'!U5")
    for r, cell in ((17, 'C9'), (18, 'C10'), (19, 'C11')):          # tailored tests switched on
        S.set(r, 9, iif(is_(book['Input 6 - Tailored Tests'][cell], 'Yes'), 1, 0))
    S.set(34, 2, trl(book, 1986))
    for c, txt in (('Z', 'Number of breaches exc. 1st year - '), ('AA', '1st year breach - '),
                   ('AB', 'One-off breach, exc. 1st year - ')):
        S.set(36, ci(c), concat(txt, S.get(35, 4)))

    # --- external block labels (block 1 from the table; the others repeat it)
    S.set(38, 2, tr(book, 1113))
    for r, t in zip(range(39, 46), (1996, 1980, 1990, 1981, 1983, 1985, 1991)):
        S.set(r, 2, trl(book, t))
    links(book, CD, f"""
        C36 '{o31}'!A9
        C38 '{o31}'!A11
        C39 '{o31}'!A14
        C40:C45 '{o31}'!A18
        C47:C50 '{o31}'!A26
        B48 $F$17
        B49 $F$18
        B50 $F$19
        C51 'Customized Scenario-External'!B8
        C58:C60 '{o31}'!A27
        B61:B62 B38
        B66 C66""")
    for r in (48, 49, 50):                                          # applicable tailored test (1/0)
        i = match(S.get(r, 2), colvals(S, 6, 17, 19))
        S.set(r, 1, index2(S, 17, 6, i, 4))
    S.set(51, 2, '' if eq(cse['D3'], 'No') else ref(cse['B20']))
    S.set(53, 1, ref(S.get(50, 1)))                                 # market financing applies -> market variant
    S.set(54, 1, iif(is_(S.get(53, 1), 1), 0, 1))
    S.set(55, 1, ref(S.get(50, 1)))
    S.set(56, 1, ref(S.get(54, 1)))
    S.set(61, 3, trl(book, 1995))
    S.set(62, 3, trl(book, 1996))
    S.set(66, 3, trl(book, 1998))
    S.set(66, 2, S.get(66, 3))
    S.set(69, 1, concat(tr(book, 1997), ' 1/'))
    S.set(70, 1, tr(book, 1997))
    for k, b in enumerate((80, 122, 164)):
        bb = '+' if k < 2 else ''
        links(book, CD, f"""
            C{b - 2} '{o31}'!{('A33', 'A57', 'A81')[k]}
            C{b}:C{b + 1} $C$38
            C{b + 1} $C$39
            B{b + 2}:B{b + 7} B40
            C{b + 2} $C$40
            C{b + 3} $C$41
            C{b + 4} $C$42
            C{b + 5} $C$43
            C{b + 6} $C$44
            C{b + 7} $C$45
            B{b + 9} B47
            C{b + 9} $C$47
            A{b + 10}:B{b + 12} A48
            C{b + 10} $C$48
            C{b + 11} $C$49
            C{b + 12} $C$50
            B{b + 13} $B$51
            C{b + 13} $C$51
            C{b + 14} C52
            A{b + 15}:B{b + 18} A53
            C{b + 15} $C$53
            C{b + 16} $C$54
            C{b + 17} $C$55
            C{b + 18} $C$56
            C{b + 19} $C$57
            C{b + 20} $C$58
            C{b + 21} $C$59
            C{b + 22} $C$60
            C{b + 23} C61
            C{b + 24} C62
            C{b + 25} C63
            C{b + 26} $C$64
            C{b + 27} $C$65
            C{b + 28} C66
            C{b + 29} $C$67
            C{b + 30} C68
            A{b + 31} $A$69
            A{b + 32} $A$70
            C{b + 36} $C$74
            C{b + 37} $C$75""")
        if k:                                                       # blocks 3-4 repeat the baseline B labels
            links(book, CD, f"B{b + 23}:B{b + 24} B61")

    # --- external blocks: indicator paths
    for b, row, clr, c4r, cus, thr in EXT:
        links(book, CD, f"""
            D{b}:X{b} 'Baseline - external'!N{row}
            D{b + 1}:X{b + 1} A1_historical_ext!D{row}
            D{b + 2}:X{b + 2} B1_GDP_ext!D{row}
            D{b + 4}:X{b + 4} B3_Exports_ext!D{row}
            D{b + 5}:X{b + 5} 'B4_other flows_ext'!D{row}
            D{b + 6}:X{b + 6} B5_depreciation_ext!D{row}
            D{b + 9}:X{b + 9} 'C1_Combined CL'!E{clr}
            D{b + 15}:X{b + 15} B2_PB_mkt_pub!E{clr}
            D{b + 16}:X{b + 16} B2_PB_non_mkt_pub!E{clr}
            D{b + 17}:X{b + 17} B6_Combo_mkt_ext!D{row}
            D{b + 18}:X{b + 18} 'B6_Combo_non-mkt_ext'!D{row}
            D{b + 20}:X{b + 20} 'C2_Natural disaster'!E{clr}
            D{b + 21}:X{b + 21} 'C3_Commodity prices_ext'!D{row}
            D{b + 22}:X{b + 22} C4_Market_financing!D{c4r}
            D{b + 23}:X{b + 24} D{b}
            D{b + 28}:X{b + 28} 'CI Summary'!$I${thr[1:]}""")
        _choose(S, b + 3, b + 15, b + 16, old_new)                  # B2 primary balance
        _choose(S, b + 7, b + 17, b + 18)                           # B6 combination
        _tailored(S, b + 10, 10)                                    # C2-C4
        for c in YRS:                                               # A2 customised scenario
            S.set(b + 13, c, NA if eq(cse['D3'], 'No') else ref(cse.get(cus, c)))

    # --- external blocks: most extreme shock, breaches and labels
    for k, (b, *_rest) in enumerate(EXT):
        _ranking(S, b, b + 13, b + 28, am=k < 2, odd_summary=k == 2)
        _mx_rows(S, b, b + 13, 'AM' if k == 0 else 'AI', S.get(21, 9))
        _breaches(S, b)
        _mx_labels(book, S, b, b + 13)

    # --- signals: breaches of any external indicator (rows 74, 116, 158, 200) excluding 1-year breaches
    exclude = S.get(16, ci('AC'))
    any_gt = lambda o: iif(any(gt(S.get(b + o, 4), exclude) is True for b, *_ in EXT), 1, 0)
    S.set(12, 4, any_gt(36))
    S.set(13, 4, any_gt(37))
    for r, b in zip((14, 15, 16, 17), (38, 80, 122, 164)):         # MX shock names
        S.set(r, 4, ref(S.get(b + 31, 3)))

    # --- public block 1: PV of debt-to-GDP (with breach tests against the public benchmark)
    b = 239
    links(book, CD, f"""
        C237 '{o32}'!B10
        B239:B246 B38
        C239 '{o32}'!B12
        C240 '{o32}'!B15
        C241:C243 '{o32}'!B19
        C244:C246 '{o32}'!B22
        B248 B47
        C248:C251 '{o32}'!B27
        A249:B251 A48
        C252 'Customized Scenario - public'!$B$7
        C253 C178
        A254:B257 A53
        C254 $C$53
        C255 $C$54
        C256 $C$55
        C257 $C$56
        C258 $C$57
        C259 $C$58
        C260 $C$59
        C261 $C$60
        C262 C61
        C263 C62
        C264 C63
        C265 $C$64
        C266 $C$65
        A270 $A$69
        A271 $A$70
        C275 $C$74
        C276 $C$75""")
    S.set(235, 2, trl(book, 1994))
    S.set(252, 2, '' if eq(csp['C3'], 'No') else ref(csp['B54']))
    S.set(267, 2, tr(book, 1977))
    links(book, CD, """
        D239:X239 'Baseline - public'!O42
        D240:X240 A1_Historical_pub!E13
        D241:X241 B1_GDP_pub!E13
        D245:X245 B5_depreciation_pub!E13
        D248:X248 'C1_Combined CL'!E13
        D254:X254 B2_PB_mkt_pub!E13
        D255:X255 B2_PB_non_mkt_pub!E13
        D256:X256 B6_combo_mkt_pub!E13
        D257:X257 'B6_combo_non-mkt_pub'!E13
        D259:X259 'C2_Natural disaster'!E13
        D260:X260 C3_commodity_prices_pub!E13
        D261:X261 'Baseline - public'!O93
        D262:X263 D239
        D267 'CI Summary'!$L$9""")
    for c in range(5, 25):                                          # benchmark carried across the years
        S.set(267, c, ref(S.get(267, c - 1)))
    _choose(S, 242, 254, 255)                                       # B2 primary balance
    for r in (243, 244):                                            # B3/B4 (not run for public debt)
        for c in YRS:
            S.set(r, c, iif(is_(old_new, 0), 0, ref(book['Baseline - public'].get(r - 152, c + 11))))
    _choose(S, 246, 256, 257)                                       # B6 combination
    _tailored(S, 249, 10)
    for c in YRS:
        S.set(252, c, NA if eq(csp['C3'], 'No') else ref(csp.get(123, c + 1)))
    _ranking(S, b, 252, 267)
    _mx_rows(S, b, 252, 'AI', S.get(21, 9))
    _breaches(S, b)
    _mx_labels(book, S, b, 252)
    S.set(12, 9, iif(gt(S.get(275, 4), exclude), 1, 0))             # fiscal signal: baseline / shock breach
    S.set(13, 9, iif(gt(S.get(276, 4), exclude), 1, 0))
    S.set(14, 9, ref(S.get(270, 3)))

    # --- public blocks 2-3 (PV debt/revenue, debt service/revenue) and block 4 (debt service/GDP): paths only,
    #     the MX is simply the stress test with the highest 10-year maximum
    links(book, CD, """
        C279 'Output 3-2 Stress-public'!B34
        C281:C282 C239
        B283:B288 B40
        C283:C288 C241
        B290 B47
        C290:C293 C248
        A291:B293 A48
        B294 $B$252
        C294 $C$252
        C295 $C$52
        A296:B299 A53
        C296 $C$53
        C297 $C$54
        C298 $C$55
        C299 $C$56
        C300 $C$57
        C301 $C$58
        C302 $C$59
        C303 $C$60
        C304:C305 C61
        C306 C63
        C308 C65
        C316 'Output 3-2 Stress-public'!B58
        C318:C320 C281
        B320:B325 B40
        C321 C242
        C322:C323 C285
        C324 C287
        C325 C246
        B327 B47
        C327:C330 C248
        A328:B330 A48
        B331 $B$252
        C331 $C$252
        C332 $C$52
        A333:B336 A53
        C333 $C$53
        C334 $C$54
        C335 $C$55
        C336 $C$56
        C337 $C$57
        C338 $C$58
        C339 $C$59
        C340 $C$60
        C341:C342 C61
        C343 C63
        C345 C65
        B351:C358 B239
        B360:C364 B248
        A361:A363 A48
        C365:C373 C253
        A366:A369 A53""")
    for b, base, rows, oldn, cus, tkey in ((281, 'O43', (95, 96, 97, 95, 96, 97), 'O96', 192, 'I21'),
                                           (318, 'O45', (93, 94, 95, 93, 94, 95), 'O105', 190, 1),
                                           (351, 'O109', (94, 95, 96, 94, 95, 96), 'O110', 191, None)):
        a1, c1, c2 = {281: (95, 95, 96), 318: (93, 93, 94), 351: (94, 94, 95)}[b]
        c3 = {281: 97, 318: 95, 351: 96}[b]
        b4 = {281: 'O98', 318: 'O107', 351: 'O112'}[b]
        links(book, CD, f"""
            D{b}:X{b} 'Baseline - public'!{base}
            D{b + 1}:X{b + 1} A1_Historical_pub!E{a1}
            D{b + 2}:X{b + 2} B1_GDP_pub!E{a1}
            D{b + 6}:X{b + 6} B5_depreciation_pub!E{a1}
            D{b + 9}:X{b + 9} 'C1_Combined CL'!E{a1}
            D{b + 15}:X{b + 15} B2_PB_mkt_pub!E{a1}
            D{b + 16}:X{b + 16} B2_PB_non_mkt_pub!E{a1}
            D{b + 17}:X{b + 17} B6_combo_mkt_pub!E{a1}
            D{b + 18}:X{b + 18} 'B6_combo_non-mkt_pub'!E{a1}
            D{b + 20}:X{b + 20} 'C2_Natural disaster'!E{c2}
            D{b + 21}:X{b + 21} C3_commodity_prices_pub!E{c3}
            D{b + 22}:X{b + 22} 'Baseline - public'!{b4}""")
        _choose(S, b + 3, b + 15, b + 16)
        for r in (b + 4, b + 5):
            m = _parse(oldn)
            for c in YRS:
                S.set(r, c, iif(is_(old_new, 0), 0,
                                ref(book['Baseline - public'].get(m[2] + r - b - 4, m[1] + c - 4))))
        _choose(S, b + 7, b + 17, b + 18)
        _tailored(S, b + 10, 10)
        for c in YRS:
            S.set(b + 13, c, NA if eq(csp['C3'], 'No') else ref(csp.get(cus, c + 1)))
        if tkey is None:
            continue
        rows = [b + o for o in STRESS]
        for r in rows:
            S.set(r, ci('Z'), xmax(rowvals(S, r, 5, 14)))
        for r in rows:
            S.set(r, ci('AA'), rank(S.get(r, ci('Z')), colvals(S, ci('Z'), b + 2, b + 12)))
        for r in rows[6:]:
            S.set(r, ci('AC'), rank(S.get(r, ci('Z')), colvals(S, ci('Z'), b + 9, b + 12)))
        links(book, CD, f"D{b + 23}:X{b + 24} D{b}")
        yrs = rowvals(S, 35, 4, 25)
        i_mx = match(1, colvals(S, ci('AA'), b + 2, b + 12))
        key = S.get(21, 9) if tkey == 'I21' else 1
        i_tail = match(key, colvals(S, ci('AC'), b + 9, b + 12))
        for c in YRS:
            j = match(S.get(35, c), yrs)
            S.set(b + 25, c, index2(S, b + 2, 4, i_mx, j))
            S.set(b + 27, c, index2(S, b + 9, 4, i_tail, j))
        S.set(b + 29, 1, ref(S.get(69, 1)))
        S.set(b + 29, 3, index2(S, b + 2, 2, i_mx, 1))
        S.set(b + 30, 1, ref(S.get(70, 1)))
        S.set(b + 30, 3, concat(S.get(b + 30, 1), ': ', S.get(b + 29, 3), ''))

    # --- moderate-risk tool: space to absorb shocks for each external indicator
    for r, xrow, thr, base in ((208, 208, 66, 38), (215, 208, 108, 80), (222, 214, 150, 122), (229, 214, 192, 164)):
        for i in (0, 1):                                            # (1-x)*threshold, (1-y)*threshold
            for c in YRS:
                S.set(r + i, c, arith(lambda x, t: (1 - x / 100) * t, S.get(xrow + i, 2), S.get(thr, c))
                      if eq(S.get(205, 3), 1) else '')
        for c in YRS:
            S.set(r + 2, c, '' if eq(S.get(r, c), '') else ref(S.get(base, c)))
            lo, hi, v = S.get(r + 1, c), S.get(r, c), S.get(r + 2, c)
            S.set(r + 3, c, '' if eq(lo, '') else iif(le(v, lo), 0, iif(gt(v, hi), 2, 1)))
            S.set(r + 4, c, ref(S.get(thr, c)))
        S.set(r + 3, ci('Y'), xmax(rowvals(S, r + 3, 4, 14)))
    links(book, CD, """
        C219 C212
        C226 C219
        C233 C212""")
    space = xmax(colvals(S, ci('Y'), 211, 232))
    S.set(206, ci('Y'), iif(lt(space, S['E27']), 'Moderate with Substantial space',
                            iif(is_(space, S['E26']), 'Moderate with some space', 'Moderate with limited space')))

    # --- debt accumulation chart
    links(book, CD, """
        D379:N379 D35
        D381:N381 'Baseline - external'!N51
        D382:N382 Ext_Debt_Data!F408
        D383:N383 'Baseline - external'!N64""")
    for r in range(380, 384):
        S.set(r, 3, tr(book, 1048 + r - 380))

    # --- risk signals: 3 High (baseline breach), 2 Moderate (shock breach only), 1 Low
    for c in (4, 9):
        S.set(11, c, iif(is_(S.get(12, c), 1), 3, iif(iif(is_(S.get(12, c), 0), is_(S.get(13, c), 1), False), 2, 1)))
    d11, i11 = S.get(11, 4), S.get(11, 9)
    S.set(11, 12, iif(iif(is_(d11, 1), is_(i11, 1), False), 1, iif(iif(is_(d11, 3), True, is_(i11, 3)), 3, 2)))
    S.set(10, 4, book.vlookup(S.get(11, 4), 'NumRiskTable', 2))
    S.set(10, 9, book.vlookup(S.get(11, 9), f"'{CD}'!$Z$19:$AA$23", 2))
    S.set(10, 12, book.vlookup(S.get(11, 12), f"'{CD}'!$Z$19:$AA$23", 2))
    space = xmax(colvals(S, ci('Y'), 211, 232))
    S.set(23, 4, iif(lt(space, S['E27']), 'Substantial space', iif(is_(space, S['E26']), 'Some space',
                                                                    'Limited space')))


# ================================================================ Output 3-1 / 3-2 (Tables 3 and 4)
def text_int(v):
    """TEXT(v, "#"): the number rounded to an integer, zero shown as ''."""
    if iserr(v):
        return v
    if isinstance(v, str):
        return v
    n = math.floor(abs(num(v)) + 0.5) * (1 if num(v) >= 0 else -1)
    return '' if n == 0 else str(int(n))


def _cd_lookup(book, label, r0, r1, year):
    """INDEX('Chart Data'!$C$r0:$X$r1, MATCH(label, $C$r0:$C$r1, 0), MATCH(year, 'Chart Data'!$C$35:$X$35, 0))."""
    C = book[CD]
    i = match(label, colvals(C, 3, r0, r1)) if not iserr(label) else label
    j = match(year, rowvals(C, 35, 3, 24)) if not iserr(year) else year
    return index2(C, r0, 3, i, j)


def _na(book):
    return ref(book.name('n.a.'))


def output_3_1(book):
    sh = 'Output 3-1 Stress-external'
    S, C = book[sh], book[CD]
    mdd = book['Macro-Debt_Data']
    S['A2'] = concat(tr(book, 1103), ' 3. ', book.name('Country'), tr(book, 1104), ' ', mdd['U5'], '-', mdd['AE5'])
    S['A3'] = trl(book, 1105)
    S['C5'] = concat(trl(book, 1107), ' 1/')
    links(book, sh, "C6:W6 'Baseline - external'!N8")
    for r, t in ((9, 1111), (11, 1113), (13, 1115), (17, 1120), (33, 1138), (57, 1141), (81, 1142), (105, 1143),
                 (106, 1144), (108, 1146)):
        S.set(r, 1, trl(book, t))
    S['A14'] = concat(trl(book, 1117), ' ', text_int(mdd['U5']), '-', text_int(mdd['AE5']), ' 2/')
    cse = book['Customized Scenario-External']
    S['A15'] = ref(cse['B8']) if eq(cse['D3'], 'Yes') else 0
    for r, t in ((18, 1121), (19, 1122), (20, 1125), (22, 1127), (23, 1128)) + tuple((25 + i, 1131 + i)
                                                                                     for i in range(5)):
        S.set(r, 1, tr(book, t))
    S['A21'] = concat(tr(book, 1126), ' 3/')
    S['A109'] = concat('1/ ', trl(book, 1147))
    S['A110'] = concat('2/ ', trl(book, 1148))
    S['A111'] = concat('3/ ', trl(book, 1152))
    links(book, sh, """
        A31 'Chart Data'!C66
        A35 A11
        A37:A38 A13
        A39 $A$15
        A41:A47 A17
        A49 A25
        A50 A$26
        A51 A$27
        A52 A$28
        A53 A$29
        A55 $A$31
        A59 A11
        A61:A62 A13
        A63 $A$15
        A65:A71 A17
        A73:A77 A25
        A79 $A$31
        A83 A11
        A85:A86 A13
        A87 $A$15
        A89:A95 A17
        A97:A101 A25
        A103 $A$31""")
    na = _na(book)
    # indicator paths looked up by label from Chart Data, one table block per indicator
    for rows, r0 in (((11, 14, 15, 18, 19, 20, 21, 22, 23, 26), 38), ((35, 38), 80),
                     ((59, 62, 66, 67, 68, 69, 70, 71, 74), 122), ((83, 86, 90, 91, 92, 93, 94, 95, 98), 164)):
        for r in rows:
            for c in range(3, 24):
                S.set(r, c, _cd_lookup(book, S.get(r, 1), r0, r0 + 13, S.get(6, c)))
    # tailored tests C2-C4 (when switched on), the rest straight from Chart Data rows
    for r0, src in ((27, 48), (51, 90), (75, 132), (99, 184)):
        for i in range(3):
            for c in range(3, 24):
                S.set(r0 + i, c, ref(C.get(src + i, c + 1)) if eq(C.get(17 + i, 9), 1) else na)
    links(book, sh, """
        C31:W31 'Chart Data'!D66
        C39:W39 'Customized Scenario-External'!D83
        C42:W47 'Chart Data'!D82
        C50:W50 'Chart Data'!D89
        C55:W55 'Chart Data'!D108
        C63:W63 'Customized Scenario-External'!D86
        C79:W79 'Chart Data'!D150
        C87:W87 'Customized Scenario-External'!D87
        C103:W103 'Chart Data'!D192
        C106 'PV Stress'!D10""")
    for c in range(4, 24):                                          # grant element carried across
        S.set(106, c, ref(S.get(106, c - 1)))


def output_3_2(book):
    sh = 'Output 3-2 Stress-public'
    S, C = book[sh], book[CD]
    o31 = 'Output 3-1 Stress-external'
    links(book, sh, f"""
        D7 '{o31}'!C5
        D8 'Macro-Debt_Data'!U5""")
    for c in range(5, 25):
        S.set(8, c, arith(lambda y: y + 1, S.get(8, c - 1)))
    S['B2'] = concat(tr(book, 1168), ' 4. ', book.name('Country'), tr(book, 1169), ' ', S['D8'], '-', S['N8'])
    S['B10'] = tr(book, 1176)
    S['B12'] = trl(book, 1178)
    S['B34'] = tr(book, 1193)
    S['B58'] = tr(book, 1194)
    S['B102'] = trl(book, 1195)
    S['B103'] = concat('1/ ', trl(book, 1198))
    S['B104'] = concat('2/ ', trl(book, 1199))
    S['B105'] = concat('3/ ', trl(book, 1152))
    csp = book['Customized Scenario - public']
    S['B16'] = ref(csp['B7']) if eq(csp['C3'], 'Yes') else 0
    links(book, sh, f"""
        B14:B15 '{o31}'!A13
        B18:B24 '{o31}'!A17
        B26:B30 '{o31}'!A25
        B32 'Chart Data'!B267
        D32:X32 'Chart Data'!D267
        B36 $B$12
        B38 $B$14
        B39 $B$15
        B40 $B$16
        D40:X40 'Customized Scenario - public'!E192
        B42 $B$18
        B43 $B$19
        B44 $B$20
        A45:B46 #REF!
        B47 $B$21
        B48 $B$22
        B49 $B$23
        B50 $B$24
        B52 $B$26
        B53 $B$27
        B54 $B$28
        B55 $B$29
        B56 $B$30
        B60 $B$12
        B62 $B$14
        B63 $B$15
        B64 $B$16
        D64:X64 'Customized Scenario - public'!E190
        B66 $B$18
        B67 $B$19
        B68 $B$20
        B69 $B$21
        B70 $B$22
        B71 $B$23
        B72 $B$24
        B74 $B$26
        B75 $B$27
        B76 $B$28
        B77 $B$29
        B78 $B$30
        B82 $B$12
        B84 $B$14
        B85 $B$15
        B86 $B$16
        B88 $B$18
        B89 $B$19
        B90 $B$20
        B91 $B$21
        B92 $B$22
        B93 $B$23
        B94 $B$24
        B96 $B$26
        B97 $B$27
        B98 $B$28
        B99 $B$29
        B100 $B$30""")
    na = _na(book)
    for rows, tail, r0 in (((12, 15, 16, 19, 20, 21, 22, 23, 24, 27), 28, 239),
                           ((36, 39, 43, 44, 45, 46, 47, 48, 49, 50, 53), 54, 281),
                           ((60, 63, 67, 68, 69, 70, 71, 72, 75), 76, 318),
                           ((82, 85, 89, 90, 91, 92, 93, 94, 97), 98, 351)):
        for r in rows:
            for c in range(4, 25):
                S.set(r, c, _cd_lookup(book, S.get(r, 2), r0, r0 + 13, S.get(8, c)))
        for i in range(3):                                          # tailored tests C2-C4, when switched on
            for c in range(4, 25):
                S.set(tail + i, c, _cd_lookup(book, S.get(tail + i, 2), r0, r0 + 13, S.get(8, c))
                      if eq(C.get(17 + i, 9), 1) else na)


# ================================================================ Output 7 - Risk rating summary
def output_7(book):
    sh = 'Output 7 - Risk rating summary'
    S, C, lk = book[sh], book[CD], book['lookup']
    S['E5'] = ref(book.name('Country'))
    S['D11'] = ref(book.name('Country'))
    S['D12'] = tr(book, 1754)
    links(book, sh, """
        B5 'Input 1 - Basics'!B7
        B6 'Input 1 - Basics'!B8
        E6 'Input 1 - Basics'!C8
        D23 'Input 2 - Debt Coverage'!C7
        C24:D31 'Input 2 - Debt Coverage'!B8
        C34:D34 'Input 2 - Debt Coverage'!B19
        G34 'Input 2 - Debt Coverage'!D19
        H35 'Input 2 - Debt Coverage'!D20
        I35:J35 'Input 2 - Debt Coverage'!F20
        C36:D39 'Input 2 - Debt Coverage'!B21
        G36:I39 'Input 2 - Debt Coverage'!D21
        D40 'Input 2 - Debt Coverage'!C25
        I40 'Input 2 - Debt Coverage'!F25
        D41 'Input 2 - Debt Coverage'!B26
        E48 'Chart Data'!D10
        E54 'Chart Data'!L10
        D61 'CI Summary'!B6
        D64:F65 'CI Summary'!B8
        E66:F66 'CI Summary'!C10
        D67 'CI Summary'!B12""")
    dc = book['Input 2 - Debt Coverage']
    for r in range(24, 32):                                         # sub-sectors covered (X)
        v = dc.get(r - 16, 5)
        S.set(r, 8, ('-' if r == 24 else '') if v is None else v)
    for r in range(36, 41):                                         # reasons for deviating from the defaults
        v = dc.get(r - 15, 7)
        S.set(r, 10, '' if v is None else v)
    # mechanical vs final ratings: "(select)" until the user picks the final rating
    S['D47'] = trl(book, 206)
    S['D48'] = trl(book, 693, ('C', REF_ERR, REF_ERR, REF_ERR))
    S['E50'] = ref(lk['Z5']) if eq(S['E48'], S['E49']) else ref(lk['Z4'])
    S['E56'] = ref(lk['Z5']) if eq(S['E54'], S['E55']) else ref(lk['Z4'])
    S['D56'] = ref(S['D50'])
    S['E14'] = 'Please select the final external rating below in cell D49' if eq(S['E49'], '(select)') \
        else ref(S['E49'])
    S['E15'] = 'Please select the final overall rating below in cell D55' if eq(S['E55'], '(select)') \
        else ref(S['E55'])
    S['E17'] = concat('No' if eq(S['E50'], 'No') and eq(S['E56'], 'No') else 'Yes:', ' ', S['E58'])
    # other risk factors: space within the moderate category, market-financing pressure
    na = _na(book)
    S['E73'] = ref(C['D23']) if is_(C['D11'], C['Z20']) is True else na
    ab12 = book['Output 5-2 Market module']['AB12']
    S['E75'] = (na if iserr(ab12) else ref(ab12)) if eq(book['Input 6 - Tailored Tests']['C11'], 'Yes') else na


# ================================================================ chart sheets: titles, legends, footnotes
def _labels(book, sh, spec):
    """Translated labels, (cell, row[, suffix[, prefix]]): prefix & ++OFFSET(translation!C<row>, 0, LANG) & suffix."""
    S = book[sh]
    for cell, row, *rest in spec:
        suf, pre = (list(rest) + ['', ''])[:2]
        S[cell] = concat(pre, tr(book, row), suf)


def _and(*conds):
    """AND(...): the first error among the conditions, else whether all hold."""
    e = err(*conds)
    return e if e else all(conds)


def _all_eq(S, pairs):
    """AND(a1=b1, a2=b2, ...) over cells of one sheet."""
    return _and(*(is_(S[a], S[b]) for a, b in pairs))


def _no_yes(cond):
    """IF(cond, "No", "Yes"): "No" = the default settings were kept."""
    return cond if iserr(cond) else ('No' if cond else 'Yes')


def output_2_1(book):
    sh = 'Output 2-1 Stress_Charts_Ex'
    S, C = book[sh], book[CD]
    mdd = book['Macro-Debt_Data']
    o31 = 'Output 3-1 Stress-external'
    S['B3'] = concat(tr(book, 1062), ' 1. ', book.name('Country'), tr(book, 1063), ' ', mdd['U5'], '-', mdd['AE5'])
    links(book, sh, f"""
        AH137 'Chart Data'!B62
        BP137 'Chart Data'!A69
        M138 'Chart Data'!B61
        CY138 'Chart Data'!B66
        CQ148 'Input 7 - Residual Financing'!C7
        CZ148 'Input 7 - Residual Financing'!D7
        AT149:AT150 'Input 7 - Residual Financing'!B8
        CQ150 'Input 7 - Residual Financing'!C9
        AT152 'Input 7 - Residual Financing'!B12
        AT153:AT156 'Input 7 - Residual Financing'!B14
        CQ153:CQ156 'Input 7 - Residual Financing'!C14
        CZ153:CZ156 'Input 7 - Residual Financing'!E14
        AS158 'Input 7 - Residual Financing'!B18
        C162 '{o31}'!A108""")
    custom = eq(book['Customized Scenario-External']['D3'], 'Yes')
    S['L142'] = ref(C['B177']) if custom else ''
    S['D143'] = 1 if custom else ''
    one_off = any(isnumber(C.get(r, 4)) for r in (64, 106, 148, 190))   # a one-off breach is charted
    S['BQ142'] = tr(book, 1750) if one_off else ''
    S['BG143'] = 1 if one_off else ''
    _labels(book, sh, [('G147', 2043), ('G148', 2047), ('AA148', 1571), ('AF148', 1573), ('F158', 2042),
                       ('G153', 2048), ('G154', 2049), ('G155', 2050), ('G156', 2051)])
    S['AT147'] = concat(tr(book, 592), '*')
    S['C163'] = concat('1/ ', tr(book, 1095), ' ', mdd['AE5'], tr(book, 1096))
    S['C164'] = concat('2/ ', tr(book, 1070))
    # customisation of the default settings: "Yes" when any user value differs from its default
    st = book['Input 6(optional)-Standard Test']
    S['AA150'] = _no_yes(_all_eq(st, [(f'C{r}', f'D{r}') for r in (17, 18, 21, 22, 25, 26, 29, 30, 32, 33, 37, 38,
                                                                     41, 42, 44, 45, 47, 48, 50, 51, 53, 54, 57, 58)]))
    S['AF150'] = _no_yes(_all_eq(st, [('G17', 'H17'), ('G21', 'H21'), ('G22', 'I22')] +
                                 [(f'G{r}', f'H{r}') for r in (25, 36, 37, 38, 41, 44, 47, 48, 56, 57)]))
    S['G150'] = ' ' if eq(S['AA150'], 'No') and eq(S['AF150'], 'No') else 'Standardized Tests'
    dc = book['Input 2 - Debt Coverage']
    S['AA153'] = _no_yes(_and(is_(dc['D21'], dc['F21']), is_(dc['D22'], dc['F22']),
                              is_(arith(lambda x: x / 100, dc['D23']), dc['E33']), is_(dc['D24'], dc['F24'])))
    tt = book['Input 6 - Tailored Tests']
    na = _na(book)
    on = lambda cell: eq(tt[cell], 'Yes')
    S['AA154'] = _no_yes(_all_eq(tt, [('G21', 'H21')])) if on('C9') else na
    S['AF154'] = _no_yes(_all_eq(tt, [('K21', 'L21'), ('K22', 'L22')])) if on('C9') else na
    S['AA155'] = _no_yes(_all_eq(tt, [(f'G{r}', f'H{r}') for r in (26, 32, 36, 38, 39, 40, 41, 46, 49, 50)])) \
        if on('C10') else na
    S['AF155'] = _no_yes(_all_eq(tt, [('K26', 'L26'), ('K27', 'L27')])) if on('C10') else na
    S['AA156'] = _no_yes(_all_eq(tt, [(f'G{r}', f'H{r}') for r in (52, 54, 55, 56, 58)])) if on('C11') else na
    S['AF156'] = _no_yes(_all_eq(tt, [('K58', 'L58')])) if on('C11') else na


def output_2_2(book):
    sh = 'Output 2-2 Stress_Charts_Pub'
    S, C = book[sh], book[CD]
    mdd = book['Macro-Debt_Data']
    S['B3'] = concat(tr(book, 1098), ' 2. ', book.name('Country'), tr(book, 1099), ' ', mdd['U5'], '-', mdd['AE5'])
    links(book, sh, """
        C25 'Chart Data'!B239
        E25 'Chart Data'!A270
        C26 'Chart Data'!B267
        E26 'Chart Data'!B240
        B31 'Output 2-1 Stress_Charts_Ex'!AT147
        E31:F31 'Input 7 - Residual Financing'!H7
        B32:B38 'Input 7 - Residual Financing'!G8
        E33:E35 'Input 7 - Residual Financing'!H9
        F33:F35 'Input 7 - Residual Financing'!J9
        E38 'Input 7 - Residual Financing'!H14
        F38 'Input 7 - Residual Financing'!J14
        B39:B47 'Input 7 - Residual Financing'!G16
        E39:E40 'Input 7 - Residual Financing'!H16
        F39:F40 'Input 7 - Residual Financing'!J16
        E42:E44 'Input 7 - Residual Financing'!H19
        F42:F44 'Input 7 - Residual Financing'!J19
        E46 'Input 7 - Residual Financing'!H23
        F46 'Input 7 - Residual Financing'!J23
        B49 'Output 3-2 Stress-public'!B102""")
    custom = eq(book['Customized Scenario - public']['C3'], 'Yes')
    S['C27'] = ref(C['B252']) if custom else ''
    S['B28'] = 1 if custom else ''
    S['E27'] = tr(book, 1750) if isnumber(C['D265']) else ''
    S['D28'] = 1 if isnumber(C['D265']) else ''
    S['B50'] = concat('1/ ', tr(book, 1095), ' ', mdd['AE5'], tr(book, 1096))


def output_4_1(book):
    sh = 'Output 4-1 - Forecast Error'
    book[sh]['A1'] = concat(tr(book, 1202), ' 3. ', book.name('Country'), tr(book, 1203))
    _labels(book, sh, [('A2', 1204), ('B3', 1207), ('B4', 1208), ('G3', 1231), ('G4', 1232), ('K3', 1233, ' 1/'),
                       ('K4', 1234), ('A21', 1205), ('B23', 1209), ('G23', 1231), ('G24', 1232),
                       ('K23', 1233, ' 1/'), ('B24', 1208), ('K24', 1234), ('A40', 1237, '', '1/ '),
                       ('A41', 1238, '', '2/ '), ('A42', 1240, '', '3/ ')])


def output_4_2(book):
    sh = 'Output 4-2 - Realism'
    book[sh]['A1'] = concat(tr(book, 1242), ' 4. ', book.name('Country'), tr(book, 1243))
    _labels(book, sh, [('A4', 1244), ('A5', 1245), ('L4', 1252, ' 1/'), ('A26', 1250, '', '1/ '),
                       ('L26', 1254, '', '1/ '), ('B29', 1259), ('N29', 1262), ('C30', 1249), ('N30', 1277),
                       ('O51', 1263), ('O53', 1264)])
    links(book, sh, """
        C51 'Realism 3 - Invest-Growth'!B20
        H51 'Realism 3 - Invest-Growth'!B21
        C53 'Realism 3 - Invest-Growth'!B23
        H53 'Realism 3 - Invest-Growth'!B24""")


def output_5_1(book):
    sh = 'Output 5-1 Moderate risk'
    S, mdd = book[sh], book['Macro-Debt_Data']
    S['C3'] = concat(tr(book, 1280), ' 5. ', book.name('Country'), tr(book, 1281), ' ', text_int(mdd['U5']), '-',
                     text_int(mdd['AE5']), ' 1/')
    _labels(book, sh, [('CS20', 1304), ('CS28', 1304, '', '(1-X)*'), ('CS36', 1304, '', '(1-Y)*&'),
                       ('AT144', 1295), ('BI144', 1296), ('BW144', 1297), ('F155', 1298, '', '1/ ')])
    links(book, sh, """
        M144 'Chart Data'!B66
        AG145 'Chart Data'!B61
        F154 'Output 3-1 Stress-external'!A108""")


def output_5_2(book):
    """Market-financing module: maximum GFN over the first three years and the EMBI spread against their
    benchmarks; both above -> high, neither -> low pressure."""
    sh = 'Output 5-2 Market module'
    S, na = book[sh], _na(book)
    S['B3'] = concat(tr(book, 697), ' 5.', ' ', book.name('Country'), tr(book, 698))
    _labels(book, sh, [('B8', 699), ('B9', 700), ('B10', 701), ('B12', 702), ('B14', 703, '', '1/ '),
                       ('B15', 704, '', '2/ ')])
    links(book, sh, """
        B1 'Output 1-1 - External DSA'!B1
        O135 'Chart Data'!B61
        AQ135 'Chart Data'!B50
        BU135 'Chart Data'!C66
        F137 'Output 3-1 Stress-external'!A108""")
    S['AB9'] = xmax(rowvals(book['Baseline - public'], 47, ci('O'), ci('Q')))
    bas = book['Input 1 - Basics']
    S['AX9'] = na if eq(bas['C28'], 'No') else ref(bas['C29'])
    S['AB10'] = iif(gt(S['AB9'], S['AB8']), 'Yes', iif(le(S['AB9'], S['AB8']), 'No', na))
    ax = S['AX9']
    S['AX10'] = na if isinstance(ax, str) else iif(gt(ax, S['AX8']), 'Yes', iif(le(ax, S['AX8']), 'No'))
    lk = book['lookup']
    a, x = S['AB10'], S['AX10']
    S['AB12'] = ref(lk['AM4']) if eq(a, 'No') and eq(x, 'No') else (
        ref(lk['AM6']) if eq(a, 'Yes') and eq(x, 'Yes') else ref(lk['AM5']))


def output_6(book):
    sh = 'Output 6 - Prob (if applicable)'
    book[sh]['C3'] = concat(tr(book, 1359), ' XX. ', book.name('Country'), tr(book, 1360), ' 1/')
    _labels(book, sh, [('D158', 2056, '', '1/ ')])
    links(book, sh, "D214 'Output 3-1 Stress-external'!A108")


# ================================================================ Probability approach
def normdist(x):
    """NORMDIST(x, 0, 1, TRUE)."""
    return 0.5 * math.erfc(-x / math.sqrt(2))


def probability(book):
    """Borderline test (is the largest baseline / stress value within the bandwidth I8 around the threshold?) and
    the probit probability of debt distress for each indicator path."""
    sh = 'Probability approach'
    S = book[sh]
    links(book, sh, f"""
        A1 'Output 1-1 - External DSA'!B1
        N6 'Input 1 - Basics'!C7
        A26 'Chart Data'!C36
        B27:B29 'Chart Data'!C61
        H27:AB29 'Chart Data'!D61
        B30 'Chart Data'!C66
        H30:AB30 'Chart Data'!D66
        B33 'Chart Data'!C70
        A34 'Chart Data'!C78
        B35:B37 'Chart Data'!C103
        H35:AB37 'Chart Data'!D103
        B38 'Chart Data'!C108
        H38:AB38 'Chart Data'!D108
        B41 'Chart Data'!C112
        A42 'Chart Data'!C120
        B43:B45 'Chart Data'!C145
        H43:AB45 'Chart Data'!D145
        B46 'Chart Data'!C150
        H46:AB46 'Chart Data'!D150
        B49 'Chart Data'!C154
        A50 'Chart Data'!C162
        B51:B53 'Chart Data'!C187
        H51:AB53 'Chart Data'!D187
        B54 'Chart Data'!C192
        H54:AB54 'Chart Data'!D192
        B57 'Chart Data'!C196
        I11 B27
        I63 H64
        J63 H65
        K63 H66
        L63 H67""")
    S['A2'] = trl(book, 839)
    S['H4'] = tr(book, 2055)
    S['H6'] = trl(book, 841, ('C', 'D', 'E', 'F842'))
    S['H8'] = trl(book, 843, ('C', 'D', 'E', 'F844'))
    S['J10'] = trl(book, 846, ('C', 'D853', 'E', 'F'))
    for c, row in (('K10', 847), ('L10', 848), ('M10', 849)):
        S[c] = trl(book, row)
    S['N10'] = trl(book, 850, ('C', 'D', 'E', 'F851'))
    S['I12'] = trl(book, 851, ('C', 'D846', 'E', 'F852'))
    S['A59'] = trl(book, 852, ('C', 'D874', 'E874', 'D889'))
    S['H62'] = trl(book, 878, ('C', 'D', 'E', 'E889'))
    S['N63'] = trl(book, 873, ('C', 'C874', 'D873', REF_ERR))
    S['A76'] = trl(book, 876, ('C', REF_ERR, 'I877', 'D891'))
    S['A78'] = trl(book, 877, ('C', 'D876', 'E876', 'D892'))
    # bandwidth around each threshold: (1 -/+ I8/2) * threshold
    band = S['I8']
    for thr in (30, 38, 46, 54):
        for c in range(8, 29):
            S.set(thr + 1, c, arith(lambda t, w: t * (1 - w / 2), S.get(thr, c), band))
            S.set(thr + 2, c, arith(lambda t, w: t * (1 + w / 2), S.get(thr, c), band))
    # borderline classification of the baseline (odd rows) and the stress tests (even rows)
    for p, base in enumerate((27, 35, 43, 51)):
        thr, lo, hi = (S.get(base + 3, 8), S.get(base + 4, 8), S.get(base + 5, 8))
        for r, mx in ((11 + 2 * p, xmax(block(S, base, base, 8, 28))),
                      (12 + 2 * p, xmax(block(S, base + 1, base + 2, 8, 28)))):
            S.set(r, 10, iif(gt(mx, thr), 1, 0))                                    # breach
            if p == 1:                                       # the template bounds this one by the threshold..lower
                S.set(r, 11, iif(_and(ge(mx, thr), lt(mx, lo)), 1, 0))
            else:
                S.set(r, 11, iif(_and(ge(mx, lo), lt(mx, thr)), 1, 0))              # near breach
            S.set(r, 12, iif(_and(ge(mx, thr), le(mx, hi)), 1, 0))                  # small breach
            S.set(r, 13, iif(gt(mx, hi), 1, 0))                                     # significant breach
            S.set(r, 14, iif(_and(ge(mx, lo), le(mx, hi)), 1, 0))                   # within the band
    for r in range(13, 21):                                        # baseline / stress-test labels repeated
        S.set(r, 9, ref(S.get(11 + (r - 11) % 2, 9)))
    for r in (19, 20):
        for c in range(10, 15):
            S.set(r, c, xmax([S.get(r - 8 + 2 * i, c) for i in range(4)]))
    # years
    S['H24'] = ref(book.name('ProjectionYear'))
    for c in range(9, 29):
        S.set(24, c, arith(lambda y: y + 1, S.get(24, c - 1)))
    for c in range(7, 2, -1):
        S.set(24, c, arith(lambda y: y - 1, S.get(24, c + 1)))
    for c in range(8, 29):
        S.set(76, c, ref(S.get(24, c)))
    for c in range(7, 2, -1):
        S.set(76, c, arith(lambda y: y - 1, S.get(76, c + 1)))
    # history used for the regressors (rows 108-117)
    imp = book['Imported data']
    for c in range(3, 19):
        S.set(108, c, ref(S.get(76, c)))
    for c in range(3, 19):
        i = match(S.get(109, 1), colvals(imp, 2, 81, 82))
        j = match(S.get(108, c), rowvals(imp, 81, 2, 22))
        v = index2(imp, 81, 2, i, j)
        S.set(109, c, ref(S.get(109, c - 1)) if iserr(v) else v)
    links(book, sh, """
        C110:R110 'Macro-Debt_Data'!P107
        C112:R112 'Input 3 - Macro-Debt data(DMX)'!S184
        C113:R113 'Input 3 - Macro-Debt data(DMX)'!S38
        C115:R115 'Input 3 - Macro-Debt data(DMX)'!S45
        C116:R116 'Macro-Debt_Data'!P56
        C117:R117 'Input 3 - Macro-Debt data(DMX)'!S183""")
    for c in range(3, 19):
        S.set(111, c, arith(lambda a, b: a / b * 100, S.get(112, c), S.get(113, c)))
        S.set(114, c, arith(lambda a, b: a / b * 100, S.get(115, c), S.get(116, c)))
    # regressors: 5-year history + projection averages, held constant over the projection
    for r, src in ((77, 109), (78, 110), (79, 111), (80, 114), (81, 117)):
        S.set(r, 8, average(rowvals(S, src, 3, 18)))
        for c in range(9, 29):
            S.set(r, c, ref(S.get(r, 8)))
    # probabilities of debt distress (probit), with the indicator's probability threshold below
    links(book, sh, """
        A83 $A$26
        B84:B87 B27
        A89 $A$34
        B90:B93 B35
        A92 $A$86
        A95 $A$42
        B96:B99 B43
        A98 $A$86
        A101 $A$50
        B102:B105 B51
        A104 $A$86""")
    for k, (r0, src, ccol) in enumerate(((84, 27, 9), (90, 35, 10), (96, 43, 11), (102, 51, 12))):
        coef = lambda r: S.get(r, ccol)
        for i in range(3):
            for c in range(8, 29):
                x = arith(lambda v, b0, b1, b2, b3, b4, b5, b6, b7, g, rr, gs, inv, rem:
                          b0 * v / 100 + b1 * g + b2 * rr / 100 + b3 * gs / 100 + b4 * (gs / 100) ** 2 +
                          b5 * inv / 100 + b6 * rem / 100 + b7,
                          S.get(src + i, c), coef(64 + k), coef(68), coef(69), coef(70), coef(71), coef(72),
                          coef(73), coef(74), S.get(77, c), S.get(78, c), S.get(79, c), S.get(80, c), S.get(81, c))
                S.set(r0 + i, c, x if iserr(x) else normdist(x) * 100)
        for c in range(8, 29):
            S.set(r0 + 3, c, arith(lambda t: t * 100, S.get(64 + k, 15)))


# ================================================================ Output 1-1 / 1-2 (Tables 1 and 2)
def _cols(*spans):
    out = []
    for a, b in spans:
        out += list(range(ci(a), ci(b) + 1))
    return out


def _trl_rows(book, S, col, spec):
    """Row labels of a table: (row, translation row[, suffix]) -> trl label & suffix."""
    for r, t, *suf in spec:
        S.set(r, col, concat(trl(book, t), *suf) if suf else trl(book, t))


# Table 1: historical C..J and L..N, projections P..U, W..AJ and AL; the source column on 'Baseline - external'
T1_HIST = {c: c if c <= 10 else c - 1 for c in _cols(('C', 'J'), ('L', 'N'))}
T1_PROJ = {c: c - (2 if c <= 21 else 3 if c <= 36 else 4) for c in _cols(('P', 'U'), ('W', 'AJ'), ('AL', 'AL'))}
T1_ALL = {**T1_HIST, **T1_PROJ}


def output_1_1(book):
    sh = 'Output 1-1 - External DSA'
    S, be = book[sh], book['Baseline - external']
    show = lambda r, c, src_r: isnum_or(be.get(src_r, T1_ALL[c]), '...')
    # years
    for c, src in T1_ALL.items():
        S.set(6, c, ref(be.get(8, src)))
    # rows shown for every year: (rows, row shift to 'Baseline - external')
    for rows, d in (((8, 9, 11), 4), (range(13, 21), 4), ((22, 23, 24, 27), 4), ((30, 31, 32), 5),
                    ((33, 34, 35), 6), (range(38, 43), 14), (range(44, 50), 16), ((51,), -2), ((54, 55), -21),
                    ((56,), -18), ((59,), -17)):
        for r in rows:
            for c in T1_ALL:
                S.set(r, c, show(r, c, r + d))
    for r, d in ((12, 4), (21, 4), (25, 4), (26, 4), (50, -2)):    # historical years only
        for c in T1_HIST:
            S.set(r, c, show(r, c, r + d))
    for r in (57, 58):                                             # PV of debt: from the last actual year (N)
        for c in ([14] if r == 57 else []) + list(T1_PROJ):
            S.set(r, c, show(r, c, r - 7))
    edd = book['Ext_Debt_Data']
    for c in T1_PROJ:
        S.set(43, c, ref(edd.get(408, c - (10 if c <= 21 else 11 if c <= 36 else 12))))   # grant element
        S.set(26, c, arith(lambda a, b: a + b, show(26, c, 30), be.get(29, T1_PROJ[c])))   # residual
        S.set(21, c, arith(lambda a, b: a + b, S.get(23, c), S.get(24, c)))              # endogenous dynamics
        S.set(12, c, arith(lambda a, b, d: a + b + d, S.get(13, c), S.get(20, c), S.get(21, c)))
    # averages: historical (D..J, L..N) and projection (P..U, W..AA)
    hist = lambda r: average(rowvals(S, r, 4, 10), rowvals(S, r, 12, 14))
    proj = lambda r: average(rowvals(S, r, 16, 21), rowvals(S, r, 23, 27))
    for r in (8, 9, 12, 13, 14, 17, 19, 20, 26, 38, 39, 40, 41, 42, 44, 51):
        S.set(r, ci('AN'), hist(r))
    for r in (8, 9, 12, 13, 14, 17, 19, 20, 26, 38, 39, 40, 41, 42, 43, 44, 48, 49, 51):
        S.set(r, ci('AO'), proj(r))
    links(book, sh, """
        AQ8:AQ9 'Input 1 - Basics'!B33
        BG8:BG9 'Input 1 - Basics'!C33""")
    # labels
    S['B3'] = concat(tr(book, 894), ' 1. ', book.name('Country'), tr(book, 895), ' ', S['L6'], '-', S['AL6'])
    S['B4'] = trl(book, 896)
    S['E5'] = trl(book, 897)
    S['P5'] = trl(book, 898)
    S['AN5'] = concat(trl(book, 899), ' 8/')
    S['AN6'] = tr(book, 900)
    S['AO6'] = tr(book, 898)
    _trl_rows(book, S, 2, [(8, 903, ' 1/ '), (9, 904), (11, 905), (12, 906)] +
              [(r, 894 + r) for r in range(13, 21)] + [(21, 915, ' 2/ ')] + [(r, 894 + r) for r in range(22, 26)] +
              [(26, 920, ' 3/ '), (27, 921), (29, 925), (30, 926), (31, 927), (32, 933), (33, 929), (34, 930),
               (35, 931), (37, 934), (38, 936), (39, 937), (40, 938, ' 4/ '), (41, 939), (42, 940), (43, 941),
               (44, 942), (45, 943, ' 5/ '), (46, 944), (47, 945), (48, 946, ' 6/ '), (49, 947, ' 6/ '), (50, 950),
               (51, 951), (53, 949), (54, 923, ' 7/ '), (55, 924), (56, 928), (57, 952), (58, 953), (59, 932),
               (64, 956), (65, 957)])
    for r, n, t in ((66, 1, 958), (68, 3, 961), (69, 4, 962), (70, 5, 964), (71, 6, 965), (72, 7, 968),
                    (73, 8, 963)):
        S.set(r, 2, concat(f'{n}/ ', trl(book, t)))
    resid = is_(book['Input 1 - Basics']['C33'], book['lookup']['X4'])
    S['B67'] = concat('2/ ', iif(resid, tr(book, 960), tr(book, 959)))


# Table 2: historical C..J and L..N, projections T..AC, AE..AN and AP
T2_HIST = _cols(('C', 'J'), ('L', 'N'))
T2_PROJ = _cols(('T', 'AC'), ('AE', 'AN'), ('AP', 'AP'))
T2_ALL = T2_HIST + T2_PROJ


def _bp_col(c):
    """Column of 'Baseline - public' shown in Table 2 column c."""
    return c + 1 if c <= 10 else c if c <= 14 else c - 5 if c <= 29 else c - 6 if c <= 40 else c - 7


def _mdd_col(c):
    """Column of 'Macro-Debt_Data' shown in Table 2 column c."""
    return c + 7 if c <= 10 else c + 6 if c <= 14 else c + 1 if c <= 29 else c if c <= 40 else c - 1


def output_1_2(book):
    sh = 'Output 1-2 - Public DSA'
    S, bp, mdd = book[sh], book['Baseline - public'], book['Macro-Debt_Data']
    # years: back from N (last actual year) and forward
    S['N6'] = ref(mdd['T5'])
    for k in range(T2_ALL.index(14) - 1, -1, -1):
        S.set(6, T2_ALL[k], arith(lambda y: y - 1, S.get(6, T2_ALL[k + 1])))
    for k in range(T2_ALL.index(14) + 1, len(T2_ALL)):
        S.set(6, T2_ALL[k], arith(lambda y: y + 1, S.get(6, T2_ALL[k - 1])))
    show = lambda r, c, d, dots='...': isnum_or(bp.get(r + d, _bp_col(c)), dots)
    plain = lambda r, c, d: ref(bp.get(r + d, _bp_col(c)))
    no_c = [c for c in T2_ALL if c != 3]                           # rows that start in column D
    for r, d, cols in ((8, 4, T2_ALL), (11, 10, T2_ALL), (12, 10, T2_HIST[1:]), (17, 10, T2_HIST[1:]),
                       (21, 10, T2_HIST[1:]), (28, 10, T2_HIST[1:])):
        for c in cols:
            S.set(r, c, show(r, c, d))
    for c in T2_ALL:
        S.set(9, c, show(9, c, 11, '...' if c <= 14 else '\u2026'))
    for r in (13, 14, 15, 16, 18, 19, 20):
        for c in T2_ALL:
            S.set(r, c, show(r, c, 10))
    for r in range(22, 28):
        for c in no_c:
            S.set(r, c, show(r, c, 10))
    for r, d, cols in ((31, 11, no_c), (32, 11, no_c), (33, 11, no_c), (35, 10, no_c), (36, 10, no_c),
                       (37, 10, T2_ALL), (41, 11, no_c), (42, 11, no_c), (43, 11, no_c), (46, 11, no_c),
                       (47, 11, T2_ALL), (48, 11, no_c), (49, 11, T2_ALL), (54, 11, T2_ALL),
                       (55, 11, T2_ALL), (56, 11, no_c)):
        for c in cols:
            S.set(r, c, plain(r, c, d))
    S.set(54, 30, ref(bp.get(65, 25)))                             # AD54 continues the T..AC run
    for c in _cols(('D', 'J'), ('L', 'AC')):                       # contingent liabilities: L..AC read in place
        S.set(58, c, ref(bp.get(69, c + 1 if c <= 10 else c)))
    for c in [c for c in no_c if c > 29]:
        S.set(58, c, plain(58, c, 11))
    for c in T2_PROJ:
        S.set(17, c, ref(S.get(18, c)))                            # automatic debt dynamics
        S.set(12, c, arith(lambda a, b, d: a + b + d, S.get(13, c), S.get(17, c), S.get(23, c)))
        o38 = bp.get(38, _bp_col(c))
        o31 = bp.get(31, _bp_col(c))
        S.set(28, c, arith(lambda a, b: a + b, o38, isnum_or(o31, 0)) if isnumber(o38) else '...')   # residual
    for c in T2_ALL:
        m = _mdd_col(c)
        S.set(38, c, arith(lambda a, b: a / b, mdd.get(101, m), mdd.get(60, m)))     # GFN in US dollars
        v = mdd.get(87, m)
        S.set(45, c, '...' if eq(v, 0) else ref(v))                # interest rate on domestic debt
        S.set(51, c, arith(lambda x: 1 / x, S.get(49, c)))         # US dollar per LC
        if c != 3:
            S.set(44, c, isnum_or(mdd.get(86, m), '...'))          # interest rate on external debt
    for r in (42, 43):                                             # real GDP growth, first year
        v = mdd.get(r + 65, _mdd_col(3))
        S.set(r, 3, ref(v) if isnumber(arith(lambda x: x * 100, v)) else '\u2026')
    for k, c in enumerate(T2_ALL[1:], 1):                          # depreciation / appreciation vs previous column
        p = T2_ALL[k - 1]
        S.set(50, c, arith(lambda a, b: (a / b - 1) * 100, S.get(49, c), S.get(49, p)))
        S.set(52, c, arith(lambda a, b: (a / b - 1) * 100, S.get(51, c), S.get(51, p)))
    for c in T2_HIST[1:]:                                          # real exchange rate depreciation
        v = arith(lambda d, us, inf: (100 + d) * (1 + us / 100) / (1 + inf / 100) - 100,
                  S.get(50, c), S.get(55, c), S.get(54, c))
        S.set(53, c, v if isnumber(v) else '\u2026')
    for c in [c for c in T2_ALL if c >= 12]:                       # debt-stabilising primary deficit
        S.set(57, c, arith(lambda a, b: -a + b, S.get(11, c), S.get(13, c)))
    # averages: historical and projection
    h2 = lambda r: average(rowvals(S, r, 4, 10), rowvals(S, r, 12, 14))
    h1 = lambda r: average(rowvals(S, r, 4, 14))
    p2 = lambda r: average(rowvals(S, r, 20, 29), [S.get(r, 31)])
    p1 = lambda r: average(rowvals(S, r, 20, 29))
    for r in (8, 9, 12, 13, 14, 16, 23, 28, 42, 43, 44, 45, 47, 53, 54, 56, 57):
        S.set(r, ci('AR'), h2(r))
    for r in (46, 48, 49, 50, 51, 52, 55):
        S.set(r, ci('AR'), h1(r))
    for r in (8, 9, 12, 13, 14, 16, 23, 28, 42, 44, 47, 54, 56, 57):
        S.set(r, ci('AS'), p2(r))
    for r in (43, 45, 46, 48, 49, 50, 51, 52, 55):
        S.set(r, ci('AS'), p1(r))
    links(book, sh, """
        AV8 'Input 1 - Basics'!B33
        AY8 'Input 1 - Basics'!C33
        AV11 'Input 1 - Basics'!B34
        AY11 'Input 1 - Basics'!C34""")
    # labels
    S['B2'] = concat(tr(book, 894), ' 2. ', book.name('Country'), tr(book, 972), ' ', S['L6'], '-', S['AP6'])
    S['B3'] = trl(book, 973)
    S['E5'] = trl(book, 974)
    S['T5'] = trl(book, 976, ('C', 'D', 'E', REF_ERR))
    S['AR5'] = concat(trl(book, 978), ' 6/')
    S['AR6'] = tr(book, 900)
    S['AS6'] = ref(S['T5'])
    _trl_rows(book, S, 2, [(8, 979, ' 1/'), (9, 980), (10, 981), (11, 983)] + [(r, 972 + r) for r in range(12, 29)] +
              [(30, 1002), (31, 1003, ' 2/ '), (32, 1009), (33, 1010), (35, 1012, ' 3/'), (36, 1013, ' 3/'),
               (37, 1007, ' 4/'), (38, 1008), (40, 1016)] + [(r, 976 + r) for r in range(41, 57)] +
              [(57, 1014, ' 5/'), (58, 1006), (61, 1035)])
    for r, n, t in ((63, 2, 1038), (64, 3, 1039), (65, 4, 1040), (66, 5, 1043), (67, 6, 963)):
        S.set(r, 2, concat(f'{n}/ ', trl(book, t)))
    S['B62'] = concat('1/ ', tr(book, 1036), ' ', book['Input 2 - Debt Coverage']['D19'], ' ', tr(book, 1037), ' ',
                      book['Input 1 - Basics']['C33'], '.')


def compute(book, sheet):
    {CD: chart_data,
     'Output 3-1 Stress-external': output_3_1,
     'Output 3-2 Stress-public': output_3_2,
     'Output 7 - Risk rating summary': output_7,
     'Output 2-1 Stress_Charts_Ex': output_2_1,
     'Output 2-2 Stress_Charts_Pub': output_2_2,
     'Output 4-1 - Forecast Error': output_4_1,
     'Output 4-2 - Realism': output_4_2,
     'Output 5-1 Moderate risk': output_5_1,
     'Output 5-2 Market module': output_5_2,
     'Output 6 - Prob (if applicable)': output_6,
     'Probability approach': probability,
     'Output 1-1 - External DSA': output_1_1,
     'Output 1-2 - Public DSA': output_1_2}[sheet](book)
