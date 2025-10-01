"""Analytics and monitoring collection for ACB Gateway.

This module provides comprehensive analytics and monitoring capabilities including:
- Request/response tracking and metrics
- Performance monitoring and analysis
- Usage analytics and reporting
- Custom event tracking
- Real-time monitoring integration
- Historical data aggregation

Features:
- Request metrics collection
- Performance tracking
- Usage analytics
- Custom event tracking
- Export to monitoring systems
- Real-time metrics streaming
"""

from __future__ import annotations

import time
import typing as t
from collections import defaultdict, deque
from dataclasses import dataclass, field
from enum import Enum

from pydantic import BaseModel, Field
from acb.gateway._base import GatewayRequest, GatewayResponse


class EventType(Enum):
    """Analytics event types."""

    REQUEST_START = "request_start"
    REQUEST_END = "request_end"
    AUTHENTICATION = "authentication"
    AUTHORIZATION = "authorization"
    RATE_LIMIT = "rate_limit"
    VALIDATION = "validation"
    ROUTING = "routing"
    UPSTREAM_REQUEST = "upstream_request"
    UPSTREAM_RESPONSE = "upstream_response"
    CACHE_HIT = "cache_hit"
    CACHE_MISS = "cache_miss"
    ERROR = "error"
    CUSTOM = "custom"


class MetricType(Enum):
    """Metric types for aggregation."""

    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    TIMER = "timer"


@dataclass
class AnalyticsEvent:
    """Analytics event data."""

    # Event identification
    event_type: EventType
    timestamp: float = field(default_factory=time.time)
    event_id: str | None = None

    # Request context
    request_id: str | None = None
    tenant_id: str | None = None
    client_id: str | None = None
    user_id: str | None = None

    # Request details
    method: str | None = None
    path: str | None = None
    status_code: int | None = None
    response_time_ms: float | None = None

    # Component details
    component: str | None = None
    operation: str | None = None

    # Metrics
    metrics: dict[str, t.Any] = field(default_factory=dict)

    # Custom attributes
    attributes: dict[str, t.Any] = field(default_factory=dict)

    # Error details
    error_message: str | None = None
    error_code: str | None = None

    def to_dict(self) -> dict[str, t.Any]:
        """Convert event to dictionary format."""
        return {
            "event_type": self.event_type.value,
            "timestamp": self.timestamp,
            "event_id": self.event_id,
            "request_id": self.request_id,
            "tenant_id": self.tenant_id,
            "client_id": self.client_id,
            "user_id": self.user_id,
            "method": self.method,
            "path": self.path,
            "status_code": self.status_code,
            "response_time_ms": self.response_time_ms,
            "component": self.component,
            "operation": self.operation,
            "metrics": self.metrics,
            "attributes": self.attributes,
            "error_message": self.error_message,
            "error_code": self.error_code,
        }


@dataclass
class MetricSample:
    """Individual metric sample."""

    name: str
    value: float
    timestamp: float = field(default_factory=time.time)
    labels: dict[str, str] = field(default_factory=dict)


