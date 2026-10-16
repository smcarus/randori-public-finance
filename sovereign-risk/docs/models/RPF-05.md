# RPF-05 v0.1: Macro early-warning panel

**Status:** built; no country data loaded; untested. Randori's own model.
**Code:** `sovrisk/ews.py`; rulebook `rulebook/ews.yaml`; data builder `connectors.build_ews_panel`.
**Run:** `python -m sovrisk.ews`; `python -m sovrisk.ews --country ARG`.

## Purpose

Flags countries heading toward a currency, banking or debt crisis within the next two years.

## Method

- **Ratings.** Seven indicators are rated green, amber or red against draft thresholds: reserves in months of
  imports (amber below 4, red below 3), reserves over short-term external debt (150% / 100%), current account (-3% /
  -5% of GDP), REER against its previous 10-year average (+10% / +20%), credit-to-GDP gap (2pp / 10pp), inflation
  (10% / 20%) and, optionally, gross financing need (10% / 15% of GDP).
- **Own history.** Each value also gets its percentile in the country's own history.
- **Warning score.** 0 when all green, 100 when all red. Indicators are weighted by the signals method of Kaminsky,
  Lizondo and Reinhart: over the crisis dates given, each indicator's noise-to-signal ratio uses a 2-year window
  before a crisis starts, with amber counting as a signal; weight is 1/NSR normalised, and indicators with an NSR of 1
  or more are dropped. Without crisis dates, the rulebook's equal weights apply. A missing indicator drops out and
  the weights are rescaled.
- **Credit gap.** Where the BIS publishes none, it is computed from credit-to-GDP with a one-sided HP filter (each
  year's trend uses data up to that year only). The BIS uses lambda 400,000 on quarterly data; the panel is annual,
  so it uses 400,000 / 4^4 = 1,562.5 (Ravn-Uhlig scaling).

## Inputs

`data/ews_panel.csv` (country, year, indicator columns) and, optionally, `data/crisis_dates.csv` (country, year,
type). Neither is in the repo, and neither is ever filled with made-up data. `scripts/fetch_country_data.py ews` builds
the panel from the IMF, World Bank and BIS (steps in the README); [DATA.md](../DATA.md) also explains how to fill
both files by hand.

## Outputs

A table per country and year of ratings, percentiles and the warning score; the dashboard's early-warning heatmap;
and, through `python -m sovrisk.serve` or `python -m sovrisk.live`, a rating for one country pulled live (Live
country data tab).

## Validation

Known-answer tests on hand-made panels in `tests/test_ews.py`. Not yet run on real data, so neither the thresholds
nor the weights have been checked against past crises.

## Limits

Thresholds and fallback weights are drafts. Annual data only. The data connectors have never run against a live
response.

## Use

Research only.

## Change log

- v0.1: engine, tests and dashboard section; no data.
