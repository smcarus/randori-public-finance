"""FAN sheet: the debt fan chart module.

Two parts:

* compute(book, 'FAN') fills the sheet's formula cells: the data table (rows 64-86) that pulls debt and its
  drivers (growth, real interest rate, primary balance, real exchange rate, inflation, U.S. inflation, FX share,
  SD of debt revisions) from BaseDB with a Macrofw fallback, the stock-flow adjustment implied by the debt
  identity, the chart blocks (rows 28-61) that turn the simulated percentiles in Z:AE into stacked bands, and the
  debt fanchart index (rows 11-15): fan width, probability of debt non-stabilisation and debt x institutions,
  each scaled, AUC-weighted and summed into an index with a Low/Moderate/High signal.

* simulate(book) ports the VBA macro MainFanchart (module ModFanchart with its Mersenne Twister and ziggurat
  helpers). It bootstraps blocks of two consecutive historical years of the debt drivers, adds a normal shock
  to the starting debt level, runs 10,000 debt paths (historical fanchart: raw historical draws; final
  fanchart: baseline + de-meaned draws), sorts them per year and writes the 5/25/50/75/95th percentiles to
  Z33:AE37 and Z45:AE49 (and the realism-adjusted fan to Z57:AE61 when that adjustment triggers), plus the
  D12 (non-stabilisation probability, written as a value) and the realism row D18:G18. The macro also writes
  D11, D13 and D21 as formulas; those are compute()'s job and follow D18.
  The macro seeds its generator from VBA's Rnd after Randomize (the clock), so a run cannot be repeated from
  the workbook alone; simulate(book, seed=...) takes the seed, and SEED is the one that reproduces the
  template's stored fan (found by searching the 2^24 seeds Rnd can produce, see QUIRKS).
"""
import math

import numpy as np

from .xl import NA, calc, iserr, isnumber, match, num

SHEETS = ['FAN']

QUIRKS = [
    'D12 is written by the macro as the formula "=1-<paths with PB above DSPB>/<paths>", so the count is a '
    'literal inside the formula. simulate() writes D12 as a value; compute() keeps a D12 that is already '
    'there and otherwise falls back to the template\'s literals (DSPB_ABOVE/NTRAJ_LIT).',
    'D53:N53 use the defined name DatesCentralDB, which does not exist: #NAME?.',
    'Row 73 (SFA): the first year looks up debt and FX share one Macrofw column earlier (D67-1), later years '
    'use the previous column of the table; the FX valuation term uses the real exchange rate change times '
    'the (1+inflation) factor of the debt identity.',
    'N68:N77 (2011) have no IFERROR fallback; they read Macrofw only.',
    'The macro declares nearly everything As Single (32-bit): historical draws, averages, baselines, debt '
    'paths and sorted percentiles are float32, except the U.S. inflation baseline (Double) and the d0 '
    'shocks (Double). Arithmetic is reproduced in float32 as VBA does.',
    'The macro seeds the Mersenne Twister with Int(Rnd*2^32-2^31) after Randomize: the seed is clock '
    'dependent and only one of 2^24 values (Rnd has a 24-bit state).',
    'In the draw loop the macro also draws an unused random column (genrand_intbtw(1, 30)) before each block '
    'draw, so every other Mersenne Twister output is thrown away.',
    'The historical fanchart draws whole blocks (2 consecutive years) from years 1..21 of the 22-year sample, '
    'so the first year of the block can never be the last historical year.',
    'In the historical and final debt identity the FX term is fxs*e*(1+p), not fxs*(1+e)*(1+p) as in the '
    '(unused) historical-scenario path d_hscen.',
    'The SFA is computed and drawn but multiplied by use_sfa = 0, so it never enters the paths.',
    'The FX share is not drawn: year 1 uses the last historical value, later years the baseline lagged one '
    'year.',
    'Percentile k is the sorted path at position Single(k)*ntraj (0.05 -> 500, 0.95 -> 9500 after rounding '
    'Single to an index); the median averages positions 5000 and 5001 because ntraj is even.',
    'The macro reads FanHistogramRange (Config!AH19) into a String before knowing whether the realism '
    'adjustment is needed; in the template that cell is #N/A (fanchart group lookup fails), which in VBA is a '
    'type-mismatch error. simulate() reads it only when the adjustment triggers.',
    'find_pos_col returns the last midpoint of its bisection, not the insertion point.',
    'With the COVID adjustment on, the first block of the historical fanchart uses baseline + de-meaned '
    'draws and adds the baseline SFA unscaled (sfa_base + sfa_ddrw*use_sfa), so the SFA enters there even '
    'though use_sfa = 0.',
    'The template\'s stored fan comes from seed -300975616 = Int(Rnd*2^32-2^31) with Rnd = 7212922/2^24, '
    'the Rnd state reached by the second Rnd call of an Excel session (Randomize keeps the low byte of '
    'the 24-bit state, 195 after one call). Found by searching the Rnd states; with it every stored '
    'percentile and the 5357 count in D12 are reproduced bit for bit.',
    'VBA evaluates each statement in double precision and rounds to Single on assignment; running sums '
    '(averages, average shocks) round at every step. Rounding every operation to float32 instead moves '
    '44 of the 60 stored percentiles by up to 3.6e-7.',
]

