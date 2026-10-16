"""Excel semantics the ported sheets share. Keep these exact: parity depends on them."""
import math

NA = '#N/A'
DIV0 = '#DIV/0!'
VALUE = '#VALUE!'


def iserr(v):
    return isinstance(v, str) and v.startswith('#')


def num(v):
    """A value as arithmetic sees it: blank -> 0, True/False -> 1/0. Errors pass through as strings."""
    if v is None or v == '':
        return 0.0
    if isinstance(v, bool):
        return 1.0 if v else 0.0
    return v


def isnumber(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def eq(a, b):
    """Excel '=': text compares case-insensitively, blank equals 0 and ''."""
    if a is None:
        a = '' if isinstance(b, str) else 0
    if b is None:
        b = '' if isinstance(a, str) else 0
    if isinstance(a, str) and isinstance(b, str):
        return a.lower() == b.lower()
    if isinstance(a, str) or isinstance(b, str):
        return False
    return a == b


def match(x, seq, kind=0):
    """MATCH: 1-based position or '#N/A'. kind 0 exact (text case-insensitive), 1 largest <= x (sorted ascending)."""
    if kind == 0:
        for i, v in enumerate(seq):
            if v is not None and eq(v, x):
                return i + 1
        return NA
    best = NA
    for i, v in enumerate(seq):
        if v is None or isinstance(v, str) != isinstance(x, str):
            continue
        if (kind == 1 and v <= x) or (kind == -1 and v >= x):
            best = i + 1
        else:
            break
    return best


def xround(x, d=0):
    """ROUND half away from zero."""
    m = 10 ** d
    return math.copysign(math.floor(abs(x) * m + 0.5) / m, x)


def xsum(values):
    """SUM over a range: numbers only (text and blanks ignored); an error anywhere returns that error."""
    t = 0.0
    for v in values:
        if iserr(v):
            return v
        if isnumber(v):
            t += v
    return t


def average(values):
    xs = [v for v in values if isnumber(v)]
    for v in values:
        if iserr(v):
            return v
    return sum(xs) / len(xs) if xs else DIV0


def div(a, b):
    if iserr(a):
        return a
    if iserr(b):
        return b
    b = num(b)
    return DIV0 if b == 0 else num(a) / b


def err(*vals):
    """The first Excel error among vals (what a formula over them returns), else None."""
    for v in vals:
        if iserr(v):
            return v
    return None


def calc(f, *vals):
    """f(*numbers) with Excel error propagation and blank -> 0."""
    e = err(*vals)
    if e:
        return e
    if any(isinstance(v, str) and v != '' for v in vals):
        return VALUE                       # text in arithmetic (numbers stored as text aside)
    try:
        return f(*(num(v) for v in vals))
    except ZeroDivisionError:
        return DIV0
    except (OverflowError, ValueError):
        return '#NUM!'
