"""Backtests: Brier score, calibration by PD bin, Kupiec proportion-of-failures (port of Backtest and VaR Backtest)."""
import math

from scipy.stats import chi2


def pd_from_score(score, a, b, cap=None):
    p = 1 / (1 + math.exp(-(a + b * score)))
    return p if cap is None else min(cap, p)


def kupiec(x, T, p):
    """Kupiec POF likelihood-ratio statistic and chi-squared(1) p-value; None when undefined."""
    if T == 0 or p is None or not 0 < p < 1:
        return None, None
    lr = -2 * ((T - x) * math.log(1 - p) + x * math.log(p))
    if x < T:
        lr += 2 * (T - x) * math.log(1 - x / T)
    if x > 0:
        lr += 2 * x * math.log(x / T)
    return lr, float(chi2.sf(lr, 1))


def _included(row, include_synthetic, predictor=None):
    t = row['row_type']
    ok_type = t in ('Live', 'Historical') or (t == 'Synthetic' and include_synthetic == 1)
    ok_pred = predictor is None or predictor == 'All' or row['predictor'] == predictor
    return ok_type and ok_pred


def pd_backtest(cfg, settings=None):
    s = settings or cfg.settings['backtest']
    rows = []
    for r in cfg.backtest_log:
        if r['score'] is None or r['outcome'] is None or not _included(r, s['include_synthetic'], s['predictor']):
            continue
        rows.append((pd_from_score(r['score'], s['pd_a'], s['pd_b']), r['outcome']))
    n = len(rows)
    out = {'n': n, 'events': sum(y for _, y in rows)}
    if n == 0:
        out.update(observed_rate=None, mean_pd=None, brier=None, climatology=None, skill=None, lr=None, p_value=None, bins=[])
        return out
    obs = out['events'] / n
    mean_pd = sum(p for p, _ in rows) / n
    brier = sum((p - y) ** 2 for p, y in rows) / n
    clim = obs * (1 - obs)
    lr, pv = kupiec(out['events'], n, mean_pd)
    out.update(observed_rate=obs, mean_pd=mean_pd, brier=brier, climatology=clim,
               skill=None if clim == 0 else 1 - brier / clim, lr=lr, p_value=pv,
               result=None if pv is None else ('Reject' if pv < s['alpha'] else 'Pass'))
    edges = s['bin_edges']
    bins = []
    for k, lo in enumerate(edges):
        hi = edges[k + 1] if k + 1 < len(edges) else 1
        sel = [(p, y) for p, y in rows if max(j for j, e in enumerate(edges) if p >= e) == k]
        T = len(sel)
        if T == 0:
            bins.append({'bin': k + 1, 'from': lo, 'to': hi, 'n': 0, 'events': 0})
            continue
        x = sum(y for _, y in sel)
        mp = sum(p for p, _ in sel) / T
        lr_, pv_ = kupiec(x, T, mp)
        bins.append({'bin': k + 1, 'from': lo, 'to': hi, 'n': T, 'mean_pd': mp, 'observed_rate': x / T,
                     'expected': mp * T, 'events': x, 'lr': lr_, 'p_value': pv_,
                     'result': 'Reject' if pv_ < s['alpha'] else 'Pass'})
    out['bins'] = bins
    return out


def var_backtest(cfg, settings=None):
    s = settings or cfg.settings['var_backtest']
    rows = [r for r in cfg.var_log if r['var_forecast'] is not None and r['realized_loss'] is not None
            and _included(r, s['include_synthetic'])]
    T = len(rows)
    x = sum(1 for r in rows if r['realized_loss'] > r['var_forecast'])
    p = 1 - s['confidence']
    lr, pv = kupiec(x, T, p) if T else (None, None)
    return {'periods': T, 'exceptions': x, 'expected_rate': p, 'observed_rate': x / T if T else None,
            'expected_exceptions': T * p, 'lr': lr, 'p_value': pv,
            'result': None if pv is None else ('Reject' if pv < s['alpha'] else 'Pass')}
