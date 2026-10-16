"""LIC DSF residual-financing sheets behind the stress tests.

- PV_ResFin_pub:                 for each public stress scenario, the residual financing (gross financing need not
  covered by the baseline) split into new external, domestic medium/long-term and domestic short-term debt, with
  their stocks, interest, amortization schedules and present values.
- PV_ResFin-add.int.cost - mkt:  the extra interest cost of that financing for the market-access scenarios (B2, B6),
  and the PV of external debt under the higher borrowing cost.
- PV Stress:                     the same new-borrowing calculation for the external stress scenarios.

Each sheet is a set of repeated scenario blocks: the block's rules are written once (rows blk + k, with SP / SE the
scenario's public / external stress sheet) and each block then lists only its own differences.
"""
from .baseline import Calc, X, TR, IF, AND, CHOOSE, ISNUMBER, ISTEXT, SUM, AVERAGE, MIN, MAX, STDEV, NPV, ROUNDDOWN, CONCATENATE, TEXT  # noqa

SHEETS = ['PV_ResFin_pub', 'PV_ResFin-add.int.cost - mkt', 'PV Stress']

QUIRKS = [
    "PV_ResFin_pub, amortization t-m terms (row 60 and the matching rows of every scenario block): the CHOOSE over cumulative borrowing takes its last three options (AD:AF) from a fixed row of an earlier block - row 37, the A1 block's cumulative external borrowing (rows 65 and 109 in the C1 and C2 blocks) - instead of the block's own cumulative row.",
    'PV_ResFin-add.int.cost - mkt!F40, F73, F106, F139: the CHOOSE over disbursements ends in three #REF! options.',
    'PV_ResFin-add.int.cost - mkt!AF20 continues the year row from AE22 instead of AE20 (same years, so no effect).',
    'PV_ResFin_pub!BB14 and PV Stress!BB9: the last NPV runs over BB:BC, one column past the schedule (blank, so no effect).',
]


def _resfin_block(s, blk, SP, SE):
    """One scenario block of PV_ResFin_pub (public and external stress scenario)"""
    BP = s.sheet('Baseline - public')
    S = s.sheet(s.name)
    # blk+0 Bounds Test 1: Real GDP Growth Shock
    s.put(blk, 'A', lambda c: SP['B2'])
    # blk+2 New borrowing (gross, in LCU)
    s.put(blk + 2, 'C', lambda c: S['C31'])
    s.put(blk + 2, 'D:X', lambda c: SP[90, c+1] - BP[78, c+11])
    # blk+3 (gross, in USD)
    s.put(blk + 3, 'E:X', lambda c: S[blk + 2, c] / S[27, c])
    # blk+4 New borrowing under the external DSA (in USD)
    s.put(blk + 4, 'C', lambda c: S['C33'])
    s.put(blk + 4, 'D:X', lambda c: SE[86, c])
    # blk+5 Modality of residual financing (1: external, 2: public):
    s.put(blk + 5, 'E:X', lambda c: IF(S[blk + 4, c] > S[blk + 2, c] * S['B4'] / S[27, c], 1, 2))
    # blk+7 New forex borrowing (gross, USD)
    s.put(blk + 7, 'C', lambda c: S['C36'])
    s.put(blk + 7, 'D:X', lambda c: IF(S[blk + 5, c] == 1, IF(S[blk + 4, c] > S[blk + 2, c] / S[27, c], S[blk + 2, c] / S[27, c], S[blk + 4, c]), S[blk + 2, c] * S['B4'] / S[27, c]))
    # blk+8 cumulative
    s.put(blk + 8, 'C', lambda c: S['C37'])
    s.put(blk + 8, 'D', lambda c: S[blk + 7, 'D'])
    s.put(blk + 8, 'E:X', lambda c: SUM(S.rng(blk + 7, 'D', blk + 7, c)))
    # blk+9 Stock of new forex debt (in USD)
    s.put(blk + 9, 'C', lambda c: S['C38'])
    s.put(blk + 9, 'D', lambda c: S[blk + 7, 'D'] - S[blk + 13, 'D'])
    s.put(blk + 9, 'E:X', lambda c: S[blk + 9, c-1] + S[blk + 7, c] - S[blk + 13, c])
    # blk+10 PV of new forex debt (in USD)
    s.put(blk + 10, 'C', lambda c: S['C39'])
    s.put(blk + 10, 'D', lambda c: IF(S['B9'] > S['B10'], S[blk + 7, 'D'], S[blk + 7, 'D'] * S['D14'] / 100))
    s.put(blk + 10, 'E:X', lambda c: IF(S['B9'] > S['B10'], S[blk + 10, c-1] - S[blk + 13, c] + S[blk + 7, c], S[blk + 10, c-1] * (1 + S['B10']) - S[blk + 11, c] + S[blk + 7, c] * S['D14'] / 100))
    # blk+11 Total debt service (in USD)
    s.put(blk + 11, 'C', lambda c: S['C40'])
    s.put(blk + 11, 'D:X', lambda c: S[blk + 12, c] + S[blk + 13, c])
    # blk+12 Interest
    s.put(blk + 12, 'C', lambda c: S['C41'])
    s.put(blk + 12, 'E:X', lambda c: S[blk + 9, c-1] * S['B9'])
    # blk+13 Amortization
    s.put(blk + 13, 'C', lambda c: S['C42'])
    s.put(blk + 13, 'D:X', lambda c: (S[blk + 16, c] - S[blk + 18, c]) / (S['B11'] - S['B12']))
    # blk+15 t-g>0
    s.put(blk + 15, 'C', lambda c: S['C44'])
    s.put(blk + 15, 'D:X', lambda c: IF(S[7, c] - S['B12'] > 0, S[7, c] - S['B12'], 0))
    # blk+16
    s.put(blk + 16, 'D:X', lambda c: IF(S[blk + 15, c] == 0, 0, CHOOSE(S[blk + 15, c], *S.cells(blk + 8, 'D', 'AF'))))
    # blk+17 t-m condition
    s.put(blk + 17, 'C', lambda c: S['C46'])
    s.put(blk + 17, 'D:X', lambda c: IF(S[7, c] - S['B11'] > 0, S[7, c] - S['B11'], 0))
    # blk+18
    s.put(blk + 18, 'D:X', lambda c: IF(S[blk + 17, c] == 0, 0, CHOOSE(S[blk + 17, c], *S.cells(blk + 8, 'D', 'AC'), *S.cells(37, 'AD', 'AF'))))
    # blk+20 New domestic MLT borrowing (gross)
    s.put(blk + 20, 'C', lambda c: S['C49'])
    s.put(blk + 20, 'D:X', lambda c: IF(SUM(S['B5'] + S['B6']) == 0, 0, (S[blk + 2, c] - S[blk + 7, c] * S[27, c]) * S['B5'] / (S['B5'] + S['B6'])))
    # blk+21 cumulative
    s.put(blk + 21, 'C', lambda c: S['C50'])
    s.put(blk + 21, 'D', lambda c: S[blk + 20, 'D'])
    s.put(blk + 21, 'E:X', lambda c: SUM(S.rng(blk + 20, 'D', blk + 20, c)))
    # blk+22 Stock of new domestic MLT debt
    s.put(blk + 22, 'C', lambda c: S['C51'])
    s.put(blk + 22, 'D', lambda c: S[blk + 20, 'D'] - S[blk + 26, 'D'])
    s.put(blk + 22, 'E:X', lambda c: S[blk + 22, c-1] + S[blk + 20, c] - S[blk + 26, c])
    # blk+24 Total debt service
    s.put(blk + 24, 'C', lambda c: S['C53'])
    s.put(blk + 24, 'D:X', lambda c: S[blk + 25, c] + S[blk + 26, c])
    # blk+25 Interest
    s.put(blk + 25, 'C', lambda c: S['C54'])
    s.put(blk + 25, 'E:X', lambda c: S[blk + 22, c-1] * S[16, c])
    # blk+26 Amortization
    s.put(blk + 26, 'C', lambda c: S['C55'])
    s.put(blk + 26, 'D:X', lambda c: (S[blk + 29, c] - S[blk + 31, c]) / (S['B18'] - S['B19']))
    # blk+28 t-g>0
    s.put(blk + 28, 'C', lambda c: S['C57'])
    s.put(blk + 28, 'D:X', lambda c: IF(S[7, c] - S['B19'] > 0, S[7, c] - S['B19'], 0))
    # blk+29
    s.put(blk + 29, 'D:X', lambda c: IF(S[blk + 28, c] == 0, 0, CHOOSE(S[blk + 28, c], *S.cells(blk + 21, 'D', 'AF'))))
    # blk+30 t-m condition
    s.put(blk + 30, 'C', lambda c: S['C59'])
    s.put(blk + 30, 'D:X', lambda c: IF(S[7, c] - S['B18'] > 0, S[7, c] - S['B18'], 0))
    # blk+31
    s.put(blk + 31, 'D:X', lambda c: IF(S[blk + 30, c] == 0, 0, CHOOSE(S[blk + 30, c], *S.cells(blk + 21, 'D', 'AC'), *S.cells(37, 'AD', 'AF'))))
    # blk+33 New domestic short-term borrowing (gross; also stock of debt)
    s.put(blk + 33, 'C', lambda c: S['C62'])
    s.put(blk + 33, 'D:X', lambda c: IF(SUM(S['B5'] + S['B6']) == 0, 0, (S[blk + 2, c] - S[blk + 7, c] * S[27, c]) * S['B6'] / (S['B5'] + S['B6'])))
    # blk+34 Interest
    s.put(blk + 34, 'C', lambda c: S['C63'])
    s.put(blk + 34, 'E:X', lambda c: S[blk + 33, c-1] * S[22, c])


