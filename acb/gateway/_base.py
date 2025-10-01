"""Base classes and protocols for ACB Gateway system.

This module provides the foundational abstractions for gateway functionality,
including configuration, protocols, and result types.
"""

from __future__ import annotations

import time
import typing as t
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field
from acb.config import Settings
from acb.depends import depends


class GatewayLevel(Enum):
    """Gateway processing levels."""

    BASIC = "basic"  # Basic routing and forwarding
    STANDARD = "standard"  # Add authentication and basic security
    ENHANCED = "enhanced"  # Add rate limiting and validation
    ENTERPRISE = "enterprise"  # Full feature set with analytics


class RequestMethod(Enum):
    """HTTP request methods."""

    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    DELETE = "DELETE"
    PATCH = "PATCH"
    HEAD = "HEAD"
    OPTIONS = "OPTIONS"
    TRACE = "TRACE"
    CONNECT = "CONNECT"


class GatewayStatus(Enum):
    """Gateway response status."""

    SUCCESS = "success"
    RATE_LIMITED = "rate_limited"
    UNAUTHORIZED = "unauthorized"
    FORBIDDEN = "forbidden"
    VALIDATION_FAILED = "validation_failed"
    ROUTING_FAILED = "routing_failed"
    UPSTREAM_ERROR = "upstream_error"
    GATEWAY_ERROR = "gateway_error"


@dataclass
class GatewayMetrics:
    """Gateway performance and usage metrics."""

    requests_processed: int = 0
    requests_blocked: int = 0
    rate_limit_hits: int = 0
    auth_failures: int = 0
    validation_failures: int = 0
    routing_failures: int = 0
    upstream_errors: int = 0

    # Performance metrics
    avg_response_time_ms: float = 0.0
    min_response_time_ms: float = float("inf")
    max_response_time_ms: float = 0.0

    # Cache metrics
    cache_hits: int = 0
    cache_misses: int = 0

    # Security metrics
    security_violations: int = 0
    cors_violations: int = 0

    # Custom metrics
    custom_metrics: dict[str, t.Any] = field(default_factory=dict)

    def record_request(
        self,
        success: bool,
        response_time_ms: float,
        status: GatewayStatus | None = None,
    ) -> None:
        """Record a request and its performance metrics."""
        self.requests_processed += 1

        if not success:
            self.requests_blocked += 1

        # Update response time metrics
        if response_time_ms > 0:
            if self.requests_processed == 1:
                self.avg_response_time_ms = response_time_ms
                self.min_response_time_ms = response_time_ms
                self.max_response_time_ms = response_time_ms
            else:
                # Running average
                self.avg_response_time_ms = (
                    self.avg_response_time_ms * (self.requests_processed - 1)
                    + response_time_ms
                ) / self.requests_processed
                self.min_response_time_ms = min(
                    self.min_response_time_ms,
                    response_time_ms,
                )
                self.max_response_time_ms = max(
                    self.max_response_time_ms,
                    response_time_ms,
                )

        # Update status-specific metrics
        if status:
            if status == GatewayStatus.RATE_LIMITED:
                self.rate_limit_hits += 1
            elif status == GatewayStatus.UNAUTHORIZED:
                self.auth_failures += 1
            elif status == GatewayStatus.VALIDATION_FAILED:
                self.validation_failures += 1
            elif status == GatewayStatus.ROUTING_FAILED:
                self.routing_failures += 1
            elif status == GatewayStatus.UPSTREAM_ERROR:
                self.upstream_errors += 1

    def to_dict(self) -> dict[str, t.Any]:
        """Convert metrics to dictionary format."""
        return {
            "requests_processed": self.requests_processed,
            "requests_blocked": self.requests_blocked,
            "rate_limit_hits": self.rate_limit_hits,
            "auth_failures": self.auth_failures,
            "validation_failures": self.validation_failures,
            "routing_failures": self.routing_failures,
            "upstream_errors": self.upstream_errors,
            "avg_response_time_ms": self.avg_response_time_ms,
            "min_response_time_ms": self.min_response_time_ms
            if self.min_response_time_ms != float("inf")
            else 0.0,
            "max_response_time_ms": self.max_response_time_ms,
            "cache_hits": self.cache_hits,
            "cache_misses": self.cache_misses,
            "security_violations": self.security_violations,
            "cors_violations": self.cors_violations,
            "custom_metrics": self.custom_metrics,
        }


