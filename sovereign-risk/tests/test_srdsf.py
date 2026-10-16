"""MAC SRDSF port: each ported sheet, run on the template's sample country with every other sheet at the
template's own values, must reproduce every formula cell of that sheet (scripts/srdsf_golden.py)."""
import gzip
import importlib
import json
import pkgutil
from pathlib import Path

import pytest

import sovrisk.srdsf as pkg
from sovrisk.srdsf.book import Book, Sheet, cl, compare

GOLDEN = Path(__file__).resolve().parent / 'golden' / 'srdsf'


def _ported():
    out = []
    for m in pkgutil.iter_modules(pkg.__path__):
        mod = importlib.import_module(f'sovrisk.srdsf.{m.name}')
        for sheet in getattr(mod, 'SHEETS', ()):
            out.append((m.name, sheet))
    return out


def _formulas(sheet):
    for f in GOLDEN.glob('*.json.gz'):
        d = json.loads(gzip.decompress(f.read_bytes()))
        if d['sheet'] == sheet:
            return [tuple(x) for x in d['formulas']]
    raise KeyError(sheet)


@pytest.mark.skipif(not GOLDEN.exists(), reason='no golden values')
@pytest.mark.parametrize('module,sheet', _ported())
def test_sheet_matches_template(module, sheet):
    book = Book.load(GOLDEN)
    want = Sheet(sheet, dict(book[sheet].cells))
    fcells = _formulas(sheet)
    for k in fcells:                      # the port must produce every formula cell itself
        book[sheet].cells.pop(k, None)
    mod = importlib.import_module(f'sovrisk.srdsf.{module}')
    mod.compute(book, sheet)
    bad = compare(book[sheet], want, fcells)
    assert not bad, f'{sheet}: {len(bad)} of {len(fcells)} cells differ, first: {bad[:5]}'
