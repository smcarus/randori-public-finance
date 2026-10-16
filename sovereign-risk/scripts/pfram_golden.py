"""Build PFRAM parity cases: write each illustrative project into the real PFRAM 2.0 workbook, recalculate it
in LibreOffice and save every Template row as tests/golden/pfram/<case>.json.

    python scripts/pfram_golden.py path/to/pfram2english.xlsm

Needs LibreOffice (soffice) on the PATH. The workbook's VBA does not run in LibreOffice, so this script does
what the macros would: it enters the inputs, links the payment rows to the service projections (Calc_Row1 and
Calc_Row2) and enters the effective interest rate that sovrisk.pfram solved for (EIR_Seek). The test then
checks that the workbook's own goal-seek condition holds at that rate.
"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import openpyxl
from openpyxl.utils import get_column_letter

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sovrisk import pfram as P  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'tests' / 'golden' / 'pfram'
ROWS = (list(range(106, 172)) + list(range(176, 238)) + [459, 618, 627, 630, 640, 641, 643, 644]
        + list(range(717, 761)))
YN = lambda b: 'Yes' if b else 'No'


def fill(wb, p, macro, shock, wacc):
    m, t, sa = wb['Menu'], wb['Template'], wb['SensitivityAnalysis']
    m['F9'], m['F10'], m['F11'] = 1, macro.start_year, macro.currency
    mp = wb['MacroParameters']
    for r, k in zip(range(4, 13), ('nominal_gdp', 'real_gdp', 'deflator', 'ner', 'primary_balance', 'overall_balance',
                                   'cash_balance', 'gross_debt', 'revenue')):
        for i, v in enumerate(getattr(macro, k)[:P.NCOL]):
            mp.cell(r, 3 + i, v)
    t['B11'], t['B31'], t['B32'], t['B33'], t['B34'], t['B35'] = (P.FUNDING[p.funding], p.name, p.type, p.start_year,
                                                                  p.contract_length, p.currency)
    t['K32'], t['K33'], t['K34'], t['K35'] = p.gov_shareholding, p.debt_share, p.interest_rate, p.fx_debt_share
    t['H37'], t['H39'], t['H41'] = p.asset_controller, p.gov_controls_services, p.gov_residual_interest
    t['T32'], t['T33'], t['T34'] = wacc, p.tax_rate, 0
    t['K40'], t['E54'] = max(1, len(p.assets)), max(1, len(p.services))
    for k, a in enumerate(p.assets):
        for r, v in zip(range(45, 51), (a.name, a.construction_period, a.construction_start, a.useful_life, a.cost,
                                        a.land_cost)):
            t.cell(r, 2 + k, v)
    for k, s in enumerate(p.services):
        r = 58 + k
        for c, v in zip('BCDEGH', (s.unit, s.start, s.tariff, s.user_demand, s.price, s.gov_demand)):
            t[f'{c}{r}'] = v
        b = 305 + 8 * k
        t[f'B{b + 1}'], t[f'B{b + 3}'], t[f'B{b + 4}'] = s.tariff_currency, YN(s.tariff_inflation_indexed), YN(s.tariff_ner_indexed)
        b2 = 387 + 6 * k
        t[f'B{b2 + 2}'] = YN(s.user_demand_gdp_linked)
        b3 = 464 + 8 * k
        t[f'B{b3 + 1}'], t[f'B{b3 + 3}'], t[f'B{b3 + 4}'] = s.price_currency, YN(s.price_inflation_indexed), YN(s.price_ner_indexed)
        b4 = 546 + 6 * k
        t[f'B{b4 + 2}'] = YN(s.gov_demand_gdp_linked)
        for row, xs in ((b + 5, s.tariff_adjust), (b2 + 3, s.user_demand_adjust), (b3 + 5, s.price_adjust),
                        (b4 + 3, s.gov_demand_adjust)):
            for j, v in enumerate(xs):
                t.cell(row, 4 + j, v)
    for row, xs in ((71, p.maintenance), (72, p.operation), (73, p.user_fees_to_gov), (74, p.royalties),
                    (75, p.other_payments_to_gov), (76, p.other_costs), (82, p.other_gov_payment)):
        for i, v in enumerate(xs):
            t.cell(row, 3 + i, v)
    for row, xs, src in ((78, p.availability_payment, 618), (84, p.tariffs, 459)):
        for i in range(P.NCOL):
            t.cell(row, 3 + i, (xs[i] if i < len(xs) else None) if xs is not None else f'={get_column_letter(4 + i)}{src}')
    t['B78'] = YN(p.availability_indexed)
    if p.other_index is not None:
        t['B79'] = 'Yes'
        for i, v in enumerate(p.other_index):
            t.cell(79, 3 + i, v)
    t['B624'] = p.debt_guarantee_share
    for row, xs in ((633, p.guaranteed_price), (637, p.guaranteed_demand)):
        for j, v in enumerate(xs):
            t.cell(row, 4 + j, v)
    t['K651'], t['A650'], t['K655'] = p.termination_year, p.termination_method, p.termination_share
    s = shock or P.Shock()
    for r, (size, (a, b)) in zip((58, 60, 62), ((s.gdp, s.gdp_years), (s.er, s.er_years), (s.inflation, s.inflation_years))):
        if a is not None:
            sa[f'L{r}'], sa[f'N{r}'], sa[f'P{r}'] = size, a, b


def recalc(src, workdir):
    profile = Path(tempfile.gettempdir()) / 'pfram_lo_profile'
    (profile / 'user').mkdir(parents=True, exist_ok=True)
    (profile / 'user' / 'registrymodifications.xcu').write_text(
        '<?xml version="1.0" encoding="UTF-8"?><oor:items xmlns:oor="http://openoffice.org/2001/registry" '
        'xmlns:xs="http://www.w3.org/2001/XMLSchema" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
        '<item oor:path="/org.openoffice.Office.Calc/Formula/Load"><prop oor:name="OOXMLRecalcMode" oor:op="fuse">'
        '<value>0</value></prop></item></oor:items>')
    out = Path(workdir) / 'out'
    subprocess.run(['soffice', f'-env:UserInstallation=file://{profile}', '--headless', '--calc', '--convert-to', 'xlsx',
                    '--outdir', str(out), str(src)], check=True, capture_output=True, timeout=600)
    return out / (Path(src).stem + '.xlsx')


def read(path):
    wb = openpyxl.load_workbook(path, data_only=True)
    t = wb['Template']
    val = lambda v: v if isinstance(v, (int, float)) and not isinstance(v, bool) else (None if v in (None, '') else str(v))
    rows = {str(r): [val(t.cell(r, c).value) for c in P.COLS] for r in ROWS}
    lower = {str(r): [val(t.cell(r, c).value) for c in range(4, 4 + P.NCOL - 1)] for r in (459, 618, 627, 630, 640, 641, 643, 644)}
    rows.update(lower)
    scal = {k: val(t[c].value) for k, c in (('I17', 'I17'), ('T36', 'T36'), ('T37', 'T37'), ('T38', 'T38'),
                                             ('C169', 'C169'), ('A651', 'A651'), ('A652', 'A652'), ('R14', 'R14'))}
    return rows, scal


def main(xlsm):
    d = P.load(ROOT)
    OUT.mkdir(parents=True, exist_ok=True)
    cases = [(p, None, None) for p in d['projects']] + [(p, name, s) for name, s in d['shocks'].items() for p in d['projects']]
    with tempfile.TemporaryDirectory() as tmp:
        for p, sname, s in cases:
            wacc = P.solve_effective_rate(p, d['macro'])          # the shocked runs keep the base rate
            wb = openpyxl.load_workbook(xlsm)
            fill(wb, p, d['macro'], s, wacc)
            case = p.id + (f'_{sname}' if sname else '')
            src = Path(tmp) / f'{case}.xlsx'
            wb.save(src)
            rows, scal = read(recalc(src, tmp))
            (OUT / f'{case}.json').write_text(json.dumps({'project': p.id, 'shock': sname, 'wacc': wacc,
                                                          'scalars': scal, 'rows': rows}))
            print(case, 'T36', scal['T36'], 'T37', scal['T37'])


if __name__ == '__main__':
    main(sys.argv[1])
