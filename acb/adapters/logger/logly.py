"""Logly-based logger adapter implementation with Rust-powered performance."""

import logging
from inspect import currentframe
from uuid import UUID

import typing as t
from contextlib import suppress

logly_logger: t.Any = None
with suppress(ImportError):
    from logly import logger as _real_logly_logger  # type: ignore[import-not-found]

    logly_logger = _real_logly_logger

from datetime import UTC

from acb.adapters import AdapterCapability, AdapterMetadata, AdapterStatus
from acb.depends import depends

from ._base import LoggerBase, LoggerBaseSettings


class LoggerSettings(LoggerBaseSettings):
    """Logly-specific logger settings with Rust backend optimization."""

    # Logly-specific format strings (similar to Loguru)
    format: dict[str, str] | None = {
        "time": "<b><e>[</e> <w>{time:YYYY-MM-DD HH:mm:ss.SSS}</w> <e>]</e></b>",
        "level": " <level>{level:>8}</level>",
        "sep": " <b><w>in</w></b> ",
        "name": "<b>{extra[mod_name]:>20}</b>",
        "line": "<b><e>[</e><w>{line:^5}</w><e>]</e></b>",
        "message": "  <level>{message}</level>",
    }

    # Rust Backend Optimization
    rust_optimized: bool = True
    thread_safe: bool = True
    lock_free: bool = True  # Leverage Rust's lock-free operations

    # Compression Settings
    compression: str | None = None  # "gzip", "zstd", or None
    compression_level: int = 6  # 1-9 for gzip, 1-22 for zstd

    # Advanced Rotation
    rotation_policy: str = "size"  # "size", "time", or "both"
    rotation_size: str = "10 MB"  # Size-based rotation
    rotation_time: str = "1 day"  # Time-based rotation

    # Logly-specific Format Options
    pretty_print: bool = False  # Enhanced pretty printing
    include_process_id: bool = False
    include_thread_id: bool = False

    # Callback Configuration
    enable_callbacks: bool = False
    callback_async: bool = True
    callback_on_levels: list[str] | None = None  # ["ERROR", "CRITICAL"]

    # Performance Tuning
    buffer_size: int = 8192  # Rust backend buffer size
    flush_interval: float = 1.0  # Auto-flush interval in seconds

    # Exception Handling
    catch_exceptions: bool = False  # Auto-catch decorator support
    diagnose_errors: bool = False  # Enhanced error diagnosis

    # Logly specific settings
    backtrace: bool = False
    catch: bool = False
    diagnose: bool = False
    colorize: bool = True

    # Type annotation for settings dict created in __init__
    settings: dict[str, t.Any] = {}

    def __init__(self, **values: t.Any) -> None:
        super().__init__(**values)
        self.settings = self._build_logly_settings()

    def _build_logly_settings(self) -> dict[str, t.Any]:
        """Build Logly-specific settings dict."""
        return {
            "format": "".join(self.format.values() if self.format else []),
            "enqueue": self.async_logging,
            "backtrace": self.backtrace,
            "catch": self.catch_exceptions,
            "serialize": self.serialize,
            "diagnose": self.diagnose_errors,
            "colorize": self.colorize and not self.json_output,
            "compression": self.compression,
            "compression_level": self.compression_level,
        }


MODULE_METADATA = AdapterMetadata(
    module_id=UUID("01940000-0000-7000-8000-000000000001"),  # Static UUID7
    name="Logly Logger",
    category="logger",
    provider="logly",
    version="1.0.0",
    acb_min_version="0.19.0",
    author="ACB Framework",
    created_date="2025-01-04T00:00:00",
    last_modified="2025-01-04T00:00:00",
    status=AdapterStatus.STABLE,
    capabilities=[
        # Standard logger capabilities
        AdapterCapability.ASYNC_LOGGING,
        AdapterCapability.CONTEXTUAL,
        AdapterCapability.ROTATION,
        AdapterCapability.FILE_LOGGING,
        AdapterCapability.CORRELATION_ID,
        AdapterCapability.STRUCTURED_OUTPUT,
        AdapterCapability.JSON_OUTPUT,
        # Logly-specific capabilities
        AdapterCapability.COMPRESSION,  # gzip, zstd compression
    ],
    required_packages=["logly>=0.1.0"],
    optional_packages={
        "zstd": "zstandard>=0.21.0",  # For zstd compression
    },
    description="Rust-powered high-performance logger with advanced rotation, compression, and async callbacks",
    settings_class="LoggerSettings",
)


