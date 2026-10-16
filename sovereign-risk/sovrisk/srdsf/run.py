"""End-to-end runner for the MAC SRDSF port: recompute every ported sheet of a book from its inputs.

Every module in this package that defines SHEETS and compute(book, sheet) is discovered at import time, so a new
sheet port joins the run as soon as it exists. The sheets read each other in cycles
(IdentFin <-> ResidFin <-> BaseDB, GFN <-> Triangles, Questions <-> Config <-> Macrofw), although the template has
no cell-level circular references. run() therefore computes the sheets in a dependency-friendly order and repeats
the sequence (Gauss-Seidel), skipping sheets whose inputs did not change except in the first and the confirming
pass, until a pass changes no formula value.

The two VBA buttons can be run after the formulas have settled, in the order the Start sheet lists them: the debt
fanchart (fan.simulate, seeded) and then the GFN `converge` macro (gfn.simulate); each is followed by a re-run of
the formulas, as Excel would recalculate after the macro writes its values.

    python -m sovrisk.srdsf.run --golden tests/golden/srdsf [--keep] [--fan] [--gfn] [-v]
"""
import argparse
import gzip
import importlib
import json
import math
import pkgutil
import time
from pathlib import Path

from .book import Book, close, split
from .xl import NA

# Sheets each sheet's formulas read (explicit Sheet! references and defined names), from the template's formula
# dump. Only the direction matters here; the counts are the number of references, used to break cycles.
DEPS = {
    'Questions': {'Config': 27, 'Macrofw': 8},
    'Macrofw': {'Config': 1, 'Questions': 465},
    'Config': {'Questions': 196, 'Macrofw': 60, 'GFN': 16, 'Signals': 2},
    'NewMacrofw': {'Questions': 156, 'Config': 133, 'Macrofw': 1509},
    'IdentFin': {'Questions': 947, 'Macrofw': 533, 'ResidFin': 30276},
    'ResidFin': {'Questions': 243, 'Macrofw': 216, 'IdentFin': 5329, 'BaseDB': 275},
    'BaseDB': {'Questions': 57, 'Macrofw': 924, 'NewMacrofw': 748, 'IdentFin': 6448, 'ResidFin': 6448},
    'LOGIT': {'Questions': 11, 'Config': 56, 'BaseDB': 66},
    'FAN': {'Questions': 65, 'BaseDB': 295, 'Config': 1, 'Macrofw': 339},
    'Triangles': {'Questions': 348, 'GFN': 1244, 'Config': 60},
    'GFN': {'BaseDB': 721, 'Questions': 1062, 'Macrofw': 339, 'Config': 1911, 'Triangles': 832,
            'IdentFin': 3136, 'ResidFin': 3136},
    'Signals': {'Questions': 8, 'LOGIT': 2, 'Config': 12, 'FAN': 2, 'GFN': 2, 'NewMacrofw': 8, 'BaseDB': 2},
    'STDesign': {'Questions': 18, 'BaseDB': 99, 'Signals': 10, 'NewMacrofw': 8},
    'STOps': {'Questions': 352, 'BaseDB': 650, 'STDesign': 654, 'IdentFin': 8976, 'ResidFin': 8976},
    'Charts': {'BaseDB': 668, 'Questions': 216, 'NewMacrofw': 38, 'Macrofw': 419, 'IdentFin': 480,
               'ResidFin': 432, 'GFN': 107, 'FAN': 101, 'STOps': 79, 'Signals': 23, 'Config': 15},
    'Output': {'Signals': 28, 'Questions': 235, 'Charts': 31, 'BaseDB': 302, 'LOGIT': 32, 'FAN': 16, 'GFN': 16,
               'Config': 6},
    'Start': {},
}

# Order used inside the big cycle, chosen by experiment (see NOTES); sheets not listed here (new ports) are placed
# after the last listed sheet they read.
ORDER = ['Questions', 'Macrofw', 'Config', 'NewMacrofw', 'ResidFin', 'IdentFin', 'BaseDB', 'LOGIT', 'FAN',
         'Triangles', 'GFN', 'Signals', 'STDesign', 'STOps', 'Charts', 'Output']

NOTES = [
    'There are no cell-level cycles, so every order settles; the order only changes how many passes it takes. '
    'From blank formula cells the template settles in 3 changing passes plus two that change nothing (a skipping pass, then a '
    'full confirming pass), 5 in all, with this ORDER '
    '(IdentFin before ResidFin, or BaseDB first, takes 4).',
    'Config reads GFN only in CJ41:CY41 (the converge check, GFNConvergeChk) and Signals only in two text '
    'cells, so Config runs early; the check is refreshed in the next pass.',
    'IdentFin, ResidFin and BaseDB read each other (IdentFin reads ResidFin, ResidFin reads IdentFin and BaseDB, '
    'BaseDB reads both): whichever runs first sees stale values, so all three change again in pass 2.',
    'GFN and Triangles read each other (GFN reads the Triangles costs, Triangles the GFN scenario); both change '
    'once more in pass 3. Without the converge macro the loop is acyclic at cell level: Triangles '
    'takes the scenario financing from Config!GFNConvergeOut, which only the macro writes.',
    'Charts reads its own TRANSPOSE spill ranges (SPILLS), which are filled after Charts.compute; the next pass '
    'catches Charts up.',
]

