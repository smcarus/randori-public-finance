"""Load the rulebook, settings and data files."""
import csv
from dataclasses import dataclass, field
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def _num(s):
    if s is None or s == '':
        return None
    if s in ('True', 'False'):
        return s == 'True'
    try:
        f = float(s)
        return int(f) if f.is_integer() and '.' not in s and 'e' not in s.lower() else f
    except ValueError:
        return s


def read_csv(path):
    with open(path, newline='') as f:
        return [{k: _num(v) for k, v in row.items()} for row in csv.DictReader(f)]


@dataclass
class Config:
    rulebook: dict
    settings: dict
    countries: list
    regions: dict
    preliminary: dict
    debt_baseline: dict          # country -> {'fx_share': x, year: value}
    inputs: dict                 # country -> {id: value}
    drivers: list                # scenario driver definitions
    overrides: dict              # (country, id, scenario) -> value
    backtest_log: list
    var_log: list
    mc_portfolio: dict
    mc_draws: list               # rows of uniforms
    indicators: list = field(init=False)

    def __post_init__(self):
        self.indicators = self.rulebook['indicators']


def load_config(root=ROOT):
    root = Path(root)
    rulebook = yaml.safe_load(open(root / 'rulebook/rulebook.yaml'))
    settings = yaml.safe_load(open(root / 'rulebook/settings.yaml'))
    cty = read_csv(root / 'data/countries.csv')
    debt = {}
    for row in read_csv(root / 'data/debt_baseline.csv'):
        d = {'fx_share': row['fx_share']}
        for k, v in row.items():
            if k.isdigit():
                d[int(k)] = v
        debt[row['country']] = d
    inputs = {c['country']: {} for c in cty}
    for row in read_csv(root / 'data/inputs.csv'):
        inputs[row['country']][row['id']] = row['value']
    overrides = {(r['country'], r['id'], r['scenario']): r['value'] for r in read_csv(root / 'data/scenario_overrides.csv')}
    draws = []
    with open(root / 'data/mc_draws.csv', newline='') as f:
        rd = csv.reader(f)
        next(rd)
        for row in rd:
            draws.append([float(x) for x in row[1:]])
    return Config(
        rulebook=rulebook, settings=settings,
        countries=[c['country'] for c in cty],
        regions={c['country']: c['region'] for c in cty},
        preliminary={c['country']: c['preliminary_score'] for c in cty},
        debt_baseline=debt, inputs=inputs,
        drivers=read_csv(root / 'data/scenario_drivers.csv'), overrides=overrides,
        backtest_log=read_csv(root / 'data/backtest_log.csv'), var_log=read_csv(root / 'data/var_log.csv'),
        mc_portfolio={r['country']: r for r in read_csv(root / 'data/mc_portfolio.csv')}, mc_draws=draws)
