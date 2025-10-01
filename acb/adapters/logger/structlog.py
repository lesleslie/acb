"""Structlog-based logger adapter implementation with full structured logging."""

import logging
import sys
import typing as t
from uuid import UUID

try:
    import structlog
except ImportError:
    structlog = None  # type: ignore[assignment]

from acb.adapters import AdapterCapability, AdapterMetadata, AdapterStatus

from ._base import LoggerBase, LoggerBaseSettings


class StructlogSettings(LoggerBaseSettings):
    """Structlog-specific logger settings."""

    # Structlog-specific configuration
    json_output: bool = True
    include_metadata: bool = True
    include_caller_info: bool = True
    pretty_print: bool = False

    # Processor configuration
    add_log_level: bool = True
    add_timestamp: bool = True
    timestamp_format: str = "ISO"
    add_logger_name: bool = True

    # Context configuration
    context_vars: bool = True
    correlation_id_header: str = "X-Correlation-ID"

    # Development vs production settings
    dev_renderer: str = "console"  # "console" or "json"
    prod_renderer: str = "json"

    def __init__(self, **values: t.Any) -> None:
        super().__init__(**values)
        self.settings = self._build_structlog_settings()

    def _build_structlog_settings(self) -> dict[str, t.Any]:
        """Build structlog-specific settings."""
        return {
            "processors": self._build_processors(),
            "wrapper_class": structlog.stdlib.BoundLogger if structlog else object,
            "context_class": dict,
            "logger_factory": structlog.stdlib.LoggerFactory() if structlog else object,
            "cache_logger_on_first_use": True,
        }

    def _build_processors(self) -> list[t.Any]:
        """Build the processor chain for structlog."""
        if not structlog:
            return []

        processors: list[t.Any] = []

        # Add timestamp
        if self.add_timestamp:
            processors.extend(
                (structlog.stdlib.add_log_level, structlog.stdlib.add_logger_name),
            )
            processors.append(structlog.processors.TimeStamper(fmt="ISO"))

        # Add context processors
        if self.context_vars:
            processors.append(structlog.contextvars.merge_contextvars)

        # Add caller info
        if self.include_caller_info:
            processors.append(
                structlog.processors.CallsiteParameterAdder(
                    parameters=[
                        structlog.processors.CallsiteParameter.FILENAME,
                        structlog.processors.CallsiteParameter.FUNC_NAME,
                        structlog.processors.CallsiteParameter.LINENO,
                    ],
                ),
            )

        # Add development/production specific processors
        if self.json_output or self.prod_renderer == "json":
            processors.extend(
                [
                    structlog.stdlib.PositionalArgumentsFormatter(),
                    structlog.processors.StackInfoRenderer(),
                    structlog.processors.format_exc_info,
                    structlog.processors.UnicodeDecoder(),
                    structlog.processors.JSONRenderer(),
                ],
            )
        else:
            processors.extend(
                [
                    structlog.stdlib.PositionalArgumentsFormatter(),
                    structlog.processors.StackInfoRenderer(),
                    structlog.processors.format_exc_info,
                    structlog.dev.ConsoleRenderer()
                    if self.pretty_print
                    else structlog.processors.JSONRenderer(),
                ],
            )

        return processors


MODULE_METADATA = AdapterMetadata(
    module_id=UUID("01937d86-4f2a-7b3c-8d9e-f3b4d3c2b1a2"),  # Static UUID7
    name="Structlog Logger",
    category="logger",
    provider="structlog",
    version="1.0.0",
    acb_min_version="0.19.0",
    author="ACB Framework",
    created_date="2025-01-01T00:00:00",
    last_modified="2025-01-01T00:00:00",
    status=AdapterStatus.STABLE,
    capabilities=[
        AdapterCapability.STRUCTURED_OUTPUT,
        AdapterCapability.ASYNC_LOGGING,
        AdapterCapability.CONTEXTUAL,
        AdapterCapability.JSON_OUTPUT,
        AdapterCapability.FILE_LOGGING,
        AdapterCapability.CORRELATION_ID,
        AdapterCapability.REMOTE_LOGGING,
    ],
    required_packages=["structlog"],
    description="Advanced structured logging with JSON output and comprehensive context management",
    settings_class="StructlogSettings",
)


