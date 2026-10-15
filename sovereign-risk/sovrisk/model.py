"""Run the full model: base, best and worst cases, scenario summary and sensitivity."""
from .inputs import N, base_case, scenario_case
from .scoring import combine, indicator_scores, pillar_scores, pillar_weights


def run_case(cfg, country, case):
    ind, raw = base_case(cfg, country) if case == 'base' else scenario_case(cfg, country, case)
    calc = indicator_scores(cfg, ind, raw)
    res = pillar_scores(cfg, calc, raw, ind)
    res.update(indicators=calc, inputs=ind, raw=raw)
    return res


def sensitivity(cfg, base_res):
    """Country-score points per 25-point move in each included indicator (linear, Base case)."""
    blend = cfg.settings['blend']
    pw = pillar_weights(cfg, base_res['small_state'])
    calc = base_res['indicators']
    wsum = {p: sum(r['weight'] for r in calc.values() if r['pillar'] == p and r['included']) for p in range(1, 8)}
    return {iid: (pw[r['pillar']] * blend * r['weight'] / wsum[r['pillar']] * 25 if r['included'] else None)
            for iid, r in calc.items()}


def run_model(cfg):
    out = {}
    for cn in cfg.countries:
        res = {case: run_case(cfg, cn, case) for case in ('base', 'best', 'worst')}
        b = res['base']
        pre = {p: N(b['raw'].get(f'pre{p}')) for p in range(1, 8)}
        res['model_on_preliminary'] = combine(cfg, pre, b['small_state'])
        res['sensitivity'] = sensitivity(cfg, b)
        contrib = {}
        for case in ('best', 'worst'):
            pw = pillar_weights(cfg, res[case]['small_state'])
            contrib[case] = {p: (None if None in (res[case]['pillars'][p]['final'], b['pillars'][p]['final'], b['score'])
                                 else pw[p] * (res[case]['pillars'][p]['final'] - b['pillars'][p]['final'])) for p in range(1, 8)}
        res['contribution_vs_base'] = contrib
        out[cn] = res
    return out
