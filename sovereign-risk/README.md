# sovrisk: Randori public finance risk models

> **FOR RESEARCH PURPOSES ONLY. CONFIDENTIAL.** Randori Resources LLC. Not investment advice, not a municipal
> advisory recommendation and not a credit rating. Use at your own risk.

**Status: v0.8.1, UNTESTED, PRELIMINARY. Engine only: Randori's analyst inputs, country scores and calibration data
are not included.**

`sovrisk` is a Python package of sovereign, sub-sovereign and fiscal risk models. Some are ports of Excel templates
(Randori's own scorecard workbook and published IMF and World Bank templates) that match the template cell for cell.
The others are Randori's own models, written in Python. Cite the model ID and version with any result.

## Models

| ID | Model | Code | Status | Model card |
| --- | --- | --- | --- | --- |
| M-13 v0.5 | Sovereign risk scorecard, with scenarios, backtests, Monte Carlo, default PD, PRI, restructuring and levers | `sovrisk/` (`scoring.py` and others) | Port of the Randori workbook; analyst inputs private | [M-13](docs/models/M-13.md) |
| M-14 v0.1 (proposed) | PPP fiscal risk (PFRAM 2.0 port) | `sovrisk/pfram.py` | Matches the workbook on illustrative projects; untested on a real one | [M-14](docs/models/M-14.md) |
| M-15 v0.2 (proposed) | Municipal credit scorecard, any US state, Massachusetts practice as benchmark | `sovrisk/muni.py` | Illustrative towns only | [M-15](docs/models/M-15.md) |
| M-16 v0.1 (proposed) | Debt sustainability: MAC SRDSF and LIC DSF ports | `sovrisk/srdsf/`, `sovrisk/licdsf/` | Matches both templates cell for cell; untested on a new country | [M-16](docs/models/M-16.md) |
| M-22 v0.1 (proposed) | Macro early-warning panel | `sovrisk/ews.py` | Built; no country data yet | [M-22](docs/models/M-22.md) |
| M-23 v0.1 (proposed) | Spillover network | `sovrisk/spillover.py` | Built; no country data yet; elasticities are drafts | [M-23](docs/models/M-23.md) |

"Proposed" means the ID is not yet entered in Randori's Model Inventory.

## Install and run

```
pip install -e .[test]
pytest -q
pip install -e .[dashboard]       # optional: embeds plotly.js so the dashboard works offline

python -m sovrisk.cli --out outputs                         # M-13 result tables
python -m sovrisk.dashboard --out outputs/dashboard.html    # one HTML page with every model
python -m sovrisk.levers --list                             # M-13 stability levers
python -m sovrisk.pfram --out outputs                       # M-14, illustrative projects
python -m sovrisk.muni --town "Town E"                      # M-15, illustrative towns
python -m sovrisk.srdsf.run --golden tests/golden/srdsf --fan --gfn   # M-16 MAC SRDSF, template sample
python -m sovrisk.ews --country ARG                         # M-22, needs data/ews_panel.csv
python -m sovrisk.spillover --scenario us_recession --rounds   # M-23, needs data/spill_*.csv
```

## Layout

```
rulebook/          weights, thresholds, stress sizes and scenarios (YAML; change by pull request)
data/              input CSVs: header-only templates and labelled illustrative rows
sovrisk/           the engines, connectors, command line and dashboard
sovrisk/srdsf/     MAC SRDSF port, one file per template sheet
sovrisk/licdsf/    LIC DSF port, one file per template sheet
tests/             tests; tests/golden/ holds values saved from the Excel templates
scripts/           regenerate rulebook/, data/ and tests/golden/ from the workbooks
docs/              technical documentation (below)
```

## Documentation

- [Architecture](docs/ARCHITECTURE.md): layers, file map and how the models interact.
- [Model cards](docs/models/README.md): one page per model with its method, inputs, limits and validation status.
- [Data](docs/DATA.md): how to plug real country data into the early-warning panel and spillover network.
- [Testing](docs/TESTING.md): how parity with the Excel templates is checked, and which tests are private.
- [Rulebook](docs/RULEBOOK.md): how to change a weight or threshold, and who reviews it.

## What is not here

Randori's analyst inputs (`data/inputs.csv`, `data/countries.csv`), live backtest forecasts, the M-13 workbook parity
tests and the LIC DSF golden values (the template's sample is real country data) are kept private.
`data/backtest_log.csv` holds only SYNTHETIC test rows. Fill `data/inputs.csv` with your own inputs (country, id,
value, verified, source) to score countries. Data in `data/debt_baseline.csv` is from the IMF World Economic Outlook;
check source licences before redistributing anything in `data/`.

The ports of IMF and World Bank templates are independent and not endorsed by either institution. Names of towns,
projects and countries in illustrative files are hypothetical and unaffiliated.
