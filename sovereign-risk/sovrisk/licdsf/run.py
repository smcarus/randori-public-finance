"""End-to-end runner for the LIC DSF port: recompute every ported sheet of a book from its inputs.

Every module of sovrisk.licdsf that defines SHEETS and compute(book, sheet) is discovered at import time. The
template's sheets read each other in cycles at sheet level (Ext_Debt_Data <-> PV_Base, the baseline sheets <->
their output tables, PV_ResFin_pub <-> the stress-test sheets, and almost everything <-> the translation sheet),
but there are no cell-level circular references. run() therefore computes the sheets in a dependency-friendly
order and repeats the sequence (Gauss-Seidel) until a pass changes no formula value. Sheets none of whose inputs
changed since they were last computed are skipped, except in the final, confirming pass.

    python -m sovrisk.licdsf.run --golden tests/golden/licdsf [--keep] [-v]
"""
import argparse
import gzip
import importlib
import json
import math
import pkgutil
import time
from pathlib import Path

from sovrisk.srdsf.book import Book, close

# Sheets each sheet's formulas read (explicit Sheet! references and defined names), from the template's formula
# dump; ported sheets only.
DEPS = {
    'A1_historical_ext': (
        'A1_Historical_pub', 'Baseline - external', 'Ext_Debt_Data', 'Macro-Debt_Data', 'PV Stress', 'START',
        'translation'),
    'A1_Historical_pub': ('Baseline - public', 'Macro-Debt_Data', 'PV_ResFin_pub', 'START', 'translation'),
    'B1_GDP_ext': (
        'A1_historical_ext', 'Baseline - external', 'Ext_Debt_Data', 'Input 6(optional)-Standard Test', 'lookup',
        'Macro-Debt_Data', 'PV Stress', 'START', 'translation'),
    'B1_GDP_pub': (
        'A1_Historical_pub', 'Baseline - public', 'Input 6(optional)-Standard Test', 'lookup', 'Macro-Debt_Data',
        'PV_ResFin_pub', 'START', 'translation'),
    'B2_PB_mkt_pub': (
        'A1_Historical_pub', 'B1_GDP_pub', 'Baseline - external', 'Baseline - public',
        'Input 6(optional)-Standard Test', 'lookup', 'Macro-Debt_Data', 'PV_ResFin-add.int.cost - mkt',
        'PV_ResFin_pub', 'START', 'translation'),
    'B2_PB_non_mkt_pub': (
        'A1_Historical_pub', 'B1_GDP_pub', 'B2_PB_mkt_pub', 'Baseline - external', 'Baseline - public',
        'Input 6(optional)-Standard Test', 'lookup', 'Macro-Debt_Data', 'PV_ResFin-add.int.cost - mkt',
        'PV_ResFin_pub', 'START', 'translation'),
    'B3_Exports_ext': (
        'A1_historical_ext', 'Baseline - external', 'Ext_Debt_Data', 'Input 6(optional)-Standard Test', 'lookup',
        'Macro-Debt_Data', 'PV Stress', 'START', 'translation'),
    'B4_other flows_ext': (
        'A1_historical_ext', 'Baseline - external', 'Ext_Debt_Data', 'Input 6(optional)-Standard Test', 'lookup',
        'Macro-Debt_Data', 'PV Stress', 'START', 'translation'),
    'B5_depreciation_ext': (
        'A1_historical_ext', 'B5_depreciation_pub', 'Baseline - external', 'Ext_Debt_Data',
        'Input 6(optional)-Standard Test', 'lookup', 'Macro-Debt_Data', 'PV Stress', 'START', 'translation'),
    'B5_depreciation_pub': (
        'A1_Historical_pub', 'B6_combo_non-mkt_pub', 'Baseline - public', 'Input 6(optional)-Standard Test',
        'lookup', 'Macro-Debt_Data', 'PV_ResFin_pub', 'START', 'translation'),
    'B6_Combo_mkt_ext': (
        'A1_historical_ext', 'Baseline - external', 'Ext_Debt_Data', 'Input 6(optional)-Standard Test', 'lookup',
        'Macro-Debt_Data', 'PV Stress', 'PV_Base-add.cost.mkt', 'START', 'translation'),
    'B6_combo_mkt_pub': (
        'A1_Historical_pub', 'B1_GDP_pub', 'B2_PB_non_mkt_pub', 'Baseline - public',
        'Input 6(optional)-Standard Test', 'lookup', 'Macro-Debt_Data', 'PV_ResFin-add.int.cost - mkt',
        'PV_ResFin_pub', 'START', 'translation'),
    'B6_Combo_non-mkt_ext': (
        'A1_historical_ext', 'Baseline - external', 'Ext_Debt_Data', 'Input 6(optional)-Standard Test', 'lookup',
        'Macro-Debt_Data', 'PV Stress', 'START', 'translation'),
    'B6_combo_non-mkt_pub': (
        'A1_Historical_pub', 'B1_GDP_pub', 'B2_PB_non_mkt_pub', 'Baseline - public',
        'Input 6(optional)-Standard Test', 'lookup', 'Macro-Debt_Data', 'PV_ResFin-add.int.cost - mkt',
        'PV_ResFin_pub', 'START', 'translation'),
    'Baseline - external': (
        'A1_historical_ext', 'Ext_Debt_Data', 'Macro-Debt_Data', 'Output 1-1 - External DSA', 'START', 'translation'),
    'Baseline - public': (
        'B3_Exports_ext', 'B4_other flows_ext', 'Baseline - external', 'C4_Market_financing', 'Input 1 - Basics',
        'lookup', 'Macro-Debt_Data', 'Output 1-2 - Public DSA', 'START', 'translation'),
    'BLEND floating calculations WB': (),
    'C1_Combined CL': (
        'A1_Historical_pub', 'B2_PB_mkt_pub', 'Baseline - external', 'Baseline - public', 'Input 2 - Debt Coverage',
        'Input 6(optional)-Standard Test', 'Macro-Debt_Data', 'PV_ResFin_pub', 'START', 'translation'),
    'C2_Natural disaster': (
        'A1_Historical_pub', 'B2_PB_mkt_pub', 'Baseline - external', 'Baseline - public', 'Input 6 - Tailored Tests',
        'Macro-Debt_Data', 'PV_ResFin_pub', 'START', 'translation'),
    'C3_Commodity prices_ext': (
        'A1_historical_ext', 'Baseline - external', 'Ext_Debt_Data', 'Input 6 - Tailored Tests', 'Macro-Debt_Data',
        'PV Stress', 'START', 'translation'),
    'C3_commodity_prices_pub': (
        'A1_Historical_pub', 'B1_GDP_pub', 'Baseline - public', 'C3_Commodity prices_ext',
        'Input 6 - Tailored Tests', 'Macro-Debt_Data', 'PV_ResFin_pub', 'START', 'translation'),
    'C4_Market_financing': (
        'Baseline - external', 'Ext_Debt_Data', 'Input 4 - External Financing', 'Input 6 - Tailored Tests',
        'Macro-Debt_Data', 'PV Stress', 'PV_baseline_com', 'PV_stress_com', 'START', 'translation'),
    'Chart Data': (
        'A1_historical_ext', 'A1_Historical_pub', 'B1_GDP_ext', 'B1_GDP_pub', 'B2_PB_mkt_pub', 'B2_PB_non_mkt_pub',
        'B3_Exports_ext', 'B4_other flows_ext', 'B5_depreciation_ext', 'B5_depreciation_pub', 'B6_Combo_mkt_ext',
        'B6_combo_mkt_pub', 'B6_Combo_non-mkt_ext', 'B6_combo_non-mkt_pub', 'Baseline - external',
        'Baseline - public', 'C1_Combined CL', 'C2_Natural disaster', 'C3_Commodity prices_ext',
        'C3_commodity_prices_pub', 'C4_Market_financing', 'CI Summary', 'Customized Scenario - public',
        'Customized Scenario-External', 'Ext_Debt_Data', 'Input 1 - Basics', 'Input 6 - Tailored Tests',
        'Input 6(optional)-Standard Test', 'Macro-Debt_Data', 'Output 3-1 Stress-external',
        'Output 3-2 Stress-public', 'START', 'translation'),
    'CI Summary': (
        'Imported data', 'Input 1 - Basics', 'Input 6(optional)-Standard Test', 'Input-INSTRUCTIONS', 'lookup',
        'START', 'translation'),
    'Customized Scenario - public': (
        'A1_Historical_pub', 'Baseline - external', 'Baseline - public', 'Input 6 - Tailored Tests',
        'Input 7 - Residual Financing', 'Macro-Debt_Data', 'PV_ResFin_pub', 'START', 'translation'),
    'Customized Scenario-External': (
        'Baseline - external', 'Customized Scenario - public', 'Ext_Debt_Data', 'Input 7 - Residual Financing',
        'Macro-Debt_Data', 'PV_ResFin_pub', 'START', 'translation'),
    'DMX_OUT': ('Input 5 - Local-debt Financing',),
    'Dom_Debt_Data': ('Baseline - external', 'Baseline - public', 'Input 1 - Basics', 'Macro-Debt_Data'),
    'Dom_Debt_Indicators': (
        'Input 1 - Basics', 'Input 7 - Residual Financing', 'Macro-Debt_Data', 'Output 3-2 Stress-public', 'START',
        'translation'),
    'Ext_Debt_Data': (
        'Input 1 - Basics', 'Input 3 - Macro-Debt data(DMX)', 'Input 4 - External Financing',
        'Input 5 - Local-debt Financing', 'Input 7 - Residual Financing', 'Input 8 - SDR', 'lookup',
        'Macro-Debt_Data', 'PV_Base', 'PV_LC_NR1', 'PV_LC_NR2', 'PV_LC_NR3', 'START', 'translation'),
    'Imported data': (
        'Input 1 - Basics', 'lookup', 'Probability approach', 'Realism 1 - Forecast Error',
        'Realism 3 - Invest-Growth', 'Trigger'),
    'Input 1 - Basics': (
        'Input 6 - Tailored Tests', 'Input-INSTRUCTIONS', 'lookup', 'Realism 1 - Forecast Error', 'START',
        'translation'),
    'Input 2 - Debt Coverage': ('Input 1 - Basics', 'START', 'translation', 'Trigger'),
    'Input 3 - Macro-Debt data(DMX)': (
        'Input 1 - Basics', 'Input 4 - External Financing', 'Input-INSTRUCTIONS', 'lookup', 'Macro-Debt_Data',
        'START', 'translation'),
    'Input 4 - External Financing': (
        'BLEND floating calculations WB', 'Input 1 - Basics', 'Input 3 - Macro-Debt data(DMX)',
        'Input 5 - Local-debt Financing', 'Macro-Debt_Data', 'PV_Base', 'START', 'translation'),
    'Input 5 - Local-debt Financing': (
        'Baseline - public', 'Ext_Debt_Data', 'Input 1 - Basics', 'Input 3 - Macro-Debt data(DMX)',
        'Input 4 - External Financing', 'Input-INSTRUCTIONS', 'lookup', 'Macro-Debt_Data', 'START', 'translation'),
    'Input 6 - Tailored Tests': (
        'Imported data', 'Input 1 - Basics', 'Macro-Debt_Data', 'START', 'translation', 'Trigger'),
    'Input 6(optional)-Standard Test': (
        'Baseline - external', 'Baseline - public', 'Input 1 - Basics', 'Input 6 - Tailored Tests', 'lookup',
        'START', 'translation'),
    'Input 7 - Residual Financing': (
        'Ext_Debt_Data', 'Input 1 - Basics', 'Input 5 - Local-debt Financing', 'START', 'translation'),
    'Input 8 - SDR': ('Input 1 - Basics', 'Macro-Debt_Data'),
    'Input-INSTRUCTIONS': ('START', 'translation'),
    'lookup': ('Input 1 - Basics', 'START', 'translation'),
    'Macro-Debt_Data': (
        'Ext_Debt_Data', 'Input 1 - Basics', 'Input 3 - Macro-Debt data(DMX)', 'Input 5 - Local-debt Financing',
        'lookup', 'START', 'translation'),
    'Output - Submit': ('CI Summary', 'Input 1 - Basics', 'lookup', 'Macro-Debt_Data'),
    'Output - Summary': ('Input 1 - Basics', 'lookup', 'Macro-Debt_Data'),
    'Output 1-1 - External DSA': (
        'Baseline - external', 'Ext_Debt_Data', 'Input 1 - Basics', 'lookup', 'START', 'translation'),
    'Output 1-2 - Public DSA': (
        'Baseline - public', 'Input 1 - Basics', 'Input 2 - Debt Coverage', 'Macro-Debt_Data', 'START',
        'translation'),
    'Output 2-1 Stress_Charts_Ex': (
        'Chart Data', 'Customized Scenario-External', 'Input 1 - Basics', 'Input 2 - Debt Coverage',
        'Input 6 - Tailored Tests', 'Input 6(optional)-Standard Test', 'Input 7 - Residual Financing', 'lookup',
        'Macro-Debt_Data', 'Output 3-1 Stress-external', 'START', 'translation'),
    'Output 2-2 Stress_Charts_Pub': (
        'Chart Data', 'Customized Scenario - public', 'Input 1 - Basics', 'Input 7 - Residual Financing',
        'Macro-Debt_Data', 'Output 2-1 Stress_Charts_Ex', 'Output 3-2 Stress-public', 'START', 'translation'),
    'Output 3-1 Stress-external': (
        'Baseline - external', 'Chart Data', 'Customized Scenario-External', 'Input 1 - Basics', 'lookup',
        'Macro-Debt_Data', 'PV Stress', 'START', 'translation'),
    'Output 3-2 Stress-public': (
        'Chart Data', 'Customized Scenario - public', 'Input 1 - Basics', 'lookup', 'Macro-Debt_Data',
        'Output 3-1 Stress-external', 'START', 'translation'),
    'Output 4-1 - Forecast Error': ('Input 1 - Basics', 'START', 'translation'),
    'Output 4-2 - Realism': ('Input 1 - Basics', 'Realism 3 - Invest-Growth', 'START', 'translation'),
    'Output 5-1 Moderate risk': (
        'Chart Data', 'Input 1 - Basics', 'Macro-Debt_Data', 'Output 3-1 Stress-external', 'START', 'translation'),
    'Output 5-2 Market module': (
        'Baseline - public', 'Chart Data', 'Input 1 - Basics', 'lookup', 'Output 1-1 - External DSA',
        'Output 3-1 Stress-external', 'START', 'translation'),
    'Output 6 - Prob (if applicable)': ('Input 1 - Basics', 'Output 3-1 Stress-external', 'START', 'translation'),
    'Output 7 - Risk rating summary': (
        'Chart Data', 'CI Summary', 'Input 1 - Basics', 'Input 2 - Debt Coverage', 'Input 6 - Tailored Tests',
        'lookup', 'Output 5-2 Market module', 'START', 'translation'),
    'Output Database': (
        'A1_historical_ext', 'B1_GDP_ext', 'B3_Exports_ext', 'B4_other flows_ext', 'B5_depreciation_ext',
        'B6_Combo_non-mkt_ext', 'Baseline - external', 'Baseline - public', 'Chart Data', 'CI Summary',
        'Ext_Debt_Data', 'Input 1 - Basics', 'Input 2 - Debt Coverage', 'Input 3 - Macro-Debt data(DMX)',
        'Input 6 - Tailored Tests', 'lookup', 'Macro-Debt_Data', 'Output - Submit', 'Output 3-2 Stress-public',
        'Output 7 - Risk rating summary'),
    'Probability approach': (
        'Chart Data', 'Imported data', 'Input 1 - Basics', 'Input 3 - Macro-Debt data(DMX)', 'Macro-Debt_Data',
        'Output 1-1 - External DSA', 'START', 'translation'),
    'PV Stress': (
        'A1_historical_ext', 'B1_GDP_ext', 'B3_Exports_ext', 'B4_other flows_ext', 'B5_depreciation_ext',
        'B6_Combo_mkt_ext', 'B6_Combo_non-mkt_ext', 'C3_Commodity prices_ext', 'C4_Market_financing',
        'Ext_Debt_Data', 'Input 7 - Residual Financing', 'Macro-Debt_Data', 'PV_Base', 'PV_ResFin_pub'),
    'PV_Base': (
        'Ext_Debt_Data', 'Input 4 - External Financing', 'Input 5 - Local-debt Financing', 'Macro-Debt_Data',
        'PV_ResFin_pub'),
    'PV_Base-add.cost.mkt': (
        'B2_PB_mkt_pub', 'B6_combo_mkt_pub', 'Baseline - public', 'Ext_Debt_Data', 'Input 4 - External Financing',
        'Input 6 - Tailored Tests', 'Macro-Debt_Data', 'PV_ResFin_pub'),
    'PV_baseline_com': ('Ext_Debt_Data', 'Input 4 - External Financing', 'PV_Base'),
    'PV_LC_NR1': ('Ext_Debt_Data', 'Input 1 - Basics', 'Input 5 - Local-debt Financing', 'Macro-Debt_Data'),
    'PV_LC_NR2': (
        'Ext_Debt_Data', 'Input 1 - Basics', 'Input 5 - Local-debt Financing', 'Macro-Debt_Data', 'PV_LC_NR1'),
    'PV_LC_NR3': (
        'Ext_Debt_Data', 'Input 1 - Basics', 'Input 5 - Local-debt Financing', 'Macro-Debt_Data', 'PV_LC_NR1'),
    'PV_ResFin-add.int.cost - mkt': (
        'B2_PB_mkt_pub', 'B2_PB_non_mkt_pub', 'B6_combo_mkt_pub', 'B6_combo_non-mkt_pub', 'Baseline - public',
        'Input 1 - Basics', 'Input 6(optional)-Standard Test', 'Input 7 - Residual Financing', 'Macro-Debt_Data',
        'Output 1-1 - External DSA', 'PV_ResFin_pub', 'START'),
    'PV_ResFin_pub': (
        'A1_historical_ext', 'A1_Historical_pub', 'B1_GDP_ext', 'B1_GDP_pub', 'B2_PB_mkt_pub', 'B2_PB_non_mkt_pub',
        'B5_depreciation_ext', 'B5_depreciation_pub', 'B6_Combo_mkt_ext', 'B6_combo_mkt_pub', 'B6_Combo_non-mkt_ext',
        'B6_combo_non-mkt_pub', 'Baseline - public', 'C1_Combined CL', 'C2_Natural disaster',
        'C3_Commodity prices_ext', 'C3_commodity_prices_pub', 'Input 3 - Macro-Debt data(DMX)',
        'Input 7 - Residual Financing', 'Macro-Debt_Data', 'Output 1-1 - External DSA', 'START', 'translation'),
    'PV_stress_com': (
        'C4_Market_financing', 'Ext_Debt_Data', 'Input 4 - External Financing', 'Output 1-1 - External DSA',
        'PV_Base'),
    'Realism 1 - Forecast Error': (
        'Baseline - external', 'Baseline - public', 'Imported data', 'Input 1 - Basics', 'lookup', 'Output - Submit',
        'START', 'translation'),
    'Realism 2 - Fiscal multiplier': ('Input 3 - Macro-Debt data(DMX)', 'Macro-Debt_Data'),
    'Realism 3 - Invest-Growth': (
        'Baseline - external', 'Imported data', 'Input 1 - Basics', 'Macro-Debt_Data', 'Output - Submit',
        'Realism 1 - Forecast Error', 'START', 'translation'),
    'Realism 4 - Fiscal adjustment': ('Baseline - public', 'Input 3 - Macro-Debt data(DMX)', 'START', 'translation'),
    'START': ('lookup',),
    'translation': (
        'Baseline - external', 'C2_Natural disaster', 'Customized Scenario-External', 'Input 1 - Basics',
        'Input 3 - Macro-Debt data(DMX)', 'Input 4 - External Financing', 'Input-INSTRUCTIONS', 'Macro-Debt_Data',
        'Output 3-1 Stress-external', 'START'),
    'Trigger': ('Imported data', 'lookup'),
}