def _resfin_block_pub(s, blk, SP):
    """One public-only scenario block of PV_ResFin_pub"""
    BP = s.sheet('Baseline - public')
    S = s.sheet(s.name)
    # blk+0 Bounds Test 2: Primary Balance Shock for non-market access countries
    s.put(blk, 'A', lambda c: SP['B2'])
    # blk+2 New borrowing (gross, in LCU)
    s.put(blk + 2, 'C', lambda c: S['C31'])
    s.put(blk + 2, 'D:X', lambda c: SP[90, c+1] - BP[78, c+11])
    # blk+4 New forex borrowing (gross, USD)
    s.put(blk + 4, 'C', lambda c: S['C36'])
    s.put(blk + 4, 'D:X', lambda c: S[blk + 2, c] * S['B4'] / S[27, c])
    # blk+5 cumulative
    s.put(blk + 5, 'C', lambda c: S['C37'])
    s.put(blk + 5, 'D', lambda c: S[blk + 4, 'D'])
    s.put(blk + 5, 'E:X', lambda c: SUM(S.rng(blk + 4, 'D', blk + 4, c)))
    # blk+6 Stock of new forex debt (in USD)
    s.put(blk + 6, 'C', lambda c: S['C38'])
    s.put(blk + 6, 'D', lambda c: S[blk + 4, 'D'] - S[blk + 10, 'D'])
    s.put(blk + 6, 'E:X', lambda c: S[blk + 6, c-1] + S[blk + 4, c] - S[blk + 10, c])
    # blk+7 PV of new forex debt (in USD)
    s.put(blk + 7, 'C', lambda c: S['C39'])
    s.put(blk + 7, 'D', lambda c: IF(S['B9'] > S['B10'], S[blk + 4, 'D'], S[blk + 4, 'D'] * S['D14'] / 100))
    s.put(blk + 7, 'E:X', lambda c: IF(S['B9'] > S['B10'], S[blk + 7, c-1] - S[blk + 10, c] + S[blk + 4, c], S[blk + 7, c-1] * (1 + S['B10']) - S[blk + 8, c] + S[blk + 4, c] * S['D14'] / 100))
    # blk+8 Total debt service (in USD)
    s.put(blk + 8, 'C', lambda c: S['C40'])
    s.put(blk + 8, 'D:X', lambda c: S[blk + 9, c] + S[blk + 10, c])
    # blk+9 Interest
    s.put(blk + 9, 'C', lambda c: S['C41'])
    s.put(blk + 9, 'E:X', lambda c: S[blk + 6, c-1] * S['B9'])
    # blk+10 Amortization
    s.put(blk + 10, 'C', lambda c: S['C42'])
    s.put(blk + 10, 'D:X', lambda c: (S[blk + 13, c] - S[blk + 15, c]) / (S['B11'] - S['B12']))
    # blk+12 t-g>0
    s.put(blk + 12, 'C', lambda c: S['C44'])
    s.put(blk + 12, 'D:X', lambda c: IF(S[7, c] - S['B12'] > 0, S[7, c] - S['B12'], 0))
    # blk+13
    s.put(blk + 13, 'D:X', lambda c: IF(S[blk + 12, c] == 0, 0, CHOOSE(S[blk + 12, c], *S.cells(blk + 5, 'D', 'AF'))))
    # blk+14 t-m condition
    s.put(blk + 14, 'C', lambda c: S['C46'])
    s.put(blk + 14, 'D:X', lambda c: IF(S[7, c] - S['B11'] > 0, S[7, c] - S['B11'], 0))
    # blk+15
    s.put(blk + 15, 'D:X', lambda c: IF(S[blk + 14, c] == 0, 0, CHOOSE(S[blk + 14, c], *S.cells(blk + 5, 'D', 'AC'), *S.cells(37, 'AD', 'AF'))))
    # blk+17 New domestic MLT borrowing (gross)
    s.put(blk + 17, 'C', lambda c: S['C49'])
    s.put(blk + 17, 'D:X', lambda c: S[blk + 2, c] * S['B5'])
    # blk+18 cumulative
    s.put(blk + 18, 'C', lambda c: S['C50'])
    s.put(blk + 18, 'D', lambda c: S[blk + 17, 'D'])
    s.put(blk + 18, 'E:X', lambda c: SUM(S.rng(blk + 17, 'D', blk + 17, c)))
    # blk+19 Stock of new domestic MLT debt
    s.put(blk + 19, 'C', lambda c: S['C51'])
    s.put(blk + 19, 'D', lambda c: S[blk + 17, 'D'] - S[blk + 23, 'D'])
    s.put(blk + 19, 'E:X', lambda c: S[blk + 19, c-1] + S[blk + 17, c] - S[blk + 23, c])
    # blk+21 Total debt service
    s.put(blk + 21, 'C', lambda c: S['C53'])
    s.put(blk + 21, 'D:X', lambda c: S[blk + 22, c] + S[blk + 23, c])
    # blk+22 Interest
    s.put(blk + 22, 'C', lambda c: S['C54'])
    s.put(blk + 22, 'E:X', lambda c: S[blk + 19, c-1] * S[16, c])
    # blk+23 Amortization
    s.put(blk + 23, 'C', lambda c: S['C55'])
    s.put(blk + 23, 'D:X', lambda c: (S[blk + 26, c] - S[blk + 28, c]) / (S['B18'] - S['B19']))
    # blk+25 t-g>0
    s.put(blk + 25, 'C', lambda c: S['C57'])
    s.put(blk + 25, 'D:X', lambda c: IF(S[7, c] - S['B19'] > 0, S[7, c] - S['B19'], 0))
    # blk+26
    s.put(blk + 26, 'D:X', lambda c: IF(S[blk + 25, c] == 0, 0, CHOOSE(S[blk + 25, c], *S.cells(blk + 18, 'D', 'AF'))))
    # blk+27 t-m condition
    s.put(blk + 27, 'C', lambda c: S['C59'])
    s.put(blk + 27, 'D:X', lambda c: IF(S[7, c] - S['B18'] > 0, S[7, c] - S['B18'], 0))
    # blk+28
    s.put(blk + 28, 'D:X', lambda c: IF(S[blk + 27, c] == 0, 0, CHOOSE(S[blk + 27, c], *S.cells(blk + 18, 'D', 'AC'), *S.cells(37, 'AD', 'AF'))))
    # blk+30 New domestic short-term borrowing (gross; also stock of debt)
    s.put(blk + 30, 'C', lambda c: S['C62'])
    s.put(blk + 30, 'D:X', lambda c: S[blk + 2, c] * S['B6'])
    # blk+31 Interest
    s.put(blk + 31, 'C', lambda c: S['C63'])
    s.put(blk + 31, 'E:X', lambda c: S[blk + 30, c-1] * S[22, c])


