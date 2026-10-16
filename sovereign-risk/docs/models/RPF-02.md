# RPF-02 v0.1: PPP fiscal risk, PFRAM 2.0 port

**Status:** matches the workbook on illustrative projects; untested on a real project. Independent port, not
endorsed by the IMF or the World Bank.
**Code:** `sovrisk/pfram.py`. **Run:** `python -m sovrisk.pfram --list`; `python -m sovrisk.pfram --project P1 --out outputs`.

## Purpose

The fiscal cost and risk to a government of a portfolio of public-private partnership (PPP) projects, as the IMF and
World Bank PPP Fiscal Risk Assessment Model (PFRAM 2.0) computes them.

## Method

Ports the Template, MacroParameters, SensitivityAnalysis and risk sheets: the private partner's income statement and
cash waterfall, the government's accrual and cash accounts, balance sheet, debt and revenue guarantees, early
termination, macro shocks, the risk matrix, and the portfolio's effect on the deficit and debt. The effective
interest rate is solved as the workbook's EIR_Seek macro does (`solve_effective_rate`).

## Inputs

`data/pfram_projects.yaml` (three hypothetical, unaffiliated projects) and `data/pfram_macro.csv` (an illustrative
macro path).

## Outputs

One table per project and a portfolio table in `outputs/`; the dashboard's PPP section.

## Validation

For each project, under the base case and the combined macro shock, every Template row from the private partner's
accounts to the termination block matches the workbook recalculated in LibreOffice to relative 1e-7
(`tests/test_pfram.py`; golden values from `scripts/pfram_golden.py`).

## Limits

Workbook behaviour kept on purpose so results match (also in `pfram.QUIRKS`):

- Debt guarantee payments (row 196) refer to names the workbook never defines, so they are always 0.
- Revenues include "other government payment" in the first year only (row 112).
- The availability payment is indexed by one year of deflator growth, not cumulatively (row 114).
- The debt-guarantee flow (row 228) lags the guaranteed debt stock (row 213) by one year.
- Macro series line up with project years by column, so every project must start in the first macro year.
- Rows 742, 743 and 747 add billions to millions; `pfram.portfolio` gives clean headline ratios.
- With combined funding there may be no rate that meets the goal-seek condition (Excel's Goal Seek also fails); the
  port then uses the project IRR.

## Use

Research only. Not advice to any government or project sponsor.

## Change log

- v0.1: port of PFRAM 2.0 with parity tests and dashboard views.
