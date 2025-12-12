"""Loguru-based logger adapter implementation."""

import logging
from inspect import currentframe
from uuid import UUID

import asyncio
import typing as t
from aioconsole import aprint
from contextlib import suppress
from datetime import UTC
from loguru._logger import Core as _Core
from loguru._logger import Logger as _Logger

from acb.adapters import (
    AdapterCapability,
    AdapterMetadata,
    AdapterStatus,
)

# Lazy import to avoid circular dependency with config
# from acb.config import debug
from acb.depends import depends

from ._base import LoggerBase, LoggerBaseSettings


class LoggerSettings(LoggerBaseSettings):
    """Loguru-specific logger settings."""

    # Loguru-specific format strings
    format: dict[str, str] | None = {
        "time": "<b><e>[</e> <w>{time:YYYY-MM-DD HH:mm:ss.SSS}</w> <e>]</e></b>",
        "level": " <level>{level:>8}</level>",
        "sep": " <b><w>in</w></b> ",
        "name": "<b>{extra[mod_name]:>20}</b>",
        "line": "<b><e>[</e><w>{line:^5}</w><e>]</e></b>",
        "message": "  <level>{message}</level>",
    }

    # Loguru specific settings
    backtrace: bool = False
    catch: bool = False
    diagnose: bool = False
    colorize: bool = True

    # Type annotation for settings dict created in __init__
    settings: dict[str, t.Any] = {}


MODULE_METADATA = AdapterMetadata(
    module_id=UUID("01937d86-4f2a-7b3c-8d9e-f3b4d3c2b1a1"),  # Static UUID7
    name="Loguru Logger",
    category="logger",
    provider="loguru",
    version="1.0.0",
    acb_min_version="0.19.0",
    author="ACB Framework",
    created_date="2025-01-01T00:00:00",
    last_modified="2025-01-01T00:00:00",
    status=AdapterStatus.STABLE,
    capabilities=[
        AdapterCapability.ASYNC_LOGGING,
        AdapterCapability.CONTEXTUAL,
        AdapterCapability.ROTATION,
        AdapterCapability.FILE_LOGGING,
        AdapterCapability.CORRELATION_ID,
    ],
    required_packages=["loguru", "aioconsole"],
    description="High-performance async logger with colored output and structured logging support",
    settings_class="LoggerSettings",
)