class GatewaySettings(Settings):
    """Gateway configuration settings."""

    # Core gateway settings
    enabled: bool = True
    level: GatewayLevel = GatewayLevel.STANDARD
    timeout: float = 30.0
    max_request_size: int = 10 * 1024 * 1024  # 10MB

    # Performance settings
    enable_performance_monitoring: bool = True
    performance_threshold_ms: float = 1000.0

    # Rate limiting settings
    enable_rate_limiting: bool = True
    global_rate_limit: int = 1000  # requests per minute
    burst_limit: int = 100

    # Authentication settings
    enable_authentication: bool = True
    require_api_key: bool = False
    jwt_secret: str | None = None

    # Validation settings
    enable_request_validation: bool = True
    enable_response_validation: bool = False

    # Security settings
    enable_cors: bool = True
    allowed_origins: list[str] = field(default_factory=lambda: ["*"])
    allowed_methods: list[str] = field(
        default_factory=lambda: ["GET", "POST", "PUT", "DELETE"],
    )
    allowed_headers: list[str] = field(default_factory=lambda: ["*"])

    # Caching settings
    enable_caching: bool = True
    cache_ttl: int = 300  # 5 minutes

    # Analytics settings
    enable_analytics: bool = True
    analytics_sampling_rate: float = 1.0  # 100% sampling

    # Multi-tenancy settings
    enable_multi_tenancy: bool = False
    tenant_header: str = "X-Tenant-ID"

    @depends.inject
    def __init__(self, **values: t.Any) -> None:
        super().__init__(**values)


class GatewayConfig(BaseModel):
    """Gateway request/response configuration."""

    level: GatewayLevel = GatewayLevel.STANDARD
    enable_rate_limiting: bool = True
    enable_authentication: bool = True
    enable_validation: bool = True
    enable_caching: bool = True
    enable_analytics: bool = True
    enable_security_headers: bool = True

    # Request-specific overrides
    max_request_size: int | None = None
    timeout: float | None = None
    rate_limit_override: int | None = None

    # Security overrides
    cors_override: dict[str, t.Any] | None = None
    require_https: bool = False

    # Tenant context
    tenant_id: str | None = None
    tenant_config: dict[str, t.Any] | None = None

    model_config = ConfigDict(extra="forbid")


@dataclass
class GatewayRequest:
    """Gateway request representation."""

    # HTTP details
    method: RequestMethod
    path: str
    query_params: dict[str, str] = field(default_factory=dict)
    headers: dict[str, str] = field(default_factory=dict)
    body: bytes | str | dict[str, t.Any] | None = None

    # Client details
    client_ip: str | None = None
    user_agent: str | None = None

    # Authentication details
    api_key: str | None = None
    bearer_token: str | None = None
    auth_user: dict[str, t.Any] | None = None

    # Gateway context
    request_id: str | None = None
    tenant_id: str | None = None
    timestamp: float = field(default_factory=time.time)

    # Processing flags
    skip_rate_limiting: bool = False
    skip_authentication: bool = False
    skip_validation: bool = False
    skip_caching: bool = False

    @property
    def content_type(self) -> str | None:
        """Get request content type."""
        return self.headers.get("content-type") or self.headers.get("Content-Type")

    @property
    def content_length(self) -> int:
        """Get request content length."""
        length_header = self.headers.get("content-length") or self.headers.get(
            "Content-Length",
        )
        if length_header:
            try:
                return int(length_header)
            except ValueError:
                pass

        if isinstance(self.body, bytes):
            return len(self.body)
        if isinstance(self.body, str):
            return len(self.body.encode("utf-8"))
        if self.body is not None:
            # Estimate for dict/object
            import json

            return len(json.dumps(self.body).encode("utf-8"))

        return 0


