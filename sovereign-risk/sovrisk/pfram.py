"""PPP fiscal risk: a Python port of the IMF and World Bank PPP Fiscal Risk Assessment Model (PFRAM 2.0).

    python -m sovrisk.pfram --list
    python -m sovrisk.pfram --project P1 --out outputs

PFRAM 2.0 is the IMF and World Bank's free Excel tool (pfram2english.xlsm). For one PPP project it builds the
private partner's statements, then the government's accrual (GFS) statements, balance sheet, cash flow,
contingent liabilities and headline fiscal indicators, with macro shocks and early termination.

The port follows the workbook's Template sheet formula by formula, including its quirks, so results match
the workbook (tests/test_pfram.py checks every row against LibreOffice recalculations of the real file).
Quirks kept on purpose, and listed in QUIRKS below, are reported rather than fixed.

Inputs are in data/pfram_projects.yaml and data/pfram_macro.csv. Projects there are ILLUSTRATIVE and
hypothetical. Not investment advice and not a credit rating. UNTESTED against a real project.
"""
import argparse
import csv
import math
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import yaml
from scipy.optimize import brentq

from .config import ROOT, read_csv

NCOL = 50                    # workbook years C..AZ
C0 = 3                       # column number of C
COLS = range(C0, C0 + NCOL)  # 3..52
MAX_ASSETS = MAX_SERVICES = 10

FUNDING = {'government': 'Tax payers--public funded', 'user': 'Users of the services--user funded',
           'combined': 'Combined'}

QUIRKS = [
    'Debt guarantee payments (Template row 196) refer to names the workbook never defines, so they are always 0. '
    'Guaranteed debt still shows as a contingent liability.',
    'Revenues in the first year include "other government payment"; later years leave it out (row 112).',
    'The availability payment is indexed by one year of GDP deflator growth, not cumulatively (row 114).',
    'The debt-guarantee flow (row 228) lags the debt-guarantee stock (row 213) by one year.',
    'Macro series line up with project years by column, so a project must start in the portfolio start year.',
    'Rows 742, 743 and 747 add billions to millions; use the portfolio indicators for headline ratios.',
    'With combined funding there may be no rate that meets the goal-seek condition (Excel\'s Goal Seek also fails); '
    'the port then uses the project IRR.',
]


# ----------------------------------------------------------------------------------------------- inputs
@dataclass
class Asset:
    name: str = ''
    construction_period: int = 1     # years
    construction_start: int = 1      # project year construction begins
    useful_life: int = 1
    cost: float = 0.0                # million
    land_cost: float = 0.0           # paid by the private partner, million


@dataclass
class Service:
    name: str = ''
    unit: str = ''
    start: int = 0                   # project year the service starts ("year 3 of contract" = 3)
    # user-funded side (tariffs)
    tariff: float | None = None      # initial tariff
    tariff_currency: str = 'DOM'     # DOM or FX (FX is converted at the NER)
    tariff_inflation_indexed: bool = False
    tariff_ner_indexed: bool = False
    tariff_adjust: list = field(default_factory=list)   # extra % a year, by project year
    user_demand: float | None = None
    user_demand_gdp_linked: bool = False
    user_demand_adjust: list = field(default_factory=list)
    # government-funded side (unitary payments)
    price: float | None = None
    price_currency: str = 'DOM'
    price_inflation_indexed: bool = False
    price_ner_indexed: bool = False
    price_adjust: list = field(default_factory=list)
    gov_demand: float | None = None
    gov_demand_gdp_linked: bool = False
    gov_demand_adjust: list = field(default_factory=list)


@dataclass
class Project:
    id: str
    name: str
    funding: str                         # government, user or combined
    start_year: int
    contract_length: int
    type: str = ''
    currency: str = 'DOM'
    gov_shareholding: float = 0.0        # K32
    debt_share: float = 0.0              # K33, share of investment financed by debt
    interest_rate: float = 0.0           # K34
    fx_debt_share: float = 0.0           # K35 (recorded, not used by the workbook's formulas)
    asset_controller: str = 'Private Partner'   # H37: Private Partner, Central Government, ...
    gov_controls_services: str = 'Yes'   # H39
    gov_residual_interest: str = 'Yes'   # H41
    tax_rate: float = 0.0                # T33
    effective_rate: float | None = None  # T32 (WACC); None = solve as the workbook's EIR_Seek macro does
    assets: list = field(default_factory=list)
    services: list = field(default_factory=list)
    # annual series by project year (million), shorter lists are padded with zeros
    maintenance: list = field(default_factory=list)
    operation: list = field(default_factory=list)
    user_fees_to_gov: list = field(default_factory=list)
    royalties: list = field(default_factory=list)
    other_payments_to_gov: list = field(default_factory=list)
    other_costs: list = field(default_factory=list)
    availability_payment: list | None = None   # row 78; None = computed from services (Calc_Row1)
    availability_indexed: bool = False         # B78
    other_index: list | None = None            # row 79 with B79 = Yes
    other_gov_payment: list = field(default_factory=list)   # row 82
    tariffs: list | None = None                # row 84; None = computed from services (Calc_Row2)
    debt_guarantee_share: float = 0.0          # B624
    guaranteed_price: list = field(default_factory=list)    # row 633, by project year
    guaranteed_demand: list = field(default_factory=list)   # row 637
    termination_year: int | None = None        # K651
    termination_method: int = 1                # A650: 1 = book value, 2 = share of lost profits
    termination_share: float = 1.0             # K655
    risks: dict = field(default_factory=dict)  # TRisk: category -> [likelihood, impact]
    illustrative: bool = True
    note: str = ''

    @classmethod
    def from_dict(cls, d):
        d = dict(d)
        d['assets'] = [Asset(**a) for a in d.get('assets', [])]
        d['services'] = [Service(**s) for s in d.get('services', [])]
        return cls(**d)


