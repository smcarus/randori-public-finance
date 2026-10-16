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
| RPF-01 v0.5 (formerly M-13) | Sovereign risk scorecard, with scenarios, backtests, Monte Carlo, default PD, PRI, restructuring and levers | `sovrisk/` (`scoring.py` and others) | Port of the Randori workbook; analyst inputs private | [RPF-01](docs/models/RPF-01.md) |
| RPF-02 v0.1 | PPP fiscal risk (PFRAM 2.0 port) | `sovrisk/pfram.py` | Matches the workbook on illustrative projects; untested on a real one | [RPF-02](docs/models/RPF-02.md) |
| RPF-03 v0.3 | Municipal credit scorecard, any US state, Massachusetts practice as benchmark | `sovrisk/muni.py` | Illustrative towns only | [RPF-03](docs/models/RPF-03.md) |
| RPF-04 v0.1 | Debt sustainability: MAC SRDSF and LIC DSF ports | `sovrisk/srdsf/`, `sovrisk/licdsf/` | Matches both templates cell for cell; untested on a new country | [RPF-04](docs/models/RPF-04.md) |
| RPF-05 v0.1 | Macro early-warning panel | `sovrisk/ews.py` | Built; no country data yet | [RPF-05](docs/models/RPF-05.md) |
| RPF-06 v0.1 | Spillover network | `sovrisk/spillover.py` | Built; no country data yet; elasticities are drafts | [RPF-06](docs/models/RPF-06.md) |

RPF stands for Randori Public Finance. Each ID is entered in Randori's Model Inventory.

## Install and run

```
pip install -e .[test]
pytest -q
pip install -e .[dashboard]       # optional: embeds plotly.js so the dashboard works offline
pip install -e .[data]            # optional: the sdmx1 client, for pulling IMF data

python -m sovrisk.cli --out outputs                         # RPF-01 result tables
python -m sovrisk.dashboard --out outputs/dashboard.html    # one HTML page with every model
python -m sovrisk.levers --list                             # RPF-01 stability levers
python -m sovrisk.pfram --out outputs                       # RPF-02, illustrative projects
python -m sovrisk.muni --town "Town E"                      # RPF-03, illustrative towns
python -m sovrisk.srdsf.run --golden tests/golden/srdsf --fan --gfn   # RPF-04 MAC SRDSF, template sample
python -m sovrisk.ews --country ARG                         # RPF-05, needs data/ews_panel.csv
python -m sovrisk.spillover --scenario us_recession --rounds   # RPF-06, needs data/spill_*.csv
```

## Pulling country data from the APIs

The early-warning panel and the spillover network read country data from four public APIs. The fetch code is in
`sovrisk/imf.py` (the IMF, through the sdmx1 client), `sovrisk/connectors.py` and `sovrisk/spillover_data.py`;
`scripts/fetch_country_data.py` runs it and writes the
files into `data/`. None of it has run against a live response yet, because the build environment blocks these
hosts, so check the first output of each source by eye against the provider's website.

| Source | Hosts | Key needed | What it supplies | Written to |
| --- | --- | --- | --- | --- |
| IMF | `api.imf.org` (SDMX API, through `sdmx.Client('IMF_DATA')`) | No | Current account and inflation (WEO); goods exports by partner (IMTS, formerly DOTS) | `ews_panel.csv`, `spill_trade.csv` |
| World Bank | `api.worldbank.org` | No | Reserves, REER, private credit, short-term debt (WDI, IDS); GDP in US$ for every % of GDP conversion; US dollar share of public debt | `ews_panel.csv`, all `spill_*.csv`, `spill_rates.csv` |
| BIS | `stats.bis.org` | No | Credit-to-GDP gaps; foreign claims of banks by nationality (consolidated banking statistics) | `ews_panel.csv`, `spill_banks.csv` |
| UN Comtrade | `comtradeapi.un.org` | Optional | Exports and imports of oil, metals, copper and food | `spill_commodities.csv` |

**1. Make the hosts reachable and install the IMF client.** On your own machine the hosts usually are reachable. In
a cloud environment, add the hosts above to its allowed network list. Then run `pip install -e .[data]`, which
installs the sdmx1 package. The IMF data is read the same way as in this example:

```
import sdmx
IMF_DATA = sdmx.Client('IMF_DATA')
data_msg = IMF_DATA.data('CPI', key='USA+CAN.CPI.CP01.IX.M', params={'startPeriod': 2018})
cpi_df = sdmx.to_pandas(data_msg)
```

