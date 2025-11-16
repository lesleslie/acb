"""Simplified logger module that uses the adapter system.

This module provides backward compatibility while delegating to the new
logger adapter system. It imports the configured logger adapter and
exposes it as the main Logger class.

The actual logger implementations are in acb.adapters.logger (Loguru, Structlog).
This module serves as a convenience import shim.
"""

import os
import sys

import typing as t
from contextlib import suppress

# Import protocol and base from the adapter system
from .adapters.logger import LoggerBaseSettings, LoggerProtocol

# Import InterceptHandler from loguru adapter for backward compatibility
from .adapters.logger.loguru import InterceptHandler


def _get_logger_adapter() -> type[t.Any]:
    """Get the configured logger adapter class.

    This function lazily imports the logger adapter to avoid
    circular dependencies during module initialization.
    """
    from .adapters import import_adapter

    # Import the logger adapter (defaults to loguru)
    try:
        return import_adapter("logger")  # type: ignore[no-any-return]
    except Exception:
        # Fallback to loguru adapter directly if import fails
        from .adapters.logger.loguru import Logger as LoguruLogger

        return LoguruLogger


def _initialize_logger() -> None:
    """Initialize the logger and register it with the dependency container.

    This is called automatically when the module is imported, unless in testing mode.
    """
    from .depends import depends

    # Check if we're in testing mode
    if "pytest" in sys.modules or os.getenv("TESTING", "False").lower() == "true":
        return

    # Get logger class
    logger_class = _get_logger_adapter()

    # Check if already registered
    with suppress(Exception):
        depends.get_sync(logger_class)
        return  # Already initialized

    # Create and initialize logger instance
    with suppress(Exception):
        logger_instance = logger_class()
        if hasattr(logger_instance, "init"):
            logger_instance.init()
        depends.set(logger_class, logger_instance)


# Create Logger class that delegates to the adapter
# This is imported by other modules as: from acb.logger import Logger
Logger = _get_logger_adapter()

# Initialize logger on module import (unless in testing mode)
_initialize_logger()

# Backward compatibility alias for settings
LoggerSettings = LoggerBaseSettings

# Export for backward compatibility
__all__ = [
    "Logger",
    "LoggerProtocol",
    "LoggerSettings",
    "LoggerBaseSettings",
    "InterceptHandler",
]
