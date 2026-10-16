"""RPF-05 macro early-warning panel: green / amber / red ratings on external, credit and price indicators, each
country's own-history percentiles, and a warning score weighted by the signals method.

    python -m sovrisk.ews                  # latest year for every country in data/ews_panel.csv
    python -m sovrisk.ews --country ARG    # one country, indicator by indicator
    python -m sovrisk.ews --year 2024 --out outputs   # ews_table.csv

Inputs: data/ews_panel.csv (country, year, one column per indicator; see rulebook/ews.yaml for ids and units), built
from real series by connectors.build_ews_panel(); optional data/crisis_dates.csv (country, year, type).
Thresholds and fallback weights live in rulebook/ews.yaml. With crisis dates, weights come from the noise-to-signal
ratio (Kaminsky, Lizondo and Reinhart 1998). Credit gaps missing from the BIS are computed with a one-sided HP filter
on credit_gdp, as the BIS does. NOT A RATING. Version 0.1 is untested and has no country data in the repository.
"""
import argparse
import csv
import math
from pathlib import Path

import numpy as np
import yaml

from .config import ROOT, read_csv

MODEL = 'RPF-05 v0.1'
RANK = {'green': 0, 'amber': 1, 'red': 2}


def load(root=ROOT):
    """Rulebook, panel rows and crisis dates. Missing files give empty lists and a note saying so."""
    root = Path(root)
    rb = yaml.safe_load(open(root / 'rulebook' / 'ews.yaml'))
    notes, out = [], {'rulebook': rb}
    for key, name in (('panel', 'ews_panel.csv'), ('crises', 'crisis_dates.csv')):
        path = root / 'data' / name
        out[key] = read_csv(path) if path.exists() else []
        if not path.exists():
            notes.append(f'data/{name} is missing' + (': no country data to rate. Build it from real series with '
                                                       'sovrisk.connectors.build_ews_panel().' if key == 'panel' else
                                                       ': using the fallback weights in rulebook/ews.yaml.'))
    out['notes'] = notes
    return out


def check_rulebook(rb):
    errs = []
    for i in rb['indicators']:
        if i.get('bad') not in ('low', 'high'):
            errs.append(f"{i['id']}: bad must be low or high")
        elif (i['red'] > i['amber']) if i['bad'] == 'low' else (i['red'] < i['amber']):
            errs.append(f"{i['id']}: red threshold is on the safe side of amber")
        if i.get('weight', 0) < 0:
            errs.append(f"{i['id']}: negative weight")
    return errs


def _val(v):
    if v is None or v == '':
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(f) else f


def rate(ind, v):
    """green / amber / red, or None when the value is missing. Breaching a threshold is strict (< or >)."""
    v = _val(v)
    if v is None:
        return None
    if ind['bad'] == 'low':
        return 'red' if v < ind['red'] else 'amber' if v < ind['amber'] else 'green'
    return 'red' if v > ind['red'] else 'amber' if v > ind['amber'] else 'green'


def percentile(v, history):
    """Percentile rank of v in the country's own history (which includes v): 0 = lowest value, 100 = highest.
    Ties count half. None with fewer than two observations."""
    v = _val(v)
    h = [x for x in (_val(x) for x in history) if x is not None]
    if v is None or len(h) < 2:
        return None
    return 100 * (sum(x < v for x in h) + 0.5 * (sum(x == v for x in h) - 1)) / (len(h) - 1)


# ---- one-sided HP filter (BIS credit gap) ------------------------------------------------------------------------

def hp_trend(y, lam):
    """Two-sided Hodrick-Prescott trend: solves (I + lam K'K) tau = y, K the second-difference matrix."""
    y = np.asarray(y, float)
    n = len(y)
    if n < 3:
        return y.copy()
    K = np.zeros((n - 2, n))
    for i in range(n - 2):
        K[i, i:i + 3] = (1, -2, 1)
    return np.linalg.solve(np.eye(n) + lam * K.T @ K, y)


def hp_one_sided(y, lam, min_obs=1):
    """One-sided HP trend: the trend at t is the last point of a two-sided HP run on y[0..t] only, so it uses no
    data after t. Points before min_obs observations are NaN."""
    y = np.asarray(y, float)
    out = np.full(len(y), np.nan)
    for t in range(max(min_obs, 1) - 1, len(y)):
        out[t] = hp_trend(y[:t + 1], lam)[-1]
    return out


def credit_gap_series(years, credit_gdp, lam, min_obs):
    """{year: gap} from credit-to-GDP (% of GDP). The filter runs on the unbroken run of years ending at each year."""
    pts = sorted((int(y), _val(v)) for y, v in zip(years, credit_gdp) if _val(v) is not None)
    gaps, run = {}, []
    for y, v in pts:
        if run and y != run[-1][0] + 1:
            run = []
        run.append((y, v))
        if len(run) >= min_obs:
            gaps[y] = v - hp_trend([x for _, x in run], lam)[-1]
    return gaps