DSPB_ABOVE, NTRAJ_LIT = 5357, 10000     # literals in the template's D12 formula, written by the last macro run
SEED = -300975616                       # MT seed of the template's stored run (see simulate)

YR0, YR1 = 4, 31                        # data table columns D..AE
DATA_ROWS = range(68, 78)               # GGXWDG_GDP .. SDDREV (row 73 SFA is derived)
COPY_ROWS = {79: 69, 80: 71, 81: 70, 82: 68, 83: 72, 85: 76}


def _v(x):
    """A looked-up cell as a formula sees it: blank -> 0."""
    return 0 if x is None else x


def compute(book, sheet='FAN'):
    F = book['FAN']
    proj = book.name('ProjYr')
    base_dates = book.hrow('BaseDBdates')
    mf_dates = book.hrow('MacrofwDates')

    # ---- data table (rows 64-86) ------------------------------------------------------------------------
    F.set(64, YR0, calc(lambda s: s + 1, book.name('StartYrDataIn')))           # years
    for c in range(YR0 + 1, YR1 + 1):
        F.set(64, c, calc(lambda y: y + 1, F.get(64, c - 1)))
    for c in range(YR0, YR1 + 1):
        F.set(65, c, calc(lambda y: y - proj, F.get(64, c)))                     # years from ProjYr
        F.set(66, c, match(F.get(65, c), base_dates))                            # BaseDB position
        F.set(67, c, match(F.get(65, c), mf_dates))                              # Macrofw position
    for r in DATA_ROWS:
        if r == 73:
            continue
        key = F.get(r, 2)
        for c in range(YR0, YR1 + 1):
            mf = calc(lambda v: v / 100, _v(book.vlookup(key, 'MacrofwData', F.get(67, c)))) \
                if not iserr(F.get(67, c)) else F.get(67, c)
            if c == 14:                                                            # N: no IFERROR
                F.set(r, c, mf)
                continue
            bd = F.get(66, c)
            v = _v(book.vlookup(key, 'BaseDBData', bd)) if not iserr(bd) else bd
            F.set(r, c, mf if iserr(v) else v)
    # SFA: debt change not explained by the debt identity
    sfa = lambda d, dl, r, g, pb, e, p, us, fx: \
        d - (dl * ((1 + r) * (1 + p) * (1 + us) + fx * e * (1 + p) + fx * (p - us)) / ((1 + g) * (1 + p) * (1 + us)) - pb)
    for c in range(YR0, YR1 + 1):
        if c == YR0:
            k = F.get(67, c)
            dl = calc(lambda v: v / 100, _v(book.vlookup(F.get(68, 2), 'MacrofwData', k - 1)))
            fx = calc(lambda v: v / 100, _v(book.vlookup(F.get(76, 2), 'MacrofwData', k - 1)))
        else:
            dl, fx = F.get(68, c - 1), F.get(76, c - 1)
        F.set(73, c, calc(sfa, F.get(68, c), dl, F.get(70, c), F.get(69, c), F.get(71, c), F.get(72, c),
                          F.get(74, c), F.get(75, c), fx))
    F.set(86, 2, 'NGDP_D')
    for c in range(YR0, YR1 + 1):
        for r, src in COPY_ROWS.items():                                           # 1.-7. drivers for the chart
            F.set(r, c, F.get(src, c))
        F.set(84, c, _v(book.vlookup(F.get(84, 2), 'MacrofwData', F.get(67, c))))  # 6. US deflator
        F.set(86, c, _v(book.vlookup(F.get(86, 2), 'MacrofwData', F.get(67, c))))  # 8. GDP deflator

    # ---- observation pick-up cell used by the macro (row 7) ---------------------------------------------
    F.set(7, 5, calc(lambda y: y - proj, F.get(7, 4)))
    F.set(7, 6, match(F.get(7, 5), [F.get(65, c) for c in range(1, YR1 + 1)]))
    k = F.get(7, 6)
    F.set(7, 7, k if iserr(k) else _v(_row_lookup(F, F.get(7, 3), k)))
    F.set(7, 8, match(F.get(6, 8), _col(F, 1)) + 1)
    F.set(7, 9, match(F.get(6, 9), _col(F, 1)) - 1)

    # ---- chart blocks ---------------------------------------------------------------------------------
    realism = bool(F.get(18, 4))
    cname = book.name('Cname')
    for top, title in ((28, 'historical'), (40, 'final'), (52, 'adjusted')):
        for c in range(5, 15):
            F.set(top, c, F.get(top, c - 1) + 1)                                   # years from ProjYr
        F.set(top, 16, f'{cname}: {title} fanchart (pct of GDP)')
        for c in range(4, 15):
            F.set(top + 2, c, proj + F.get(top, c))                                # calendar year
    for c in range(4, 15):
        F.set(29, c, match(F.get(28, c), base_dates))                              # BaseDB position
        F.set(53, c, '#NAME?')                                                     # DatesCentralDB: no such name
    # historical fanchart
    for c in range(4, 9):
        k = F.get(29, c)
        F.set(31, c, calc(lambda v: v * 100, _v(book.vlookup(F.get(31, 2), 'BaseDBData', k)) if not iserr(k) else k))
    F.set(32, 8, F.get(31, 8))
    for c in range(9, 15):
        k = F.get(29, c)
        F.set(32, c, calc(lambda v: v * 100, _v(book.vlookup(F.get(32, 2), 'BaseDBData', k)) if not iserr(k) else k))
    # final and adjusted fancharts: actual and baseline copied from the block above
    for top in (40, 52):
        for c in range(4, 9):
            F.set(top + 3, c, F.get(top - 9, c))
        F.set(top + 4, 8, F.get(top + 3, 8))
        for c in range(9, 15):
            F.set(top + 4, c, F.get(top - 8, c))
    # percentile bands: first band is the 5th percentile level, later bands the gap to the band below
    for r0 in (33, 45, 57):
        F.set(r0, 8, F.get(r0 - 1, 8))
        for i in range(5):
            r = r0 + i
            for c in range(9, 15):
                z = 26 + c - 9                                                     # Z.. AE
                if i == 0:
                    F.set(r, c, calc(lambda a: a * 100, F.get(r, z)))
                else:
                    F.set(r, c, calc(lambda a, b: (a - b) * 100, F.get(r, z), F.get(r - 1, z)))
    for i, code in enumerate(('FFC0005', 'FFC0525', 'FFC2550', 'FFC5075', 'FFC7595')):
        F.set(45 + i, 1, '' if realism else f'GGXWDG_GDP_{code}')
        F.set(57 + i, 1, f'GGXWDG_GDP_{code}' if realism else '')

    # ---- debt fanchart index (rows 11-22); D11, D12, D13 and D21 are the formulas the macro wrote ------
    F.set(21, 4, F.get(59 if realism else 47, 31))                                 # Debt(t+5): median, last year
    F.set(22, 4, book.vlookup(F.get(22, 2), 'BaseDBData', match(-1, base_dates)))  # institutional quality
    hi, lo = (61, 57) if realism else (49, 45)
    F.set(11, 4, calc(lambda a, b: a - b, F.get(hi, 31), F.get(lo, 31)))          # fan width (95th - 5th)
    if F.get(12, 4) is None:                                                       # prob. of non-stabilisation:
        F.set(12, 4, 1 - DSPB_ABOVE / NTRAJ_LIT)                                   # macro-owned literal formula
    F.set(13, 4, calc(lambda a, b: a * b, F.get(21, 4), F.get(22, 4)))
    auc = calc(lambda *g: sum(g), *(F.get(r, 7) for r in (11, 12, 13)))
    for r in (11, 12, 13):
        F.set(r, 6, calc(lambda d, e: d / e, F.get(r, 4), F.get(r, 5)))
        F.set(r, 8, calc(lambda g, s: g / s, F.get(r, 7), auc))
        F.set(r, 9, calc(lambda f, h: f * h, F.get(r, 6), F.get(r, 8)))
    idx = calc(lambda *v: sum(v), *(F.get(r, 9) for r in (11, 12, 13)))
    F.set(14, 9, idx)
    lo_t, hi_t = F.get(25, 4), F.get(25, 5)
    if iserr(idx):
        sig = idx
    elif idx >= num(hi_t):
        sig = 'High'
    elif idx <= num(lo_t):
        sig = 'Low'
    elif num(lo_t) < idx < num(hi_t):
        sig = 'Moderate'
    else:
        sig = NA
    F.set(15, 9, sig)


