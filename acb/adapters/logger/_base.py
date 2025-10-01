"""Base logger adapter interface following ACB's adapter pattern."""

import typing as t
from abc import abstractmethod

from pydantic import SecretStr
from acb.cleanup import CleanupMixin
from acb.config import Config, Settings
from acb.depends import Inject


class LoggerBaseSettings(Settings):
    """Base settings for all logger adapters."""

    # Basic logging configuration
    verbose: bool = False
    deployed_level: str = "WARNING"
    log_level: str | None = "INFO"
    serialize: bool | None = False

    # Output format configuration
    format: dict[str, str] | None = {
        "time": "<b><e>[</e> <w>{time:YYYY-MM-DD HH:mm:ss.SSS}</w> <e>]</e></b>",
        "level": " <level>{level:>8}</level>",
        "sep": " <b><w>in</w></b> ",
        "name": "<b>{extra[mod_name]:>20}</b>",
        "line": "<b><e>[</e><w>{line:^5}</w><e>]</e></b>",
        "message": "  <level>{message}</level>",
    }

    # Module-specific logging levels
    level_per_module: dict[str, str | None] | None = {}
    level_colors: dict[str, str] | None = {}

    # Structured logging configuration
    json_output: bool = False
    include_metadata: bool = True
    include_caller_info: bool = True

    # File logging configuration
    log_file_path: str | None = None
    log_file_rotation: str | None = "1 day"
    log_file_retention: str | None = "7 days"
    log_file_compression: bool = True

    # Remote logging configuration
    remote_endpoint: SecretStr | None = None
    remote_api_key: SecretStr | None = None
    remote_batch_size: int = 100
    remote_flush_interval: float = 5.0

    # Advanced settings
    async_logging: bool = True
    context_vars: bool = True
    correlation_id_header: str = "X-Correlation-ID"

    def __init__(self, **values: t.Any) -> None:
        super().__init__(**values)
        self.settings = self._build_adapter_settings()

    def _build_adapter_settings(self) -> dict[str, t.Any]:
        """Build adapter-specific settings dict."""
        return {
            "format": "".join(self.format.values() if self.format else []),
            "enqueue": self.async_logging,
            "backtrace": False,
            "catch": False,
            "serialize": self.serialize,
            "diagnose": False,
            "colorize": not self.json_output,
        }


@t.runtime_checkable
class LoggerProtocol(t.Protocol):
    """Protocol defining the logger interface."""

    def debug(self, msg: str, *args: t.Any, **kwargs: t.Any) -> None: ...
    def info(self, msg: str, *args: t.Any, **kwargs: t.Any) -> None: ...
    def warning(self, msg: str, *args: t.Any, **kwargs: t.Any) -> None: ...
    def error(self, msg: str, *args: t.Any, **kwargs: t.Any) -> None: ...
    def critical(self, msg: str, *args: t.Any, **kwargs: t.Any) -> None: ...

    # Structured logging methods
    def log_structured(self, level: str, msg: str, **context: t.Any) -> None: ...
    def bind(self, **context: t.Any) -> "LoggerProtocol": ...

    # Context management
    def with_context(self, **context: t.Any) -> "LoggerProtocol": ...
    def with_correlation_id(self, correlation_id: str) -> "LoggerProtocol": ...

    # Initialization
    def init(self) -> None: ...