def _pv_resfin_pub(s):
    """PV_ResFin_pub"""
    B5E = s.sheet('B5_depreciation_ext')
    BP = s.sheet('Baseline - public')
    C1P = s.sheet('C1_Combined CL')
    C2P = s.sheet('C2_Natural disaster')
    C3E = s.sheet('C3_Commodity prices_ext')
    IN3 = s.sheet('Input 3 - Macro-Debt data(DMX)')
    IN7 = s.sheet('Input 7 - Residual Financing')
    MD = s.sheet('Macro-Debt_Data')
    O11 = s.sheet('Output 1-1 - External DSA')
    S = s.sheet(s.name)
    # 1
    s.cell('B1', lambda: O11['B1'])
    # 2 Assumptions
    s.cell('A2', lambda: TR(s, 1935))
    s.cell('D2', lambda: MD['U5'])
    s.put(2, 'E:BO', lambda c: 1 + S[2, c-1])
    # 3 Shares of marginal debt
    s.cell('A3', lambda: IN7['G8'])
    # 4 External PPG medium and long-term
    s.cell('A4', lambda: IN7['G9'])
    s.cell('B4', lambda: IN7['J9'])
    # 5 Domestic medium and long-term
    s.cell('A5', lambda: IN7['G10'])
    s.cell('B5', lambda: IN7['J10'])
    # 6 Domestic short-term
    s.cell('A6', lambda: IN7['G11'])
    s.cell('B6', lambda: IN7['J11'])
    # 7 Period
    s.cell('C7', lambda: TR(s, 1938))
    s.put(7, 'E:BO', lambda c: S[7, c-1] + 1)
    # 8 First year of projections
    s.cell('A8', lambda: IN7['G13'])
    s.cell('C8', lambda: TR(s, 1939))
    s.cell('D8', lambda: S['D2'])
    s.put(8, 'E:BO', lambda c: S[8, c-1] + 1)
    # 9 Disbursement
    s.cell('A9', lambda: IN7['G14'])
    s.cell('B9', lambda: IN7['J14'])
    s.cell('C9', lambda: TR(s, 1940))
    # 10 Debt stock
    s.cell('A10', lambda: IN7['G15'])
    s.cell('B10', lambda: IN7['J15'])
    s.cell('C10', lambda: TR(s, 1941))
    s.cell('D10', lambda: S['D9'] - S['D11'])
    s.put(10, 'E:BB', lambda c: S[10, c-1] - S[11, c])
    # 11 Amortization
    s.cell('A11', lambda: IN7['G16'])
    s.cell('B11', lambda: IN7['J16'])
    s.cell('C11', lambda: TR(s, 1942))
    s.put(11, 'D:BB', lambda c: IF(S[7, c] - S['D7'] - 1 < S['B12'], 0, IF(S[7, c] - S['D7'] - 1 < S['B11'], S['D9'] / (S['B11'] - S['B12']), 0)))
    # 12 Interest
    s.cell('A12', lambda: IN7['G17'])
    s.cell('B12', lambda: IN7['J17'])
    s.cell('C12', lambda: TR(s, 1943))
    s.put(12, 'E:BB', lambda c: S[10, c-1] * S['B9'])
    # 13 Total debt service
    s.cell('C13', lambda: TR(s, 1944))
    s.put(13, 'D:BB', lambda c: S[11, c] + S[12, c])
    # 14 PV of debt
    s.cell('C14', lambda: TR(s, 1945))
    s.put(14, 'D:BA', lambda c: IF(S['B9'] >= S['B10'], S[10, c], NPV(S['B10'], S.rng(13, c+1, 13, 'BB'))))
    s.cell('BB14', lambda: IF(S['B9'] >= S['B10'], S['BB10'], NPV(S['B10'], S.rng(13, 'BB', 13, 'BC'))))
    # 15 Grant element
    s.cell('C15', lambda: TR(s, 1946))
    s.cell('D15', lambda: (1 - S['D14'] / S['D10']) * 100)
    # 16 Domestic MLT debt
    s.cell('A16', lambda: IN7['G18'])
    s.put(16, 'E:X', lambda c: S[17, c] + S[24, c])
    # 17 Avg. real interest rate on new borrowing
    s.cell('A17', lambda: IN7['G19'])
    s.cell('B17', lambda: IN7['J19'])
    s.put(17, 'E:X', lambda c: S['B17'])
    # 18 Avg. maturity (incl. grace period)
    s.cell('A18', lambda: IN7['G20'])
    s.cell('B18', lambda: ROUNDDOWN(IN7['J20'], 0))
    # 19 Avg. grace period
    s.cell('A19', lambda: IN7['G21'])
    s.cell('B19', lambda: ROUNDDOWN(IN7['J21'], 0))
    # 21 Domestic short-term debt
    s.cell('A21', lambda: IN7['G22'])
    # 22 Avg. interest rate
    s.cell('A22', lambda: TR(s, 1936))
    s.put(22, 'E:X', lambda c: S[23, c] + S[24, c])
    # 23 Avg. real interest rate
    s.cell('A23', lambda: IN7['G23'])
    s.cell('B23', lambda: IN7['J23'])
    s.cell('E23', lambda: S['B23'])
    s.put(23, 'F:X', lambda c: S[23, c-1])
    # 24 Inflation (GDP deflator)
    s.cell('A24', lambda: TR(s, 1937))
    s.put(24, 'E:X', lambda c: MD[109, c+17] / 100)
    # 25 Average interest rate on Domestic Debt
    s.put(25, 'E:X', lambda c: IF(S['B5'] + S['B6'] == 0, S[16, c], S[16, c] * S['B5'] / (S['B5'] + S['B6']) + S['B6'] * S[22, c] / (S['B5'] + S['B6'])))
    # 27 Exchange rate (pa)
    s.put(27, 'D:X', lambda c: IN3[20, c+20])
    # the scenario blocks
    _resfin_block(s, 29, s.sheet('A1_Historical_pub'), s.sheet('A1_historical_ext'))
    _resfin_block(s, 65, s.sheet('B1_GDP_pub'), s.sheet('B1_GDP_ext'))
    _resfin_block(s, 170, s.sheet('B5_depreciation_pub'), s.sheet('B5_depreciation_ext'))
    _resfin_block(s, 206, s.sheet('B6_combo_mkt_pub'), s.sheet('B6_Combo_mkt_ext'))
    _resfin_block(s, 242, s.sheet('B6_combo_non-mkt_pub'), s.sheet('B6_Combo_non-mkt_ext'))
    _resfin_block(s, 344, s.sheet('C3_commodity_prices_pub'), s.sheet('C3_Commodity prices_ext'))
    # the scenario blocks
    _resfin_block_pub(s, 104, s.sheet('B2_PB_mkt_pub'))
    _resfin_block_pub(s, 137, s.sheet('B2_PB_non_mkt_pub'))
    _resfin_block_pub(s, 278, s.sheet('C1_Combined CL'))
    _resfin_block_pub(s, 311, s.sheet('C2_Natural disaster'))
    # differences of the block at row 29 (A1_Historical_pub)
    # 31 New borrowing (gross, in LCU)
    s.cell('C31', lambda: TR(s, 1947))
    # 33 New borrowing under the external DSA (in USD)
    s.drop(33, 'C')
    # 36 New forex borrowing (gross, USD)
    s.cell('C36', lambda: TR(s, 1949))
    # 37 cumulative
    s.cell('C37', lambda: TR(s, 1950))
    # 38 Stock of new forex debt (in USD)
    s.cell('C38', lambda: TR(s, 1951))
    # 39 PV of new forex debt (in USD)
    s.cell('C39', lambda: TR(s, 1952))
    # 40 Total debt service (in USD)
    s.cell('C40', lambda: TR(s, 1953))
    # 41 Interest
    s.cell('C41', lambda: TR(s, 1954))
    # 42 Amortization
    s.cell('C42', lambda: TR(s, 1955))
    # 44 t-g>0
    s.cell('C44', lambda: TR(s, 1957))
    # 46 t-m condition
    s.cell('C46', lambda: TR(s, 1959))
    # 47
    s.put(47, 'D:X', lambda c: IF(S[46, c] == 0, 0, CHOOSE(S[46, c], *S.cells(37, 'D', 'AF'))))
    # 49 New domestic MLT borrowing (gross)
    s.cell('C49', lambda: TR(s, 1962))
    # 50 cumulative
    s.cell('C50', lambda: TR(s, 1963))
    # 51 Stock of new domestic MLT debt
    s.cell('C51', lambda: TR(s, 1964))
    # 53 Total debt service
    s.cell('C53', lambda: TR(s, 1966))
    # 54 Interest
    s.cell('C54', lambda: TR(s, 1967))
    # 55 Amortization
    s.cell('C55', lambda: TR(s, 1968))
    # 57 t-g>0
    s.cell('C57', lambda: TR(s, 1970))
    # 59 t-m condition
    s.cell('C59', lambda: TR(s, 1972))
    # 60
    s.put(60, 'D:X', lambda c: IF(S[59, c] == 0, 0, CHOOSE(S[59, c], *S.cells(50, 'D', 'AC'), *S.cells(37, 'AD', 'AF'))))
    # 62 New domestic short-term borrowing (gross; also stock of debt)
    s.cell('C62', lambda: TR(s, 1975))
    # 63 Interest
    s.cell('C63', lambda: TR(s, 1976))
    # differences of the block at row 170 (B5_depreciation_pub)
    # 174 New borrowing under the external DSA (in USD)
    s.put(174, 'D:X', lambda c: B5E[87, c])
    # differences of the block at row 242 (B6_combo_non-mkt_pub)
    # 254 Interest
    s.put(254, 'E:X', lambda c: S[248, c-1] * S['B9'])
    # 258
    s.put(258, 'D:X', lambda c: IF(S[257, c] == 0, 0, CHOOSE(S[257, c], *S.cells(247, 'D', 'AF'))))
    # 260
    s.put(260, 'D:X', lambda c: IF(S[259, c] == 0, 0, CHOOSE(S[259, c], *S.cells(247, 'D', 'AC'), *S.cells(37, 'AD', 'AF'))))
    # differences of the block at row 344 (C3_commodity_prices_pub)
    # 348 New borrowing under the external DSA (in USD)
    s.put(348, 'D:X', lambda c: C3E[92, c])
    # differences of the block at row 278 (C1_Combined CL)
    # 280 New borrowing (gross, in LCU)
    s.cell('E280', lambda: C1P['F90'] - BP['P78'] + C1P['AA60'] * C1P['F41'] / 100)
    # 293
    s.put(293, 'D:X', lambda c: IF(S[292, c] == 0, 0, CHOOSE(S[292, c], *S.cells(283, 'D', 'AC'), *S.cells(65, 'AD', 'AF'))))
    # 306
    s.put(306, 'D:X', lambda c: IF(S[305, c] == 0, 0, CHOOSE(S[305, c], *S.cells(296, 'D', 'AC'), *S.cells(65, 'AD', 'AF'))))
    # differences of the block at row 311 (C2_Natural disaster)
    # 311 CL1: Natural disaster
    s.drop(311, 'A')
    # 313 New borrowing (gross, in LCU)
    s.cell('D313', lambda: C2P['E91'] - BP['O78'])
    s.cell('E313', lambda: C2P['F91'] - BP['P78'] + C2P['AA62'] * C2P['F41'] / 100)
    s.put(313, 'F:X', lambda c: C2P[91, c+1] - BP[78, c+11])
    # 326
    s.put(326, 'D:X', lambda c: IF(S[325, c] == 0, 0, CHOOSE(S[325, c], *S.cells(316, 'D', 'AC'), *S.cells(109, 'AD', 'AF'))))
    # 339
    s.put(339, 'D:X', lambda c: IF(S[338, c] == 0, 0, CHOOSE(S[338, c], *S.cells(329, 'D', 'AC'), *S.cells(109, 'AD', 'AF'))))


