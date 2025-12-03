"""Base service class for ACB services layer.

This module provides the foundation for ACB's services architecture,
following the comprehensive architecture patterns introduced in v0.20.0+.
"""

import logging
from abc import ABC
from enum import Enum

import asyncio
import typing as t
from contextlib import suppress
from dataclasses import dataclass, field
from pydantic import BaseModel, ConfigDict, Field

from acb.cleanup import CleanupMixin
from acb.config import Settings
from acb.depends import depends
from acb.logger import Logger

logger = logging.getLogger(__name__)


class ServiceStatus(Enum):
    """Service lifecycle status."""

    INACTIVE = "inactive"
    INITIALIZING = "initializing"
    ACTIVE = "active"
    ERROR = "error"
    STOPPING = "stopping"
    STOPPED = "stopped"


@dataclass
class ServiceMetrics:
    """Basic service metrics."""

    initialized_at: float | None = None
    requests_handled: int = 0
    errors_count: int = 0
    last_error: str | None = None
    custom_metrics: dict[str, t.Any] = field(default_factory=dict)


class ServiceSettings(Settings):
    """Base settings for services."""

    enabled: bool = True
    timeout: float = 30.0
    retry_attempts: int = 3
    retry_delay: float = 1.0

    # Health check settings
    health_check_enabled: bool = True
    health_check_interval: float = 60.0

    # Events system settings (used by EventsServiceSettings and subclasses)
    # These are default values that can be overridden by child classes
    # Publisher settings
    enable_publisher: bool = True
    event_topic_prefix: str = "events"
    max_concurrent_events: int = 100
    default_max_retries: int = 3
    default_retry_delay: float = 1.0
    max_retry_delay: float = 30.0
    exponential_backoff: bool = True
    log_events: bool = False
    default_timeout: float = 30.0

    # Subscriber settings
    enable_subscriber: bool = True
    max_subscriptions: int = 1000
    default_subscription_mode: t.Any = "push"  # Can be str or SubscriptionMode enum
    subscription_timeout: float = 30.0
    handler_timeout: float = 30.0
    default_mode: t.Any = "push"  # Can be str or SubscriptionMode enum

    # Buffer configuration
    enable_buffering: bool = True
    buffer_size: int = 1000
    buffer_timeout: float = 5.0

    # Batch processing
    enable_batching: bool = False
    batch_size: int = 10

    # Retry configuration (events-specific)
    enable_retries: bool = True
    max_retries: int = 3

    # Alternative naming for health checks (used by some event subsystems)
    enable_health_checks: bool = True

    def __init__(self, config: t.Any = None, **values: t.Any) -> None:
        # For test environments, config may be passed directly or not needed
        # For production, config should ideally still be injected
        super().__init__(**values)


class ServiceConfig(BaseModel):
    """Configuration model for services."""

    model_config = ConfigDict(extra="forbid")

    service_id: str = Field(description="Unique service identifier")
    name: str = Field(description="Human-readable service name")
    version: str = Field(default="1.0.0", description="Service version")
    description: str | None = Field(default=None, description="Service description")
    dependencies: list[str] = Field(
        default_factory=list,
        description="Required service dependencies",
    )
    priority: int = Field(
        default=100,
        description="Service initialization priority (lower = earlier)",
    )