@dataclass
class Macro:
    """MacroParameters rows 4-12 (billion, national currency). None = carry the previous growth rate forward."""
    start_year: int
    nominal_gdp: list
    real_gdp: list
    deflator: list
    ner: list
    primary_balance: list = field(default_factory=list)
    overall_balance: list = field(default_factory=list)
    cash_balance: list = field(default_factory=list)
    gross_debt: list = field(default_factory=list)
    revenue: list = field(default_factory=list)
    currency: str = 'DOM'


@dataclass
class Shock:
    """SensitivityAnalysis shocks: added to growth rates (0.02 = 2 points) from start to end year inclusive."""
    gdp: float = 0.0
    gdp_years: tuple = (None, None)
    er: float = 0.0
    er_years: tuple = (None, None)
    inflation: float = 0.0
    inflation_years: tuple = (None, None)


def _pad(xs, n=NCOL, fill=0.0):
    xs = [fill if v is None else v for v in (xs or [])][:n]
    return xs + [fill] * (n - len(xs))


def _blank(xs, n=NCOL):
    xs = list(xs or [])[:n]
    return xs + [None] * (n - len(xs))


# ---------------------------------------------------------------------------------------- macro tables
def macro_tables(m, shock=None):
    """MacroParameters growth rows (14-17) and SensitivityAnalysis rows 26-43, keyed by calendar year."""
    years = [m.start_year + i for i in range(NCOL)]
    raw = {k: _blank(getattr(m, k)) for k in ('nominal_gdp', 'real_gdp', 'deflator', 'ner')}

    def growth(xs):  # MacroParameters rows 14-17: =IF(D4="",C14,D4/C4-1); the C column is blank (0)
        g = [0.0]
        for i in range(1, NCOL):
            g.append(g[-1] if xs[i] is None else xs[i] / xs[i - 1] - 1)
        return g

    def sa_growth(xs):  # SensitivityAnalysis rows 27, 29, 31, 33: =IF(C26<>0,C26/B26-1,B27); B blank -> 0
        g = [0.0]
        for i in range(1, NCOL):
            v, p = xs[i] or 0, xs[i - 1] or 0
            g.append(v / p - 1 if v != 0 else g[-1])
        return g

    s = shock or Shock()

    def shock_row(size, span, from_col=0):
        a, b = span
        return [0.0 if i < from_col or a is None or not (a <= y <= b) else size for i, y in enumerate(years)]

    g_shock = shock_row(s.gdp, s.gdp_years)          # row 3 (as a fraction)
    e_shock = shock_row(s.er, s.er_years, 3)         # row 4: B..D are typed zeros in the workbook
    i_shock = shock_row(s.inflation, s.inflation_years, 3)
    rg, dg, ng, nomg = (sa_growth(raw[k]) for k in ('real_gdp', 'deflator', 'ner', 'nominal_gdp'))
    # rows 39, 41, 43: shocked growth; 38, 40, 42 levels; 37, 36 nominal GDP
    rgs, dgs, ngs = [0.0], [0.0], [0.0]
    for i in range(1, NCOL):
        rgs.append((raw['real_gdp'][i] / raw['real_gdp'][i - 1] - 1 + g_shock[i]) if (raw['real_gdp'][i] or 0) != 0 else rg[i])
        dgs.append((raw['deflator'][i] / raw['deflator'][i - 1] - 1 + i_shock[i]) if (raw['deflator'][i] or 0) != 0 else dg[i])
        ngs.append((raw['ner'][i] / raw['ner'][i - 1] - 1 + e_shock[i]) if (raw['ner'][i] or 0) != 0 else ngs[-1])
    ner_lvl = [raw['ner'][0] or 0]
    gdp_s = [raw['nominal_gdp'][0] or 0]
    for i in range(1, NCOL):
        ner_lvl.append(ner_lvl[-1] * (1 + ngs[i]))
        gdp_s.append(gdp_s[-1] * (1 + (nomg[i] if g_shock[i] == 0 else rgs[i] + dgs[i])))
    rgs[0] = dgs[0] = ngs[0] = 0.0   # B39, B41, B43 are blank
    return {
        'years': years,
        'deflator_growth': growth(raw['deflator']),          # MacroParameters row 16 (unshocked)
        'real_gdp_growth_shocked': dict(zip(years, rgs)),    # SA row 39
        'deflator_growth_shocked': dict(zip(years, dgs)),    # SA row 41
        'ner_shocked': dict(zip(years, ner_lvl)),            # SA row 42
        'ner_growth_shocked': dict(zip(years, ngs)),         # SA row 43
        'nominal_gdp_shocked': dict(zip(years, gdp_s)),      # SA row 36
        'gdp': [(v or 0) for v in raw['nominal_gdp']],       # MacroParameters row 4 (inputs only)
        'raw': {k: _blank(getattr(m, k)) for k in ('overall_balance', 'cash_balance', 'gross_debt')},
    }


