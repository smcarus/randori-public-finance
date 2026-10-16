"""End-to-end MAC SRDSF run (sovrisk.srdsf.run): starting from the template's inputs only, chaining every ported sheet
must reproduce the template.

1. The template's sample country: blank every formula cell of every ported sheet, run, compare with Excel's
   cached values (errors must be the same error).
2. Changed inputs (scripts/srdsf_alt_golden.py): a few macro paths, debt-instrument terms and the country are
   edited, LibreOffice recalculates the workbook, and run() must reproduce LibreOffice's values. LibreOffice
   sometimes returns a different error type than Excel for the same failing formula (#VALUE! for #N/A or #NUM!,
   already on the unchanged template), so there an error only has to come out as an error.
"""
import gzip
import json
from pathlib import Path

import pytest

from sovrisk.srdsf import run as R
from sovrisk.srdsf.book import cl, close, iserr, split

GOLDEN = Path(__file__).resolve().parent / 'golden' / 'srdsf'
ALT = Path(__file__).resolve().parent / 'golden' / 'srdsf_alt'
pytestmark = pytest.mark.skipif(not GOLDEN.exists(), reason='no golden values')

# Cells where LibreOffice's result is not Excel's, so the oracle is wrong there. Charts!E4538/F4538 are
# SWITCH(<TRUE/FALSE>, 0, ..., 1, ..., default): Excel never matches a logical to 0 or 1 and takes the default
# (charts.QUIRKS); LibreOffice converts FALSE to 0. Output!EL338/EL339 print those two cells.
LO_DIFFERS = {'Charts': {'E4538', 'F4538'}, 'Output': {'EL338', 'EL339'}}


def _diff(got, want, cells, same_error):
    bad = []
    for k in cells:
        g, w = got.cells.get(k), want.get(k)
        if iserr(w) or iserr(g):
            ok = (g == w) if same_error else (iserr(g) and iserr(w))
        else:
            ok = close(g, w)
        if not ok:
            bad.append((f'{cl(k[1])}{k[0]}', g, w))
    return bad


def _check(book, want, same_error, skip=None):
    report = {}
    for sheet in R.modules():
        cells = [(r, c) for r, c in book.formulas[sheet] if f'{cl(c)}{r}' not in (skip or {}).get(sheet, ())]
        bad = _diff(book[sheet], want[sheet], cells, same_error)
        if bad:
            report[sheet] = (len(bad), len(book.formulas[sheet]), bad[:5])
    assert not report, report


def test_run_from_inputs_reproduces_template():
    book = R.load(GOLDEN)
    want = {s: dict(book[s].cells) for s in book.sheets}
    R.blank(book)
    assert all(book[s].get(r, c) is None for s in R.modules() for r, c in book.formulas[s])
    res = R.run(book)
    assert res['settled'], res['history']
    _check(book, want, same_error=True)


@pytest.mark.skipif(not (ALT / 'expected.json.gz').exists(), reason='no LibreOffice changed-input golden')
def test_run_reproduces_libreoffice_with_changed_inputs():
    book = R.load(GOLDEN)
    for sheet, ref, v in json.loads((ALT / 'changes.json').read_text()):
        c, r = split(ref)
        assert (r, c) not in book.formulas[sheet] and book[sheet][ref] != v       # an input, really changed
        book[sheet][ref] = v
    want = {s: dict(book[s].cells) for s in book.sheets}
    for sheet, cells in json.loads(gzip.decompress((ALT / 'expected.json.gz').read_bytes())).items():
        for r, c, v in cells:
            want[sheet][(r, c)] = v
    R.blank(book)
    res = R.run(book)
    assert res['settled'], res['history']
    _check(book, want, same_error=False, skip=LO_DIFFERS)


def test_run_order_places_new_sheets_after_what_they_read():
    seq = R.order(['Output', 'Charts', 'BaseDB', 'Signals', 'Questions', 'Unknown'])
    assert seq.index('Charts') > seq.index('Signals') and seq.index('Output') > seq.index('Charts')
    assert seq[0] == 'Questions' and 'Unknown' in seq
