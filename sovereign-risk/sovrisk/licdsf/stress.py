"""LIC DSF stress-test sheets.

Public debt (one structure, _public_stress): A1 historical averages, B1 real GDP growth, B2 primary balance
(market / non-market access), B5 exchange rate, B6 combined shock (market / non-market access), C1 contingent
liabilities, C2 natural disaster, C3 commodity prices. Each sheet recomputes the public debt path of the baseline
under its shocked growth, primary balance, interest and exchange rate assumptions, with the residual financing it
needs taken from its own block of PV_ResFin_pub (rows blk...).

External debt (one structure, _external_stress): A1 historical averages, B1 real GDP growth, B3 exports, B4 other
flows, B5 depreciation, B6 combined shock (market / non-market access), C3 commodity prices, C4 market financing.
Each recomputes the external debt path, its PV and the debt-burden ratios, with new borrowing from its own block of
PV Stress.

The shared structure holds the formula each cell has on most sheets; each sheet's function then lists only its
own differences (other formulas, or s.drop for cells that are inputs or blank on that sheet).
"""
from .baseline import Calc, X, TR, IF, AND, CHOOSE, ISNUMBER, ISTEXT, SUM, AVERAGE, MIN, MAX, STDEV, NPV, ROUNDDOWN, CONCATENATE, TEXT  # noqa

SHEETS = ['A1_Historical_pub', 'B1_GDP_pub', 'B2_PB_mkt_pub', 'B2_PB_non_mkt_pub', 'B5_depreciation_pub', 'B6_combo_mkt_pub', 'B6_combo_non-mkt_pub', 'C1_Combined CL', 'C2_Natural disaster', 'C3_commodity_prices_pub', 'A1_historical_ext', 'B1_GDP_ext', 'B3_Exports_ext', 'B4_other flows_ext', 'B5_depreciation_ext', 'B6_Combo_mkt_ext', 'B6_Combo_non-mkt_ext', 'C3_Commodity prices_ext', 'C4_Market_financing']

QUIRKS = [
    "Public stress sheets, C19 (grants, first year): tests Macro-Debt_Data!S46 but divides the next year's T46 by this year's GDP.",
    "C3_commodity_prices_pub!E20:Y20 (primary expenditure) divides by B1_GDP_pub's nominal GDP (row 41), not the sheet's own; B1_GDP_pub writes the same reference to itself by name.",
    "Public stress sheets F31 (other debt-creating flows): the else branch is 0*'Baseline - public'!P52/F41 where the other years use a plain 0 (same value unless that cell is an error).",
    'B6_combo_non-mkt_pub!B58 and B5_depreciation_ext!B73 (translated labels) point at deleted translation cells; B58 shows 0 (blank English text) and B73 #REF!.',
    'C4_Market_financing!E98 = IF(E97>E96,1,""): E96 and E97 differ only in the 16th digit, which Excel treats as equal, so the cell is "".',
    "The shared structure's references to the PV sheets (PV_ResFin_pub, PV Stress) are relative to each scenario's block; C4_Market_financing uses its own PV_stress_com / PV_baseline_com layout and overrides them.",
]


def _public_stress(s, blk):
    """Shared structure of the public-debt stress sheets"""
    A1P = s.sheet('A1_Historical_pub')
    B1P = s.sheet('B1_GDP_pub')
    BP = s.sheet('Baseline - public')
    MD = s.sheet('Macro-Debt_Data')
    PVR = s.sheet('PV_ResFin_pub')
    S = s.sheet(s.name)
    # column B of these rows repeats the same cells of A1_Historical_pub
    s.same(A1P, 'B', [3, 11, 12, 13, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 34, 36, 37,
                      39, 41, 42, 43, 44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 59, 78, 79, 80, 81, 82, 83,
                      84, 85, 86, 87, 88, 90, 91, 93, 94, 95])
    # 2 Bounds Test 1: Real GDP Growth Shock
    s.cell('B2', lambda: TR(s, 1771))
    # 3 (In percent of GDP, unless otherwise indicated)
    # 6 First year of proj.
    s.cell('E6', lambda: BP['O6'])
    # 7
    s.cell('C7', lambda: MD['S5'])
    s.put(7, 'D:Y', lambda c: S[7, c-1] + 1)
    # 9 I. Baseline Medium Term Projections
    s.cell('B9', lambda: A1P.ii(9, 'B', 9, 'I', 9, 'B'))
    # 11 Public sector debt 1/
    s.put(11, 'C:E', lambda c: IF(ISNUMBER(MD[80, c+16] / (MD[56, c+16] * MD[60, c+16])), 100 * MD[80, c+16] / (MD[56, c+16] * MD[60, c+16]), '.'))
    s.put(11, 'F:Y', lambda c: S[11, c-1] + S[15, c])
    # 12 of which: external debt
    s.cell('C12', lambda: IF(ISNUMBER(MD['S83']), MD['S83'] / S['C41'] * 100, '...'))
    s.put(12, 'D:Y', lambda c: S[82, c] / S[41, c] * 100)
    # 13 PV of total public debt
    s.put(13, 'C:Y', lambda c: (S[91, c] + S[80, c]) / S[41, c] * 100)
    # 15 Change in public sector debt
    s.put(15, 'D:Y', lambda c: S[16, c] + S[32, c])
    # 16 Identified debt-creating flows
    s.put(16, 'D:Y', lambda c: S[17, c] + S[21, c] + S[27, c])
    # 17 Primary deficit
    s.put(17, 'C:Y', lambda c: S[20, c] - S[18, c])
    # 18 Revenue and grants
    s.put(18, 'C:E', lambda c: IF(ISNUMBER(MD[45, c+16] / S[41, c]), 100 * MD[45, c+16] / S[41, c], '.'))
    s.put(18, 'F:Y', lambda c: BP[24, c+10] - BP[25, c+10] + S[19, c])
    # 19 of which: grants
    s.put(19, 'C:D', lambda c: IF(ISNUMBER(MD[46, c+16]), MD['T46'] / S[41, c] * 100, '...'))
    s.put(19, 'E:Y', lambda c: IF(ISNUMBER(MD[46, c+16]), MD[46, c+16] / S[41, c] * 100, '...'))
    # 20 Primary (noninterest) expenditure
    s.cell('C20', lambda: IF(ISNUMBER((MD['S48'] - MD['S49']) / S['C41']), 100 * ((MD['S48'] - MD['S49']) / S['C41']), '.'))
    s.cell('D20', lambda: BP['N26'])
    s.put(20, 'E:Y', lambda c: BP[26, c+10] * BP[52, c+10] / S[41, c])
    # 21 Automatic debt dynamics
    s.put(21, 'D:Y', lambda c: S[22, c] + S[25, c])
    # 22 Contribution from interest rate/growth differential
    s.put(22, 'D:Y', lambda c: S[23, c] + S[24, c])
    # 23 of which: contribution from average real interest rate
    s.put(23, 'D:Y', lambda c: S[46, c] / 100 * S[11, c-1] / S[26, c])
    # 24 of which: contribution from real GDP growth
    s.put(24, 'D:Y', lambda c: -(S[42, c] / 100) * (S[11, c-1] / S[26, c]))
    # 25 Contribution from real exchange rate depreciation
    s.put(25, 'D:Y', lambda c: S[53, c] / 100 * S[12, c-1] * (1 + S[48, c] / 100) / S[26, c])
    # 26 Denominator = 1+g
    s.put(26, 'D:Y', lambda c: 1 + S[42, c] / 100)
    # 27 Other identified debt-creating flows
    s.put(27, 'C:Y', lambda c: SUM(S.rng(28, c, 31, c)))
    # 28 Privatization receipts (negative)
    s.put(28, 'C:Y', lambda c: BP[34, c+10] * BP[52, c+10] / S[41, c])
    # 29 Recognition of contingent liabilities (e.g., bank recapitalization)
    s.put(29, 'C:Y', lambda c: IF(ISNUMBER(BP[35, c+10]), BP[35, c+10] * BP[52, c+10] / S[41, c], 0))
    # 30 Debt relief (HIPC and other)
    s.put(30, 'C:Y', lambda c: BP[36, c+10] * BP[52, c+10] / S[41, c])
    # 31 Other debt creating or reducing flow (please specify)
    s.put(31, 'C:E', lambda c: IF(ISNUMBER(BP[37, c+10]), BP[37, c+10] * BP[52, c+10] / S[41, c], 0))
    s.cell('F31', lambda: IF(ISNUMBER(BP['P37']), BP['P37'] * BP['P52'] / S['F41'], 0 * BP['P52'] / S['F41']))
    s.put(31, 'G:Y', lambda c: IF(ISNUMBER(BP[37, c+10]), BP[37, c+10] * BP[52, c+10] / S[41, c], 0))
    # 32 Residual
    s.put(32, 'C:Y', lambda c: BP[38, c+10] * BP[52, c+10] / S[41, c])
    # 34 Public sector debt-to-revenue-and-grants ratio (in percent)
    s.put(34, 'C:Y', lambda c: S[11, c] / S[18, c] * 100)
    # 36 Gross financing need 4/
    s.cell('C36', lambda: MD['S101'] / (MD['S56'] * MD['S60']) * 100)
    s.put(36, 'D:Y', lambda c: S[90, c] / S[41, c] * 100)
    # 37 in billions of U.S. dollars
    s.cell('C37', lambda: MD['S101'] / MD['S60'])
    s.put(37, 'D:Y', lambda c: S[90, c] / S[49, c])
    # 39 Key macroeconomic and fiscal assumptions
    s.cell('E39', lambda: S['D39'] * BP['O26'])
    # 41 Nominal GDP (local currency)
    s.put(41, 'C:E', lambda c: MD[56, c+16] * MD[60, c+16])
    s.put(41, 'F:Y', lambda c: S[41, c-1] * (1 + S[42, c] / 100) * (1 + S[54, c] / 100))
    # 42 Real GDP growth (in percent)
    s.put(42, 'C:D', lambda c: MD[107, c+16])
    s.put(42, 'E:Y', lambda c: BP[53, c+10])
    # 43 Average nominal interest rate on public debt (in percent)
    s.cell('C43', lambda: IF(ISNUMBER(100 * MD['S49'] / MD['R80']), 100 * MD['S49'] / MD['R80'], '.'))
    s.put(43, 'D:E', lambda c: BP[54, c+10])
    s.put(43, 'F:Y', lambda c: S[85, c] / S[79, c-1] * 100)
    # 44 Average nominal interest rate on external debt (in percent)
    s.put(44, 'C:E', lambda c: BP[55, c+10])
    s.put(44, 'F:Y', lambda c: S[87, c] / S[82, c-1] * 100 * MD[59, c+15] / MD[60, c+16])
    # 45 Average nominal interest rate on domestic debt (in percent)
    s.put(45, 'C:E', lambda c: BP[56, c+10])
    s.put(45, 'F:Y', lambda c: IF(S[80, c-1] == 0, PVR[25, c-1] * 100, S[86, c] / S[80, c-1] * 100))
    # 46 Average real interest rate (in percent)
    s.put(46, 'D:Y', lambda c: S[12, c-1] / S[11, c-1] * S[48, c] + (1 - S[12, c-1] / S[11, c-1]) * S[47, c])
    # 47 Average real interest rate on domestic debt (in percent)
    s.put(47, 'C:E', lambda c: BP[58, c+10])
    s.put(47, 'F:Y', lambda c: (S[45, c] - S[54, c]) / (1 + S[54, c] / 100))
    # 48 Average real interest rate on external debt (in percent)
    s.put(48, 'D:Y', lambda c: IF(ISNUMBER(S[44, c]), (S[44, c] - S[55, c]) / (1 + S[55, c] / 100), '...'))
    # 49 Exchange rate (LC per US dollar)
    s.put(49, 'C:D', lambda c: MD[59, c+16])
    s.put(49, 'E:Y', lambda c: BP[60, c+10])
    # 50 Nominal depreciation of local currency (percentage change in LC per dollar)
    s.put(50, 'D:Y', lambda c: (S[49, c] / S[49, c-1] - 1) * 100)
    # 51 Exchange rate (US dollar per LC)
    s.put(51, 'C:Y', lambda c: 1 / S[49, c])
    # 52 Nominal appreciation (increase in US dollar value of local currency, in percent)
    s.put(52, 'D:Y', lambda c: (S[51, c] / S[51, c-1] - 1) * 100)
    # 53 Real exchange rate depreciation (in percent, + indicates depreciation)
    s.put(53, 'D:Y', lambda c: (100 + S[50, c]) * (1 + S[55, c] / 100) / (1 + S[54, c] / 100) - 100)
    # 54 Inflation rate (GDP deflator, in percent)
    s.put(54, 'C:D', lambda c: IF(ISNUMBER(MD[109, c+16]), MD[109, c+16], '.'))
    s.put(54, 'E:Y', lambda c: BP[65, c+10])
    # 55 US Inflation rate (GDP deflator, in percent)
    s.put(55, 'C:D', lambda c: MD[112, c+16])
    s.put(55, 'E:Y', lambda c: BP[66, c+10])
    # 56 Growth of real primary spending (deflated by GDP deflator, in percent)
    s.cell('C56', lambda: MD['S100'])
    s.put(56, 'D:E', lambda c: BP[67, c+10])
    s.put(56, 'F:Y', lambda c: S[74, c])
    # 59 Historical Statistics for Key Variables (past 10 years)
    s.cell('H59', lambda: B1P['H59'])
    # 60 Historical
    s.cell('D60', lambda: A1P['F59'])
    s.cell('F60', lambda: A1P['H59'])
    s.cell('H60', lambda: S['D61'])
    # 61 Average
    s.cell('D61', lambda: A1P['F60'])
    s.cell('F61', lambda: A1P['H60'])
    # 63 Primary deficit
    s.cell('B63', lambda: A1P['B62'])
    s.cell('D63', lambda: A1P['F62'])
    s.cell('F63', lambda: BP['AK23'])
    s.cell('H63', lambda: BP['AP23'])
    # 64 Real GDP growth (in percent)
    s.cell('B64', lambda: A1P['B63'])
    s.cell('D64', lambda: A1P['F63'])
    s.cell('F64', lambda: BP['AK53'])
    s.cell('H64', lambda: BP['AP53'])
    # 65 Nominal interest rate (in percent) 6/
    s.cell('B65', lambda: A1P['B64'])
    s.cell('D65', lambda: A1P['F64'])
    s.cell('F65', lambda: BP['AK54'])
    s.cell('H65', lambda: BP['AP54'])
    # 66 Real interest rate (in percent)
    s.cell('B66', lambda: A1P['B65'])
    s.cell('D66', lambda: A1P['F65'])
    s.cell('F66', lambda: BP['AK57'])
    s.cell('H66', lambda: BP['AP57'])
    # 67 Inflation rate (GDP deflator, in percent)
    s.cell('B67', lambda: A1P['B66'])
    s.cell('D67', lambda: A1P['F66'])
    s.cell('F67', lambda: BP['AK65'])
    s.cell('H67', lambda: BP['AP65'])
    # 68 Revenue to GDP ratio
    s.cell('B68', lambda: A1P['B67'])
    s.cell('D68', lambda: A1P['F67'])
    s.cell('F68', lambda: BP['AK24'])
    # 72
    s.put(72, 'E:Y', lambda c: S[20, c] / 100 * S[41, c])
    # 73
    s.put(73, 'F:Y', lambda c: (S[72, c] / S[72, c-1] - 1) * 100)
    # 74
    s.put(74, 'F:Y', lambda c: ((1 + S[73, c] / 100) / (1 + S[54, c] / 100) - 1) * 100)
    # 78 In billions of local currency
    # 79 Nominal debt
    s.put(79, 'C:Y', lambda c: S[11, c] / 100 * S[41, c])
    # 80 Total public domestic debt
    s.put(80, 'C:Y', lambda c: S[79, c] - S[82, c])
    # 81 of which: Short term
    s.put(81, 'C:E', lambda c: MD[16, c+16])
    s.put(81, 'F:Y', lambda c: PVR[blk + 33, c-1] + MD[16, c+16])
    # 82 Total public external debt
    s.cell('C82', lambda: MD['S81'])
    s.put(82, 'D:E', lambda c: MD[81, c+16] / MD[59, c+16] * S[49, c])
    s.put(82, 'F:Y', lambda c: (MD[81, c+16] / MD[59, c+16] + PVR[blk + 9, c-1]) * S[49, c])
    # 83 Debt service
    # 84 Amortization (excluding ST domestic debt)
    s.put(84, 'C:E', lambda c: (MD[24, c+16] + MD[26, c+16]) * MD[60, c+16])
    s.put(84, 'F:Y', lambda c: (MD[24, c+16] + MD[26, c+16] + PVR[blk + 13, c-1]) * MD[60, c+16] + PVR[blk + 26, c-1])
    # 85 Interest Expenditure
    s.put(85, 'C:Y', lambda c: S[86, c] + S[87, c])
    # 86 Domestic debt
    s.put(86, 'C:E', lambda c: MD[21, c+16] * MD[60, c+16])
    s.put(86, 'F:Y', lambda c: MD[21, c+16] * MD[60, c+16] + PVR[blk + 25, c-1] + PVR[blk + 34, c-1])
    # 87 External debt
    s.put(87, 'C:E', lambda c: MD[19, c+16] * MD[60, c+16])
    s.put(87, 'F:Y', lambda c: (MD[19, c+16] + PVR[blk + 12, c-1]) * MD[60, c+16])
    # 88 Primary deficit
    s.put(88, 'D:Y', lambda c: S[17, c] / 100 * S[41, c])
    # 89 Other debt creating flows
    s.put(89, 'D:Y', lambda c: BP[33, c+10] / 100 * BP[52, c+10])
    # 90 Gross financing need (in local currency)
    s.put(90, 'D:Y', lambda c: S[88, c] + S[85, c] + S[84, c] + S[81, c-1] + S[89, c])
    # 91 PV of public sector external debt (end of period)
    s.put(91, 'D:E', lambda c: MD[92, c+16] * S[49, c] / BP[60, c+10])
    s.put(91, 'F:Y', lambda c: (MD[92, c+16] / BP[60, c+10] + PVR[blk + 10, c-1]) * S[49, c])
    # 93 Debt service-to-revenue-and-grants ratio (in percent)
    s.put(93, 'D:Y', lambda c: 10000 * (S[84, c] + S[85, c] + S[81, c-1]) / (S[18, c] * S[41, c]))
    # 94 Debt service-to-GDP ratio (in percent)
    s.put(94, 'D:Y', lambda c: 100 * (S[84, c] + S[85, c] + S[81, c-1]) / S[41, c])
    # 95 PV of public debt-to-revenue and grants ratio
    s.put(95, 'D:Y', lambda c: S[13, c] / S[18, c] * 100)