# Multi-cell array formulas (the only four in the workbook). The template stores just the anchor as a formula cell
# and the rest of the range as plain values, and the sheet ports compute only the anchor; run() fills the whole
# range after the sheet is computed, as Excel spills it: target cell (i, j) <- source cell (j, i), #N/A where the
# source is smaller than the target range (C364:C376), blank source cells -> 0.
SPILLS = [
    ('Charts', 'H318:M318', 'K358:K363'),
    ('Charts', 'H319:M319', 'L358:L363'),
    ('Charts', 'H320:M320', 'M358:M363'),
    ('Charts', 'C353:C376', 'C314:M314'),
]

_SKIP_MODULES = {'run', 'book', 'xl'}


def modules():
    """{sheet: module} for every module of the package that ports a sheet (has SHEETS and compute)."""
    import sovrisk.srdsf as pkg
    out = {}
    for m in pkgutil.iter_modules(pkg.__path__):
        if m.name in _SKIP_MODULES:
            continue
        mod = importlib.import_module(f'{pkg.__name__}.{m.name}')
        if not hasattr(mod, 'compute'):
            continue
        for sheet in getattr(mod, 'SHEETS', ()):
            out[sheet] = mod
    return out


def order(sheets):
    """Sheets in run order: ORDER first, then any other sheet after the last sheet (already placed) it reads."""
    sheets = list(sheets)
    out = [s for s in ORDER if s in sheets]
    for s in sorted(s for s in sheets if s not in out):
        deps = DEPS.get(s, {})
        pos = max((out.index(d) + 1 for d in deps if d in out), default=len(out))
        out.insert(pos, s)
    return out


# ---------------------------------------------------------------------------------------------------------------
# Loading and blanking
# ---------------------------------------------------------------------------------------------------------------

def _box(ref):
    a, b = ref.split(':')
    (c0, r0), (c1, r1) = split(a), split(b)
    return r0, c0, r1, c1


def spill_cells(sheet):
    """(row, col) of every cell of the sheet's multi-cell array ranges, anchors included."""
    out = []
    for s, target, _ in SPILLS:
        if s == sheet:
            r0, c0, r1, c1 = _box(target)
            out += [(r, c) for r in range(r0, r1 + 1) for c in range(c0, c1 + 1)]
    return out


def fill_spills(book, sheet):
    """Spill the sheet's TRANSPOSE array formulas over their whole range (see SPILLS)."""
    S = book[sheet]
    for s, target, source in SPILLS:
        if s != sheet:
            continue
        r0, c0, r1, c1 = _box(target)
        q0, d0, q1, d1 = _box(source)
        for i in range(r1 - r0 + 1):
            for j in range(c1 - c0 + 1):
                r, c = q0 + j, d0 + i                       # transposed
                v = S.get(r, c) if r <= q1 and c <= d1 else NA
                S.set(r0 + i, c0 + j, 0 if v is None else v)


def load(folder):
    """Book.load plus book.formulas = {sheet: [(row, col), ...]}: the cells that hold a formula in the template,
    including every cell of a multi-cell array formula (SPILLS), not just its anchor."""
    folder = Path(folder)
    book = Book.load(folder)
    book.formulas = {}
    for f in folder.glob('*.json.gz'):
        d = json.loads(gzip.decompress(f.read_bytes()))
        cells = [tuple(x) for x in d['formulas']]
        book.formulas[d['sheet']] = cells + [k for k in spill_cells(d['sheet']) if k not in set(cells)]
    return book


def blank(book, sheets=None):
    """Delete every formula cell of the given sheets (default: every ported sheet), leaving only inputs."""
    for s in (modules() if sheets is None else sheets):
        S = book[s]
        for k in book.formulas.get(s, ()):
            S.cells.pop(k, None)


# ---------------------------------------------------------------------------------------------------------------
# The run
# ---------------------------------------------------------------------------------------------------------------

def _same(a, b, tol):
    if a == b:
        return True
    if a in (None, '') and b in (None, ''):
        return True
    if isinstance(a, float) and isinstance(b, float) and math.isnan(a) and math.isnan(b):
        return True
    return tol > 0 and close(a, b, rel=tol, abs_=tol)


