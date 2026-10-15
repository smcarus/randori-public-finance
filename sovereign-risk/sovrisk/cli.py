"""Command line: run the model and write result tables.

    python -m sovrisk.cli --out outputs
"""
import argparse
import csv
from pathlib import Path

from . import load_config, run_model
from .backtest import pd_backtest, var_backtest
from .montecarlo import simulate


def main(argv=None):
    ap = argparse.ArgumentParser(description='run the M-13 sovereign risk model (v0.5, UNTESTED, PRELIMINARY).')
    ap.add_argument('--root', default=None, help='repository root holding rulebook/ and data/')
    ap.add_argument('--out', default='outputs')
    a = ap.parse_args(argv)
    cfg = load_config(a.root) if a.root else load_config()
    m = run_model(cfg)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    names = cfg.rulebook['pillars']
    with open(out / 'pillars.csv', 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['country', 'region', 'scenario', 'pillar', 'pillar_name', 'wtd_avg', 'worst_core', 'raw', 'triggers',
                    'adjust', 'floor', 'final', 'country_score', 'grade', 'small_state'])
        for cn in cfg.countries:
            for case in ('base', 'best', 'worst'):
                r = m[cn][case]
                for p in range(1, 8):
                    d = r['pillars'][p]
                    w.writerow([cn, cfg.regions[cn], case, p, names[p]] + [d[k] for k in
                               ('wtd_avg', 'worst_core', 'raw', 'triggers', 'adjust', 'floor', 'final')]
                               + [r['score'], r['grade'], r['small_state']])
    with open(out / 'indicators.csv', 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['country', 'scenario', 'pillar', 'id', 'value', 'score', 'weight_used', 'included', 'sensitivity_points_per_band'])
        for cn in cfg.countries:
            for case in ('base', 'best', 'worst'):
                for iid, d in m[cn][case]['indicators'].items():
                    w.writerow([cn, case, d['pillar'], iid, d['value'], d['score'], d['weight'], int(d['included']),
                                m[cn]['sensitivity'][iid] if case == 'base' else None])
    mc = simulate(cfg, m)
    with open(out / 'monte_carlo.csv', 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['measure', 'value'])
        for cl, v, e in zip(cfg.settings['monte_carlo']['confidence_levels'], mc['var'], mc['es']):
            w.writerow([f'VaR {cl:.1%}', v])
            w.writerow([f'ES {cl:.1%}', e])
        for k in ('expected_loss', 'analytic_expected_loss', 'sd', 'p_one_default', 'p_two_defaults', 'max_loss'):
            w.writerow([k, mc[k]])
    bt, vb = pd_backtest(cfg), var_backtest(cfg)
    print(f"Scores written to {out}/. Belize {m['Belize']['base']['score']:.1f}, Chile {m['Chile']['base']['score']:.1f}. "
          f"99% VaR {mc['var'][1]:.1f}. Backtest forecasts with outcomes: {bt['n']}; VaR periods: {vb['periods']}.")


if __name__ == '__main__':
    main()
