"""Health Check System for ACB Services Layer.

This module provides comprehensive health monitoring capabilities for ACB services,
adapters, and system components. It integrates with the Services Layer and provides
centralized health status reporting and alerting.
"""

import logging
import time
from abc import ABC, abstractmethod
from enum import Enum

import asyncio
import contextlib
import typing as t
from dataclasses import dataclass, field

from acb.cleanup import CleanupMixin
from acb.config import Config, Settings
from acb.depends import depends

from ._base import ServiceBase, ServiceConfig, ServiceSettings

# Service metadata for discovery system
try:
    from .discovery import (
        ServiceCapability,
        ServiceMetadata,
        ServiceStatus,
        generate_service_id,
    )

    SERVICE_METADATA: ServiceMetadata | None = ServiceMetadata(
        service_id=generate_service_id(),
        name="Health Service",
        category="health",
        service_type="monitor",
        version="1.0.0",
        acb_min_version="0.19.1",
        author="ACB Framework Team",
        created_date="2024-01-01T00:00:00",
        last_modified="2024-01-01T00:00:00",
        status=ServiceStatus.STABLE,
        capabilities=[
            ServiceCapability.HEALTH_MONITORING,
            ServiceCapability.METRICS_COLLECTION,
            ServiceCapability.ASYNC_OPERATIONS,
            ServiceCapability.LIFECYCLE_MANAGEMENT,
        ],
        description="Comprehensive health monitoring and alerting service for ACB components",
        settings_class="HealthServiceSettings",
        config_example={
            "reporter_check_interval": 30.0,
            "auto_register_services": True,
            "enable_adapter_monitoring": True,
            "expose_health_endpoint": True,
        },
    )
except ImportError:
    # Discovery system not available
    SERVICE_METADATA = None

logger = logging.getLogger(__name__)