# Run order. A tuple is a group of sheets that feed each other year by year (PV_ResFin_pub finances each stress
# test's gap of year t, and the stress sheets read its interest bill back for year t+1): a group is iterated on its
# own until it settles before the run moves on, so the sheets downstream of it are not recomputed ~20 times.
# Settled by experiment (see NOTES); sheets not listed here (new ports) are placed after the last listed sheet
# they read.
INPUTS = (
    # settings, labels and the imported country data
    'START', 'lookup', 'Input-INSTRUCTIONS', 'Input 1 - Basics', 'translation', 'Imported data', 'Trigger',
    'CI Summary', 'Input 2 - Debt Coverage', 'Input 6 - Tailored Tests', 'BLEND floating calculations WB',
    # macro and debt inputs, loan-by-loan debt service and its present value
    'Input 3 - Macro-Debt data(DMX)', 'Input 4 - External Financing', 'Input 8 - SDR', 'PV_Base', 'PV_LC_NR1',
    'PV_LC_NR2', 'PV_LC_NR3', 'Ext_Debt_Data', 'Input 5 - Local-debt Financing', 'Input 7 - Residual Financing',
    'Macro-Debt_Data', 'Dom_Debt_Data', 'DMX_OUT',
    # baseline
    'Baseline - external', 'Output 1-1 - External DSA', 'Baseline - public', 'Output 1-2 - Public DSA',
    'Input 6(optional)-Standard Test', 'PV_baseline_com')
