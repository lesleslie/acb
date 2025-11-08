"""Type checking adapters for the ACB framework.

This package provides adapters for various type checking tools,
including the Zuban type checker which offers fast Rust-based
type checking for Python code.
"""

from .zuban import ZubanAdapter, ZubanSettings

__all__ = ["ZubanAdapter", "ZubanSettings"]