class Logger(LoggerBase):
    """Logly-based logger adapter with Rust-powered performance."""

    def __init__(self) -> None:
        LoggerBase.__init__(self)
        self._logger: t.Any = None
        self._bound_context: dict[str, t.Any] = {}
        self._callbacks: list[t.Callable[..., t.Any]] = []
        self._sinks: list[t.Any] = []

        if not logly_logger:
            msg = "logly is required for LoglyLogger. Install with: pip install logly"
            raise ImportError(msg)

    @property
    def settings(self) -> LoggerSettings:
        """Get Logly-specific settings."""
        if self._settings is None:
            self._settings = LoggerSettings()
        return self._settings  # type: ignore[return-value]

    def _ensure_logger(self) -> t.Any:
        """Ensure logger is initialized (lazy initialization)."""
        if self._logger is None:
            self._logger = self._create_logger()
        return self._logger

    def _create_logger(self) -> t.Any:
        """Create Logly logger instance."""
        # Use the global logly logger instance
        return logly_logger

    # Private implementation methods for LoggerBase abstract methods
    def _debug(self, msg: str, *args: t.Any, **kwargs: t.Any) -> None:
        """Implementation of debug logging."""
        logger = self._ensure_logger()
        logger.debug(msg, *args, **kwargs)

    def _info(self, msg: str, *args: t.Any, **kwargs: t.Any) -> None:
        """Implementation of info logging."""
        logger = self._ensure_logger()
        logger.info(msg, *args, **kwargs)

    def _warning(self, msg: str, *args: t.Any, **kwargs: t.Any) -> None:
        """Implementation of warning logging."""
        logger = self._ensure_logger()
        logger.warning(msg, *args, **kwargs)

    def _error(self, msg: str, *args: t.Any, **kwargs: t.Any) -> None:
        """Implementation of error logging."""
        logger = self._ensure_logger()
        logger.error(msg, *args, **kwargs)

    def _critical(self, msg: str, *args: t.Any, **kwargs: t.Any) -> None:
        """Implementation of critical logging."""
        logger = self._ensure_logger()
        logger.critical(msg, *args, **kwargs)

    def _log_structured(self, level: str, msg: str, **context: t.Any) -> None:
        """Implementation of structured logging."""
        logger = self._ensure_logger()
        # Merge with bound context
        full_context = self._bound_context | context
        logger.bind(**full_context).log(level.upper(), msg)

    def _bind(self, **context: t.Any) -> "Logger":
        """Implementation of context binding."""
        new_logger = self.__class__()
        logger = self._ensure_logger()
        new_logger._logger = logger.bind(**context)
        new_logger._bound_context = self._bound_context | context
        new_logger._settings = self._settings
        new_logger._initialized = self._initialized
        new_logger._callbacks = self._callbacks
        new_logger._sinks = self._sinks
        return new_logger

    def _with_context(self, **context: t.Any) -> "Logger":
        """Implementation of context creation."""
        return self._bind(**context)

    def _with_correlation_id(self, correlation_id: str) -> "Logger":
        """Implementation of correlation ID creation."""
        return self._bind(correlation_id=correlation_id)

    def _init(self) -> None:
        """Initialize Logly logger."""
        if self._is_testing_mode():
            self._configure_for_testing()
            return

        self._configure_logger()
        self._setup_sinks()
        self._setup_callbacks()
        self._log_app_info()

    def _configure_for_testing(self) -> None:
        """Configure logger for testing environment."""
        logger = self._ensure_logger()
        logger.remove()
        logger.configure(handlers=[])

    def _configure_logger(self) -> None:
        """Configure the main logger."""
        logger = self._ensure_logger()
        logger.remove()

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

    def _setup_sinks(self) -> None:
        """Set up logging sinks (console, file, etc.)."""
        # Use new sink management system
        self._configure_sinks()

    def _add_primary_sink(self) -> None:
        """Add primary stdout sink (human-readable)."""
        logger = self._ensure_logger()
        sink_config = self.settings.settings.copy()

        # Add file sink if configured
        if self.settings.log_file_path:
            sink_id = logger.add(
                self.settings.log_file_path,
                rotation=self.settings.log_file_rotation,
                retention=self.settings.log_file_retention,
                compression=self.settings.compression,
                **sink_config,
            )
            self._active_sinks.append(sink_id)
        else:
            # Add console sink
            try:
                sink_id = logger.add(
                    lambda msg: print(msg, end=""),
                    **sink_config,
                )
                self._active_sinks.append(sink_id)
            except Exception as e:
                # Fallback to simple print if configuration fails
                print(f"Warning: Failed to configure Logly sink: {e}")

    def _add_stderr_sink(self) -> None:
        """Add stderr sink for structured JSON logging (AI/machine consumption)."""
        import json
        import sys

        from datetime import datetime

        logger = self._ensure_logger()

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

        sink_id = logger.add(
            sys.stderr,
            format=json_formatter,
            level=self.settings.stderr_level,
            colorize=False,
            serialize=False,
        )
        self._active_sinks.append(sink_id)

    def _setup_callbacks(self) -> None:
        """Set up async callbacks if enabled."""
        if not self.settings.enable_callbacks:
            return

        logger = self._ensure_logger()
        for callback in self._callbacks:
            with suppress(AttributeError):
                # Logly might not support callbacks yet
                logger.add_callback(callback)

    def _log_app_info(self) -> None:
        """Log application startup information."""
        logger = self._ensure_logger()
        logger.info(f"App path: {self.config.root_path}")
        logger.info(f"App deployed: {self.config.deployed}")

    # Logly-specific extension methods
    def add_callback(self, callback: t.Callable[..., t.Any]) -> None:
        """Register async callback for log processing.

        Args:
            callback: Async function to call for each log record
        """
        self._callbacks.append(callback)
        logger = self._ensure_logger()
        with suppress(AttributeError):
            # Logly might not support callbacks in this version
            logger.add_callback(callback)

    def remove_callback(self, callback: t.Callable[..., t.Any]) -> None:
        """Unregister callback.

        Args:
            callback: Previously registered callback to remove
        """
        if callback in self._callbacks:
            self._callbacks.remove(callback)
            logger = self._ensure_logger()
            with suppress(AttributeError):
                logger.remove_callback(callback)

    def contextualize(self, **context: t.Any) -> t.Any:
        """Context manager for temporary context.

        Args:
            **context: Context key-value pairs

        Returns:
            Context manager that applies context temporarily

        Example:
            with logger.contextualize(request_id="123"):
                logger.info("Processing request")
        """
        logger = self._ensure_logger()
        try:
            return logger.contextualize(**context)
        except AttributeError:
            # Fallback: use regular bind if contextualize not available
            return self._bind(**context)

    def complete(self) -> None:
        """Flush all pending log messages.

        This is useful before program termination to ensure all
        buffered log messages are written.
        """
        logger = self._ensure_logger()
        with suppress(AttributeError):
            logger.complete()
            return
        # If complete() not available, try flush()
        with suppress(AttributeError):
            logger.flush()

    def trace(self, msg: str, *args: t.Any, **kwargs: t.Any) -> None:
        """Log trace message (below debug level).

        Args:
            msg: Message to log
            *args: Positional arguments for message formatting
            **kwargs: Additional keyword arguments
        """
        logger = self._ensure_logger()
        try:
            logger.trace(msg, *args, **kwargs)
        except AttributeError:
            # Fallback to debug if trace not available
            logger.debug(f"[TRACE] {msg}", *args, **kwargs)

    def success(self, msg: str, *args: t.Any, **kwargs: t.Any) -> None:
        """Log success message (between info and warning).

        Args:
            msg: Message to log
            *args: Positional arguments for message formatting
            **kwargs: Additional keyword arguments
        """
        logger = self._ensure_logger()
        try:
            logger.success(msg, *args, **kwargs)
        except AttributeError:
            # Fallback to info if success not available
            logger.info(f"✓ {msg}", *args, **kwargs)

    async def _cleanup_resources(self) -> None:
        """Clean up logger resources."""
        # Flush any pending logs
        self.complete()
        # Call parent cleanup
        await super().cleanup()


depends.set(Logger, "logly")


class InterceptHandler(logging.Handler):
    """Handler to intercept standard library logging and route to Logly."""

    def emit(self, record: logging.LogRecord) -> None:
        """Emit log record via Logly."""
        # Get logger from dependency container
        try:
            logger_instance = depends.get_sync(Logger)
        except Exception:
            # Fallback to basic logging if logger not available
            return

        try:
            level = record.levelname
        except (ValueError, AttributeError):
            level = "INFO"

        frame, depth = (currentframe(), 0)
        while frame and (depth == 0 or frame.f_code.co_filename == logging.__file__):
            frame = frame.f_back
            depth += 1

        logger_instance.log(level, record.getMessage())


# Configure stdlib logging interception
# Deferred initialization to avoid import-time side effects
def configure_stdlib_logging_interception() -> None:
    """Configure standard library logging to route through Logly."""
    logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)


# Note: Call configure_stdlib_logging_interception() after app initialization
# to enable standard library logging interception

# Backward compatibility alias for tests
LoglySettings = LoggerSettings