STRESS = ('PV_ResFin_pub',
          'A1_Historical_pub', 'B1_GDP_pub', 'B2_PB_mkt_pub', 'B2_PB_non_mkt_pub', 'B5_depreciation_pub',
          'B6_combo_mkt_pub', 'B6_combo_non-mkt_pub', 'C1_Combined CL', 'C2_Natural disaster',
          'PV_ResFin-add.int.cost - mkt', 'PV_Base-add.cost.mkt',
          'A1_historical_ext', 'B1_GDP_ext', 'B3_Exports_ext', 'B4_other flows_ext', 'B5_depreciation_ext',
          'B6_Combo_mkt_ext', 'B6_Combo_non-mkt_ext', 'C3_Commodity prices_ext', 'C3_commodity_prices_pub',
          'PV_stress_com', 'C4_Market_financing', 'PV Stress')
ORDER = [
    INPUTS,
    STRESS,
    'Customized Scenario - public', 'Customized Scenario-External',
    # summaries, charts and the database
    'Chart Data', 'Output 3-1 Stress-external', 'Output 3-2 Stress-public', 'Output 2-1 Stress_Charts_Ex',
    'Output 2-2 Stress_Charts_Pub', 'Output 5-1 Moderate risk', 'Output 5-2 Market module',
    'Output 6 - Prob (if applicable)', 'Output 7 - Risk rating summary', 'Output 4-1 - Forecast Error',
    'Realism 1 - Forecast Error', 'Realism 2 - Fiscal multiplier', 'Realism 3 - Invest-Growth',
    'Realism 4 - Fiscal adjustment', 'Output 4-2 - Realism', 'Probability approach', 'Dom_Debt_Indicators',
    'Output - Summary', 'Output - Submit', 'Output Database',
]

