"""Rate limiting functionality for API Gateway."""

import asyncio
import time
import typing as t
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum

from pydantic import BaseModel

from ._base import GatewayBase, GatewaySettings


class RateLimitStatus(str, Enum):
    """Rate limit check status."""

    ALLOWED = "allowed"
    RATE_LIMITED = "rate_limited"
    ERROR = "error"


@dataclass
class RateLimitResult:
    """Result of rate limit check."""

    status: RateLimitStatus
    remaining: int = 0
    reset_time: float = 0.0
    retry_after: int = 0
    error: str | None = None


class RateLimitConfig(BaseModel):
    """Configuration for rate limiting."""

    requests_per_window: int = 100
    window_seconds: int = 60
    burst_size: int | None = None  # For token bucket
    replenish_rate: float = 1.0  # Tokens per second for token bucket

    class Config:
        extra = "forbid"


class RateLimiter(ABC):
    """Abstract base class for rate limiters."""

    def __init__(self, config: RateLimitConfig) -> None:
        self.config = config

    @abstractmethod
    async def check_rate_limit(self, key: str) -> RateLimitResult:
        """Check if request is within rate limit."""
        pass

    @abstractmethod
    async def reset_limit(self, key: str) -> bool:
        """Reset rate limit for a key."""
        pass


class TokenBucketLimiter(RateLimiter):
    """Token bucket rate limiter implementation."""

    def __init__(self, config: RateLimitConfig) -> None:
        super().__init__(config)
        self._buckets: dict[str, dict[str, t.Any]] = {}
        self._lock = asyncio.Lock()

    async def check_rate_limit(self, key: str) -> RateLimitResult:
        """Check rate limit using token bucket algorithm."""
        async with self._lock:
            try:
                current_time = time.time()
                bucket_size = self.config.burst_size or self.config.requests_per_window
                replenish_rate = self.config.replenish_rate

                if key not in self._buckets:
                    self._buckets[key] = {
                        "tokens": bucket_size,
                        "last_update": current_time,
                    }

                bucket = self._buckets[key]

                # Calculate tokens to add based on time elapsed
                time_elapsed = current_time - bucket["last_update"]
                tokens_to_add = time_elapsed * replenish_rate
                bucket["tokens"] = min(bucket_size, bucket["tokens"] + tokens_to_add)
                bucket["last_update"] = current_time

                if bucket["tokens"] >= 1:
                    bucket["tokens"] -= 1
                    return RateLimitResult(
                        status=RateLimitStatus.ALLOWED,
                        remaining=int(bucket["tokens"]),
                        reset_time=current_time
                        + (bucket_size - bucket["tokens"]) / replenish_rate,
                    )
                else:
                    retry_after = int((1 - bucket["tokens"]) / replenish_rate) + 1
                    return RateLimitResult(
                        status=RateLimitStatus.RATE_LIMITED,
                        remaining=0,
                        retry_after=retry_after,
                        reset_time=current_time + retry_after,
                    )

            except Exception as e:
                return RateLimitResult(
                    status=RateLimitStatus.ERROR,
                    error=f"Token bucket error: {e}",
                )

    async def reset_limit(self, key: str) -> bool:
        """Reset token bucket for a key."""
        async with self._lock:
            if key in self._buckets:
                bucket_size = self.config.burst_size or self.config.requests_per_window
                self._buckets[key] = {
                    "tokens": bucket_size,
                    "last_update": time.time(),
                }
                return True
            return False