class ServiceBase(ABC, CleanupMixin):
    """Base class for ACB services.

    Provides standardized patterns for service lifecycle management,
    dependency injection, configuration, and resource cleanup.
    """

    def __init__(
        self,
        service_config: ServiceConfig | None = None,
        settings: ServiceSettings | None = None,
    ) -> None:
        super().__init__()
        CleanupMixin.__init__(self)

        self._service_config = service_config or ServiceConfig(
            service_id=self.__class__.__name__.lower(),
            name=self.__class__.__name__,
        )
        self._settings = settings or ServiceSettings()
        self._status = ServiceStatus.INACTIVE
        self._metrics = ServiceMetrics()
        self._health_check_task: asyncio.Task[t.Any] | None = None
        self._initialization_lock = asyncio.Lock()
        self._shutdown_event = asyncio.Event()

        # Service-specific state
        self._initialized = False
        self._start_time: float | None = None

        # Initialize logger (synchronous fallback for tests)
        self._logger: logging.Logger | None = None

    @property
    def logger(self) -> logging.Logger:
        """Get logger instance with lazy initialization."""
        if self._logger is None:
            try:
                # Try to get injected logger from DI container
                injected_logger = depends.get_sync(Logger)
                # Check if it's actually a logger or a marker
                if isinstance(injected_logger, logging.Logger):
                    self._logger = injected_logger
                else:
                    # Fallback if DI returns a marker instead of logger
                    self._logger = logging.getLogger(self.__class__.__name__)
            except Exception:
                # Fallback to standard logging if DI not available
                self._logger = logging.getLogger(self.__class__.__name__)
        return self._logger

    @logger.setter
    def logger(self, value: logging.Logger) -> None:
        """Set logger instance."""
        self._logger = value

    @property
    def service_id(self) -> str:
        """Get service identifier."""
        return self._service_config.service_id

    @property
    def name(self) -> str:
        """Get service name."""
        return self._service_config.name

    @property
    def status(self) -> ServiceStatus:
        """Get current service status."""
        return self._status

    @property
    def metrics(self) -> ServiceMetrics:
        """Get service metrics."""
        return self._metrics

    @property
    def is_healthy(self) -> bool:
        """Check if service is healthy."""
        return self._status == ServiceStatus.ACTIVE

    async def initialize(self) -> None:
        """Initialize the service with proper lifecycle management."""
        async with self._initialization_lock:
            if self._initialized:
                return

            self._status = ServiceStatus.INITIALIZING

            try:
                import time

                self._start_time = time.time()
                self._metrics.initialized_at = self._start_time

                # Run service-specific initialization
                await self._initialize()

                # Start health check if enabled
                if self._settings.health_check_enabled:
                    await self._start_health_check()

                self._status = ServiceStatus.ACTIVE
                self._initialized = True

                self.logger.info(f"Service {self.name} initialized successfully")

            except Exception as e:
                self._status = ServiceStatus.ERROR
                self._metrics.errors_count += 1
                self._metrics.last_error = str(e)
                self.logger.exception(f"Failed to initialize service {self.name}: {e}")
                raise

    async def shutdown(self) -> None:
        """Shutdown the service gracefully."""
        if self._status in (ServiceStatus.STOPPING, ServiceStatus.STOPPED):
            return

        self._status = ServiceStatus.STOPPING
        self._shutdown_event.set()

        try:
            # Stop health check
            if self._health_check_task:
                self._health_check_task.cancel()
                with suppress(asyncio.CancelledError):
                    await self._health_check_task

            # Run service-specific shutdown
            await self._shutdown()

            # Clean up resources
            await self.cleanup()

            self._status = ServiceStatus.STOPPED
            self.logger.info(f"Service {self.name} shut down successfully")

        except Exception as e:
            self._status = ServiceStatus.ERROR
            self._metrics.errors_count += 1
            self._metrics.last_error = str(e)
            self.logger.exception(f"Error during service {self.name} shutdown: {e}")
            raise

    async def health_check(self) -> dict[str, t.Any]:
        """Perform health check and return status information."""
        try:
            # Run service-specific health check
            service_health = await self._health_check()

            return {
                "service_id": self.service_id,
                "name": self.name,
                "status": self._status.value,
                "healthy": self.is_healthy,
                "uptime": self._get_uptime(),
                "metrics": {
                    "requests_handled": self._metrics.requests_handled,
                    "errors_count": self._metrics.errors_count,
                    "last_error": self._metrics.last_error,
                }
                | self._metrics.custom_metrics,
                "service_specific": service_health,
            }

        except Exception as e:
            self._metrics.errors_count += 1
            self._metrics.last_error = str(e)
            self.logger.warning(f"Health check failed for service {self.name}: {e}")

            return {
                "service_id": self.service_id,
                "name": self.name,
                "status": ServiceStatus.ERROR.value,
                "healthy": False,
                "error": str(e),
            }

    def _get_uptime(self) -> float | None:
        """Calculate service uptime in seconds."""
        if self._start_time is None:
            return None
        import time

        return time.time() - self._start_time

    async def _start_health_check(self) -> None:
        """Start periodic health check task."""
        self._health_check_task = asyncio.create_task(self._health_check_loop())

    async def _health_check_loop(self) -> None:
        """Health check loop that runs periodically."""
        while not self._shutdown_event.is_set():
            try:
                await asyncio.sleep(self._settings.health_check_interval)
                if self._shutdown_event.is_set():
                    break

                health = await self.health_check()
                if not health.get("healthy", False):
                    self.logger.warning(
                        f"Service {self.name} health check failed: {health}",
                    )

            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.exception(
                    f"Health check loop error for service {self.name}: {e}",
                )
                await asyncio.sleep(self._settings.health_check_interval)

    async def _initialize(self) -> None:
        """Service-specific initialization logic."""
        # Default implementation does nothing - override in subclasses

    async def _shutdown(self) -> None:
        """Service-specific shutdown logic."""
        # Default implementation does nothing - override in subclasses

    async def _health_check(self) -> dict[str, t.Any]:
        """Service-specific health check logic.

        Override this method to provide custom health check logic.
        Return a dictionary with service-specific health information.
        """
        return {"status": "ok"}

    def increment_requests(self) -> None:
        """Increment request counter."""
        self._metrics.requests_handled += 1

    def record_error(self, error: str | Exception) -> None:
        """Record an error in service metrics."""
        self._metrics.errors_count += 1
        self._metrics.last_error = str(error)

    def set_custom_metric(self, key: str, value: t.Any) -> None:
        """Set a custom metric value."""
        self._metrics.custom_metrics[key] = value

    def get_custom_metric(self, key: str, default: t.Any = None) -> t.Any:
        """Get a custom metric value."""
        return self._metrics.custom_metrics.get(key, default)

    async def __aenter__(self) -> "ServiceBase":
        """Async context manager entry."""
        await self.initialize()
        return self

    async def __aexit__(self, exc_type: t.Any, exc_val: t.Any, exc_tb: t.Any) -> None:
        """Async context manager exit."""
        await self.shutdown()