def _a1_historical_pub(s):
    """A1_Historical_pub"""
    BP = s.sheet('Baseline - public')
    MD = s.sheet('Macro-Debt_Data')
    PVR = s.sheet('PV_ResFin_pub')
    TRS = s.sheet('translation')
    S = s.sheet(s.name)
    blk = 29
    _public_stress(s, blk)
    # 3 (In percent of GDP, unless otherwise indicated)
    s.cell('B3', lambda: BP['B3'])
    # 9 I. Baseline Medium Term Projections
    s.cell('B9', lambda: BP['O10'])
    # 11 Public sector debt 1/
    s.cell('B11', lambda: BP['B12'])
    # 12 of which: external debt
    s.cell('B12', lambda: TRS['C1789'])
    # 13 PV of total public debt
    s.cell('B13', lambda: TR(s, 1770))
    s.put(13, 'C:Y', lambda c: IF((S[91, c] + S[80, c]) / S[41, c] * 100 < 0, 0, (S[91, c] + S[80, c]) / S[41, c] * 100))
    # 15 Change in public sector debt
    s.cell('B15', lambda: BP['B21'])
    # 16 Identified debt-creating flows
    s.cell('B16', lambda: BP['B22'])
    # 17 Primary deficit
    s.cell('B17', lambda: BP['B23'])
    s.cell('F17', lambda: S['F62'])
    s.put(17, 'G:Y', lambda c: S[17, c-1])
    # 18 Revenue and grants
    s.cell('B18', lambda: BP['B24'])
    # 19 of which: grants
    s.cell('B19', lambda: BP['B25'])
    # 20 Primary (noninterest) expenditure
    s.cell('B20', lambda: BP['B26'])
    s.put(20, 'F:Y', lambda c: S[18, c] + S[17, c])
    # 21 Automatic debt dynamics
    s.cell('B21', lambda: BP['B27'])
    # 22 Contribution from interest rate/growth differential
    s.cell('B22', lambda: BP['B28'])
    # 23 of which: contribution from average real interest rate
    s.cell('B23', lambda: BP['B29'])
    # 24 of which: contribution from real GDP growth
    s.cell('B24', lambda: BP['B30'])
    # 25 Contribution from real exchange rate depreciation
    s.cell('B25', lambda: BP['B31'])
    # 26 Denominator = 1+g
    s.cell('B26', lambda: BP['B32'])
    # 27 Other identified debt-creating flows
    s.cell('B27', lambda: BP['B33'])
    # 28 Privatization receipts (negative)
    s.cell('B28', lambda: BP['B34'])
    # 29 Recognition of contingent liabilities (e.g., bank recapitalization)
    s.cell('B29', lambda: BP['B35'])
    s.put(29, 'C:Y', lambda c: IF(ISNUMBER(BP[35, c+10]), BP[35, c+10] * BP[52, c+10] / S[41, c], 0 * BP[52, c+10] / S[41, c]))
    # 30 Debt relief (HIPC and other)
    s.cell('B30', lambda: BP['B36'])
    # 31 Other debt creating or reducing flow (please specify)
    s.cell('B31', lambda: BP['B37'])
    s.put(31, 'C:E', lambda c: IF(ISNUMBER(BP[37, c+10]), BP[37, c+10] * BP[52, c+10] / S[41, c], 0 * BP[52, c+10] / S[41, c]))
    s.put(31, 'G:Y', lambda c: IF(ISNUMBER(BP[37, c+10]), BP[37, c+10] * BP[52, c+10] / S[41, c], 0 * BP[52, c+10] / S[41, c]))
    # 32 Residual
    s.cell('B32', lambda: BP['B38'])
    # 34 Public sector debt-to-revenue-and-grants ratio (in percent)
    s.cell('B34', lambda: TRS['C1766'])
    # 36 Gross financing need 4/
    s.cell('B36', lambda: BP['B47'])
    # 37 in billions of U.S. dollars
    s.cell('B37', lambda: BP['B48'])
    # 39 Key macroeconomic and fiscal assumptions
    s.drop(39, 'E')
    s.cell('B39', lambda: BP['B51'])
    # 41 Nominal GDP (local currency)
    s.cell('B41', lambda: BP['B52'])
    # 42 Real GDP growth (in percent)
    s.cell('B42', lambda: BP['B53'])
    s.cell('E42', lambda: MD['U107'])
    s.cell('F42', lambda: S['F63'])
    s.put(42, 'G:Y', lambda c: S[42, c-1])
    # 43 Average nominal interest rate on public debt (in percent)
    s.cell('B43', lambda: BP['B54'])
    s.put(43, 'D:E', lambda c: IF(ISNUMBER(100 * MD[49, c+16] / MD[80, c+15]), 100 * MD[49, c+16] / MD[80, c+15], '.'))
    # 44 Average nominal interest rate on external debt (in percent)
    s.cell('B44', lambda: BP['B55'])
    # 45 Average nominal interest rate on domestic debt (in percent)
    s.cell('B45', lambda: BP['B56'])
    # 46 Average real interest rate (in percent)
    s.cell('B46', lambda: BP['B57'])
    # 47 Average real interest rate on domestic debt (in percent)
    s.cell('B47', lambda: BP['B58'])
    # 48 Average real interest rate on external debt (in percent)
    s.cell('B48', lambda: BP['B59'])
    # 49 Exchange rate (LC per US dollar)
    s.cell('B49', lambda: BP['B60'])
    s.put(49, 'E:Y', lambda c: MD[59, c+16])
    # 50 Nominal depreciation of local currency (percentage change in LC per dollar)
    s.cell('B50', lambda: BP['B61'])
    # 51 Exchange rate (US dollar per LC)
    s.cell('B51', lambda: BP['B62'])
    # 52 Nominal appreciation (increase in US dollar value of local currency, in percent)
    s.cell('B52', lambda: BP['B63'])
    # 53 Real exchange rate depreciation (in percent, + indicates depreciation)
    s.cell('B53', lambda: BP['B64'])
    # 54 Inflation rate (GDP deflator, in percent)
    s.cell('B54', lambda: BP['B65'])
    s.cell('E54', lambda: IF(ISNUMBER(MD['U109']), MD['U109'], '.'))
    s.cell('F54', lambda: S['F66'])
    s.put(54, 'G:Y', lambda c: S[54, c-1])
    # 55 US Inflation rate (GDP deflator, in percent)
    s.cell('B55', lambda: BP['B66'])
    s.put(55, 'E:Y', lambda c: MD[112, c+16])
    # 56 Growth of real primary spending (deflated by GDP deflator, in percent)
    s.cell('B56', lambda: BP['B67'])
    s.cell('C56', lambda: BP['M67'])
    # 59 Historical Statistics for Key Variables (past 10 years)
    s.cell('B59', lambda: TR(s, 1773))
    s.cell('F59', lambda: TR(s, 1809))
    s.cell('H59', lambda: TR(s, 1811))
    # 60
    s.drop(60, 'D')
    s.cell('F60', lambda: TR(s, 1810))
    s.cell('H60', lambda: TR(s, 1812))
    # 61
    s.drop(61, 'D')
    s.drop(61, 'F')
    # 62 Primary deficit
    s.cell('B62', lambda: TR(s, 1776))
    s.cell('F62', lambda: BP['AL23'])
    s.cell('H62', lambda: BP['AK23'])
    # 63 Real GDP growth (in percent)
    s.drop(63, 'D')
    s.cell('B63', lambda: TR(s, 1777))
    s.cell('F63', lambda: BP['AL53'])
    s.cell('H63', lambda: BP['AK53'])
    # 64 Nominal interest rate (in percent) 6/
    s.drop(64, 'D')
    s.cell('B64', lambda: TR(s, 1778))
    s.cell('F64', lambda: BP['AL54'])
    s.cell('H64', lambda: BP['AK54'])
    # 65 Real interest rate (in percent)
    s.drop(65, 'D')
    s.cell('B65', lambda: TR(s, 1779))
    s.cell('F65', lambda: BP['AL57'])
    s.cell('H65', lambda: BP['AK57'])
    # 66 Inflation rate (GDP deflator, in percent)
    s.drop(66, 'D')
    s.cell('B66', lambda: TR(s, 1780))
    s.cell('F66', lambda: BP['AL65'])
    s.cell('H66', lambda: BP['AK65'])
    # 67 Revenue to GDP ratio
    s.drop(67, 'D')
    s.cell('B67', lambda: TR(s, 1781))
    s.cell('F67', lambda: BP['AL24'])
    s.cell('H67', lambda: BP['AK24'])
    # 68
    s.drop(68, 'B')
    s.drop(68, 'D')
    s.drop(68, 'F')
    # 72 Nominal spending
    s.cell('B72', lambda: TR(s, 1785))
    s.put(72, 'C:D', lambda c: S[20, c] / 100 * S[41, c])
    # 73 Increase in percent
    s.cell('B73', lambda: TR(s, 1786))
    s.put(73, 'D:E', lambda c: (S[72, c] / S[72, c-1] - 1) * 100)
    # 74 Increase in real spending in percent
    s.cell('B74', lambda: TR(s, 1787))
    s.put(74, 'D:E', lambda c: ((1 + S[73, c] / 100) / (1 + S[54, c] / 100) - 1) * 100)
    # 78 In billions of local currency
    s.cell('B78', lambda: TR(s, 1791))
    # 79 Nominal debt
    s.cell('B79', lambda: TR(s, 1792))
    # 80 Total public domestic debt
    s.cell('B80', lambda: TR(s, 1794))
    # 81 of which: Short term
    s.cell('B81', lambda: TR(s, 1793))
    s.put(81, 'F:Y', lambda c: MD[16, c+16] + PVR[blk + 33, c-1])
    # 82 Total public external debt
    s.cell('B82', lambda: TR(s, 1795))
    # 83 Debt service
    s.cell('B83', lambda: TR(s, 1796))
    # 84 Amortization (excluding ST domestic debt)
    s.cell('B84', lambda: TR(s, 1797))
    s.put(84, 'C:E', lambda c: (MD[26, c+16] + MD[24, c+16]) * MD[60, c+16])
    # 85 Interest Expenditure
    s.cell('B85', lambda: TR(s, 1798))
    # 86 Domestic debt
    s.cell('B86', lambda: TR(s, 1799))
    s.put(86, 'F:Y', lambda c: MD[21, c+16] * MD[60, c+16] + PVR[blk + 34, c-1] + PVR[blk + 25, c-1])
    # 87 External debt
    s.cell('B87', lambda: TR(s, 1800))
    # 88 Primary deficit
    s.cell('B88', lambda: TR(s, 1801))
    # 89 Other debt creating flows
    s.cell('B89', lambda: TR(s, 1802))
    # 90 Gross financing need (in local currency)
    s.cell('B90', lambda: TR(s, 1803))
    # 91 PV of public sector external debt (end of period)
    s.cell('B91', lambda: TR(s, 408))
    # 93 Debt service-to-revenue-and-grants ratio (in percent)
    s.cell('B93', lambda: TR(s, 1806))
    s.put(93, 'D:Y', lambda c: IF((S[84, c] + S[85, c] + S[81, c-1]) / (S[18, c] * S[41, c]) < 0, 0, 10000 * (S[84, c] + S[85, c] + S[81, c-1]) / (S[18, c] * S[41, c])))
    # 94 Debt service-to-GDP ratio (in percent)
    s.cell('B94', lambda: TR(s, 1807))
    s.put(94, 'D:Y', lambda c: IF((S[84, c] + S[85, c] + S[81, c-1]) / S[41, c] < 0, 0, 100 * (S[84, c] + S[85, c] + S[81, c-1]) / S[41, c]))
    # 95 PV of public debt-to-revenue and grants ratio
    s.drop(95, 'B')


def _b1_gdp_pub(s):
    """B1_GDP_pub"""
    A1P = s.sheet('A1_Historical_pub')
    BP = s.sheet('Baseline - public')
    LK = s.sheet('lookup')
    STD = s.sheet('Input 6(optional)-Standard Test')
    TRS = s.sheet('translation')
    S = s.sheet(s.name)
    LANG = s.name_('LANG')
    blk = 65
    _public_stress(s, blk)
    # 2 Bounds Test 1: Real GDP Growth Shock
    s.cell('B2', lambda: TR(s, 1818))
    # 3 (In percent of GDP, unless otherwise indicated)
    s.cell('B3', lambda: A1P.ii(3, 'B', 3, 'I', 3, 'B'))
    # 29 Recognition of contingent liabilities (e.g., bank recapitalization)
    s.put(29, 'C:Y', lambda c: IF(ISNUMBER(BP[35, c+10]), BP[35, c+10] * BP[52, c+10] / S[41, c], 0 * BP[52, c+10] / S[41, c]))
    # 31 Other debt creating or reducing flow (please specify)
    s.put(31, 'C:E', lambda c: IF(ISNUMBER(BP[37, c+10]), BP[37, c+10] * BP[52, c+10] / S[41, c], 0 * BP[52, c+10] / S[41, c]))
    s.put(31, 'G:Y', lambda c: IF(ISNUMBER(BP[37, c+10]), BP[37, c+10] * BP[52, c+10] / S[41, c], 0 * BP[52, c+10] / S[41, c]))
    # 39 Key macroeconomic and fiscal assumptions
    s.drop(39, 'E')
    # 42 Real GDP growth (in percent)
    s.cell('F42', lambda: IF(S['AA63'] == STD['C7'], MIN(S['D64'] - S['AA62'] * S['F64'], BP['P53'] - S['AA62'] * S['F64']), IF(S['AA63'] == STD['C5'], S['D64'] - S['AA62'] * S['F64'], BP['P53'] - S['AA62'] * S['F64'])))
    s.cell('G42', lambda: IF(S['F42'] == S['D64'] - S['AA62'] * S['F64'], S['D64'] - S['AA62'] * S['F64'], BP['Q53'] - S['AA62'] * S['F64']))
    # 54 Inflation rate (GDP deflator, in percent)
    s.put(54, 'F:G', lambda c: BP[65, c+10] - (BP[53, c+10] - S[42, c]) * S['AA66'])
    # 56 Growth of real primary spending (deflated by GDP deflator, in percent)
    s.put(56, 'F:Y', lambda c: BP[67, c+10])
    # 59 Historical Statistics for Key Variables (past 10 years)
    s.cell('H59', lambda: TRS.offset(1813, 'C', 0, LANG))
    # 61 Average
    s.cell('H61', lambda: BP['AP7'])
    # 62
    s.cell('AA62', lambda: STD['D17'])
    # 63 Primary deficit
    s.cell('AA63', lambda: IF(STD['C4'] == LK['AF4'], STD['D18'], STD['C18']))
    # 66 Real interest rate (in percent)
    s.cell('AA66', lambda: STD['H17'])
    # 68 Revenue to GDP ratio
    s.cell('H68', lambda: BP['AP24'])
    # 72
    s.drop(72, 'E:Y')
    # 73
    s.drop(73, 'F:Y')
    # 74
    s.drop(74, 'F:Y')
    # 89 Other debt creating flows
    s.cell('B89', lambda: A1P['B89'])
    # 94 Debt service-to-GDP ratio (in percent)
    s.put(94, 'D:Y', lambda c: 100 * (S[84, c] + S[85, c] + S[81, c-1]) / S[41, c])


def _b2_pb_mkt_pub(s):
    """B2_PB_mkt_pub"""
    A1P = s.sheet('A1_Historical_pub')
    BE = s.sheet('Baseline - external')
    BP = s.sheet('Baseline - public')
    LK = s.sheet('lookup')
    MD = s.sheet('Macro-Debt_Data')
    PVM = s.sheet('PV_ResFin-add.int.cost - mkt')
    PVR = s.sheet('PV_ResFin_pub')
    STD = s.sheet('Input 6(optional)-Standard Test')
    S = s.sheet(s.name)
    blk = 101
    _public_stress(s, blk)
    # column B of these rows repeats the same cells of A1_Historical_pub
    s.same(A1P, 'B', [72, 73, 74])
    # 2 Bounds Test 2: Primary Balance Shock for Market Access Countries
    s.cell('B2', lambda: TR(s, 1822))
    # 17 Primary deficit
    s.cell('F17', lambda: IF(S['AA63'] == STD['C7'], MAX(S['D63'] + S['AA62'] * S['F63'], BP['P23'] + S['AA62'] * S['F63']), IF(S['AA63'] == STD['C5'], S['D63'] + S['AA62'] * S['F63'], BP['P23'] + S['AA62'] * S['F63'])))
    s.cell('G17', lambda: IF(S['F17'] == S['D63'] + S['AA62'] * S['F63'], S['D63'] + S['AA62'] * S['F63'], BP['Q23'] + S['AA62'] * S['F63']))
    # 20 Primary (noninterest) expenditure
    s.put(20, 'F:G', lambda c: S[17, c] + S[18, c])
    # 31 Other debt creating or reducing flow (please specify)
    s.cell('F31', lambda: IF(ISNUMBER(BP['P37']), BP['P37'] * BP['P52'] / S['F41'], 0))
    # 39 Key macroeconomic and fiscal assumptions
    s.put(39, 'F:Y', lambda c: S[39, c-1] * BP[26, c+10])
    # 56 Growth of real primary spending (deflated by GDP deflator, in percent)
    s.cell('C56', lambda: BP['M67'])
    # 61 Average
    s.cell('H61', lambda: BP['AP7'])
    # 62
    s.cell('AA62', lambda: STD['D21'])
    # 63 Primary deficit
    s.cell('AA63', lambda: IF(STD['C4'] == LK['AF4'], STD['D22'], STD['C22']))
    # 66 Real interest rate (in percent)
    s.cell('AA66', lambda: STD['H21'])
    # 67 Inflation rate (GDP deflator, in percent)
    s.cell('AA67', lambda: STD['H22'])
    # 68 Revenue to GDP ratio
    s.cell('H68', lambda: BP['AP24'])
    # 72 Nominal spending
    # 73 Increase in percent
    # 74 Increase in real spending in percent
    # 83 Debt service (PV_ResFin-fiscal & PV_ResFin-fiscal_add.cost.mkt added)
    s.drop(83, 'B')
    # 86 Domestic debt
    s.put(86, 'F:Y', lambda c: MD[21, c+16] * MD[60, c+16] + PVR[blk + 25, c-1] + PVR[blk + 34, c-1] + (PVM[47, c+1] + PVM[56, c+1]))
    # 87 External debt
    s.put(87, 'F:Y', lambda c: (MD[19, c+16] + PVR[blk + 12, c-1] + PVM[34, c+1]) * MD[60, c+16])
    # 91 PV of public sector external debt (end of period)
    s.put(91, 'G:Y', lambda c: (MD[92, c+16] / BP[60, c+10] + PVR[blk + 10, c-1] + PVM[32, c+1]) * S[49, c])
    # 94 Debt service-to-GDP ratio (in percent)
    s.cell('D94', lambda: 100 * (S['D84'] + S['D8'] + S['C814']) / S['D41'])
    # 101 PV of Debt/GDP
    s.put(101, 'D:Y', lambda c: S[91, c] / S[49, c] / (S[41, c] / S[110, c]) * 100)
    # 102 PV of Debt/exports
    s.put(102, 'D:Y', lambda c: S[91, c] / S[49, c] / S[108, c] * 100)
    # 103 Debt service/exports
    s.put(103, 'D:E', lambda c: (MD[19, c+16] + MD[24, c+16]) / S[108, c] * 100)
    s.put(103, 'F:Y', lambda c: (MD[19, c+16] + MD[24, c+16] + PVR[blk + 44, c-1] + PVM[34, c+1]) / S[108, c] * 100)
    # 104 Debt service/revenue (excl. grants)
    s.put(104, 'D:E', lambda c: (MD[19, c+16] + MD[24, c+16]) / MD[95, c+16] * 100)
    s.put(104, 'F:Y', lambda c: (MD[19, c+16] + MD[24, c+16] + PVR[blk + 44, c-1] + PVM[34, c+1]) / S[109, c] * 100)
    # 106 External PPG debt/GDP (baseline)
    s.put(106, 'D:Y', lambda c: BE[13, c+9])
    # 107 External PPG debt/GDP
    s.put(107, 'D:Y', lambda c: S[82, c] / S[41, c] * 100)
    # 108 Exports (US$) - baseline
    s.put(108, 'D:Y', lambda c: MD[29, c+16])
    # 109 Revenue
    s.put(109, 'D:Y', lambda c: (S[18, c] - S[19, c]) / 100 * (S[41, c] / S[110, c]))
    # 110 Exchange rate (pa)
    s.put(110, 'D:Y', lambda c: MD[60, c+16])


def _b2_pb_non_mkt_pub(s):
    """B2_PB_non_mkt_pub"""
    A1P = s.sheet('A1_Historical_pub')
    B2MP = s.sheet('B2_PB_mkt_pub')
    BE = s.sheet('Baseline - external')
    BP = s.sheet('Baseline - public')
    LK = s.sheet('lookup')
    MD = s.sheet('Macro-Debt_Data')
    PVM = s.sheet('PV_ResFin-add.int.cost - mkt')
    PVR = s.sheet('PV_ResFin_pub')
    STD = s.sheet('Input 6(optional)-Standard Test')
    S = s.sheet(s.name)
    blk = 134
    _public_stress(s, blk)
    # column B of these rows repeats the same cells of A1_Historical_pub
    s.same(A1P, 'B', [72, 73, 74])
    # column B of these rows repeats the same cells of B2_PB_mkt_pub
    s.same(B2MP, 'B', [101, 102, 103, 104, 106, 107, 108, 109, 110])
    # 2 Bounds Test 2: Primary Balance Shock for non-market access countries
    s.cell('B2', lambda: TR(s, 1825))
    # 17 Primary deficit
    s.cell('F17', lambda: IF(S['AA63'] == STD['C7'], MAX(S['D63'] + S['AA62'] * S['F63'], BP['P23'] + S['AA62'] * S['F63']), IF(S['AA63'] == STD['C5'], S['D63'] + S['AA62'] * S['F63'], BP['P23'] + S['AA62'] * S['F63'])))
    s.cell('G17', lambda: IF(S['F17'] == S['D63'] + S['AA62'] * S['F63'], S['D63'] + S['AA62'] * S['F63'], BP['Q23'] + S['AA62'] * S['F63']))
    # 20 Primary (noninterest) expenditure
    s.put(20, 'F:G', lambda c: S[17, c] + S[18, c])
    # 29 Recognition of contingent liabilities (e.g., bank recapitalization)
    s.put(29, 'C:Y', lambda c: IF(ISNUMBER(BP[35, c+10]), BP[35, c+10] * BP[52, c+10] / S[41, c], 0 * BP[52, c+10] / S[41, c]))
    # 31 Other debt creating or reducing flow (please specify)
    s.put(31, 'C:E', lambda c: IF(ISNUMBER(BP[37, c+10]), BP[37, c+10] * BP[52, c+10] / S[41, c], 0 * BP[52, c+10] / S[41, c]))
    s.put(31, 'G:Y', lambda c: IF(ISNUMBER(BP[37, c+10]), BP[37, c+10] * BP[52, c+10] / S[41, c], 0 * BP[52, c+10] / S[41, c]))
    # 39 Key macroeconomic and fiscal assumptions
    s.put(39, 'F:Y', lambda c: S[39, c-1] * BP[26, c+10])
    # 56 Growth of real primary spending (deflated by GDP deflator, in percent)
    s.cell('D56', lambda: S['D74'])
    # 61 Average
    s.cell('H61', lambda: BP['AP7'])
    # 62
    s.cell('AA62', lambda: STD['D21'])
    # 63 Primary deficit
    s.cell('AA63', lambda: IF(STD['C4'] == LK['AF4'], STD['D22'], STD['C22']))
    # 66 Real interest rate (in percent)
    s.cell('AA66', lambda: STD['H21'])
    # 68 Revenue to GDP ratio
    s.cell('H68', lambda: BP['AP24'])
    # 72 Nominal spending
    # 73 Increase in percent
    # 74 Increase in real spending in percent
    # 83 Debt service (PV_ResFin-fiscal & PV_ResFin-fiscal_add.cost.mkt added)
    s.drop(83, 'B')
    # 86 Domestic debt
    s.put(86, 'F:Y', lambda c: MD[21, c+16] * MD[60, c+16] + PVR[blk + 25, c-1] + PVR[blk + 34, c-1] + (PVM[80, c+1] + PVM[89, c+1]))
    # 101 PV of Debt/GDP
    s.put(101, 'D:Y', lambda c: S[91, c] / S[49, c] / (S[41, c] / S[110, c]) * 100)
    # 102 PV of Debt/exports
    s.put(102, 'D:Y', lambda c: S[91, c] / S[49, c] / S[108, c] * 100)
    # 103 Debt service/exports
    s.put(103, 'D:E', lambda c: (MD[19, c+16] + MD[24, c+16]) / S[108, c] * 100)
    s.put(103, 'F:Y', lambda c: (MD[19, c+16] + MD[24, c+16] + PVR[blk + 11, c-1]) / S[108, c] * 100)
    # 104 Debt service/revenue (excl. grants)
    s.put(104, 'D:E', lambda c: (MD[19, c+16] + MD[24, c+16]) / S[109, c] * 100)
    s.put(104, 'F:Y', lambda c: (MD[19, c+16] + MD[24, c+16] + PVR[blk + 11, c-1]) / S[109, c] * 100)
    # 106 External PPG debt/GDP (baseline)
    s.put(106, 'D:Y', lambda c: BE[13, c+9])
    # 107 External PPG debt/GDP
    s.put(107, 'D:Y', lambda c: S[82, c] / S[41, c] * 100)
    # 108 Exports (US$) - baseline
    s.put(108, 'D:Y', lambda c: MD[29, c+16])
    # 109 Revenue
    s.put(109, 'D:Y', lambda c: (S[18, c] - S[19, c]) / 100 * (S[41, c] / S[110, c]))
    # 110 Exchange rate (pa)
    s.put(110, 'D:Y', lambda c: B2MP[110, c])


