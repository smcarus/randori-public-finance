"""sovrisk: Python port of the Randori M-13 sovereign risk scorecard (v0.5, UNTESTED, PRELIMINARY).

Not investment advice and not a credit rating.
"""
from .config import load_config
from .model import run_model

__version__ = '0.5.0'
__all__ = ['load_config', 'run_model']
