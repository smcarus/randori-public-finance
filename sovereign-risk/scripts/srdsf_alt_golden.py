"""Changed-input oracle for the MAC SRDSF port: edit a few inputs of the template, recalculate it in LibreOffice and
store what changed, so tests/test_srdsf_run.py can check that sovrisk.srdsf.run reproduces it.

    python scripts/srdsf_alt_golden.py path/to/mac-srdsf-template.xlsm [workdir]

Writes tests/golden/srdsf_alt/changes.json   [[sheet, cell, new value], ...]
       tests/golden/srdsf_alt/expected.json.gz {sheet: [[row, col, value], ...]}: every formula cell (template
       formula list) whose LibreOffice value with the edits differs from LibreOffice's value for the unedited
       template. Applied over the template's cached (Excel) values in tests/golden/srdsf, this gives the expected
       book without the few places where LibreOffice and Excel disagree on the unchanged template (error types,
       TEXT(6,"0.#")).
The input cells are edited directly in the sheet XML (no openpyxl round trip), LibreOffice recalculates every
formula on load, and scripts/srdsf_golden.py reads the result. The sample country's data stay the template's
fictional sample; the country name is set only so that the country lookups (IFS code, AE/EM, currency union)
resolve.
"""
import gzip
import json
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'scripts'))

from sovrisk.srdsf.book import Book, ci, cl  # noqa: E402
from sovrisk.srdsf.run import load  # noqa: E402

GOLDEN = ROOT / 'tests' / 'golden' / 'srdsf'
OUT = ROOT / 'tests' / 'golden' / 'srdsf_alt'


def changes(book):
    """The edited inputs: (sheet, cell, value)."""
    M = book['Macrofw']
    out = [('Questions', 'C4', 'Albania')]                    # country lookups resolve (EM, not in a union)
    for k, c in enumerate(range(ci('AE'), ci('AO') + 1)):
        out.append(('Macrofw', f'{cl(c)}7', M.get(7, c) * (1 - 0.01 * (k + 1))))     # real GDP: lower growth
        out.append(('Macrofw', f'{cl(c)}13', M.get(13, c) * 1.1))                     # exchange rate, avg: +10%
        out.append(('Macrofw', f'{cl(c)}14', M.get(14, c) * 1.1))                     # exchange rate, eop: +10%
        out.append(('Macrofw', f'{cl(c)}183', M.get(183, c) + 0.02))                  # instrument 1 interest rate
        out.append(('Macrofw', f'{cl(c)}236', 7))                                     # instrument 2 maturity 15 -> 7
    for c in range(ci('AE'), ci('AI') + 1):
        out.append(('Macrofw', f'{cl(c)}28', M.get(28, c) - 2.0))                     # revenues: -2 bn
        out.append(('Macrofw', f'{cl(c)}158', M.get(158, c) * 1.5))                   # instrument 2 issuance +50%
    for c in range(ci('AG'), ci('AO') + 1):
        out.append(('Macrofw', f'{cl(c)}262', 2))                                     # instrument 2 in FX from t+2
    out += [('NewMacrofw', 'AE52', 10.0), ('NewMacrofw', 'AE53', 5.0)]               # intl-law / multilateral debt
    return out


def _sheet_files(z):
    wb = z.read('xl/workbook.xml').decode()
    rels = z.read('xl/_rels/workbook.xml.rels').decode()
    target = dict(re.findall(r'<Relationship Id="([^"]+)"[^>]*Target="([^"]+)"', rels))
    target.update({a: b for b, a in re.findall(r'<Relationship [^>]*Target="([^"]+)"[^>]*Id="([^"]+)"', rels)})
    out = {}
    for name, rid in re.findall(r'<sheet name="([^"]+)"[^>]*r:id="([^"]+)"', wb):
        out[name] = 'xl/' + target[rid].lstrip('/').removeprefix('xl/')
    return out


def _set(xml, ref, v):
    m = re.search(rf'<c r="{ref}"(?P<a>[^>]*?)(?:/>|>(?P<body>.*?)</c>)', xml, re.S)
    if not m:
        raise KeyError(ref)
    if m.group('body') and '<f' in m.group('body'):
        raise ValueError(f'{ref} holds a formula')
    s = re.search(r'\ss="\d+"', m.group('a'))
    s = s.group(0) if s else ''
    if isinstance(v, str):
        esc = v.replace('&', '&amp;').replace('<', '&lt;')
        new = f'<c r="{ref}"{s} t="inlineStr"><is><t>{esc}</t></is></c>'
    else:
        new = f'<c r="{ref}"{s}><v>{float(v)!r}</v></c>'
    return xml[:m.start()] + new + xml[m.end():]


def build(src, dst, edits):
    files = {}
    with zipfile.ZipFile(src) as z:
        paths = _sheet_files(z)
        for sheet in {s for s, _, _ in edits}:
            files[paths[sheet]] = z.read(paths[sheet]).decode()
        for sheet, ref, v in edits:
            files[paths[sheet]] = _set(files[paths[sheet]], ref, v)
        with zipfile.ZipFile(dst, 'w', zipfile.ZIP_DEFLATED) as out:
            for item in z.infolist():
                data = files[item.filename].encode() if item.filename in files else z.read(item.filename)
                out.writestr(item, data)


def recalc(src, outdir):
    """Full recalculation in LibreOffice (recalc on load = always), saved as xlsx."""
    prof = Path(outdir) / 'lo_profile' / 'user'
    prof.mkdir(parents=True, exist_ok=True)
    (prof / 'registrymodifications.xcu').write_text(
        '<?xml version="1.0" encoding="UTF-8"?><oor:items xmlns:oor="http://openoffice.org/2001/registry" '
        'xmlns:xs="http://www.w3.org/2001/XMLSchema" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
        '<item oor:path="/org.openoffice.Office.Calc/Formula/Load"><prop oor:name="OOXMLRecalcMode" oor:op="fuse">'
        '<value>0</value></prop></item></oor:items>')
    subprocess.run(['soffice', f'-env:UserInstallation=file://{prof.parent}', '--headless', '--calc',
                    '--convert-to', 'xlsx', '--outdir', str(outdir), str(src)], check=True, timeout=1800)
    return Path(outdir) / (Path(src).stem + '.xlsx')


def main(src, work=None):
    import srdsf_golden
    work = Path(work or tempfile.mkdtemp())
    work.mkdir(parents=True, exist_ok=True)
    base = load(GOLDEN)
    edits = changes(base)
    xlsm = work / 'mac-srdsf-alt.xlsm'
    build(src, xlsm, edits)
    srdsf_golden.main(recalc(xlsm, work), work / 'golden')
    srdsf_golden.main(recalc(src, work / 'orig'), work / 'golden_orig')
    alt, orig = Book.load(work / 'golden'), Book.load(work / 'golden_orig')
    expected = {}
    for sheet, cells in base.formulas.items():
        diff = [[r, c, alt[sheet].get(r, c)] for r, c in cells if alt[sheet].get(r, c) != orig[sheet].get(r, c)]
        if diff:
            expected[sheet] = diff
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / 'changes.json').write_text(json.dumps(edits, indent=0))
    (OUT / 'expected.json.gz').write_bytes(gzip.compress(json.dumps(expected, separators=(',', ':')).encode(),
                                                         mtime=0))
    print({s: len(v) for s, v in expected.items()})
    shutil.rmtree(work / 'lo_profile', ignore_errors=True)


if __name__ == '__main__':
    main(*sys.argv[1:])