NOTES = [
    'INPUTS is one group because its sheets read each other in both directions (Ext_Debt_Data sums PV_Base and '
    'PV_LC_NR1-3, which read the loan terms back from Ext_Debt_Data; Input 5 reads Baseline - public, Macro-Debt_Data '
    'reads Input 5; translation builds labels from Input 4 / Macro-Debt_Data); sweeping it to a fixed point first '
    'keeps the expensive stress group from being re-run on half-settled inputs.',
    'STRESS needs about one sweep per projection year (PV_ResFin_pub year t -> stress sheet year t+1 -> '
    'PV_ResFin_pub year t+1), about 20 sweeps from blank formula cells; as a group, the summaries downstream '
    '(Chart Data, Output Database, ...) are computed once instead of once per sweep.',
    'Imported data reads Realism 1 / 3 and Probability approach (downstream), and Baseline - public rows 85+ read '
    'B3 / B4 / C4; these back edges are picked up by the next pass. From blank formula cells the sample settles in '
    '3 changing passes plus the confirming ones (5 passes, ~25 s); a flat, ungrouped Gauss-Seidel took 27 passes.',
]

_SKIP_MODULES = {'run'}


def modules():
    """{sheet: module} for every module of the package that ports a sheet (has SHEETS and compute)."""
    import sovrisk.licdsf as pkg
    out = {}
    for m in pkgutil.iter_modules(pkg.__path__):
        if m.name in _SKIP_MODULES:
            continue
        mod = importlib.import_module(f'{pkg.__name__}.{m.name}')
        if not hasattr(mod, 'compute'):
            continue
        for sheet in getattr(mod, 'SHEETS', ()):
            out[sheet] = mod
    return out


