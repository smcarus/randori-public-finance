"""Indicator scores, pillar scores and the country score (port of Model Calc and Model Pillars)."""
from .inputs import N


def _interp(x, t):
    """Five threshold points -> 0/25/50/75/100, straight-line between; thresholds may run up or down."""
    k = 1 if t[4] > t[0] else -1
    x, t = k * x, [k * v for v in t]
    if x <= t[0]:
        return 0.0
    if x >= t[4]:
        return 100.0
    for j in range(4):
        if x <= t[j + 1]:
            return 25 * j + 25 * (x - t[j]) / (t[j + 1] - t[j])
    return 100.0


def _twosided(v, lo, hi):
    """Real policy rate: 0 inside [0, hi[0]]; negative side scored on lo, positive side on hi."""
    if 0 <= v <= hi[0]:
        return 0.0
    if v < 0:
        if v <= lo[4]:
            return 100.0
        if v >= lo[1]:
            return 25 * (v - lo[0]) / (lo[1] - lo[0])
        if v >= lo[2]:
            return 25 + 25 * (v - lo[1]) / (lo[2] - lo[1])
        if v >= lo[3]:
            return 50 + 25 * (v - lo[2]) / (lo[3] - lo[2])
        return 75 + 25 * (v - lo[3]) / (lo[4] - lo[3])
    if v >= hi[4]:
        return 100.0
    if v <= hi[1]:
        return 25 * (v - hi[0]) / (hi[1] - hi[0])
    if v <= hi[2]:
        return 25 + 25 * (v - hi[1]) / (hi[2] - hi[1])
    if v <= hi[3]:
        return 50 + 25 * (v - hi[2]) / (hi[3] - hi[2])
    return 75 + 25 * (v - hi[3]) / (hi[4] - hi[3])


def indicator_scores(cfg, ind, raw):
    """Return {id: dict(value, weight, score, included, core)} for one country and case."""
    S = cfg.settings
    wmap = {i['id']: i['weight'] for i in cfg.indicators}
    out = {}
    for i in cfg.indicators:
        iid, v = i['id'], ind.get(i['id'])
        if iid == 'p7_protect':
            w = i['weight'] + (wmap['p7_basis'] if ind.get('p7_basis') is None else 0)
        elif iid == 'p7_basis':
            w = 0 if v is None else i['weight']
        else:
            w = i['weight']
        if v is None:
            sc = None
        elif i['type'] == 'rubric':
            sc = v
        elif i['type'] == 'twosided':
            sc = _twosided(v, i['thresholds'], i['high_thresholds'])
        else:
            sc = _interp(v, i['thresholds'])
        if iid == 'p7_b2b' and sc is not None:
            sc = max(sc, S['b2bfloor'] if raw.get('r_recovering') == 1 else 0)
        inc = sc is not None
        out[iid] = {'pillar': i['pillar'], 'value': v, 'weight': w, 'score': sc, 'included': inc,
                    'core': inc and i['weight'] * 100 >= S['coremin']}
    return out


def pillar_scores(cfg, calc, raw, ind):
    """Return per-pillar components, small-state flag, country score and grade."""
    S = cfg.settings
    pillars = {}
    for p in range(1, 8):
        rows = [r for r in calc.values() if r['pillar'] == p]
        wsum = sum(r['weight'] for r in rows if r['included'])
        a = sum(r['weight'] * r['score'] for r in rows if r['included']) / wsum if wsum else None
        m = None if a is None else max([r['score'] for r in rows if r['core']], default=0)
        rawp = None if a is None else S['blend'] * a + (1 - S['blend']) * m
        pillars[p] = {'wtd_avg': a, 'worst_core': m, 'raw': rawp}
    p1raw = pillars[1]['raw']
    for p in range(1, 8):
        if p == 3:
            if pillars[3]['wtd_avg'] is None:
                tr = 0
            else:
                boom = N(raw.get('t_boom')) >= S['boomprice']
                sq = N(p1raw) >= S['squeeze']
                t1 = 10 if (boom and sq) else (0 if S['boomboth'] == 1 else (5 if (boom or sq) else 0))
                c = N(raw.get('t_contagion'))
                tr = min(S['cap3'], t1 + (10 if c >= 2 else 5 if c == 1 else 0))
        elif p == 4:
            shock = N(raw.get('t_price')) >= 2 or N(raw.get('t_cut')) == 1
            street = N(calc['p4_street']['score'])
            tr = max(-S['cap4'], min(S['cap4'], (10 if street >= 50 else 5) * shock + N(raw.get('t_term'))))
        elif p == 7:
            tr = min(S['cap7'], (5 if N(raw.get('t_season')) == 1 and N(raw.get('t_inseason')) == 1 else 0)
                     + (5 if N(raw.get('t_enso')) == 1 else 0))
        else:
            tr = 0
        adj = max(-S['adjlim'], min(S['adjlim'], N(raw.get(f'adj{p}'))))
        fl = N(raw.get(f'floor{p}'))
        r_ = pillars[p]['raw']
        pillars[p].update(triggers=tr, adjust=adj, floor=fl,
                          final=None if r_ is None else min(100, max(fl, r_ + tr + adj)))
    pop = raw.get('r_pop')
    small = 1 if ((pop is not None and pop < S['popthr']) or N(ind.get('p7_pml')) >= S['pmlthr']) else 0
    fin = {p: pillars[p]['final'] for p in range(1, 8)}
    score = None
    if all(v is not None for v in fin.values()):
        score = combine(cfg, fin, small)
    grade = None if score is None else min(10, int(score // 10) + 1)
    return {'pillars': pillars, 'small_state': small, 'score': score, 'grade': grade}


def pillar_weights(cfg, small):
    W, sw = cfg.settings['pillar_weights'], cfg.settings['smallw']
    if not small:
        return dict(W)
    return {p: (sw if p == 7 else W[p] * (1 - sw) / (1 - W[7])) for p in range(1, 8)}


def combine(cfg, fin, small):
    """Country score from final pillar scores (small states: climate weight raised, others scaled down)."""
    W, sw = cfg.settings['pillar_weights'], cfg.settings['smallw']
    std = sum(W[p] * fin[p] for p in range(1, 8))
    if small:
        return sw * fin[7] + (1 - sw) / (1 - W[7]) * (std - W[7] * fin[7])
    return std
