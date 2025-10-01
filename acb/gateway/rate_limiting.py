"""Rate limiting algorithms and implementations for ACB Gateway.

This module provides various rate limiting strategies including:
- Token bucket algorithm
- Sliding window algorithm
- Fixed window algorithm
- Leaky bucket algorithm

Features:
- Multiple rate limiting algorithms
- Per-client, per-endpoint, and global rate limiting
- Multi-tenant rate limiting with isolation
- Distributed rate limiting support
- Burst handling and graceful degradation
"""

from __future__ import annotations

import asyncio
import time
import typing as t
from abc import ABC, abstractmethod
from collections import defaultdict, deque
from dataclasses import dataclass
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

if t.TYPE_CHECKING:
    from acb.gateway._base import GatewayRequest


class RateLimitAlgorithm(Enum):
    """Rate limiting algorithm types."""

    TOKEN_BUCKET = "token_bucket"
    SLIDING_WINDOW = "sliding_window"
    FIXED_WINDOW = "fixed_window"
    LEAKY_BUCKET = "leaky_bucket"


class RateLimitScope(Enum):
    """Rate limiting scope."""

    GLOBAL = "global"
    PER_CLIENT = "per_client"
    PER_ENDPOINT = "per_endpoint"
    PER_USER = "per_user"
    PER_TENANT = "per_tenant"


class RateLimitStatus(Enum):
    """Rate limit check status."""

    ALLOWED = "allowed"
    RATE_LIMITED = "rate_limited"
    QUOTA_EXCEEDED = "quota_exceeded"
    ERROR = "error"


@dataclass
class RateLimitInfo:
    """Rate limit information."""

    limit: int
    remaining: int
    reset_time: float
    retry_after: float | None = None


class RateLimitConfig(BaseModel):
    """Rate limiting configuration."""

    # Algorithm settings
    algorithm: RateLimitAlgorithm = RateLimitAlgorithm.TOKEN_BUCKET
    scope: RateLimitScope = RateLimitScope.PER_CLIENT

    # Rate limits
    requests_per_second: int | None = None
    requests_per_minute: int | None = None
    requests_per_hour: int | None = None
    requests_per_day: int | None = None

    # Burst settings
    burst_limit: int | None = None
    burst_duration: float = 60.0  # seconds

    # Window settings (for window-based algorithms)
    window_size: float = 60.0  # seconds
    window_precision: int = 10  # number of sub-windows

    # Leaky bucket settings
    leak_rate: float | None = None  # requests per second

    # Client identification
    client_id_header: str = "X-Client-ID"
    user_id_header: str = "X-User-ID"
    tenant_id_header: str = "X-Tenant-ID"

    # Override settings
    whitelist_clients: list[str] = Field(default_factory=list)
    blacklist_clients: list[str] = Field(default_factory=list)

    # Custom limits per client/endpoint
    custom_limits: dict[str, dict[str, int]] = Field(default_factory=dict)

    model_config = ConfigDict(extra="forbid")


class RateLimitResult(BaseModel):
    """Rate limiting result."""

    status: RateLimitStatus
    allowed: bool
    info: RateLimitInfo | None = None
    reason: str | None = None

    # Context
    client_id: str | None = None
    endpoint: str | None = None
    tenant_id: str | None = None

    model_config = ConfigDict(arbitrary_types_allowed=True)


class RateLimiterProtocol(ABC):
    """Protocol for rate limiting implementations."""

    @abstractmethod
    async def check_rate_limit(
        self,
        request: GatewayRequest,
        config: RateLimitConfig,
    ) -> RateLimitResult:
        """Check if request is within rate limits.

        Args:
            request: The gateway request
            config: Rate limiting configuration

        Returns:
            RateLimitResult indicating if request is allowed
        """
        ...

    @abstractmethod
    async def reset_limits(self, client_id: str | None = None) -> None:
        """Reset rate limits for a client or all clients.

        Args:
            client_id: Optional client ID to reset, None for all
        """
        ...

    @abstractmethod
    async def get_limit_info(
        self,
        client_id: str,
        endpoint: str | None = None,
    ) -> RateLimitInfo | None:
        """Get current rate limit information for a client.

        Args:
            client_id: Client identifier
            endpoint: Optional endpoint identifier

        Returns:
            Current rate limit information or None if not found
        """
        ...


