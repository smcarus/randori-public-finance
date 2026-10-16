"""MainFanchart port: blank the cells the macro writes into FAN, run simulate() with the template's seed and get
back exactly the values the macro left in the workbook."""
import gzip
import json
from pathlib import Path

import numpy as np
import pytest

from sovrisk.srdsf.book import Book, cl
from sovrisk.srdsf.fan import SEED, MersenneTwister, draw_zig_n, simulate

GOLDEN = Path(__file__).resolve().parent / 'golden' / 'srdsf'
pytestmark = pytest.mark.skipif(not GOLDEN.exists(), reason='no golden values')

# value cells the macro writes: the percentile blocks Z31:AE61, the D12 probability (written as a formula of
# literals), the realism-adjustment row D18:G18 and the observation pick-up cells C7:D7
OUT = [(r, c) for r in range(31, 62) for c in range(26, 32)] + [(12, 4), (18, 4), (18, 5), (18, 6), (18, 7),
                                                                 (7, 3), (7, 4)]


def _formulas(sheet):
    for f in GOLDEN.glob('*.json.gz'):
        d = json.loads(gzip.decompress(f.read_bytes()))
        if d['sheet'] == sheet:
            return {tuple(x) for x in d['formulas']}
    raise KeyError(sheet)


def test_mersenne_twister_matches_reference():
    ref = np.random.MT19937()
    ref._legacy_seeding(SEED & 0xFFFFFFFF)          # numpy's init_genrand-seeded MT19937
    mt = MersenneTwister(SEED)
    assert [mt.uint32() for _ in range(2000)] == ref.random_raw(2000).tolist()


def test_ziggurat_is_standard_normal():
    z = draw_zig_n(MersenneTwister(12345), 20000, 0, 1)
    assert abs(z.mean()) < 0.03 and abs(z.std() - 1) < 0.03


def test_simulate_reproduces_macro_output():
    book = Book.load(GOLDEN)
    F = book['FAN']
    formulas = _formulas('FAN')
    want = {k: F.cells.get(k) for k in OUT if k not in formulas or k == (12, 4)}
    for k in want:
        F.cells.pop(k, None)
    out = simulate(book, seed=SEED)
    assert out['dspb_above'] == 5357 and not out['adj_realism']
    bad = [(f'{cl(c)}{r}', F.cells.get((r, c)), w) for (r, c), w in want.items()
           if F.cells.get((r, c)) != w]                         # bit-for-bit
    # Z:AE only: AF:AI in rows 33-49 are leftovers of an older run and lie outside the macro's clear range
    assert not bad, bad[:10]
    assert sum(isinstance(v, float) for v in want.values()) == 61      # 60 percentiles + D12


def test_simulate_then_compute():
    from sovrisk.srdsf.fan import compute
    book = Book.load(GOLDEN)
    want = dict(book['FAN'].cells)
    simulate(book)
    compute(book, 'FAN')
    for ref, (r, c) in (('D11', (11, 4)), ('I14', (14, 9)), ('I15', (15, 9)), ('N49', (49, 14))):
        assert book['FAN'].cells[(r, c)] == pytest.approx(want[(r, c)], rel=1e-12) \
            if isinstance(want[(r, c)], float) else book['FAN'].cells[(r, c)] == want[(r, c)], ref
