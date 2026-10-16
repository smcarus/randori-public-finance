"""Default probabilities fitted to real default history, with confidence bands and a market benchmark.

Pipeline (needs network access to the IMF and World Bank hosts; default dates from the BoC-BoE
database are supplied as a file):
  1. build a country-year panel (connectors.py) with features known at the start of each year;
  2. label a year 1 if a new default or restructuring starts within the horizon (BoC-BoE database);
  3. fit a logit (IRLS), bootstrap by country for parameter uncertainty, test walk-forward;
  4. blend the fitted PD with the scorecard PD in log-odds; compare with market-implied PDs.
"""
import math

import numpy as np


def logit_fit(X, y, l2=1e-6, iters=100, tol=1e-10):
    """Logistic regression by iteratively reweighted least squares. X includes an intercept column."""
    X, y = np.asarray(X, float), np.asarray(y, float)
    b = np.zeros(X.shape[1])
    for _ in range(iters):
        p = 1 / (1 + np.exp(-X @ b))
        W = p * (1 - p)
        H = X.T @ (X * W[:, None]) + l2 * np.eye(X.shape[1])
        step = np.linalg.solve(H, X.T @ (y - p) - l2 * b)
        b += step
        if np.max(np.abs(step)) < tol:
            break
    return b


def predict(b, X):
    return 1 / (1 + np.exp(-np.asarray(X, float) @ b))


def cluster_bootstrap(X, y, groups, draws=500, seed=0):
    """Resample whole countries with replacement; returns array of coefficient draws."""
    rng = np.random.default_rng(seed)
    X, y, groups = np.asarray(X, float), np.asarray(y, float), np.asarray(groups)
    ids = np.unique(groups)
    idx = {g: np.where(groups == g)[0] for g in ids}
    out = []
    for _ in range(draws):
        pick = rng.choice(ids, size=len(ids), replace=True)
        rows = np.concatenate([idx[g] for g in pick])
        if y[rows].sum() == 0:
            continue
        out.append(logit_fit(X[rows], y[rows], l2=1e-3))
    return np.array(out)


def pd_band(B, x, band=(0.05, 0.95)):
    ps = 1 / (1 + np.exp(-(B @ np.asarray(x, float))))
    return float(np.quantile(ps, band[0])), float(np.median(ps)), float(np.quantile(ps, band[1]))


def auc(p, y):
    p, y = np.asarray(p), np.asarray(y)
    pos, neg = p[y == 1], p[y == 0]
    if len(pos) == 0 or len(neg) == 0:
        return None
    return float(((pos[:, None] > neg[None, :]).sum() + 0.5 * (pos[:, None] == neg[None, :]).sum()) / (len(pos) * len(neg)))


def walk_forward(X, y, years, first_test_year):
    """Refit each year on data before it; score that year out of sample. Returns (pred, y) arrays."""
    X, y, years = np.asarray(X, float), np.asarray(y, float), np.asarray(years)
    P, Y = [], []
    for yr in sorted(set(years[years >= first_test_year])):
        tr, te = years < yr, years == yr
        if y[tr].sum() == 0:
            continue
        b = logit_fit(X[tr], y[tr], l2=1e-3)
        P.extend(predict(b, X[te]))
        Y.extend(y[te])
    return np.array(P), np.array(Y)


def blend_pd(fitted, scorecard, w):
    """Log-odds blend: w on the fitted PD, 1 - w on the scorecard PD. Either may be None."""
    if fitted is None:
        return scorecard
    if scorecard is None:
        return fitted
    lo = lambda p: math.log(p / (1 - p))
    z = w * lo(fitted) + (1 - w) * lo(scorecard)
    return 1 / (1 + math.exp(-z))


def cds_implied_pd(spread_bps, recovery=0.4, years=1):
    """Constant-hazard approximation: hazard = spread / (1 - recovery); PD over `years` = 1 - exp(-hazard x years)."""
    if spread_bps is None:
        return None
    h = spread_bps / 10000 / (1 - recovery)
    return 1 - math.exp(-h * years)


def benchmark_gap(model_pd, market_pd, tol):
    """Log-odds gap model minus market and a flag when it exceeds the tolerance."""
    if model_pd is None or market_pd is None:
        return None, None
    lo = lambda p: math.log(p / (1 - p))
    g = lo(model_pd) - lo(market_pd)
    return g, ('Model above market' if g > tol else 'Model below market' if g < -tol else 'Within tolerance')
