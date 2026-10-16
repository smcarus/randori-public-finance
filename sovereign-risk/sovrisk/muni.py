"""M-15 municipal credit scorecard: a 0-100 risk score for a Massachusetts city or town.

    python -m sovrisk.muni                 # score every town in data/muni_towns.csv
    python -m sovrisk.muni --town "Town E" # one town, factor by factor
    python -m sovrisk.muni --out outputs   # muni_scores.csv and muni_indicators.csv

Scores run from 0 (lowest risk) to 100 (highest risk), like the sovereign scorecard, with grades 1-10. Indicators,
thresholds, weights and stress cases live in rulebook/muni.yaml. Randori's own model, drawing on the factor families
in public rating methods. NOT A CREDIT RATING. Version 0.1 runs on ILLUSTRATIVE towns only and is untested.
"""
import argparse
import csv
from pathlib import Path

import yaml

from .config import ROOT, read_csv
from .scoring import _interp

MODEL = 'M-15 v0.1'


def load(root=ROOT):
    root = Path(root)
    rb = yaml.safe_load(open(root / 'rulebook' / 'muni.yaml'))
    path = root / 'data' / 'muni_towns.csv'
    towns = read_csv(path) if path.exists() else []
    return {'rulebook': rb, 'towns': towns}


def check_rulebook(rb):
    """Weights add to 1 for the factors and within each factor; every indicator has what it needs."""
    errs = []
    if abs(sum(f['weight'] for f in rb['factors'].values()) - 1) > 1e-9:
        errs.append('factor weights do not add to 1')
    for k in rb['factors']:
        w = sum(i['weight'] for i in rb['indicators'] if i['factor'] == k)
        if abs(w - 1) > 1e-9:
            errs.append(f'indicator weights in {k} add to {w:g}, not 1')
    for i in rb['indicators']:
        if i['factor'] not in rb['factors']:
            errs.append(f"{i['id']}: unknown factor {i['factor']}")
        if i.get('type', 'num') == 'num' and len(i.get('thresholds', [])) != 5:
            errs.append(f"{i['id']}: needs five thresholds")
    ids = {i['id'] for i in rb['indicators']}
    for name, steps in (rb.get('stress') or {}).items():
        errs += [f"stress {name}: unknown indicator {s['id']}" for s in steps if s['id'] not in ids]
    return errs


def _flag(v):
    if v is None or v == '':
        return None
    return 0.0 if str(v).strip().lower() in ('yes', 'y', 'true', '1') else 100.0


def indicator_score(ind, v):
    if v is None or v == '':
        return None
    if ind.get('type') == 'flag':
        return _flag(v)
    return _interp(float(v), ind['thresholds'])


