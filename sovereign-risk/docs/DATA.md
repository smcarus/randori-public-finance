# Plugging in real country data

The early-warning panel (RPF-05) and spillover network (RPF-06) read plain CSV files from `data/`. Fill them by either
route below, then run the module. Neither module ships with country data.

Country codes are ISO3 (ARG, ZMB, SLV). The sovereign scorecard files (`data/countries.csv`, `data/inputs.csv`)
use country names, so keep a name-to-ISO3 list if you want to compare results side by side.

## Route 1: fetch automatically (needs the data hosts reachable)

Run this on your own machine, or in a cloud environment once api.imf.org, api.worldbank.org, stats.bis.org and
comtradeapi.un.org are allowed. The README's "Pulling country data from the APIs" section has the step-by-step
guide. In short: install the IMF's sdmx1 client with `pip install -e .[data]`, check the IMF keys with the
`imf-describe` command, fill `data/country_codes.csv` (iso3, iso2, m49, name) with the `codes` command (from the
World Bank country list; add M49 numbers by hand), then run `scripts/fetch_country_data.py` once per file:

    cd sovereign-risk
    python scripts/fetch_country_data.py ews   --countries ARG,ZMB,SLV
    python scripts/fetch_country_data.py trade --countries ARG,ZMB,SLV --partners USA,CHN,ARG,ZMB,SLV --years 2015-2024

and likewise `banks`, `commodities`, `rates` and `remittances`. The script calls `build_ews_panel` in
`sovrisk/connectors.py` and the fetch and parse functions in `sovrisk/spillover_data.py` (both read the IMF through
`sovrisk/imf.py`), converts flows to % of GDP with World Bank GDP in US$, and writes each file. If a source fails,
nothing is written and the error names the URL. These have never run against a live response, so check the first
output by eye. The remittance matrix and each country's gross financing need have no API: see the README.

Market prices (US Treasury yields, oil, copper, exchange rates) come from Yahoo Finance through yfinance
(`sovrisk/market.py`, `fetch_country_data.py market`) into `data/market_prices.csv`, columns `series, ticker, date,
value, unit, source`. Yahoo's terms forbid redistribution, so the file is in `.gitignore` and stays in the private
copy. Yahoo has no sovereign CDS: `data/market_spreads.csv` is still entered by hand.

## Live pulls for one country

`python -m sovrisk.serve` serves the dashboard at http://localhost:8080. In its Live country data tab, pick a country
and the server pulls that country's IMF WEO series, World Bank series, BIS credit gap and Yahoo Finance prices
(`sovrisk/live.py`), then rates it on the early-warning panel. Each feed is pulled on its own, so a blocked or failing
source is reported and the others still show. A pull is cached in `outputs/live/<ISO3>.json` (not committed) and
nothing is written to `data/`. `python -m sovrisk.live ARG --fx ARS` does the same pull from the command line. The
server listens on your machine only (127.0.0.1). It has not yet run against live responses: check the first pull by eye.

## Route 2: enter it by hand (works today)

Copy the columns below into a spreadsheet, fill the rows from the sources named, and save as CSV in `data/`.

### `data/ews_panel.csv`: one row per country and year

| Column | Meaning | Unit | Where to find it |
| --- | --- | --- | --- |
| country | ISO3 code | | |
| year | calendar year | | |
| reserves_months | reserves in months of imports | months | World Bank WDI FI.RES.TOTL.MO |
| reserves_std | reserves / short-term external debt | % | World Bank IDS (100 x reserves / short-term debt) |
| ca_gdp | current account balance | % of GDP | IMF WEO BCA_NGDPD |
| reer | real effective exchange rate index | index | World Bank PX.REX.REER or IMF IFS |
| credit_gdp | private credit | % of GDP | World Bank FS.AST.PRVT.GD.ZS |
| credit_gap | credit-to-GDP gap, if the BIS publishes one | pp | BIS credit-to-GDP gaps (leave blank otherwise) |
| inflation | consumer price inflation | % | IMF WEO PCPIPCH |
| gfn_gdp | gross financing need (optional) | % of GDP | the debt sustainability module or the IMF DSA |

Put in at least 10 years per country: the module works out each country's own-history percentiles and the REER and
credit trends from the history. A blank cell is fine; that indicator drops out for that year.

### `data/crisis_dates.csv` (optional, switches on the fitted weights)

Columns: `country, year, type`, with type one of currency, banking or sovereign, one row per crisis start. Source:
Laeven and Valencia, "Systemic Banking Crises Database" (IMF), plus the default database the program already uses.
Without this file every indicator gets equal weight.

### Spillover exposure files: long format, one row per country and partner

All five share the columns `country, partner, value_pct_gdp, year, source`. What `partner` means differs:

| File | partner | value_pct_gdp | Where to find it |
| --- | --- | --- | --- |
| spill_trade.csv | ISO3 of the country it exports to (USA, CHN, ...) | exports to that partner | IMF trade statistics (IMTS, formerly DOTS) |
| spill_commodities.csv | oil, metals, copper or food | NET exports (negative for an importer) | UN Comtrade or UNCTAD |
| spill_banks.csv | ISO3 of the lending banks' home country | claims of those banks on the country | BIS consolidated banking statistics |
| spill_rates.csv | `usd_debt_share` or `gfn` (two rows per country) | USD share of public debt (%), or gross financing need (% of GDP) | World Bank IDS; the country's IMF DSA |
| spill_remittances.csv | ISO3 of the sending country | remittance inflows from it | World Bank bilateral remittance matrix |

Divide each flow by the country's nominal GDP in US dollars (World Bank NY.GDP.MKTP.CD) for the same year.

## Run it

    python -m sovrisk.ews                       # every country, latest year
    python -m sovrisk.ews --country ARG         # one country, indicator by indicator
    python -m sovrisk.spillover --list          # the five scenarios
    python -m sovrisk.spillover --scenario us_recession --rounds

Both commands say which files are missing. Once the files exist, rebuild the dashboard (`python -m sovrisk.dashboard`)
and its early-warning and spillover sections fill in.

## Check before relying on results

- Thresholds in `rulebook/ews.yaml` and every elasticity in `rulebook/spillover.yaml` are drafts.
- Spot-check a few values against the source pages.
- Keep licensed data (Bloomberg, LSEG, paid Comtrade, Yahoo Finance prices) out of the public repo. Store it only in the private copy.