def _b5_depreciation_pub(s):
    """B5_depreciation_pub"""
    A1P = s.sheet('A1_Historical_pub')
    B6NP = s.sheet('B6_combo_non-mkt_pub')
    BP = s.sheet('Baseline - public')
    LK = s.sheet('lookup')
    MD = s.sheet('Macro-Debt_Data')
    PVR = s.sheet('PV_ResFin_pub')
    STD = s.sheet('Input 6(optional)-Standard Test')
    S = s.sheet(s.name)
    blk = 170
    _public_stress(s, blk)
    # column B of these rows repeats the same cells of A1_Historical_pub
    s.same(A1P, 'B', [62, 63, 64, 65, 66, 67])
    # 2 Bounds Test 5: Exchange Rate Shock
    s.cell('B2', lambda: TR(s, 1828))
    # 31 Other debt creating or reducing flow (please specify)
    s.cell('F31', lambda: IF(ISNUMBER(BP['P37']), BP['P37'] * BP['P52'] / S['F41'], 0))
    # 49 Exchange rate (LC per US dollar)
    s.put(49, 'F:Y', lambda c: 1 / S[51, c])
    # 51 Exchange rate (US dollar per LC)
    s.put(51, 'F:Y', lambda c: S[51, c-1] * (1 + S[52, c] / 100))
    # 52 Nominal appreciation (increase in US dollar value of local currency, in percent)
    s.cell('F52', lambda: -S['AA62'])
    s.put(52, 'G:Y', lambda c: BP[63, c+10])
    # 53 Real exchange rate depreciation (in percent, + indicates depreciation)
    s.drop(53, 'B')
    # 54 Inflation rate (GDP deflator, in percent)
    s.cell('F54', lambda: BP['P65'] - S['AA65'] * S['F52'])
    # 56 Growth of real primary spending (deflated by GDP deflator, in percent)
    s.cell('C56', lambda: BP['M67'])
    s.put(56, 'F:Y', lambda c: BP[67, c+10])
    # 59 Historical Statistics for Key Variables (past 10 years)
    s.drop(59, 'H')
    # 60 Historical
    s.drop(60, 'H')
    s.cell('AA60', lambda: STD['C36'])
    # 61 Average
    s.cell('AA61', lambda: IF(STD['C4'] == LK['AF4'], STD['D37'], STD['C37']))
    # 62 Primary deficit
    s.cell('D62', lambda: B6NP['D63'])
    s.cell('F62', lambda: BP['AK23'])
    s.cell('AA62', lambda: IF(STD['C4'] == LK['AF4'], STD['D38'], STD['C38']))
    # 63 Real GDP growth (in percent)
    s.drop(63, 'H')
    s.cell('D63', lambda: B6NP['D64'])
    s.cell('F63', lambda: BP['AK53'])
    # 64 Nominal interest rate (in percent) 6/
    s.drop(64, 'H')
    s.cell('D64', lambda: B6NP['D65'])
    s.cell('F64', lambda: BP['AK54'])
    # 65 Real interest rate (in percent)
    s.drop(65, 'H')
    s.cell('D65', lambda: B6NP['D66'])
    s.cell('F65', lambda: BP['AK57'])
    s.cell('AA65', lambda: STD['H36'])
    # 66 Inflation rate (GDP deflator, in percent)
    s.drop(66, 'H')
    s.cell('D66', lambda: B6NP['D67'])
    s.cell('F66', lambda: BP['AK65'])
    # 67 Revenue to GDP ratio
    s.drop(67, 'H')
    s.cell('D67', lambda: B6NP['D68'])
    s.cell('F67', lambda: BP['AK24'])
    # 68
    s.drop(68, 'B')
    s.drop(68, 'D')
    s.drop(68, 'F')
    # 72
    s.drop(72, 'E:Y')
    # 73
    s.drop(73, 'F:Y')
    # 74
    s.drop(74, 'F:Y')
    # 84 Amortization (excluding ST domestic debt)
    s.put(84, 'F:Y', lambda c: MD[26, c+16] * MD[60, c+16] + PVR[blk + 26, c-1] + (MD[24, c+16] + PVR[blk + 13, c-1]) * (S[49, c] + S[49, c-1]) / 2)
    # 87 External debt
    s.put(87, 'F:Y', lambda c: (MD[19, c+16] + PVR[blk + 12, c-1]) * (S[49, c] + S[49, c-1]) / 2)
    # 92
    s.cell('E92', lambda: PVR[blk + 10, 'D'])


def _b6_combo_mkt_pub(s):
    """B6_combo_mkt_pub"""
    B2NP = s.sheet('B2_PB_non_mkt_pub')
    BP = s.sheet('Baseline - public')
    LK = s.sheet('lookup')
    MD = s.sheet('Macro-Debt_Data')
    PVM = s.sheet('PV_ResFin-add.int.cost - mkt')
    PVR = s.sheet('PV_ResFin_pub')
    STD = s.sheet('Input 6(optional)-Standard Test')
    S = s.sheet(s.name)
    blk = 206
    _public_stress(s, blk)
    # column B of these rows repeats the same cells of B2_PB_non_mkt_pub
    s.same(B2NP, 'B', [72, 73, 74])
    # 2 Bounds Test 6: Combined Shock for Market Access Countries
    s.cell('B2', lambda: TR(s, 1832))
    # 17 Primary deficit
    s.cell('F17', lambda: IF(S['AB69'] == STD['C7'], MAX(S['D63'] + S['AB68'] * S['F63'], BP['P23'] + S['AB68'] * S['F63']), IF(S['AB69'] == STD['C5'], S['D63'] + S['AB68'] * S['F63'], BP['P23'] + S['AB68'] * S['F63'])))
    s.cell('G17', lambda: IF(S['F17'] == S['D63'] + S['AB68'] * S['F63'], S['D63'] + S['AB68'] * S['F63'], BP['Q23'] + S['AB68'] * S['F63']))
    # 20 Primary (noninterest) expenditure
    s.put(20, 'F:G', lambda c: S[17, c] + S[18, c])
    # 31 Other debt creating or reducing flow (please specify)
    s.cell('F31', lambda: IF(ISNUMBER(BP['P37']), BP['P37'] * BP['P52'] / S['F41'], 0))
    # 42 Real GDP growth (in percent)
    s.cell('F42', lambda: IF(S['AB63'] == STD['C7'], MIN(S['D64'] - S['AB62'] * S['F64'], BP['P53'] - S['AB62'] * S['F64']), IF(S['AB63'] == STD['C5'], S['D64'] - S['AB62'] * S['F64'], BP['P53'] - S['AB62'] * S['F64'])))
    s.cell('G42', lambda: IF(S['F42'] == S['D64'] - S['AB62'] * S['F64'], S['D64'] - S['AB62'] * S['F64'], BP['Q53'] - S['AB62'] * S['F64']))
    # 52 Nominal appreciation (increase in US dollar value of local currency, in percent)
    s.cell('F52', lambda: -S['AB77'])
    # 54 Inflation rate (GDP deflator, in percent)
    s.cell('F54', lambda: BP['P65'] - S['AB79'] * S['F52'])
    # 56 Growth of real primary spending (deflated by GDP deflator, in percent)
    s.cell('C56', lambda: BP['M67'])
    # 61 Average
    s.cell('H61', lambda: BP['AP7'])
    # 62
    s.cell('AB62', lambda: STD['D41'])
    # 63 Primary deficit
    s.cell('AB63', lambda: IF(STD['C4'] == LK['AF4'], STD['D42'], STD['C42']))
    # 65 Nominal interest rate (in percent) 6/
    s.cell('AB65', lambda: STD['H41'])
    # 68 Revenue to GDP ratio
    s.cell('H68', lambda: BP['AP24'])
    s.cell('AB68', lambda: STD['D47'])
    # 69
    s.cell('AB69', lambda: IF(STD['C4'] == LK['AF4'], STD['D48'], STD['C48']))
    # 71
    s.cell('AB71', lambda: STD['H47'])
    # 72 Nominal spending
    s.cell('AB72', lambda: STD['H48'])
    # 73 Increase in percent
    # 74 Increase in real spending in percent
    # 75
    s.cell('AB75', lambda: STD['C56'])
    # 76
    s.cell('AB76', lambda: IF(STD['C4'] == LK['AF4'], STD['D57'], STD['C57']))
    # 77
    s.cell('AB77', lambda: IF(STD['C4'] == LK['AF4'], STD['D58'], STD['C58']))
    # 79 Nominal debt
    s.cell('AB79', lambda: STD['H56'])
    # 81 of which: Short term
    s.put(81, 'G:Y', lambda c: MD[10, c+16] * MD[59, c+16] + PVR[blk + 33, c-1] + MD[16, c+16])
    # 86 Domestic debt
    s.put(86, 'F:Y', lambda c: MD[21, c+16] * MD[60, c+16] + PVR[blk + 25, c-1] + PVR[blk + 34, c-1] + PVM[113, c+1] + PVM[122, c+1])
    # 87 External debt
    s.put(87, 'F:Y', lambda c: (MD[19, c+16] + PVR[blk + 12, c-1] + PVM[100, c+1]) * MD[60, c+16])


def _b6_combo_non_mkt_pub(s):
    """B6_combo_non-mkt_pub"""
    B2NP = s.sheet('B2_PB_non_mkt_pub')
    BP = s.sheet('Baseline - public')
    LK = s.sheet('lookup')
    MD = s.sheet('Macro-Debt_Data')
    PVM = s.sheet('PV_ResFin-add.int.cost - mkt')
    PVR = s.sheet('PV_ResFin_pub')
    START = s.sheet('START')
    STD = s.sheet('Input 6(optional)-Standard Test')
    TRS = s.sheet('translation')
    S = s.sheet(s.name)
    blk = 242
    _public_stress(s, blk)
    # column B of these rows repeats the same cells of B2_PB_non_mkt_pub
    s.same(B2NP, 'B', [72, 73, 74])
    # 2 Bounds Test 6: Combined Shock for Non-Market Access Countries
    s.cell('B2', lambda: TR(s, 1835))
    # 17 Primary deficit
    s.cell('F17', lambda: IF(S['AB69'] == STD['C7'], MAX(S['D63'] + S['AB68'] * S['F63'], BP['P23'] + S['AB68'] * S['F63']), IF(S['AB69'] == STD['C5'], S['D63'] + S['AB68'] * S['F63'], BP['P23'] + S['AA62'] * S['F63'])))
    s.cell('G17', lambda: IF(S['F17'] == S['D63'] + S['AB68'] * S['F63'], S['D63'] + S['AB68'] * S['F63'], BP['Q23'] + S['AB68'] * S['F63']))
    # 20 Primary (noninterest) expenditure
    s.put(20, 'F:G', lambda c: S[17, c] + S[18, c])
    # 31 Other debt creating or reducing flow (please specify)
    s.cell('F31', lambda: IF(ISNUMBER(BP['P37']), BP['P37'] * BP['P52'] / S['F41'], 0))
    # 42 Real GDP growth (in percent)
    s.cell('F42', lambda: IF(S['AB63'] == STD['C7'], MIN(S['D64'] - S['AB62'] * S['F64'], BP['P53'] - S['AB62'] * S['F64']), IF(S['AB63'] == STD['C5'], S['D64'] - S['AB62'] * S['F64'], BP['P53'] - S['AB62'] * S['F64'])))
    s.cell('G42', lambda: IF(S['F42'] == S['D64'] - S['AB62'] * S['F64'], S['D64'] - S['AB62'] * S['F64'], BP['Q53'] - S['AB62'] * S['F64']))
    # 52 Nominal appreciation (increase in US dollar value of local currency, in percent)
    s.cell('F52', lambda: -S['AB76'])
    # 54 Inflation rate (GDP deflator, in percent)
    s.cell('F54', lambda: BP['P65'] - S['AB78'] * S['F52'])
    # 56 Growth of real primary spending (deflated by GDP deflator, in percent)
    s.cell('D56', lambda: S['D74'])
    # 58
    s.cell('B58', lambda: IF(START['L10'] == 'English', TRS['C1836'], IF(START['L10'] == 'French', X('#REF!'), IF(START['L10'] == 'Portuguese', X('#REF!'), S['B115']))))
    # 61 Average
    s.cell('H61', lambda: BP['AP7'])
    # 62
    s.cell('AB62', lambda: STD['D41'])
    # 63 Primary deficit
    s.cell('AB63', lambda: IF(STD['C4'] == LK['AF4'], STD['D42'], STD['C42']))
    # 64 Real GDP growth (in percent)
    s.cell('K64', lambda: S['J64'] - S['F64'] * S['AB62'])
    # 65 Nominal interest rate (in percent) 6/
    s.cell('AB65', lambda: STD['H41'])
    # 68 Revenue to GDP ratio
    s.cell('H68', lambda: BP['AP24'])
    s.cell('AB68', lambda: STD['D47'])
    # 69
    s.cell('AB69', lambda: IF(STD['C4'] == LK['AF4'], STD['D48'], STD['C48']))
    # 71
    s.cell('AB71', lambda: STD['H47'])
    # 72 Nominal spending
    # 73 Increase in percent
    # 74 Increase in real spending in percent
    s.cell('AB74', lambda: STD['C56'])
    # 75
    s.cell('AB75', lambda: IF(STD['C4'] == LK['AF4'], STD['D57'], STD['C57']))
    # 76
    s.cell('AB76', lambda: IF(STD['C4'] == LK['AF4'], STD['D58'], STD['C58']))
    # 78 In billions of local currency
    s.cell('AB78', lambda: STD['H56'])
    # 86 Domestic debt
    s.put(86, 'F:Y', lambda c: MD[21, c+16] * MD[60, c+16] + PVR[blk + 25, c-1] + PVR[blk + 34, c-1] + PVM[146, c+1] + PVM[155, c+1])
    # 91 PV of public sector external debt (end of period)
    s.put(91, 'F:Y', lambda c: (MD[92, c+16] / BP[60, c+10] + PVR[blk + 7, c-1]) * S[49, c])


def _c1_combined_cl(s):
    """C1_Combined CL"""
    A1P = s.sheet('A1_Historical_pub')
    B2MP = s.sheet('B2_PB_mkt_pub')
    BE = s.sheet('Baseline - external')
    BP = s.sheet('Baseline - public')
    IN2 = s.sheet('Input 2 - Debt Coverage')
    MD = s.sheet('Macro-Debt_Data')
    PVR = s.sheet('PV_ResFin_pub')
    S = s.sheet(s.name)
    blk = 275
    _public_stress(s, blk)
    # column B of these rows repeats the same cells of B2_PB_mkt_pub
    s.same(B2MP, 'B', [101, 102, 103, 104, 106, 107, 108, 109, 110])
    # 2 Tailored Stress Test 1: Contingent Liability Shock
    s.cell('B2', lambda: TR(s, 1885))
    # 6 First year of proj.
    s.cell('E6', lambda: A1P.ii(6, 'E', 6, 'Y', 6, 'E'))
    # 31 Other debt creating or reducing flow (please specify)
    s.put(31, 'C:E', lambda c: IF(ISTEXT(BP[37, c+10]), 0 * BP[52, c+10] / S[41, c], BP[37, c+10] * BP[52, c+10] / S[41, c]))
    s.cell('F31', lambda: BP['P37'] * BP['P52'] / S['F41'] + S['AA60'])
    s.put(31, 'G:Y', lambda c: BP[37, c+10] * BP[52, c+10] / S[41, c])
    # 56 Growth of real primary spending (deflated by GDP deflator, in percent)
    s.cell('D56', lambda: S['D74'])
    s.put(56, 'F:Y', lambda c: BP[67, c+10])
    # 59 Historical Statistics for Key Variables (past 10 years)
    s.drop(59, 'H')
    # 60 Historical
    s.drop(60, 'F')
    s.drop(60, 'H')
    s.cell('AA60', lambda: IF(s.name_('Old_New_Scenario') == 0, 10, SUM(S.rng(62, 'AA', 65, 'AA'))))
    # 61 Average
    s.drop(61, 'F')
    # 62
    s.cell('AA62', lambda: IN2['F21'])
    # 63 Primary deficit
    s.drop(63, 'H')
    s.cell('AA63', lambda: IN2['F22'])
    # 64 Real GDP growth (in percent)
    s.drop(64, 'H')
    s.cell('AA64', lambda: IN2['F23'])
    # 65 Nominal interest rate (in percent) 6/
    s.drop(65, 'H')
    s.cell('AA65', lambda: IN2['F24'])
    # 66 Real interest rate (in percent)
    s.drop(66, 'H')
    # 67 Inflation rate (GDP deflator, in percent)
    s.drop(67, 'H')
    # 72
    s.drop(72, 'E:Y')
    # 73
    s.drop(73, 'F:Y')
    # 74
    s.drop(74, 'F:Y')
    # 87 External debt
    s.put(87, 'F:Y', lambda c: (MD[19, c+16] + PVR[blk + 12, c-1]) * MD[60, c+16])
    # 93 Debt service-to-revenue-and-grants ratio (in percent)
    s.drop(93, 'D')
    # 94 Debt service-to-GDP ratio (in percent)
    s.drop(94, 'D')
    # 95 PV of public debt-to-revenue and grants ratio
    s.drop(95, 'D')
    # 101 PV of Debt/GDP
    s.put(101, 'D:Y', lambda c: S[91, c] / S[49, c] / (S[41, c] / S[110, c]) * 100)
    # 102 PV of Debt/exports
    s.put(102, 'D:Y', lambda c: S[91, c] / S[49, c] / S[108, c] * 100)
    # 103 Debt service/exports
    s.put(103, 'D:E', lambda c: (MD[19, c+16] + MD[24, c+16]) / S[108, c] * 100)
    s.put(103, 'F:Y', lambda c: (MD[19, c+16] + MD[24, c+16] + PVR[blk + 11, c-1]) / S[108, c] * 100)
    # 104 Debt service/revenue (excl. grants)
    s.put(104, 'D:E', lambda c: (MD[19, c+16] + MD[24, c+16]) / S[109, c] * 100)
    s.put(104, 'F:Y', lambda c: (MD[19, c+16] + MD[24, c+16] + PVR[blk + 11, c-1]) / S[109, c] * 100)
    # 106 External PPG debt/GDP (baseline)
    s.put(106, 'D:Y', lambda c: BE[13, c+9])
    # 107 External PPG debt/GDP
    s.put(107, 'D:Y', lambda c: S[82, c] / S[41, c] * 100)
    # 108 Exports (US$) - baseline
    s.put(108, 'D:Y', lambda c: MD[29, c+16])
    # 109 Revenue
    s.put(109, 'D:Y', lambda c: (S[18, c] - S[19, c]) / 100 * (S[41, c] / S[110, c]))
    # 110 Exchange rate (pa)
    s.put(110, 'D:Y', lambda c: B2MP[110, c])