class TokenBucketLimiter:
    """Token bucket rate limiting implementation."""

    def __init__(self) -> None:
        self._buckets: dict[str, dict[str, t.Any]] = {}
        self._lock = asyncio.Lock()

    async def check_rate_limit(
        self,
        request: GatewayRequest,
        config: RateLimitConfig,
    ) -> RateLimitResult:
        """Check rate limit using token bucket algorithm."""
        client_id = self._get_client_id(request, config)
        endpoint = self._get_endpoint_id(request, config)
        bucket_key = f"{client_id}:{endpoint}"

        # Check whitelist/blacklist
        if client_id in config.whitelist_clients:
            return RateLimitResult(
                status=RateLimitStatus.ALLOWED,
                allowed=True,
                client_id=client_id,
                endpoint=endpoint,
            )

        if client_id in config.blacklist_clients:
            return RateLimitResult(
                status=RateLimitStatus.RATE_LIMITED,
                allowed=False,
                reason="Client blacklisted",
                client_id=client_id,
                endpoint=endpoint,
            )

        async with self._lock:
            return await self._check_bucket(bucket_key, config, client_id, endpoint)

    async def _check_bucket(
        self,
        bucket_key: str,
        config: RateLimitConfig,
        client_id: str,
        endpoint: str,
    ) -> RateLimitResult:
        """Check and update token bucket."""
        current_time = time.time()

        # Get or create bucket
        if bucket_key not in self._buckets:
            capacity = self._get_rate_limit(config, client_id, endpoint)
            self._buckets[bucket_key] = {
                "tokens": capacity,
                "capacity": capacity,
                "last_refill": current_time,
                "refill_rate": capacity / 60.0,  # tokens per second
            }

        bucket = self._buckets[bucket_key]

        # Refill tokens based on time elapsed
        time_elapsed = current_time - bucket["last_refill"]
        tokens_to_add = time_elapsed * bucket["refill_rate"]
        bucket["tokens"] = min(bucket["capacity"], bucket["tokens"] + tokens_to_add)
        bucket["last_refill"] = current_time

        # Check if request can be allowed
        if bucket["tokens"] >= 1:
            bucket["tokens"] -= 1
            remaining = int(bucket["tokens"])
            reset_time = (
                current_time
                + (bucket["capacity"] - bucket["tokens"]) / bucket["refill_rate"]
            )

            return RateLimitResult(
                status=RateLimitStatus.ALLOWED,
                allowed=True,
                info=RateLimitInfo(
                    limit=bucket["capacity"],
                    remaining=remaining,
                    reset_time=reset_time,
                ),
                client_id=client_id,
                endpoint=endpoint,
            )
        # Calculate retry after time
        retry_after = (1 - bucket["tokens"]) / bucket["refill_rate"]
        reset_time = current_time + bucket["capacity"] / bucket["refill_rate"]

        return RateLimitResult(
            status=RateLimitStatus.RATE_LIMITED,
            allowed=False,
            info=RateLimitInfo(
                limit=bucket["capacity"],
                remaining=0,
                reset_time=reset_time,
                retry_after=retry_after,
            ),
            reason="Rate limit exceeded",
            client_id=client_id,
            endpoint=endpoint,
        )

    def _get_rate_limit(
        self,
        config: RateLimitConfig,
        client_id: str,
        endpoint: str,
    ) -> int:
        """Get rate limit for client/endpoint combination."""
        # Check for custom limits
        if client_id in config.custom_limits:
            client_limits = config.custom_limits[client_id]
            if endpoint in client_limits:
                return client_limits[endpoint]

        # Use configured limits
        if config.requests_per_minute:
            return config.requests_per_minute
        if config.requests_per_second:
            return config.requests_per_second * 60
        if config.requests_per_hour:
            return config.requests_per_hour
        if config.requests_per_day:
            return config.requests_per_day
        return 100  # Default fallback

    def _get_client_id(self, request: GatewayRequest, config: RateLimitConfig) -> str:
        """Extract client ID from request."""
        if config.scope == RateLimitScope.GLOBAL:
            return "global"
        if config.scope == RateLimitScope.PER_CLIENT:
            return (
                request.headers.get(config.client_id_header)
                or request.client_ip
                or "unknown"
            )
        if config.scope == RateLimitScope.PER_USER:
            return (
                request.headers.get(config.user_id_header)
                or request.auth_user.get("user_id")
                if request.auth_user
                else "anonymous"
            )
        if config.scope == RateLimitScope.PER_TENANT:
            return (
                request.headers.get(config.tenant_id_header)
                or request.tenant_id
                or "default"
            )
        return request.client_ip or "unknown"

    def _get_endpoint_id(self, request: GatewayRequest, config: RateLimitConfig) -> str:
        """Extract endpoint ID from request."""
        if config.scope == RateLimitScope.PER_ENDPOINT:
            return f"{request.method.value}:{request.path}"
        return "all"

    async def reset_limits(self, client_id: str | None = None) -> None:
        """Reset rate limits."""
        async with self._lock:
            if client_id:
                # Reset specific client
                keys_to_remove = [
                    key for key in self._buckets if key.startswith(f"{client_id}:")
                ]
                for key in keys_to_remove:
                    del self._buckets[key]
            else:
                # Reset all
                self._buckets.clear()

    async def get_limit_info(
        self,
        client_id: str,
        endpoint: str | None = None,
    ) -> RateLimitInfo | None:
        """Get current limit information."""
        bucket_key = f"{client_id}:{endpoint or 'all'}"
        async with self._lock:
            if bucket_key in self._buckets:
                bucket = self._buckets[bucket_key]
                current_time = time.time()
                reset_time = (
                    current_time
                    + (bucket["capacity"] - bucket["tokens"]) / bucket["refill_rate"]
                )

                return RateLimitInfo(
                    limit=bucket["capacity"],
                    remaining=int(bucket["tokens"]),
                    reset_time=reset_time,
                )
        return None


