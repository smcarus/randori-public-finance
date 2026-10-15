"""Political risk insurance: probability and loss for each peril over the policy term.

Hazard for each peril starts from the country's pillar scores (or the default PD for non-honoring),
then mean-reverts toward its level at a neutral score of 50 over the policy term. ILLUSTRATIVE parameters.
"""
import math

from .backtest import pd_from_score

PERILS = ['ci', 'expropriation', 'political_violence', 'breach', 'nhsfo']


def driver_score(model_case, drivers, fallback):
    fins = {p: model_case['pillars'][p]['final'] for p in range(1, 8)}
    if any(fins[p] is None for p in drivers):
        return fallback
    tot = sum(drivers.values())
    return sum(w * fins[int(p)] for p, w in drivers.items()) / tot


def hazards(cfg, model, country, sector='Other', obligor='Sovereign', location_mult=1.0, pd_override=None):
    """Year-1 hazard h0 and long-run hazard h_LR for each peril."""
    s = cfg.settings['pri']
    case = model[country][s['score_source'].lower()]
    fallback = case['score'] if case['score'] is not None else cfg.preliminary[country]
    out = {}
    for k in PERILS:
        P = s['perils'][k]
        if k == 'nhsfo':
            bt = cfg.settings['backtest']
            pd0 = pd_override if pd_override is not None else pd_from_score(fallback, bt['pd_a'], bt['pd_b'])
            f = s['obligor_factors'][obligor]
            h0, hlr = pd0 * f, pd_from_score(50, bt['pd_a'], bt['pd_b']) * f
        else:
            D = driver_score(case, {int(p): w for p, w in P['drivers'].items()}, fallback)
            m = (s['sector_multipliers'][sector] if P['sector_multiplier'] else 1.0) * (location_mult if k == 'political_violence' else 1.0)
            h0 = P['base_rate'] * math.exp(P['beta'] * (D - 50) / 10) * m
            hlr = P['base_rate'] * m
        out[k] = (min(s['hazard_cap'], h0), min(s['hazard_cap'], hlr))
    return out


def price_policy(cfg, model, policy, pd_override=None):
    """policy: dict with country, sector, obligor, term_years, limit, insured_share, deductible, location_mult and
    cover flags ci/expropriation/political_violence/breach/nhsfo (1/0). Returns per-peril and total results."""
    s = cfg.settings['pri']
    hz = hazards(cfg, model, policy['country'], policy.get('sector') or 'Other', policy.get('obligor') or 'Sovereign',
                 policy.get('location_mult') or 1.0, pd_override)
    T, L = int(policy['term_years']), policy['limit']
    phi, r = s['mean_reversion'], s['discount_rate']
    res, tot = {}, {'el_total': 0.0, 'el_pv': 0.0, 'ul': 0.0, 'premium_rate': 0.0}
    for k in PERILS:
        if not policy.get(k):
            continue
        P = s['perils'][k]
        h0, hlr = hz[k]
        net = max(0.0, P['severity'] - (policy.get('deductible') or 0)) * (1 - P['recovery']) * (policy.get('insured_share') or 1)
        S, cum_el, pv_el, cs = 1.0, 0.0, 0.0, []
        for t in range(1, T + 1):
            c = (hlr + (h0 - hlr) * phi ** (t - 1)) * P['persistence']
            q = S * c
            S *= (1 - c)
            cs.append(c)
            cum_el += q * net * L
            pv_el += q * net * L / (1 + r) ** t
        cbar = sum(cs) / T
        ul = L * net * math.sqrt(cbar * (1 - cbar)) * s['ul_multiplier']
        prem = (cum_el / T + s['cost_of_capital'] * ul) / (1 - s['expense_ratio']) / L
        res[k] = {'h0': h0, 'h_long_run': hlr, 'claim_prob_year1': cs[0], 'claim_prob_term': 1 - S,
                  'net_severity': net, 'el_total': cum_el, 'el_pv': pv_el, 'ul': ul, 'premium_rate': prem}
        for key in tot:
            tot[key] += res[k][key]
    surv = 1.0
    for k in res:
        surv *= 1 - res[k]['claim_prob_term']
    tot['any_claim_prob_term'] = 1 - surv if res else 0.0
    return {'perils': res, 'total': tot}
