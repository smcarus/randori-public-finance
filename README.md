# Randori Municipal Finance

One codebase, three versions: a web app (installable, works offline), a macOS desktop app (Electron) and an Android app (Capacitor). All three run the same `web/` files and the same calculation engine.

**Illustrative only.** Every figure is for "Town of Example", a hypothetical Massachusetts town. Nothing here is advice to any town or issuer. Randori Resources' municipal advisor registration is pending.

## Also in this repo: sovereign-risk

`sovereign-risk/` holds `sovrisk`, Randori's Python package of sovereign, sub-sovereign and fiscal risk models
(RPF-01 to RPF-06; RPF stands for Randori Public Finance). It has its own README, docs and tests: see
[sovereign-risk/README.md](sovereign-risk/README.md).

## What's inside

| Tab | Source | Status |
|---|---|---|
| Tax bill | M-06 School Building, M-07 Debt Exclusion Impact (Planning Models v1.0); DLS Tax Rate Options (commercial shift) | Tested: 630 values against the workbook |
| Capital plan and debt | M-08 Capital Plan v1.0; DLS maximum borrowing terms (Aug 11, 2017) | Tested: 330 values against M-08 |
| Five-year forecast | DLS Financial Forecast template layout; DLS levy limit method | **Draft model, sample figures, not in the Model Inventory.** Only the levy limit is tested (5 values) |
| Budget calendar | DLS Budget to Tax Rate Recap Calendar template | Dates shifted from the template |

Bond payments are also checked against the DLS Debt Service Calculator (12 values).

## What this public copy holds

This copy holds `sovereign-risk/` and a text export of the app page (`Randori Municipal Finance.md`). The app's
source (`web/`, `tests/`, `electron/`, `android/`, `scripts/`), its build and release steps and the source templates
are kept in the private repo.

## Known gaps

- Forecast needs a Model Inventory entry (the next free M- number; M-13 is retired, since it was the sovereign scorecard, now RPF-01) and a real test before it supports any recommendation.
- M-08 does not compound new growth at 2.5% the way the DLS levy limit worksheet does. The Capital plan tab keeps M-08 v1.0; the Forecast tab uses the DLS method. Fix in M-08 v1.1.
- M-06 School Building tab: row 30 column headings are shifted by one from column J on (labels only).
- Not built yet: cash flow (DLS Cash Flow Forecast tool) and financial indicators (DLS indicator template).
- Fonts load from Google Fonts when online; offline, the app falls back to system fonts.
