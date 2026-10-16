# sovrisk: M-13 sovereign risk model (Python port)

> **FOR RESEARCH PURPOSES ONLY. CONFIDENTIAL.** Randori Resources LLC. Not investment advice, not a municipal
> advisory recommendation and not a credit rating. Use at your own risk.

**Status: v0.7, UNTESTED, PRELIMINARY. Engine only: Randori's analyst inputs, country scores and calibration data are not included.**

A Python port of the Randori M-13 sovereign risk scorecard workbook
(`Randori_Country_Risk_Scores_Oct2026.xlsx`). Privately it reproduces the workbook to within 1e-7; the parity tests and
their golden values use Randori's analyst inputs, so they are not in this public repository.

## What it does

| Module | Workbook tab(s) | What it computes |
| --- | --- | --- |
| `sovrisk/debt.py` | Debt Scenarios | IMF baseline plus macro-fiscal and combined stress paths |
| `sovrisk/inputs.py` | Model Inputs, Scenario Drivers, Best/Worst Inputs | Stress-derived indicators; best and worst cases |
| `sovrisk/scoring.py` | Model Calc, Model Pillars | Indicator scores, pillar scores, triggers, floors, country score, grade |
| `sovrisk/model.py` | Scenario Summary, Sensitivity | Runs all cases; pillar contributions; points per band |
| `sovrisk/backtest.py` | Backtest, VaR Backtest | Brier score, calibration bins, Kupiec tests |
| `sovrisk/montecarlo.py` | Monte Carlo, MC Trials | t-copula default loss, VaR, ES, tail contributions |
| `sovrisk/pri.py` | PRI Perils, PRI Calc | Five perils: hazard, claim probability over the policy term, expected loss, indicative premium |
| `sovrisk/restructuring.py` | Restructuring, Restructuring Calc | Bond cash flows, NPV haircut (SZ), market haircut (CT), recovery, holdout risk, months to deal |
| `sovrisk/default_fit.py`, `connectors.py` | Default PD | Logit fit, country bootstrap bands, walk-forward AUC, log-odds blend, CDS-implied benchmark |
| `sovrisk/decisions.py` | (all three) | Runs the decision modules on the data files |
| `sovrisk/levers.py` | (Python only) | Stability levers (insurance, reinsurance, credit, banking, revenue, investor protection) from `rulebook/levers.yaml`; exact re-run with any set switched on. ILLUSTRATIVE magnitudes |
| `sovrisk/dashboard.py` | (all) | One HTML page: colour-coded risk map, ranking, Monte Carlo loss, and per-country pillars, scenarios, sensitivity, default PD, insurance perils, bond recovery and lever toggles |
| `sovrisk/pfram.py` | PFRAM 2.0 (IMF and World Bank) | PPP fiscal risk: private partner's income statement and cash waterfall, government accrual and cash accounts, balance sheet, debt and revenue guarantees, early termination, macro shocks, risk matrix, and the portfolio's effect on deficit and debt. ILLUSTRATIVE projects in `data/pfram_projects.yaml` |
| `sovrisk/muni.py` | (Python only) | M-15 municipal credit scorecard: 0-100 risk score and grade for a US city or town in any state, with Massachusetts practice as the administration benchmark, from economy, finances, debt and governance indicators (`rulebook/muni.yaml`), recession and pension stress cases, peer percentiles. ILLUSTRATIVE towns in `data/muni_towns.csv`; not a credit rating |

## Layout

```
rulebook/rulebook.yaml    pillars, indicators, weights, thresholds (edit here, review by pull request)
rulebook/settings.yaml    levers: blend, caps, stress shocks, small-state rule, backtest and Monte Carlo settings
data/                     templates and illustrative rows; inputs.csv and countries.csv are header-only templates
scripts/extract_workbook.py   regenerates rulebook/, data/ and tests/golden/ from the workbook
tests/test_engine.py      engine tests that need no analyst inputs
data/pfram_projects.yaml, data/pfram_macro.csv   ILLUSTRATIVE PPP portfolio and macro path for sovrisk.pfram
scripts/pfram_golden.py   writes the illustrative projects into the PFRAM 2.0 workbook, recalculates it in LibreOffice
                          and saves every row to tests/golden/pfram/
tests/test_pfram.py       PFRAM parity: every Template row against the recalculated workbook
```

## Run

```
pip install -e .[test]
pytest -q
python -m sovrisk.cli --out outputs
pip install -e .[dashboard]       # optional: embeds plotly.js so the dashboard works offline
python -m sovrisk.dashboard --out outputs/dashboard.html
python -m sovrisk.levers --list
python -m sovrisk.pfram --out outputs   # PPP fiscal risk, illustrative projects
python -m sovrisk.muni --town "Town E"   # municipal scorecard, illustrative towns
```

## Differences from the workbook

None in results. One workbook bug was found during the port and fixed in both places on 15 Oct 2026.
Venezuela, Ecuador and Zambia have no WEO projections. For them, the debt indicators read the next
country's stress rows in Debt Scenarios: Venezuela took Nigeria's debt path, Ecuador took El Salvador's,
and Zambia took Zimbabwe's. These countries now show the debt indicators as blank. Their country scores
were already blank, because they have no other inputs, so no headline result changed.

## Municipal credit scorecard (sovrisk.muni, M-15 v0.2)

Scores a city or town in any US state from 0 (lowest risk) to 100 (highest), with grades 1-10, as in the sovereign
scorecard. Draft weights: economy and tax base 30%, financial performance 30%, debt and liabilities 30%, management and
governance 10%. The indicators, thresholds, weights and stress cases are all in `rulebook/muni.yaml`; a missing
indicator drops out and its factor's weights are rescaled.