class Logger(LoggerBase):
    """Structlog-based logger adapter with full structured logging support."""

    def __init__(self) -> None:
        super().__init__()
        self._logger: t.Any = None
        self._bound_context: dict[str, t.Any] = {}

        if not structlog:
            msg = (
                "structlog is required for StructlogLogger. "
                "Install with: pip install structlog"
            )
            raise ImportError(
                msg,
            )

    @property
    def settings(self) -> StructlogSettings:
        """Get structlog-specific settings."""
        if self._settings is None:
            self._settings = StructlogSettings()
        return self._settings  # type: ignore[return-value]

    def _ensure_logger(self) -> t.Any:
        """Ensure logger is initialized."""
        if self._logger is None:
            self._logger = self._create_logger()
        return self._logger

    def _create_logger(self) -> t.Any:
        """Create structlog logger instance."""
        return structlog.get_logger(self.__class__.__module__)

    # Private implementation methods
    def _debug(self, msg: str, *args: t.Any, **kwargs: t.Any) -> None:
        """Implementation of debug logging."""
        logger = self._ensure_logger()
        self._log_with_context(logger.debug, msg, *args, **kwargs)

    def _info(self, msg: str, *args: t.Any, **kwargs: t.Any) -> None:
        """Implementation of info logging."""
        logger = self._ensure_logger()
        self._log_with_context(logger.info, msg, *args, **kwargs)

    def _warning(self, msg: str, *args: t.Any, **kwargs: t.Any) -> None:
        """Implementation of warning logging."""
        logger = self._ensure_logger()
        self._log_with_context(logger.warning, msg, *args, **kwargs)

    def _error(self, msg: str, *args: t.Any, **kwargs: t.Any) -> None:
        """Implementation of error logging."""
        logger = self._ensure_logger()
        self._log_with_context(logger.error, msg, *args, **kwargs)

    def _critical(self, msg: str, *args: t.Any, **kwargs: t.Any) -> None:
        """Implementation of critical logging."""
        logger = self._ensure_logger()
        self._log_with_context(logger.critical, msg, *args, **kwargs)

    def _log_structured(self, level: str, msg: str, **context: t.Any) -> None:
        """Implementation of structured logging."""
        logger = self._ensure_logger()

        # Merge with bound context
        full_context = self._bound_context | context

        # Get the appropriate logging method
        log_method = getattr(logger, level.lower(), logger.info)
        log_method(msg, **full_context)

    def _bind(self, **context: t.Any) -> "Logger":
        """Implementation of context binding."""
        new_logger = self.__class__()
        new_logger._logger = self._ensure_logger().bind(**context)
        new_logger._bound_context = self._bound_context | context
        new_logger._settings = self._settings
        new_logger._initialized = self._initialized
        return new_logger

    def _with_context(self, **context: t.Any) -> "Logger":
        """Implementation of context creation."""
        return self._bind(**context)

    def _with_correlation_id(self, correlation_id: str) -> "Logger":
        """Implementation of correlation ID creation."""
        return self._bind(correlation_id=correlation_id)

    def _init(self) -> None:
        """Initialize structlog logger."""
        if self._is_testing_mode():
            self._configure_for_testing()
            return

        self._configure_structlog()
        self._setup_stdlib_integration()
        self._log_app_info()

    def _log_with_context(
        self,
        log_method: t.Callable[..., t.Any],
        msg: str,
        *args: t.Any,
        **kwargs: t.Any,
    ) -> None:
        """Log message with merged context."""
        # Extract additional context from kwargs
        context = kwargs.pop("extra", {})
        context.update(self._bound_context)

        # Add module information
        frame = sys._getframe(3)  # Go up the stack to find the actual caller
        context.update(
            {
                "module": frame.f_globals.get("__name__", "unknown"),
                "function": frame.f_code.co_name,
                "line": frame.f_lineno,
            },
        )

        # Format message with args if provided
        if args:
            try:
                formatted_msg = msg % args
            except (TypeError, ValueError):
                formatted_msg = msg
                context["log_args"] = args
        else:
            formatted_msg = msg

        # Log with context
        log_method(formatted_msg, **context, **kwargs)

    def _configure_for_testing(self) -> None:
        """Configure logger for testing environment."""
        # Use simple configuration for tests
        if structlog:
            structlog.configure(
                processors=[
                    structlog.stdlib.add_log_level,
                    structlog.testing.LogCapture(),
                ],
                wrapper_class=structlog.stdlib.BoundLogger,
                logger_factory=structlog.stdlib.LoggerFactory(),
                cache_logger_on_first_use=True,
            )

    def _configure_structlog(self) -> None:
        """Configure structlog with full processors."""
        if not structlog:
            return

        structlog.configure(**self.settings.settings)

        # Configure context variables if enabled
        if self.settings.context_vars:
            structlog.contextvars.clear_contextvars()

    def _setup_stdlib_integration(self) -> None:
        """Set up integration with Python standard library logging."""
        if not structlog:
            return

        # Configure stdlib logging to use structlog
        logging.basicConfig(
            format="%(message)s",
            stream=sys.stdout,
            level=getattr(logging, self._get_effective_level()),
        )

        # Wrap existing loggers
        structlog.stdlib.recreate_defaults(
            log_level=getattr(logging, self._get_effective_level()),
        )

    def _log_app_info(self) -> None:
        """Log application startup information."""
        logger = self._ensure_logger()
        logger.info(
            "Application started",
            app_path=str(self.config.root_path),
            deployed=self.config.deployed,
            logger_type="structlog",
        )

    # Additional structured logging methods specific to structlog
    def log_event(self, event: str, **context: t.Any) -> None:
        """Log a structured event with context."""
        logger = self._ensure_logger()
        logger.info(f"Event: {event}", event_type=event, **context)

    def log_metric(self, metric_name: str, value: float, **tags: t.Any) -> None:
        """Log a metric with tags."""
        logger = self._ensure_logger()
        logger.info(
            f"Metric: {metric_name}",
            metric_name=metric_name,
            metric_value=value,
            **tags,
        )

    def log_performance(
        self,
        operation: str,
        duration_ms: float,
        **context: t.Any,
    ) -> None:
        """Log performance metrics."""
        logger = self._ensure_logger()
        logger.info(
            f"Performance: {operation}",
            operation=operation,
            duration_ms=duration_ms,
            performance_log=True,
            **context,
        )

    def log_error_with_context(self, error: Exception, **context: t.Any) -> None:
        """Log error with full context and stack trace."""
        logger = self._ensure_logger()
        logger.error(
            f"Error: {type(error).__name__}",
            error_type=type(error).__name__,
            error_message=str(error),
            exception=error,
            **context,
        )
