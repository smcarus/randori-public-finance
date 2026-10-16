"""Stability levers: switch on insurance, credit, banking, revenue and other measures and re-run the model exactly.

    python -m sovrisk.levers --country Belize --on cat_insurance,revenue
    python -m sovrisk.levers --list

Levers and their effects are in rulebook/levers.yaml (ILLUSTRATIVE magnitudes). Indicator effects move the
indicator toward lower risk before scoring, so they flow through pillars, triggers, floors, the country score,
default PD and the PRI hazards. lgd_mult, pri_net_share, bond_guarantee and bond_cac act outside the scorecard.
"""
import argparse
import math

import yaml

from . import load_config, run_model
from .backtest import pd_from_score
from .config import ROOT
from .decisions import _rows, default_table
from .inputs import base_case
from .pri import price_policy
from .restructuring import bond_recovery, deal_months, holdout_risk, recovery_at_default
from .scoring import indicator_scores, pillar_scores


def load_levers(cfg, root=ROOT):
    L = yaml.safe_load(open(root / 'rulebook' / 'levers.yaml'))
    ids = {i['id'] for i in cfg.indicators}
    for lv in L['levers']:
        for e in lv['effects']:
            if 'ind' in e and e['ind'] not in ids:
                raise ValueError(f"lever {lv['id']}: unknown indicator {e['ind']}")
    return L


def _improve(idef, v, e):
    """Move value v of indicator idef toward lower risk."""
    if v is None:
        return None
    if idef['type'] == 'rubric':
        return max(0.0, v - e.get('improve', 0))
    t = idef['thresholds']
    k = 1 if t[4] > t[0] else -1  # +1: higher value is riskier
    if 'improve' in e:
        return v - k * e['improve']
    return v - k * abs(v) * e['improve_pct'] / 100


def effects(levers, active):
    return [e for lv in levers['levers'] if lv['id'] in active for e in lv['effects']]


def apply_indicators(cfg, ind, levers, active):
    idefs = {i['id']: i for i in cfg.indicators}
    out = dict(ind)
    for e in effects(levers, active):
        if 'ind' in e and idefs[e['ind']]['type'] != 'twosided':
            out[e['ind']] = _improve(idefs[e['ind']], out.get(e['ind']), e)
    return out


def run_with_levers(cfg, country, active, levers=None, model=None, root=ROOT):
    """Exact re-run of one country with the given levers on (base case). Returns score, PD, loss, PRI and bond results."""
    levers = levers or load_levers(cfg, root)
    model = model or run_model(cfg)
    active = set(active)
    ind, raw = base_case(cfg, country)
    ind2 = apply_indicators(cfg, ind, levers, active)
    calc = indicator_scores(cfg, ind2, raw)
    res = pillar_scores(cfg, calc, raw, ind2)
    res.update(indicators=calc, inputs=ind2, raw=raw)
    m2 = dict(model)
    m2[country] = dict(model[country], base=res)
    dt = default_table(cfg, m2, root)[country]
    eff = effects(levers, active)
    lgd_mult = math.prod(e['lgd_mult'] for e in eff if 'lgd_mult' in e)
    net_share = math.prod(e['pri_net_share'] for e in eff if 'pri_net_share' in e)
    g = max([e['bond_guarantee'] for e in eff if 'bond_guarantee' in e], default=0.0)
    cac = next((e['bond_cac'] for e in eff if 'bond_cac' in e), None)
    mp = cfg.mc_portfolio[country]
    pd_ = dt['blended_pd']
    pri = {}
    for p in _rows('pri_policies.csv', root):
        if p['country'] == country:
            r = price_policy(cfg, m2, p, pd_override=pd_)
            pri[p['policy_id']] = {'premium_bps': 1e4 * r['total']['premium_rate'], 'el': r['total']['el_total'],
                                   'net_el': r['total']['el_total'] * net_share,
                                   'claim_prob_term': r['total']['any_claim_prob_term']}
    V = cfg.settings['restructuring']['valuation_year']
    bonds = [dict(b, cac=cac or b['cac']) for b in _rows('bonds.csv', root) if b['country'] == country]
    cred = {r['country']: r for r in _rows('creditor_map.csv', root)}.get(country, {})
    months = deal_months(cfg, cred, bonds) if bonds else None
    bt = {}
    for b in bonds:
        rec = bond_recovery(b, b, V)['recovery_per_100']
        if g:
            rec = (1 - g) * rec + g * bond_recovery(b, dict(b, exit_yield=levers['guarantor_yield']), V)['recovery_per_100']
        bt[b['bond_id']] = {'recovery': rec, 'deal_months': months, 'holdout_risk': holdout_risk(b['cac']), 'exit_yield': b['exit_yield'],
                            'recovery_at_default': recovery_at_default(rec, months, b['exit_yield'])}
    score = res['score'] if res['score'] else cfg.preliminary[country]
    return {'score': score, 'from_model': bool(res['score']), 'grade': None if score is None else min(10, int(score // 10) + 1),
            'pillars': [res['pillars'][p]['final'] for p in range(1, 8)], 'small_state': res['small_state'],
            'pd': pd_, 'lgd_mult': lgd_mult, 'expected_loss': pd_ * mp['lgd_mean'] * lgd_mult * mp['exposure'],
            'pri': pri, 'bonds': bt}


def lever_table(cfg, levers=None, model=None, root=ROOT):
    """For every country: the base run and one run per single lever (what the dashboard combines)."""
    levers = levers or load_levers(cfg, root)
    model = model or run_model(cfg)
    return {cn: {'base': run_with_levers(cfg, cn, [], levers, model, root),
                 'single': {lv['id']: run_with_levers(cfg, cn, [lv['id']], levers, model, root) for lv in levers['levers']}}
            for cn in cfg.countries}


def main(argv=None):
    ap = argparse.ArgumentParser(description='Re-run one country with stability levers switched on.')
    ap.add_argument('--country', help='required unless --list')
    ap.add_argument('--on', default='', help='comma-separated lever ids; --list shows them')
    ap.add_argument('--list', action='store_true')
    a = ap.parse_args(argv)
    cfg = load_config()
    L = load_levers(cfg)
    if a.list:
        for lv in L['levers']:
            print(f"{lv['id']:20s} {lv['category']:28s} {lv['label']}")
        return
    if not a.country:
        ap.error('--country is required unless --list is given')
    on = [x for x in a.on.split(',') if x]
    b, w = run_with_levers(cfg, a.country, []), run_with_levers(cfg, a.country, on)
    print(f"{a.country}: score {b['score']:.1f} -> {w['score']:.1f}; PD {b['pd']:.2%} -> {w['pd']:.2%}; "
          f"expected loss {b['expected_loss']:.3f} -> {w['expected_loss']:.3f} (US$m)")


if __name__ == '__main__':
    main()