class Logger(_Logger, LoggerBase):  # type: ignore[misc]
    """Loguru-based logger adapter."""

    def __init__(self) -> None:
        LoggerBase.__init__(self)
        _Logger.__init__(  # type: ignore[no-untyped-call]
            self,
            core=_Core(),  # type: ignore[no-untyped-call]
            exception=None,
            depth=0,
            record=False,
            lazy=False,
            colors=False,
            raw=False,
            capture=True,
            patchers=[],
            extra={},
        )
        self._bound_context: dict[str, t.Any] = {}

    @property
    def settings(self) -> LoggerSettings:
        """Get Loguru-specific settings."""
        if self._settings is None:
            self._settings = LoggerSettings()
        return self._settings  # type: ignore[return-value]

    # Private implementation methods
    def _debug(self, msg: str, *args: t.Any, **kwargs: t.Any) -> None:
        """Implementation of debug logging."""
        super().debug(msg, *args, **kwargs)  # type: ignore[no-untyped-call]

    def _info(self, msg: str, *args: t.Any, **kwargs: t.Any) -> None:
        """Implementation of info logging."""
        super().info(msg, *args, **kwargs)  # type: ignore[no-untyped-call]

    def _warning(self, msg: str, *args: t.Any, **kwargs: t.Any) -> None:
        """Implementation of warning logging."""
        super().warning(msg, *args, **kwargs)  # type: ignore[no-untyped-call]

    def _error(self, msg: str, *args: t.Any, **kwargs: t.Any) -> None:
        """Implementation of error logging."""
        super().error(msg, *args, **kwargs)  # type: ignore[no-untyped-call]

    def _critical(self, msg: str, *args: t.Any, **kwargs: t.Any) -> None:
        """Implementation of critical logging."""
        super().critical(msg, *args, **kwargs)  # type: ignore[no-untyped-call]

    def _log_structured(self, level: str, msg: str, **context: t.Any) -> None:
        """Implementation of structured logging."""
        # Merge with bound context
        full_context = self._bound_context | context
        self.bind(**full_context).log(level.upper(), msg)  # type: ignore[no-untyped-call]

    def _bind(self, **context: t.Any) -> "Logger":
        """Implementation of context binding."""
        new_logger: Logger = self.bind(**context)  # type: ignore[no-untyped-call]
        new_logger._bound_context = self._bound_context | context
        return new_logger

    def _with_context(self, **context: t.Any) -> "Logger":
        """Implementation of context creation."""
        return self._bind(**context)

    def _with_correlation_id(self, correlation_id: str) -> "Logger":
        """Implementation of correlation ID creation."""
        return self._bind(correlation_id=correlation_id)

    def _init(self) -> None:
        """Initialize Loguru logger."""
        if self._is_testing_mode():
            self._configure_for_testing()
            return

        self._configure_logger()
        self._setup_level_colors()
        self._log_debug_levels()
        self._log_app_info()

    @staticmethod
    async def async_sink(message: str) -> None:
        """Async sink for Loguru messages."""
        try:
            # Check if event loop is running before attempting async operation
            loop = asyncio.get_running_loop()
            if loop and not loop.is_closed():
                await aprint(message, end="")
        except RuntimeError:
            # Event loop is not available or closed, fall back to sync print
            pass

    def _configure_for_testing(self) -> None:
        """Configure logger for testing environment."""
        self.remove()  # type: ignore[no-untyped-call]
        self.configure(handlers=[])  # type: ignore[no-untyped-call]

    def _configure_logger(self) -> None:
        """Configure the main logger."""
        self.remove()  # type: ignore[no-untyped-call]

        def _patch(record: dict[str, t.Any]) -> None:
            """Ensure required extra fields exist for configured formats."""
            record["extra"].setdefault("timestamp", record["time"].isoformat())
            record["extra"]["mod_name"] = self._patch_name(record)

        self.configure(  # type: ignore[no-untyped-call]
            patcher=_patch,
        )

        # Set log level based on environment
        self.config.logger.log_level = (
            self.settings.deployed_level.upper()
            if self.config.deployed
            or (self.config.debug and self.config.debug.production)
            else self.settings.log_level
        )

        # Configure per-module levels
        # Lazy import to avoid circular dependency
        from acb.config import debug

        self.config.logger.level_per_module = {
            m: "DEBUG" if v else self.config.logger.log_level for m, v in debug.items()
        }

        # Use new sink management system
        self._configure_sinks()

    def _patch_name(self, record: dict[str, t.Any]) -> str:
        """Extract and clean module name from log record."""
        return self._extract_module_name(record)

    def _filter_by_module(self, record: dict[str, t.Any]) -> bool:
        """Filter log records by module-specific levels."""
        try:
            name = record["name"].split(".")[-2]
        except IndexError:
            name = record["name"]

        return self._should_log_level(record["level"].name, name)

    def _add_primary_sink(self) -> None:
        """Add the primary stdout sink (human-readable)."""
        try:
            # Check if we can use asyncio before adding the async sink
            is_async_available = True
            try:
                loop = asyncio.get_running_loop()
                is_async_available = bool(loop and not loop.is_closed())
            except RuntimeError:
                # No event loop running
                is_async_available = False

            # Use async sink if available, otherwise use sync
            sink_func = self.async_sink if is_async_available else self._sync_print_sink

            sink_id = self.add(  # type: ignore[no-untyped-call]
                sink_func,
                filter=t.cast("t.Any", self._filter_by_module),
                **self.settings.settings,
            )
            self._active_sinks.append(sink_id)
        except ValueError as e:
            if "event loop is required" in str(e):
                self._add_sync_sink()
            else:
                raise

    def _sync_print_sink(self, message: str) -> None:
        """Synchronous sink for Loguru messages."""

    def _cleanup(self) -> None:
        """Clean up logger resources before shutdown."""
        # Remove all handlers to prevent issues during shutdown
        try:
            self.remove()  # type: ignore[no-untyped-call]
        except Exception:
            pass  # Already removed or other error, ignore

    def _add_sync_sink(self) -> None:
        """Add synchronous sink as fallback."""
        settings = {k: v for k, v in self.settings.settings.items() if k != "enqueue"}
        self.add(  # type: ignore[no-untyped-call]
            lambda msg: print(msg, end=""),
            filter=t.cast("t.Any", self._filter_by_module),
            **settings,
        )

    def _add_stderr_sink(self) -> None:
        """Add stderr sink for structured JSON logging (AI/machine consumption)."""
        import json
        import sys

        from datetime import datetime
        from loguru._handler import Message  # type: ignore[attr-defined]

        def json_formatter(record: dict[str, t.Any]) -> str:
            """Format log record as JSON for AI consumption."""
            event = {
                "timestamp": datetime.now(UTC).isoformat(),
                "level": record["level"].name,
                "event": f"{record['extra'].get('mod_name', 'unknown')}.{record['function']}",
                "message": record["message"],
                "attributes": {
                    "line": record["line"],
                    "module": record["name"],
                    **record["extra"],
                },
                "version": "1.0.0",
            }

            # Add OpenTelemetry trace context if enabled (Phase 2)
            if self.settings.enable_otel:
                with suppress(ImportError):
                    from opentelemetry.trace import get_current_span

                    span = get_current_span()
                    if span.is_recording():
                        ctx = span.get_span_context()
                        event["trace_id"] = format(ctx.trace_id, "032x")
                        event["span_id"] = format(ctx.span_id, "016x")

            return json.dumps(event) + "\n"

        def stderr_sink(message: Message) -> None:
            """Write structured JSON directly to stderr."""
            sys.stderr.write(json_formatter(message.record))

        sink_id = self.add(  # type: ignore[no-untyped-call]
            stderr_sink,
            level=self.settings.stderr_level,
            colorize=False,
            serialize=False,
        )
        self._active_sinks.append(sink_id)

    def _setup_level_colors(self) -> None:
        """Configure level-specific colors."""
        # Type narrowing: ensure level_colors is not None
        if self.settings.level_colors is not None:
            for level, color in self.settings.level_colors.items():
                self.level(level.upper(), color=f"[{color}]")  # type: ignore[no-untyped-call]

    def _log_debug_levels(self) -> None:
        """Log test messages for all levels if debug enabled."""
        if self.config.debug and self.config.debug.logger:
            self.debug("debug")  # type: ignore[no-untyped-call]
            self.info("info")  # type: ignore[no-untyped-call]
            self.warning("warning")  # type: ignore[no-untyped-call]
            self.error("error")  # type: ignore[no-untyped-call]
            self.critical("critical")  # type: ignore[no-untyped-call]

    def _log_app_info(self) -> None:
        """Log application startup information."""
        self.info(f"App path: {self.config.root_path}")  # type: ignore[no-untyped-call]
        self.info(f"App deployed: {self.config.deployed}")  # type: ignore[no-untyped-call]


