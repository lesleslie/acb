"""Multi-tenant routing and traffic management for ACB Gateway.

This module provides comprehensive routing capabilities including:
- Path-based routing with pattern matching
- Multi-tenant routing with isolation
- Load balancing across upstream services
- Circuit breaker integration
- Health check integration
- Dynamic route configuration

Features:
- Flexible route matching (exact, prefix, regex)
- Multi-tenant isolation and routing
- Upstream service discovery
- Load balancing algorithms
- Health-aware routing
- Route-specific configuration
"""

from __future__ import annotations

import re
import time
import typing as t
from dataclasses import dataclass
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field
from acb.gateway._base import GatewayRequest, RequestMethod


class RouteType(Enum):
    """Route matching types."""

    EXACT = "exact"
    PREFIX = "prefix"
    REGEX = "regex"
    WILDCARD = "wildcard"


class LoadBalancingAlgorithm(Enum):
    """Load balancing algorithms."""

    ROUND_ROBIN = "round_robin"
    WEIGHTED_ROUND_ROBIN = "weighted_round_robin"
    LEAST_CONNECTIONS = "least_connections"
    RANDOM = "random"
    IP_HASH = "ip_hash"
    HEALTH_AWARE = "health_aware"


class UpstreamStatus(Enum):
    """Upstream service status."""

    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    DEGRADED = "degraded"
    UNKNOWN = "unknown"


@dataclass
class Upstream:
    """Upstream service configuration."""

    # Service details
    id: str
    url: str
    weight: int = 1
    priority: int = 1

    # Health check details
    status: UpstreamStatus = UpstreamStatus.UNKNOWN
    last_health_check: float = 0.0
    consecutive_failures: int = 0
    consecutive_successes: int = 0

    # Load balancing metrics
    active_connections: int = 0
    total_requests: int = 0
    average_response_time: float = 0.0

    # Timeout settings
    connect_timeout: float = 5.0
    read_timeout: float = 30.0

    # Circuit breaker state
    circuit_breaker_open: bool = False
    circuit_breaker_reset_time: float = 0.0

    def is_healthy(self) -> bool:
        """Check if upstream is healthy."""
        return self.status == UpstreamStatus.HEALTHY and not self.circuit_breaker_open

    def record_request(self, success: bool, response_time: float) -> None:
        """Record request metrics."""
        self.total_requests += 1

        if success:
            self.consecutive_failures = 0
            self.consecutive_successes += 1
            # Update average response time
            if self.total_requests == 1:
                self.average_response_time = response_time
            else:
                self.average_response_time = (
                    self.average_response_time * (self.total_requests - 1)
                    + response_time
                ) / self.total_requests
        else:
            self.consecutive_successes = 0
            self.consecutive_failures += 1


class RoutingConfig(BaseModel):
    """Routing configuration."""

    # Load balancing
    algorithm: LoadBalancingAlgorithm = LoadBalancingAlgorithm.ROUND_ROBIN
    health_check_enabled: bool = True
    health_check_interval: float = 30.0
    health_check_timeout: float = 5.0
    health_check_path: str = "/health"

    # Circuit breaker settings
    circuit_breaker_enabled: bool = True
    failure_threshold: int = 5
    success_threshold: int = 3
    timeout_duration: float = 60.0

    # Multi-tenancy
    enable_tenant_isolation: bool = True
    tenant_header: str = "X-Tenant-ID"
    default_tenant: str = "default"

    # Route overrides
    preserve_host_header: bool = False
    strip_path_prefix: bool = True
    add_request_headers: dict[str, str] = Field(default_factory=dict)
    remove_request_headers: list[str] = Field(default_factory=list)

    # Timeouts
    request_timeout: float = 30.0
    connect_timeout: float = 5.0

    model_config = ConfigDict(extra="forbid")


