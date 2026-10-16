# Architecture

`sovrisk` is one Python package with five layers. Each layer reads only from the layers above it. Numbers a person
should review (weights, thresholds, stress sizes, scenarios) live in YAML files, not in code, so a change to one is a
pull request anyone can read.

```
  Inputs      rulebook/*.yaml      data/*.csv       tests/golden/ (Excel values)     connectors (IMF, WB, BIS, ...)
                    \                   |                   |                          /
  Engines      RPF-01 scorecard -> decision tools    RPF-02 PFRAM    RPF-04 SRDSF / LIC DSF
               RPF-03 muni        RPF-05 early warning   RPF-06 spillover
                    \                   |                   /
  Outputs      cli.py -> outputs/*.csv      dashboard.py -> one HTML page      python -m sovrisk.<module>
```

## Layers

| Layer | Where | What it holds |
| --- | --- | --- |
| Rulebook | `rulebook/*.yaml` | `rulebook.yaml` (RPF-01 pillars, indicators, weights, thresholds) and `settings.yaml` (RPF-01 blend, caps, stress shocks, backtest, Monte Carlo, PRI and restructuring settings), both generated from the workbook; `levers.yaml`, `muni.yaml`, `ews.yaml` and `spillover.yaml`, written by hand with comments. See [RULEBOOK.md](RULEBOOK.md) |
| Data | `data/` | Input CSVs and YAML. Analyst inputs are header-only templates in the public repo; illustrative rows are labelled. RPF-05 and RPF-06 data files are not in the repo until real data is loaded (see [DATA.md](DATA.md)) |
| Connectors | `imf.py`, `connectors.py`, `spillover_data.py` | Fetch and parse functions for the IMF (its SDMX API, through the sdmx1 client `sdmx.Client('IMF_DATA')`), World Bank, BIS and UN Comtrade. Not yet run against live responses: those hosts are blocked in the build environment |
| Engines | one module or package per model | The calculations (below). `config.py` loads the rulebook and data files and defines `ROOT`, the repo folder every engine reads from |
| Outputs | `cli.py`, `dashboard.py`, each engine's `main()` | Result tables in `outputs/`, one self-contained HTML dashboard, and a console report per engine |

## Engines

| Model | Files | How it is built |
| --- | --- | --- |
| RPF-01 sovereign scorecard | `debt.py` -> `inputs.py` -> `scoring.py` -> `model.py` | Port of the Randori workbook, tab by tab. `debt.py` builds debt stress paths, `inputs.py` derives stress indicators and the best and worst cases, `scoring.py` scores indicators and pillars, `model.py` runs all cases and the sensitivity table |
| RPF-01 decision tools | `backtest.py`, `montecarlo.py`, `pri.py`, `restructuring.py`, `default_fit.py`, `decisions.py`, `levers.py` | Ports of the workbook's decision tabs; `decisions.py` runs them on the data files; `levers.py` is Python only |
| RPF-02 PPP fiscal risk | `pfram.py` | Port of IMF and World Bank PFRAM 2.0. `run_project` computes one project, `solve_effective_rate` reproduces the EIR_Seek macro, `portfolio` adds projects up |
| RPF-03 municipal scorecard | `muni.py` | Python only |
| RPF-04 MAC SRDSF | `srdsf/` | One file per template sheet, plus helpers (`basedb.py`, `identfin.py`, `gfn.py`, ...). `book.py` holds the workbook in memory, `xl.py` reimplements the Excel functions the template uses, `fan.py` and `gfn.py` port the two VBA macros, and `run.py` chains the sheets |
| RPF-04 LIC DSF | `licdsf/` | One file per group of template sheets. Reuses `srdsf/book.py`; `run.py` chains the sheets the same way |
| RPF-05 early warning | `ews.py` | Python only |
| RPF-06 spillover | `spillover.py` | Python only; `spillover_data.py` builds its input files |

### Chaining the Excel ports

The template sheets read each other in cycles (for example IdentFin, ResidFin and BaseDB in the MAC SRDSF), although
no single cell is circular. Each `run.py` therefore finds every module in its package that defines `SHEETS` and
`compute(book, sheet)`, computes the sheets in a dependency-friendly order, and repeats the sequence
(Gauss-Seidel) until a pass changes no value. Sheets whose inputs did not change are skipped, except in the first
pass and the final, confirming pass. A new sheet port joins the run as soon as its file exists. Macros run
after the formulas settle, and the formulas are recomputed after each one, as Excel recalculates after a macro.

## Interactions

Most models run on their own and meet only in the dashboard. The links that exist in code:

- **Score to default probability.** `backtest.pd_from_score` turns the RPF-01 country score into a default
  probability, which drives the PRI premium (`pri.py`), the Monte Carlo portfolio loss (`montecarlo.py`) and bond
  recovery (`restructuring.py`). Once `default_fit.py` has fitted coefficients, `decisions.py` blends the fitted
  probability with the scorecard's in log-odds and compares both with the CDS-implied probability.
- **Levers re-run the scorecard.** `levers.py` changes indicator values and re-runs scoring and the decision tools
  exactly.
- **Muni reuses one function.** `muni.py` uses `scoring._interp` (five thresholds to a 0-100 score) and nothing
  else from RPF-01.
- **The dashboard reads everything.** `dashboard.py` calls every engine, including a fresh MAC SRDSF run on the
  template sample, and embeds the results and the world map in one page.

Proposed links, not built:

- The RPF-04 gross financing need fills the `gfn_gdp` column of the RPF-05 panel. Today it is entered by hand.
- An RPF-06 scenario's GDP hit becomes a stress case for RPF-01 and RPF-04.

## Conventions

- Every model has a `python -m` command. RPF-03, RPF-05 and RPF-06 carry a `MODEL` string (ID and version) that their output repeats.
- A missing input drops out and the remaining weights are rescaled; nothing is filled with made-up values.
- Ports keep the template's own slips so results match, and list them in a `QUIRKS` constant.
- Illustrative rows are labelled (EXAMPLE, hypothetical town or project names).
