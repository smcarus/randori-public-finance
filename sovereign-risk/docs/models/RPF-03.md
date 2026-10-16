# RPF-03 v0.2: Municipal credit scorecard

**Status:** untested; runs on illustrative towns only. Randori's own model, not a credit rating.
**Code:** `sovrisk/muni.py`; rulebook `rulebook/muni.yaml`.
**Run:** `python -m sovrisk.muni`; `python -m sovrisk.muni --town "Town E"`; `python -m sovrisk.muni --out outputs`.

## Purpose

A 0-100 risk score (0 lowest risk) and a grade from 1 to 10 for a city or town in any US state, built the same way as
the sovereign scorecard, with the factors behind it.

## Method

- **Factors.** Draft weights: economy and tax base 30%, financial performance 30%, debt and liabilities 30%,
  management and governance 10%. Each indicator is scored 0-100 by straight lines between five thresholds. A
  missing indicator drops out and its factor's weights are rescaled.
- **Massachusetts benchmark.** Massachusetts is the gold standard for administration. The governance factor scores
  every town against what Massachusetts requires or recommends, whatever its own state requires: free cash
  certification, state review of revaluations every five years, PERAC schedules to full pension funding, OPEB
  trusts, written reserve policies, five-year capital plans and timely audits with few findings. Each town shows how
  many of these eight practices it meets (a yes for a flag, a score of 25 or less for a number).
- **Generic definitions.** Economic and financial indicators use generic definitions (full market value rather
  than Massachusetts equalized valuation, for example), each with a `benchmark` note naming the Massachusetts
  measure. In a state with no property tax limit (Connecticut, New Hampshire, Vermont), levy capacity is blank and
  drops out.
- **Stress cases.** Recession and pension shock, defined in the rulebook.
- **Peers.** Each town's percentile on each indicator among the towns scored.

## Inputs

`data/muni_towns.csv`: one row per town with a `state` column. The ten towns in the repo are hypothetical, spread
across several states. Planned sources for real towns: the state's local-government finance data (in Massachusetts,
the DLS Municipal Databank), the Census of Governments and ACS, BLS local unemployment, state pension valuations
(PERAC in Massachusetts) and audited financial statements on MSRB EMMA.

## Outputs

`muni_scores.csv` and `muni_indicators.csv`; the dashboard's municipal section.

## Validation

Known-answer tests in `tests/test_muni.py` (rulebook checks, scoring, missing data, the benchmark count, scoring
outside Massachusetts). Not checked against any rating or real outcome.

## Limits

Weights and thresholds are drafts awaiting approval. Regional school districts are not covered yet.

## Use

Research only. Until Randori is registered (Series 50 and Series 54), it runs only on illustrative or anonymized
towns, and no output goes to municipal officials.

## Change log

- v0.2: any US state; governance scored against eight Massachusetts practices; levy capacity drops out where there
  is no levy limit.
- v0.1: Massachusetts towns only.