def reer_dev_series(years, reer, n):
    """{year: % deviation of the REER index from the average of the n previous years} (data up to t-1 only)."""
    d = {int(y): _val(v) for y, v in zip(years, reer) if _val(v) is not None}
    out = {}
    for y, v in d.items():
        past = [d.get(y - k) for k in range(1, n + 1)]
        if all(p is not None for p in past):
            out[y] = 100 * (v / (sum(past) / n) - 1)
    return out


def fill_derived(rb, rows):
    """Copy of the panel with credit_gap and reer_dev filled where blank, from credit_gdp and reer. Cells filled here
    are listed in each row's '_derived'. BIS gaps and supplied deviations are never overwritten."""
    rows = [dict(r) for r in rows]
    by = {}
    for r in rows:
        by.setdefault(r['country'], []).append(r)
    hp = rb.get('hp', {})
    for rs in by.values():
        ys = [r['year'] for r in rs]
        gaps = credit_gap_series(ys, [r.get('credit_gdp') for r in rs], hp.get('lambda_annual', 1562.5),
                                 hp.get('min_obs', 10))
        devs = reer_dev_series(ys, [r.get('reer') for r in rs], rb.get('reer_trend_years', 10))
        for r in rs:
            r.setdefault('_derived', [])
            for col, src in (('credit_gap', gaps), ('reer_dev', devs)):
                if _val(r.get(col)) is None and r['year'] in src:
                    r[col] = src[r['year']]
                    r['_derived'].append(col)
    return rows


# ---- signals method ----------------------------------------------------------------------------------------------

def nsr_table(rb, rows, crises):
    """Noise-to-signal ratio per indicator over a crisis panel (KLR adjusted form):
        A signal, crisis starts within the window   B signal, no crisis in window
        C no signal, crisis within the window       D no signal, no crisis
        NSR = [B / (B + D)] / [A / (A + C)]
    Window: crisis starts in years t+1 .. t+window_years. Crisis-start years are left out. NSR is inf when A = 0."""
    sg = rb.get('signals', {})
    win, at, types = sg.get('window_years', 2), RANK[sg.get('signal_at', 'amber')], sg.get('crisis_types') or []
    starts = {}
    for c in crises:
        if not types or str(c.get('type', '')).strip().lower() in types:
            starts.setdefault(c['country'], set()).add(int(c['year']))
    out = {}
    for ind in rb['indicators']:
        A = B = C = D = 0
        for r in rows:
            s = starts.get(r['country'], set())
            y = int(r['year'])
            g = rate(ind, r.get(ind['id']))
            if g is None or y in s:
                continue
            crisis, sig = any(y + k in s for k in range(1, win + 1)), RANK[g] >= at
            A += sig and crisis
            B += sig and not crisis
            C += crisis and not sig
            D += not crisis and not sig
        hit = A / (A + C) if A + C else 0
        noise = B / (B + D) if B + D else 0
        out[ind['id']] = {'A': A, 'B': B, 'C': C, 'D': D, 'nsr': noise / hit if hit else math.inf}
    return out


def nsr_weights(nsr):
    """weight = (1 / NSR) normalised to 1; indicators with NSR >= 1 (or no good signals) get 0."""
    inv = {k: (1 / v['nsr'] if v['nsr'] > 0 else math.inf) if v['nsr'] < 1 else 0.0 for k, v in nsr.items()}
    if any(math.isinf(x) for x in inv.values()):     # no false alarms at all: share equally among those
        inv = {k: 1.0 if math.isinf(x) else 0.0 for k, x in inv.items()}
    tot = sum(inv.values())
    return {k: x / tot if tot else 0.0 for k, x in inv.items()}


# ---- table -------------------------------------------------------------------------------------------------------

def score_country(rb, rows, weights, year=None):
    """One country's rows -> per-indicator value, year used, rating, percentile; score 0-100; top drivers."""
    rows = sorted(rows, key=lambda r: int(r['year']))
    year = int(year) if year is not None else int(rows[-1]['year'])
    pts, stale = rb.get('points', {'green': 0, 'amber': 50, 'red': 100}), rb.get('stale_years', 1)
    inds, tot_w, tot = {}, 0.0, 0.0
    for ind in rb['indicators']:
        k = ind['id']
        have = [r for r in rows if _val(r.get(k)) is not None and year - stale <= int(r['year']) <= year]
        r = have[-1] if have else None
        v = _val(r[k]) if r else None
        g = rate(ind, v)
        hist = [r2.get(k) for r2 in rows if int(r2['year']) <= year]
        w = weights.get(k, 0.0)
        inds[k] = {'label': ind['label'], 'unit': ind['unit'], 'value': v, 'year': int(r['year']) if r else None,
                   'rating': g, 'percentile': percentile(v, hist), 'weight': w,
                   'derived': bool(r and k in r.get('_derived', []))}
        if g is not None and w > 0:
            tot_w += w
            tot += w * pts[g]
    for x in inds.values():
        x['points'] = x['weight'] * pts[x['rating']] / tot_w if x['rating'] is not None and tot_w and x['weight'] else None
    drivers = sorted((k for k, x in inds.items() if x['points']), key=lambda k: -inds[k]['points'])[:3]
    return {'year': year, 'score': tot / tot_w if tot_w else None, 'coverage': tot_w, 'indicators': inds, 'drivers': [inds[k]['label'] for k in drivers]}


