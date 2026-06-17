"""
Core — Dependency Injection (shim)
====================================
The canonical implementation now lives in the package:
  app/core/dependency_injection/__init__.py

Python resolves `app.core.dependency_injection` to the package directory
when both a .py file and a directory with __init__.py share the same name.
This file is kept as a forward-compatibility shim so any tool or script
that directly references this .py path still works.

DO NOT add logic here — edit the package __init__.py instead.
"""
from app.core.dependency_injection import (  # noqa: F401 — re-export
    DIContainer,
    ServiceContainer,
    ServiceDescriptor,
    ServiceScope,
    get_container,
    reset_container,
)

__all__ = [
    "DIContainer",
    "ServiceContainer",
    "ServiceDescriptor",
    "ServiceScope",
    "get_container",
    "reset_container",
]