# ---------------------------------------------------------------------------------------- helpers
def _irr(flows):
    """Excel IRR on the flows (trailing zeros kept, as Excel does)."""
    f = np.asarray(flows, dtype=float)
    f[np.abs(f) < 1e-9] = 0.0      # rounding dust such as -5.7e-14 in a late year would swamp NPV near -100%
    if not (np.any(f > 0) and np.any(f < 0)):
        return None
    npv = lambda r: float(np.sum(f / (1 + r) ** np.arange(len(f))))
    for lo, hi in ((-0.99, 1.0), (-0.9999, 10.0)):
        try:
            return brentq(npv, lo, hi, xtol=1e-14, maxiter=500)
        except ValueError:
            continue
    return None


def _pmt_pos(r, n, pv):
    """-PMT(r, n, pv): the level payment that repays pv over n periods."""
    if r == 0:
        return pv / n
    return pv * r / (1 - (1 + r) ** -n)


def _z(x):
    """Excel's = 0 test: Excel snaps tiny subtraction residues to zero."""
    return abs(x) < 1e-9


def _roundup(x):
    return math.ceil(x - 1e-12) if x > 0 else math.floor(x + 1e-12)


# ---------------------------------------------------------------------------------------- the model
def _services_block(p, mt, L):
    """Rows 303-618: tariff, demand and payment projections. Arrays are indexed by column D..AZ (j = 0..48),
    with column D holding project year 1. Returns (users' revenue row 459, government payments row 618)."""
    rows459 = [0.0] * NCOL
    rows618 = [0.0] * NCOL
    look = lambda tbl, yr: tbl.get(yr, 0.0)
    for k, s in enumerate(p.services[:MAX_SERVICES]):
        seed_year = p.start_year + (s.start or 0)
        t_adj, d_adj = _pad(s.tariff_adjust), _pad(s.user_demand_adjust)
        p_adj, g_adj = _pad(s.price_adjust), _pad(s.gov_demand_adjust)
        tariff = demand = price = gdem = 0.0
        for j in range(NCOL - 1):           # columns D..AZ
            yr = p.start_year + j
            years_idx = j + 2                # Template row 1 at that column
            alive = years_idx <= L + 1
            seed = yr == seed_year
            # tariff, rows 306-311
            if seed and s.tariff is not None:
                base = s.tariff * look(mt['ner_shocked'], yr) if s.tariff_currency.upper() == 'FX' else s.tariff
                tariff = base if alive else 0.0
            else:
                infl = look(mt['deflator_growth_shocked'], yr) if s.tariff_inflation_indexed else 0.0
                nerg = look(mt['ner_growth_shocked'], yr) if s.tariff_ner_indexed else 0.0
                tariff = tariff * (1 + infl) * (1 + nerg) * (1 + t_adj[j]) if alive else 0.0
            # user demand, rows 388-391
            if seed and s.user_demand is not None:
                demand = s.user_demand if alive else 0.0
            else:
                gg = look(mt['real_gdp_growth_shocked'], yr) if s.user_demand_gdp_linked else 0.0
                demand = demand * (1 + gg) * (1 + d_adj[j]) if alive else 0.0
            # government unit price, rows 465-470
            if seed and s.price is not None:
                base = s.price * look(mt['ner_shocked'], yr) if s.price_currency.upper() == 'FX' else s.price
                price = base if alive else 0.0
            else:
                infl = look(mt['deflator_growth_shocked'], yr) if s.price_inflation_indexed else 0.0
                nerg = look(mt['ner_growth_shocked'], yr) if s.price_ner_indexed else 0.0
                price = price * (1 + infl) * (1 + nerg) * (1 + p_adj[j]) if alive else 0.0
            # government-paid demand, rows 547-550 (service 1 stops after the contract; others only at D)
            if seed and s.gov_demand is not None:
                gdem = s.gov_demand if (alive or (k > 0 and j > 0)) else 0.0
            else:
                gg = look(mt['real_gdp_growth_shocked'], yr) if s.gov_demand_gdp_linked else 0.0
                truncate = (k == 0 or j == 0) and not alive
                gdem = 0.0 if truncate else gdem * (1 + gg) * (1 + g_adj[j])
            rows459[j] += tariff * demand
            rows618[j] += price * gdem
    return rows459, rows618


def run_project(p, macro, shock=None, effective_rate=None):
    """Run one project. Returns a dict of rows by Template row number (lists over columns C..AZ) plus a summary."""
    mt = macro_tables(macro, shock)
    if p.start_year != macro.start_year:
        raise ValueError(f'{p.id}: PFRAM lines macro data up by column, so the project must start in '
                         f'{macro.start_year} (the portfolio start year), not {p.start_year}')
    rate = effective_rate if effective_rate is not None else p.effective_rate
    if rate is None:
        rate = solve_effective_rate(p, macro, shock)
    return _run(p, mt, rate)