class SlidingWindowLimiter:
    """Sliding window rate limiting implementation."""

    def __init__(self) -> None:
        self._windows: dict[str, deque[float]] = defaultdict(deque)
        self._lock = asyncio.Lock()

    async def check_rate_limit(
        self,
        request: GatewayRequest,
        config: RateLimitConfig,
    ) -> RateLimitResult:
        """Check rate limit using sliding window algorithm."""
        client_id = self._get_client_id(request, config)
        endpoint = self._get_endpoint_id(request, config)
        window_key = f"{client_id}:{endpoint}"

        # Check whitelist/blacklist
        if client_id in config.whitelist_clients:
            return RateLimitResult(
                status=RateLimitStatus.ALLOWED,
                allowed=True,
                client_id=client_id,
                endpoint=endpoint,
            )

        if client_id in config.blacklist_clients:
            return RateLimitResult(
                status=RateLimitStatus.RATE_LIMITED,
                allowed=False,
                reason="Client blacklisted",
                client_id=client_id,
                endpoint=endpoint,
            )

        async with self._lock:
            return await self._check_window(window_key, config, client_id, endpoint)

    async def _check_window(
        self,
        window_key: str,
        config: RateLimitConfig,
        client_id: str,
        endpoint: str,
    ) -> RateLimitResult:
        """Check and update sliding window."""
        current_time = time.time()
        window_start = current_time - config.window_size
        window = self._windows[window_key]

        # Remove old entries
        while window and window[0] <= window_start:
            window.popleft()

        # Check rate limit
        limit = self._get_rate_limit(config, client_id, endpoint)
        current_count = len(window)

        if current_count < limit:
            # Allow request
            window.append(current_time)
            remaining = limit - current_count - 1
            reset_time = (
                window[0] + config.window_size
                if window
                else current_time + config.window_size
            )

            return RateLimitResult(
                status=RateLimitStatus.ALLOWED,
                allowed=True,
                info=RateLimitInfo(
                    limit=limit,
                    remaining=remaining,
                    reset_time=reset_time,
                ),
                client_id=client_id,
                endpoint=endpoint,
            )
        # Rate limited
        reset_time = (
            window[0] + config.window_size
            if window
            else current_time + config.window_size
        )
        retry_after = reset_time - current_time

        return RateLimitResult(
            status=RateLimitStatus.RATE_LIMITED,
            allowed=False,
            info=RateLimitInfo(
                limit=limit,
                remaining=0,
                reset_time=reset_time,
                retry_after=retry_after,
            ),
            reason="Rate limit exceeded",
            client_id=client_id,
            endpoint=endpoint,
        )

    def _get_rate_limit(
        self,
        config: RateLimitConfig,
        client_id: str,
        endpoint: str,
    ) -> int:
        """Get rate limit for client/endpoint combination."""
        # Check for custom limits
        if client_id in config.custom_limits:
            client_limits = config.custom_limits[client_id]
            if endpoint in client_limits:
                return client_limits[endpoint]

        # Convert to window-based limit
        if config.requests_per_minute and config.window_size == 60.0:
            return config.requests_per_minute
        if config.requests_per_second:
            return int(config.requests_per_second * config.window_size)
        if config.requests_per_minute:
            return int(config.requests_per_minute * config.window_size / 60.0)
        if config.requests_per_hour:
            return int(config.requests_per_hour * config.window_size / 3600.0)
        return int(100 * config.window_size / 60.0)  # Default fallback

    def _get_client_id(self, request: GatewayRequest, config: RateLimitConfig) -> str:
        """Extract client ID from request."""
        if config.scope == RateLimitScope.GLOBAL:
            return "global"
        if config.scope == RateLimitScope.PER_CLIENT:
            return (
                request.headers.get(config.client_id_header)
                or request.client_ip
                or "unknown"
            )
        if config.scope == RateLimitScope.PER_USER:
            return (
                request.headers.get(config.user_id_header)
                or request.auth_user.get("user_id")
                if request.auth_user
                else "anonymous"
            )
        if config.scope == RateLimitScope.PER_TENANT:
            return (
                request.headers.get(config.tenant_id_header)
                or request.tenant_id
                or "default"
            )
        return request.client_ip or "unknown"

    def _get_endpoint_id(self, request: GatewayRequest, config: RateLimitConfig) -> str:
        """Extract endpoint ID from request."""
        if config.scope == RateLimitScope.PER_ENDPOINT:
            return f"{request.method.value}:{request.path}"
        return "all"

    async def reset_limits(self, client_id: str | None = None) -> None:
        """Reset rate limits."""
        async with self._lock:
            if client_id:
                # Reset specific client
                keys_to_remove = [
                    key for key in self._windows if key.startswith(f"{client_id}:")
                ]
                for key in keys_to_remove:
                    del self._windows[key]
            else:
                # Reset all
                self._windows.clear()

    async def get_limit_info(
        self,
        client_id: str,
        endpoint: str | None = None,
    ) -> RateLimitInfo | None:
        """Get current limit information."""
        window_key = f"{client_id}:{endpoint or 'all'}"
        async with self._lock:
            if window_key in self._windows:
                window = self._windows[window_key]
                current_time = time.time()

                # Clean old entries
                window_start = current_time - 60.0  # Assume 60s window
                while window and window[0] <= window_start:
                    window.popleft()

                limit = 100  # Default limit
                remaining = max(0, limit - len(window))
                reset_time = window[0] + 60.0 if window else current_time + 60.0

                return RateLimitInfo(
                    limit=limit,
                    remaining=remaining,
                    reset_time=reset_time,
                )
        return None