@dataclass
class AggregatedMetrics:
    """Aggregated metrics data."""

    # Request metrics
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0

    # Response time metrics
    avg_response_time_ms: float = 0.0
    min_response_time_ms: float = float('inf')
    max_response_time_ms: float = 0.0
    p50_response_time_ms: float = 0.0
    p95_response_time_ms: float = 0.0
    p99_response_time_ms: float = 0.0

    # Status code distribution
    status_codes: dict[int, int] = field(default_factory=dict)

    # Error metrics
    error_rate: float = 0.0
    error_count: int = 0

    # Rate limiting metrics
    rate_limited_requests: int = 0
    rate_limit_rate: float = 0.0

    # Authentication metrics
    auth_failures: int = 0
    auth_success_rate: float = 0.0

    # Cache metrics
    cache_hits: int = 0
    cache_misses: int = 0
    cache_hit_rate: float = 0.0

    # Tenant metrics
    tenant_distribution: dict[str, int] = field(default_factory=dict)

    # Endpoint metrics
    endpoint_distribution: dict[str, int] = field(default_factory=dict)

    # Custom metrics
    custom_metrics: dict[str, t.Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, t.Any]:
        """Convert to dictionary format."""
        return {
            "total_requests": self.total_requests,
            "successful_requests": self.successful_requests,
            "failed_requests": self.failed_requests,
            "avg_response_time_ms": self.avg_response_time_ms,
            "min_response_time_ms": self.min_response_time_ms if self.min_response_time_ms != float('inf') else 0.0,
            "max_response_time_ms": self.max_response_time_ms,
            "p50_response_time_ms": self.p50_response_time_ms,
            "p95_response_time_ms": self.p95_response_time_ms,
            "p99_response_time_ms": self.p99_response_time_ms,
            "status_codes": self.status_codes,
            "error_rate": self.error_rate,
            "error_count": self.error_count,
            "rate_limited_requests": self.rate_limited_requests,
            "rate_limit_rate": self.rate_limit_rate,
            "auth_failures": self.auth_failures,
            "auth_success_rate": self.auth_success_rate,
            "cache_hits": self.cache_hits,
            "cache_misses": self.cache_misses,
            "cache_hit_rate": self.cache_hit_rate,
            "tenant_distribution": self.tenant_distribution,
            "endpoint_distribution": self.endpoint_distribution,
            "custom_metrics": self.custom_metrics,
        }


class AnalyticsConfig(BaseModel):
    """Analytics configuration."""

    # Collection settings
    enabled: bool = True
    sampling_rate: float = 1.0  # 0.0 to 1.0
    batch_size: int = 100
    flush_interval: float = 60.0  # seconds

    # Storage settings
    max_events_in_memory: int = 10000
    retention_period: int = 86400  # seconds (24 hours)

    # Export settings
    enable_export: bool = False
    export_format: str = "json"  # json, prometheus, statsd
    export_endpoint: str | None = None
    export_interval: float = 300.0  # seconds

    # Metric collection
    collect_request_metrics: bool = True
    collect_response_metrics: bool = True
    collect_error_metrics: bool = True
    collect_performance_metrics: bool = True
    collect_security_metrics: bool = True

    # Privacy settings
    anonymize_ip: bool = False
    exclude_headers: list[str] = Field(default_factory=lambda: ["authorization", "cookie"])
    exclude_paths: list[str] = Field(default_factory=lambda: ["/health", "/metrics"])

    # Custom dimensions
    custom_dimensions: list[str] = Field(default_factory=list)

    class Config:
        extra = "forbid"


class ResponseTimeTracker:
    """Track response times for percentile calculations."""

    def __init__(self, max_samples: int = 1000) -> None:
        self._samples: deque[float] = deque(maxlen=max_samples)

    def add_sample(self, response_time_ms: float) -> None:
        """Add a response time sample."""
        self._samples.append(response_time_ms)

    def get_percentiles(self) -> dict[str, float]:
        """Calculate response time percentiles."""
        if not self._samples:
            return {
                "p50": 0.0,
                "p95": 0.0,
                "p99": 0.0,
            }

        sorted_samples = sorted(self._samples)
        len(sorted_samples)

        return {
            "p50": self._percentile(sorted_samples, 50),
            "p95": self._percentile(sorted_samples, 95),
            "p99": self._percentile(sorted_samples, 99),
        }

    def _percentile(self, sorted_data: list[float], percentile: float) -> float:
        """Calculate a specific percentile."""
        if not sorted_data:
            return 0.0

        index = (percentile / 100.0) * (len(sorted_data) - 1)
        lower_index = int(index)
        upper_index = min(lower_index + 1, len(sorted_data) - 1)

        if lower_index == upper_index:
            return sorted_data[lower_index]

        # Linear interpolation
        weight = index - lower_index
        return sorted_data[lower_index] * (1 - weight) + sorted_data[upper_index] * weight


