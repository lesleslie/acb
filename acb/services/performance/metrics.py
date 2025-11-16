"""Performance metrics collection service.

Provides comprehensive performance monitoring and metrics collection
for ACB applications with FastBlocks integration.
"""

import time
from collections import defaultdict, deque
from statistics import mean, median

import asyncio
import contextlib
import typing as t
from dataclasses import dataclass, field
from pydantic import BaseModel, ConfigDict, Field

from acb.config import Config
from acb.depends import Inject, depends
from acb.services._base import ServiceBase, ServiceConfig, ServiceSettings

# Service metadata for discovery system
SERVICE_METADATA: t.Any = None

try:
    from acb.services.discovery import (
        ServiceCapability,
        ServiceMetadata,
        ServiceStatus,
        generate_service_id,
    )

    SERVICE_METADATA = ServiceMetadata(
        service_id=generate_service_id(),
        name="Metrics Collector",
        category="performance",
        service_type="metrics_collector",
        version="1.0.0",
        acb_min_version="0.19.1",
        author="ACB Framework Team",
        created_date="2024-01-01T00:00:00",
        last_modified="2024-01-01T00:00:00",
        status=ServiceStatus.STABLE,
        capabilities=[
            ServiceCapability.METRICS_COLLECTION,
            ServiceCapability.ASYNC_OPERATIONS,
            ServiceCapability.LIFECYCLE_MANAGEMENT,
        ],
        description="Performance metrics collection and analysis service",
        settings_class="MetricsCollectorSettings",
        config_example={
            "collection_interval": 10.0,
            "max_metrics_history": 1000,
            "enable_background_collection": True,
            "metrics_retention_seconds": 3600,
        },
    )
except ImportError:
    # Discovery system not available
    SERVICE_METADATA = None


@dataclass
class PerformanceMetric:
    """Individual performance metric data point."""

    name: str
    value: float
    timestamp: float
    tags: dict[str, str] = field(default_factory=dict)
    metadata: dict[str, t.Any] = field(default_factory=dict)


@dataclass
class MetricsSummary:
    """Statistical summary of performance metrics."""

    count: int
    mean: float
    median: float
    min: float
    max: float
    p95: float
    p99: float


class PerformanceMetrics(BaseModel):
    """Performance metrics data model."""

    model_config = ConfigDict(extra="forbid")

    response_times: list[float] = Field(default_factory=list)
    error_rates: list[float] = Field(default_factory=list)
    throughput: list[float] = Field(default_factory=list)
    cache_hit_rates: list[float] = Field(default_factory=list)
    database_query_times: list[float] = Field(default_factory=list)
    memory_usage: list[float] = Field(default_factory=list)
    custom_metrics: dict[str, list[float]] = Field(default_factory=dict)


class MetricsCollectorSettings(ServiceSettings):
    """Settings for the metrics collector service."""

    collection_interval_seconds: float = 60.0
    max_data_points: int = 1000
    enable_system_metrics: bool = True
    enable_application_metrics: bool = True
    metrics_retention_hours: int = 24

    @depends.inject
    def __init__(self, config: Inject[Config], **values: t.Any) -> None:
        super().__init__(**values)