def ews_table(cfg_or_panel=None, year=None, crises=None, rb=None):
    """Per country: indicators (value, rating, percentile), score, top drivers. Takes the dict from load() or a list of
    panel rows (then rb defaults to rulebook/ews.yaml and crises to none). Returns {'model', 'weights', 'weighting',
    'nsr', 'countries', 'notes'}."""
    if cfg_or_panel is None:
        cfg_or_panel = load()
    if isinstance(cfg_or_panel, dict):
        rb = rb or cfg_or_panel['rulebook']
        panel, crises = cfg_or_panel['panel'], crises if crises is not None else cfg_or_panel.get('crises', [])
        notes = list(cfg_or_panel.get('notes', []))
    else:
        rb = rb or yaml.safe_load(open(ROOT / 'rulebook' / 'ews.yaml'))
        panel, crises, notes = list(cfg_or_panel), crises or [], []
    errs = check_rulebook(rb)
    if errs:
        raise ValueError('rulebook/ews.yaml: ' + '; '.join(errs))
    panel = fill_derived(rb, panel)
    nsr = nsr_table(rb, panel, crises) if crises else None
    if nsr:
        weights, how = nsr_weights(nsr), 'signals (1/NSR)'
        if not sum(weights.values()):
            notes.append('no indicator has NSR < 1 on the crisis panel: falling back to rulebook weights.')
            nsr = None
    if not nsr:
        tw = sum(i.get('weight', 0) for i in rb['indicators'])
        weights, how = {i['id']: i.get('weight', 0) / tw for i in rb['indicators']}, 'rulebook'
    by = {}
    for r in panel:
        if year is None or int(r['year']) <= int(year):
            by.setdefault(r['country'], []).append(r)
    return {'model': MODEL, 'weights': weights, 'weighting': how, 'nsr': nsr, 'notes': notes,
            'countries': {c: score_country(rb, rs, weights, year) for c, rs in sorted(by.items())}}


def main(argv=None):
    ap = argparse.ArgumentParser(description=f'{MODEL} macro early-warning panel (untested).')
    ap.add_argument('--root', default=None)
    ap.add_argument('--country', default=None)
    ap.add_argument('--year', type=int, default=None)
    ap.add_argument('--out', default=None, help='folder for ews_table.csv')
    a = ap.parse_args(argv)
    t = ews_table(load(Path(a.root) if a.root else ROOT), year=a.year)
    print(f"{MODEL}, untested. Warning score 0 (all green) to 100 (all red). Weights: {t['weighting']}.")
    for n in t['notes']:
        print('Note: ' + n)
    for c, s in t['countries'].items():
        if a.country and c != a.country:
            continue
        sc = 'n/a' if s['score'] is None else f"{s['score']:5.1f}"
        print(f"{c:6s} {s['year']}  score {sc}  drivers: {', '.join(s['drivers']) or 'none'}")
        if a.country:
            for k, x in s['indicators'].items():
                if x['value'] is None:
                    print(f"    {x['label'][:40]:40s} no data, drops out")
                    continue
                pc = '' if x['percentile'] is None else f"  own-history pct {x['percentile']:5.1f}"
                print(f"    {x['label'][:40]:40s} {x['value']:9.2f} {x['unit']:9s} ({x['year']}) {x['rating']:5s}"
                      f"  weight {x['weight']:.2f}{pc}{'  (computed)' if x['derived'] else ''}")
    if a.out:
        out = Path(a.out)
        out.mkdir(parents=True, exist_ok=True)
        with open(out / 'ews_table.csv', 'w', newline='') as f:
            w = csv.writer(f)
            w.writerow(['country', 'year', 'model', 'score', 'indicator', 'value', 'value_year', 'rating', 'percentile',
                        'weight', 'points', 'derived'])
            for c, s in t['countries'].items():
                for k, x in s['indicators'].items():
                    w.writerow([c, s['year'], MODEL, s['score'], k, x['value'], x['year'], x['rating'], x['percentile'],
                                x['weight'], x['points'], x['derived']])
        print(f'Table written to {out}/ews_table.csv')


if __name__ == '__main__':
    main()
