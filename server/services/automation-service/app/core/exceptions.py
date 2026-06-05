"""
Core - Exception Hierarchy (module shim)
=========================================
Canonical definitions live in _exceptions.py.
This file exists so `from app.core.exceptions import X` works whether
Python resolves `app.core.exceptions` to this .py file or to the
exceptions/ package __init__.py.
"""
from app.core._exceptions import *  # noqa: F401, F403
from app.core._exceptions import __all__  # noqa: F401