def _c2_natural_disaster(s):
    """C2_Natural disaster"""
    A1P = s.sheet('A1_Historical_pub')
    B2MP = s.sheet('B2_PB_mkt_pub')
    BE = s.sheet('Baseline - external')
    BP = s.sheet('Baseline - public')
    MD = s.sheet('Macro-Debt_Data')
    PVR = s.sheet('PV_ResFin_pub')
    TT = s.sheet('Input 6 - Tailored Tests')
    S = s.sheet(s.name)
    blk = 308
    _public_stress(s, blk)
    # column B of these rows repeats the same cells of B2_PB_mkt_pub
    s.same(B2MP, 'B', [101, 102, 103, 104, 106, 107, 108])
    # 2 Tailored Stress Test 2: Natural Disasters Shock
    s.cell('B2', lambda: TR(s, 1889))
    # 6 First year of proj.
    s.cell('E6', lambda: A1P.ii(6, 'E', 6, 'Y', 6, 'E'))
    # 12 of which: external debt
    s.put(12, 'D:Y', lambda c: S[83, c] / S[41, c] * 100)
    # 13 PV of total public debt
    s.put(13, 'C:Y', lambda c: (S[92, c] + S[81, c]) / S[41, c] * 100)
    # 31 Other debt creating or reducing flow (please specify)
    s.cell('F31', lambda: IF(ISNUMBER(BP['P37']), BP['P37'] * BP['P52'] / S['F41'] + S['AA62'], 0 * BP['P52'] / S['F41'] + S['AA62']))
    # 36 Gross financing need 4/
    s.put(36, 'D:Y', lambda c: S[91, c] / S[41, c] * 100)
    # 37 in billions of U.S. dollars
    s.put(37, 'D:Y', lambda c: S[91, c] / S[49, c])
    # 42 Real GDP growth (in percent)
    s.cell('F42', lambda: BP['P53'] - S['AA65'])
    # 43 Average nominal interest rate on public debt (in percent)
    s.put(43, 'F:Y', lambda c: S[86, c] / S[79, c-1] * 100)
    # 44 Average nominal interest rate on external debt (in percent)
    s.put(44, 'F:Y', lambda c: S[88, c] / S[83, c-1] * 100 * MD[59, c+15] / MD[60, c+16])
    # 45 Average nominal interest rate on domestic debt (in percent)
    s.put(45, 'F:Y', lambda c: IF(S[81, c-1] == 0, PVR[25, c-1] * 100, S[87, c] / S[81, c-1] * 100))
    # 56 Growth of real primary spending (deflated by GDP deflator, in percent)
    s.cell('D56', lambda: S['D74'])
    s.put(56, 'F:Y', lambda c: BP[67, c+10])
    # 58 Stress Tests 5: 10 percent of GDP increase in other debt-creating flows in 2025 7/
    s.cell('B58', lambda: TR(s, 1890))
    # 59 Historical Statistics for Key Variables (past 10 years)
    s.drop(59, 'H')
    # 60 Historical
    s.drop(60, 'F')
    s.drop(60, 'H')
    # 61 Average
    s.drop(61, 'F')
    # 62
    s.cell('AA62', lambda: TT['H21'])
    # 63 Primary deficit
    s.drop(63, 'H')
    # 64 Real GDP growth (in percent)
    s.drop(64, 'H')
    # 65 Nominal interest rate (in percent) 6/
    s.drop(65, 'H')
    s.cell('AA65', lambda: TT['L21'])
    # 66 Real interest rate (in percent)
    s.drop(66, 'H')
    s.cell('AA66', lambda: TT['L22'])
    # 67 Inflation rate (GDP deflator, in percent)
    s.drop(67, 'H')
    # 72
    s.drop(72, 'E:Y')
    # 73
    s.drop(73, 'F:Y')
    # 74
    s.drop(74, 'F:Y')
    # 75
    s.cell('G75', lambda: PVR[blk + 9, 'F'])
    # 80
    s.drop(80, 'B:Y')
    # 81 Total public domestic debt
    s.cell('B81', lambda: A1P['B80'])
    s.put(81, 'C:Y', lambda c: S[79, c] - S[83, c])
    # 82 of which: Short term
    s.cell('B82', lambda: A1P['B81'])
    s.put(82, 'C:E', lambda c: MD[16, c+16])
    s.put(82, 'F:Y', lambda c: PVR[blk + 33, c-1] + MD[16, c+16])
    # 83 Total public external debt
    s.cell('B83', lambda: A1P['B82'])
    s.cell('C83', lambda: MD['S81'])
    s.put(83, 'D:E', lambda c: MD[81, c+16] / MD[59, c+16] * S[49, c])
    s.put(83, 'F:Y', lambda c: (MD[81, c+16] / MD[59, c+16] + PVR[blk + 9, c-1]) * S[49, c])
    # 84 Debt service
    s.drop(84, 'C:Y')
    s.cell('B84', lambda: A1P['B83'])
    # 85 Amortization (excluding ST domestic debt)
    s.cell('B85', lambda: A1P['B84'])
    s.put(85, 'C:E', lambda c: (MD[24, c+16] + MD[26, c+16]) * MD[60, c+16])
    s.put(85, 'F:Y', lambda c: (MD[24, c+16] + MD[26, c+16] + PVR[blk + 13, c-1]) * MD[60, c+16] + PVR[blk + 26, c-1])
    # 86 Interest Expenditure
    s.cell('B86', lambda: A1P['B85'])
    s.put(86, 'C:Y', lambda c: S[87, c] + S[88, c])
    # 87 Domestic debt
    s.cell('B87', lambda: A1P['B86'])
    s.put(87, 'C:E', lambda c: MD[21, c+16] * MD[60, c+16])
    s.put(87, 'F:Y', lambda c: MD[21, c+16] * MD[60, c+16] + PVR[blk + 25, c-1] + PVR[blk + 34, c-1])
    # 88 External debt
    s.cell('B88', lambda: A1P['B87'])
    s.put(88, 'C:E', lambda c: MD[19, c+16] * MD[60, c+16])
    s.put(88, 'F:Y', lambda c: (MD[19, c+16] + PVR[blk + 12, c-1]) * MD[60, c+16])
    # 89 Primary deficit
    s.cell('B89', lambda: A1P['B88'])
    s.put(89, 'D:Y', lambda c: S[17, c] / 100 * S[41, c])
    # 90 Other debt creating flows
    s.drop(90, 'B')
    s.put(90, 'D:Y', lambda c: BP[33, c+10] / 100 * BP[52, c+10])
    # 91 Gross financing need (in local currency)
    s.cell('B91', lambda: A1P['B90'])
    s.put(91, 'D:Y', lambda c: S[89, c] + S[86, c] + S[85, c] + S[82, c-1] + S[90, c])
    # 92 PV of public sector external debt (end of period)
    s.cell('B92', lambda: A1P['B91'])
    s.put(92, 'D:E', lambda c: MD[92, c+16] * S[49, c] / BP[60, c+10])
    s.put(92, 'F:Y', lambda c: (MD[92, c+16] / BP[60, c+10] + PVR[blk + 10, c-1]) * S[49, c])
    # 93
    s.drop(93, 'B')
    s.drop(93, 'D:Y')
    # 94 Debt service-to-revenue-and-grants ratio (in percent)
    s.drop(94, 'D')
    s.cell('B94', lambda: A1P['B93'])
    s.put(94, 'E:Y', lambda c: 10000 * (S[85, c] + S[86, c] + S[82, c-1]) / (S[18, c] * S[41, c]))
    # 95 Debt service-to-GDP ratio (in percent)
    s.drop(95, 'D')
    s.cell('B95', lambda: A1P['B94'])
    s.put(95, 'E:Y', lambda c: 100 * (S[85, c] + S[86, c] + S[82, c-2]) / S[41, c])
    # 96 PV of public debt-to-revenue and grants ratio
    s.cell('B96', lambda: A1P['B95'])
    s.put(96, 'E:Y', lambda c: S[13, c] / S[18, c] * 100)
    # 101 PV of Debt/GDP
    s.put(101, 'D:Y', lambda c: S[92, c] / S[49, c] / (S[41, c] / S[111, c]) * 100)
    # 102 PV of Debt/exports
    s.put(102, 'D:Y', lambda c: S[92, c] / S[49, c] / S[108, c] * 100)
    # 103 Debt service/exports
    s.put(103, 'D:E', lambda c: (MD[19, c+16] + MD[24, c+16]) / S[108, c] * 100)
    s.put(103, 'F:Y', lambda c: (MD[19, c+16] + MD[24, c+16] + PVR[blk + 11, c-1]) / S[108, c] * 100)
    # 104 Debt service/revenue (excl. grants)
    s.put(104, 'D:E', lambda c: (MD[19, c+16] + MD[24, c+16]) / S[110, c] * 100)
    s.put(104, 'F:Y', lambda c: (MD[19, c+16] + MD[24, c+16] + PVR[blk + 11, c-1]) / S[110, c] * 100)
    # 106 External PPG debt/GDP (baseline)
    s.put(106, 'D:Y', lambda c: BE[13, c+9])
    # 107 External PPG debt/GDP
    s.put(107, 'D:Y', lambda c: S[83, c] / S[41, c] * 100)
    # 108 Exports (US$) - baseline
    s.put(108, 'D:E', lambda c: MD[29, c+16])
    s.put(108, 'F:Y', lambda c: S[108, c-1] * (1 + S[109, c] / 100))
    # 109 Exports growth rate
    s.put(109, 'D:E', lambda c: BE[55, c+9])
    s.cell('F109', lambda: BE['O55'] - S['AA66'])
    s.put(109, 'G:Y', lambda c: BE[55, c+9])
    # 110 Revenue
    s.cell('B110', lambda: B2MP['B109'])
    s.put(110, 'D:Y', lambda c: (S[18, c] - S[19, c]) / 100 * (S[41, c] / S[111, c]))
    # 111 Exchange rate (pa)
    s.cell('B111', lambda: B2MP['B110'])
    s.put(111, 'D:Y', lambda c: B2MP[110, c])


def _c3_commodity_prices_pub(s):
    """C3_commodity_prices_pub"""
    A1P = s.sheet('A1_Historical_pub')
    B1P = s.sheet('B1_GDP_pub')
    BP = s.sheet('Baseline - public')
    C3E = s.sheet('C3_Commodity prices_ext')
    TRS = s.sheet('translation')
    TT = s.sheet('Input 6 - Tailored Tests')
    S = s.sheet(s.name)
    LANG = s.name_('LANG')
    blk = 344
    _public_stress(s, blk)
    # 2 Tailored Stress Test 3. Commodity Price shock - Public
    s.cell('B2', lambda: TRS.offset(1897, 'C', 0, LANG))
    # 3 (In percent of GDP, unless otherwise indicated)
    s.cell('B3', lambda: A1P.ii(3, 'B', 3, 'I', 3, 'B'))
    # 6 First year of proj.
    s.cell('E6', lambda: A1P['E6'])
    # 18 Revenue and grants
    s.put(18, 'F:H', lambda c: BP[24, c+10] - BP[25, c+10] + S[19, c] - S['AA66'])
    s.cell('I18', lambda: BP['S24'] - BP['S25'] + S['I19'] - S['AA66'] * (S['AA62'] - 3) / (S['AA62'] - 2))
    s.cell('J18', lambda: BP['T24'] - BP['T25'] + S['J19'] - S['AA66'] * (S['AA62'] - 4) / (S['AA62'] - 2))
    s.cell('K18', lambda: BP['U24'] - BP['U25'] + S['K19'] - S['AA66'] * (S['AA62'] - 5) / (S['AA62'] - 2))
    # 20 Primary (noninterest) expenditure
    s.put(20, 'E:Y', lambda c: BP[26, c+10] * BP[52, c+10] / B1P[41, c])
    # 29 Recognition of contingent liabilities (e.g., bank recapitalization)
    s.put(29, 'C:Y', lambda c: IF(ISNUMBER(BP[35, c+10]), BP[35, c+10] * BP[52, c+10] / S[41, c], 0 * BP[52, c+10] / S[41, c]))
    # 31 Other debt creating or reducing flow (please specify)
    s.put(31, 'C:E', lambda c: IF(ISNUMBER(BP[37, c+10]), BP[37, c+10] * BP[52, c+10] / S[41, c], 0 * BP[52, c+10] / S[41, c]))
    s.put(31, 'G:Y', lambda c: IF(ISNUMBER(BP[37, c+10]), BP[37, c+10] * BP[52, c+10] / S[41, c], 0 * BP[52, c+10] / S[41, c]))
    # 39 Key macroeconomic and fiscal assumptions
    s.drop(39, 'E')
    # 42 Real GDP growth (in percent)
    s.put(42, 'F:K', lambda c: C3E[50, c-1])
    # 54 Inflation rate (GDP deflator, in percent)
    s.cell('F54', lambda: BP['P65'] * (1 + S['AA69'] * C3E['D19'] / 100))
    s.cell('G54', lambda: BP['Q65'] - (BP['Q65'] - S['F54']) * (S['AA62'] - 1) / S['AA62'])
    s.cell('H54', lambda: BP['R65'] - (BP['Q65'] - S['F54']) * (S['AA62'] - 2) / S['AA62'])
    s.cell('I54', lambda: BP['S65'] - (BP['Q65'] - S['F54']) * (S['AA62'] - 3) / S['AA62'])
    s.cell('J54', lambda: BP['T65'] - (BP['Q65'] - S['F54']) * (S['AA62'] - 4) / S['AA62'])
    s.cell('K54', lambda: BP['U65'] - (BP['Q65'] - S['F54']) * (S['AA62'] - 5) / S['AA62'])
    # 56 Growth of real primary spending (deflated by GDP deflator, in percent)
    s.cell('D56', lambda: S['D74'])
    s.put(56, 'F:Y', lambda c: BP[67, c+10])
    # 59 Historical Statistics for Key Variables (past 10 years)
    s.drop(59, 'H')
    # 60 Historical
    s.drop(60, 'F')
    s.drop(60, 'H')
    # 61 Average
    s.drop(61, 'F')
    # 62
    s.cell('AA62', lambda: TT['H26'])
    # 63 Primary deficit
    s.drop(63, 'H')
    # 64 Real GDP growth (in percent)
    s.drop(64, 'H')
    # 65 Nominal interest rate (in percent) 6/
    s.drop(65, 'H')
    s.cell('AA65', lambda: TT['L26'])
    # 66 Real interest rate (in percent)
    s.drop(66, 'H')
    s.cell('AA66', lambda: TT['L27'])
    # 67 Inflation rate (GDP deflator, in percent)
    s.drop(67, 'H')
    # 69
    s.cell('AA69', lambda: S['AA70'] * S['AA71'])
    # 70
    s.cell('AA70', lambda: TT['H30'])
    # 71
    s.cell('AA71', lambda: TT['H46'])
    # 72
    s.drop(72, 'E:Y')
    # 73
    s.drop(73, 'F:Y')
    # 74
    s.drop(74, 'F:Y')
    # 93
    s.drop(93, 'B')
    s.drop(93, 'D:Y')
    # 94
    s.drop(94, 'B')
    s.drop(94, 'D:Y')
    # 95 Debt service-to-revenue-and-grants ratio (in percent)
    s.drop(95, 'D')
    s.cell('B95', lambda: A1P['B93'])
    s.put(95, 'E:Y', lambda c: 10000 * (S[84, c] + S[85, c] + S[81, c-1]) / (S[18, c] * S[41, c]))
    # 96 Debt service-to-GDP ratio (in percent)
    s.cell('B96', lambda: A1P['B94'])
    s.put(96, 'E:Y', lambda c: 100 * (S[84, c] + S[85, c] + S[81, c-1]) / S[41, c])
    # 97 PV of public debt-to-revenue and grants ratio
    s.cell('B97', lambda: A1P['B95'])
    s.put(97, 'E:Y', lambda c: S[13, c] / S[18, c] * 100)


