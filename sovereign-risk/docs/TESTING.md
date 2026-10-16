# Testing

```
pip install -e .[test]
pytest -q
```

Two kinds of test run here. The Excel ports are checked for **parity**: the port must reproduce the template's own
values. Randori's own models are checked with **known answers**: small hand-made inputs whose results were worked out
by hand from the formulas. Neither kind validates a model against real outcomes. A model stays marked untested until
it has been run on real data and the results reviewed.

## Parity with the Excel templates

The reference values come from the templates themselves and are saved in `tests/golden/`:

| Model | Reference | Saved by | Checked by |
| --- | --- | --- | --- |
| RPF-01 scorecard | the Randori workbook's cached values | `scripts/extract_workbook.py` | `test_parity.py` (private: it needs analyst inputs) |
| RPF-02 PFRAM | the PFRAM 2.0 workbook with the illustrative projects written in, recalculated in LibreOffice | `scripts/pfram_golden.py` | `test_pfram.py` |
| RPF-04 MAC SRDSF | the template's cached values for every cell | `scripts/srdsf_golden.py` | `test_srdsf.py` (each sheet), `test_srdsf_run.py` (whole chain), `test_srdsf_fan.py`, `test_srdsf_gfn.py` (the two macros) |
| RPF-04 MAC SRDSF, changed inputs | the template with 101 inputs changed, recalculated in LibreOffice | `scripts/srdsf_alt_golden.py` | `test_srdsf_run.py` |
| RPF-04 LIC DSF | the template's cached values for every cell | `scripts/srdsf_golden.py` | `test_licdsf.py`, `test_licdsf_run.py` (private: the sample is real country data) |
| RPF-04 LIC DSF, changed inputs | `tests/licdsf_oracle.py`, an independent evaluator of the template's own formulas | computed at test time | `test_licdsf_run.py` (private) |

Each port is checked three ways where the template allows it:

1. **Sheet by sheet.** Each ported sheet runs with every other sheet held at the template's values and must match
   every formula cell, Excel errors included.
2. **Whole chain.** Every formula cell is blanked, the chain runs from inputs only, and every cell must match again.
3. **Changed inputs.** Inputs are changed and the result is compared with a fresh recalculation, so the port is
   checked off the template's own sample. LibreOffice does this for PFRAM and the MAC SRDSF. It cannot recalculate
   the LIC DSF template, so `licdsf_oracle.py` reads the formulas from the .xlsm with openpyxl and evaluates them.

A number matches when it is within relative 1e-7 (absolute 1e-6 near zero); the fan chart macro's cells must match
to 1e-12. Template slips kept on purpose are listed in each module's
`QUIRKS`, so a reviewer can tell a kept slip from a porting error.

### Regenerating golden values

Run the script with the template's path; it writes into `tests/golden/<model>/`.

```
python scripts/pfram_golden.py path/to/pfram2english.xlsm
python scripts/srdsf_golden.py path/to/mac-srdsf-template.xlsm tests/golden/srdsf
python scripts/srdsf_alt_golden.py path/to/mac-srdsf-template.xlsm
```

The LibreOffice scripts need `soffice` on the path. Commit regenerated files together with the code change that
needed them, and say why in the commit message.

## Known-answer tests

| File | Covers |
| --- | --- |
| `test_engine.py` | RPF-01 scoring interpolation, PD from score, Kupiec test, bond cash flows and haircuts, CDS-implied PD and blending, logit fit |
| `test_levers_dashboard.py` | RPF-01 levers, and the dashboard's data and sections (including RPF-04, RPF-05 and RPF-06) |
| `test_muni.py` | RPF-03 rulebook checks, scoring, missing indicators, the Massachusetts benchmark count, any-state scoring |
| `test_ews.py` | RPF-05 ratings, own-history percentiles, signals-method weights, one-sided HP filter, missing data |
| `test_spillover.py` | RPF-06 first and second rounds, channel split, damping, refusal of a matrix that does not shrink |
| `test_imf.py` | IMF data through the sdmx1 client: the WEO and IMTS keys sent, unit scaling, blank values dropped, a blocked host stopping with an error. Uses a hand-made SDMX-ML sample (`tests/fixtures/`), no network |

All inputs in these tests are hand-made (hypothetical towns, countries A, B and C). None is real data.

## What is private

Tests that need Randori's analyst inputs (`test_parity.py`) or real country data (`test_licdsf.py`,
`test_licdsf_run.py` and `tests/golden/licdsf/`) are kept in the private copy only, and the public repo's git
exclude file stops them being committed by mistake. The public test suite runs without them.