class AnalyticsCollector:
    """Main analytics collector for gateway metrics and events."""

    def __init__(self, config: AnalyticsConfig | None = None) -> None:
        self._config = config or AnalyticsConfig()
        self._events: deque[AnalyticsEvent] = deque(maxlen=self._config.max_events_in_memory)
        self._metrics = AggregatedMetrics()
        self._response_time_tracker = ResponseTimeTracker()

        # Per-tenant metrics
        self._tenant_metrics: dict[str, AggregatedMetrics] = defaultdict(AggregatedMetrics)

        # Per-endpoint metrics
        self._endpoint_metrics: dict[str, AggregatedMetrics] = defaultdict(AggregatedMetrics)

        # Sampling state
        self._sample_counter = 0

    async def collect_request_start(
        self,
        request: GatewayRequest,
        request_id: str | None = None,
    ) -> None:
        """Collect request start event."""
        if not self._should_sample():
            return

        event = AnalyticsEvent(
            event_type=EventType.REQUEST_START,
            request_id=request_id or request.request_id,
            tenant_id=request.tenant_id,
            client_id=self._extract_client_id(request),
            user_id=request.auth_user.get("user_id") if request.auth_user else None,
            method=request.method.value,
            path=self._sanitize_path(request.path),
            component="gateway",
            operation="request_start",
        )

        await self._add_event(event)

    async def collect_request_end(
        self,
        request: GatewayRequest,
        response: GatewayResponse,
        processing_time_ms: float,
        request_id: str | None = None,
    ) -> None:
        """Collect request end event and update metrics."""
        if not self._should_sample():
            return

        # Create event
        event = AnalyticsEvent(
            event_type=EventType.REQUEST_END,
            request_id=request_id or request.request_id,
            tenant_id=request.tenant_id,
            client_id=self._extract_client_id(request),
            user_id=request.auth_user.get("user_id") if request.auth_user else None,
            method=request.method.value,
            path=self._sanitize_path(request.path),
            status_code=response.status_code,
            response_time_ms=processing_time_ms,
            component="gateway",
            operation="request_end",
        )

        await self._add_event(event)

        # Update aggregated metrics
        await self._update_request_metrics(request, response, processing_time_ms)

    async def collect_authentication_event(
        self,
        request: GatewayRequest,
        success: bool,
        auth_method: str | None = None,
        error_message: str | None = None,
    ) -> None:
        """Collect authentication event."""
        if not self._should_sample():
            return

        event = AnalyticsEvent(
            event_type=EventType.AUTHENTICATION,
            request_id=request.request_id,
            tenant_id=request.tenant_id,
            client_id=self._extract_client_id(request),
            method=request.method.value,
            path=self._sanitize_path(request.path),
            component="auth",
            operation=auth_method or "unknown",
            attributes={"success": success},
            error_message=error_message,
        )

        await self._add_event(event)

        # Update auth metrics
        if success:
            self._metrics.successful_requests += 1
        else:
            self._metrics.auth_failures += 1

    async def collect_rate_limit_event(
        self,
        request: GatewayRequest,
        limited: bool,
        limit_info: dict[str, t.Any] | None = None,
    ) -> None:
        """Collect rate limiting event."""
        if not self._should_sample():
            return

        event = AnalyticsEvent(
            event_type=EventType.RATE_LIMIT,
            request_id=request.request_id,
            tenant_id=request.tenant_id,
            client_id=self._extract_client_id(request),
            method=request.method.value,
            path=self._sanitize_path(request.path),
            component="rate_limiter",
            operation="check_limit",
            attributes={"limited": limited, "limit_info": limit_info or {}},
        )

        await self._add_event(event)

        # Update rate limit metrics
        if limited:
            self._metrics.rate_limited_requests += 1

    async def collect_cache_event(
        self,
        request: GatewayRequest,
        cache_hit: bool,
        cache_key: str | None = None,
    ) -> None:
        """Collect cache event."""
        if not self._should_sample():
            return

        event_type = EventType.CACHE_HIT if cache_hit else EventType.CACHE_MISS
        event = AnalyticsEvent(
            event_type=event_type,
            request_id=request.request_id,
            tenant_id=request.tenant_id,
            client_id=self._extract_client_id(request),
            method=request.method.value,
            path=self._sanitize_path(request.path),
            component="cache",
            operation="lookup",
            attributes={"cache_key": cache_key or "unknown"},
        )

        await self._add_event(event)

        # Update cache metrics
        if cache_hit:
            self._metrics.cache_hits += 1
        else:
            self._metrics.cache_misses += 1

    async def collect_error_event(
        self,
        request: GatewayRequest,
        error_message: str,
        error_code: str | None = None,
        component: str | None = None,
    ) -> None:
        """Collect error event."""
        if not self._should_sample():
            return

        event = AnalyticsEvent(
            event_type=EventType.ERROR,
            request_id=request.request_id,
            tenant_id=request.tenant_id,
            client_id=self._extract_client_id(request),
            method=request.method.value,
            path=self._sanitize_path(request.path),
            component=component or "gateway",
            operation="error",
            error_message=error_message,
            error_code=error_code,
        )

        await self._add_event(event)

        # Update error metrics
        self._metrics.error_count += 1

    async def collect_custom_event(
        self,
        event_name: str,
        attributes: dict[str, t.Any] | None = None,
        request: GatewayRequest | None = None,
    ) -> None:
        """Collect custom event."""
        if not self._should_sample():
            return

        event = AnalyticsEvent(
            event_type=EventType.CUSTOM,
            request_id=request.request_id if request else None,
            tenant_id=request.tenant_id if request else None,
            client_id=self._extract_client_id(request) if request else None,
            method=request.method.value if request else None,
            path=self._sanitize_path(request.path) if request else None,
            component="custom",
            operation=event_name,
            attributes=attributes or {},
        )

        await self._add_event(event)

    async def get_metrics(self, tenant_id: str | None = None) -> AggregatedMetrics:
        """Get aggregated metrics."""
        if tenant_id:
            return self._tenant_metrics.get(tenant_id, AggregatedMetrics())

        # Calculate derived metrics
        self._calculate_derived_metrics()
        return self._metrics

    async def get_endpoint_metrics(self, endpoint: str | None = None) -> dict[str, AggregatedMetrics]:
        """Get per-endpoint metrics."""
        if endpoint:
            return {endpoint: self._endpoint_metrics.get(endpoint, AggregatedMetrics())}
        return dict(self._endpoint_metrics)

    async def get_recent_events(
        self,
        limit: int = 100,
        event_type: EventType | None = None,
        tenant_id: str | None = None,
    ) -> list[AnalyticsEvent]:
        """Get recent events."""
        events = list(self._events)

        # Filter by event type
        if event_type:
            events = [e for e in events if e.event_type == event_type]

        # Filter by tenant
        if tenant_id:
            events = [e for e in events if e.tenant_id == tenant_id]

        # Sort by timestamp and limit
        events.sort(key=lambda e: e.timestamp, reverse=True)
        return events[:limit]

    async def reset_metrics(self, tenant_id: str | None = None) -> None:
        """Reset metrics."""
        if tenant_id:
            if tenant_id in self._tenant_metrics:
                del self._tenant_metrics[tenant_id]
        else:
            self._metrics = AggregatedMetrics()
            self._tenant_metrics.clear()
            self._endpoint_metrics.clear()
            self._response_time_tracker = ResponseTimeTracker()

    async def export_metrics(self, format_type: str = "json") -> str | dict[str, t.Any]:
        """Export metrics in specified format."""
        metrics = await self.get_metrics()

        if format_type == "json":
            return metrics.to_dict()
        elif format_type == "prometheus":
            return self._export_prometheus_format(metrics)
        else:
            return metrics.to_dict()

    def _should_sample(self) -> bool:
        """Check if this request should be sampled."""
        if not self._config.enabled:
            return False

        if self._config.sampling_rate >= 1.0:
            return True

        self._sample_counter += 1
        return (self._sample_counter % int(1.0 / self._config.sampling_rate)) == 0

    async def _add_event(self, event: AnalyticsEvent) -> None:
        """Add event to collection."""
        self._events.append(event)

    async def _update_request_metrics(
        self,
        request: GatewayRequest,
        response: GatewayResponse,
        processing_time_ms: float,
    ) -> None:
        """Update aggregated request metrics."""
        # Global metrics
        self._metrics.total_requests += 1

        if response.is_success():
            self._metrics.successful_requests += 1
        else:
            self._metrics.failed_requests += 1

        # Response time tracking
        self._response_time_tracker.add_sample(processing_time_ms)
        self._update_response_time_metrics(processing_time_ms)

        # Status code distribution
        if response.status_code not in self._metrics.status_codes:
            self._metrics.status_codes[response.status_code] = 0
        self._metrics.status_codes[response.status_code] += 1

        # Tenant metrics
        if request.tenant_id:
            tenant_metrics = self._tenant_metrics[request.tenant_id]
            tenant_metrics.total_requests += 1
            if response.is_success():
                tenant_metrics.successful_requests += 1
            else:
                tenant_metrics.failed_requests += 1

        # Endpoint metrics
        endpoint = f"{request.method.value} {request.path}"
        endpoint_metrics = self._endpoint_metrics[endpoint]
        endpoint_metrics.total_requests += 1
        if response.is_success():
            endpoint_metrics.successful_requests += 1
        else:
            endpoint_metrics.failed_requests += 1

    def _update_response_time_metrics(self, response_time_ms: float) -> None:
        """Update response time metrics."""
        if self._metrics.total_requests == 1:
            self._metrics.avg_response_time_ms = response_time_ms
            self._metrics.min_response_time_ms = response_time_ms
            self._metrics.max_response_time_ms = response_time_ms
        else:
            # Running average
            self._metrics.avg_response_time_ms = (
                (self._metrics.avg_response_time_ms * (self._metrics.total_requests - 1) + response_time_ms)
                / self._metrics.total_requests
            )
            self._metrics.min_response_time_ms = min(self._metrics.min_response_time_ms, response_time_ms)
            self._metrics.max_response_time_ms = max(self._metrics.max_response_time_ms, response_time_ms)

    def _calculate_derived_metrics(self) -> None:
        """Calculate derived metrics."""
        # Error rate
        if self._metrics.total_requests > 0:
            self._metrics.error_rate = self._metrics.failed_requests / self._metrics.total_requests
            self._metrics.rate_limit_rate = self._metrics.rate_limited_requests / self._metrics.total_requests
            self._metrics.auth_success_rate = (self._metrics.total_requests - self._metrics.auth_failures) / self._metrics.total_requests

        # Cache hit rate
        total_cache_operations = self._metrics.cache_hits + self._metrics.cache_misses
        if total_cache_operations > 0:
            self._metrics.cache_hit_rate = self._metrics.cache_hits / total_cache_operations

        # Response time percentiles
        percentiles = self._response_time_tracker.get_percentiles()
        self._metrics.p50_response_time_ms = percentiles["p50"]
        self._metrics.p95_response_time_ms = percentiles["p95"]
        self._metrics.p99_response_time_ms = percentiles["p99"]

    def _extract_client_id(self, request: GatewayRequest) -> str | None:
        """Extract client ID from request."""
        return (
            request.headers.get("X-Client-ID") or
            request.api_key or
            request.client_ip
        )

    def _sanitize_path(self, path: str) -> str:
        """Sanitize path for analytics (remove sensitive data)."""
        # Check if path should be excluded
        for excluded_path in self._config.exclude_paths:
            if path.startswith(excluded_path):
                return "[excluded]"

        return path

    def _export_prometheus_format(self, metrics: AggregatedMetrics) -> str:
        """Export metrics in Prometheus format."""
        lines = [
            "# HELP gateway_requests_total Total number of requests processed",
            "# TYPE gateway_requests_total counter",
            f"gateway_requests_total {metrics.total_requests}",
            "",
            "# HELP gateway_request_duration_ms Request duration in milliseconds",
            "# TYPE gateway_request_duration_ms histogram",
            f"gateway_request_duration_ms_sum {metrics.avg_response_time_ms * metrics.total_requests}",
            f"gateway_request_duration_ms_count {metrics.total_requests}",
            "",
            "# HELP gateway_errors_total Total number of errors",
            "# TYPE gateway_errors_total counter",
            f"gateway_errors_total {metrics.error_count}",
        ]

        return "\n".join(lines)