# RPF-06 v0.1: Spillover network

**Status:** built; no country data loaded; elasticities are drafts; untested. Randori's own model.
**Code:** `sovrisk/spillover.py`; rulebook `rulebook/spillover.yaml`; data builders in `sovrisk/spillover_data.py`.
**Run:** `python -m sovrisk.spillover --list`; `python -m sovrisk.spillover --scenario us_recession --rounds`.

## Purpose

Estimates how much a shock abroad would cut each country's GDP growth, and through which channel.

## Method

- **Channels.** Trade, commodities, banks, US dollar debt (rates) and remittances.
- **First round.** Shock x exposure x the channel's elasticities.
- **Second round.** Those GDP losses pass through the trade matrix to trading partners, damped by half each round
  until they die out. A network whose losses would not shrink is refused rather than run.
- **Scenarios.** US recession (GDP -2%), China slowdown (GDP -3%), oil -30%, copper -25%, US rates +200 bp. A
  scenario shocks only what it lists.

Results are split by channel and by round.

## Inputs

`data/spill_trade.csv`, `spill_commodities.csv`, `spill_banks.csv`, `spill_rates.csv` and `spill_remittances.csv`
(country, partner, value_pct_gdp, year, source). None exist yet; [DATA.md](../DATA.md) explains how to build them
from IMF trade statistics, BIS banking statistics, UN Comtrade and World Bank data, or by hand. The command says
which files are missing.

## Outputs

A table of GDP impacts per country, by channel and round; the dashboard's spillover section.

## Validation

Hand-worked examples on hand-made countries in `tests/test_spillover.py`. Not compared with any published spillover
estimate yet.

## Limits

Every elasticity and the damping factor are drafts to verify; each has a `source` note in the rulebook naming the
literature it is meant to sit in. The fetch functions have never run against a live response. Exchange rates and
policy responses are not modelled, which the damping stands in for.

## Use

Research only.

## Change log

- v0.1: engine, five scenarios, tests and dashboard section; no data.