class SlidingWindowLimiter(RateLimiter):
    """Sliding window rate limiter implementation."""

    def __init__(self, config: RateLimitConfig) -> None:
        super().__init__(config)
        self._windows: dict[str, list[float]] = {}
        self._lock = asyncio.Lock()

    async def check_rate_limit(self, key: str) -> RateLimitResult:
        """Check rate limit using sliding window algorithm."""
        async with self._lock:
            try:
                current_time = time.time()
                window_start = current_time - self.config.window_seconds

                if key not in self._windows:
                    self._windows[key] = []

                # Remove old requests outside the window
                window = self._windows[key]
                self._windows[key] = [
                    req_time for req_time in window if req_time > window_start
                ]

                if len(self._windows[key]) < self.config.requests_per_window:
                    self._windows[key].append(current_time)
                    remaining = self.config.requests_per_window - len(
                        self._windows[key]
                    )
                    oldest_request = (
                        min(self._windows[key]) if self._windows[key] else current_time
                    )
                    reset_time = oldest_request + self.config.window_seconds

                    return RateLimitResult(
                        status=RateLimitStatus.ALLOWED,
                        remaining=remaining,
                        reset_time=reset_time,
                    )
                else:
                    oldest_request = min(self._windows[key])
                    retry_after = (
                        int(oldest_request + self.config.window_seconds - current_time)
                        + 1
                    )

                    return RateLimitResult(
                        status=RateLimitStatus.RATE_LIMITED,
                        remaining=0,
                        retry_after=max(1, retry_after),
                        reset_time=oldest_request + self.config.window_seconds,
                    )

            except Exception as e:
                return RateLimitResult(
                    status=RateLimitStatus.ERROR,
                    error=f"Sliding window error: {e}",
                )

    async def reset_limit(self, key: str) -> bool:
        """Reset sliding window for a key."""
        async with self._lock:
            if key in self._windows:
                self._windows[key] = []
                return True
            return False


class RateLimitMiddleware(GatewayBase):
    """Rate limiting middleware for API Gateway."""

    def __init__(self, settings: GatewaySettings | None = None) -> None:
        super().__init__(settings)
        self.limiters: dict[str, RateLimiter] = {}
        self.default_config = RateLimitConfig(
            requests_per_window=settings.gateway_config.default_rate_limit
            if settings
            else 100,
            window_seconds=settings.gateway_config.rate_limit_window_seconds
            if settings
            else 60,
        )

    async def initialize(self) -> None:
        """Initialize rate limiters."""
        await super().initialize()

        # Create default limiters
        self.limiters["token_bucket"] = TokenBucketLimiter(self.default_config)
        self.limiters["sliding_window"] = SlidingWindowLimiter(self.default_config)

    def add_limiter(self, name: str, limiter: RateLimiter) -> None:
        """Add a custom rate limiter."""
        self.limiters[name] = limiter

    async def check_rate_limit(
        self,
        key: str,
        limiter_type: str = "sliding_window",
        config: RateLimitConfig | None = None,
    ) -> RateLimitResult:
        """Check rate limit for a key."""
        try:
            if limiter_type not in self.limiters:
                return RateLimitResult(
                    status=RateLimitStatus.ERROR,
                    error=f"Unknown limiter type: {limiter_type}",
                )

            limiter = self.limiters[limiter_type]

            # Use custom config if provided
            if config and config != limiter.config:
                if limiter_type == "token_bucket":
                    limiter = TokenBucketLimiter(config)
                elif limiter_type == "sliding_window":
                    limiter = SlidingWindowLimiter(config)

            result = await limiter.check_rate_limit(key)

            # Update metrics
            if result.status == RateLimitStatus.RATE_LIMITED:
                self.metrics.requests_rate_limited += 1

            self.record_request(success=result.status == RateLimitStatus.ALLOWED)
            return result

        except Exception as e:
            self.record_error(f"Rate limit check error: {e}")
            return RateLimitResult(
                status=RateLimitStatus.ERROR,
                error=f"Rate limit error: {e}",
            )

    async def reset_limit(self, key: str, limiter_type: str = "sliding_window") -> bool:
        """Reset rate limit for a key."""
        try:
            if limiter_type not in self.limiters:
                return False

            return await self.limiters[limiter_type].reset_limit(key)

        except Exception as e:
            self.record_error(f"Rate limit reset error: {e}")
            return False

    def get_rate_limit_key(
        self, user_id: str | None, ip_address: str | None = None
    ) -> str:
        """Generate rate limit key from user ID and/or IP address."""
        if user_id:
            return f"user:{user_id}"
        elif ip_address:
            return f"ip:{ip_address}"
        else:
            return "anonymous"