A key lists the dataflow's dimension values in order, separated by dots; `+` joins several values and an empty
position means all. The WEO and IMTS keys in `sovrisk/imf.py` follow the IMF's published dimension order but have
not been checked against a live response, so check them once:

```
python scripts/fetch_country_data.py imf-describe --flow WEO
python scripts/fetch_country_data.py imf-describe --flow IMTS
```

Each prints the dataflow's dimensions in key order with some of their codes. If the order or a code differs from
`WEO`, `IMTS` or `IMTS_EXPORTS` in `sovrisk/imf.py`, change them there.

**2. List the country codes.** The models and the IMF use ISO3, but the BIS keys countries by ISO2, Comtrade by UN
M49 number and the remittance matrix by name. Fill `data/country_codes.csv` (columns `iso3, iso2, m49, name`) with one
row for every country you score and every partner economy (USA, CHN, ...). ISO2 and ISO3 are on the ISO 3166 list;
M49 numbers are on the UN Statistics Division's M49 page; use the country names exactly as the remittance matrix
spells them.

**3. (Optional) Get a Comtrade key.** Without one, the script uses Comtrade's public preview endpoint, which caps
the rows returned. A free subscription key from the Comtrade developer portal lifts the cap. Put it in an
environment variable, never in a file in the repo:

```
export COMTRADE_KEY=your-key
```

**4. Pull each file.** Run from the `sovereign-risk` folder. Use the same `--countries` list for every command,
and list as `--partners` the economies whose shocks you want to model plus the countries you score, so the second
round of the spillover network can pass losses between them.

```
python scripts/fetch_country_data.py ews         --countries ARG,ZMB,SLV
python scripts/fetch_country_data.py trade       --countries ARG,ZMB,SLV --partners USA,CHN,ARG,ZMB,SLV --years 2015-2024
python scripts/fetch_country_data.py banks       --countries ARG,ZMB,SLV --partners USA,GBR,ESP --years 2015-2024
python scripts/fetch_country_data.py commodities --countries ARG,ZMB,SLV --years 2023-2024
python scripts/fetch_country_data.py rates       --countries ARG,ZMB,SLV --years 2015-2024
python scripts/fetch_country_data.py remittances --countries ARG,ZMB,SLV --matrix path/to/matrix.csv --years 2021
```

- `ews` writes `data/ews_panel.csv` from the IMF, World Bank and BIS. Without `country_codes.csv` it skips the BIS
  and the model computes credit gaps itself.
- `rates` writes the US dollar debt share. Add one `gfn` row per country by hand (gross financing need, % of GDP,
  from its IMF debt sustainability analysis or `sovrisk.srdsf`); the rates channel skips a country without one.
- `remittances` reads the World Bank bilateral remittance matrix, which has no API. Download it from the World
  Bank's migration and remittances data page, save the sheet for one year as CSV, and pass its path.
- A failed download stops with an error naming the URL and writes nothing. Nothing is filled with made-up values.

**5. Optional: crisis dates.** For the early-warning panel's fitted weights, add `data/crisis_dates.csv` (country,
year, type) from the Laeven and Valencia systemic crises database. It has no API.

**6. Check and run.** Spot-check a few values against the source websites, then run
`python -m sovrisk.ews` and `python -m sovrisk.spillover --scenario us_recession --rounds`, and rebuild the
dashboard. [docs/DATA.md](docs/DATA.md) lists every column, unit and source, and how to fill the files by hand
instead.

Keep licensed data (Bloomberg, LSEG, paid Comtrade extracts) out of the public repo. Check each provider's terms
before redistributing anything in `data/`.

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

Randori's analyst inputs (`data/inputs.csv`, `data/countries.csv`), live backtest forecasts, the RPF-01 workbook parity
tests and the LIC DSF golden values (the template's sample is real country data) are kept private.
`data/backtest_log.csv` holds only SYNTHETIC test rows. Fill `data/inputs.csv` with your own inputs (country, id,
value, verified, source) to score countries. Data in `data/debt_baseline.csv` is from the IMF World Economic Outlook;
check source licences before redistributing anything in `data/`.

The ports of IMF and World Bank templates are independent and not endorsed by either institution. Names of towns,
projects and countries in illustrative files are hypothetical and unaffiliated.
