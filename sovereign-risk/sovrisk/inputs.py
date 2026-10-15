"""Indicator values: base case (Model Inputs) and scenario cases (Best/Worst Inputs)."""
from .debt import stress_paths

DERIVED = ('p1_debt', 'p1_ddebt', 'p1_gfn', 'p1_pbgap', 'p1_default', 'p2_ara', 'p2_ca', 'p5_infl', 'p5_growth')
RAW_IDS = ['r_debt26', 'r_debt27', 'r_debt31', 'r_gfn', 'r_pb', 'r_r', 'r_g', 'r_default', 'r_ara', 'r_netres', 'r_ca',
           'r_expgdp', 'r_shock', 'r_floater', 'r_infl', 'r_growth', 'r_pop', 'r_recovering', 'debt_country',
           't_boom', 't_contagion', 't_price', 't_cut', 't_term', 't_season', 't_inseason', 't_enso'] + \
          [f'{k}{p}' for k in ('adj', 'floor', 'pre') for p in range(1, 8)]


def N(x):
    """Excel N(): numbers pass, blanks and text become 0."""
    return x if isinstance(x, (int, float)) and not isinstance(x, bool) else (int(x) if isinstance(x, bool) else 0)


def derive(raw, ind, cfg, s, dshift=0.0):
    """Stress-derived indicators from raw inputs. `ind` supplies p5_gdppc. `dshift` adds to both debt paths."""
    S = cfg.settings
    dc = raw.get('debt_country')
    paths = stress_paths(cfg.debt_baseline[dc], S['debt_scenarios']) if dc else None
    out = {}
    v = raw.get
    if paths is None:
        out['p1_debt'] = out['p1_ddebt'] = None
    else:
        b, c = paths['baseline'], paths['combined']
        if c is None:   # no projections: baseline only (fixes a workbook offset bug, see README)
            d27 = v('r_debt27') if v('r_debt27') is not None else (None if b[2027] is None else b[2027] + dshift)
            out['p1_debt'] = d27
            out['p1_ddebt'] = None
        else:
            d27 = v('r_debt27') if v('r_debt27') is not None else N(b[2027]) + dshift
            out['p1_debt'] = max(d27, c[2027] + dshift)
            d31 = v('r_debt31') if v('r_debt31') is not None else N(b[2031]) + dshift
            d26 = v('r_debt26') if v('r_debt26') is not None else N(b[2026])
            out['p1_ddebt'] = max(d31 - d26, c[2031] + dshift - c[2026])
    out['p1_gfn'] = None if v('r_gfn') is None else v('r_gfn') + S['gfnadd']
    if None in (v('r_pb'), v('r_r'), v('r_g')) or paths is None:
        out['p1_pbgap'] = None
    else:
        d26 = v('r_debt26') if v('r_debt26') is not None else N(paths['baseline'][2026])
        pb, r, g = v('r_pb'), v('r_r'), v('r_g')
        g2 = g - S['gshock']
        out['p1_pbgap'] = min(pb - d26 * (r - g) / 100 / (1 + g / 100),
                              (pb - S['pbshock']) - d26 * (r - g2) / 100 / (1 + g2 / 100))
    d = v('r_default')
    out['p1_default'] = None if d is None else (0 if d <= 0 else 50 if d <= 1 else 75 if d <= 2 else 100)
    if v('r_ara') is None or v('r_netres') is None:
        out['p2_ara'] = None
    elif N(v('r_floater')) == 0 or S['resfloat'] == 1:
        loss = N(v('r_shock')) * N(v('r_expgdp')) / 100 * N(ind.get('p5_gdppc')) * N(v('r_pop')) / 1000
        out['p2_ara'] = v('r_ara') * max(v('r_netres') - loss, 0) / v('r_netres')
    else:
        out['p2_ara'] = v('r_ara')
    out['p2_ca'] = None if v('r_ca') is None else v('r_ca') - N(v('r_shock')) * N(v('r_expgdp'))
    out['p5_infl'] = None if v('r_infl') is None else v('r_infl') + S['passthru'] * S['dep'] * N(v('r_floater'))
    out['p5_growth'] = None if v('r_growth') is None else v('r_growth') - S['gshock']
    return out


def base_case(cfg, country):
    """Return (indicators, raw) for the base case of one country."""
    raw = dict(cfg.inputs[country])
    ind = {i['id']: raw.get(i['id']) for i in cfg.indicators}
    ind.update(derive(raw, ind, cfg, 0))
    return ind, raw


def _shift(cfg, country, did, scen):
    """Additive shift: country cell, else default, else 0."""
    v = cfg.overrides.get((country, did, scen))
    if v is not None:
        return v
    d = cfg.driver_defaults[did][scen]
    return N(d)


def _set(cfg, country, did, scen, base):
    v = cfg.overrides.get((country, did, scen))
    if v is not None:
        return v
    d = cfg.driver_defaults[did][scen]
    return d if d is not None else base


def scenario_case(cfg, country, scen):
    """Return (indicators, raw) for 'best' or 'worst'."""
    if not hasattr(cfg, 'driver_defaults'):
        cfg.driver_defaults = {d['id']: {'best': d['best_default'], 'worst': d['worst_default']} for d in cfg.drivers}
    b = cfg.inputs[country]
    sh = lambda did: _shift(cfg, country, did, scen)
    raw = dict(b)
    add = lambda rid, did: None if b.get(rid) is None else b[rid] + sh(did)
    for rid, did in (('r_debt27', 'd_debt'), ('r_debt31', 'd_debt'), ('r_gfn', 'd_gfn'), ('r_pb', 'd_pb'), ('r_r', 'd_rate'),
                     ('r_g', 'd_ngdp'), ('r_ca', 'd_ca'), ('r_growth', 'd_growth'), ('t_boom', 'd_boom')):
        raw[rid] = add(rid, did)
    for rid in ('r_ara', 'r_netres'):
        raw[rid] = None if b.get(rid) is None else b[rid] * (1 + sh('d_res') / 100)
    raw['r_infl'] = None if b.get('r_infl') is None else b['r_infl'] + sh('d_infl') + cfg.settings['passthru'] * sh('d_dep') * N(b.get('r_floater'))
    raw['r_shock'] = _set(cfg, country, 'd_shock', scen, b.get('r_shock'))
    for rid, did in (('t_contagion', 'o_contagion'), ('t_price', 'o_price'), ('t_cut', 'o_cut'), ('t_term', 'o_term'),
                     ('t_season', 'o_season'), ('t_inseason', 'o_inseason'), ('t_enso', 'o_enso'), ('r_recovering', 'o_recovering')):
        raw[rid] = _set(cfg, country, did, scen, b.get(rid))
    for p in range(1, 8):
        raw[f'adj{p}'] = _set(cfg, country, f'o_adj{p}', scen, b.get(f'adj{p}'))
    base_ind = {i['id']: b.get(i['id']) for i in cfg.indicators}
    # p5_gdppc used inside p2_ara is the scenario's own indicator value
    gdppc = base_ind.get('p5_gdppc')
    if gdppc is not None:
        gdppc = gdppc + sh('i_p5_gdppc')
    der = derive(raw, {'p5_gdppc': gdppc}, cfg, scen, dshift=sh('d_debt'))
    ind = {}
    for i in cfg.indicators:
        iid = i['id']
        inner = der[iid] if iid in DERIVED else base_ind[iid]
        if inner is None:
            ind[iid] = None
            continue
        x = inner + sh(f'i_{iid}')
        ind[iid] = max(0, min(100, x)) if i['type'] == 'rubric' else x
    return ind, raw
