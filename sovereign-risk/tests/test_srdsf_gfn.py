"""GFN `converge` macro port (sovrisk.srdsf.gfn.simulate): blank the macro's output (Config!GFNConvergeOut), rerun
it, and compare with the values the template ships with."""
from pathlib import Path

import pytest

from sovrisk.srdsf import gfn
from sovrisk.srdsf.book import Book, close

GOLDEN = Path(__file__).resolve().parent / 'golden' / 'srdsf'
pytestmark = pytest.mark.skipif(not GOLDEN.exists(), reason='no golden values')


def _out(book):
    _, c0, r, c1, _ = book.area('GFNConvergeOut')
    return [book['Config'].get(r, c) for c in range(c0, c1 + 1)]


def _blank(book):
    _, c0, r, c1, _ = book.area('GFNConvergeOut')
    for c in range(c0, c1 + 1):
        book['Config'].cells.pop((r, c), None)


def test_converge_reproduces_template_output():
    book = Book.load(GOLDEN)
    want = _out(book)
    # The shipped workbook has no country selected, so GFNinCU and the AE/EM exchange-rate pass-through are #N/A
    # and the macro cannot run. GFNConvergeOut was left by a run for the sample country: not in a currency union
    # (GFNinCU FALSE), emerging market (pass-through 0.25).
    book['Config']['CG7'] = False
    book['Config']['CI21'] = 0.25
    _blank(book)
    converged, iters, chk = gfn.simulate(book)
    assert converged and iters <= book.name('GFNMaxiters') + 1
    got = _out(book)
    bad = [(i, g, w) for i, (g, w) in enumerate(zip(got, want)) if not close(g, w)]
    assert not bad, bad
    # at the fixed point GFN's financing feeds back unchanged
    G = book['GFN']
    for k, w in enumerate(want[:12]):
        assert close(G.get(144, 10 + k), w)


def test_converge_stops_on_error_check_like_vba():
    book = Book.load(GOLDEN)
    with pytest.raises(gfn.MacroError):
        gfn.simulate(book)
    assert all(v is None for v in _out(book))       # ClearContents ran before the type mismatch
