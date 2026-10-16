"""sovrisk: Randori Public Finance risk models RPF-01 to RPF-06 (UNTESTED, PRELIMINARY).

RPF-01 sovereign scorecard (sovrisk.model and the decision tools), RPF-02 PFRAM (sovrisk.pfram), RPF-03 municipal
scorecard (sovrisk.muni), RPF-04 debt sustainability (sovrisk.srdsf, sovrisk.licdsf), RPF-05 early warning
(sovrisk.ews) and RPF-06 spillover (sovrisk.spillover). See docs/models/ for one card per model.

Not investment advice and not a credit rating.
"""
from .config import load_config
from .model import run_model

__version__ = '0.8.1'
__all__ = ['load_config', 'run_model']