depends.set(Logger, "loguru")  # Register identifier for proper initialization


class InterceptHandler(logging.Handler):
    """Handler to intercept standard library logging and route to Loguru."""

    def emit(self, record: logging.LogRecord) -> None:
        """Emit log record via Loguru."""
        # Get logger from dependency container
        try:
            logger_instance = depends.get_sync(Logger)
        except Exception:
            # Fallback to basic logging if logger not available
            return

        if not hasattr(logger_instance, "opt"):  # Logger not initialized yet
            return

        try:
            level = logger_instance.level(record.levelname).name  # type: ignore[no-untyped-call]
        except (ValueError, AttributeError):
            level = record.levelno

        frame, depth = (currentframe(), 0)
        while frame and (depth == 0 or frame.f_code.co_filename == logging.__file__):
            frame = frame.f_back
            depth += 1

        logger_instance.opt(depth=depth, exception=record.exc_info).log(  # type: ignore[no-untyped-call]
            level,
            record.getMessage(),
        )


# Configure stdlib logging interception
# Deferred initialization to avoid import-time side effects
def configure_stdlib_logging_interception() -> None:
    """Configure standard library logging to route through Loguru."""
    logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)


# Note: Call configure_stdlib_logging_interception() after app initialization
# to enable standard library logging interception


# Backward compatibility alias for tests
LoguruSettings = LoggerSettings