def _col(S, c):
    maxr = max(r for r, _ in S.cells)
    return [S.get(r, c) for r in range(1, maxr + 1)]


def _row_lookup(F, key, k):
    """VLOOKUP(key, FanDataIn, k, FALSE) over FAN!$68:$78."""
    from .xl import eq
    for r in range(68, 79):
        v = F.get(r, 1)
        if v is not None and eq(v, key):
            return F.get(r, k)
    return NA


# ======================================================================================================
# The macro MainFanchart (VBA module ModFanchart) and its random number helpers
# ======================================================================================================

class MersenneTwister:
    """MT19937 as ModuleMersenneTwister implements it with signed Longs and bit tricks (init_genrand,
    genrand_signedInt32, genrand_real2, genrand_intbtw); here with plain unsigned 32-bit integers."""
    N, M = 624, 397

    def __init__(self, seed):
        mt = [seed & 0xFFFFFFFF]
        for i in range(1, self.N):
            prev = mt[-1]
            mt.append((1812433253 * (prev ^ (prev >> 30)) + i) & 0xFFFFFFFF)
        self.mt, self.mti = mt, self.N

    def _twist(self):
        mt, N, M = self.mt, self.N, self.M
        for i in range(N):
            y = (mt[i] & 0x80000000) | (mt[(i + 1) % N] & 0x7FFFFFFF)
            mt[i] = mt[(i + M) % N] ^ (y >> 1) ^ (0x9908B0DF if y & 1 else 0)
        self.mti = 0

    def uint32(self):
        if self.mti == self.N:
            self._twist()
        y = self.mt[self.mti]
        self.mti += 1
        y ^= y >> 11
        y ^= (y << 7) & 0x9D2C5680
        y ^= (y << 15) & 0xEFC60000
        return y ^ (y >> 18)

    def signed_int32(self):                       # genrand_signedInt32: the same bits as a signed Long
        y = self.uint32()
        return y - (1 << 32) if y & 0x80000000 else y

    def real2(self):                              # genrand_real2: [0, 1)
        return self.uint32() / 4294967296.0

    def intbtw(self, lo, hi):                     # genrand_intbtw: Int(r*hi + (1-r)*lo + r)
        r = self.real2()
        return math.floor(r * hi + (1 - r) * lo + r)