def _run(p, mt, wacc):
    L = p.contract_length
    Y = list(range(1, NCOL + 1))                     # row 1 "Years" at columns C..AZ
    cal = [p.start_year + i for i in range(NCOL)]     # row 69
    n = NCOL
    z = lambda: [0.0] * n
    A = (p.assets + [Asset(construction_period=None, construction_start=None, useful_life=None, cost=0.0, land_cost=0.0)
                     for _ in range(MAX_ASSETS - len(p.assets))])[:MAX_ASSETS]
    used = [k < len(p.assets) for k in range(MAX_ASSETS)]
    cp = [a.construction_period or 0 for a in A]
    cs = [a.construction_start or 0 for a in A]
    ul = [a.useful_life or 0 for a in A]
    y1op = [cp[k] + cs[k] for k in range(MAX_ASSETS)]           # row 52
    I22 = max([c for k, c in enumerate(cp) if used[k]] or [0])  # MAX(construction_period)
    s1 = p.services[0].start if p.services else 0               # start_service1

    # rows 86-106: land and construction outlays
    land = [[(A[k].land_cost or 0) if Y[i] == cs[k] else 0.0 for i in range(n)] for k in range(MAX_ASSETS)]
    cost = []
    for k in range(MAX_ASSETS):
        u, c = (ul[k] or 1), (cp[k] or 1)
        cost.append([((A[k].cost or 0) / c if (Y[i] - cs[k]) % u < c else 0.0) * (Y[i] <= L) for i in range(n)])
    r106 = [sum(land[k][i] + cost[k][i] for k in range(MAX_ASSETS)) for i in range(n)]

    # residual values (row 51)
    resid = []
    for k in range(MAX_ASSETS):
        try:
            if not ul[0]:
                v = 0.0
            elif ul[k] == L + y1op[k] - 1:
                v = 0.0
            elif ul[k] > L + y1op[k] - 1:
                v = (A[k].cost / ul[k]) * (ul[k] - L + y1op[k] - 1)
            else:
                v = (A[k].cost / ul[k]) * (_roundup((L + y1op[k] - 1) / ul[k]) * ul[k] - L + y1op[k] - 1)
        except ZeroDivisionError:
            v = 0.0
        resid.append(v)

    # services and inputs
    r459, r618 = _services_block(p, mt, L)
    nxt = lambda row, i: row[i] if i < n - 1 else 0.0           # C78 = D618: lower block shifted one column
    r78 = _pad(p.availability_payment) if p.availability_payment is not None else [nxt(r618, i) for i in range(n)]
    r84 = _pad(p.tariffs) if p.tariffs is not None else [nxt(r459, i) for i in range(n)]
    r79 = _pad(p.other_index)
    maint, oper = _pad(p.maintenance), _pad(p.operation)
    fees, roy, othp, othc = (_pad(x) for x in (p.user_fees_to_gov, p.royalties, p.other_payments_to_gov, p.other_costs))
    r82 = _pad(p.other_gov_payment)

    # guarantees (rows 621-644), lower block: index j = column D..AZ
    gp, gd = _pad(p.guaranteed_price), _pad(p.guaranteed_demand)
    r634 = [gp[j] if j + 2 <= L + 1 else 0.0 for j in range(n - 1)]
    r638 = [gd[j] if j + 2 <= L + 1 else 0.0 for j in range(n - 1)]
    r640 = [r634[j] * r638[j] for j in range(n - 1)]
    has_mrg = 1 if sum(r640) != 0 else 0
    fund = p.funding
    r630 = [(r618[j] if fund == 'government' else r459[j] if fund == 'user' else r459[j] + r618[j]) * has_mrg
            for j in range(n - 1)]
    r641 = [max(0.0, r640[j] - r630[j]) for j in range(n - 1)]
    r643 = [0.0 if r640[j] == 0 else sum(r640[j:]) for j in range(n - 1)]
    r644 = [0.0 if r641[j] == 0 else sum(r641[j:]) for j in range(n - 1)]
    r80 = [nxt(r641, i) for i in range(n)]

    # (3) concessionaire statements
    defl = mt['deflator_growth']
    r113 = r84[:]
    r114 = [r78[i] * ((1 + defl[i]) if p.availability_indexed else 1) * ((1 + r79[i]) if p.other_index is not None else 1)
            for i in range(n)]
    r115 = r82[:]
    r116 = [r80[i] if Y[i] <= L else 0.0 for i in range(n)]
    r112 = [r113[i] + r114[i] + r116[i] + (r115[i] if i == 0 else 0.0) for i in range(n)]
    r118 = [(oper[i] + maint[i]) if Y[i] <= L else 0.0 for i in range(n)]
    r119 = [(roy[i] + fees[i] + othp[i]) if Y[i] <= L else 0.0 for i in range(n)]
    r120 = [othc[i] if Y[i] <= L else 0.0 for i in range(n)]
    r117 = [r118[i] + r119[i] + r120[i] for i in range(n)]
    r121 = [r112[i] - r117[i] for i in range(n)]
    ds = p.debt_share
    rows = {k: z() for k in (122, 123, 124, 125, 126, 127, 128, 130, 131, 132, 134, 135, 136, 137, 138, 141, 142, 143,
                             144, 145, 146, 148, 151, 152, 153, 154, 155, 156, 157, 158, 159, 160, 161, 163, 164, 165,
                             166, 168, 171)}
    R = rows
    cum156 = 0.0
    for i in range(n):
        prev = lambda r: R[r][i - 1] if i > 0 else 0.0
        R[134][i] = prev(138)
        R[141][i] = prev(146)
        R[135][i] = r106[i]
        R[142][i] = r106[i] * ds
        R[143][i] = R[141][i] * p.interest_rate
        R[137][i] = (R[134][i] / (L - Y[i] + 1) if L - Y[i] + 1 > 0 else 0.0) * (Y[i] > I22)
        R[148][i] = (_pmt_pos(p.interest_rate, L - Y[i] + 1, R[141][i]) if L - Y[i] + 1 > 0 else 0.0) * (Y[i] > I22)
        R[122][i] = 0.0 if Y[i] <= s1 else R[143][i]
        R[123][i] = R[137][i]
        R[124][i] = r121[i] - R[122][i] - R[123][i]
        R[125][i] = (R[124][i] + prev(125)) if Y[i] <= L else 0.0
        R[126][i] = min(R[124][i], R[125][i]) * p.tax_rate if (R[124][i] > 0 and R[125][i] > 0) else 0.0
        R[127][i] = R[124][i] - R[126][i]
        R[128][i] = 0.0 if _z(R[127][i]) else R[127][i] + prev(128)    # contract_end >= Years is always true
        R[151][i], R[152][i], R[153][i], R[154][i] = r112[i], r106[i], r117[i], R[126][i]
        R[155][i] = R[151][i] - R[152][i] - R[153][i] - R[154][i]
        need = r106[i] * (1 - ds) + max(0.0, R[148][i] - R[155][i] - R[152][i]) * (Y[i] > I22)
        R[156][i] = need - prev(166) if need > prev(166) else 0.0
        R[157][i] = r106[i] * ds
        R[159][i] = R[155][i] + R[156][i] + R[157][i]
        avail = R[159][i] + prev(166)
        R[144][i] = avail if R[143][i] > avail else R[143][i]
        R[145][i] = 0.0 if avail < R[143][i] else (avail - R[143][i] if avail < R[148][i] else R[148][i] - R[143][i])
        R[146][i] = R[141][i] + R[142][i] + R[143][i] - R[144][i] - R[145][i]
        R[136][i] = R[143][i] - R[144][i]
        R[158][i] = R[136][i]
        R[138][i] = R[134][i] + R[135][i] + R[136][i] - R[137][i]
        R[160][i] = R[145][i] + R[144][i]
        R[161][i] = R[159][i] - R[160][i]
        cum156 += R[156][i]
        R[163][i] = (L + 1 == Y[i]) * max(0.0, min(R[161][i] + prev(166), cum156))
        R[164][i] = ((min(R[161][i] + prev(166) + prev(163), R[127][i] + prev(132))
                      if R[161][i] + prev(166) + prev(163) > 0 else 0.0) if R[127][i] + prev(132) > 0 else 0.0)
        R[130][i] = R[164][i]
        R[131][i] = R[127][i] - R[130][i]
        R[132][i] = R[131][i] + prev(132)
        R[165][i] = R[161][i] - R[163][i] - R[164][i]
        R[166][i] = R[165][i] + prev(166)
        R[168][i] = -R[156][i] + R[161][i]
        R[171][i] = 0.0 if _z(R[168][i]) else R[168][i]
    for k, v in ((112, r112), (113, r113), (114, r114), (115, r115), (116, r116), (117, r117), (118, r118),
                 (119, r119), (120, r120), (121, r121), (106, r106), (78, r78), (84, r84), (80, r80)):
        R[k] = v

    # share of costs funded by government (I17)
    s114, s113 = sum(r114), sum(r113)
    scgf = s114 / (s114 + s113) if s114 + s113 else 0.0
    capital_transfer = p.asset_controller == 'Private Partner'      # O37
    on_bs = 0 if (p.gov_controls_services == 'No' and p.gov_residual_interest == 'No') else 1

    # (4) government statements
    G = {k: z() for k in range(176, 238)}
    lower_shift = lambda row, i: row[i] if i < n - 1 else 0.0       # D641 at column C, etc.
    r627 = [ (R[146][j] * p.debt_guarantee_share) + ((A[0].cost or 0) * p.gov_shareholding) for j in range(n - 1)]
    sum224 = 0.0
    cum220_221 = cum222 = 0.0
    for i in range(n):
        live = Y[i] <= L
        prev = lambda r: G[r][i - 1] if i > 0 else 0.0
        G[177][i] = R[126][i] if live else 0.0
        G[178][i] = (sum(resid) if (capital_transfer and Y[i] == L) else 0.0) if live else 0.0
        G[179][i] = sum(((1 - scgf) * (sum(land[k]) + sum(cost[k])) / (L - y1op[k] + 1)
                         if (Y[i] >= y1op[k] and Y[i] <= L) else 0.0) for k in range(MAX_ASSETS)) if live else 0.0
        G[180][i] = r119[i] if live else 0.0
        G[176][i] = (G[177][i] + G[178][i] + G[179][i] + G[180][i]) if live else 0.0
        G[182][i] = r118[i] * scgf if live else 0.0
        G[183][i] = (prev(209) * wacc * (0 if r114[i] == 0 else 1)) if live else 0.0
        for k in range(MAX_ASSETS):
            u = ul[k] or 1
            G[184 + k][i] = ((A[k].cost or 0) / u if (Y[i] >= y1op[k] and Y[i] <= y1op[k] - 1 + _roundup(L / u) * u)
                             else 0.0) * (0 if capital_transfer else 1)
        G[194][i] = sum(G[184 + k][i] for k in range(MAX_ASSETS))
        G[195][i] = lower_shift(r641, i) if live else 0.0
        G[196][i] = 0.0     # see QUIRKS
        G[197][i] = r115[i] if live else 0.0
        G[181][i] = G[182][i] + G[183][i] + G[194][i] + G[195][i] + G[197][i]
        G[198][i] = G[176][i] - G[181][i]
        G[199][i] = (r106[i] - G[194][i]) * on_bs
        G[200][i] = G[198][i] - G[199][i]
        G[215][i] = G[199][i]
        G[203][i] = prev(203) + G[215][i]
        # cash flow
        G[231][i] = (G[177][i] + G[180][i]) if live else 0.0
        G[230][i] = G[231][i] if live else 0.0
        G[233][i] = r114[i] if live else 0.0
        G[234][i] = lower_shift(r641, i) if live else 0.0
        G[235][i] = G[196][i] if live else 0.0
        G[236][i] = G[197][i] if live else 0.0
        G[232][i] = (G[233][i] + G[234][i] + G[235][i] + G[236][i]) if live else 0.0
        G[237][i] = (G[230][i] - G[232][i]) if live else 0.0
        G[217][i] = G[237][i] if live else 0.0
        G[216][i] = G[217][i] if live else 0.0
        G[207][i] = (prev(207) + G[217][i]) if live else 0.0
        G[206][i] = G[207][i] if live else 0.0
        # liabilities
        G[220][i] = r106[i] * scgf if live else 0.0
        G[221][i] = (G[183][i] if r114[i] == 0 else 0.0) if live else 0.0
        red = r114[i] - (G[182][i] + G[183][i])
        G[222][i] = ((red if (r114[i] > 0 and red > 0) else 0.0) * (0 if cum222 >= cum220_221 else 1)) if live else 0.0
        cum220_221 += G[220][i] + G[221][i]
        cum222 += G[222][i]
        nxt209 = prev(209) + G[220][i] + G[221][i] - G[222][i]
        G[209][i] = (nxt209 if nxt209 >= 0 else 0.0) if live else 0.0
        G[224][i] = r106[i] * (1 - scgf) if live else 0.0
        G[218][i] = 0.0  # filled below once 225 is known
    tot224 = sum(G[224])
    c224 = c225 = 0.0
    for i in range(n):
        live = Y[i] <= L
        G[225][i] = ((tot224 / (L - y1op[0] + 1)) if (Y[i] >= y1op[0]) else 0.0) if live else 0.0
        c224 += G[224][i]
        c225 += G[225][i]
        G[210][i] = (c224 - c225) if live else 0.0
        G[208][i] = (G[209][i] + G[210][i]) if live else 0.0
        G[205][i] = (G[206][i] - G[208][i]) if live else 0.0
        G[202][i] = G[203][i] + G[205][i]
        G[218][i] = (G[220][i] + G[221][i] - G[222][i] + G[224][i] - G[225][i]) if live else 0.0
        G[212][i] = (lower_shift(r643, i) if (Y[i] >= y1op[0] or Y[i] >= y1op[1]) else 0.0) if live else 0.0
        G[213][i] = (lower_shift(r627, i) if Y[i] >= min(y1op) else 0.0) if live else 0.0
        G[211][i] = (G[212][i] + G[213][i]) if live else 0.0
        G[227][i] = lower_shift(r641, i) if live else 0.0
        l627 = lambda col_i: r627[col_i - 1] if 1 <= col_i <= n - 1 else 0.0   # row 627 at column C+col_i
        G[228][i] = (l627(i) - l627(i - 1)) if live else 0.0
        G[226][i] = (G[227][i] + G[228][i]) if live else 0.0
    R.update(G)
    R[641], R[643], R[644], R[627], R[459], R[618], R[640], R[630] = r641, r643, r644, r627, r459, r618, r640, r630

    # (9) contract termination and headline indicators (rows 696-760)
    gdp = [v * 1000 for v in mt['gdp']]
    T = _termination(p, R, cal, wacc, gdp, mt)
    R[110] = cal
    R[169] = [_irr(R[168])] + [None] * (n - 1)
    R.update(T)
    summary = {
        'effective_rate': wacc, 'equity_irr': _irr(R[168]), 'project_irr': _irr(R[155]),
        'share_government_funded': scgf, 'capital_transfer': capital_transfer, 'on_balance_sheet': bool(on_bs),
        'government_payments': sum(r114), 'tariff_collection': sum(r113),
        'debt_guarantee_max': p.debt_guarantee_share * max(R[146]), 'revenue_guarantee': sum(r80),
        'total_construction_cost': sum(r106), 'construction_period': I22,
        'npv_check': {'sum_nlb': sum(G[200]), 'minus_sum_availability': -sum(G[233])},
        'residual_values': resid,
    }
    return {'project': p, 'rows': R, 'years': cal, 'summary': summary, 'macro': mt}