def _external_stress(s, blk):
    """Shared structure of the external-debt stress sheets"""
    A1E = s.sheet('A1_historical_ext')
    BE = s.sheet('Baseline - external')
    EDD = s.sheet('Ext_Debt_Data')
    MD = s.sheet('Macro-Debt_Data')
    PVS = s.sheet('PV Stress')
    S = s.sheet(s.name)
    # column B of these rows repeats the same cells of A1_historical_ext
    s.same(A1E, 'B', [79, 82, 83, 84, 85, 86, 88, 89, 90, 91, 92, 94, 95, 96, 98, 99, 100, 101, 103, 104, 105, 106,
                      107])
    # column B of these rows repeats the same cells of Baseline - external
    s.same(BE, 'B', [4, 10, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 33, 34, 35, 36,
                     37, 38, 39, 40, 41])
    # 3 Bounds Test 1: Real GDP Growth Shock
    s.cell('B3', lambda: TR(s, 1771))
    # 4 (In percent of GDP, unless otherwise indicated)
    # 7 Projections
    s.cell('D7', lambda: BE['N7'])
    # 8
    s.cell('C8', lambda: S['D8'] - 1)
    s.cell('D8', lambda: MD['U4'])
    s.put(8, 'E:X', lambda c: S[8, c-1] + 1)
    # 10 I. Baseline Medium Term Projections
    # 12 External debt (nominal) 1/
    s.put(12, 'C:D', lambda c: BE[12, c+10])
    s.put(12, 'E:X', lambda c: S[12, c-1] + S[15, c])
    # 13 of which: public and publicly guaranteed (PPG)
    s.put(13, 'C:X', lambda c: S[12, c] - S[14, c])
    # 14 of which: Private
    s.put(14, 'C:D', lambda c: BE[12, c+10] - BE[13, c+10])
    s.put(14, 'E:X', lambda c: BE[14, c+10] * BE[48, c+10] / S[46, c])
    # 15 Change in external debt
    s.put(15, 'C:Y', lambda c: S[16, c] + S[30, c])
    # 16 Identified net debt-creating flows
    s.put(16, 'C:Y', lambda c: S[17, c] + S[24, c] + S[25, c])
    # 17 Non-interest current account deficit
    s.put(17, 'C:X', lambda c: S[18, c] + S[21, c] + S[23, c])
    s.cell('Y17', lambda: -(S['Y24'] + S['Y25']))
    # 18 Deficit in balance of goods and services
    s.put(18, 'C:X', lambda c: S[20, c] - S[19, c])
    # 19 Exports
    s.put(19, 'C:D', lambda c: BE[19, c+10])
    s.put(19, 'E:X', lambda c: BE[19, c+10] * BE[48, c+10] / S[46, c])
    # 20 Imports
    s.put(20, 'C:D', lambda c: BE[20, c+10])
    s.put(20, 'E:F', lambda c: BE[20, c+10] * BE[48, c+10] / S[46, c])
    s.put(20, 'G:X', lambda c: S[18, c] + S[19, c])
    # 21 Net current transfers (negative = inflow)
    s.put(21, 'C:D', lambda c: BE[21, c+10])
    s.put(21, 'E:X', lambda c: BE[21, c+10] * BE[48, c+10] / S[46, c])
    # 22 of which: official
    s.put(22, 'C:D', lambda c: BE[22, c+10])
    s.put(22, 'E:X', lambda c: BE[22, c+10] * BE[48, c+10] / S[46, c])
    # 23 Other current account flows (negative = net inflow)
    s.put(23, 'C:D', lambda c: BE[23, c+10])
    s.put(23, 'E:X', lambda c: BE[23, c+10] * BE[48, c+10] / S[46, c])
    # 24 Net FDI (negative = inflow)
    s.put(24, 'C:D', lambda c: BE[24, c+10])
    s.put(24, 'E:X', lambda c: BE[24, c+10] * BE[48, c+10] / S[46, c])
    s.cell('Y24', lambda: S['X24'])
    # 25 Endogenous debt dynamics 2/
    s.cell('C25', lambda: BE['M25'])
    s.put(25, 'D:Y', lambda c: S[27, c] + S[28, c] + S[29, c])
    # 26 Denominator: 1+g+ρ+gρ
    s.cell('C26', lambda: BE['M26'])
    s.put(26, 'D:Y', lambda c: 1 + S[50, c] / 100 + S[51, c] / 100 + S[50, c] / 100 * S[51, c] / 100)
    # 27 Contribution from nominal interest rate
    s.put(27, 'C:D', lambda c: BE[27, c+10])
    s.put(27, 'E:Y', lambda c: S[52, c] / 100 * S[12, c-1] / S[26, c])
    # 28 Contribution from real GDP growth
    s.put(28, 'C:D', lambda c: BE[28, c+10])
    s.put(28, 'E:Y', lambda c: -(S[50, c] / 100) * S[12, c-1] / S[26, c])
    # 29 Contribution from price and exchange rate changes
    s.put(29, 'C:D', lambda c: BE[29, c+10])
    s.put(29, 'E:Y', lambda c: -(S[51, c] / 100 * (1 + S[50, c] / 100)) * S[12, c-1] / S[26, c] + S[56, c-1] * (-S[58, c] / 100) * (1 + S[52, c] / 100) * S[12, c-1] / S[26, c])
    # 30 Residual 3/
    s.put(30, 'C:D', lambda c: BE[30, c+10])
    s.put(30, 'E:X', lambda c: BE[30, c+10] * BE[48, c+10] / S[46, c])
    # 33 PV of external debt 7/
    s.put(33, 'C:D', lambda c: BE[33, c+10])
    s.put(33, 'E:X', lambda c: S[92, c] / S[46, c] * 100)
    # 34 In percent of exports
    s.put(34, 'C:D', lambda c: BE[34, c+10])
    s.put(34, 'E:X', lambda c: S[33, c] / S[19, c] * 100)
    # 35 PV of PPG external debt-to-GDP ratio
    s.put(35, 'C:D', lambda c: BE[35, c+10])
    s.put(35, 'E:X', lambda c: S[90, c] / S[46, c] * 100)
    # 36 PV of PPG external debt-to-exports ratio
    s.put(36, 'C:D', lambda c: BE[36, c+10])
    s.put(36, 'E:X', lambda c: S[35, c] / S[19, c] * 100)
    # 37 PV of PPG external debt-to-revenue ratio
    s.put(37, 'C:X', lambda c: S[35, c] * S[46, c] / S[106, c])
    # 38 Total external debt service-to-exports ratio
    s.put(38, 'C:D', lambda c: BE[38, c+10])
    s.put(38, 'E:X', lambda c: S[100, c] / S[105, c] * 100)
    # 39 PPG debt service-to-exports ratio
    s.put(39, 'C:D', lambda c: BE[39, c+10])
    s.put(39, 'E:X', lambda c: S[101, c] / S[105, c] * 100)
    # 40 PPG debt service-to-revenue ratio
    s.put(40, 'C:D', lambda c: BE[40, c+10])
    s.put(40, 'E:X', lambda c: S[101, c] / S[106, c] * 100)
    # 41 Gross external financing need (Million of U.S. dollars)
    s.put(41, 'C:D', lambda c: BE[41, c+10])
    s.put(41, 'E:X', lambda c: (S[17, c] + S[24, c]) / 100 * S[46, c] + S[100, c] + S[107, c-1])
    # 44 II. Key macroeconomic assumptions
    s.cell('B44', lambda: BE['B46'])
    # 46 Nominal GDP (Million of US dollars)
    s.cell('B46', lambda: BE['B48'])
    s.put(46, 'C:D', lambda c: BE[48, c+10])
    s.put(46, 'E:X', lambda c: S[46, c-1] * (1 + S[50, c] / 100) * (1 + S[51, c] / 100))
    # 47 Nominal dollar GDP growth
    s.cell('B47', lambda: BE['B49'])
    s.put(47, 'D:X', lambda c: (S[46, c] / S[46, c-1] - 1) * 100)
    # 48 PV of PPG external debt (in Million of US dollars)
    s.cell('B48', lambda: BE['B50'])
    s.cell('C48', lambda: S['C88'])
    s.put(48, 'D:X', lambda c: S[90, c])
    # 49 (PVt-PVt-1)/GDPt-1 (in percent)
    s.cell('B49', lambda: BE['B51'])
    s.put(49, 'D:X', lambda c: (S[48, c] - S[48, c-1]) / S[46, c-1] * 100)
    # 50 Real GDP growth (in percent)
    s.cell('B50', lambda: BE['B52'])
    s.put(50, 'C:E', lambda c: BE[52, c+10])
    s.cell('F50', lambda: IF(S['E50'] == S['D65'] - S['AA63'] * S['F65'], S['D65'] - S['AA63'] * S['F65'], BE['P52'] - S['AA63'] * S['F65']))
    s.put(50, 'G:X', lambda c: BE[52, c+10])
    s.cell('Y50', lambda: S['X50'])
    # 51 GDP deflator in US dollar terms (change in percent)
    s.cell('B51', lambda: BE['B53'])
    s.put(51, 'C:X', lambda c: BE[53, c+10])
    s.cell('Y51', lambda: S['X51'])
    # 52 Effective interest rate (percent) 4/
    s.cell('B52', lambda: BE['B54'])
    s.put(52, 'C:D', lambda c: BE[54, c+10])
    s.put(52, 'E:X', lambda c: S[104, c])
    s.cell('Y52', lambda: S['X52'])
    # 53 Growth of exports of G&S (US dollar terms, in percent)
    s.cell('B53', lambda: BE['B55'])
    s.put(53, 'C:X', lambda c: BE[55, c+10])
    # 54 Growth of imports of G&S (US dollar terms, in percent)
    s.cell('B54', lambda: BE['B56'])
    s.put(54, 'C:X', lambda c: BE[56, c+10])
    # 55 Current transfers, net total
    s.cell('B55', lambda: BE['B57'])
    s.put(55, 'C:X', lambda c: BE[57, c+10])
    # 56 Share of local-currency denominated external debt to total external debt
    s.cell('B56', lambda: BE['B43'])
    s.put(56, 'C:X', lambda c: BE[43, c+10])
    # 58 Depreciation of NC (+: depreciation)
    s.cell('B58', lambda: BE['B59'])
    s.put(58, 'C:X', lambda c: BE[59, c+10])
    # 59 Government revenues (excluding grants, in percent of GDP)
    s.cell('B59', lambda: BE['B60'])
    s.put(59, 'C:X', lambda c: S[106, c] / S[46, c] * 100)
    # 61 Historical
    s.cell('I61', lambda: S['D62'])
    # 62 III. Averages and Standard Deviations 9/
    s.cell('B62', lambda: BE['B68'])
    s.cell('I62', lambda: BE['S68'])
    s.cell('K62', lambda: BE['U68'])
    s.cell('M62', lambda: BE['W68'])
    # 64 Non-interest current account in percent of GDP
    s.cell('B64', lambda: BE['B70'])
    s.cell('D64', lambda: BE['N70'])
    s.cell('F64', lambda: BE['P70'])
    s.cell('I64', lambda: BE['S70'])
    s.cell('K64', lambda: BE['U70'])
    s.cell('M64', lambda: BE['W70'])
    # 65 Real GDP growth (in percent)
    s.cell('B65', lambda: BE['B71'])
    s.cell('D65', lambda: BE['N71'])
    s.cell('F65', lambda: BE['P71'])
    s.cell('I65', lambda: BE['S71'])
    s.cell('K65', lambda: BE['U71'])
    s.cell('M65', lambda: BE['W71'])
    # 66 US GDP Deflator (percent change)
    s.cell('B66', lambda: BE['B72'])
    s.cell('D66', lambda: BE['N72'])
    s.cell('F66', lambda: BE['P72'])
    s.cell('I66', lambda: BE['S72'])
    s.cell('K66', lambda: BE['U72'])
    s.cell('M66', lambda: BE['W72'])
    # 67 Growth of exports of G&S (US dollar terms, in percent)
    s.cell('B67', lambda: BE['B73'])
    s.cell('D67', lambda: BE['N73'])
    s.cell('F67', lambda: BE['P73'])
    s.cell('I67', lambda: BE['S73'])
    s.cell('K67', lambda: BE['U73'])
    s.cell('M67', lambda: BE['W73'])
    # 68 Current official transfers in percent of GDP
    s.cell('B68', lambda: BE['B74'])
    s.cell('D68', lambda: BE['N74'])
    s.cell('F68', lambda: BE['P74'])
    s.cell('I68', lambda: BE['S74'])
    s.cell('K68', lambda: BE['U74'])
    s.cell('M68', lambda: BE['W74'])
    # 69 Net non-debt creating flows (FDI) to GDP ratio
    s.cell('B69', lambda: BE['B75'])
    s.cell('D69', lambda: BE['N75'])
    s.cell('F69', lambda: BE['P75'])
    s.cell('I69', lambda: BE['S75'])
    s.cell('K69', lambda: BE['U75'])
    s.cell('M69', lambda: BE['W75'])
    # 71 Sources: Country authorities; and staff estimates and projections.
    s.cell('B71', lambda: BE['B77'])
    # 73 1/ Includes both public and private sector external debt.
    s.cell('B73', lambda: BE['B79'])
    # 74 2/ Derived as [r - g - ρ(1+g) + Ɛα (1+r)]/(1+g+ρ+gρ) times previous period debt ratio, ...
    s.cell('B74', lambda: BE['B80'])
    # 75 3/ Includes exceptional financing (i.e., changes in arrears and debt relief); changes i...
    s.cell('B75', lambda: BE['B81'])
    # 76 7/ Assumes that PV of private sector debt is equivalent to its face value.
    s.cell('B76', lambda: BE['B85'])
    # 77 4/ Current-year interest payments divided by previous period debt stock.
    s.cell('B77', lambda: BE['B82'])
    # 78 8/ Historical averages are generally derived over the past 10 years, subject to data av...
    s.cell('B78', lambda: BE['B86'])
    # 79 7/ Long-run, constant balance that stabilizes the debt ratio assuming that key variable...
    # 82 Nominal debt baseline
    s.put(82, 'C:X', lambda c: BE[12, c+10] / 100 * BE[48, c+10])
    # 83 Increase
    s.put(83, 'D:X', lambda c: S[82, c] - S[82, c-1])
    # 84 Nominal debt stress
    s.put(84, 'C:X', lambda c: S[12, c] / 100 * S[46, c])
    # 85 Increase
    s.put(85, 'D:X', lambda c: S[84, c] - S[84, c-1])
    # 86 Residual gross borrowing
    s.put(86, 'D:X', lambda c: S[85, c] - S[83, c])
    # 88 PV PPG baseline
    s.put(88, 'C:X', lambda c: EDD[391, c+2])
    # 89 PV of additional borrowing
    s.put(89, 'D:X', lambda c: PVS[blk + 5, c])
    # 90 PV PPG stress
    s.put(90, 'D:X', lambda c: S[88, c] + S[89, c])
    # 91 Private debt (=PV)
    s.put(91, 'D:X', lambda c: MD[12, c+17])
    # 92 PV total
    s.put(92, 'D:X', lambda c: S[90, c] + S[91, c])
    # 94 Debt service baseline
    s.put(94, 'D:X', lambda c: MD[18, c+17] + MD[23, c+17])
    # 95 o/w interest
    s.put(95, 'D:X', lambda c: MD[18, c+17])
    # 96 Debt service PPG baseline
    s.put(96, 'D:X', lambda c: EDD[394, c+2])
    # 98 Additional debt service stress
    s.put(98, 'E:X', lambda c: PVS[blk + 7, c])
    # 99 o/w interest
    s.put(99, 'D:X', lambda c: PVS[blk + 8, c])
    # 100 Total debt service stress
    s.put(100, 'D:X', lambda c: S[98, c] + S[94, c])
    # 101 PPG debt service stress
    s.put(101, 'D:X', lambda c: S[96, c] + S[98, c])
    # 103 New interest payments
    s.put(103, 'D:X', lambda c: S[95, c] + S[99, c])
    # 104 Effective rate
    s.put(104, 'D:X', lambda c: S[103, c] / S[84, c-1] * 100)
    # 105 Exports
    s.put(105, 'D:X', lambda c: S[19, c] / 100 * S[46, c])
    # 106 Revenue
    s.put(106, 'C:D', lambda c: BE[60, c+10] / 100 * BE[48, c+10])
    s.put(106, 'E:X', lambda c: BE[60, c+10] / 100 * S[46, c])
    # 107 Short-term debt
    s.put(107, 'C:X', lambda c: MD[89, c+17])


def _a1_historical_ext(s):
    """A1_historical_ext"""
    A1P = s.sheet('A1_Historical_pub')
    BE = s.sheet('Baseline - external')
    MD = s.sheet('Macro-Debt_Data')
    PVS = s.sheet('PV Stress')
    S = s.sheet(s.name)
    blk = 10
    _external_stress(s, blk)
    # 14 of which: Private
    s.put(14, 'E:X', lambda c: BE[12, c+10] - BE[13, c+10])
    # 17 Non-interest current account deficit
    s.cell('E17', lambda: -S['D64'])
    s.put(17, 'F:X', lambda c: S[17, c-1])
    # 19 Exports
    s.put(19, 'E:X', lambda c: BE[19, c+10])
    # 20 Imports
    s.put(20, 'E:X', lambda c: BE[20, c+10])
    # 21 Net current transfers (negative = inflow)
    s.put(21, 'E:X', lambda c: BE[21, c+10])
    # 22 of which: official
    s.put(22, 'E:X', lambda c: BE[22, c+10])
    # 23 Other current account flows (negative = net inflow)
    s.put(23, 'E:X', lambda c: BE[23, c+10])
    # 24 Net FDI (negative = inflow)
    s.cell('E24', lambda: -S['D69'])
    s.put(24, 'F:X', lambda c: S[24, c-1])
    # 30 Residual 3/
    s.put(30, 'E:X', lambda c: BE[30, c+10])
    # 33 PV of external debt 7/
    s.put(33, 'E:X', lambda c: S[92, c] * MD[59, c+17] / (S[46, c] * MD[60, c+17]) * 100)
    # 35 PV of PPG external debt-to-GDP ratio
    s.put(35, 'E:X', lambda c: IF(S[90, c] / S[46, c] * 100 < 0, 0, S[90, c] / S[46, c] * 100))
    # 39 PPG debt service-to-exports ratio
    s.put(39, 'E:X', lambda c: IF(S[101, c] / S[105, c] * 100 < 0, 0, S[101, c] / S[105, c] * 100))
    # 40 PPG debt service-to-revenue ratio
    s.put(40, 'E:X', lambda c: IF(S[101, c] / S[106, c] < 0, 0, S[101, c] / S[106, c] * 100))
    # 44 II. Key macroeconomic assumptions
    s.cell('X44', lambda: S['X41'] - S['X43'])
    # 45
    s.put(45, 'C:X', lambda c: S[46, c] - BE[48, c+10])
    # 50 Real GDP growth (in percent)
    s.cell('E50', lambda: S['D65'])
    s.put(50, 'F:X', lambda c: S[50, c-1])
    # 51 GDP deflator in US dollar terms (change in percent)
    s.cell('E51', lambda: S['D66'])
    s.put(51, 'F:X', lambda c: S[51, c-1])
    # 61 Historical
    s.cell('D61', lambda: A1P['F59'])
    s.cell('F61', lambda: A1P['H59'])
    s.cell('K61', lambda: S['D62'])
    # 62 III. Averages and Standard Deviations 9/
    s.drop(62, 'M')
    s.cell('D62', lambda: A1P['F60'])
    s.cell('F62', lambda: A1P['H60'])
    # 64 Non-interest current account in percent of GDP
    s.drop(64, 'M')
    # 65 Real GDP growth (in percent)
    s.drop(65, 'M')
    # 66 US GDP Deflator (percent change)
    s.drop(66, 'M')
    # 67 Growth of exports of G&S (US dollar terms, in percent)
    s.drop(67, 'M')
    # 68 Current official transfers in percent of GDP
    s.drop(68, 'M')
    # 69 Net non-debt creating flows (FDI) to GDP ratio
    s.drop(69, 'M')
    # 79 7/ Long-run, constant balance that stabilizes the debt ratio assuming that key variable...
    s.cell('B79', lambda: TR(s, 1847))
    # 82 Nominal debt baseline
    s.cell('B82', lambda: TR(s, 1848))
    # 83 Increase
    s.cell('B83', lambda: TR(s, 1849))
    # 84 Nominal debt stress
    s.cell('B84', lambda: TR(s, 1850))
    # 85 Increase
    s.cell('B85', lambda: TR(s, 1851))
    # 86 Residual gross borrowing
    s.cell('B86', lambda: TR(s, 1852))
    # 88 PV PPG baseline
    s.cell('B88', lambda: TR(s, 1854))
    # 89 PV of additional borrowing
    s.cell('B89', lambda: TR(s, 1855))
    # 90 PV PPG stress
    s.cell('B90', lambda: TR(s, 1856))
    # 91 Private debt (=PV)
    s.cell('B91', lambda: TR(s, 1857))
    # 92 PV total
    s.cell('B92', lambda: TR(s, 1858))
    # 94 Debt service baseline
    s.cell('B94', lambda: TR(s, 1860))
    # 95 o/w interest
    s.cell('B95', lambda: TR(s, 1861))
    # 96 Debt service PPG baseline
    s.cell('B96', lambda: TR(s, 1862))
    # 98 Additional debt service stress
    s.cell('B98', lambda: TR(s, 1864))
    s.cell('D98', lambda: PVS[blk + 7, 'D'])
    # 99 o/w interest
    s.cell('B99', lambda: TR(s, 1865))
    # 100 Total debt service stress
    s.cell('B100', lambda: TR(s, 1866))
    # 101 PPG debt service stress
    s.cell('B101', lambda: TR(s, 1867))
    # 103 New interest payments
    s.cell('B103', lambda: TR(s, 1869))
    # 104 Effective rate
    s.cell('B104', lambda: TR(s, 1870))
    # 105 Exports
    s.cell('B105', lambda: TR(s, 1871))
    # 106 Revenue
    s.cell('B106', lambda: TR(s, 1872))
    # 107 Short-term debt
    s.cell('B107', lambda: TR(s, 1873))


def _b1_gdp_ext(s):
    """B1_GDP_ext"""
    A1E = s.sheet('A1_historical_ext')
    BE = s.sheet('Baseline - external')
    LK = s.sheet('lookup')
    PVS = s.sheet('PV Stress')
    START = s.sheet('START')
    STD = s.sheet('Input 6(optional)-Standard Test')
    S = s.sheet(s.name)
    blk = 27
    _external_stress(s, blk)
    # 3 Bounds Test 1: Real GDP Growth Shock
    s.cell('B3', lambda: TR(s, 1818))
    # 20 Imports
    s.put(20, 'G:X', lambda c: BE[20, c+10] * BE[48, c+10] / S[46, c])
    # 50 Real GDP growth (in percent)
    s.cell('E50', lambda: IF(S['AA64'] == STD['C7'], MIN(S['D65'] - S['AA63'] * S['F65'], BE['O52'] - S['AA63'] * S['F65']), IF(S['AA64'] == STD['C5'], S['D65'] - S['AA63'] * S['F65'], BE['O52'] - S['AA63'] * S['F65'])))
    # 51 GDP deflator in US dollar terms (change in percent)
    s.put(51, 'E:F', lambda c: BE[53, c+10] - (BE[52, c+10] - S[50, c]) * S['AA67'])
    # 61 Historical
    s.cell('D61', lambda: A1E['D61'])
    s.cell('F61', lambda: A1E['F61'])
    s.cell('K61', lambda: S['D62'])
    s.cell('M61', lambda: S['D62'])
    # 62 III. Averages and Standard Deviations 9/
    s.cell('D62', lambda: A1E['D62'])
    s.cell('F62', lambda: A1E['F62'])
    # 63
    s.cell('AA63', lambda: STD['D17'])
    # 64 Non-interest current account in percent of GDP
    s.cell('AA64', lambda: IF(STD['C4'] == LK['AF4'], STD['D18'], STD['C18']))
    # 67 Growth of exports of G&S (US dollar terms, in percent)
    s.cell('AA67', lambda: STD['H17'])
    # 80
    s.cell('B80', lambda: IF(START['L10'] == 'English', S['B146'], IF(START['L10'] == 'French', S['B178'], IF(START['L10'] == 'Portuguese', S['B210'], S['B242']))))
    # 98 Additional debt service stress
    s.cell('D98', lambda: PVS[blk + 7, 'D'])


def _b3_exports_ext(s):
    """B3_Exports_ext"""
    A1E = s.sheet('A1_historical_ext')
    BE = s.sheet('Baseline - external')
    LK = s.sheet('lookup')
    PVS = s.sheet('PV Stress')
    STD = s.sheet('Input 6(optional)-Standard Test')
    S = s.sheet(s.name)
    blk = 44
    _external_stress(s, blk)
    # 3 Bound Test 2: Exports Shock
    s.cell('B3', lambda: TR(s, 1880))
    # 14 of which: Private
    s.put(14, 'E:X', lambda c: BE[12, c+10] - BE[13, c+10])
    # 18 Deficit in balance of goods and services
    s.put(18, 'G:X', lambda c: BE[18, c+10] * BE[48, c+10] / S[46, c])
    # 19 Exports
    s.put(19, 'E:X', lambda c: S[105, c] / S[46, c] * 100)
    # 50 Real GDP growth (in percent)
    s.put(50, 'E:F', lambda c: IF(S[68, c+22] == 0, BE[52, c+10] + S['AA66'] * S[53, c] * S[19, c-1] / 100, BE[52, c+10] - S['AA66'] * (BE[55, c+10] - S[53, c]) * S[19, c-1] / 100))
    # 53 Growth of exports of G&S (US dollar terms, in percent)
    s.cell('E53', lambda: IF(S['AA63'] == STD['C7'], MIN(S['D67'] - S['AA62'] * S['F67'], BE['O55'] - S['AA62'] * S['F67']), IF(S['AA63'] == STD['C5'], S['D67'] - S['AA62'] * S['F67'], BE['O55'] - S['AA62'] * S['F67'])))
    s.cell('F53', lambda: IF(S['E53'] == S['D67'] - S['AA62'] * S['F67'], S['D67'] - S['AA62'] * S['F67'], BE['P55'] - S['AA62'] * S['F67']))
    # 61 Historical
    s.cell('D61', lambda: A1E['D61'])
    s.cell('F61', lambda: A1E['F61'])
    s.cell('K61', lambda: S['D62'])
    s.cell('M61', lambda: S['D62'])
    # 62 III. Averages and Standard Deviations 9/
    s.cell('D62', lambda: A1E['D62'])
    s.cell('F62', lambda: A1E['F62'])
    s.cell('AA62', lambda: STD['D25'])
    # 63
    s.cell('AA63', lambda: IF(STD['C4'] == LK['AF4'], STD['D26'], STD['C26']))
    # 66 US GDP Deflator (percent change)
    s.cell('AA66', lambda: STD['H25'])
    # 68 Current official transfers in percent of GDP
    s.put(68, 'AA:AB', lambda c: IF(S[53, c-22] < 0, 0, 1))
    # 72 a/ Exports values are assumed to remain permanently at the lower level, but the current...
    s.cell('B72', lambda: TR(s, 1879))
    # 98 Additional debt service stress
    s.cell('D98', lambda: PVS[blk + 7, 'D'])
    # 105 Exports
    s.cell('C105', lambda: S['C19'] / 100 * S['C46'])
    s.put(105, 'E:X', lambda c: S[105, c-1] * (1 + S[53, c] / 100))