def _zig_tables():
    """Part 1 of draw_zig_n: Marsaglia-Tsang ziggurat tables for 128 strips (kn(1) stays 0, as in the VBA)."""
    m1, dn, vn = 2147483647.0, 3.442619855899, 9.91256303526217E-03
    tn = dn
    q = vn / math.exp(-0.5 * dn * dn)
    kn, wn, fn = [0.0] * 128, [0.0] * 128, [0.0] * 128
    kn[0], kn[1] = (dn / q) * m1, 0.0
    wn[0], wn[127] = q / m1, dn / m1
    fn[0], fn[127] = 1.0, math.exp(-0.5 * dn * dn)
    for i in range(126, 0, -1):
        dn = math.sqrt(-2 * math.log(vn / dn + math.exp(-0.5 * dn * dn)))
        kn[i + 1] = (dn / tn) * m1
        tn = dn
        fn[i] = math.exp(-0.5 * dn * dn)
        wn[i] = dn / m1
    return kn, fn, wn


def _randn(mt, kn, fn, wn):
    """randn: one standard normal draw, line for line as the VBA."""
    r = 3.442619855899
    hz = mt.signed_int32()
    iz = abs(hz) % 128
    if abs(hz) < kn[iz]:
        return hz * wn[iz]
    while True:
        if iz == 0:                                            # tail beyond r
            while True:
                x = -0.2904764 * math.log(mt.real2())
                y = -math.log(mt.real2())
                if not x * x > y + y:
                    break
            return -r - x if hz <= 0 else r + x
        x = hz * wn[iz]
        if fn[iz] + mt.real2() * (fn[iz - 1] - fn[iz]) < math.exp(-0.5 * x * x):
            return x
        hz = mt.signed_int32()
        iz = abs(hz) % 128
        if abs(hz) < kn[iz]:
            return hz * wn[iz]


