# sovrisk: M-13 sovereign risk model (Python port)

> **FOR RESEARCH PURPOSES ONLY. CONFIDENTIAL.** Randori Resources LLC. Not investment advice, not a municipal
> advisory recommendation and not a credit rating. Use at your own risk.

**Status: v0.5, UNTESTED, PRELIMINARY. Engine only: Randori's analyst inputs, country scores and calibration data are not included.**

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

## Layout

```
rulebook/rulebook.yaml    pillars, indicators, weights, thresholds (edit here, review by pull request)
rulebook/settings.yaml    levers: blend, caps, stress shocks, small-state rule, backtest and Monte Carlo settings
data/                     templates and illustrative rows; inputs.csv and countries.csv are header-only templates
scripts/extract_workbook.py   regenerates rulebook/, data/ and tests/golden/ from the workbook
tests/test_engine.py      engine tests that need no analyst inputs
```

## Run

```
pip install -e .[test]
pytest -q                          # 8 engine tests
python -m sovrisk.cli --out outputs
```

## Differences from the workbook

None in results. One workbook bug was found during the port and fixed in both places on 15 Oct 2026.
Venezuela, Ecuador and Zambia have no WEO projections. For them, the debt indicators read the next
country's stress rows in Debt Scenarios: Venezuela took Nigeria's debt path, Ecuador took El Salvador's,
and Zambia took Zimbabwe's. These countries now show the debt indicators as blank. Their country scores
were already blank, because they have no other inputs, so no headline result changed.

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