def _b4_other_flows_ext(s):
    """B4_other flows_ext"""
    A1E = s.sheet('A1_historical_ext')
    BE = s.sheet('Baseline - external')
    LK = s.sheet('lookup')
    STD = s.sheet('Input 6(optional)-Standard Test')
    S = s.sheet(s.name)
    blk = 61
    _external_stress(s, blk)
    # 3 Bound Test 4: Other Flows Shock
    s.cell('B3', lambda: TR(s, 1882))
    # 20 Imports
    s.put(20, 'G:X', lambda c: BE[20, c+10] * BE[48, c+10] / S[46, c])
    # 21 Net current transfers (negative = inflow)
    s.cell('E21', lambda: IF(S['AA64'] == STD['C7'], MAX(-(S['D68'] - S['AA63'] * S['F68']), BE['O21'] + S['AA63'] * S['F68']), IF(S['AA64'] == STD['C5'], -(S['D68'] - S['AA63'] * S['F68']), BE['O21'] + S['AA63'] * S['F68'])))
    s.cell('F21', lambda: IF(S['E21'] == -(S['D68'] - S['AA63'] * S['F68']), -(S['D68'] - S['AA63'] * S['F68']), BE['P21'] + S['AA63'] * S['F68']))
    # 22 of which: official
    s.drop(22, 'E')
    s.cell('F22', lambda: S['E22'])
    # 24 Net FDI (negative = inflow)
    s.cell('E24', lambda: IF(S['AA67'] == STD['C7'], MAX(-(S['D69'] - S['AA66'] * S['F69']), BE['O24'] + S['AA66'] * S['F69']), IF(S['AA67'] == STD['C5'], -(S['D69'] - S['AA66'] * S['F69']), BE['O24'] + S['AA66'] * S['F69'])))
    s.cell('F24', lambda: IF(S['E24'] == -(S['D69'] - S['AA66'] * S['F69']), -(S['D69'] - S['AA66'] * S['F69']), BE['P24'] + S['AA66'] * S['F69']))
    # 50 Real GDP growth (in percent)
    s.cell('F50', lambda: BE['P52'])
    # 61 Historical
    s.cell('D61', lambda: A1E['D61'])
    s.cell('F61', lambda: A1E['F61'])
    s.cell('K61', lambda: S['F62'])
    s.cell('M61', lambda: S['H62'])
    # 62 III. Averages and Standard Deviations 9/
    s.cell('D62', lambda: A1E['D62'])
    s.cell('F62', lambda: A1E['F62'])
    # 63
    s.cell('AA63', lambda: STD['D29'])
    # 64 Non-interest current account in percent of GDP
    s.cell('O64', lambda: S['D64'] + S['F64'])
    s.cell('AA64', lambda: IF(STD['C4'] == LK['AF4'], STD['D30'], STD['C30']))
    # 66 US GDP Deflator (percent change)
    s.cell('AA66', lambda: STD['D32'])
    # 67 Growth of exports of G&S (US dollar terms, in percent)
    s.cell('AA67', lambda: IF(STD['C4'] == LK['AF4'], STD['D33'], STD['C33']))
    # 69 Net non-debt creating flows (FDI) to GDP ratio
    s.cell('O69', lambda: S['D69'] + S['F69'])


def _b5_depreciation_ext(s):
    """B5_depreciation_ext"""
    A1E = s.sheet('A1_historical_ext')
    B5P = s.sheet('B5_depreciation_pub')
    BE = s.sheet('Baseline - external')
    EDD = s.sheet('Ext_Debt_Data')
    LK = s.sheet('lookup')
    MD = s.sheet('Macro-Debt_Data')
    PVS = s.sheet('PV Stress')
    START = s.sheet('START')
    STD = s.sheet('Input 6(optional)-Standard Test')
    S = s.sheet(s.name)
    blk = 111
    _external_stress(s, blk)
    # 3 Bounds Test 5: Exchange Rate Shock
    s.cell('B3', lambda: TR(s, 1828))
    # 18 Deficit in balance of goods and services
    s.cell('F18', lambda: BE['P18'] - S['AA68'] * S['E43'])
    # 20 Imports
    s.cell('F20', lambda: S['F19'] + S['F18'])
    s.put(20, 'G:X', lambda c: BE[20, c+10] * BE[48, c+10] / S[46, c])
    # 33 PV of external debt 7/
    s.put(33, 'E:X', lambda c: S[93, c] / S[46, c] * 100)
    # 35 PV of PPG external debt-to-GDP ratio
    s.put(35, 'E:X', lambda c: S[91, c] / S[46, c] * 100)
    # 37 PV of PPG external debt-to-revenue ratio
    s.put(37, 'C:X', lambda c: S[35, c] * S[46, c] / S[107, c])
    # 38 Total external debt service-to-exports ratio
    s.put(38, 'E:X', lambda c: S[101, c] / S[106, c] * 100)
    # 39 PPG debt service-to-exports ratio
    s.put(39, 'E:X', lambda c: S[102, c] / S[106, c] * 100)
    # 40 PPG debt service-to-revenue ratio
    s.put(40, 'E:X', lambda c: S[102, c] / S[107, c] * 100)
    # 41 Gross external financing need (Million of U.S. dollars)
    s.put(41, 'E:X', lambda c: (S[17, c] + S[24, c]) / 100 * S[46, c] + S[101, c] + S[108, c-1])
    # 43
    s.cell('E43', lambda: (100 + S['E58']) * (100 + MD['V112']) / (100 + MD['V109'] + S['AA67'] * S['E58']) - 100)
    # 44 II. Key macroeconomic assumptions
    s.put(44, 'E:F', lambda c: B5P[53, c+1])
    # 48 PV of PPG external debt (in Million of US dollars)
    s.cell('C48', lambda: S['C89'])
    s.put(48, 'D:X', lambda c: S[91, c])
    # 50 Real GDP growth (in percent)
    s.cell('F50', lambda: BE['P52'])
    # 51 GDP deflator in US dollar terms (change in percent)
    s.cell('E51', lambda: BE['O53'] + IF(STD['C4'] == LK['AF5'], BE['O59'] - (1 - S['AA67']) * S['E58'], 0 * BE['O59'] - (1 - S['AA67']) * S['E58']))
    # 52 Effective interest rate (percent) 4/
    s.put(52, 'E:X', lambda c: S[105, c])
    # 53 Growth of exports of G&S (US dollar terms, in percent)
    s.cell('F53', lambda: (S['F19'] * S['F46'] / (S['E19'] * S['E46']) - 1) * 100)
    # 54 Growth of imports of G&S (US dollar terms, in percent)
    s.cell('F54', lambda: (S['F20'] * S['F46'] / (S['E20'] * S['E46']) - 1) * 100)
    # 58 Depreciation of NC (+: depreciation)
    s.cell('E58', lambda: S['AA64'])
    # 59 Exchange rate dollar / NC (baseline)
    s.drop(59, 'B')
    s.put(59, 'C:X', lambda c: MD[113, c+17])
    # 60 Government revenues (excluding grants, in percent of GDP)
    s.cell('B60', lambda: BE['B60'])
    s.put(60, 'C:X', lambda c: S[107, c] / S[46, c] * 100)
    # 61
    s.drop(61, 'I')
    # 62 Historical
    s.drop(62, 'B')
    s.drop(62, 'I')
    s.drop(62, 'K')
    s.drop(62, 'M')
    s.cell('AA62', lambda: STD['C36'])
    # 63 III. Averages and Standard Deviations 9/
    s.cell('B63', lambda: BE['B68'])
    s.cell('I63', lambda: BE['S68'])
    s.cell('K63', lambda: BE['U68'])
    s.cell('AA63', lambda: IF(STD['C4'] == LK['AF4'], STD['D37'], STD['C37']))
    # 64
    s.drop(64, 'B')
    s.drop(64, 'D')
    s.drop(64, 'F')
    s.drop(64, 'I')
    s.drop(64, 'K')
    s.drop(64, 'M')
    s.cell('AA64', lambda: IF(STD['C4'] == LK['AF4'], STD['D38'], STD['C38']))
    # 65 Non-interest current account in percent of GDP
    s.drop(65, 'M')
    s.cell('B65', lambda: BE['B70'])
    s.cell('D65', lambda: BE['N70'])
    s.cell('F65', lambda: BE['P70'])
    s.cell('I65', lambda: BE['S70'])
    s.cell('K65', lambda: BE['U70'])
    # 66 Real GDP growth (in percent)
    s.drop(66, 'M')
    s.cell('B66', lambda: BE['B71'])
    s.cell('D66', lambda: BE['N71'])
    s.cell('F66', lambda: BE['P71'])
    s.cell('I66', lambda: BE['S71'])
    s.cell('K66', lambda: BE['U71'])
    # 67 US GDP Deflator (percent change)
    s.drop(67, 'M')
    s.cell('B67', lambda: BE['B72'])
    s.cell('D67', lambda: BE['N72'])
    s.cell('F67', lambda: BE['P72'])
    s.cell('I67', lambda: BE['S72'])
    s.cell('K67', lambda: BE['U72'])
    s.cell('AA67', lambda: STD['H36'])
    # 68 Growth of exports of G&S (US dollar terms, in percent)
    s.drop(68, 'M')
    s.cell('B68', lambda: BE['B73'])
    s.cell('D68', lambda: BE['N73'])
    s.cell('F68', lambda: BE['P73'])
    s.cell('I68', lambda: BE['S73'])
    s.cell('K68', lambda: BE['U73'])
    s.cell('AA68', lambda: STD['H37'])
    # 69 Current official transfers in percent of GDP
    s.drop(69, 'M')
    s.cell('B69', lambda: BE['B74'])
    s.cell('D69', lambda: BE['N74'])
    s.cell('F69', lambda: BE['P74'])
    s.cell('I69', lambda: BE['S74'])
    s.cell('K69', lambda: BE['U74'])
    # 70 Net non-debt creating flows (FDI) to GDP ratio
    s.cell('B70', lambda: BE['B75'])
    s.cell('D70', lambda: BE['N75'])
    s.cell('F70', lambda: BE['P75'])
    s.cell('I70', lambda: BE['S75'])
    s.cell('K70', lambda: BE['U75'])
    # 71
    s.drop(71, 'B')
    # 72 Sources: Country authorities; and staff estimates and projections.
    s.cell('B72', lambda: BE['B77'])
    # 73
    s.cell('B73', lambda: IF(START['L10'] == 'English', X('#REF!'), IF(START['L10'] == 'French', X('#REF!'), IF(START['L10'] == 'Portuguese', X('#REF!'), X('#REF!')))))
    # 74 1/ Includes both public and private sector external debt.
    s.cell('B74', lambda: BE['B79'])
    # 75 2/ Derived as [r - g - ρ(1+g) + Ɛα (1+r)]/(1+g+ρ+gρ) times previous period debt ratio, ...
    s.cell('B75', lambda: BE['B80'])
    # 76 3/ Includes exceptional financing (i.e., changes in arrears and debt relief); changes i...
    s.cell('B76', lambda: BE['B81'])
    # 77 7/ Assumes that PV of private sector debt is equivalent to its face value.
    s.cell('B77', lambda: BE['B85'])
    # 78 4/ Current-year interest payments divided by previous period debt stock.
    s.cell('B78', lambda: BE['B82'])
    # 79 8/ Historical averages are generally derived over the past 10 years, subject to data av...
    s.cell('B79', lambda: BE['B86'])
    # 80 7/ Long-run, constant balance that stabilizes the debt ratio assuming that key variable...
    s.cell('B80', lambda: A1E['B79'])
    # 81
    s.cell('B81', lambda: IF(START['L10'] == 'English', S['B130'], IF(START['L10'] == 'French', S['B162'], IF(START['L10'] == 'Portuguese', S['B194'], S['B226']))))
    # 82
    s.drop(82, 'B:X')
    # 83 Nominal debt baseline
    s.cell('B83', lambda: A1E['B82'])
    s.put(83, 'C:X', lambda c: BE[12, c+10] / 100 * BE[48, c+10])
    # 84 Increase
    s.drop(84, 'C')
    s.cell('B84', lambda: A1E['B83'])
    s.put(84, 'D:X', lambda c: S[83, c] - S[83, c-1])
    # 85 Nominal debt stress
    s.cell('B85', lambda: A1E['B84'])
    s.put(85, 'C:X', lambda c: S[12, c] / 100 * S[46, c])
    # 86 Increase
    s.cell('B86', lambda: A1E['B85'])
    s.put(86, 'D:X', lambda c: S[85, c] - S[85, c-1])
    # 87 Residual gross borrowing
    s.cell('B87', lambda: A1E['B86'])
    s.put(87, 'D:X', lambda c: S[86, c] - S[84, c])
    # 88
    s.drop(88, 'B:X')
    # 89 PV PPG baseline
    s.cell('B89', lambda: A1E['B88'])
    s.put(89, 'C:X', lambda c: EDD[391, c+2])
    # 90 PV of additional borrowing
    s.cell('B90', lambda: A1E['B89'])
    s.put(90, 'D:X', lambda c: PVS[blk + 6, c])
    # 91 PV PPG stress
    s.cell('B91', lambda: A1E['B90'])
    s.put(91, 'D:X', lambda c: S[89, c] + S[90, c])
    # 92 Private debt (=PV)
    s.cell('B92', lambda: A1E['B91'])
    s.put(92, 'D:X', lambda c: MD[12, c+17])
    # 93 PV total
    s.cell('B93', lambda: A1E['B92'])
    s.put(93, 'D:X', lambda c: S[91, c] + S[92, c])
    # 94
    s.drop(94, 'B')
    s.drop(94, 'D:X')
    # 95 Debt service baseline
    s.cell('B95', lambda: A1E['B94'])
    s.put(95, 'D:X', lambda c: MD[18, c+17] + MD[23, c+17])
    # 96 o/w interest
    s.cell('B96', lambda: A1E['B95'])
    s.put(96, 'D:X', lambda c: MD[18, c+17])
    # 97 Debt service PPG baseline
    s.cell('B97', lambda: A1E['B96'])
    s.put(97, 'D:X', lambda c: EDD[394, c+2])
    # 98
    s.drop(98, 'B')
    s.drop(98, 'E:X')
    # 99 Additional debt service stress
    s.drop(99, 'D')
    s.cell('B99', lambda: A1E['B98'])
    # 100 o/w interest
    s.cell('B100', lambda: A1E['B99'])
    s.put(100, 'D:X', lambda c: PVS[blk + 9, c])
    # 101 Total debt service stress
    s.cell('B101', lambda: A1E['B100'])
    s.put(101, 'D:X', lambda c: S[99, c] + S[95, c])
    # 102 PPG debt service stress
    s.cell('B102', lambda: A1E['B101'])
    s.put(102, 'D:X', lambda c: S[97, c] + S[99, c])
    # 103
    s.drop(103, 'B')
    s.drop(103, 'D:X')
    # 104 New interest payments
    s.cell('B104', lambda: A1E['B103'])
    s.put(104, 'D:X', lambda c: S[96, c] + S[100, c])
    # 105 Effective rate
    s.cell('B105', lambda: A1E['B104'])
    s.put(105, 'D:X', lambda c: S[104, c] / S[85, c-1] * 100)
    # 106 Exports
    s.drop(106, 'C')
    s.cell('B106', lambda: A1E['B105'])
    s.put(106, 'D:X', lambda c: S[19, c] / 100 * S[46, c])
    # 107 Revenue
    s.cell('B107', lambda: A1E['B106'])
    s.put(107, 'C:D', lambda c: BE[60, c+10] / 100 * BE[48, c+10])
    s.put(107, 'E:X', lambda c: BE[60, c+10] / 100 * S[46, c])
    # 108 Short-term debt
    s.cell('B108', lambda: A1E['B107'])
    s.put(108, 'C:X', lambda c: MD[89, c+17])


def _b6_combo_mkt_ext(s):
    """B6_Combo_mkt_ext"""
    BE = s.sheet('Baseline - external')
    LK = s.sheet('lookup')
    MD = s.sheet('Macro-Debt_Data')
    PVBM = s.sheet('PV_Base-add.cost.mkt')
    PVS = s.sheet('PV Stress')
    STD = s.sheet('Input 6(optional)-Standard Test')
    S = s.sheet(s.name)
    blk = 78
    _external_stress(s, blk)
    # 3 Bounds Test 6: Combined Shock for Market Access Countries
    s.cell('B3', lambda: TR(s, 1832))
    # 18 Deficit in balance of goods and services
    s.cell('F18', lambda: BE['P18'] - S['AA93'] * S['E43'])
    s.put(18, 'G:X', lambda c: BE[18, c+10] * BE[48, c+10] / S[46, c])
    # 19 Exports
    s.cell('E19', lambda: S['E105'] / S['E46'] * 100)
    s.put(19, 'G:X', lambda c: S[105, c] / S[46, c] * 100)
    # 20 Imports
    s.cell('F20', lambda: S['F18'] + S['F19'])
    # 21 Net current transfers (negative = inflow)
    s.cell('E21', lambda: IF(S['AA83'] == STD['C7'], MAX(-(S['D68'] - S['AA82'] * S['F68']), BE['O21'] + S['AA82'] * S['F68']), IF(S['AA83'] == STD['C5'], -(S['D68'] - S['AA82'] * S['F68']), BE['O21'] + S['AA82'] * S['F68'])))
    s.cell('F21', lambda: IF(S['E21'] == -(S['D68'] - S['AA82'] * S['F68']), -(S['D68'] - S['AA82'] * S['F68']), BE['P21'] + S['AA82'] * S['F68']))
    # 22 of which: official
    s.drop(22, 'E:F')
    # 24 Net FDI (negative = inflow)
    s.cell('E24', lambda: IF(S['AA85'] == STD['C7'], MAX(-(S['D69'] - S['AA84'] * S['F69']), BE['O24'] + S['AA84'] * S['F69']), IF(S['AA85'] == STD['C5'], -(S['D69'] - S['AA84'] * S['F69']), BE['O24'] + S['AA84'] * S['F69'])))
    s.cell('F24', lambda: IF(S['E24'] == -(S['D69'] - S['AA82'] * S['F69']), -(S['D69'] - S['AA82'] * S['F69']), BE['P24'] + S['AA82'] * S['F69']))
    # 29 Contribution from price and exchange rate changes
    s.cell('Y29', lambda: -(S['Y51'] / 100 * (1 + S['Y50'] / 100)) * S['X12'] / S['Y26'])
    # 43
    s.cell('E43', lambda: (100 + S['E58']) * (100 + MD['V112']) / (100 + MD['V109'] + S['AA92'] * S['E58'] - (BE['O52'] - S['E50']) * S['AA66']) - 100)
    # 50 Real GDP growth (in percent)
    s.cell('E50', lambda: IF(S['AA64'] == STD['C7'], MIN(S['D65'] - S['AA63'] * S['F65'], BE['O52'] - S['AA63'] * S['F65'], BE['O52'] + S['AA69'] * S['E53'] * S['D19'] / 100), IF(S['AA64'] == STD['C5'], MIN(S['D65'] - S['AA63'] * S['F65'], BE['O52'] + S['AA69'] * S['E53'] * S['D19'] / 100), MIN(BE['O52'] - S['AA63'] * S['F65'], BE['O52'] + S['AA69'] * S['E53'] * S['D19'] / 100))))
    # 51 GDP deflator in US dollar terms (change in percent)
    s.cell('E51', lambda: BE['O53'] + S['AA92'] * (BE['O59'] - S['E58']) - (BE['O52'] - S['E50']) * S['AA66'])
    s.cell('F51', lambda: BE['P53'] - (BE['P52'] - S['F50']) * S['AA66'])
    # 53 Growth of exports of G&S (US dollar terms, in percent)
    s.cell('E53', lambda: IF(S['AA70'] == STD['C7'], MIN(S['D67'] - S['AA69'] * S['F67'], BE['O55'] - S['AA69'] * S['F67']), IF(S['AA70'] == STD['C5'], S['D67'] - S['AA69'] * S['F67'], BE['O55'] - S['AA69'] * S['F67'])))
    s.cell('F53', lambda: IF(S['E53'] == S['D67'] - S['AA69'] * S['F67'], S['D67'] - S['AA69'] * S['F67'], BE['P55'] - S['AA69'] * S['F67']))
    # 58 Depreciation of NC (+: depreciation)
    s.cell('E58', lambda: S['AA90'])
    # 61 Historical
    s.drop(61, 'I')
    # 63
    s.cell('AA63', lambda: STD['D41'])
    # 64 Non-interest current account in percent of GDP
    s.cell('AA64', lambda: IF(STD['C4'] == LK['AF4'], STD['D42'], STD['C42']))
    # 66 US GDP Deflator (percent change)
    s.cell('AA66', lambda: STD['H41'])
    # 69 Net non-debt creating flows (FDI) to GDP ratio
    s.cell('AA69', lambda: STD['D44'])
    # 70
    s.cell('AA70', lambda: IF(STD['C4'] == LK['AF4'], STD['D45'], STD['C45']))
    # 72
    s.cell('AA72', lambda: STD['H44'])
    # 75 3/ Includes exceptional financing (i.e., changes in arrears and debt relief); changes i...
    s.cell('AA75', lambda: STD['D47'])
    # 76 7/ Assumes that PV of private sector debt is equivalent to its face value.
    s.cell('AA76', lambda: IF(STD['C4'] == LK['AF4'], STD['D48'], STD['C48']))
    # 78 8/ Historical averages are generally derived over the past 10 years, subject to data av...
    s.cell('AA78', lambda: STD['H47'])
    # 79 7/ Long-run, constant balance that stabilizes the debt ratio assuming that key variable...
    s.cell('AA79', lambda: STD['H48'])
    # 82 Nominal debt baseline
    s.cell('AA82', lambda: STD['D50'])
    # 83 Increase
    s.cell('AA83', lambda: IF(STD['C4'] == LK['AF4'], STD['D51'], STD['C51']))
    # 84 Nominal debt stress
    s.cell('AA84', lambda: STD['D53'])
    # 85 Increase
    s.cell('AA85', lambda: IF(STD['C4'] == LK['AF4'], STD['D54'], STD['C54']))
    # 88 PV PPG baseline
    s.cell('AA88', lambda: STD['C56'])
    # 89 PV of additional borrowing
    s.cell('AA89', lambda: IF(STD['C4'] == LK['AF4'], STD['D57'], STD['C57']))
    # 90 PV PPG stress
    s.cell('AA90', lambda: IF(STD['C4'] == LK['AF4'], STD['D58'], STD['C58']))
    # 92 PV total
    s.cell('AA92', lambda: STD['H56'])
    # 93
    s.cell('AA93', lambda: STD['H57'])
    # 98 Additional debt service stress
    s.put(98, 'E:X', lambda c: PVS[blk + 7, c] + S[111, c])
    # 99 o/w interest
    s.put(99, 'D:X', lambda c: PVS[blk + 8, c] + S[112, c])
    # 105 Exports
    s.put(105, 'E:X', lambda c: S[105, c-1] * (1 + S[53, c] / 100))
    # 111 Debt services associated with new external borrowing
    s.put(111, 'D:X', lambda c: PVBM[13, c])
    # 112 o/w: interest
    s.put(112, 'D:X', lambda c: PVBM[13, c])