def draw_zig_n(mt, n, mu, sd):
    """draw_zig_n: n normal draws (Double) with mean mu and standard deviation sd."""
    tabs = _zig_tables()
    return np.array([_randn(mt, *tabs) * sd + mu for _ in range(n)])


def find_pos_col(comp, col):
    """find_pos_col over a sorted 1-based column (col[0] unused): the bisection's last midpoint."""
    floor, ceiling, mid = 0, len(col) - 1, 0
    while floor < ceiling:
        mid = (ceiling - floor) // 2 + floor
        if mid < 1:
            raise IndexError('find_pos_col: subscript out of range (VBA error 9)')
        if col[mid] < comp:
            floor = mid + 1
        elif col[mid] > comp:
            ceiling = mid - 1
        else:
            floor = ceiling
    return mid


def _vround(x):
    """VBA's conversion of a Double to an integer (array index, Integer/Long variable): round half to even."""
    return int(round(x))


S1 = np.float32                                       # VBA Single


def _single(x):
    """Assign a Double-evaluated expression to a Single variable (or array)."""
    return np.asarray(x, dtype=np.float64).astype(np.float32)


def _ensure_ok(F, rows, hist_cols, proj_cols, sd_cell):
    """missing_obs: every historical and projection value of the table rows must be a number."""
    bad = [F.get(r, 2) for r in rows if not all(isnumber(F.get(r, c)) for c in list(hist_cols) + list(proj_cols))]
    if bad or not isnumber(sd_cell):
        raise ValueError(f'fanchart: missing observations for {bad or ["SDDREV"]}')


