"""Simplified logger module that uses the adapter system.

This module provides backward compatibility while delegating to the new
logger adapter system. It imports the configured logger adapter and
exposes it as the main Logger class.
"""

import logging
import typing as t
from inspect import currentframe

# Import from the adapter system
from .adapters.logger import LoggerProtocol
from .config import Config, Settings
from .depends import depends


class LoggerSettings(Settings):
    """Backward compatibility logger settings."""

    verbose: bool = False
    deployed_level: str = "WARNING"
    log_level: str | None = "INFO"
    serialize: bool | None = False
    format: dict[str, str] | None = {
        "time": "<b><e>[</e> <w>{time:YYYY-MM-DD HH:mm:ss.SSS}</w> <e>]</e></b>",
        "level": " <level>{level:>8}</level>",
        "sep": " <b><w>in</w></b> ",
        "name": "<b>{extra[mod_name]:>20}</b>",
        "line": "<b><e>[</e><w>{line:^5}</w><e>]</e></b>",
        "message": "  <level>{message}</level>",
    }
    level_per_module: dict[str, str | None] | None = {}
    level_colors: dict[str, str] | None = {}
    settings: dict[str, t.Any] | None = {}

    def __init__(self, **values: t.Any) -> None:
        super().__init__(**values)
        self.settings = {
            "format": "".join(self.format.values() if self.format else []),
            "enqueue": True,
            "backtrace": False,
            "catch": False,
            "serialize": self.serialize,
            "diagnose": False,
            "colorize": True,
        }


# Set up logger settings for backward compatibility
depends.get(Config).logger = LoggerSettings()


def _get_logger_adapter() -> type[t.Any]:
    """Get the configured logger adapter class."""
    from .adapters import import_adapter

    # Import the logger adapter (defaults to loguru)
    try:
        return import_adapter("logger")  # type: ignore[no-any-return]
    except Exception:
        # Fallback to loguru adapter directly if import fails
        from .adapters.logger.loguru import Logger as LoguruLogger

        return LoguruLogger


# Create Logger class that delegates to the adapter
Logger = _get_logger_adapter()
# Initialize the logger
try:
    logger_instance = depends.get(Logger)
    if hasattr(logger_instance, "init"):
        logger_instance.init()
    depends.set(Logger, logger_instance)
except Exception:
    # Fallback initialization
    from .adapters.logger.loguru import Logger as LoguruLogger

    logger_instance = LoguruLogger()
    logger_instance.init()
    depends.set(Logger, logger_instance)


class InterceptHandler(logging.Handler):
    """Handler to intercept standard library logging."""

    def emit(self, record: logging.LogRecord) -> None:
        """Emit log record via the configured logger adapter."""
        # Get logger instance from dependency container
        try:
            logger = depends.get(Logger)
        except Exception:
            # Fallback to basic logging if logger not available
            return

        try:
            # Try to get level from logger if it has the method
            if hasattr(logger, "level"):
                level = logger.level(record.levelname).name  # type: ignore[no-untyped-call]
            else:
                level = record.levelno
        except (ValueError, AttributeError):
            level = record.levelno

        frame, depth = (currentframe(), 0)
        while frame and (depth == 0 or frame.f_code.co_filename == logging.__file__):
            frame = frame.f_back
            depth += 1

        # Use the logger's appropriate method based on its capabilities
        if hasattr(logger, "opt") and hasattr(logger, "log"):
            # Loguru-style logging
            logger.opt(depth=depth, exception=record.exc_info).log(  # type: ignore[no-untyped-call]
                level,
                record.getMessage(),
            )
        else:
            # Fallback to basic logging methods
            level_name = record.levelname.lower()
            log_method = getattr(logger, level_name, logger.info)
            log_method(record.getMessage())


# Configure stdlib logging interception
logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)

# Export for backward compatibility
__all__ = ["InterceptHandler", "Logger", "LoggerProtocol", "LoggerSettings"]