Massachusetts is the gold standard for administration. The governance factor scores every town against what MA
requires or recommends, whatever its own state requires: free cash certification, state review of revaluations every
five years, PERAC schedules to full pension funding, OPEB trusts, written reserve policies, five-year capital plans and
timely audits. Each town shows how many of these eight practices it meets. Economic and financial indicators use
generic definitions (full market value rather than MA equalized valuation, for example); where a state sets no
property tax limit, the levy-capacity indicator is left blank and drops out.

It is Randori's own model, not a credit rating, and is untested: the ten towns in `data/muni_towns.csv` are
hypothetical, spread across several states. Planned data sources for real towns: the state's local-government finance
data (in MA, the DLS Municipal Databank), Census of Governments and ACS, BLS local unemployment, state pension
valuations (PERAC in MA) and audited financial statements on MSRB EMMA.

## PFRAM 2.0 port (sovrisk.pfram)

`sovrisk/pfram.py` ports the Template, MacroParameters, SensitivityAnalysis and risk sheets of the PPP Fiscal Risk
Assessment Model (PFRAM 2.0) by the IMF and the World Bank. It is an independent port, not endorsed by either
institution. The three projects in `data/pfram_projects.yaml` are hypothetical and unaffiliated.

Parity: for each project, under the base case and the combined macro shock, every Template row from the private
partner's accounts to the termination block matches the workbook recalculated in LibreOffice (relative 1e-7).
The effective interest rate is solved as the workbook's EIR_Seek macro does. Untested on a real project.

Workbook behaviour kept on purpose so results match (also in `pfram.QUIRKS`):

- Debt guarantee payments (row 196) refer to names the workbook never defines, so they are always 0.
- Revenues include "other government payment" in the first year only (row 112).
- The availability payment is indexed by one year of deflator growth, not cumulatively (row 114).
- The debt-guarantee flow (row 228) lags the guaranteed debt stock (row 213) by one year.
- Macro series line up with project years by column, so every project must start in the first macro year.
- Rows 742, 743 and 747 add billions to millions; `pfram.portfolio` gives clean headline ratios.
- With combined funding there may be no rate that meets the goal-seek condition (Excel's Goal Seek also
  fails); the port then uses the project IRR.

## Debt sustainability: MAC SRDSF port (sovrisk.srdsf, M-16 v0.1)

`sovrisk/srdsf/` ports the IMF's Sovereign Risk and Debt Sustainability Framework template for market-access
countries (MAC SRDSF), sheet by sheet, plus its two macros: the fan chart simulation (`fan.simulate`, with the
template's own random-number generator and seed) and the GFN converge loop (`gfn.simulate`). It is an independent
port, not endorsed by the IMF. The sample in the template is a fictional country; untested on a real one.

    python -m sovrisk.srdsf.run --golden tests/golden/srdsf --fan --gfn

Parity:

- Each of the 16 formula sheets reproduces every formula cell of the template's stored Excel values, errors
  included (`tests/test_srdsf.py`).
- `run()` starts from inputs only, chains the sheets until no value changes, and again matches every cell
  (`tests/test_srdsf_run.py`).
- With 101 changed inputs (growth, exchange rates, revenue, debt instruments) it matches the template recalculated
  in LibreOffice (`tests/golden/srdsf_alt`, built by `scripts/srdsf_alt_golden.py`). That check sets the country
  selector to a listed country so the peer-group lookups resolve; the data stay the fictional sample.

The template's own slips are kept so results match, and each module lists them in `QUIRKS` (for example, the
stress-scenario GDP expansion drops higher-order terms, and a zero-coupon instrument amortizes as #N/A because of a
label mismatch). The dashboard's debt sustainability section shows the sample run: risk signals, the fan chart, the
near-term logit, gross financing needs, the medium-term index and the stress tests.

## Debt sustainability: LIC DSF port (sovrisk.licdsf, M-16 v0.1)

`sovrisk/licdsf/` ports the IMF and World Bank Debt Sustainability Framework template for low-income countries
(LIC DSF, IDA21 version of 8 Dec 2025), all 76 formula sheets. It is an independent port, not endorsed by either
institution, and untested on a new country.

    python -m sovrisk.licdsf.run --golden <folder of golden files>

Parity: each sheet matches every formula cell of the template's stored Excel values; `run()` from inputs only
matches all 199,437 formula cells, errors included; and under changed macro paths, loan terms and stress-test
settings it agrees on every cell with an independent evaluator of the template's own formulas
(`tests/licdsf_oracle.py`), since LibreOffice cannot recalculate this template. The template's sample is real
country data, so its golden files and the tests that need them are kept private.

## What is not here

Randori's analyst inputs (`data/inputs.csv`, `data/countries.csv`), live backtest forecasts and the
workbook parity tests are kept private. `data/backtest_log.csv` holds only the SYNTHETIC test rows.
Fill `data/inputs.csv` with your own inputs (country, id, value, verified, source) to score countries.
Data in `data/debt_baseline.csv` is from the IMF World Economic Outlook; check source licences before
redistributing anything in `data/`.

## Not yet fitted (v0.5)

The default fit needs a country-year panel and default events. This environment blocks
www.imf.org, api.worldbank.org and www.bankofcanada.ca, so `connectors.py` has not been run, and
`data/default_coefficients.csv`, `default_bands.csv`, `market_spreads.csv` and `creditor_map.csv` are
blank. Until the coefficients are filled, the blended PD equals the illustrative scorecard PD. Peril,
premium and deal-duration parameters in `rulebook/settings.yaml` are illustrative. Rows marked
EXAMPLE in `data/pri_policies.csv` and `data/bonds.csv` are illustrations, not real policies or bonds.