def simulate(book, seed=SEED):
    """Port of MainFanchart: simulate the debt fan and write its outputs into FAN (values, not formulas).

    Returns a dict with the run's key numbers. With seed=SEED the template's stored fan is reproduced exactly.
    The macro draws its seed as Int(Rnd * 2^32 - 2^31) after Randomize; pass seed=None to do the same with
    Python's clock-seeded generator."""
    F, C = book['FAN'], book['Config']
    nm = book.name
    if seed is None:
        import random
        seed = math.floor(random.randrange(1 << 24) / 2 ** 24 * 2 ** 32 - 2 ** 31)

    # ---- Task 1: setup ----------------------------------------------------------------------------------
    rng_begins, rng_ends = F.get(7, 8), F.get(7, 9)            # H7, I7: first and last row of the data table
    for r in range(31, 62):                                    # ClearContents Z31:AE61
        for c in range(26, 32):
            F.cells.pop((r, c), None)
    yrs = int(F.get(2, 8))                                     # H2: years in the fan
    obs_block, ntraj = int(nm('FanYrsBlock')), int(nm('FanNTraj'))
    stand_horiz = yrs == nm('FanYrsHoriz')
    if not stand_horiz and yrs % obs_block != 0:
        raise ValueError('Error: Length of horizon is not consistent with block structure.')
    blocks_traj = _vround(yrs / obs_block)
    ndraws = ntraj * yrs
    nblocks = _vround(ndraws / obs_block)
    hyr0, hyrN = int(nm('FanHistYr0')), int(nm('FanHistYrN'))
    hist_yrs = hyrN - hyr0 + 1
    max_draw = hyrN - hyr0 + 1 - (obs_block - 1)
    proj_yr = int(nm('ProjYr'))
    nsd = int(nm('FanNSD'))
    real_cut, real_yrs, real_cut_last = S1(nm('FanRealCutoff')), nm('FanRealYrs'), S1(nm('FanRealCutoffLast'))
    apply_center_adj, debug_mode, covid_adj = bool(nm('FanCenterAdjust')), bool(nm('FanDebugMode')), bool(nm('FanCOVIDadj'))
    min_perc = nm('FanMinPerc')
    init_d, use_sfa = S1(1), S1(0)
    pctiles = _single([0.05, 0.25, 0.5, 0.75, 0.95]).astype(np.float64)

    # Observations: the macro writes a code and a year into C7/D7 and reads G7; here the same lookup
    codes = {F.get(r, 1): r for r in range(68, 79) if F.get(r, 1) is not None}
    year_col = {F.get(65, c) + proj_yr: c for c in range(1, 32) if isnumber(F.get(65, c))}
    obs = lambda code, yr: F.get(codes[code], year_col[yr])
    hist_cols = [year_col[hyr0 + m] for m in range(hist_yrs)]
    proj_cols = [year_col[proj_yr + m] for m in range(yrs)]
    _ensure_ok(F, range(rng_begins, rng_ends), hist_cols, proj_cols, obs('SDDREV', proj_yr))
    sd = S1(obs('SDDREV', proj_yr))

    # ---- Task 2-3: historical sample (with averages) and baseline projections, all Single --------------
    keys = dict(d='GGXWDG_GDP', g='NGDP_RPCH', r='FI_R', pb='GGXONLB_GDP', e='ERERUS_RPCH', sfa='SFA',
                p='NGDP_DPCH', usp='111NGDP_DPCH', fxs='GGXWDGCF_PCT')
    hist = {k: _single([obs(code, hyr0 + m) for m in range(hist_yrs)]) for k, code in keys.items()}
    avg = {}
    for k, h in hist.items():
        s = S1(0)
        for v in h:                                            # x_sum = x_sum + x_hist(m): Single running sum
            s = S1(float(s) + float(v))
        avg[k] = S1(float(s) / hist_yrs)
    base = {k: _single([obs(code, proj_yr + m) for m in range(yrs)]) for k, code in keys.items()}
    base['usp'] = np.array([obs(keys['usp'], proj_yr + m) for m in range(yrs)], dtype=np.float64)   # As Double
    d0 = S1(obs('GGXWDG_GDP', proj_yr - 1))
    F.set(7, 3, 'GGXWDG_GDP')                                   # what the macro leaves in C7/D7
    F.set(7, 4, proj_yr - 1)

    # ---- Task 5: block draws ----------------------------------------------------------------------------
    mt = MersenneTwister(seed)
    id_rand = np.empty(nblocks, dtype=np.int64)
    for i in range(nblocks):
        mt.intbtw(1, 30)                                       # rand_col: drawn and never used
        id_rand[i] = int(C.get(9 + i + 1, 104)) if debug_mode else mt.intbtw(1, max_draw)
    id_draws = (id_rand[:, None] + np.arange(obs_block)[None, :]).ravel()      # 1-based historical year

    # ---- Task 6: drawn observations and de-meaned draws ------------------------------------------------
    drawn = {k: hist[k][id_draws - 1] for k in hist}
    ddrw = {k: _single(drawn[k].astype(np.float64) - float(avg[k])) for k in hist}

    # ---- Task 7: shocks to the starting debt level ----------------------------------------------------
    if debug_mode:
        shock_hfc = np.array([C.get(10 + i, 105) for i in range(ntraj)], dtype=np.float64)
        shock_ffc = np.array([C.get(10 + i, 106) for i in range(ntraj)], dtype=np.float64)
    else:
        shock_hfc = draw_zig_n(mt, ntraj, 0, float(S1(float(sd) * nsd)))
        shock_ffc = draw_zig_n(mt, ntraj, 0, float(S1(float(sd) * nsd)))

    # ---- Task 8: debt trajectories --------------------------------------------------------------------
    # draw used by trajectory i (0-based), year l: block (i + j*ntraj) for j = (l-1) // obs_block
    lyr = np.arange(yrs)
    jblk, kobs = lyr // obs_block, lyr % obs_block
    drw = kobs[None, :] + np.arange(ntraj)[:, None] * obs_block + jblk[None, :] * _vround(ndraws / blocks_traj)
    drivers = ('r', 'g', 'e', 'p', 'usp', 'pb', 'sfa')
    hfc, ffc, shk = {}, {}, {}
    for k in drivers[:-1]:
        b = base[k].astype(np.float64)[None, :]
        dd = ddrw[k][drw].astype(np.float64)
        ffc[k] = _single(b + dd)                                # baseline + de-meaned draw
        shk[k] = ddrw[k][drw]
        hfc[k] = drawn[k][drw]                                  # raw historical draw
        if covid_adj:                                           # first block: baseline + de-meaned draw
            hfc[k] = hfc[k].copy()
            hfc[k][:, jblk == 0] = ffc[k][:, jblk == 0]
    # stock-flow adjustment, switched off by use_sfa = 0 (except in the COVID first block, see QUIRKS)
    sfa_b, sfa_d = base['sfa'].astype(np.float64)[None, :], ddrw['sfa'][drw].astype(np.float64)
    hfc['sfa'] = _single(drawn['sfa'][drw].astype(np.float64) * float(use_sfa))
    if covid_adj:
        first = _single(sfa_b + sfa_d * float(use_sfa))
        hfc['sfa'][:, jblk == 0] = first[:, jblk == 0]
    ffc['sfa'] = _single((sfa_b + sfa_d) * float(use_sfa))
    fxs = np.concatenate([[hist['fxs'][-1]], base['fxs'][:-1]])  # FX share: not drawn, lagged baseline

    def paths(start, X):
        d = np.empty((ntraj, yrs + 1), dtype=np.float32)
        d[:, 0] = _single(float(d0) + start * float(init_d))
        for n in range(yrs):
            r, p, u, e, g, pb, sf = (X[k][:, n].astype(np.float64) for k in ('r', 'p', 'usp', 'e', 'g', 'pb', 'sfa'))
            x = float(fxs[n])
            d[:, n + 1] = _single(d[:, n] * ((1 + r) * (1 + p) * (1 + u) + x * e * (1 + p) + x * (p - u))
                                  / ((1 + g) * (1 + p) * (1 + u)) - pb + sf)
        return d

    d_hfc, d_ffc = paths(shock_hfc, hfc), paths(shock_ffc, ffc)

    # average de-meaned shock per trajectory (running Single sums) -> drivers for the debt-stabilising PB
    av = {}
    for k in ('r', 'g', 'p', 'usp', 'e'):
        a = np.zeros(ntraj, dtype=np.float32)
        for n in range(yrs):
            a = _single(a + _single(shk[k][:, n].astype(np.float64) / yrs))
        av[k] = a
    dspb_in = {k: _single(base[k][yrs - 1] + av[k].astype(np.float64)) for k in av}
    x_last = float(fxs[yrs - 1])

    def dspb(d_last):
        g, r, p, u = (dspb_in[k].astype(np.float64) for k in ('g', 'r', 'p', 'usp'))
        return _single(d_last.astype(np.float64) * (r - g + x_last * (p - u) / ((1 + p) * (1 + u))) / (1 + g))

    dspb_ffc_above = int(np.sum(base['pb'][yrs - 1] > dspb(d_ffc[:, yrs])))

    # ---- Task 9-11: sort each year, median, centering adjustment --------------------------------------
    hs = np.sort(d_hfc[:, 1:], axis=0)                          # row q-1 holds VBA's d_*_sort(q, j)
    fs = np.sort(d_ffc[:, 1:], axis=0)
    at = lambda s, q: s[q - 1]
    half = _vround(0.5 * ntraj)
    if ntraj % 2 == 0:
        med = lambda s: _single((at(s, half).astype(np.float64) + at(s, _vround(0.5 * ntraj + 1))) / 2)
    else:
        med = lambda s: at(s, half)
    if apply_center_adj:
        shift = base['d'].astype(np.float64) - med(fs).astype(np.float64)
        fs = _single(fs.astype(np.float64) + shift)             # d_sort - median + baseline, one expression
        d_ffc = d_ffc.copy()
        d_ffc[:, 1:] = _single(d_ffc[:, 1:].astype(np.float64) + shift)

    def fan(s):
        rows = []
        for i, pc in enumerate(pctiles):
            q = _vround(pc * ntraj)
            if i == 2 and ntraj % 2 == 0:
                rows.append(_single((at(s, q).astype(np.float64) + at(s, q + 1)) / 2))
            else:
                rows.append(at(s, q))
        return rows

    # ---- Task 12: historical fanchart, baseline percentile and the realism test ----------------------
    for i, row in enumerate(fan(hs)):
        for j in range(yrs):
            F.set(33 + i, 26 + j, float(row[j]))
    yrs_below, base_pct = 0, None
    for i in range(yrs):
        pos = find_pos_col(base['d'][i], [None] + list(hs[:, i]))
        base_pct = S1(pos / ntraj)
        if base_pct < real_cut:
            yrs_below += 1
    adj_realism = yrs_below >= real_yrs and base_pct < real_cut_last

    # ---- Task 13: realism adjustment ----------------------------------------------------------------
    if adj_realism:
        demed = _single(base['d'].astype(np.float64) - at(hs, ntraj // 2))
        col_h, nobs, start = nm('FanHistogramRange'), int(nm('FanHistogramObs')), int(nm('FanHistogramStartRow'))
        from .book import ci
        histogram = [None] + [S1(C.get(i + start, ci(col_h)) / 100) for i in range(1, nobs + 1)]
        pos_realism = find_pos_col(demed[yrs - 1], histogram)
        pct_realism = S1(pos_realism / nobs)
        if pct_realism < min_perc:
            pct_realism = S1(min_perc)
        anchor = at(fs, _vround(float(pct_realism) * ntraj)).astype(np.float64)
        shift = base['d'].astype(np.float64) - anchor
        d_afc = _single(d_ffc[:, 1:].astype(np.float64) + shift)
        afs = _single(fs.astype(np.float64) + shift)
        dspb_afc_above = int(np.sum(base['pb'][yrs - 1] > dspb(d_afc[:, yrs - 1])))

    # ---- Task 14: output ----------------------------------------------------------------------------
    for i, row in enumerate(fan(fs)):
        for j in range(yrs):
            F.set(45 + i, 26 + j, float(row[j]))
    if adj_realism:
        for i, row in enumerate(fan(afs)):
            for j in range(yrs):
                F.set(57 + i, 26 + j, float(row[j]))
    above = dspb_afc_above if adj_realism else dspb_ffc_above
    F.set(12, 4, 1 - above / ntraj)                              # D12: "=1-<above>/<ntraj>"
    F.set(18, 4, adj_realism)
    if adj_realism:
        F.set(18, 5, float(demed[yrs - 1]))
        F.set(18, 6, pos_realism)
        F.set(18, 7, float(pct_realism))
    else:
        for c in (5, 6, 7):
            F.set(18, c, 'n.a.')
        warn = None if stand_horiz else 'Warning-Not valid, non-standard fan >>'
        for r in (14, 15):                                      # D14:D15 (I14/I15 hold the index and signal)
            if warn is None:
                F.cells.pop((r, 4), None)
            else:
                F.set(r, 4, warn)
    return {'seed': seed, 'dspb_above': above, 'adj_realism': adj_realism, 'ntraj': ntraj}
