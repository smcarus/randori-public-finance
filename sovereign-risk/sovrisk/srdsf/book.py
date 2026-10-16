"""Cell store with the workbook's layout, so ported sheets read and write cells as the template does."""
import gzip
import json
import math
import re
from pathlib import Path

from openpyxl.utils import column_index_from_string, get_column_letter

_CELL = re.compile(r"^\$?([A-Z]{1,3})\$?(\d+)$")


def ci(col):
    """Column letters -> 1-based index ('A' -> 1)."""
    return column_index_from_string(col)


def cl(i):
    """1-based index -> column letters."""
    return get_column_letter(i)


def split(ref):
    m = _CELL.match(ref)
    if not m:
        raise ValueError(f'not a cell reference: {ref}')
    return ci(m.group(1)), int(m.group(2))


class Sheet:
    """Values of one sheet, keyed by (row, col). Missing cells read as None (Excel blank)."""

    def __init__(self, name, cells=None):
        self.name = name
        self.cells = {} if cells is None else cells

    def __getitem__(self, ref):
        if isinstance(ref, str):
            ref = split(ref)[::-1]
        return self.cells.get(ref)

    def __setitem__(self, ref, v):
        if isinstance(ref, str):
            ref = split(ref)[::-1]
        self.cells[ref] = v

    def get(self, row, col):
        return self.cells.get((row, col))

    def set(self, row, col, v):
        self.cells[(row, col)] = v

    def n(self, row, col):
        """Numeric value as Excel uses it in arithmetic: blank -> 0, bool -> 0/1."""
        v = self.cells.get((row, col))
        if v is None or v == '':
            return 0.0
        if isinstance(v, bool):
            return float(v)
        return v

    def row(self, row, c0, c1):
        return [self.cells.get((row, c)) for c in range(c0, c1 + 1)]

    def rng(self, ref):
        """'A1:C3' -> list of rows of values."""
        a, b = ref.replace('$', '').split(':') if ':' in ref else (ref, ref)
        (c0, r0), (c1, r1) = split(a), split(b)
        return [[self.cells.get((r, c)) for c in range(c0, c1 + 1)] for r in range(r0, r1 + 1)]


class Book:
    """Sheets by name plus the workbook's defined names."""

    def __init__(self, sheets=None, names=None):
        self.sheets = sheets or {}
        self.names = names or {}

    def __getitem__(self, name):
        if name not in self.sheets:
            self.sheets[name] = Sheet(name)
        return self.sheets[name]

    def name(self, nm):
        """Resolve a single-cell defined name to its value."""
        ref = self.names[nm.lower()]
        sh, cell = ref.rsplit('!', 1)
        return self[sh.strip("'")][cell.replace('$', '')]

    def name_ref(self, nm):
        ref = self.names[nm.lower()]
        sh, cell = ref.rsplit('!', 1)
        return sh.strip("'"), cell.replace('$', '')

    def area(self, nm_or_ref):
        """A defined name or 'Sheet!A1:B9' -> (sheet, c0, r0, c1, r1). Whole rows ('$9:$333') and whole columns
        ('$A:$C') extend to the sheet's used cells."""
        ref = self.names.get(nm_or_ref.lower(), nm_or_ref)
        sh, a = ref.rsplit('!', 1)
        sh, a = sh.strip("'"), a.replace('$', '')
        p, q = a.split(':') if ':' in a else (a, a)
        S = self[sh]
        maxr = max((r for r, _ in S.cells), default=1)
        maxc = max((c for _, c in S.cells), default=1)
        def one(x, lo):
            if x.isdigit():                       # whole row
                return (1 if lo else maxc), int(x)
            if x.isalpha():                       # whole column
                return ci(x), (1 if lo else maxr)
            return split(x)
        (c0, r0), (c1, r1) = one(p, True), one(q, False)
        return sh, c0, r0, c1, r1

    def vlookup(self, key, area, col):
        """VLOOKUP(key, area, col, FALSE): exact match (text case-insensitive) in the area's first column."""
        from .xl import NA, eq
        if isinstance(key, str) and key.startswith('#'):
            return key
        sh, c0, r0, c1, r1 = self.area(area)
        S = self[sh]
        for r in range(r0, r1 + 1):
            v = S.get(r, c0)
            if v is not None and eq(v, key):
                return S.get(r, c0 + col - 1)
        return NA

    def hrow(self, area):
        """Values of a one-row area (for MATCH over a row)."""
        sh, c0, r0, c1, r1 = self.area(area)
        return [self[sh].get(r0, c) for c in range(c0, c1 + 1)]

    @classmethod
    def load(cls, folder, sheets=None):
        """Load golden values written by scripts/srdsf_golden.py (one <sheet>.json.gz per sheet + names.json)."""
        folder = Path(folder)
        names = json.loads((folder / 'names.json').read_text())
        b = cls(names=names)
        for f in sorted(folder.glob('*.json.gz')):
            nm = json.loads(gzip.decompress(f.read_bytes()))
            if sheets is not None and nm['sheet'] not in sheets:
                continue
            b.sheets[nm['sheet']] = Sheet(nm['sheet'], {(r, c): v for r, c, v in nm['cells']})
        return b


def iserr(v):
    return isinstance(v, str) and v.startswith('#')


def close(a, b, rel=1e-7, abs_=1e-6):
    if isinstance(a, bool) or isinstance(b, bool):
        return a == b
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        if isinstance(a, float) and math.isnan(a):
            return False
        return abs(a - b) <= max(abs_, rel * abs(b))
    if a in (None, '') and b in (None, ''):
        return True
    return a == b


def compare(got, want, formula_cells=None):
    """Mismatches between two Sheets over want's cells (or only formula_cells). Returns list of (ref, got, want)."""
    keys = formula_cells if formula_cells is not None else want.cells.keys()
    out = []
    for (r, c) in keys:
        w = want.cells.get((r, c))
        g = got.cells.get((r, c))
        if iserr(w):
            if not (iserr(g) or g is None):
                out.append((f'{cl(c)}{r}', g, w))
            continue
        if not close(g, w):
            out.append((f'{cl(c)}{r}', g, w))
    return out