class Route(BaseModel):
    """Route definition."""

    # Route identification
    id: str
    name: str | None = None
    description: str | None = None

    # Route matching
    path_pattern: str
    route_type: RouteType = RouteType.PREFIX
    methods: list[RequestMethod] = Field(default_factory=lambda: [RequestMethod.GET])
    headers: dict[str, str] = Field(default_factory=dict)

    # Upstream configuration
    upstreams: list[Upstream] = Field(default_factory=list)
    default_upstream: str | None = None

    # Multi-tenancy
    tenant_id: str | None = None
    tenant_specific: bool = False

    # Route-specific settings
    config: RoutingConfig | None = None
    enabled: bool = True
    priority: int = 100

    # Rate limiting override
    rate_limit_override: dict[str, t.Any] | None = None

    # Authentication override
    auth_override: dict[str, t.Any] | None = None

    def matches(self, request: GatewayRequest) -> bool:
        """Check if route matches the request."""
        # Check method
        if request.method not in self.methods:
            return False

        # Check path
        if not self._matches_path(request.path):
            return False

        # Check headers
        for header_name, header_value in self.headers.items():
            request_value = request.headers.get(header_name)
            if request_value != header_value:
                return False

        # Check tenant isolation
        if self.tenant_specific and self.tenant_id:
            request_tenant = request.tenant_id or request.headers.get("X-Tenant-ID")
            if request_tenant != self.tenant_id:
                return False

        return True

    def _matches_path(self, path: str) -> bool:
        """Check if path matches the route pattern."""
        if self.route_type == RouteType.EXACT:
            return path == self.path_pattern
        if self.route_type == RouteType.PREFIX:
            return path.startswith(self.path_pattern)
        if self.route_type == RouteType.REGEX:
            try:
                pattern = re.compile(
                    self.path_pattern
                )  # REGEX OK: dynamic route pattern matching
                return bool(pattern.match(path))
            except re.error:
                return False
        elif self.route_type == RouteType.WILDCARD:
            # Simple wildcard matching (* and ?)
            pattern_str = self.path_pattern.replace("*", ".*").replace("?", ".")
            try:
                pattern = re.compile(
                    f"^{pattern_str}$"
                )  # REGEX OK: wildcard route pattern matching
                return bool(pattern.match(path))
            except re.error:
                return False
        else:
            return False

    def get_healthy_upstreams(self) -> list[Upstream]:
        """Get list of healthy upstreams."""
        return [upstream for upstream in self.upstreams if upstream.is_healthy()]

    model_config = ConfigDict(arbitrary_types_allowed=True)


class LoadBalancer:
    """Load balancing implementation."""

    def __init__(self) -> None:
        self._round_robin_counters: dict[str, int] = {}

    async def select_upstream(
        self,
        route: Route,
        request: GatewayRequest,
        config: RoutingConfig,
    ) -> Upstream | None:
        """Select an upstream using configured algorithm."""
        healthy_upstreams = route.get_healthy_upstreams()
        if not healthy_upstreams:
            return None

        algorithm = config.algorithm
        if algorithm == LoadBalancingAlgorithm.ROUND_ROBIN:
            return self._round_robin_selection(route.id, healthy_upstreams)
        if algorithm == LoadBalancingAlgorithm.WEIGHTED_ROUND_ROBIN:
            return self._weighted_round_robin_selection(route.id, healthy_upstreams)
        if algorithm == LoadBalancingAlgorithm.LEAST_CONNECTIONS:
            return self._least_connections_selection(healthy_upstreams)
        if algorithm == LoadBalancingAlgorithm.RANDOM:
            return self._random_selection(healthy_upstreams)
        if algorithm == LoadBalancingAlgorithm.IP_HASH:
            return self._ip_hash_selection(request, healthy_upstreams)
        if algorithm == LoadBalancingAlgorithm.HEALTH_AWARE:
            return self._health_aware_selection(healthy_upstreams)
        return self._round_robin_selection(route.id, healthy_upstreams)

    def _round_robin_selection(
        self,
        route_id: str,
        upstreams: list[Upstream],
    ) -> Upstream:
        """Round robin selection."""
        if route_id not in self._round_robin_counters:
            self._round_robin_counters[route_id] = 0

        index = self._round_robin_counters[route_id] % len(upstreams)
        self._round_robin_counters[route_id] += 1
        return upstreams[index]

    def _weighted_round_robin_selection(
        self,
        route_id: str,
        upstreams: list[Upstream],
    ) -> Upstream:
        """Weighted round robin selection."""
        # Calculate total weight
        total_weight = sum(upstream.weight for upstream in upstreams)

        if route_id not in self._round_robin_counters:
            self._round_robin_counters[route_id] = 0

        # Find weighted selection
        counter = self._round_robin_counters[route_id] % total_weight
        current_weight = 0

        for upstream in upstreams:
            current_weight += upstream.weight
            if counter < current_weight:
                self._round_robin_counters[route_id] += 1
                return upstream

        # Fallback to first upstream
        self._round_robin_counters[route_id] += 1
        return upstreams[0]

    def _least_connections_selection(self, upstreams: list[Upstream]) -> Upstream:
        """Least connections selection."""
        return min(upstreams, key=lambda u: u.active_connections)

    def _random_selection(self, upstreams: list[Upstream]) -> Upstream:
        """Random selection."""
        import random

        return random.choice(upstreams)

    def _ip_hash_selection(
        self,
        request: GatewayRequest,
        upstreams: list[Upstream],
    ) -> Upstream:
        """IP hash-based selection."""
        client_ip = request.client_ip or "unknown"
        hash_value = hash(client_ip)
        index = hash_value % len(upstreams)
        return upstreams[index]

    def _health_aware_selection(self, upstreams: list[Upstream]) -> Upstream:
        """Health-aware selection (prefer faster responses)."""
        # Sort by average response time and select the fastest
        sorted_upstreams = sorted(
            upstreams,
            key=lambda u: u.average_response_time or float("inf"),
        )
        return sorted_upstreams[0]