def _addcost_block(s, blk, SP):
    """One scenario block of PV_ResFin-add.int.cost - mkt"""
    BP = s.sheet('Baseline - public')
    IN7 = s.sheet('Input 7 - Residual Financing')
    S = s.sheet(s.name)
    # blk+0 Bounds Test 2: Primary Balance Shock for non-market access countries
    s.put(blk, 'A', lambda c: SP['B2'])
    # blk+2 New borrowing (gross)
    s.put(blk + 2, 'E', lambda c: S['E27'])
    # blk+4 New forex borrowing (gross USD)
    s.put(blk + 4, 'E', lambda c: S['E29'])
    # blk+5 cumulative
    s.put(blk + 5, 'E', lambda c: S['E30'])
    s.put(blk + 5, 'F', lambda c: S[blk + 4, 'F'])
    s.put(blk + 5, 'G:AH', lambda c: SUM(S.rng(blk + 4, 'F', blk + 4, c)))
    # blk+6 Stock of new forex debt (in USD)
    s.put(blk + 6, 'E', lambda c: S['E31'])
    s.put(blk + 6, 'F', lambda c: S[blk + 4, 'F'] - S[blk + 10, 'F'])
    s.put(blk + 6, 'G:AH', lambda c: S[blk + 6, c-1] + S[blk + 4, c] - S[blk + 10, c])
    # blk+7 Interest only =>
    s.put(blk + 7, 'E', lambda c: S['E32'])
    s.put(blk + 7, 'G:AG', lambda c: IF(S[blk + 13, 'B'] > S['B15'], SUM(S.rng(blk + 9, c+1, blk + 9, 'AH')), NPV(S['B15'], S.rng(blk + 9, c+1, blk + 9, 'AH'))))
    s.put(blk + 7, 'AH', lambda c: IF(S[blk + 13, 'B'] > S['B15'], SUM(S.rng(blk + 9, 'AH', blk + 9, 'AI')), NPV(S['B15'], S.rng(blk + 9, 'AH', blk + 9, 'AI'))))
    # blk+8 Assumption
    s.put(blk + 8, 'E', lambda c: S['E33'])
    s.put(blk + 8, 'F:AH', lambda c: S[blk + 9, c] + S[blk + 10, c])
    # blk+9 Interest
    s.put(blk + 9, 'B:C', lambda c: S[22, c+5])
    s.put(blk + 9, 'E', lambda c: S['E34'])
    s.put(blk + 9, 'G:AH', lambda c: S[blk + 6, c-1] * S[blk + 13, 'B'])
    # blk+10 Deviation in PB (ppt)
    s.put(blk + 10, 'B:C', lambda c: SP[17, c+4] - BP[23, c+14])
    s.put(blk + 10, 'E', lambda c: S['E35'])
    s.put(blk + 10, 'F:AH', lambda c: (S[blk + 13, c] - S[blk + 15, c]) / (S['B16'] - S['B17']))
    # blk+12 Avg. nominal interest rate on new borrowing in USD
    s.put(blk + 12, 'A', lambda c: IN7['G14'])
    s.put(blk + 12, 'B:C', lambda c: MIN(S['B7'] / 10000, S['B6'] * S[blk + 10, c] / 100))
    s.put(blk + 12, 'E', lambda c: S['E37'])
    s.put(blk + 12, 'F:AH', lambda c: IF(S[23, c] - S['B17'] > 0, S[23, c] - S['B17'], 0))
    # blk+13 Average of 2025 and 2026
    s.put(blk + 13, 'A', lambda c: CONCATENATE('Average of ', S[blk + 9, 'B'], ' and ', S[blk + 9, 'C']))
    s.put(blk + 13, 'B', lambda c: AVERAGE(S.rng(blk + 12, 'B', blk + 12, 'C')))
    s.put(blk + 13, 'F:AH', lambda c: IF(S[blk + 12, c] == 0, 0, CHOOSE(S[blk + 12, c], *S.cells(blk + 5, 'F', 'AH'))))
    # blk+14 Additional domestic interest rate
    s.put(blk + 14, 'B:C', lambda c: S['B5'] / 10000 * S[blk + 10, c])
    s.put(blk + 14, 'E', lambda c: S['E39'])
    s.put(blk + 14, 'F:AH', lambda c: IF(S[23, c] - S['B16'] > 0, S[23, c] - S['B16'], 0))
    # blk+15 Average of 2025 and 2026
    s.put(blk + 15, 'A', lambda c: CONCATENATE('Average of ', S[blk + 9, 'B'], ' and ', S[blk + 9, 'C']))
    s.put(blk + 15, 'B', lambda c: AVERAGE(S[blk + 14, 'B'], S[blk + 14, 'C']))
    s.put(blk + 15, 'F', lambda c: IF(S[blk + 14, 'F'] == 0, 0, CHOOSE(S[blk + 14, 'F'], *S.cells(blk + 5, 'F', 'AE'), X('#REF!'), X('#REF!'), X('#REF!'))))
    s.put(blk + 15, 'G:AH', lambda c: IF(S[blk + 14, c] == 0, 0, CHOOSE(S[blk + 14, c], *S.cells(blk + 5, 'F', 'AH'))))
    # blk+17 New domestic MLT borrowing (gross)
    s.put(blk + 17, 'E', lambda c: S['E42'])
    # blk+18 cumulative
    s.put(blk + 18, 'E', lambda c: S['E43'])
    s.put(blk + 18, 'F', lambda c: S[blk + 17, 'F'])
    s.put(blk + 18, 'G:Z', lambda c: SUM(S.rng(blk + 17, 'F', blk + 17, c)))
    # blk+19 Stock of new domestic MLT debt
    s.put(blk + 19, 'E', lambda c: S['E44'])
    s.put(blk + 19, 'F', lambda c: S[blk + 17, 'F'] - S[blk + 23, 'F'])
    s.put(blk + 19, 'G:Z', lambda c: S[blk + 19, c-1] + S[blk + 17, c] - S[blk + 23, c])
    # blk+21 Total debt service
    s.put(blk + 21, 'E', lambda c: S['E46'])
    s.put(blk + 21, 'F:Z', lambda c: S[blk + 22, c] + S[blk + 23, c])
    # blk+22 Interest
    s.put(blk + 22, 'E', lambda c: S['E47'])
    s.put(blk + 22, 'G:Z', lambda c: S[blk + 19, c-1] * S[blk + 15, 'B'])
    # blk+23 Amortization
    s.put(blk + 23, 'E', lambda c: S['E48'])
    s.put(blk + 23, 'F:Z', lambda c: (S[blk + 26, c] - S[blk + 28, c]) / (S['B19'] - S['B20']))
    # blk+25 t-g>0
    s.put(blk + 25, 'E', lambda c: S['E50'])
    s.put(blk + 25, 'F:Z', lambda c: IF(S[23, c] - S['B20'] > 0, S[23, c] - S['B20'], 0))
    # blk+26
    s.put(blk + 26, 'F:Z', lambda c: IF(S[blk + 25, c] == 0, 0, CHOOSE(S[blk + 25, c], *S.cells(blk + 18, 'F', 'AH'))))
    # blk+27 t-m condition
    s.put(blk + 27, 'E', lambda c: S['E52'])
    s.put(blk + 27, 'F:Z', lambda c: IF(S[23, c] - S['B19'] > 0, S[23, c] - S['B19'], 0))
    # blk+28
    s.put(blk + 28, 'F:Z', lambda c: IF(S[blk + 27, c] == 0, 0, CHOOSE(S[blk + 27, c], *S.cells(blk + 18, 'F', 'AE'), *S.cells(blk + 5, 'AF', 'AH'))))
    # blk+30 New domestic short-term borrowing (gross; also stock of debt)
    s.put(blk + 30, 'E', lambda c: S['E55'])
    s.put(blk + 30, 'F', lambda c: S[blk + 2, 'F'] * S['B12'])
    # blk+31 Interest
    s.put(blk + 31, 'E', lambda c: S['E56'])
    s.put(blk + 31, 'G:Z', lambda c: S[blk + 30, c-1] * S[blk + 15, 'B'])


