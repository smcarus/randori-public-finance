"""Glue for the decision modules: default PD table, insurance pricing of the policy book, bond recovery table."""
import math

from .backtest import pd_from_score
from .config import read_csv, ROOT
from .default_fit import benchmark_gap, blend_pd, cds_implied_pd
from .pri import PERILS, price_policy
from .restructuring import bond_recovery, deal_months, holdout_risk, recovery_at_default

FEATURES = ['debt_gdp', 'growth', 'inflation_log', 'ca_gdp', 'reserves_months', 'past_default_10y']


def _rows(name, root=ROOT):
    return read_csv(root / 'data' / name)


def default_table(cfg, model, root=ROOT):
    s, bt = cfg.settings['default_fit'], cfg.settings['backtest']
    coef = {r['term']: r['coefficient'] for r in _rows('default_coefficients.csv', root)}
    fitted_ready = all(coef.get(t) is not None for t in ['intercept'] + FEATURES)
    extra = {r['country']: r for r in _rows('default_features_extra.csv', root)}
    bands = {r['country']: r for r in _rows('default_bands.csv', root)}
    mkt = {r['country']: r for r in _rows('market_spreads.csv', root)}
    out = {}
    for cn in cfg.countries:
        raw = cfg.inputs[cn]
        score = model[cn]['base']['score']
        src = 'Model Base' if score else 'Preliminary'
        score = score if score else cfg.preliminary[cn]
        sc_pd = pd_from_score(score, bt['pd_a'], bt['pd_b'])
        dc = raw.get('debt_country')
        infl = raw.get('r_infl')
        feats = {'debt_gdp': cfg.debt_baseline[dc].get(2026) if dc else None, 'growth': raw.get('r_growth'),
                 'inflation_log': None if infl is None else math.log(1 + max(infl, -50) / 100), 'ca_gdp': raw.get('r_ca'),
                 'reserves_months': extra[cn]['reserves_months'], 'past_default_10y': extra[cn]['past_default_10y']}
        fitted = None
        if fitted_ready and all(feats[f] is not None for f in FEATURES):
            z = coef['intercept'] + sum(coef[f] * feats[f] for f in FEATURES)
            fitted = 1 / (1 + math.exp(-z))
        blended = blend_pd(fitted, sc_pd, s['blend_weight_fitted'])
        m_pd = cds_implied_pd(mkt[cn]['cds_5y_bps'], s['cds_recovery'])
        gap, flag = benchmark_gap(blended, m_pd, s['gap_tolerance_logodds'])
        out[cn] = {'score_used': score, 'score_from': src, 'scorecard_pd': sc_pd, 'features': feats, 'fitted_pd': fitted,
                   'blended_pd': blended, 'pd_low': bands[cn]['pd_low'], 'pd_high': bands[cn]['pd_high'],
                   'market_pd': m_pd, 'gap_logodds': gap, 'flag': flag}
    return out


def pri_book(cfg, model, dtable=None, root=ROOT):
    dtable = dtable or default_table(cfg, model, root)
    return {p['policy_id']: price_policy(cfg, model, p, pd_override=dtable[p['country']]['blended_pd'])
            for p in _rows('pri_policies.csv', root) if p['country'] in dtable}


def bond_table(cfg, root=ROOT):
    V = cfg.settings['restructuring']['valuation_year']
    bonds = [b for b in _rows('bonds.csv', root) if b['country'] in cfg.countries]
    cred = {r['country']: r for r in _rows('creditor_map.csv', root)}
    out = {}
    for b in bonds:
        r = bond_recovery(b, b, V)
        months = deal_months(cfg, cred.get(b['country'], {}), [x for x in bonds if x['country'] == b['country']])
        r.update(holdout_risk=holdout_risk(b['cac']), deal_months=months,
                 recovery_at_default=recovery_at_default(r['recovery_per_100'], months, b['exit_yield']),
                 market_recovery=b['price'])
        out[b['bond_id']] = r
    return out
