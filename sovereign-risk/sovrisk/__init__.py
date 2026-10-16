"""sovrisk: Python port of the Randori RPF-01 sovereign risk scorecard (v0.5, UNTESTED, PRELIMINARY).

Not investment advice and not a credit rating.
"""
from .config import load_config
from .model import run_model

__version__ = '0.8.1'
__all__ = ['load_config', 'run_model']