def _termination(p, R, cal, wacc, gdp, mt):
    n = NCOL
    T = {}
    K651 = p.termination_year or 0     # blank in the workbook: termination rows then read as zero
    try:
        col = cal.index(K651)                                    # MATCH(K651, C696:AY696, 0) - 1
    except ValueError:
        col = None
    A651 = R[203][col] if col is not None else 0.0              # book value of nonfinancial assets
    horizon = cal[0] + p.contract_length - K651                  # A656
    if col is not None and horizon > 0:
        e = R[121][col:col + horizon]
        A652 = sum(v / (1 + wacc) ** (t + 1) for t, v in enumerate(e)) * p.termination_share
    else:
        A652 = 0.0
    pay = A651 if p.termination_method == 1 else A652
    gd = lambda i: gdp[i] if gdp[i] else math.nan
    T[717], T[718], T[719], T[720], T[721], T[722] = R[203], R[121], R[208], R[211], R[198], R[200]
    T[723] = [R[230][i] - R[232][i] for i in range(n)]
    T[725] = [R[208][i] if cal[i] < K651 else 0.0 for i in range(n)]
    T[726] = [pay if cal[i] == K651 else 0.0 for i in range(n)]
    T[727] = [T[726][i] - R[208][i] if cal[i] == K651 else 0.0 for i in range(n)]
    T[728] = R[211]
    T[729] = [R[198][i] if cal[i] < K651 else R[194][i] - T[727][i] for i in range(n)]
    T[730] = [R[200][i] if cal[i] < K651 else -T[727][i] for i in range(n)]
    T[731] = [T[723][i] if cal[i] < K651 else (T[723][i] - T[726][i] if cal[i] == K651 else 0.0) for i in range(n)]
    T[733] = gdp
    T[736] = [R[198][i] / gd(i) * 100 for i in range(n)]
    T[737] = [R[200][i] / gd(i) * 100 for i in range(n)]
    T[738] = [R[237][i] / gd(i) * 100 if cal[i] <= K651 else 0.0 for i in range(n)]
    T[739] = [R[203][i] / gd(i) * 100 for i in range(n)]
    T[740] = [R[208][i] / gd(i) * 100 for i in range(n)]
    T[748] = [R[211][i] / gd(i) * 100 for i in range(n)]
    T[751] = [T[729][i] / gd(i) for i in range(n)]
    T[752] = [T[730][i] / gd(i) for i in range(n)]
    T[753] = [T[731][i] / gd(i) * 100 for i in range(n)]
    T[754] = [T[717][i] / gd(i) for i in range(n)]
    T[755] = T[725]
    T[756] = [T[728][i] / gd(i) for i in range(n)]
    ob, cb, dbt = (mt['raw'][k] for k in ('overall_balance', 'cash_balance', 'gross_debt'))
    T[742] = [(ob[i] or 0) / gd(i) * 100 for i in range(n)]               # billion over million (see QUIRKS)
    T[743] = [T[742][i] + R[200][i] for i in range(n)]
    T[744] = [R[237][i] / gd(i) * 100 for i in range(n)]
    T[745] = [((cb[i] or 0) + R[237][i]) * 100 / gd(i) for i in range(n)]
    T[746] = R[208]
    T[747] = [((dbt[i] or 0) + R[208][i]) / gd(i) * 100 for i in range(n)]
    T[758] = [T[746][i] + T[755][i] for i in range(n)]
    T[759] = [T[742][i] + T[752][i] for i in range(n)]
    T[760] = [T[744][i] + T[753][i] for i in range(n)]
    T['termination'] = {'year': K651, 'book_value': A651, 'lost_profit_npv': A652, 'payment': pay,
                        'method': 'book value' if p.termination_method == 1 else 'share of lost profits'}
    return T


