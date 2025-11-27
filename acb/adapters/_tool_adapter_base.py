"""Shared helpers for simple CLI-like tool adapters used in tests.

This is a minimal surface for tool adapter implementations.
"""

from __future__ import annotations

import typing as t
from dataclasses import dataclass

from acb.config import Settings


class ToolAdapterSettings(Settings):
    """Base settings for simple tool adapters."""

    # Common timeouts / retries
    connection_timeout: int = 30
    api_retry_attempts: int = 3
    api_retry_delay: float = 1.0


@dataclass
class ServiceResponse:
    """Generic response wrapper used by tests."""

    success: bool
    result: t.Any = None
