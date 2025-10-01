"""Base classes for API Gateway adapter."""

import time
import typing as t
from dataclasses import dataclass, field
from enum import Enum

from pydantic import BaseModel, Field
from acb.config import Config
from acb.depends import depends

try:
    from uuid import uuid7
except ImportError:
    from uuid import uuid4 as uuid7


class GatewayStatus(str, Enum):
    """Gateway operational status."""

    INACTIVE = "inactive"
    ACTIVE = "active"
    DEGRADED = "degraded"
    ERROR = "error"


@dataclass
class GatewayMetrics:
    """Gateway performance metrics."""

    requests_total: int = 0
    requests_success: int = 0
    requests_failed: int = 0
    requests_rate_limited: int = 0
    requests_unauthorized: int = 0
    average_response_time: float = 0.0
    uptime_seconds: float = 0.0
    errors: list[str] = field(default_factory=list)


class GatewayConfig(BaseModel):
    """Configuration for API Gateway."""

    # Basic gateway settings
    enabled: bool = True
    host: str = "0.0.0.0"
    port: int = 8080
    debug: bool = False

    # Security settings
    cors_enabled: bool = True
    cors_origins: list[str] = ["*"]
    cors_methods: list[str] = ["GET", "POST", "PUT", "DELETE", "OPTIONS"]
    cors_headers: list[str] = ["*"]

    # Rate limiting
    rate_limiting_enabled: bool = True
    default_rate_limit: int = 100  # requests per minute
    rate_limit_window_seconds: int = 60

    # Authentication
    auth_enabled: bool = True
    auth_providers: list[str] = ["jwt", "api_key"]
    jwt_secret: str = Field(default="", description="JWT secret key")
    jwt_algorithm: str = "HS256"
    jwt_expiry_seconds: int = 3600

    # Usage tracking
    usage_tracking_enabled: bool = True
    usage_analytics_enabled: bool = True

    # Request/response validation
    validation_enabled: bool = True
    strict_validation: bool = False

    # Middleware
    middleware_enabled: bool = True
    custom_middleware: list[str] = field(default_factory=list)

    class Config:
        extra = "forbid"


class GatewaySettings(BaseModel):
    """Settings for API Gateway adapter."""

    gateway_config: GatewayConfig = Field(default_factory=GatewayConfig)
    cache_enabled: bool = True
    cache_ttl_seconds: int = 300
    redis_enabled: bool = True

    @depends.inject
    def __init__(self, config: Config = depends(), **values: t.Any) -> None:
        # Load gateway-specific configuration
        gateway_settings = config.get("gateway", {})
        if gateway_settings:
            values["gateway_config"] = GatewayConfig(**gateway_settings)
        super().__init__(**values)


class GatewayBase:
    """Base class for API Gateway components."""

    def __init__(self, settings: GatewaySettings | None = None) -> None:
        self.settings = settings or GatewaySettings()
        self.status = GatewayStatus.INACTIVE
        self.metrics = GatewayMetrics()
        self._start_time = time.time()
        self._component_id = str(uuid7())

    async def initialize(self) -> None:
        """Initialize the gateway component."""
        self.status = GatewayStatus.ACTIVE
        self._start_time = time.time()

    async def shutdown(self) -> None:
        """Shutdown the gateway component."""
        self.status = GatewayStatus.INACTIVE

    async def health_check(self) -> dict[str, t.Any]:
        """Perform health check."""
        self.metrics.uptime_seconds = time.time() - self._start_time

        return {
            "status": self.status.value,
            "component_id": self._component_id,
            "uptime_seconds": self.metrics.uptime_seconds,
            "requests_total": self.metrics.requests_total,
            "success_rate": (
                self.metrics.requests_success / max(1, self.metrics.requests_total)
            ),
            "error_count": len(self.metrics.errors),
        }

    def record_request(self, success: bool = True, response_time: float = 0.0) -> None:
        """Record a request in metrics."""
        self.metrics.requests_total += 1
        if success:
            self.metrics.requests_success += 1
        else:
            self.metrics.requests_failed += 1

        # Update average response time
        if response_time > 0:
            total_requests = self.metrics.requests_total
            current_avg = self.metrics.average_response_time
            self.metrics.average_response_time = (
                current_avg * (total_requests - 1) + response_time
            ) / total_requests

    def record_error(self, error: str) -> None:
        """Record an error."""
        self.metrics.errors.append(error)
        # Keep only last 100 errors
        if len(self.metrics.errors) > 100:
            self.metrics.errors = self.metrics.errors[-100:]
