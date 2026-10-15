"""Sovereign bond restructuring: cash flows, NPV haircut (Sturzenegger-Zettelmeyer), recovery and deal duration."""


def schedule(face, coupon, maturity, amort_start, start_year):
    """Annual end-of-year cash flows from start_year+1 to maturity. Equal principal from amort_start (bullet if
    amort_start is None or >= maturity). Returns list of (year, cash_flow)."""
    if amort_start is None or amort_start >= maturity:
        amort_start = maturity
    first = max(amort_start, start_year + 1)
    n = maturity - first + 1
    out, bal = [], face
    for y in range(start_year + 1, maturity + 1):
        prin = face / n if y >= first else 0.0
        out.append((y, bal * coupon + prin))
        bal -= prin
    return out


def pv(flows, y, start_year):
    return sum(cf / (1 + y) ** (yr - start_year) for yr, cf in flows)


def bond_recovery(bond, terms, valuation_year):
    """bond: face, coupon, maturity, amort_start. terms: face_haircut, new_coupon, new_maturity, grace_years, exit_yield."""
    old = schedule(bond['face'], bond['coupon'], bond['maturity'], bond.get('amort_start'), valuation_year)
    new_face = bond['face'] * (1 - terms['face_haircut'])
    new = schedule(new_face, terms['new_coupon'], terms['new_maturity'], valuation_year + terms['grace_years'] + 1, valuation_year)
    y = terms['exit_yield']
    pv_old, pv_new = pv(old, y, valuation_year), pv(new, y, valuation_year)
    return {'pv_old': pv_old, 'pv_new': pv_new, 'npv_haircut_sz': 1 - pv_new / pv_old,
            'market_haircut_ct': 1 - pv_new / bond['face'], 'recovery_per_100': 100 * pv_new / bond['face'],
            'old_flows': old, 'new_flows': new}


def holdout_risk(cac):
    return {'None': 'High', 'Series-by-series': 'Medium', 'Two-limb': 'Low', 'Single-limb': 'Low'}.get(cac, 'Unknown')


def deal_months(cfg, creditors, bonds):
    """Expected months from default to deal. creditors: dict of shares and flags for one country; bonds: its bonds."""
    s = cfg.settings['restructuring']
    m = s['base_months']
    if (creditors.get('china') or 0) >= s['china_share_threshold']:
        m += s['china_months']
    cacs = {b.get('cac') for b in bonds}
    if 'None' in cacs:
        m += s['no_cac_months']
    elif 'Series-by-series' in cacs:
        m += s['series_cac_months']
    if len({b.get('governing_law') for b in bonds if b.get('governing_law')}) > 1:
        m += s['multi_law_months']
    if creditors.get('imf_program') == 1:
        m += s['imf_program_months']
    if creditors.get('common_framework') == 1:
        m += s['common_framework_months']
    return m


def recovery_at_default(rec_per_100, months, exit_yield):
    """Value at the default date of the restructured claim, discounting for the time to a deal."""
    return rec_per_100 / (1 + exit_yield) ** (months / 12)
