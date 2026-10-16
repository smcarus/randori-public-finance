"""RPF-06 spillover network: how a shock abroad hits each country's GDP, by channel and by round.

    python -m sovrisk.spillover --list                    # scenarios in rulebook/spillover.yaml
    python -m sovrisk.spillover --scenario us_recession   # table of GDP impacts from the exposure files
    python -m sovrisk.spillover --scenario oil_down_30 --rounds

Five channels: trade (exports to the shocked partner), commodities (net exports of the commodity whose price moves),
banks (claims of banks from the shocked lending country), rates (US dollar debt refinanced at higher rates) and
remittances (inflows from the shocked sending country). First round: shock x exposure x the channel's elasticities.
Second round: the first-round GDP losses travel through the trade matrix, damped, one round at a time, until they die
out. Exposures are long-format CSVs in data/ (country, partner, value_pct_gdp, year, source), built by
sovrisk/spillover_data.py from IMF, BIS, UN Comtrade and World Bank data. Elasticities, damping and scenarios live in
rulebook/spillover.yaml. Results are % changes in GDP. Version 0.1 is untested and has no real data yet.
"""
import argparse
from pathlib import Path

import yaml

from .config import ROOT, read_csv

MODEL = 'RPF-06 v0.1'
CHANNELS = ('trade', 'commodities', 'banks', 'rates', 'remittances')


def load_rulebook(root=ROOT):
    return yaml.safe_load(open(Path(root) / 'rulebook' / 'spillover.yaml'))


def load_exposures(root=ROOT, rb=None):
    """{channel: rows} from data/spill_*.csv, plus the list of files that are missing."""
    rb = rb or load_rulebook(root)
    out, missing = {}, []
    for ch in CHANNELS:
        path = Path(root) / 'data' / rb['channels'][ch]['file']
        if path.exists():
            out[ch] = read_csv(path)
        else:
            out[ch], missing = [], missing + [str(path)]
    return out, missing


def latest(rows):
    """{(country, partner): value} keeping the latest year for each pair."""
    best = {}
    for r in rows:
        k, y = (str(r['country']), str(r['partner'])), r.get('year') or 0
        if r.get('value_pct_gdp') in (None, ''):
            continue
        if k not in best or y >= best[k][0]:
            best[k] = (y, float(r['value_pct_gdp']))
    return {k: v for k, (_, v) in best.items()}


def get_scenario(rb, scenario):
    if isinstance(scenario, dict):
        return scenario
    if scenario not in rb['scenarios']:
        raise KeyError(f"unknown scenario {scenario!r}; choose from {', '.join(rb['scenarios'])}")
    return rb['scenarios'][scenario]


def trade_matrix(rb, exposures):
    """{country: {partner: sensitivity}}: % change in country's GDP per 1% change in partner's GDP."""
    t = rb['channels']['trade']
    k = t['income_elasticity'] * t['value_added_share'] / 100
    a = {}
    for (c, p), v in latest(exposures.get('trade', [])).items():
        a.setdefault(c, {})[p] = v * k
    return a


def first_round(rb, scenario, exposures):
    """{country: {channel: GDP impact %}} from the direct hit of the shock."""
    ch, s = rb['channels'], get_scenario(rb, scenario)
    gdp, price, rate = s.get('gdp') or {}, s.get('price') or {}, s.get('rate') or {}
    out = {}

    def add(c, channel, x):
        out.setdefault(c, {k: 0.0 for k in CHANNELS})[channel] += x

    t, b, m = ch['trade'], ch['banks'], ch['remittances']
    for (c, p), v in latest(exposures.get('trade', [])).items():
        if p in gdp:
            add(c, 'trade', v / 100 * gdp[p] * t['income_elasticity'] * t['value_added_share'])
    for (c, p), v in latest(exposures.get('banks', [])).items():
        if p in gdp:
            add(c, 'banks', v / 100 * gdp[p] * b['retrenchment_elasticity'] * b['gdp_per_credit'])
    for (c, p), v in latest(exposures.get('remittances', [])).items():
        if p in gdp:
            add(c, 'remittances', v / 100 * gdp[p] * m['host_gdp_elasticity'] * m['consumption_pass_through'])
    for (c, p), v in latest(exposures.get('commodities', [])).items():
        if p in price:   # v is NET exports: an exporter (v > 0) loses on a price fall, an importer (v < 0) gains
            add(c, 'commodities', v / 100 * price[p] * ch['commodities']['income_pass_through'])
    if 'USD' in rate:
        r, vals = ch['rates'], latest(exposures.get('rates', []))
        for c in {c for c, _ in vals}:
            share, gfn = vals.get((c, 'usd_debt_share')), vals.get((c, 'gfn'))
            if share is None or gfn is None:
                continue
            cost = rate['USD'] / 100 * r['yield_pass_through'] * share / 100 * gfn / 100   # extra interest, % GDP
            add(c, 'rates', -cost * r['fiscal_multiplier'])
    return out