def solve_effective_rate(p, macro, shock=None):
    """The workbook's EIR_Seek macro. With no availability payments, WACC = IRR of cash flow before financing.
    Otherwise WACC is the rate at which total net lending/borrowing equals minus total availability payments."""
    mt = macro_tables(macro, shock)
    base = _run(p, mt, 0.0)
    if sum(base['rows'][233]) == 0:
        r = _irr(base['rows'][155])
        return r if r is not None else 0.0
    f = lambda w: (lambda o: sum(o['rows'][200]) + sum(o['rows'][233]))(_run(p, mt, w))
    lo = -0.5
    for hi in (1.0, 2.0, 5.0):
        if f(lo) * f(hi) <= 0:
            return brentq(f, lo, hi, xtol=1e-15, rtol=1e-15, maxiter=500)
    # No rate balances the two (typical of combined funding, where Excel's Goal Seek also fails):
    # fall back to the project IRR, which is what the workbook uses when there are no availability payments.
    r = _irr(base['rows'][155])
    return r if r is not None else 0.0


# ---------------------------------------------------------------------------------------- risk matrix
RISK_CATEGORIES = ['Governance', 'Construction', 'Demand', 'Operational and performance', 'Financial',
                   'Force majeure', 'Material adverse government action', 'Change in law',
                   'Rebalancing of financial equilibrium', 'Renegotiation', 'Contract termination']