def _flat(items):
    return [x for it in items for x in (it if isinstance(it, tuple) else (it,))]


def order(sheets):
    """Run order as a list of items, each a sheet or a tuple of sheets iterated together (see ORDER): ORDER first,
    then any other sheet after the last item (already placed) holding a sheet it reads."""
    sheets = set(sheets)
    out = []
    for it in ORDER:
        it = tuple(s for s in it if s in sheets) if isinstance(it, tuple) else it
        if it and (isinstance(it, tuple) or it in sheets):
            out.append(it)
    placed = _flat(out)
    for s in sorted(s for s in sheets if s not in placed):
        deps = set(DEPS.get(s, ()))
        pos = max((i + 1 for i, it in enumerate(out) if deps & set(_flat([it]))), default=len(out))
        out.insert(pos, s)
    return out


# ---------------------------------------------------------------------------------------------------------------
# Loading and blanking
# ---------------------------------------------------------------------------------------------------------------

def load(folder):
    """Book.load plus book.formulas = {sheet: [(row, col), ...]}: the cells that hold a formula in the template."""
    folder = Path(folder)
    book = Book.load(folder)
    book.formulas = {}
    for f in folder.glob('*.json.gz'):
        d = json.loads(gzip.decompress(f.read_bytes()))
        book.formulas[d['sheet']] = [tuple(x) for x in d['formulas']]
    return book