def _pv_resfin_add_int_cost_mkt(s):
    """PV_ResFin-add.int.cost - mkt"""
    IN7 = s.sheet('Input 7 - Residual Financing')
    MD = s.sheet('Macro-Debt_Data')
    O11 = s.sheet('Output 1-1 - External DSA')
    PVR = s.sheet('PV_ResFin_pub')
    START = s.sheet('START')
    STD = s.sheet('Input 6(optional)-Standard Test')
    S = s.sheet(s.name)
    # 1
    s.cell('A1', lambda: O11['B1'])
    # 4 Assumptions
    s.cell('A4', lambda: IF(START['L10'] == 'English', S['A162'], IF(START['L10'] == 'French', S['A216'], IF(START['L10'] == 'Portuguese', S['A270'], S['A324']))))
    # 5 bps/ppt
    s.cell('B5', lambda: STD['H21'])
    # 7 bps/ppt
    s.cell('D7', lambda: STD['H22'])
    # 9 Shares of marginal debt
    s.cell('A9', lambda: IN7['G8'])
    # 10 External PPG medium and long-term
    s.cell('A10', lambda: IN7['G9'])
    s.cell('B10', lambda: IN7['J9'])
    # 11 Domestic medium and long-term
    s.cell('A11', lambda: IN7['G10'])
    s.cell('B11', lambda: IN7['J10'])
    # 12 Domestic short-term
    s.cell('A12', lambda: IN7['G11'])
    s.cell('B12', lambda: IN7['J11'])
    # 14 External MLT debt
    s.cell('A14', lambda: IN7['G13'])
    # 15 USD Discount rate
    s.cell('A15', lambda: IN7['G15'])
    s.cell('B15', lambda: s.name_('Discount_Rate_GE'))
    # 16 Avg. maturity (incl. grace period)
    s.cell('A16', lambda: IN7['G16'])
    s.cell('B16', lambda: IN7['J16'])
    # 17 Avg. grace period
    s.cell('A17', lambda: IN7['G17'])
    s.cell('B17', lambda: IN7['J17'])
    # 18 Domestic MLT debt
    s.cell('A18', lambda: IN7['G18'])
    # 19 Avg. maturity (incl. grace period)
    s.cell('A19', lambda: IN7['G20'])
    s.cell('B19', lambda: ROUNDDOWN(IN7['J20'], 0))
    # 20 Avg. grace period
    s.cell('A20', lambda: IN7['G21'])
    s.cell('B20', lambda: ROUNDDOWN(IN7['J21'], 0))
    s.cell('AF20', lambda: 1 + S['AE22'])
    s.put(20, 'AG:BQ', lambda c: 1 + S[20, c-1])
    # 22 Year
    s.cell('F22', lambda: MD['U5'])
    s.put(22, 'G:AE', lambda c: 1 + S[22, c-1])
    # 23 Period
    s.cell('E23', lambda: IF(START['L10'] == 'English', S['E162'], IF(START['L10'] == 'French', S['E216'], IF(START['L10'] == 'Portuguese', S['E270'], S['E324']))))
    s.put(23, 'G:BQ', lambda c: S[23, c-1] + 1)
    # the scenario blocks
    _addcost_block(s, 25, s.sheet('B2_PB_mkt_pub'))
    _addcost_block(s, 58, s.sheet('B2_PB_non_mkt_pub'))
    _addcost_block(s, 91, s.sheet('B6_combo_mkt_pub'))
    _addcost_block(s, 124, s.sheet('B6_combo_non-mkt_pub'))
    # differences of the block at row 25 (B2_PB_mkt_pub)
    # 27 New borrowing (gross)
    s.cell('E27', lambda: IF(START['L10'] == 'English', S['E183'], IF(START['L10'] == 'French', S['E237'], IF(START['L10'] == 'Portuguese', S['E291'], S['E345']))))
    s.put(27, 'G:H', lambda c: PVR[106, c-2])
    # 29 New forex borrowing (gross USD)
    s.cell('E29', lambda: IF(START['L10'] == 'English', S['E185'], IF(START['L10'] == 'French', S['E239'], IF(START['L10'] == 'Portuguese', S['E293'], S['E347']))))
    s.put(29, 'G:H', lambda c: PVR[108, c-2])
    # 30 cumulative
    s.cell('E30', lambda: IF(START['L10'] == 'English', S['E186'], IF(START['L10'] == 'French', S['E240'], IF(START['L10'] == 'Portuguese', S['E294'], S['E348']))))
    # 31 Stock of new forex debt (in USD)
    s.cell('E31', lambda: IF(START['L10'] == 'English', S['E187'], IF(START['L10'] == 'French', S['E241'], IF(START['L10'] == 'Portuguese', S['E295'], S['E349']))))
    # 32 Interest only =>
    s.cell('E32', lambda: IF(START['L10'] == 'English', S['E188'], IF(START['L10'] == 'French', S['E242'], IF(START['L10'] == 'Portuguese', S['E296'], S['E350']))))
    # 33 Assumption
    s.cell('E33', lambda: IF(START['L10'] == 'English', S['E189'], IF(START['L10'] == 'French', S['E243'], IF(START['L10'] == 'Portuguese', S['E297'], S['E351']))))
    # 34 Interest
    s.cell('E34', lambda: IF(START['L10'] == 'English', S['E190'], IF(START['L10'] == 'French', S['E244'], IF(START['L10'] == 'Portuguese', S['E298'], S['E352']))))
    # 35 Deviation in PB (ppt)
    s.cell('E35', lambda: IF(START['L10'] == 'English', S['E191'], IF(START['L10'] == 'French', S['E245'], IF(START['L10'] == 'Portuguese', S['E299'], S['E353']))))
    # 37 Avg. nominal interest rate on new borrowing in USD
    s.cell('E37', lambda: IF(START['L10'] == 'English', S['E193'], IF(START['L10'] == 'French', S['E247'], IF(START['L10'] == 'Portuguese', S['E301'], S['E355']))))
    # 39 Additional domestic interest rate
    s.cell('E39', lambda: IF(START['L10'] == 'English', S['E195'], IF(START['L10'] == 'French', S['E249'], IF(START['L10'] == 'Portuguese', S['E303'], S['E357']))))
    # 42 New domestic MLT borrowing (gross)
    s.cell('E42', lambda: IF(START['L10'] == 'English', S['E198'], IF(START['L10'] == 'French', S['E252'], IF(START['L10'] == 'Portuguese', S['E306'], S['E360']))))
    s.put(42, 'G:H', lambda c: PVR[121, c-2])
    # 43 cumulative
    s.cell('E43', lambda: IF(START['L10'] == 'English', S['E199'], IF(START['L10'] == 'French', S['E253'], IF(START['L10'] == 'Portuguese', S['E307'], S['E361']))))
    # 44 Stock of new domestic MLT debt
    s.cell('E44', lambda: IF(START['L10'] == 'English', S['E200'], IF(START['L10'] == 'French', S['E254'], IF(START['L10'] == 'Portuguese', S['E308'], S['E362']))))
    # 46 Total debt service
    s.cell('E46', lambda: IF(START['L10'] == 'English', S['E202'], IF(START['L10'] == 'French', S['E256'], IF(START['L10'] == 'Portuguese', S['E310'], S['E364']))))
    # 47 Interest
    s.cell('E47', lambda: IF(START['L10'] == 'English', S['E203'], IF(START['L10'] == 'French', S['E257'], IF(START['L10'] == 'Portuguese', S['E311'], S['E365']))))
    # 48 Amortization
    s.cell('E48', lambda: IF(START['L10'] == 'English', S['E204'], IF(START['L10'] == 'French', S['E258'], IF(START['L10'] == 'Portuguese', S['E312'], S['E366']))))
    # 50 t-g>0
    s.cell('E50', lambda: IF(START['L10'] == 'English', S['E206'], IF(START['L10'] == 'French', S['E260'], IF(START['L10'] == 'Portuguese', S['E314'], S['E368']))))
    # 52 t-m condition
    s.cell('E52', lambda: IF(START['L10'] == 'English', S['E208'], IF(START['L10'] == 'French', S['E262'], IF(START['L10'] == 'Portuguese', S['E316'], S['E370']))))
    # 55 New domestic short-term borrowing (gross; also stock of debt)
    s.cell('E55', lambda: IF(START['L10'] == 'English', S['E211'], IF(START['L10'] == 'French', S['E265'], IF(START['L10'] == 'Portuguese', S['E319'], S['E373']))))
    s.put(55, 'G:H', lambda c: PVR[134, c-2])
    # 56 Interest
    s.cell('E56', lambda: IF(START['L10'] == 'English', S['E212'], IF(START['L10'] == 'French', S['E266'], IF(START['L10'] == 'Portuguese', S['E320'], S['E374']))))
    # differences of the block at row 58 (B2_PB_non_mkt_pub)
    # 60 New borrowing (gross)
    s.put(60, 'G:H', lambda c: PVR[139, c-2])
    # 62 New forex borrowing (gross USD)
    s.put(62, 'G:H', lambda c: PVR[141, c-2])
    # 70 Avg. nominal interest rate on new borrowing in USD
    s.drop(70, 'B:C')
    # 75 New domestic MLT borrowing (gross)
    s.put(75, 'G:H', lambda c: PVR[154, c-2])
    # 88 New domestic short-term borrowing (gross; also stock of debt)
    s.put(88, 'G:H', lambda c: PVR[167, c-2])
    # differences of the block at row 91 (B6_combo_mkt_pub)
    # 93 New borrowing (gross)
    s.put(93, 'G:H', lambda c: PVR[208, c-2])
    # 95 New forex borrowing (gross USD)
    s.put(95, 'G:H', lambda c: PVR[210, c-2])
    # 108 New domestic MLT borrowing (gross)
    s.put(108, 'G:H', lambda c: PVR[226, c-2])
    # 121 New domestic short-term borrowing (gross; also stock of debt)
    s.put(121, 'G:H', lambda c: PVR[239, c-2])
    # differences of the block at row 124 (B6_combo_non-mkt_pub)
    # 126 New borrowing (gross)
    s.put(126, 'G:H', lambda c: PVR[244, c-2])
    # 128 New forex borrowing (gross USD)
    s.put(128, 'G:H', lambda c: PVR[249, c-2])
    # 136 Avg. nominal interest rate on new borrowing in USD
    s.drop(136, 'B:C')
    # 141 New domestic MLT borrowing (gross)
    s.put(141, 'G:H', lambda c: PVR[262, c-2])
    # 154 New domestic short-term borrowing (gross; also stock of debt)
    s.put(154, 'G:H', lambda c: PVR[275, c-2])