def _b6_combo_non_mkt_ext(s):
    """B6_Combo_non-mkt_ext"""
    BE = s.sheet('Baseline - external')
    LK = s.sheet('lookup')
    MD = s.sheet('Macro-Debt_Data')
    START = s.sheet('START')
    STD = s.sheet('Input 6(optional)-Standard Test')
    S = s.sheet(s.name)
    blk = 95
    _external_stress(s, blk)
    # 3 Bounds Test 6: Combined Shock for Non-Market Access Countries
    s.cell('B3', lambda: TR(s, 1835))
    # 18 Deficit in balance of goods and services
    s.cell('F18', lambda: BE['P18'] - S['AA92'] * S['E43'])
    s.put(18, 'G:X', lambda c: BE[18, c+10] * BE[48, c+10] / S[46, c])
    # 19 Exports
    s.cell('E19', lambda: S['E105'] / S['E46'] * 100)
    s.put(19, 'G:X', lambda c: S[105, c] / S[46, c] * 100)
    # 20 Imports
    s.cell('F20', lambda: S['F18'] + S['F19'])
    # 21 Net current transfers (negative = inflow)
    s.cell('E21', lambda: IF(S['AA82'] == STD['C7'], MAX(-(S['D68'] - S['AA81'] * S['F68']), BE['O21'] + S['AA81'] * S['F68']), IF(S['AA82'] == STD['C5'], -(S['D68'] - S['AA81'] * S['F68']), BE['O21'] + S['AA81'] * S['F68'])))
    s.cell('F21', lambda: IF(S['E21'] == -(S['D68'] - S['AA81'] * S['F68']), -(S['D68'] - S['AA81'] * S['F68']), BE['P21'] + S['AA81'] * S['F68']))
    # 24 Net FDI (negative = inflow)
    s.cell('E24', lambda: IF(S['AA84'] == STD['C7'], MAX(-(S['D69'] - S['AA83'] * S['F69']), BE['O24'] + S['AA83'] * S['F69']), IF(S['AA84'] == STD['C5'], -(S['D69'] - S['AA83'] * S['F69']), BE['O24'] + S['AA83'] * S['F69'])))
    s.cell('F24', lambda: IF(S['E24'] == -(S['D69'] - S['AA83'] * S['F69']), -(S['D69'] - S['AA83'] * S['F69']), BE['P24'] + S['AA83'] * S['F69']))
    # 29 Contribution from price and exchange rate changes
    s.cell('Y29', lambda: -(S['Y51'] / 100 * (1 + S['Y50'] / 100)) * S['X12'] / S['Y26'])
    # 43
    s.cell('E43', lambda: (100 + S['E58']) * (100 + MD['V112']) / (100 + MD['V109'] + S['AA91'] * S['E58'] - (BE['O52'] - S['E50']) * S['AA66']) - 100)
    # 50 Real GDP growth (in percent)
    s.cell('E50', lambda: IF(S['AA64'] == STD['C7'], MIN(S['D65'] - S['AA63'] * S['F65'], BE['O52'] - S['AA63'] * S['F65'], BE['O52'] + S['AA69'] * S['E53'] * S['D19'] / 100), IF(S['AA64'] == STD['C5'], MIN(S['D65'] - S['AA63'] * S['F65'], BE['O52'] + S['AA69'] * S['E53'] * S['D19'] / 100), MIN(BE['O52'] - S['AA63'] * S['F65'], BE['O52'] + S['AA69'] * S['E53'] * S['D19'] / 100))))
    # 51 GDP deflator in US dollar terms (change in percent)
    s.cell('E51', lambda: BE['O53'] + S['AA91'] * (BE['O59'] - S['E58']) - (BE['O52'] - S['E50']) * S['AA66'])
    s.cell('F51', lambda: BE['P53'] - (BE['P52'] - S['F50']) * S['AA66'])
    # 53 Growth of exports of G&S (US dollar terms, in percent)
    s.cell('E53', lambda: IF(S['AA70'] == STD['C7'], MIN(S['D67'] - S['AA69'] * S['F67'], BE['O55'] - S['AA69'] * S['F67']), IF(S['AA70'] == STD['C5'], S['D67'] - S['AA69'] * S['F67'], BE['O55'] - S['AA69'] * S['F67'])))
    s.cell('F53', lambda: IF(S['E53'] == S['D67'] - S['AA69'] * S['F67'], S['D67'] - S['AA69'] * S['F67'], BE['P55'] - S['AA69'] * S['F67']))
    # 58 Depreciation of NC (+: depreciation)
    s.cell('E58', lambda: S['AA89'])
    # 61 Historical
    s.drop(61, 'I')
    # 63
    s.cell('AA63', lambda: STD['D41'])
    # 64 Non-interest current account in percent of GDP
    s.cell('AA64', lambda: IF(STD['C4'] == LK['AF4'], STD['D42'], STD['C42']))
    # 66 US GDP Deflator (percent change)
    s.cell('AA66', lambda: STD['H41'])
    # 69 Net non-debt creating flows (FDI) to GDP ratio
    s.cell('AA69', lambda: STD['D44'])
    # 70
    s.cell('AA70', lambda: IF(STD['C4'] == LK['AF4'], STD['D45'], STD['C45']))
    # 72
    s.cell('AA72', lambda: STD['H44'])
    # 75 3/ Includes exceptional financing (i.e., changes in arrears and debt relief); changes i...
    s.cell('AA75', lambda: STD['D47'])
    # 76 7/ Assumes that PV of private sector debt is equivalent to its face value.
    s.cell('AA76', lambda: IF(STD['C4'] == LK['AF4'], STD['D48'], STD['C48']))
    # 78 8/ Historical averages are generally derived over the past 10 years, subject to data av...
    s.cell('AA78', lambda: STD['H47'])
    # 80
    s.cell('B80', lambda: IF(START['L10'] == 'English', S['B129'], IF(START['L10'] == 'French', S['B161'], IF(START['L10'] == 'Portuguese', S['B193'], S['B225']))))
    # 81
    s.cell('AA81', lambda: STD['D50'])
    # 82 Nominal debt baseline
    s.cell('AA82', lambda: IF(STD['C4'] == LK['AF4'], STD['D51'], STD['C51']))
    # 83 Increase
    s.cell('AA83', lambda: STD['D53'])
    # 84 Nominal debt stress
    s.cell('AA84', lambda: IF(STD['C4'] == LK['AF4'], STD['D54'], STD['C54']))
    # 87
    s.cell('AA87', lambda: STD['C56'])
    # 88 PV PPG baseline
    s.cell('AA88', lambda: IF(STD['C4'] == LK['AF4'], STD['D57'], STD['C57']))
    # 89 PV of additional borrowing
    s.cell('AA89', lambda: IF(STD['C4'] == LK['AF4'], STD['D58'], STD['C58']))
    # 91 Private debt (=PV)
    s.cell('AA91', lambda: STD['H56'])
    # 92 PV total
    s.cell('AA92', lambda: STD['H57'])
    # 97
    s.cell('D97', lambda: (S['D94'] - S['D96']) / S['D107'] * 100)
    # 105 Exports
    s.put(105, 'E:X', lambda c: S[105, c-1] * (1 + S[53, c] / 100))


def _c3_commodity_prices_ext(s):
    """C3_Commodity prices_ext"""
    A1E = s.sheet('A1_historical_ext')
    BE = s.sheet('Baseline - external')
    EDD = s.sheet('Ext_Debt_Data')
    MD = s.sheet('Macro-Debt_Data')
    PVS = s.sheet('PV Stress')
    START = s.sheet('START')
    TRS = s.sheet('translation')
    TT = s.sheet('Input 6 - Tailored Tests')
    S = s.sheet(s.name)
    LANG = s.name_('LANG')
    blk = 129
    _external_stress(s, blk)
    # column B of these rows repeats the same cells of Baseline - external
    s.same(BE, 'B', [77, 79, 80, 81])
    # 3 Tailored Stress Test 3. Commodity Price shock -External
    s.cell('B3', lambda: TRS.offset(1894, 'C', 0, LANG))
    # 14 of which: Private
    s.put(14, 'E:X', lambda c: BE[12, c+10] - BE[13, c+10])
    # 18 Deficit in balance of goods and services
    s.put(18, 'G:X', lambda c: BE[18, c+10])
    # 19 Exports
    s.cell('E19', lambda: S['E111'] / S['E46'] * 100)
    s.cell('F19', lambda: BE['P19'] - (BE['O19'] - S['E19']) * (S['AA63'] - 1) / S['AA63'])
    s.cell('G19', lambda: BE['Q19'] - (BE['O19'] - S['E19']) * (S['AA63'] - 2) / S['AA63'])
    s.cell('H19', lambda: BE['R19'] - (BE['O19'] - S['E19']) * (S['AA63'] - 3) / S['AA63'])
    s.cell('I19', lambda: BE['S19'] - (BE['O19'] - S['E19']) * (S['AA63'] - 4) / S['AA63'])
    s.cell('J19', lambda: BE['T19'] - (BE['O19'] - S['E19']) * (S['AA63'] - 5) / S['AA63'])
    s.put(19, 'K:X', lambda c: S[111, c] / S[46, c] * 100)
    # 33 PV of external debt 7/
    s.put(33, 'E:X', lambda c: S[98, c] / S[46, c] * 100)
    # 35 PV of PPG external debt-to-GDP ratio
    s.put(35, 'E:X', lambda c: S[96, c] / S[46, c] * 100)
    # 37 PV of PPG external debt-to-revenue ratio
    s.put(37, 'C:X', lambda c: S[35, c] * S[46, c] / S[112, c])
    # 38 Total external debt service-to-exports ratio
    s.put(38, 'E:X', lambda c: S[106, c] / S[111, c] * 100)
    # 39 PPG debt service-to-exports ratio
    s.put(39, 'E:X', lambda c: S[107, c] / S[111, c] * 100)
    # 40 PPG debt service-to-revenue ratio
    s.put(40, 'E:X', lambda c: S[107, c] / S[112, c] * 100)
    # 41 Gross external financing need (Million of U.S. dollars)
    s.put(41, 'E:X', lambda c: (S[17, c] + S[24, c]) / 100 * S[46, c] + S[106, c] + S[113, c-1])
    # 48 PV of PPG external debt (in Million of US dollars)
    s.cell('C48', lambda: S['C94'])
    s.put(48, 'D:X', lambda c: S[96, c])
    # 50 Real GDP growth (in percent)
    s.put(50, 'E:G', lambda c: BE[52, c+10] - S['AA65'])
    s.cell('H50', lambda: BE['R52'] - S['AA65'] * (S['AA63'] - 3) / (S['AA63'] - 2))
    s.cell('I50', lambda: BE['S52'] - S['AA65'] * (S['AA63'] - 4) / (S['AA63'] - 2))
    s.cell('J50', lambda: BE['T52'] - S['AA65'] * (S['AA63'] - 5) / (S['AA63'] - 2))
    # 51 GDP deflator in US dollar terms (change in percent)
    s.cell('E51', lambda: BE['O53'] * (1 - S['AA68'] * (S['D19'] / 100) * -S['AA76']))
    s.cell('F51', lambda: BE['P53'] - (BE['O53'] - S['E51']) * (S['AA63'] - 1) / S['AA63'])
    s.cell('G51', lambda: BE['Q53'] - (BE['O53'] - S['E51']) * (S['AA63'] - 2) / S['AA63'])
    s.cell('H51', lambda: BE['R53'] - (BE['O53'] - S['E51']) * (S['AA63'] - 3) / S['AA63'])
    s.cell('I51', lambda: BE['S53'] - (BE['O53'] - S['E51']) * (S['AA63'] - 4) / S['AA63'])
    s.cell('J51', lambda: BE['T53'] - (BE['O53'] - S['E51']) * (S['AA63'] - 5) / S['AA63'])
    # 52 Effective interest rate (percent) 4/
    s.put(52, 'E:X', lambda c: S[110, c])
    # 59 Government revenues (excluding grants, in percent of GDP)
    s.put(59, 'C:X', lambda c: S[112, c] / S[46, c] * 100)
    # 61 Historical
    s.drop(61, 'I')
    # 62 III. Averages and Standard Deviations 9/
    s.drop(62, 'M')
    # 63
    s.cell('AA63', lambda: TT['H26'])
    # 64 Non-interest current account in percent of GDP
    s.drop(64, 'M')
    # 65 Real GDP growth (in percent)
    s.drop(65, 'M')
    s.cell('AA65', lambda: TT['L26'])
    # 66 US GDP Deflator (percent change)
    s.drop(66, 'M')
    s.cell('AA66', lambda: TT['L27'])
    # 67 Growth of exports of G&S (US dollar terms, in percent)
    s.drop(67, 'M')
    # 68 Current official transfers in percent of GDP
    s.drop(68, 'M')
    s.cell('AA68', lambda: TT['H30'])
    # 69 Net non-debt creating flows (FDI) to GDP ratio
    s.drop(69, 'M')
    # 70
    s.cell('AA70', lambda: TT['H32'])
    # 71
    s.drop(71, 'B')
    s.cell('AA71', lambda: TT['H34'])
    # 73
    s.drop(73, 'B')
    s.cell('AA73', lambda: TT['H36'])
    # 74
    s.drop(74, 'B')
    s.cell('AA74', lambda: TT['H44'])
    # 75
    s.drop(75, 'B')
    # 76
    s.drop(76, 'B')
    s.cell('AA76', lambda: TT['H46'])
    # 77 Sources: Country authorities; and staff estimates and projections.
    # 78
    s.drop(78, 'B')
    # 79 1/ Includes both public and private sector external debt.
    # 80 2/ Derived as [r - g - ρ(1+g) + Ɛα (1+r)]/(1+g+ρ+gρ) times previous period debt ratio, ...
    # 81 3/ Includes exceptional financing (i.e., changes in arrears and debt relief); changes i...
    # 82 7/ Assumes that PV of private sector debt is equivalent to its face value.
    s.drop(82, 'C:X')
    s.cell('B82', lambda: BE['B85'])
    # 83 4/ Current-year interest payments divided by previous period debt stock.
    s.drop(83, 'D:X')
    s.cell('B83', lambda: BE['B82'])
    # 84 8/ Historical averages are generally derived over the past 10 years, subject to data av...
    s.drop(84, 'C:X')
    s.cell('B84', lambda: BE['B86'])
    # 85 7/ Long-run, constant balance that stabilizes the debt ratio assuming that key variable...
    s.drop(85, 'D:X')
    s.cell('B85', lambda: A1E['B79'])
    # 86
    s.drop(86, 'D:X')
    s.cell('B86', lambda: IF(START['L10'] == 'English', S['B124'], IF(START['L10'] == 'French', S['B156'], IF(START['L10'] == 'Portuguese', S['B188'], S['B220']))))
    # 88 Nominal debt baseline
    s.cell('B88', lambda: A1E['B82'])
    s.put(88, 'C:X', lambda c: BE[12, c+10] / 100 * BE[48, c+10])
    # 89 Increase
    s.cell('B89', lambda: A1E['B83'])
    s.put(89, 'D:X', lambda c: S[88, c] - S[88, c-1])
    # 90 Nominal debt stress
    s.cell('B90', lambda: A1E['B84'])
    s.put(90, 'C:X', lambda c: S[12, c] / 100 * S[46, c])
    # 91 Increase
    s.cell('B91', lambda: A1E['B85'])
    s.put(91, 'D:X', lambda c: S[90, c] - S[90, c-1])
    # 92 Residual gross borrowing
    s.cell('B92', lambda: A1E['B86'])
    s.put(92, 'D:X', lambda c: S[91, c] - S[89, c])
    # 94 PV PPG baseline
    s.cell('B94', lambda: A1E['B88'])
    s.put(94, 'C:X', lambda c: EDD[391, c+2])
    # 95 PV of additional borrowing
    s.cell('B95', lambda: A1E['B89'])
    s.put(95, 'D:X', lambda c: PVS[blk + 5, c])
    # 96 PV PPG stress
    s.cell('B96', lambda: A1E['B90'])
    s.put(96, 'D:X', lambda c: S[94, c] + S[95, c])
    # 97 Private debt (=PV)
    s.cell('B97', lambda: A1E['B91'])
    s.put(97, 'D:X', lambda c: MD[12, c+17])
    # 98 PV total
    s.cell('B98', lambda: A1E['B92'])
    s.put(98, 'D:X', lambda c: S[96, c] + S[97, c])
    # 99
    s.drop(99, 'B')
    s.drop(99, 'D:X')
    # 100 Debt service baseline
    s.cell('B100', lambda: A1E['B94'])
    s.put(100, 'D:X', lambda c: MD[18, c+17] + MD[23, c+17])
    # 101 o/w interest
    s.cell('B101', lambda: A1E['B95'])
    s.put(101, 'D:X', lambda c: MD[18, c+17])
    # 102 Debt service PPG baseline
    s.cell('B102', lambda: A1E['B96'])
    s.put(102, 'D:X', lambda c: EDD[394, c+2])
    # 103
    s.drop(103, 'B')
    s.drop(103, 'D:X')
    # 104 Additional debt service stress
    s.cell('B104', lambda: A1E['B98'])
    s.put(104, 'D:X', lambda c: PVS[blk + 7, c])
    # 105 o/w interest
    s.cell('B105', lambda: A1E['B99'])
    s.put(105, 'D:X', lambda c: PVS[blk + 8, c])
    # 106 Total debt service stress
    s.drop(106, 'C')
    s.cell('B106', lambda: A1E['B100'])
    s.put(106, 'D:X', lambda c: S[104, c] + S[100, c])
    # 107 PPG debt service stress
    s.drop(107, 'C')
    s.cell('B107', lambda: A1E['B101'])
    s.put(107, 'D:X', lambda c: S[102, c] + S[104, c])
    # 109 New interest payments
    s.cell('B109', lambda: A1E['B103'])
    s.put(109, 'D:X', lambda c: S[101, c] + S[105, c])
    # 110 Effective rate
    s.cell('B110', lambda: A1E['B104'])
    s.put(110, 'D:X', lambda c: S[109, c] / S[90, c-1] * 100)
    # 111 Exports
    s.cell('B111', lambda: A1E['B105'])
    s.put(111, 'C:D', lambda c: S[19, c] / 100 * S[46, c])
    s.cell('E111', lambda: MD['V29'] * (1 + (S['AA68'] * S['AA73'] * S['AA74'] + S['AA68'] * S['AA70'] * S['AA71'])))
    s.put(111, 'F:J', lambda c: S[19, c] / 100 * S[46, c])
    s.put(111, 'K:X', lambda c: S[111, c-1] * (1 + S[53, c] / 100))
    # 112 Revenue
    s.cell('B112', lambda: A1E['B106'])
    s.put(112, 'C:D', lambda c: BE[60, c+10] / 100 * BE[48, c+10])
    s.put(112, 'E:J', lambda c: S[118, c] / 100 * S[46, c])
    s.put(112, 'K:X', lambda c: BE[60, c+10] / 100 * S[46, c])
    # 113 Short-term debt
    s.cell('B113', lambda: A1E['B107'])
    s.put(113, 'C:X', lambda c: MD[89, c+17])
    # 116 Export/GDP (baseline)
    s.put(116, 'C:X', lambda c: MD[29, c+17] / MD[56, c+17] * 100)
    # 117 Revenue/GDP (baseline)
    s.put(117, 'C:X', lambda c: BE[60, c+10])
    # 118 Revenue/GDP (stress)
    s.put(118, 'C:D', lambda c: S[117, c])
    s.put(118, 'E:G', lambda c: BE[60, c+10] - S['AA66'])
    s.cell('H118', lambda: BE['R60'] - S['AA66'] * (S['AA63'] - 3) / (S['AA63'] - 2))
    s.cell('I118', lambda: BE['S60'] - S['AA66'] * (S['AA63'] - 4) / (S['AA63'] - 2))
    s.cell('J118', lambda: BE['T60'] - S['AA66'] * (S['AA63'] - 5) / (S['AA63'] - 2))
    s.put(118, 'K:X', lambda c: S[117, c])


