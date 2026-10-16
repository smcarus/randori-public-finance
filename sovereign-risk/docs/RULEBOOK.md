# Changing the rulebook

Every number a reviewer should be able to question (weights, thresholds, stress sizes, elasticities, scenarios) is in
`rulebook/`, not in code. Changing one changes a model's results, so it goes through the same steps as a code change.

## Files

| File | Model | Written | What is in it |
| --- | --- | --- | --- |
| `rulebook.yaml` | RPF-01 | generated from the workbook by `scripts/extract_workbook.py` | Pillars, indicators, indicator weights, five-point thresholds |
| `settings.yaml` | RPF-01 | generated from the workbook | Pillar weights, worst-core blend, trigger caps, analyst adjustment limit, small-state rule, debt stress shocks, backtest, Monte Carlo, default fit, PRI and restructuring settings |
| `levers.yaml` | RPF-01 levers | by hand | Each lever's indicator effects. Illustrative magnitudes |
| `muni.yaml` | RPF-03 | by hand | Factors and weights, indicators with thresholds and their Massachusetts benchmark notes, stress cases |
| `ews.yaml` | RPF-05 | by hand | Indicators with amber and red thresholds, fallback weights, signals-method window, HP filter lambda |
| `spillover.yaml` | RPF-06 | by hand | Channels with elasticities and a source note for each, second-round damping, scenarios |

Each hand-written file starts with comments on units and the direction of risk. All values in them are drafts until
reviewed.

## How thresholds work

The RPF-01 and RPF-03 scorecards use five threshold points per indicator, from the value that scores 0 (lowest risk) to
the value that scores 100 (highest risk), scored in straight lines between them (`scoring._interp`). The points may
run up or down, so `[3, 4, 5, 6.5, 8]` (unemployment, higher is worse) and `[20, 15, 10, 6, 3]` (reserves, lower is
worse) are both valid. RPF-05 uses two points per indicator, amber and red, with `bad: low` or `bad: high`.

## Making a change

1. **Edit on a branch.** Change the YAML, not the code. For `rulebook.yaml` and `settings.yaml`, change the
   workbook and rerun `scripts/extract_workbook.py` so the two stay in step.
2. **Say where the number comes from.** Add or update the comment or `source` note: a publication, a template, or
   "draft, to verify".
3. **Bump the version.** Raise `version:` in the file and the model's `MODEL` string where it has one, and add a line to the model
   card's change log.
4. **Run the tests.** `pytest -q`. A change to a weight or threshold is expected to move some known-answer results;
   update those expected values in the same commit and say why in the commit message.
5. **Open a pull request** that lists every changed number with its old and new value and the reason. The model's
   reviewer approves it before it merges.
6. **Update the Model Inventory** with the new version once merged.

## What not to put in the rulebook

- Country, town or project data: that goes in `data/`, labelled with its source and year.
- Licensed data (Bloomberg, LSEG, paid Comtrade): keep it in the private copy only.
- Analyst inputs and adjustments for a specific country: these stay in the private `data/inputs.csv`.