def blank(book, sheets=None):
    """Delete every formula cell of the given sheets (default: every ported sheet), leaving only inputs."""
    for s in (modules() if sheets is None else sheets):
        S = book[s]
        for k in book.formulas.get(s, ()):
            S.cells.pop(k, None)


# ---------------------------------------------------------------------------------------------------------------
# The run
# ---------------------------------------------------------------------------------------------------------------

def _same(a, b, tol):
    if a == b and type(a) is type(b):
        return True
    if isinstance(a, float) and isinstance(b, float) and math.isnan(a) and math.isnan(b):
        return True
    return tol > 0 and close(a, b, rel=tol, abs_=tol)


def _changed(before, after, tol):
    """Number of cells whose value differs (a blank and a missing cell are the same; 0 and a blank are not)."""
    n = 0
    for k in before.keys() | after.keys():
        if not _same(before.get(k), after.get(k), tol):
            n += 1
    return n


def settle(book, max_passes=60, tol=0.0, sheets=None, log=None, max_sweeps=200):
    """Gauss-Seidel over the sheets until a pass changes nothing. Returns (passes, settled, history), history being
    one {sheet: cells changed} per pass (summed over a group's sweeps). A sheet is skipped when none of the sheets
    it reads (nor itself) has changed since it was last computed, except in a full pass: the first pass and the
    confirming pass that ends the run. A group (tuple in ORDER) is swept until a sweep changes nothing, at most
    max_sweeps times per pass."""
    mods = modules()
    seq = order(s for s in mods if sheets is None or s in sheets)
    version = {s: 0 for s in _flat(seq)}
    seen = {}
    history = []
    full = True

    def step(s, changed, force):
        deps = [d for d in DEPS.get(s, ()) if d in version] + [s]
        if not force and seen.get(s) == tuple(version[d] for d in deps):
            return 0
        S = book[s]
        before = dict(S.cells)
        mods[s].compute(book, s)
        n = _changed(before, S.cells, tol)
        if n:
            changed[s] = changed.get(s, 0) + n
            version[s] += 1
        seen[s] = tuple(version[d] for d in deps)
        return n

    for p in range(1, max_passes + 1):
        changed = {}
        for it in seq:
            if not isinstance(it, tuple):
                step(it, changed, full)
                continue
            for k in range(max_sweeps):
                if not sum(step(s, changed, full and k == 0) for s in it):
                    break
        history.append(changed)
        if log:
            log(f'pass {p}: ' + (', '.join(f'{s} {n}' for s, n in changed.items()) or 'no change'))
        if not changed:
            if full:
                return p, True, history
            full = True               # confirm with a pass that recomputes every sheet
        else:
            full = False
    return max_passes, False, history