class HealthStatus(Enum):
    """Health status levels for components and systems."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    CRITICAL = "critical"
    UNKNOWN = "unknown"

    def __bool__(self) -> bool:
        """Return True if status indicates healthy or degraded state."""
        return self.value in ("healthy", "degraded")


class HealthCheckType(Enum):
    """Types of health checks that can be performed."""

    LIVENESS = "liveness"  # Is the component alive?
    READINESS = "readiness"  # Is the component ready to serve?
    STARTUP = "startup"  # Has the component started successfully?
    DEPENDENCY = "dependency"  # Are dependencies healthy?
    RESOURCE = "resource"  # Are resources available?


@dataclass
class HealthCheckResult:
    """Result of a health check operation."""

    component_id: str
    component_name: str
    status: HealthStatus
    check_type: HealthCheckType
    message: str | None = None
    details: dict[str, t.Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    duration_ms: float | None = None
    error: str | None = None

    @property
    def is_healthy(self) -> bool:
        """Check if the result indicates healthy status."""
        return bool(self.status)

    def to_dict(self) -> dict[str, t.Any]:
        """Convert result to dictionary for serialization."""
        return {
            "component_id": self.component_id,
            "component_name": self.component_name,
            "status": self.status.value,
            "check_type": self.check_type.value,
            "message": self.message,
            "details": self.details,
            "timestamp": self.timestamp,
            "duration_ms": self.duration_ms,
            "error": self.error,
            "is_healthy": self.is_healthy,
        }


class HealthCheckMixin(ABC):
    """Mixin to add health check capabilities to any component.

    This mixin provides a standardized interface for health checks
    that can be applied to services, adapters, or any system component.
    """

    def __init__(self, *args: t.Any, **kwargs: t.Any) -> None:
        super().__init__(*args, **kwargs)
        self._last_health_check: HealthCheckResult | None = None
        self._health_check_lock = asyncio.Lock()

    @property
    def component_id(self) -> str:
        """Get unique identifier for this component."""
        return getattr(self, "service_id", None) or self.__class__.__name__.lower()

    @property
    def component_name(self) -> str:
        """Get human-readable name for this component."""
        return getattr(self, "name", None) or self.__class__.__name__

    async def perform_health_check(
        self,
        check_type: HealthCheckType = HealthCheckType.LIVENESS,
        timeout: float = 10.0,
    ) -> HealthCheckResult:
        """Perform a health check with proper error handling and timing."""
        async with self._health_check_lock:
            start_time = time.time()

            try:
                # Run the health check with timeout
                result = await asyncio.wait_for(
                    self._perform_health_check(check_type),
                    timeout=timeout,
                )

                # Calculate duration and update result
                duration = (time.time() - start_time) * 1000
                result.duration_ms = duration
                result.timestamp = start_time

                self._last_health_check = result
                return result

            except TimeoutError:
                return HealthCheckResult(
                    component_id=self.component_id,
                    component_name=self.component_name,
                    status=HealthStatus.CRITICAL,
                    check_type=check_type,
                    message=f"Health check timed out after {timeout}s",
                    error="Timeout",
                    duration_ms=(time.time() - start_time) * 1000,
                )

            except Exception as e:
                return HealthCheckResult(
                    component_id=self.component_id,
                    component_name=self.component_name,
                    status=HealthStatus.CRITICAL,
                    check_type=check_type,
                    message=f"Health check failed: {e}",
                    error=str(e),
                    duration_ms=(time.time() - start_time) * 1000,
                )

    @abstractmethod
    async def _perform_health_check(
        self,
        check_type: HealthCheckType,
    ) -> HealthCheckResult:
        """Implement component-specific health check logic.

        Args:
            check_type: Type of health check to perform

        Returns:
            HealthCheckResult with status and details
        """
        ...

    @property
    def last_health_check(self) -> HealthCheckResult | None:
        """Get the result of the last health check."""
        return self._last_health_check


class HealthReporterSettings(Settings):
    """Settings for health reporting."""

    enabled: bool = True
    check_interval: float = 30.0
    critical_threshold: int = 3  # Failed checks before critical
    degraded_threshold: int = 1  # Failed checks before degraded
    timeout: float = 10.0

    # Alerting settings
    alert_on_status_change: bool = True
    alert_on_critical: bool = True
    alert_webhook_url: str | None = None


class HealthReporter(CleanupMixin):
    """Aggregates and reports health status from multiple components.

    The HealthReporter collects health check results from registered components,
    maintains historical data, and provides system-wide health status reporting.
    """

    def __init__(self, settings: HealthReporterSettings | None = None) -> None:
        super().__init__()
        self._settings = settings or HealthReporterSettings()
        self._components: dict[str, HealthCheckMixin] = {}
        self._history: dict[str, list[HealthCheckResult]] = {}
        self._system_status = HealthStatus.UNKNOWN
        self._check_task: asyncio.Task[t.Any] | None = None
        self._shutdown_event = asyncio.Event()

        # Initialize configuration - try DI first, fallback to direct instantiation
        try:
            self.config = depends.get_sync(Config)
        except Exception:
            self.config = Config()

        # Use standard logging for logger - simpler and more reliable
        self.logger = logging.getLogger(__name__)

    def register_component(self, component: HealthCheckMixin) -> None:
        """Register a component for health monitoring."""
        component_id = component.component_id
        self._components[component_id] = component
        self._history[component_id] = []
        self.logger.info(f"Registered component for health monitoring: {component_id}")

    def unregister_component(self, component: HealthCheckMixin | str) -> None:
        """Unregister a component from health monitoring."""
        component_id = (
            component if isinstance(component, str) else component.component_id
        )
        if component_id in self._components:
            del self._components[component_id]
            # Keep history for analysis
            self.logger.info(
                f"Unregistered component from health monitoring: {component_id}",
            )

    async def check_all_components(
        self,
        check_type: HealthCheckType = HealthCheckType.LIVENESS,
    ) -> dict[str, HealthCheckResult]:
        """Check health of all registered components."""
        if not self._components:
            return {}

        # Run all health checks concurrently
        tasks = [
            component.perform_health_check(check_type, self._settings.timeout)
            for component in self._components.values()
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results and update history
        component_results: dict[str, HealthCheckResult] = {}
        for component_id, result in zip(self._components.keys(), results, strict=False):
            if isinstance(result, BaseException):
                # Create error result for failed checks
                health_result = HealthCheckResult(
                    component_id=component_id,
                    component_name=self._components[component_id].component_name,
                    status=HealthStatus.CRITICAL,
                    check_type=check_type,
                    error=str(result),
                    message="Health check execution failed",
                )
            else:
                health_result = result

            component_results[component_id] = health_result
            self._update_history(component_id, health_result)

        # Update system status based on component results
        self._update_system_status(component_results)

        return component_results

    def get_system_health(
        self,
        fresh_results: dict[str, HealthCheckResult] | None = None,
    ) -> dict[str, t.Any]:
        """Get overall system health status and summary."""
        component_count = len(self._components)

        # Count components by detailed status
        status_counts = {
            "healthy": 0,
            "degraded": 0,
            "unhealthy": 0,
            "critical": 0,
            "unknown": 0,
        }

        if fresh_results:
            # Use fresh results if provided
            for component_id, result in fresh_results.items():
                status = result.status
                if status == HealthStatus.HEALTHY:
                    status_counts["healthy"] += 1
                elif status == HealthStatus.DEGRADED:
                    status_counts["degraded"] += 1
                elif status == HealthStatus.UNHEALTHY:
                    status_counts["unhealthy"] += 1
                elif status == HealthStatus.CRITICAL:
                    status_counts["critical"] += 1
                else:
                    status_counts["unknown"] += 1
        else:
            # Use cached status from history
            for component_id in self._components:
                status = self._get_component_status(component_id)
                if status == HealthStatus.HEALTHY:
                    status_counts["healthy"] += 1
                elif status == HealthStatus.DEGRADED:
                    status_counts["degraded"] += 1
                elif status == HealthStatus.UNHEALTHY:
                    status_counts["unhealthy"] += 1
                elif status == HealthStatus.CRITICAL:
                    status_counts["critical"] += 1
                else:
                    status_counts["unknown"] += 1

        # Calculate unhealthy total (unhealthy + critical)
        unhealthy_total = status_counts["unhealthy"] + status_counts["critical"]

        # Determine system health status
        if status_counts["critical"] > 0:
            system_healthy = False
            system_status = "critical"
        elif unhealthy_total > component_count // 2:
            system_healthy = False
            system_status = "unhealthy"
        elif unhealthy_total > 0 or status_counts["degraded"] > 0:
            system_healthy = not unhealthy_total > 0
            system_status = "degraded"
        else:
            system_healthy = True
            system_status = "healthy"

        return {
            "system_status": system_status,
            "system_healthy": system_healthy,
            "timestamp": time.time(),
            "components": {
                "total": component_count,
                "healthy": status_counts["healthy"],
                "degraded": status_counts["degraded"],
                "unhealthy": status_counts["unhealthy"],
                "critical": status_counts["critical"],
                "unknown": status_counts["unknown"],
            },
            "component_details": {
                component_id: {
                    "status": self._get_component_status(component_id).value,
                    "last_check": self._get_last_check_time(component_id),
                }
                for component_id in self._components
            },
        }

    def get_component_history(
        self,
        component_id: str,
        limit: int = 10,
    ) -> list[HealthCheckResult]:
        """Get health check history for a specific component."""
        history = self._history.get(component_id, [])
        return history[-limit:] if history else []

    async def start_monitoring(self) -> None:
        """Start continuous health monitoring."""
        if self._check_task is not None:
            return

        self._shutdown_event.clear()
        self._check_task = asyncio.create_task(self._monitoring_loop())
        self.logger.info("Started health monitoring")

    async def stop_monitoring(self) -> None:
        """Stop health monitoring."""
        self._shutdown_event.set()

        if self._check_task:
            self._check_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._check_task
            self._check_task = None

        self.logger.info("Stopped health monitoring")

    async def _monitoring_loop(self) -> None:
        """Main monitoring loop that runs periodic health checks."""
        while not self._shutdown_event.is_set():
            try:
                await self.check_all_components()

                # Wait for next check or shutdown
                try:
                    await asyncio.wait_for(
                        self._shutdown_event.wait(),
                        timeout=self._settings.check_interval,
                    )
                    break  # Shutdown requested
                except TimeoutError:
                    continue  # Time for next check

            except Exception as e:
                self.logger.exception(f"Error in health monitoring loop: {e}")
                await asyncio.sleep(self._settings.check_interval)

    def _update_history(self, component_id: str, result: HealthCheckResult) -> None:
        """Update health check history for a component."""
        if component_id not in self._history:
            self._history[component_id] = []

        history = self._history[component_id]
        history.append(result)

        # Keep only last 100 results to prevent memory issues
        if len(history) > 100:
            self._history[component_id] = history[-100:]

    def _get_component_status(self, component_id: str) -> HealthStatus:
        """Get current status of a component based on recent history."""
        history = self._history.get(component_id, [])
        if not history:
            return HealthStatus.UNKNOWN

        # Look at recent results to determine status
        recent_results = history[-5:]  # Last 5 checks
        failed_checks = sum(1 for r in recent_results if not r.is_healthy)

        # For single checks, use the result directly if thresholds don't make sense
        if len(recent_results) == 1:
            return recent_results[0].status

        if failed_checks >= self._settings.critical_threshold:
            return HealthStatus.CRITICAL
        if failed_checks >= self._settings.degraded_threshold:
            return HealthStatus.DEGRADED
        return HealthStatus.HEALTHY

    def _get_last_check_time(self, component_id: str) -> float | None:
        """Get timestamp of last health check for component."""
        history = self._history.get(component_id, [])
        if history:
            return history[-1].timestamp
        return None

    def _update_system_status(self, results: dict[str, HealthCheckResult]) -> None:
        """Update overall system status based on component results."""
        if not results:
            self._system_status = HealthStatus.UNKNOWN
            return

        critical_count = sum(
            1 for r in results.values() if r.status == HealthStatus.CRITICAL
        )
        unhealthy_count = sum(
            1 for r in results.values() if r.status == HealthStatus.UNHEALTHY
        )
        degraded_count = sum(
            1 for r in results.values() if r.status == HealthStatus.DEGRADED
        )

        if critical_count > 0:
            self._system_status = HealthStatus.CRITICAL
            return

        if unhealthy_count > len(results) // 2:  # More than half unhealthy
            self._system_status = HealthStatus.UNHEALTHY
            return

        if unhealthy_count > 0 or degraded_count > 0:
            self._system_status = HealthStatus.DEGRADED
            return

        self._system_status = HealthStatus.HEALTHY

    async def cleanup(self) -> None:
        """Clean up resources."""
        await self.stop_monitoring()
        await super().cleanup()


class HealthServiceSettings(ServiceSettings):
    """Settings for the Health Service."""

    # Override health check settings for the health service itself
    health_check_enabled: bool = False  # Prevent recursion

    # Health reporting settings
    reporter_check_interval: float = 30.0
    auto_register_services: bool = True
    enable_adapter_monitoring: bool = True

    # API settings
    expose_health_endpoint: bool = True
    health_endpoint_path: str = "/health"
    detailed_health_endpoint_path: str = "/health/detailed"


class HealthService(ServiceBase, HealthCheckMixin):
    """Central health monitoring service for ACB applications.

    This service coordinates health monitoring across all system components,
    provides health status APIs, and integrates with monitoring systems.
    """

    def __init__(
        self,
        service_config: ServiceConfig | None = None,
        settings: HealthServiceSettings | None = None,
    ) -> None:
        # Initialize service config
        if service_config is None:
            service_config = ServiceConfig(
                service_id="health_service",
                name="Health Service",
                description="Central health monitoring and reporting service",
                priority=10,  # Start early
            )

        super().__init__(service_config, settings or HealthServiceSettings())
        HealthCheckMixin.__init__(self)

        self._reporter = HealthReporter()
        self._service_registry: t.Any = None  # Will be injected

    async def _initialize(self) -> None:
        """Initialize the health service."""
        # Start the health reporter
        await self._reporter.start_monitoring()

        # Auto-register services if enabled
        if (
            hasattr(self._settings, "auto_register_services")
            and self._settings.auto_register_services
        ):
            await self._auto_register_services()

        self.logger.info("Health service initialized successfully")

    async def _shutdown(self) -> None:
        """Shutdown the health service."""
        await self._reporter.stop_monitoring()
        await self._reporter.cleanup()
        self.logger.info("Health service shut down successfully")

    async def _perform_health_check(
        self,
        check_type: HealthCheckType,
    ) -> HealthCheckResult:
        """Health check for the health service itself."""
        # Check if reporter is running
        is_monitoring = (
            self._reporter._check_task is not None
            and not self._reporter._check_task.done()
        )

        if is_monitoring:
            status = HealthStatus.HEALTHY
            message = "Health service is operational"
        else:
            status = HealthStatus.UNHEALTHY
            message = "Health monitoring is not running"

        return HealthCheckResult(
            component_id=self.component_id,
            component_name=self.component_name,
            status=status,
            check_type=check_type,
            message=message,
            details={
                "monitoring_active": is_monitoring,
                "registered_components": len(self._reporter._components),
                "system_status": self._reporter._system_status.value,
            },
        )

    async def _auto_register_services(self) -> None:
        """Automatically register services from the service registry."""
        try:
            from .registry import get_registry

            registry = get_registry()
            self._service_registry = registry

            # Register all services that implement HealthCheckMixin
            for service in registry._services.values():
                if isinstance(service, HealthCheckMixin) and service != self:
                    self._reporter.register_component(service)

        except Exception as e:
            self.logger.warning(f"Failed to auto-register services: {e}")

    def register_component(self, component: HealthCheckMixin) -> None:
        """Register a component for health monitoring."""
        self._reporter.register_component(component)

    def unregister_component(self, component: HealthCheckMixin | str) -> None:
        """Unregister a component from health monitoring."""
        self._reporter.unregister_component(component)

    async def check_system_health(self) -> dict[str, t.Any]:
        """Get comprehensive system health status."""
        # Perform dependency health checks on all components for comprehensive status
        component_results = await self._reporter.check_all_components(
            HealthCheckType.DEPENDENCY,
        )

        # Get system summary using fresh results
        system_health = self._reporter.get_system_health(component_results)

        # Add detailed component results
        system_health["component_results"] = {
            comp_id: result.to_dict() for comp_id, result in component_results.items()
        }

        return system_health

    async def check_component_health(
        self,
        component_id: str,
    ) -> HealthCheckResult | None:
        """Check health of a specific component."""
        if component_id in self._reporter._components:
            component = self._reporter._components[component_id]
            result = await component.perform_health_check()
            # Update the reporter's history
            self._reporter._update_history(component_id, result)
            return result
        return None

    def get_component_history(
        self,
        component_id: str,
        limit: int = 10,
    ) -> list[dict[str, t.Any]]:
        """Get health history for a component."""
        history = self._reporter.get_component_history(component_id, limit)
        return [result.to_dict() for result in history]