class MetricsCollector(ServiceBase):
    """Service for collecting and analyzing performance metrics.

    Provides comprehensive metrics collection with statistical analysis
    and integration with monitoring systems.
    """

    def __init__(
        self,
        service_config: ServiceConfig | None = None,
        settings: MetricsCollectorSettings | None = None,
    ) -> None:
        if service_config is None:
            service_config = ServiceConfig(
                service_id="metrics_collector",
                name="Metrics Collector",
                description="Performance metrics collection and analysis service",
                priority=10,  # High priority - start early
            )

        super().__init__(service_config, settings or MetricsCollectorSettings())
        self._settings: MetricsCollectorSettings = self._settings  # type: ignore

        # Metrics storage with bounded queues
        def _create_deque() -> deque[PerformanceMetric]:
            return deque(maxlen=self._settings.max_data_points)

        self._metrics_data: dict[str, deque[PerformanceMetric]] = defaultdict(
            _create_deque,
        )
        self._collection_task: asyncio.Task[t.Any] | None = None
        self._start_time = time.time()

    async def _initialize(self) -> None:
        """Initialize the metrics collector."""
        # Start metrics collection task
        self._collection_task = asyncio.create_task(self._collection_loop())
        self.logger.info("Metrics collector initialized")

    async def _shutdown(self) -> None:
        """Shutdown the metrics collector."""
        if self._collection_task:
            self._collection_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._collection_task

    async def _health_check(self) -> dict[str, t.Any]:
        """Health check for metrics collector."""
        total_metrics = sum(len(queue) for queue in self._metrics_data.values())
        return {
            "total_metrics_collected": total_metrics,
            "metrics_categories": len(self._metrics_data),
            "collection_running": (
                self._collection_task is not None and not self._collection_task.done()
            ),
            "uptime_seconds": time.time() - self._start_time
            if self._start_time is not None
            else 0.0,
        }

    async def record_metric(
        self,
        name: str,
        value: float,
        tags: dict[str, str] | None = None,
        metadata: dict[str, t.Any] | None = None,
    ) -> None:
        """Record a performance metric.

        Args:
            name: Metric name
            value: Metric value
            tags: Optional tags for categorization
            metadata: Optional additional metadata
        """
        metric = PerformanceMetric(
            name=name,
            value=value,
            timestamp=time.time(),
            tags=tags or {},
            metadata=metadata or {},
        )

        self._metrics_data[name].append(metric)
        self.increment_requests()

    async def record_response_time(
        self,
        duration_ms: float,
        endpoint: str | None = None,
    ) -> None:
        """Record HTTP response time metric.

        Args:
            duration_ms: Response time in milliseconds
            endpoint: Optional endpoint identifier
        """
        tags = {"endpoint": endpoint} if endpoint else {}
        await self.record_metric("response_time", duration_ms, tags)

    async def record_database_query_time(
        self,
        duration_ms: float,
        query_type: str | None = None,
    ) -> None:
        """Record database query time metric.

        Args:
            duration_ms: Query duration in milliseconds
            query_type: Optional query type (SELECT, INSERT, etc.)
        """
        tags = {"query_type": query_type} if query_type else {}
        await self.record_metric("db_query_time", duration_ms, tags)

    async def record_cache_operation(
        self,
        hit: bool,
        duration_ms: float | None = None,
    ) -> None:
        """Record cache operation metric.

        Args:
            hit: Whether the cache operation was a hit or miss
            duration_ms: Optional operation duration
        """
        tags = {"operation": "hit" if hit else "miss"}
        await self.record_metric("cache_operation", 1.0 if hit else 0.0, tags)

        if duration_ms is not None:
            await self.record_metric("cache_duration", duration_ms, tags)

    async def record_error_metric(
        self,
        error_type: str,
        endpoint: str | None = None,
    ) -> None:
        """Record error metric.

        Args:
            error_type: Type of error
            endpoint: Optional endpoint where error occurred
        """
        tags = {"error_type": error_type}
        if endpoint:
            tags["endpoint"] = endpoint

        await self.record_metric("error", 1.0, tags)

    def get_metrics_summary(
        self,
        metric_name: str,
        time_window_seconds: int | None = None,
    ) -> MetricsSummary | None:
        """Get statistical summary for a metric.

        Args:
            metric_name: Name of the metric
            time_window_seconds: Optional time window to limit data

        Returns:
            Statistical summary or None if no data
        """
        if metric_name not in self._metrics_data:
            return None

        metrics = self._metrics_data[metric_name]
        if not metrics:
            return None

        # Filter by time window if specified
        if time_window_seconds:
            cutoff_time = time.time() - time_window_seconds
            filtered_metrics = [m for m in metrics if m.timestamp >= cutoff_time]
        else:
            filtered_metrics = list(metrics)

        if not filtered_metrics:
            return None

        values = [m.value for m in filtered_metrics]
        sorted_values = sorted(values)

        return MetricsSummary(
            count=len(values),
            mean=mean(values),
            median=median(values),
            min=min(values),
            max=max(values),
            p95=self._percentile(sorted_values, 95),
            p99=self._percentile(sorted_values, 99),
        )

    def get_current_performance_metrics(self) -> PerformanceMetrics:
        """Get current performance metrics summary.

        Returns:
            Performance metrics with recent data
        """
        metrics = PerformanceMetrics()

        # Extract recent values for standard metrics
        time_window = 300  # Last 5 minutes
        cutoff_time = time.time() - time_window

        # Response times
        if "response_time" in self._metrics_data:
            metrics.response_times = [
                m.value
                for m in self._metrics_data["response_time"]
                if m.timestamp >= cutoff_time
            ]

        # Database query times
        if "db_query_time" in self._metrics_data:
            metrics.database_query_times = [
                m.value
                for m in self._metrics_data["db_query_time"]
                if m.timestamp >= cutoff_time
            ]

        # Cache hit rates (calculate from cache operations)
        if "cache_operation" in self._metrics_data:
            cache_ops = [
                m
                for m in self._metrics_data["cache_operation"]
                if m.timestamp >= cutoff_time
            ]
            if cache_ops:
                hit_rate = sum(m.value for m in cache_ops) / len(cache_ops) * 100
                metrics.cache_hit_rates = [hit_rate]

        # Error rates (calculate from error and response metrics)
        if "error" in self._metrics_data and "response_time" in self._metrics_data:
            error_count = len(
                [m for m in self._metrics_data["error"] if m.timestamp >= cutoff_time],
            )
            response_count = len(
                [
                    m
                    for m in self._metrics_data["response_time"]
                    if m.timestamp >= cutoff_time
                ],
            )
            if response_count > 0:
                error_rate = (error_count / response_count) * 100
                metrics.error_rates = [error_rate]

        # Custom metrics
        for metric_name, metric_queue in self._metrics_data.items():
            if metric_name not in {
                "response_time",
                "db_query_time",
                "cache_operation",
                "error",
            }:
                recent_values = [
                    m.value for m in metric_queue if m.timestamp >= cutoff_time
                ]
                if recent_values:
                    metrics.custom_metrics[metric_name] = recent_values

        return metrics

    def _percentile(self, sorted_values: list[float], percentile: int) -> float:
        """Calculate percentile from sorted values."""
        if not sorted_values:
            return 0.0

        index = (percentile / 100.0) * (len(sorted_values) - 1)
        lower_index = int(index)
        upper_index = min(lower_index + 1, len(sorted_values) - 1)

        if lower_index == upper_index:
            return sorted_values[lower_index]

        # Linear interpolation
        weight = index - lower_index
        return (
            sorted_values[lower_index] * (1 - weight)
            + sorted_values[upper_index] * weight
        )

    async def _collection_loop(self) -> None:
        """Main metrics collection loop."""
        while not self._shutdown_event.is_set():
            try:
                await asyncio.sleep(self._settings.collection_interval_seconds)
                if self._shutdown_event.is_set():
                    break

                await self._collect_system_metrics()
                await self._cleanup_old_metrics()

            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.exception(f"Metrics collection error: {e}")
                await asyncio.sleep(60)  # Wait before retrying

    async def _collect_system_metrics(self) -> None:
        """Collect system-level performance metrics."""
        if not self._settings.enable_system_metrics:
            return

        try:
            import psutil

            # Memory usage
            memory = psutil.virtual_memory()
            await self.record_metric("memory_usage_percent", memory.percent)
            await self.record_metric("memory_usage_bytes", memory.used)

            # CPU usage
            cpu_percent = psutil.cpu_percent(interval=None)
            await self.record_metric("cpu_usage_percent", cpu_percent)

        except ImportError:
            # psutil not available, skip system metrics
            pass
        except Exception as e:
            self.logger.warning(f"Failed to collect system metrics: {e}")

    async def _cleanup_old_metrics(self) -> None:
        """Remove old metrics beyond retention period."""
        cutoff_time = time.time() - (self._settings.metrics_retention_hours * 3600)
        cleaned_count = 0

        for metric_queue in self._metrics_data.values():
            # Remove old metrics from the front of the deque
            while metric_queue and metric_queue[0].timestamp < cutoff_time:
                metric_queue.popleft()
                cleaned_count += 1

        if cleaned_count > 0:
            self.logger.debug(f"Cleaned up {cleaned_count} old metrics")
