# RPF-01 v0.5: Sovereign risk scorecard (formerly M-13)

**Status:** untested, preliminary. Port of `Randori_Country_Risk_Scores_Oct2026.xlsx`. Analyst inputs are private.
**Code:** `sovrisk/debt.py`, `inputs.py`, `scoring.py`, `model.py`; decision tools in `backtest.py`,
`montecarlo.py`, `pri.py`, `restructuring.py`, `default_fit.py`, `decisions.py`, `levers.py`.
**Run:** `python -m sovrisk.cli --out outputs`; `python -m sovrisk.levers --country <name> --on <lever,...>`.

## Purpose

A 0-100 country risk score (0 lowest risk) and a grade from 1 to 10 for sovereigns, with base, best and worst cases,
and the decision tools that use it: default probability, portfolio loss, political risk insurance pricing and bond
restructuring.

## Method

- **Indicators.** Each indicator in `rulebook/rulebook.yaml` is scored 0-100 by straight lines between five
  thresholds. Debt indicators use the worse of the IMF baseline and a stress path (`debt.py`: primary balance,
  growth and exchange-rate shocks from `settings.yaml`).
- **Pillars.** Seven pillars: fiscal and debt 25%, external 20%, institutions and governance 15%, political and
  policy 15%, macro and financial 10%, security and social 10%, climate and disaster 5%. A pillar's raw score is
  70% the weighted average of its indicators and 30% its worst core indicator. Event triggers (capped), an analyst
  adjustment (at most 10 points either way) and a floor give the final pillar score.
- **Small states.** A country with population under 1.5 million, or a 1-in-100-year disaster loss of 25% of GDP
  or more, has climate weighted 15% and the other pillars scaled down.
- **Grade.** Score divided by 10, plus 1, capped at 10.
- **Decision tools.** Default PD is a logistic function of the score; `default_fit.py` fits a logit on default
  history and blends it with the scorecard PD in log-odds once fitted. Monte Carlo uses a one-factor t copula for
  portfolio loss, VaR and expected shortfall. PRI prices five perils over a policy term. Restructuring computes the
  NPV haircut (Sturzenegger-Zettelmeyer), recovery, holdout risk and months to a deal. Levers change indicators and
  re-run everything exactly.

## Inputs

`data/inputs.csv` and `data/countries.csv` (analyst inputs, header-only in the public repo), `data/debt_baseline.csv`
(IMF WEO), scenario files, and the decision-tool files (`bonds.csv`, `pri_policies.csv`, `mc_*.csv`, backtest logs).
Rows marked EXAMPLE are illustrations.

## Outputs

Pillar and indicator tables and Monte Carlo results in `outputs/`; the dashboard's map, ranking and country pages.

## Validation

Privately reproduces the workbook to within 1e-7 on every indicator, pillar, score, scenario, sensitivity, backtest
and Monte Carlo figure (`test_parity.py`, private). Public known-answer tests in `test_engine.py`. The default fit
has not been run: `data/default_coefficients.csv`, `default_bands.csv`, `market_spreads.csv` and `creditor_map.csv`
are blank, so the blended PD equals the illustrative scorecard PD.

## Limits

- Peril, premium, deal-duration and lever magnitudes are illustrative, not calibrated.
- Venezuela, Ecuador and Zambia have no WEO projections, so their debt indicators are blank.
- Not a credit rating and not investment advice.

## Change log

- 16 Oct 2026: renumbered from M-13 to RPF-01 in the Model Inventory; no change to the model.
- v0.5: Python port matching the workbook; decision tools, levers and dashboard. One workbook bug found during the
  port was fixed in both places on 15 Oct 2026; no headline result changed.