def propagate(rb, a, y1):
    """Damped rounds y(k+1) = d * A y(k) through the trade matrix. Needs every row of d*A to sum below 1 in absolute
    value, so each round is smaller than the last. Returns the list of rounds, round 1 first."""
    sr = rb['second_round']
    d = sr['damping']
    norm = max([d * sum(abs(x) for x in row.values()) for row in a.values()] or [0])
    if norm >= 1:
        raise ValueError(f'damped trade matrix has row sum {norm:.3f} >= 1: the rounds would not shrink. '
                         'Raise damping (rulebook second_round) or check the trade exposures.')
    rounds, y = [dict(y1)], dict(y1)
    for _ in range(sr['max_rounds']):
        y = {c: d * sum(s * y.get(p, 0.0) for p, s in row.items()) for c, row in a.items()}
        y = {c: v for c, v in y.items() if v != 0}
        if not y or max(abs(v) for v in y.values()) < sr['tolerance']:
            break
        rounds.append(y)
    return rounds


def run(scenario, exposures, rb=None):
    """GDP impact (%) per country for a scenario, split by channel and by round.

    Second-round effects are traced back to the channel that started them (the model is linear, so they add up).
    Returns {'countries': {c: {'first': {ch: x}, 'second': {ch: x}, 'by_channel': {ch: x}, 'total': x}},
             'rounds': [{c: total in that round}], 'n_rounds': n, 'model': MODEL}."""
    rb = rb or load_rulebook()
    a = trade_matrix(rb, exposures)
    y1 = first_round(rb, scenario, exposures)
    per = {ch: propagate(rb, a, {c: v[ch] for c, v in y1.items() if v[ch]}) for ch in CHANNELS}
    n = max(len(r) for r in per.values())
    rounds = [{} for _ in range(n)]
    for ch, rs in per.items():
        for i, r in enumerate(rs):
            for c, v in r.items():
                rounds[i][c] = rounds[i].get(c, 0.0) + v
    countries = {}
    for c in sorted(set(y1) | {c for r in rounds for c in r}):
        first = {ch: y1.get(c, {}).get(ch, 0.0) for ch in CHANNELS}
        second = {ch: sum(r.get(c, 0.0) for r in per[ch][1:]) for ch in CHANNELS}
        countries[c] = {'first': first, 'second': second,
                        'by_channel': {ch: first[ch] + second[ch] for ch in CHANNELS},
                        'total': sum(first.values()) + sum(second.values())}
    return {'model': MODEL, 'scenario': get_scenario(rb, scenario), 'countries': countries, 'rounds': rounds,
            'n_rounds': n}


def main(argv=None):
    ap = argparse.ArgumentParser(description=f'{MODEL} spillover network (untested, needs real exposure data).')
    ap.add_argument('--root', default=None)
    ap.add_argument('--scenario', default='us_recession')
    ap.add_argument('--list', action='store_true', help='list the scenarios')
    ap.add_argument('--rounds', action='store_true', help='also print the total for each round')
    a = ap.parse_args(argv)
    root = Path(a.root) if a.root else ROOT
    rb = load_rulebook(root)
    if a.list:
        for k, s in rb['scenarios'].items():
            print(f"{k:18s} {s['label']}")
        return
    ex, missing = load_exposures(root, rb)
    print(f'{MODEL}, untested. GDP impact in %. Not a forecast.')
    if missing:
        print('Missing exposure files (those channels count as zero; build them with sovrisk/spillover_data.py):')
        for m in missing:
            print(f'    {m}')
    if not any(ex.values()):
        print('No exposure data at all, so there is nothing to compute.')
        return
    r = run(a.scenario, ex, rb)
    print(f"Scenario: {r['scenario'].get('label', a.scenario)}. Second round converged in {r['n_rounds'] - 1} rounds.")
    hdr = ''.join(f'{ch[:8]:>9s}' for ch in CHANNELS)
    print(f"{'country':8s}{hdr}{'1st':>9s}{'2nd':>9s}{'total':>9s}")
    for c, x in sorted(r['countries'].items(), key=lambda kv: kv[1]['total']):
        row = ''.join(f"{x['by_channel'][ch]:9.3f}" for ch in CHANNELS)
        print(f"{c:8s}{row}{sum(x['first'].values()):9.3f}{sum(x['second'].values()):9.3f}{x['total']:9.3f}")
    if a.rounds:
        for i, rd in enumerate(r['rounds'], 1):
            print(f"round {i}: " + ', '.join(f'{c} {v:.3g}' for c, v in sorted(rd.items())))


if __name__ == '__main__':
    main()