def run(book, max_passes=60, tol=0.0, log=None):
    """Recompute every formula sheet of `book` from the values already in it.

    Returns a dict: passes (formula passes), settled (a pass changed nothing) and history (per pass, the number
    of cells each sheet changed)."""
    p, ok, h = settle(book, max_passes, tol, log=log)
    return {'passes': p, 'settled': ok, 'history': h}


# ---------------------------------------------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------------------------------------------

HEADLINES = [
    ('Debt-carrying capacity (CI Summary!B9)', 'CI Summary', 'B9'),
    ('Composite indicator (CI Summary!C10)', 'CI Summary', 'C10'),
    ('Mechanical external risk rating (Chart Data!D10)', 'Chart Data', 'D10'),
    ('Fiscal (public debt) signal (Chart Data!I10)', 'Chart Data', 'I10'),
    ('Mechanical overall risk rating (Chart Data!L10)', 'Chart Data', 'L10'),
    ('Moderate-risk space to absorb shocks (Chart Data!D23)', 'Chart Data', 'D23'),
]

# (indicator, threshold cell, baseline-breach count cell, shock-breach count cell, most extreme shock cell) on
# Chart Data; breaches are counted over the first ten projection years.
BREACHES = [
    ('PV of external debt-to-GDP', 'D66', 'D74', 'D75', 'C69'),
    ('PV of external debt-to-exports', 'D108', 'D116', 'D117', 'C111'),
    ('External debt service-to-exports', 'D150', 'D158', 'D159', 'C153'),
    ('External debt service-to-revenue', 'D192', 'D200', 'D201', 'C195'),
    ('PV of total public debt-to-GDP', 'D267', 'D275', 'D276', 'C270'),
]