def _pvstress_block(s, blk, SE):
    """One scenario block of PV Stress"""
    S = s.sheet(s.name)
    # blk+0 Bounds Test 1: Real GDP Growth Shock
    s.put(blk, 'A', lambda c: SE['B3'])
    # blk+2 New forex borrowing (gross, USD)
    s.put(blk + 2, 'C', lambda c: S['C12'])
    s.put(blk + 2, 'D:X', lambda c: SE[86, c])
    # blk+3 cumulative
    s.put(blk + 3, 'C', lambda c: S['C13'])
    s.put(blk + 3, 'D', lambda c: S[blk + 2, 'D'])
    s.put(blk + 3, 'E:X', lambda c: SUM(S.rng(blk + 2, 'D', blk + 2, c)))
    # blk+4 Stock of new forex debt (in USD)
    s.put(blk + 4, 'C', lambda c: S['C14'])
    s.put(blk + 4, 'D', lambda c: S[blk + 2, 'D'] - S[blk + 9, 'D'])
    s.put(blk + 4, 'E:X', lambda c: S[blk + 4, c-1] + S[blk + 2, c] - S[blk + 9, c])
    # blk+5 PV of new forex debt (in USD)
    s.put(blk + 5, 'C', lambda c: S['C15'])
    s.put(blk + 5, 'D', lambda c: IF(S['B6'] >= S['B7'], S[blk + 2, 'D'], S[blk + 2, 'D'] * S['D9'] / 100))
    s.put(blk + 5, 'E:X', lambda c: IF(S['B6'] >= S['B7'], S[blk + 5, c-1] - S[blk + 9, c] + S[blk + 2, c], S[blk + 5, c-1] * (1 + S['B7']) - S[blk + 7, c] + S[blk + 2, c] * S['D9'] / 100))
    # blk+7 Total debt service (in USD)
    s.put(blk + 7, 'C', lambda c: S['C17'])
    s.put(blk + 7, 'D:X', lambda c: S[blk + 8, c] + S[blk + 9, c])
    # blk+8 Interest
    s.put(blk + 8, 'C', lambda c: S['C18'])
    s.put(blk + 8, 'E:X', lambda c: S[blk + 4, c-1] * S['B6'])
    # blk+9 Amortization
    s.put(blk + 9, 'C', lambda c: S['C19'])
    s.put(blk + 9, 'D:X', lambda c: (S[blk + 12, c] - S[blk + 14, c]) / (S['B8'] - S['B9']))
    # blk+11 t-g>0
    s.put(blk + 11, 'C', lambda c: S['C21'])
    s.put(blk + 11, 'D:X', lambda c: IF(S[2, c] - S['B9'] > 0, S[2, c] - S['B9'], 0))
    # blk+12
    s.put(blk + 12, 'D:X', lambda c: IF(S[blk + 11, c] == 0, 0, CHOOSE(S[blk + 11, c], *S.cells(blk + 3, 'D', 'AF'))))
    # blk+13 t-m condition
    s.put(blk + 13, 'C', lambda c: S['C23'])
    s.put(blk + 13, 'D:X', lambda c: IF(S[2, c] - S['B8'] > 0, S[2, c] - S['B8'], 0))
    # blk+14
    s.put(blk + 14, 'D:X', lambda c: IF(S[blk + 13, c] == 0, 0, CHOOSE(S[blk + 13, c], *S.cells(blk + 3, 'D', 'X'))))


