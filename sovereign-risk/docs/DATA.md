# Plugging in real country data

The early-warning panel (M-22) and spillover network (M-23) read plain CSV files from `data/`. Fill them by either
route below, then run the module. Neither module ships with country data.

Country codes are ISO3 (ARG, ZMB, SLV). The sovereign scorecard files (`data/countries.csv`, `data/inputs.csv`)
use country names, so keep a name-to-ISO3 list if you want to compare results side by side.

## Route 1: fetch automatically (needs the data hosts reachable)

Run this on your own machine, or here once imf.org, api.worldbank.org, stats.bis.org and comtradeapi.un.org are
allowed in the project's cloud environment.

    cd sovereign-risk
    python -c "from sovrisk.connectors import build_ews_panel; build_ews_panel(countries=['ARG','ZMB','SLV'], iso2_by_iso3={'ARG':'AR','ZMB':'ZM','SLV':'SV'})"

That writes `data/ews_panel.csv` from the IMF (current account, inflation), the World Bank (reserves cover, short-term
debt, REER, private credit) and the BIS (credit gaps, where it publishes them). `iso2_by_iso3` is only for the BIS;
without it the module computes credit gaps itself. If a source fails, nothing is written and the error names the URL.

For the spillover files, `sovrisk/spillover_data.py` has a fetch and a parse function per source (IMF trade, BIS bank
claims, UN Comtrade, World Bank GDP and USD debt share). It also converts flows to % of GDP with `to_pct_gdp` and
writes each file with `write(rows, 'spill_trade.csv')`. These have never run against a live response, so check
the first output by eye. The remittance matrix has no API: download it from the World Bank remittances page
and read it with `parse_remittance_matrix(path, year)`.

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

Both commands say which files are missing. Once the files exist, the dashboard sections can be built on them.

## Check before relying on results

- Thresholds in `rulebook/ews.yaml` and every elasticity in `rulebook/spillover.yaml` are drafts.
- Spot-check a few values against the source pages.
- Keep licensed data (Bloomberg, LSEG, paid Comtrade) out of the public repo. Store it only in the private copy.