def grade(score):
    return None if score is None else min(10, int(score // 10) + 1)


def score_town(rb, values):
    """Score one set of indicator values. Missing indicators drop out and their factor's weights are rescaled."""
    rows, factors = {}, {}
    for i in rb['indicators']:
        rows[i['id']] = {'factor': i['factor'], 'label': i['label'], 'unit': i['unit'], 'value': values.get(i['id']),
                         'score': indicator_score(i, values.get(i['id'])), 'weight': i['weight']}
    for k, f in rb['factors'].items():
        mine = [r for r in rows.values() if r['factor'] == k and r['score'] is not None]
        w = sum(r['weight'] for r in mine)
        factors[k] = {'label': f['label'], 'weight': f['weight'],
                      'score': sum(r['weight'] * r['score'] for r in mine) / w if w else None,
                      'coverage': w}
    avail = [f for f in factors.values() if f['score'] is not None]
    fw = sum(f['weight'] for f in avail)
    score = sum(f['weight'] * f['score'] for f in avail) / fw if fw else None
    for k, f in factors.items():          # points each indicator adds to the town score
        for r in rows.values():
            if r['factor'] == k:
                r['points'] = (f['weight'] / fw) * (r['weight'] / f['coverage']) * r['score'] \
                    if r['score'] is not None and f['coverage'] else None
    return {'score': score, 'grade': grade(score), 'factors': factors, 'indicators': rows,
            'coverage': sum(f['weight'] * f['coverage'] for f in factors.values())}


def stressed_values(rb, values, case):
    out = dict(values)
    for s in rb['stress'][case]:
        v = out.get(s['id'])
        if v is None or v == '':
            continue
        out[s['id']] = float(v) * s['mul'] if 'mul' in s else float(v) + s['add']
    return out


def percentiles(rb, towns):
    """Each town's percentile rank on each indicator among the towns scored (100 = riskiest)."""
    out = {t['town']: {} for t in towns}
    for i in rb['indicators']:
        sc = [(t['town'], indicator_score(i, t.get(i['id']))) for t in towns]
        vals = [s for _, s in sc if s is not None]
        for name, s in sc:
            out[name][i['id']] = None if s is None or len(vals) < 2 else \
                100 * (sum(v < s for v in vals) + 0.5 * (sum(v == s for v in vals) - 1)) / (len(vals) - 1)
    return out


def run_all(root=ROOT):
    d = load(root)
    rb = d['rulebook']
    errs = check_rulebook(rb)
    if errs:
        raise ValueError('rulebook/muni.yaml: ' + '; '.join(errs))
    pct = percentiles(rb, d['towns'])
    res = {}
    for t in d['towns']:
        base = score_town(rb, t)
        res[t['town']] = {'profile': t.get('profile'), 'population': t.get('population'),
                          'fiscal_year': t.get('fiscal_year'), 'note': t.get('note', ''), 'base': base,
                          'stress': {c: score_town(rb, stressed_values(rb, t, c)) for c in rb.get('stress', {})},
                          'percentile': pct[t['town']]}
    return {'model': MODEL, 'rulebook': rb, 'towns': res}


def main(argv=None):
    ap = argparse.ArgumentParser(description=f'{MODEL} municipal credit scorecard (ILLUSTRATIVE towns, not a rating).')
    ap.add_argument('--root', default=None)
    ap.add_argument('--town', default=None)
    ap.add_argument('--out', default=None, help='folder for muni_scores.csv and muni_indicators.csv')
    a = ap.parse_args(argv)
    r = run_all(Path(a.root) if a.root else ROOT)
    rb, cases = r['rulebook'], list(r['rulebook'].get('stress', {}))
    print(f"{MODEL}, untested, illustrative towns only. Scores 0 (lowest risk) to 100. Not a credit rating.")
    for name, t in sorted(r['towns'].items(), key=lambda kv: kv[1]['base']['score']):
        if a.town and name != a.town:
            continue
        b = t['base']
        st = ', '.join(f"{c} {t['stress'][c]['score']:.1f}" for c in cases)
        print(f"{name:10s} {t['profile'] or '':18s} score {b['score']:5.1f} grade {b['grade']:2d}  ({st})")
        if a.town:
            for k, f in b['factors'].items():
                print(f"    {f['label']:28s} {f['score']:5.1f}  weight {f['weight']:.0%}")
            for iid, x in sorted(b['indicators'].items(), key=lambda kv: -(kv[1]['points'] or 0)):
                print(f"      {x['label'][:44]:44s} {str(x['value']):>8s} {x['unit'][:22]:22s} "
                      f"score {x['score']:5.1f}  adds {x['points']:4.1f} pts")
    if a.out:
        out = Path(a.out)
        out.mkdir(parents=True, exist_ok=True)
        with open(out / 'muni_scores.csv', 'w', newline='') as f:
            w = csv.writer(f)
            w.writerow(['town', 'model', 'score', 'grade'] + [f'{k}_score' for k in rb['factors']]
                       + [f'{c} score' for c in cases])
            for name, t in r['towns'].items():
                b = t['base']
                w.writerow([name, MODEL, b['score'], b['grade']] + [b['factors'][k]['score'] for k in rb['factors']]
                           + [t['stress'][c]['score'] for c in cases])
        with open(out / 'muni_indicators.csv', 'w', newline='') as f:
            w = csv.writer(f)
            w.writerow(['town', 'indicator', 'factor', 'value', 'unit', 'score', 'points', 'percentile'])
            for name, t in r['towns'].items():
                for iid, x in t['base']['indicators'].items():
                    w.writerow([name, iid, x['factor'], x['value'], x['unit'], x['score'], x['points'],
                                t['percentile'][iid]])
        print(f'Tables written to {out}/')


if __name__ == '__main__':
    main()