@dataclass
class GatewayResponse:
    """Gateway response representation."""

    # HTTP response details
    status_code: int
    headers: dict[str, str] = field(default_factory=dict)
    body: bytes | str | dict[str, t.Any] | None = None

    # Gateway processing details
    gateway_status: GatewayStatus = GatewayStatus.SUCCESS
    processing_time_ms: float = 0.0

    # Error details
    error_message: str | None = None
    error_code: str | None = None

    # Cache details
    cache_hit: bool = False
    cache_ttl: int | None = None

    # Upstream details
    upstream_url: str | None = None
    upstream_status: int | None = None
    upstream_time_ms: float = 0.0

    # Request context
    request_id: str | None = None
    tenant_id: str | None = None

    def is_success(self) -> bool:
        """Check if response indicates success."""
        return (
            self.gateway_status == GatewayStatus.SUCCESS
            and 200 <= self.status_code < 400
        )

    def is_client_error(self) -> bool:
        """Check if response indicates client error."""
        return 400 <= self.status_code < 500

    def is_server_error(self) -> bool:
        """Check if response indicates server error."""
        return self.status_code >= 500


class GatewayResult(BaseModel):
    """Gateway processing result."""

    # Processing outcome
    success: bool
    status: GatewayStatus
    message: str | None = None

    # Request/response
    request: GatewayRequest | None = None
    response: GatewayResponse | None = None

    # Processing details
    processing_time_ms: float = 0.0
    components_used: list[str] = Field(default_factory=list)

    # Errors and warnings
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

    # Context information
    tenant_id: str | None = None
    request_id: str | None = None

    def add_error(self, error: str) -> None:
        """Add an error message."""
        self.errors.append(error)
        self.success = False

    def add_warning(self, warning: str) -> None:
        """Add a warning message."""
        self.warnings.append(warning)

    def add_component_used(self, component: str) -> None:
        """Track which gateway components were used."""
        if component not in self.components_used:
            self.components_used.append(component)

    model_config = ConfigDict(arbitrary_types_allowed=True)


class GatewayProtocol(ABC):
    """Protocol defining the gateway interface."""

    @abstractmethod
    async def process_request(
        self,
        request: GatewayRequest,
        config: GatewayConfig | None = None,
    ) -> GatewayResult:
        """Process a gateway request through the complete pipeline.

        Args:
            request: The gateway request to process
            config: Optional configuration overrides

        Returns:
            GatewayResult with processing outcome
        """
        ...

    @abstractmethod
    async def validate_request(
        self,
        request: GatewayRequest,
        config: GatewayConfig | None = None,
    ) -> GatewayResult:
        """Validate a request without full processing.

        Args:
            request: The gateway request to validate
            config: Optional configuration overrides

        Returns:
            GatewayResult with validation outcome
        """
        ...

    @abstractmethod
    async def get_metrics(self) -> GatewayMetrics:
        """Get current gateway metrics.

        Returns:
            Current gateway metrics
        """
        ...

    @abstractmethod
    async def reset_metrics(self) -> None:
        """Reset gateway metrics."""
        ...


class MiddlewareProtocol(ABC):
    """Protocol for gateway middleware components."""

    @abstractmethod
    async def process(
        self,
        request: GatewayRequest,
        config: GatewayConfig,
        next_middleware: t.Callable[
            [GatewayRequest, GatewayConfig],
            t.Awaitable[GatewayResult],
        ],
    ) -> GatewayResult:
        """Process request through middleware.

        Args:
            request: The gateway request
            config: Gateway configuration
            next_middleware: Next middleware in the chain

        Returns:
            GatewayResult from processing
        """
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        """Get middleware name."""
        ...

    @property
    @abstractmethod
    def priority(self) -> int:
        """Get middleware priority (lower = earlier in chain)."""
        ...


class RouteProtocol(ABC):
    """Protocol for route definitions."""

    @abstractmethod
    def matches(self, request: GatewayRequest) -> bool:
        """Check if route matches the request.

        Args:
            request: The gateway request

        Returns:
            True if route matches, False otherwise
        """
        ...

    @abstractmethod
    async def handle(
        self,
        request: GatewayRequest,
        config: GatewayConfig,
    ) -> GatewayResponse:
        """Handle the matched request.

        Args:
            request: The gateway request
            config: Gateway configuration

        Returns:
            GatewayResponse from handling
        """
        ...

    @property
    @abstractmethod
    def path_pattern(self) -> str:
        """Get route path pattern."""
        ...

    @property
    @abstractmethod
    def methods(self) -> list[RequestMethod]:
        """Get supported HTTP methods."""
        ...