def _pv_stress(s):
    """PV Stress"""
    A1E = s.sheet('A1_historical_ext')
    B5E = s.sheet('B5_depreciation_ext')
    C3E = s.sheet('C3_Commodity prices_ext')
    C4E = s.sheet('C4_Market_financing')
    EDD = s.sheet('Ext_Debt_Data')
    IN7 = s.sheet('Input 7 - Residual Financing')
    MD = s.sheet('Macro-Debt_Data')
    PVB = s.sheet('PV_Base')
    PVR = s.sheet('PV_ResFin_pub')
    S = s.sheet(s.name)
    # 2 Period
    s.cell('C2', lambda: PVR['C7'])
    s.put(2, 'D:BB', lambda c: PVB[49, c])
    # 3 First year of projections
    s.cell('C3', lambda: PVR['C8'])
    s.cell('D3', lambda: MD['U5'])
    s.put(3, 'E:BB', lambda c: S[3, c-1] + 1)
    # 4 Disbursement
    s.cell('A4', lambda: A1E['B3'])
    s.cell('C4', lambda: PVR['C9'])
    # 5 Debt stock
    s.cell('C5', lambda: PVR['C10'])
    s.cell('D5', lambda: S['D4'] - S['D6'])
    s.put(5, 'E:BB', lambda c: S[5, c-1] - S[6, c])
    # 6 Amortization
    s.cell('A6', lambda: EDD['A131'])
    s.cell('B6', lambda: IN7['E14'])
    s.cell('C6', lambda: PVR['C11'])
    s.put(6, 'D:BB', lambda c: IF(S[2, c] - S['D2'] - 1 < S['B9'], 0, IF(S[2, c] - S['D2'] - 1 < S['B8'], S['D4'] / (S['B8'] - S['B9']), 0)))
    # 7 Interest
    s.cell('A7', lambda: IN7['G15'])
    s.cell('B7', lambda: IN7['E15'])
    s.cell('C7', lambda: PVR['C12'])
    s.put(7, 'E:BB', lambda c: S[5, c-1] * S['B6'])
    # 8 Total debt service
    s.cell('A8', lambda: EDD['A133'])
    s.cell('B8', lambda: IN7['E16'])
    s.cell('C8', lambda: PVR['C13'])
    s.put(8, 'D:BB', lambda c: S[6, c] + S[7, c])
    # 9 PV of debt
    s.cell('A9', lambda: EDD['A132'])
    s.cell('B9', lambda: IN7['E17'])
    s.cell('C9', lambda: PVR['C14'])
    s.put(9, 'D:BA', lambda c: IF(S['B6'] >= S['B7'], S[5, c], NPV(S['B7'], S.rng(8, c+1, 8, 'BB'))))
    s.cell('BB9', lambda: IF(S['B6'] >= S['B7'], S['BB5'], NPV(S['B7'], S.rng(8, 'BB', 8, 'BB'))))
    # 145 Tailored stress test 4: Market Financing Stress Test
    s.cell('A145', lambda: C4E['B3'])
    # 147 New forex borrowing (gross, USD)
    s.cell('A147', lambda: S['A6'])
    s.cell('B147', lambda: C4E['K41'])
    s.cell('C147', lambda: S['C12'])
    s.put(147, 'E:G', lambda c: C4E[73, c])
    # 148 cumulative
    s.put(148, 'A:B', lambda c: S[7, c])
    s.cell('C148', lambda: S['C13'])
    s.cell('D148', lambda: S['D147'])
    s.put(148, 'E:X', lambda c: SUM(S.rng(147, 'D', 147, c)))
    # 149 Stock of new forex debt (in USD)
    s.cell('A149', lambda: S['A8'])
    s.cell('B149', lambda: C4E['H41'])
    s.cell('C149', lambda: S['C14'])
    s.cell('D149', lambda: S['D147'] - S['D154'])
    s.put(149, 'E:X', lambda c: S[149, c-1] + S[147, c] - S[154, c])
    # 150 PV of new forex debt (in USD)
    s.cell('A150', lambda: S['A9'])
    s.cell('B150', lambda: C4E['I41'])
    s.cell('C150', lambda: S['C15'])
    s.cell('D150', lambda: IF(S['B147'] >= S['B148'], S['D147'], S['D147'] * S['D9'] / 100))
    s.put(150, 'E:X', lambda c: IF(S['B147'] >= S['B148'], S[150, c-1] - S[154, c] + S[147, c], S[150, c-1] * (1 + S['B7']) - S[152, c] + S[147, c] * S['D9'] / 100))
    # 152 Total debt service (in USD)
    s.cell('C152', lambda: S['C17'])
    s.put(152, 'D:X', lambda c: S[153, c] + S[154, c])
    # 153 Interest
    s.cell('C153', lambda: S['C18'])
    s.put(153, 'E:X', lambda c: S[149, c-1] * S['B147'])
    # 154 Amortization
    s.cell('C154', lambda: S['C19'])
    s.put(154, 'D:X', lambda c: (S[157, c] - S[159, c]) / (S['B149'] - S['B150']))
    # 156 t-g>0
    s.cell('C156', lambda: S['C21'])
    s.put(156, 'D:X', lambda c: IF(S[2, c] - S['B150'] > 0, S[2, c] - S['B150'], 0))
    # 157
    s.put(157, 'D:X', lambda c: IF(S[156, c] == 0, 0, CHOOSE(S[156, c], *S.cells(148, 'D', 'AF'))))
    # 158 t-m condition
    s.cell('C158', lambda: S['C23'])
    s.put(158, 'D:X', lambda c: IF(S[2, c] - S['B149'] > 0, S[2, c] - S['B149'], 0))
    # 159
    s.put(159, 'D:X', lambda c: IF(S[158, c] == 0, 0, CHOOSE(S[158, c], *S.cells(148, 'D', 'X'))))
    # 161 New forex borrowing (gross, USD)
    s.cell('C161', lambda: S['C12'])
    s.put(161, 'H:X', lambda c: C4E[73, c])
    # 162 cumulative
    s.cell('C162', lambda: S['C13'])
    s.cell('D162', lambda: S['D161'])
    s.put(162, 'E:X', lambda c: SUM(S.rng(161, 'D', 161, c)))
    # 163 Stock of new forex debt (in USD)
    s.cell('C163', lambda: S['C14'])
    s.cell('D163', lambda: S['D161'] - S['D168'])
    s.put(163, 'E:X', lambda c: S[163, c-1] + S[161, c] - S[168, c])
    # 164 PV of new forex debt (in USD)
    s.cell('C164', lambda: S['C15'])
    s.cell('D164', lambda: IF(S['B6'] >= S['B7'], S['D161'], S['D161'] * S['D9'] / 100))
    s.put(164, 'E:X', lambda c: IF(S['B6'] >= S['B7'], S[164, c-1] - S[168, c] + S[161, c], S[164, c-1] * (1 + S['B7']) - S[166, c] + S[161, c] * S['D9'] / 100))
    # 166 Total debt service (in USD)
    s.cell('C166', lambda: S['C17'])
    s.put(166, 'D:X', lambda c: S[167, c] + S[168, c])
    # 167 Interest
    s.cell('C167', lambda: S['C18'])
    s.put(167, 'E:X', lambda c: S[163, c-1] * S['B6'])
    # 168 Amortization
    s.cell('C168', lambda: S['C19'])
    s.put(168, 'D:X', lambda c: IF(S['B8'] - S['B9'] == 0, 0, (S[171, c] - S[173, c]) / (S['B8'] - S['B9'])))
    # 170 t-g>0
    s.cell('C170', lambda: S['C21'])
    s.put(170, 'D:X', lambda c: IF(S[2, c] - S['B9'] > 0, S[2, c] - S['B9'], 0))
    # 171
    s.put(171, 'D:X', lambda c: IF(S[170, c] == 0, 0, CHOOSE(S[170, c], *S.cells(162, 'D', 'AF'))))
    # 172 t-m condition
    s.cell('C172', lambda: S['C23'])
    s.put(172, 'D:X', lambda c: IF(S[2, c] - S['B8'] > 0, S[2, c] - S['B8'], 0))
    # 173
    s.put(173, 'D:X', lambda c: IF(S[172, c] == 0, 0, CHOOSE(S[172, c], *S.cells(162, 'D', 'X'))))
    # the scenario blocks
    _pvstress_block(s, 10, s.sheet('A1_historical_ext'))
    _pvstress_block(s, 27, s.sheet('B1_GDP_ext'))
    _pvstress_block(s, 44, s.sheet('B3_Exports_ext'))
    _pvstress_block(s, 61, s.sheet('B4_other flows_ext'))
    _pvstress_block(s, 78, s.sheet('B6_Combo_mkt_ext'))
    _pvstress_block(s, 95, s.sheet('B6_Combo_non-mkt_ext'))
    _pvstress_block(s, 112, s.sheet('B5_depreciation_ext'))
    _pvstress_block(s, 129, s.sheet('C3_Commodity prices_ext'))
    # differences of the block at row 10 (A1_historical_ext)
    # 10 Grant element
    s.drop(10, 'A')
    s.cell('C10', lambda: PVR['C15'])
    s.put(10, 'D:BB', lambda c: IF(S[9, c] == 0, 0, (1 - S[9, c] / S[5, c]) * 100))
    # 12 New forex borrowing (gross, USD)
    s.cell('C12', lambda: PVR['C36'])
    # 13 cumulative
    s.cell('C13', lambda: PVR['C37'])
    # 14 Stock of new forex debt (in USD)
    s.cell('C14', lambda: PVR['C38'])
    # 15 PV of new forex debt (in USD)
    s.cell('C15', lambda: PVR['C39'])
    # 17 Total debt service (in USD)
    s.cell('C17', lambda: PVR['C40'])
    # 18 Interest
    s.cell('C18', lambda: PVR['C41'])
    # 19 Amortization
    s.cell('C19', lambda: PVR['C42'])
    # 21 t-g>0
    s.drop(21, 'C')
    # 23 t-m condition
    s.cell('C23', lambda: PVR['C46'])
    # differences of the block at row 112 (B5_depreciation_ext)
    # 114 New forex borrowing (gross, USD)
    s.put(114, 'D:X', lambda c: B5E[87, c])
    # differences of the block at row 129 (C3_Commodity prices_ext)
    # 131 New forex borrowing (gross, USD)
    s.put(131, 'D:X', lambda c: C3E[92, c])


RULES = {
    'PV_ResFin_pub': _pv_resfin_pub,
    'PV_ResFin-add.int.cost - mkt': _pv_resfin_add_int_cost_mkt,
    'PV Stress': _pv_stress,
}



def compute(book, sheet):
    s = Calc(book, sheet)
    RULES[sheet](s)
    s.run()