def _c4_market_financing(s):
    """C4_Market_financing"""
    BE = s.sheet('Baseline - external')
    EDD = s.sheet('Ext_Debt_Data')
    IN4 = s.sheet('Input 4 - External Financing')
    MD = s.sheet('Macro-Debt_Data')
    PVBC = s.sheet('PV_baseline_com')
    PVS = s.sheet('PV Stress')
    PVSC = s.sheet('PV_stress_com')
    TRS = s.sheet('translation')
    TT = s.sheet('Input 6 - Tailored Tests')
    S = s.sheet(s.name)
    LANG = s.name_('LANG')
    blk = 145
    _external_stress(s, blk)
    # 3 Tailored stress test 4: Market Financing Stress Test
    s.cell('B3', lambda: TRS.offset(1901, 'C', 0, LANG))
    # 10 I. Macro indicators
    s.drop(10, 'B')
    # 12 Nominal GDP (Million of US dollars)
    s.cell('B12', lambda: BE['B48'])
    s.put(12, 'C:D', lambda c: BE[48, c+10])
    s.put(12, 'E:X', lambda c: S[12, c-1] * (1 + S[14, c] / 100) * (1 + S[15, c] / 100))
    # 13 Nominal dollar GDP growth
    s.drop(13, 'C')
    s.cell('B13', lambda: BE['B49'])
    s.put(13, 'D:X', lambda c: (S[12, c] / S[12, c-1] - 1) * 100)
    # 14 Real GDP growth (in percent)
    s.cell('B14', lambda: BE['B52'])
    s.put(14, 'C:X', lambda c: BE[52, c+10])
    s.cell('Y14', lambda: S['X14'])
    # 15 GDP deflator in US dollar terms (change in percent)
    s.cell('B15', lambda: BE['B53'])
    s.put(15, 'C:D', lambda c: BE[53, c+10])
    s.cell('E15', lambda: IF(S['AB20'] == 1, BE['O53'] + (S['AB23'] - 1) * S['E18'], BE['O53']))
    s.put(15, 'F:X', lambda c: BE[53, c+10])
    s.cell('Y15', lambda: S['X15'])
    # 16 Growth of exports of G&S (US dollar terms, in percent)
    s.drop(16, 'Y')
    s.cell('B16', lambda: BE['B55'])
    s.put(16, 'C:X', lambda c: BE[55, c+10])
    # 17 Current transfers, net total
    s.drop(17, 'Y')
    s.cell('B17', lambda: BE['B57'])
    s.put(17, 'C:X', lambda c: BE[57, c+10])
    # 18 Depreciation of NC (+: depreciation)
    s.cell('B18', lambda: BE['B59'])
    s.put(18, 'C:D', lambda c: BE[59, c+10])
    s.cell('E18', lambda: BE['O59'] * 0 + S['AB22'])
    s.put(18, 'F:X', lambda c: BE[59, c+10])
    # 19
    s.drop(19, 'B:X')
    # 20 Historical
    s.drop(20, 'B:X')
    s.cell('AB20', lambda: IF(SUM(EDD.rng(99, 'F', 99, 'Z')) > 0, 1, 0))
    # 21 II. Averages and Standard Deviations
    s.drop(21, 'B:H')
    s.drop(21, 'J')
    s.drop(21, 'L:X')
    s.cell('I21', lambda: BE['S68'])
    s.cell('K21', lambda: BE['U68'])
    # 22
    s.drop(22, 'B:X')
    s.cell('AB22', lambda: TT['H58'])
    # 23 Non-interest current account in percent of GDP
    s.drop(23, 'C')
    s.drop(23, 'E')
    s.drop(23, 'G:H')
    s.drop(23, 'J')
    s.drop(23, 'L:X')
    s.cell('B23', lambda: BE['B70'])
    s.cell('D23', lambda: BE['N70'])
    s.cell('F23', lambda: BE['P70'])
    s.cell('I23', lambda: BE['S70'])
    s.cell('K23', lambda: BE['U70'])
    s.cell('AB23', lambda: TT['L58'])
    # 24 Real GDP growth (in percent)
    s.drop(24, 'C')
    s.drop(24, 'E')
    s.drop(24, 'G:H')
    s.drop(24, 'J')
    s.drop(24, 'L:Y')
    s.cell('B24', lambda: BE['B71'])
    s.cell('D24', lambda: BE['N71'])
    s.cell('F24', lambda: BE['P71'])
    s.cell('I24', lambda: BE['S71'])
    s.cell('K24', lambda: BE['U71'])
    # 25 US GDP Deflator (percent change)
    s.drop(25, 'C')
    s.drop(25, 'E')
    s.drop(25, 'G:H')
    s.drop(25, 'J')
    s.drop(25, 'L:Y')
    s.cell('B25', lambda: BE['B72'])
    s.cell('D25', lambda: BE['N72'])
    s.cell('F25', lambda: BE['P72'])
    s.cell('I25', lambda: BE['S72'])
    s.cell('K25', lambda: BE['U72'])
    s.cell('AB25', lambda: TT['H52'])
    # 26 Growth of exports of G&S (US dollar terms, in percent)
    s.drop(26, 'C')
    s.drop(26, 'E')
    s.drop(26, 'G:H')
    s.drop(26, 'J')
    s.drop(26, 'L:Y')
    s.cell('B26', lambda: BE['B73'])
    s.cell('D26', lambda: BE['N73'])
    s.cell('F26', lambda: BE['P73'])
    s.cell('I26', lambda: BE['S73'])
    s.cell('K26', lambda: BE['U73'])
    # 27 Current official transfers in percent of GDP
    s.drop(27, 'C')
    s.drop(27, 'E')
    s.drop(27, 'G:H')
    s.drop(27, 'J')
    s.drop(27, 'L:Y')
    s.cell('B27', lambda: BE['B74'])
    s.cell('D27', lambda: BE['N74'])
    s.cell('F27', lambda: BE['P74'])
    s.cell('I27', lambda: BE['S74'])
    s.cell('K27', lambda: BE['U74'])
    s.cell('AA27', lambda: TT['C53'])
    # 28 Net non-debt creating flows (FDI) to GDP ratio
    s.drop(28, 'C')
    s.drop(28, 'E')
    s.drop(28, 'G:H')
    s.drop(28, 'J')
    s.drop(28, 'L:Y')
    s.cell('B28', lambda: BE['B75'])
    s.cell('D28', lambda: BE['N75'])
    s.cell('F28', lambda: BE['P75'])
    s.cell('I28', lambda: BE['S75'])
    s.cell('K28', lambda: BE['U75'])
    s.cell('AA28', lambda: TT['C54'])
    s.cell('AB28', lambda: TT['H54'])
    # 29
    s.drop(29, 'B:Y')
    s.cell('AA29', lambda: TT['C55'])
    s.cell('AB29', lambda: TT['H55'])
    # 30
    s.drop(30, 'B:X')
    s.cell('AA30', lambda: TT['C56'])
    s.cell('AB30', lambda: TT['H56'])
    # 33 Grace period
    s.drop(33, 'B')
    s.drop(33, 'E:X')
    s.put(33, 'C:D', lambda c: IN4[6, c+4])
    # 34 Bullet (1) or Amort. (>1)
    s.drop(34, 'B:X')
    # 35 Eurobond
    s.drop(35, 'J')
    s.drop(35, 'L:X')
    s.cell('B35', lambda: IN4['B38'])
    s.put(35, 'C:D', lambda c: IN4[38, c+4])
    s.cell('E35', lambda: IF(S['D35'] - S['C35'] <= 1, 1, 0))
    s.cell('F35', lambda: IF(S['D35'] > 5, S['AB28'], S['AB29'] * S['D35']))
    s.cell('G35', lambda: IF(S['E35'] == 1, S['F35'] - 1, MIN(S['AB30'] * S['F35'], S['C35'])))
    s.put(35, 'H:I', lambda c: ROUNDDOWN(S[35, c-2], 0))
    s.cell('K35', lambda: PVSC['B24'])
    # 36 Commecial Bank
    s.drop(36, 'J')
    s.drop(36, 'L:X')
    s.cell('B36', lambda: IN4['B39'])
    s.put(36, 'C:D', lambda c: IN4[39, c+4])
    s.cell('E36', lambda: IF(S['D36'] - S['C36'] <= 1, 1, 0))
    s.cell('F36', lambda: IF(S['D36'] > 5, S['AB28'], S['AB29'] * S['D36']))
    s.cell('G36', lambda: IF(S['E36'] == 1, S['F36'] - 1, MIN(S['AB30'] * S['F36'], S['C36'])))
    s.put(36, 'H:I', lambda c: ROUNDDOWN(S[36, c-2], 0))
    s.cell('K36', lambda: PVSC['B50'])
    # 37 COM3
    s.drop(37, 'J')
    s.drop(37, 'L:X')
    s.cell('B37', lambda: IN4['B40'])
    s.put(37, 'C:D', lambda c: IN4[40, c+4])
    s.cell('E37', lambda: IF(S['D37'] - S['C37'] <= 1, 1, 0))
    s.cell('F37', lambda: IF(S['D37'] > 5, S['AB28'], S['AB29'] * S['D37']))
    s.cell('G37', lambda: IF(S['E37'] == 1, S['F37'] - 1, MIN(S['AB30'] * S['F37'], S['C37'])))
    s.put(37, 'H:I', lambda c: ROUNDDOWN(S[37, c-2], 0))
    s.cell('K37', lambda: PVSC['B76'])
    # 38 COM4
    s.drop(38, 'J')
    s.drop(38, 'L:X')
    s.cell('B38', lambda: IN4['B41'])
    s.put(38, 'C:D', lambda c: IN4[41, c+4])
    s.cell('E38', lambda: IF(S['D38'] - S['C38'] <= 1, 1, 0))
    s.cell('F38', lambda: IF(S['D38'] > 5, S['AB28'], S['AB29'] * S['D38']))
    s.cell('G38', lambda: IF(S['E38'] == 1, S['F38'] - 1, MIN(S['AB30'] * S['F38'], S['C38'])))
    s.put(38, 'H:I', lambda c: ROUNDDOWN(S[38, c-2], 0))
    s.cell('K38', lambda: PVSC['B102'])
    # 39 COM5
    s.drop(39, 'J')
    s.drop(39, 'L:X')
    s.cell('B39', lambda: IN4['B42'])
    s.put(39, 'C:D', lambda c: IN4[42, c+4])
    s.cell('E39', lambda: IF(S['D39'] - S['C39'] <= 1, 1, 0))
    s.cell('F39', lambda: IF(S['D39'] > 5, S['AB28'], S['AB29'] * S['D39']))
    s.cell('G39', lambda: IF(S['E39'] == 1, S['F39'] - 1, MIN(S['AB30'] * S['F39'], S['C39'])))
    s.put(39, 'H:I', lambda c: ROUNDDOWN(S[39, c-2], 0))
    s.cell('K39', lambda: PVSC['B128'])
    # 40
    s.drop(40, 'B:X')
    # 41 Average lending terms used for residual financing
    s.drop(41, 'B:E')
    s.drop(41, 'J')
    s.drop(41, 'L:X')
    s.put(41, 'F:G', lambda c: IF(S['I48'] == 0, 0, (S[35, c] * S['I49'] + S[36, c] * S['I50'] + S[37, c] * S['I51'] + S[38, c] * S['I52'] + S[39, c] * S['I53']) / S['I48']))
    s.put(41, 'H:I', lambda c: ROUNDDOWN(S[41, c-2], 0))
    s.cell('K41', lambda: IF(S['I48'] == 0, 0, (S['K35'] * S['I49'] + S['K36'] * S['I50'] + S['K37'] * S['I51'] + S['K38'] * S['I52'] + S['K39'] * S['I53']) / S['I48']))
    # 44
    s.drop(44, 'B')
    # 46
    s.drop(46, 'B:X')
    # 47 New borrowing
    s.drop(47, 'B')
    s.drop(47, 'D:X')
    # 48 Total Commercial
    s.drop(48, 'B:D')
    s.drop(48, 'H')
    s.drop(48, 'J:X')
    s.cell('A48', lambda: 'Total ' & IN4['B37'])
    s.put(48, 'E:G', lambda c: SUM(S.rng(49, c, 53, c)))
    s.cell('I48', lambda: SUM(S.rng(48, 'E', 48, 'G')))
    # 49 Eurobond
    s.drop(49, 'B')
    s.drop(49, 'D')
    s.drop(49, 'H')
    s.drop(49, 'J:X')
    s.cell('A49', lambda: IN4['B38'])
    s.put(49, 'E:G', lambda c: EDD[100, c+2])
    s.cell('I49', lambda: SUM(S.rng(49, 'E', 49, 'G')))
    # 50 Commecial Bank
    s.drop(50, 'B:D')
    s.drop(50, 'H')
    s.drop(50, 'J:Y')
    s.cell('A50', lambda: IN4['B39'])
    s.put(50, 'E:G', lambda c: EDD[101, c+2])
    s.cell('I50', lambda: SUM(S.rng(50, 'E', 50, 'G')))
    # 51 COM3
    s.drop(51, 'B:D')
    s.drop(51, 'H')
    s.drop(51, 'J:Y')
    s.cell('A51', lambda: IN4['B40'])
    s.put(51, 'E:G', lambda c: EDD[102, c+2])
    s.cell('I51', lambda: SUM(S.rng(51, 'E', 51, 'G')))
    # 52 COM4
    s.drop(52, 'B:D')
    s.drop(52, 'H')
    s.drop(52, 'J:Y')
    s.cell('A52', lambda: IN4['B41'])
    s.put(52, 'E:G', lambda c: EDD[103, c+2])
    s.cell('I52', lambda: SUM(S.rng(52, 'E', 52, 'G')))
    # 53 COM5
    s.drop(53, 'B:D')
    s.drop(53, 'H')
    s.drop(53, 'J:X')
    s.cell('A53', lambda: IN4['B42'])
    s.put(53, 'E:G', lambda c: EDD[104, c+2])
    s.cell('I53', lambda: SUM(S.rng(53, 'E', 53, 'G')))
    # 54
    s.drop(54, 'B:X')
    # 55 Commercial financing (shock years) - Baseline
    s.drop(55, 'B:X')
    # 56
    s.drop(56, 'B:X')
    # 57 Total commercial
    s.cell('A57', lambda: PVBC['A8'])
    # 58 Stock of new forex debt (in USD)
    s.drop(58, 'B:D')
    s.cell('A58', lambda: PVBC['A9'])
    s.put(58, 'E:X', lambda c: PVBC[9, c])
    # 59 PV of debt
    s.drop(59, 'B:D')
    s.cell('A59', lambda: PVBC['A10'])
    s.put(59, 'E:X', lambda c: PVBC[10, c])
    # 60 Total debt service (in USD)
    s.cell('A60', lambda: PVBC['A11'])
    s.put(60, 'E:X', lambda c: PVBC[11, c])
    # 61 Interest
    s.cell('A61', lambda: PVBC['A12'])
    s.put(61, 'E:X', lambda c: PVBC[12, c])
    s.cell('Z61', lambda: SUM(S.rng(61, 'E', 61, 'X')))
    s.cell('AA61', lambda: SUM(S.rng(61, 'E', 61, 'L')))
    # 62 Amortization
    s.drop(62, 'B')
    s.cell('A62', lambda: PVBC['A13'])
    s.put(62, 'E:X', lambda c: PVBC[13, c])
    s.cell('Z62', lambda: SUM(S.rng(62, 'E', 62, 'X')))
    # 64 Commercial financing (shock years) - Stress tests
    s.drop(64, 'B')
    s.drop(64, 'D')
    s.drop(64, 'F')
    s.drop(64, 'I')
    s.drop(64, 'K')
    s.drop(64, 'M')
    # 65
    s.drop(65, 'B')
    s.drop(65, 'D')
    s.drop(65, 'F')
    s.drop(65, 'I')
    s.drop(65, 'K')
    s.drop(65, 'M')
    # 66 Total commercial
    s.drop(66, 'B')
    s.drop(66, 'D')
    s.drop(66, 'F')
    s.drop(66, 'I')
    s.drop(66, 'K')
    s.drop(66, 'M')
    s.cell('A66', lambda: S['A57'])
    # 67 Stock of new forex debt (in USD)
    s.drop(67, 'B')
    s.drop(67, 'D')
    s.cell('A67', lambda: S['A58'])
    s.put(67, 'E:X', lambda c: PVSC[12, c])
    # 68 PV of debt
    s.drop(68, 'B')
    s.drop(68, 'D')
    s.cell('A68', lambda: S['A59'])
    s.put(68, 'E:X', lambda c: PVSC[13, c])
    # 69 Total debt service (in USD)
    s.drop(69, 'B')
    s.drop(69, 'D')
    s.cell('A69', lambda: S['A60'])
    s.put(69, 'E:X', lambda c: PVSC[14, c])
    # 70 Interest
    s.cell('A70', lambda: S['A61'])
    s.put(70, 'E:X', lambda c: PVSC[15, c])
    s.cell('Z70', lambda: SUM(S.rng(70, 'E', 70, 'X')))
    s.cell('AA70', lambda: SUM(S.rng(70, 'E', 70, 'L')))
    # 71 Amortization
    s.drop(71, 'B')
    s.cell('A71', lambda: S['A62'])
    s.put(71, 'E:X', lambda c: PVSC[16, c])
    s.cell('Z71', lambda: SUM(S.rng(71, 'E', 71, 'X')))
    # 73 Increase in external gross financing needs
    s.drop(73, 'B')
    s.put(73, 'E:X', lambda c: S[69, c] - S[60, c])
    # 74
    s.drop(74, 'B')
    # 75 PV of residual financing
    s.drop(75, 'B')
    s.put(75, 'E:X', lambda c: PVS[blk + 5, c] + PVS[blk + 19, c])
    # 76
    s.drop(76, 'B')
    # 77 Adjustments to PV of debt
    s.drop(77, 'B')
    s.put(77, 'E:X', lambda c: S[68, c] - S[59, c] + S[75, c])
    # 78 Baseline PV of debt
    s.drop(78, 'B')
    s.put(78, 'D:X', lambda c: EDD[391, c+2])
    # 79 (in percent of GDP)
    s.drop(79, 'B')
    s.put(79, 'D:X', lambda c: S[78, c] / BE[48, c+10] * 100)
    # 80 (in percent of exports)
    s.put(80, 'D:X', lambda c: S[78, c] / S[85, c] * 100)
    # 81 Revised PV of debt
    s.put(81, 'D:X', lambda c: S[78, c] + S[77, c])
    # 82 (in percent of GDP)
    s.drop(82, 'B:C')
    s.put(82, 'D:X', lambda c: S[81, c] / S[84, c] * 100)
    # 83 (in percent of exports)
    s.drop(83, 'B')
    s.put(83, 'D:X', lambda c: S[81, c] / S[85, c] * 100)
    # 84 Nominal GDP under the stress test
    s.drop(84, 'B:C')
    s.put(84, 'D:X', lambda c: S[12, c])
    # 85 Exports under the baseline / stress test
    s.drop(85, 'B')
    s.put(85, 'D:X', lambda c: MD[29, c+17])
    # 86
    s.drop(86, 'B')
    s.drop(86, 'D:X')
    # 88 Baeline debt service
    s.drop(88, 'B:C')
    s.put(88, 'D:X', lambda c: MD[19, c+17] + MD[24, c+17])
    # 89 Adjustment to debt service
    s.drop(89, 'B')
    s.put(89, 'D:X', lambda c: S[69, c] - S[60, c] + PVS[blk + 7, c] + PVS[blk + 21, c])
    # 90 Adjusted debt service
    s.drop(90, 'B')
    # 91
    s.drop(91, 'B')
    s.drop(91, 'D:X')
    # 92
    s.drop(92, 'B')
    s.drop(92, 'D:X')
    # 93 Exports
    s.put(93, 'D:X', lambda c: MD[29, c+17])
    # 94 Revenue (excluding grants)
    s.drop(94, 'B')
    s.put(94, 'D:X', lambda c: BE[60, c+10] / 100 * BE[48, c+10])
    # 95 Revised PV of debt to Exports
    s.drop(95, 'B')
    s.cell('A95', lambda: S['A81'] & ' to ' & S['A93'])
    s.cell('D95', lambda: BE['N36'])
    s.put(95, 'E:X', lambda c: (S[78, c] + S[77, c]) / S[93, c] * 100)
    # 96 Debt service to exports ratio - stress test
    s.drop(96, 'B')
    s.put(96, 'D:X', lambda c: S[90, c] / S[93, c] * 100)
    # 97 Debt service to exports ratio - baseline
    s.put(97, 'D:X', lambda c: BE[39, c+10])
    # 98
    s.drop(98, 'B')
    s.put(98, 'E:X', lambda c: IF(S[97, c] > S[96, c], 1, ''))
    # 99 Debt service to revenue ratio -stress test
    s.drop(99, 'B')
    s.put(99, 'D:X', lambda c: S[90, c] / S[94, c] * 100)
    # 100 Debt service to revenue ratio - baseline
    s.drop(100, 'B')
    s.put(100, 'D:X', lambda c: BE[40, c+10])
    # 101
    s.drop(101, 'B')
    s.drop(101, 'D:F')
    s.put(101, 'G:Z', lambda c: IF(S[100, c-2] > S[99, c-2], 1, ''))
    # 103
    s.drop(103, 'B')
    s.drop(103, 'D:X')
    # 104
    s.drop(104, 'B')
    s.drop(104, 'D:X')
    # 105
    s.drop(105, 'B')
    s.drop(105, 'D:X')
    # 106
    s.drop(106, 'B:X')
    # 107
    s.drop(107, 'B:X')


RULES = {
    'A1_Historical_pub': _a1_historical_pub,
    'B1_GDP_pub': _b1_gdp_pub,
    'B2_PB_mkt_pub': _b2_pb_mkt_pub,
    'B2_PB_non_mkt_pub': _b2_pb_non_mkt_pub,
    'B5_depreciation_pub': _b5_depreciation_pub,
    'B6_combo_mkt_pub': _b6_combo_mkt_pub,
    'B6_combo_non-mkt_pub': _b6_combo_non_mkt_pub,
    'C1_Combined CL': _c1_combined_cl,
    'C2_Natural disaster': _c2_natural_disaster,
    'C3_commodity_prices_pub': _c3_commodity_prices_pub,
    'A1_historical_ext': _a1_historical_ext,
    'B1_GDP_ext': _b1_gdp_ext,
    'B3_Exports_ext': _b3_exports_ext,
    'B4_other flows_ext': _b4_other_flows_ext,
    'B5_depreciation_ext': _b5_depreciation_ext,
    'B6_Combo_mkt_ext': _b6_combo_mkt_ext,
    'B6_Combo_non-mkt_ext': _b6_combo_non_mkt_ext,
    'C3_Commodity prices_ext': _c3_commodity_prices_ext,
    'C4_Market_financing': _c4_market_financing,
}



def compute(book, sheet):
    s = Calc(book, sheet)
    RULES[sheet](s)
    s.run()
