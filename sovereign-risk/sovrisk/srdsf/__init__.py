"""RPF-04 debt sustainability: a Python port of the IMF Sovereign Risk and Debt Sustainability Framework for
market-access countries (MAC SRDSF) public template.

Each module ports one sheet (or a tightly linked group of sheets) of the template. A sheet function takes a Book
holding the values of the sheets it reads and fills its own sheet in the same cell layout as the workbook, so every
cell can be checked against the template (tests/test_srdsf.py). run.py chains the sheets.
Independent port; not endorsed by the IMF. Untested on a real country.
"""