class CircuitBreaker:
    """Circuit breaker implementation for upstream protection."""

    def __init__(self) -> None:
        pass

    async def check_circuit_breaker(
        self,
        upstream: Upstream,
        config: RoutingConfig,
    ) -> bool:
        """Check if circuit breaker allows the request."""
        if not config.circuit_breaker_enabled:
            return True

        current_time = time.time()

        # Check if circuit breaker is open
        if upstream.circuit_breaker_open:
            # Check if timeout has passed
            if current_time >= upstream.circuit_breaker_reset_time:
                # Reset circuit breaker
                upstream.circuit_breaker_open = False
                upstream.consecutive_failures = 0
                return True
            return False

        # Check failure threshold
        if upstream.consecutive_failures >= config.failure_threshold:
            # Open circuit breaker
            upstream.circuit_breaker_open = True
            upstream.circuit_breaker_reset_time = current_time + config.timeout_duration
            return False

        return True

    async def record_result(
        self,
        upstream: Upstream,
        config: RoutingConfig,
        success: bool,
        response_time: float,
    ) -> None:
        """Record request result for circuit breaker logic."""
        upstream.record_request(success, response_time)

        if not config.circuit_breaker_enabled:
            return

        if success:
            # Check if we can close the circuit breaker
            if (
                upstream.circuit_breaker_open
                and upstream.consecutive_successes >= config.success_threshold
            ):
                upstream.circuit_breaker_open = False
                upstream.circuit_breaker_reset_time = 0.0
        # Check if we need to open the circuit breaker
        elif upstream.consecutive_failures >= config.failure_threshold:
            upstream.circuit_breaker_open = True
            upstream.circuit_breaker_reset_time = time.time() + config.timeout_duration


