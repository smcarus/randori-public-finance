"""Signals sheet: the summary of the model's risk signals. Near-term (LOGIT), medium-term (fanchart and GFN
module indices averaged into a Low/Moderate/High signal), the mechanical triggers of the five stress tests
(compared with the user's activation choices) and the debt-stabilization and sustainability flags."""
from .stress import Table, ge, gt, le, lt, truth, xand, xeq, xmatch, xnot, xor
from .xl import average, calc, iserr, isnumber

SHEETS = ['Signals']

QUIRKS = [
    "K8 concatenates the stress-test labels of column P, which depend on the user's activation (G9:G13), not on "
    "the mechanical triggers (H9:H13).",
]

PROGRAM = 'Program, nonprecautionary'


def _if(cond, a, b):
    t = truth(cond)
    return t if iserr(t) else (a if t else b)


def _yesno(a, b):
    """IF(a=b,"No","Yes")."""
    return _if(xeq(a, b), 'No', 'Yes')


def compute(book, sheet='Signals'):
    S = book['Signals']
    C = book['Config']
    eng = book.name('Engagement')
    program = xeq(eng, PROGRAM)
    nmf = Table(book, 'NewMacrofwData')
    dates = book.hrow('NewMacrofwDates')
    last = xmatch(-1, dates)

    # Near-term: logit probability and signal
    S['H3'] = _if(program, False, True)
    S['G3'] = S['H3']
    S['I3'] = book['LOGIT']['J23']
    S['J3'] = S['I3']
    S['K3'] = _if(program, 'n.a.', book['LOGIT']['J24'])
    S['M3'] = _yesno(S['K3'], S['L3'])

    # Medium-term: fanchart and GFN indices, transformed and averaged
    S['I6'] = book['FAN']['I14']
    S['J6'] = calc(lambda a, b: a / b, S['I6'], C['AH23'])
    S['K6'] = book['FAN']['I15']
    S['I7'] = book['GFN']['K8']
    S['J7'] = calc(lambda a, b: a / b, S['I7'], C['CG8'])
    S['K7'] = book['GFN']['K9']
    S['J5'] = average([S['J6'], S['J7']])
    j, lo, hi = S['J5'], C['CX4'], C['CX5']
    S['K5'] = _if(lt(j, lo), 'Low', _if(gt(j, hi), 'High', _if(xand(ge(j, lo), le(j, hi)), 'Moderate', 'n.a.')))
    S['M5'] = _yesno(S['K5'], S['L5'])

    # Stress-test triggers
    lims = Table(book, 'STBnksLIMs')
    S['H9'] = xor(gt(nmf('FPMISPRCSRT', last), lims('LIM_FPMISPRCSRT', 4)),
                  gt(nmf('FSLTDSRT', last), lims('LIM_FSLTDSRT', 4)))
    ifs = book.name('IFScode')
    S['H10'] = isnumber(xmatch(ifs, _col(book, 'STCommCtrys')))
    S['H11'] = xand(xeq(book.name('Perimeter'), 'Central government'), xeq(book.name('CovExclSectors'), 'No'))
    lim = book.name('STERLim')
    S['H12'] = xand(gt(nmf('EREER_GAP', last), lim),
                    gt(nmf('EREER_GAP', xmatch(book.name('MTHorizon'), dates)), lim))
    S['H13'] = isnumber(xmatch(ifs, _col(book, 'STNatDisList')))
    labels = {9: 'Bank. Crisis ', 10: 'Comm. Prices ', 11: 'Cont. Liabty. ', 12: 'FX rate ', 13: 'Nat. Diast.'}
    for r, lab in labels.items():
        S.set(r, 14, xnot(xeq(S.get(r, 7), S.get(r, 8))))          # manual override of the trigger
        S.set(r, 16, _if(xeq(S.get(r, 7), True), lab, ''))
    parts = [S.get(r, 16) for r in labels]
    e = next((p for p in parts if iserr(p)), None)
    S['K8'] = e or ''.join('' if p is None else str(p) for p in parts)

    # Debt stabilization and sustainability
    S['H20'] = program
    S['G20'] = S['H20']
    S['H19'] = xnot(S['H20'])
    S['G19'] = S['H19']
    B = book['BaseDB']
    S['K19'] = _if(xand(gt(B['W152'], 0), gt(B['X152'], 0)), 'No', 'Yes')
    S['K20'] = ''
    S['M20'] = _yesno(S['K20'], S['L20'])
    S['G22'] = xand(*(xnot(S.get(r, 14)) for r in labels))


def _col(book, name):
    sh, c0, r0, c1, r1 = book.area(name)
    S = book[sh]
    return [S.get(r, c) for r in range(r0, r1 + 1) for c in range(c0, c1 + 1)]