def risk_rating(likelihood, impact):
    """TRisk sheet: risk rating from likelihood and fiscal impact (Low, Medium, High)."""
    lv = {'low': 1, 'medium': 2, 'high': 3}
    a, b = lv.get(str(likelihood).lower()), lv.get(str(impact).lower())
    if a is None or b is None:
        return ''
    return {2: 'Irrelevant', 3: 'Low', 4: 'Medium', 5: 'High', 6: 'Critical'}[a + b]


# ---------------------------------------------------------------------------------------- portfolio
def load(root=ROOT):
    root = Path(root)
    spec = yaml.safe_load(open(root / 'data' / 'pfram_projects.yaml'))
    rows = read_csv(root / 'data' / 'pfram_macro.csv')
    col = lambda k: [r[k] if r[k] != '' else None for r in rows]
    macro = Macro(start_year=int(rows[0]['year']), currency=spec.get('currency', 'DOM'),
                  **{k: col(k) for k in ('nominal_gdp', 'real_gdp', 'deflator', 'ner', 'primary_balance',
                                         'overall_balance', 'cash_balance', 'gross_debt', 'revenue')})
    projects = [Project.from_dict(d) for d in spec['projects']]
    shocks = {k: Shock(**{kk: tuple(vv) if kk.endswith('years') else vv for kk, vv in v.items()})
              for k, v in (spec.get('shocks') or {}).items()}
    return {'macro': macro, 'projects': projects, 'shocks': shocks, 'risks': spec.get('risks', {}),
            'country': spec.get('country', ''), 'note': spec.get('note', '')}


