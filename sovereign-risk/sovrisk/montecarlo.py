"""Monte Carlo portfolio default loss with a one-factor t (or Gaussian) copula (port of the Monte Carlo tabs)."""
import numpy as np
from scipy import stats

from .backtest import pd_from_score


def scores_for_mc(cfg, model, source):
    """Model score from the chosen case; preliminary score where the model has none."""
    out = {}
    for cn in cfg.countries:
        s = model[cn][source.lower()]['score']
        out[cn] = (s, f'Model {source}') if s else (cfg.preliminary[cn], 'Preliminary')
    return out


def simulate(cfg, model, settings=None, draws=None):
    s = settings or cfg.settings['monte_carlo']
    bt = cfg.settings['backtest']
    U = np.asarray(draws if draws is not None else cfg.mc_draws, dtype=float)
    cs = cfg.countries
    nc = len(cs)
    sc = scores_for_mc(cfg, model, s['score_source'])
    pd_ = np.array([pd_from_score(sc[c][0], bt['pd_a'], bt['pd_b'], s['pd_cap']) for c in cs])
    E = np.array([cfg.mc_portfolio[c]['exposure'] for c in cs], float)
    m = np.array([cfg.mc_portfolio[c]['lgd_mean'] for c in cs], float)
    sd = np.array([cfg.mc_portfolio[c]['lgd_sd'] for c in cs], float)
    k = m * (1 - m) / sd ** 2 - 1
    a, b = m * k, (1 - m) * k
    rho, df = s['rho'], s['df']
    gauss = df >= 1000
    thr = stats.norm.ppf(pd_) if gauss else stats.t.ppf(pd_, df)
    Z = stats.norm.ppf(U[:, 0])
    W = np.ones(len(U)) if gauss else np.sqrt(stats.chi2.isf(U[:, 1], df) / df)
    eps = stats.norm.ppf(U[:, 2:2 + nc])
    lgd = stats.beta.ppf(U[:, 2 + nc:2 + 2 * nc], a, b)
    X = (np.sqrt(rho) * Z[:, None] + np.sqrt(1 - rho) * eps) / W[:, None]
    loss = np.where(X < thr, E * lgd, 0.0)
    tot = loss.sum(axis=1)
    ndef = (loss > 0).sum(axis=1)
    res = {'pd': dict(zip(cs, pd_)), 'score_used': sc, 'analytic_expected_loss': float((pd_ * E * m).sum()),
           'expected_loss': float(tot.mean()), 'sd': float(tot.std(ddof=1)),
           'p_one_default': float((ndef >= 1).mean()), 'p_two_defaults': float((ndef >= 2).mean()),
           'max_loss': float(tot.max()), 'var': [], 'es': []}
    for cl in s['confidence_levels']:
        v = float(np.percentile(tot, cl * 100))
        res['var'].append(v)
        res['es'].append(float(tot[tot >= v].mean()))
    v2 = res['var'][1]
    tail = tot >= v2
    contrib = loss[tail].mean(axis=0)
    res['es_contribution'] = dict(zip(cs, contrib))
    res['es_share'] = dict(zip(cs, contrib / res['es'][1]))
    nb = s['histogram_bands']
    width = max(res['max_loss'], 1) / nb
    hist = []
    for i in range(nb):
        lo, hi = i * width, (i + 1) * width
        hist.append(int(((tot >= lo) & (tot <= hi)).sum() if i == 0 else ((tot > lo) & (tot <= hi)).sum()))
    res['histogram'] = hist
    res['default_counts'] = [int((ndef == j).sum()) for j in range(6)] + [int((ndef >= 6).sum())]
    res['total_loss'] = tot
    return res