def headlines(book):
    return [(label, book[sh][cell]) for label, sh, cell in HEADLINES]


def breaches(book):
    """[(indicator, threshold, baseline breaches, shock breaches, most extreme shock)]."""
    S = book['Chart Data']
    return [(label,) + tuple(S[c] for c in cells) for label, *cells in BREACHES]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--golden', default='tests/golden/licdsf', help='folder of the template golden values')
    ap.add_argument('--keep', action='store_true', help='start from the cached values instead of blank formulas')
    ap.add_argument('--max-passes', type=int, default=60)
    ap.add_argument('--tol', type=float, default=0.0)
    ap.add_argument('-v', '--verbose', action='store_true')
    a = ap.parse_args(argv)
    book = load(a.golden)
    if not a.keep:
        blank(book)
    t = time.time()
    res = run(book, a.max_passes, a.tol, log=print if a.verbose else None)
    print(f"sheets: {len(modules())}")
    print(f"passes: {res['passes']}  settled: {res['settled']}  time: {time.time() - t:.1f}s")
    for label, v in headlines(book):
        print(f'{label}: {v}')
    print('Breaches over the first 10 projection years (threshold; baseline years; shock years; most extreme shock):')
    def show(v):
        return int(v) if isinstance(v, float) and v.is_integer() else v
    for label, thr, base, shock, mx in breaches(book):
        print(f'  {label}: {show(thr)}; {show(base)}; {show(shock)}; {mx}')
    return 0 if res['settled'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