class RoutingEngine:
    """Main routing engine for request routing and load balancing."""

    def __init__(self) -> None:
        self._routes: list[Route] = []
        self._load_balancer = LoadBalancer()
        self._circuit_breaker = CircuitBreaker()

    async def find_route(
        self,
        request: GatewayRequest,
        tenant_id: str | None = None,
    ) -> Route | None:
        """Find matching route for the request."""
        # Filter routes by tenant if specified
        candidate_routes = []

        for route in self._routes:
            if not route.enabled:
                continue

            # Check tenant isolation
            if tenant_id:
                if route.tenant_specific and route.tenant_id != tenant_id:
                    continue

            if route.matches(request):
                candidate_routes.append(route)

        if not candidate_routes:
            return None

        # Sort by priority (lower = higher priority)
        candidate_routes.sort(key=lambda r: r.priority)
        return candidate_routes[0]

    async def select_upstream(
        self,
        route: Route,
        request: GatewayRequest,
        config: RoutingConfig | None = None,
    ) -> Upstream | None:
        """Select an upstream for the route."""
        routing_config = config or route.config or RoutingConfig()

        # Get healthy upstreams
        healthy_upstreams = route.get_healthy_upstreams()
        if not healthy_upstreams:
            return None

        # Filter by circuit breaker
        available_upstreams = [
            upstream
            for upstream in healthy_upstreams
            if await self._circuit_breaker.check_circuit_breaker(
                upstream,
                routing_config,
            )
        ]

        if not available_upstreams:
            return None

        # Select using load balancing algorithm
        return await self._load_balancer.select_upstream(
            route,
            request,
            routing_config,
        )

    async def build_upstream_url(
        self,
        upstream: Upstream,
        request: GatewayRequest,
        route: Route,
        config: RoutingConfig | None = None,
    ) -> str:
        """Build the upstream URL for the request."""
        routing_config = config or route.config or RoutingConfig()

        # Get the target path
        target_path = request.path
        if routing_config.strip_path_prefix and route.route_type == RouteType.PREFIX:
            # Remove the route prefix from the path
            if target_path.startswith(route.path_pattern):
                target_path = target_path[len(route.path_pattern) :]
                if not target_path.startswith("/"):
                    target_path = "/" + target_path

        # Build query string
        query_string = ""
        if request.query_params:
            query_parts = [
                f"{key}={value}" for key, value in request.query_params.items()
            ]
            query_string = "?" + "&".join(query_parts)

        # Combine URL
        return upstream.url.rstrip("/") + target_path + query_string

    async def transform_request(
        self,
        request: GatewayRequest,
        route: Route,
        upstream: Upstream,
        config: RoutingConfig | None = None,
    ) -> GatewayRequest:
        """Transform request for upstream."""
        routing_config = config or route.config or RoutingConfig()

        # Create a copy of the request
        transformed_request = GatewayRequest(
            method=request.method,
            path=request.path,
            query_params=request.query_params.copy(),
            headers=request.headers.copy(),
            body=request.body,
            client_ip=request.client_ip,
            user_agent=request.user_agent,
            api_key=request.api_key,
            bearer_token=request.bearer_token,
            auth_user=request.auth_user,
            request_id=request.request_id,
            tenant_id=request.tenant_id,
            timestamp=request.timestamp,
        )

        # Add headers
        for header_name, header_value in routing_config.add_request_headers.items():
            transformed_request.headers[header_name] = header_value

        # Remove headers
        for header_name in routing_config.remove_request_headers:
            transformed_request.headers.pop(header_name, None)

        # Preserve or update host header
        if not routing_config.preserve_host_header:
            from urllib.parse import urlparse

            parsed_url = urlparse(upstream.url)
            if parsed_url.hostname:
                transformed_request.headers["Host"] = parsed_url.hostname

        return transformed_request

    async def record_upstream_result(
        self,
        upstream: Upstream,
        success: bool,
        response_time: float,
        config: RoutingConfig | None = None,
    ) -> None:
        """Record upstream request result."""
        routing_config = config or RoutingConfig()
        await self._circuit_breaker.record_result(
            upstream,
            routing_config,
            success,
            response_time,
        )

    def add_route(self, route: Route) -> None:
        """Add a route to the routing table."""
        self._routes.append(route)
        # Sort routes by priority
        self._routes.sort(key=lambda r: r.priority)

    def remove_route(self, route_id: str) -> bool:
        """Remove a route from the routing table."""
        for i, route in enumerate(self._routes):
            if route.id == route_id:
                del self._routes[i]
                return True
        return False

    def get_route(self, route_id: str) -> Route | None:
        """Get a route by ID."""
        for route in self._routes:
            if route.id == route_id:
                return route
        return None

    def list_routes(self, tenant_id: str | None = None) -> list[Route]:
        """List all routes, optionally filtered by tenant."""
        if tenant_id is None:
            return self._routes.copy()

        return [
            route
            for route in self._routes
            if not route.tenant_specific or route.tenant_id == tenant_id
        ]

    def get_route_metrics(self, route_id: str) -> dict[str, t.Any]:
        """Get metrics for a specific route."""
        route = self.get_route(route_id)
        if not route:
            return {}

        upstream_metrics = [
            {
                "id": upstream.id,
                "url": upstream.url,
                "status": upstream.status.value,
                "active_connections": upstream.active_connections,
                "total_requests": upstream.total_requests,
                "average_response_time": upstream.average_response_time,
                "consecutive_failures": upstream.consecutive_failures,
                "consecutive_successes": upstream.consecutive_successes,
                "circuit_breaker_open": upstream.circuit_breaker_open,
            }
            for upstream in route.upstreams
        ]

        return {
            "route_id": route.id,
            "enabled": route.enabled,
            "upstreams": upstream_metrics,
        }