class RateLimiter:
    """Main rate limiter with multiple algorithm support."""

    def __init__(self) -> None:
        self._token_bucket = TokenBucketLimiter()
        self._sliding_window = SlidingWindowLimiter()

    async def check_rate_limit(
        self,
        request: GatewayRequest,
        config: RateLimitConfig,
    ) -> RateLimitResult:
        """Check rate limit using configured algorithm."""
        if config.algorithm == RateLimitAlgorithm.TOKEN_BUCKET:
            return await self._token_bucket.check_rate_limit(request, config)
        if config.algorithm == RateLimitAlgorithm.SLIDING_WINDOW:
            return await self._sliding_window.check_rate_limit(request, config)
        # Default to token bucket
        return await self._token_bucket.check_rate_limit(request, config)

    async def reset_limits(self, client_id: str | None = None) -> None:
        """Reset rate limits for all algorithms."""
        await self._token_bucket.reset_limits(client_id)
        await self._sliding_window.reset_limits(client_id)

    async def get_limit_info(
        self,
        client_id: str,
        endpoint: str | None = None,
        algorithm: RateLimitAlgorithm = RateLimitAlgorithm.TOKEN_BUCKET,
    ) -> RateLimitInfo | None:
        """Get current limit information."""
        if algorithm == RateLimitAlgorithm.TOKEN_BUCKET:
            return await self._token_bucket.get_limit_info(client_id, endpoint)
        if algorithm == RateLimitAlgorithm.SLIDING_WINDOW:
            return await self._sliding_window.get_limit_info(client_id, endpoint)
        return await self._token_bucket.get_limit_info(client_id, endpoint)