class LoggerBase(CleanupMixin):
    """Base class for all logger adapters."""

    config: Inject[Config]

    def __init__(self, **kwargs: t.Any) -> None:
        super().__init__()
        self._settings: LoggerBaseSettings | None = None
        self._initialized = False
        self._context: dict[str, t.Any] = {}

    @property
    def settings(self) -> LoggerBaseSettings:
        """Get adapter settings."""
        if self._settings is None:
            self._settings = LoggerBaseSettings()
        return self._settings

    # Public methods that delegate to private implementations
    def debug(self, msg: str, *args: t.Any, **kwargs: t.Any) -> None:
        """Log debug message."""
        return self._debug(msg, *args, **kwargs)

    def info(self, msg: str, *args: t.Any, **kwargs: t.Any) -> None:
        """Log info message."""
        return self._info(msg, *args, **kwargs)

    def warning(self, msg: str, *args: t.Any, **kwargs: t.Any) -> None:
        """Log warning message."""
        return self._warning(msg, *args, **kwargs)

    def error(self, msg: str, *args: t.Any, **kwargs: t.Any) -> None:
        """Log error message."""
        return self._error(msg, *args, **kwargs)

    def critical(self, msg: str, *args: t.Any, **kwargs: t.Any) -> None:
        """Log critical message."""
        return self._critical(msg, *args, **kwargs)

    def log_structured(self, level: str, msg: str, **context: t.Any) -> None:
        """Log structured message with context."""
        return self._log_structured(level, msg, **context)

    def bind(self, **context: t.Any) -> "LoggerBase":
        """Bind context to logger."""
        return self._bind(**context)

    def with_context(self, **context: t.Any) -> "LoggerBase":
        """Create logger with additional context."""
        return self._with_context(**context)

    def with_correlation_id(self, correlation_id: str) -> "LoggerBase":
        """Create logger with correlation ID."""
        return self._with_correlation_id(correlation_id)

    def init(self) -> None:
        """Initialize the logger adapter."""
        if self._initialized:
            return
        self._init()
        self._initialized = True

    # Abstract methods that must be implemented by subclasses
    @abstractmethod
    def _debug(self, msg: str, *args: t.Any, **kwargs: t.Any) -> None:
        """Implementation of debug logging."""
        ...

    @abstractmethod
    def _info(self, msg: str, *args: t.Any, **kwargs: t.Any) -> None:
        """Implementation of info logging."""
        ...

    @abstractmethod
    def _warning(self, msg: str, *args: t.Any, **kwargs: t.Any) -> None:
        """Implementation of warning logging."""
        ...

    @abstractmethod
    def _error(self, msg: str, *args: t.Any, **kwargs: t.Any) -> None:
        """Implementation of error logging."""
        ...

    @abstractmethod
    def _critical(self, msg: str, *args: t.Any, **kwargs: t.Any) -> None:
        """Implementation of critical logging."""
        ...

    @abstractmethod
    def _log_structured(self, level: str, msg: str, **context: t.Any) -> None:
        """Implementation of structured logging."""
        ...

    @abstractmethod
    def _bind(self, **context: t.Any) -> "LoggerBase":
        """Implementation of context binding."""
        ...

    @abstractmethod
    def _with_context(self, **context: t.Any) -> "LoggerBase":
        """Implementation of context creation."""
        ...

    @abstractmethod
    def _with_correlation_id(self, correlation_id: str) -> "LoggerBase":
        """Implementation of correlation ID creation."""
        ...

    @abstractmethod
    def _init(self) -> None:
        """Implementation-specific initialization."""
        ...

    # Utility methods
    def _is_testing_mode(self) -> bool:
        """Check if running in testing mode."""
        import os
        import sys

        return (
            "pytest" in sys.modules or os.getenv("TESTING", "False").lower() == "true"
        )

    def _get_effective_level(self) -> str:
        """Get the effective logging level."""
        if self.config.deployed or (self.config.debug and self.config.debug.production):
            return self.settings.deployed_level.upper()
        return self.settings.log_level or "INFO"

    def _extract_module_name(self, record: dict[str, t.Any]) -> str:
        """Extract module name from log record."""
        mod_parts = record.get("name", "").split(".")
        mod_name = ".".join(mod_parts[:-1])
        if len(mod_parts) > 3:
            mod_name = ".".join(mod_parts[1:-1])
        return mod_name.replace("_sdk", "")

    def _should_log_level(self, level: str, module_name: str) -> bool:
        """Check if message should be logged based on level and module."""
        # Type narrowing: ensure level_per_module is not None
        if self.settings.level_per_module is None:
            target_level: str | None = self._get_effective_level()
        else:
            target_level = self.settings.level_per_module.get(
                module_name,
                self._get_effective_level(),
            )
        # Check if logging is disabled for this module (None or False)
        if target_level is None:
            return False
        # Type narrowing: target_level is str | None at this point, check for False-like values
        if not target_level or (
            isinstance(target_level, str) and target_level.upper() == "FALSE"
        ):
            return False

        # Basic level comparison (could be enhanced with actual level objects)
        level_hierarchy = {
            "DEBUG": 0,
            "INFO": 1,
            "WARNING": 2,
            "ERROR": 3,
            "CRITICAL": 4,
        }
        current_level_no = level_hierarchy.get(level.upper(), 0)
        target_level_no = level_hierarchy.get(str(target_level).upper(), 1)
        return current_level_no >= target_level_no

    async def _cleanup_resources(self) -> None:
        """Clean up logger resources."""
        # Implementation-specific cleanup should be handled by subclasses
        await super().cleanup()