def _changed(before, after, tol):
    """Number of cells whose value differs."""
    n = 0
    for k in before.keys() | after.keys():
        if not _same(before.get(k), after.get(k), tol):
            n += 1
    return n


def settle(book, max_passes=40, tol=0.0, sheets=None, log=None):
    """Gauss-Seidel over the sheets until a pass changes nothing. Returns (passes, settled, history), history being
    one {sheet: cells changed} per pass. A sheet is skipped in a pass when none of the sheets it reads (nor itself)
    has changed since it was last computed; the settling pass is always a full one."""
    mods = modules()
    seq = order(s for s in mods if sheets is None or s in sheets)
    version = {s: 0 for s in DEPS} | {s: 0 for s in seq}
    seen = {}
    history = []
    full = True
    for p in range(1, max_passes + 1):
        changed = {}
        for s in seq:
            deps = [d for d in DEPS.get(s, {}) if d in version] + [s]
            stamp = tuple(version[d] for d in deps)
            if not full and seen.get(s) == stamp:
                continue
            S = book[s]
            before = dict(S.cells)
            mods[s].compute(book, s)
            fill_spills(book, s)
            n = _changed(before, S.cells, tol)
            if n:
                changed[s] = n
                version[s] += 1
            seen[s] = tuple(version[d] for d in deps)
        history.append(changed)
        if log:
            log(f'pass {p}: ' + (', '.join(f'{s} {n}' for s, n in changed.items()) or 'no change'))
        if not changed:
            if full:
                return p, True, history
            full = True               # confirm with a pass that recomputes every sheet
        else:
            full = False
    return max_passes, False, history


def run(book, max_passes=40, tol=0.0, fan=False, gfn=False, seed=None, log=None):
    """Recompute every formula sheet of `book` from the values already in it, then optionally run the fanchart and
    GFN converge macros (in the template's button order), re-settling after each.

    Returns a dict: passes (formula passes in total), settled (every settle reached a fixed point), history, and
    the macros' results ('fan': simulate's dict; 'gfn': (converged, iterations, check) or the MacroError text)."""
    from . import fan as fanmod
    from . import gfn as gfnmod
    out = {'passes': 0, 'settled': True, 'history': []}

    def go():
        p, ok, h = settle(book, max_passes, tol, log=log)
        out['passes'] += p
        out['settled'] &= ok
        out['history'] += h

    go()
    if fan:
        out['fan'] = fanmod.simulate(book, seed=fanmod.SEED if seed is None else seed)
        go()
    if gfn:
        try:
            out['gfn'] = gfnmod.simulate(book)
        except gfnmod.MacroError as e:          # the VBA would stop here too (see gfn.QUIRKS)
            out['gfn'] = f'MacroError: {e}'
        go()
    return out


# ---------------------------------------------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------------------------------------------

HEADLINES = [
    ('Logit stress probability (LOGIT!J23)', 'LOGIT', 'J23'),
    ('Near-term signal (LOGIT!J24)', 'LOGIT', 'J24'),
    ('Debt fanchart index (FAN!I14)', 'FAN', 'I14'),
    ('Debt fanchart signal (FAN!I15)', 'FAN', 'I15'),
    ('GFN financeability index (GFN!K8)', 'GFN', 'K8'),
    ('GFN financeability signal (GFN!K9)', 'GFN', 'K9'),
    ('Medium-term index (Signals!J5)', 'Signals', 'J5'),
    ('Medium-term signal (Signals!K5)', 'Signals', 'K5'),
]


def headlines(book):
    return [(label, book[sh][cell]) for label, sh, cell in HEADLINES]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--golden', default='tests/golden/srdsf', help='folder written by scripts/srdsf_golden.py')
    ap.add_argument('--keep', action='store_true', help='start from the cached values instead of blank formulas')
    ap.add_argument('--fan', action='store_true', help='run the fanchart macro (seeded) after settling')
    ap.add_argument('--gfn', action='store_true', help='run the GFN converge macro after settling')
    ap.add_argument('--max-passes', type=int, default=40)
    ap.add_argument('--tol', type=float, default=0.0)
    ap.add_argument('-v', '--verbose', action='store_true')
    a = ap.parse_args(argv)
    book = load(a.golden)
    if not a.keep:
        blank(book)
    t = time.time()
    res = run(book, a.max_passes, a.tol, fan=a.fan, gfn=a.gfn, log=print if a.verbose else None)
    print(f"sheets: {', '.join(order(modules()))}")
    print(f"passes: {res['passes']}  settled: {res['settled']}  time: {time.time() - t:.1f}s")
    for k in ('fan', 'gfn'):
        if k in res:
            print(f'{k} macro: {res[k]}')
    for label, v in headlines(book):
        print(f'{label}: {v}')
    return 0 if res['settled'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