def portfolio(results, macro):
    """MacroParameters rows 44-60: the portfolio's impact on headline indicators (billion in, % of GDP out)."""
    n = NCOL
    tot = lambda r: [sum(res['rows'][r][i] for res in results) for i in range(n)]
    nlb, cash, debt, cl = tot(200), tot(237), tot(208), tot(211)
    g = [v or 0 for v in _blank(macro.nominal_gdp)]
    pct = lambda x, i: x / (g[i] * 1e3) * 100 if g[i] else None
    ob, cb, gd = (_blank(getattr(macro, k)) for k in ('overall_balance', 'cash_balance', 'gross_debt'))
    years = [macro.start_year + i for i in range(n)]
    out = []
    for i in range(n):
        if not g[i]:
            continue
        out.append({
            'year': years[i], 'ppp_nlb': nlb[i], 'ppp_nlb_pct': pct(nlb[i], i), 'ppp_cash': cash[i],
            'ppp_cash_pct': pct(cash[i], i), 'ppp_debt': debt[i], 'ppp_debt_pct': pct(debt[i], i),
            'ppp_contingent': cl[i], 'ppp_contingent_pct': pct(cl[i], i),
            'overall_balance_pct': pct(ob[i] * 1e3, i) if ob[i] is not None else None,
            'overall_balance_with_ppp_pct': pct(ob[i] * 1e3 + nlb[i], i) if ob[i] is not None else None,
            'cash_balance_pct': pct(cb[i] * 1e3, i) if cb[i] is not None else None,
            'cash_balance_with_ppp_pct': pct(cb[i] * 1e3 + cash[i], i) if cb[i] is not None else None,
            'gross_debt_pct': pct(gd[i] * 1e3, i) if gd[i] is not None else None,
            'gross_debt_with_ppp_pct': pct(gd[i] * 1e3 + debt[i], i) if gd[i] is not None else None,
        })
    return out


def project_table(res):
    """One row per year with the series the dashboard and CSV export use (million, national currency)."""
    R, L = res['rows'], res['project'].contract_length
    out = []
    for i, y in enumerate(res['years']):
        if i >= L + 1:
            break
        out.append({
            'year': y, 'revenue': R[112][i], 'tariffs': R[113][i], 'gov_payments': R[114][i],
            'construction': R[106][i], 'opex': R[117][i], 'debt_service': R[160][i], 'cfads': R[159][i],
            'equity_in': R[156][i], 'dividends': R[164][i], 'private_debt': R[146][i],
            'gov_revenue': R[176][i], 'gov_expense': R[181][i], 'net_operating_balance': R[198][i],
            'net_lending_borrowing': R[200][i], 'nonfinancial_assets': R[203][i], 'liabilities': R[208][i],
            'financial_liability': R[209][i], 'nonfinancial_liability': R[210][i], 'net_worth': R[202][i],
            'gov_cash_in': R[230][i], 'gov_cash_out': R[232][i], 'gov_net_cash': R[237][i],
            'contingent_max': R[211][i], 'contingent_revenue_guarantee': R[212][i],
            'contingent_debt_guarantee': R[213][i], 'expected_guarantee_payment': R[227][i],
            'liabilities_pct_gdp': R[740][i], 'contingent_pct_gdp': R[748][i], 'nlb_pct_gdp': R[737][i],
            'termination_liabilities': R[725][i], 'termination_nlb': R[730][i], 'termination_cash': R[731][i],
        })
    return out


def run_all(root=ROOT):
    d = load(root)
    base = [run_project(p, d['macro']) for p in d['projects']]
    shocked = {name: [run_project(p, d['macro'], s, effective_rate=b['summary']['effective_rate'])
                      for p, b in zip(d['projects'], base)] for name, s in d['shocks'].items()}
    return {**d, 'base': base, 'shocked': shocked, 'portfolio': portfolio(base, d['macro']),
            'portfolio_shocked': {k: portfolio(v, d['macro']) for k, v in shocked.items()}}


def main(argv=None):
    ap = argparse.ArgumentParser(description='PFRAM 2.0 port: PPP fiscal risk (ILLUSTRATIVE projects).')
    ap.add_argument('--root', default=None)
    ap.add_argument('--list', action='store_true')
    ap.add_argument('--project', default=None)
    ap.add_argument('--out', default=None, help='folder for pfram_<id>.csv and pfram_portfolio.csv')
    a = ap.parse_args(argv)
    root = Path(a.root) if a.root else ROOT
    r = run_all(root)
    for res in r['base']:
        p, s = res['project'], res['summary']
        if a.project and p.id != a.project:
            continue
        peak = max(range(len(res['rows'][208])), key=lambda i: res['rows'][208][i])
        print(f"{p.id} {p.name} [{p.funding}] {p.start_year}-{p.start_year + p.contract_length - 1}: "
              f"cost {s['total_construction_cost']:,.0f}m, effective rate {s['effective_rate']:.2%}, "
              f"peak liabilities {res['rows'][208][peak]:,.0f}m ({res['rows'][740][peak]:.2f}% GDP, {res['years'][peak]})")
    if a.out:
        out = Path(a.out)
        out.mkdir(parents=True, exist_ok=True)
        for res in r['base']:
            t = project_table(res)
            with open(out / f"pfram_{res['project'].id}.csv", 'w', newline='') as f:
                w = csv.DictWriter(f, fieldnames=list(t[0]))
                w.writeheader()
                w.writerows(t)
        with open(out / 'pfram_portfolio.csv', 'w', newline='') as f:
            w = csv.DictWriter(f, fieldnames=list(r['portfolio'][0]))
            w.writeheader()
            w.writerows(r['portfolio'])
        print(f'Tables written to {out}/')


if __name__ == '__main__':
    main()
