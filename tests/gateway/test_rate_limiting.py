"""Tests for Rate Limiting functionality."""

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock

import pytest

from acb.gateway.rate_limiting import (
    RateLimitAlgorithm,
    RateLimitConfig,
    RateLimitResult,
    RateLimiter,
    TokenBucketRateLimiter,
    SlidingWindowRateLimiter,
)


@pytest.fixture
def token_bucket_config():
    """Token bucket rate limit configuration."""
    return RateLimitConfig(
        algorithm=RateLimitAlgorithm.TOKEN_BUCKET,
        requests_per_second=10,
        burst_capacity=20,
        enabled=True,
    )


@pytest.fixture
def sliding_window_config():
    """Sliding window rate limit configuration."""
    return RateLimitConfig(
        algorithm=RateLimitAlgorithm.SLIDING_WINDOW,
        requests_per_window=100,
        window_size_seconds=60,
        enabled=True,
    )


@pytest.fixture
def mock_storage():
    """Mock storage backend."""
    storage = AsyncMock()
    storage.get.return_value = None
    storage.set.return_value = None
    storage.increment.return_value = 1
    return storage


class TestTokenBucketRateLimiter:
    """Test cases for TokenBucketRateLimiter."""

    @pytest.mark.asyncio
    async def test_check_rate_limit_allow(self, token_bucket_config, mock_storage):
        """Test rate limit check allowing request."""
        limiter = TokenBucketRateLimiter(token_bucket_config, mock_storage)

        # Mock bucket with tokens available
        mock_storage.get.return_value = {
            "tokens": 10,
            "last_refill": time.time(),
        }

        result = await limiter.check_rate_limit("test-key")

        assert result.allowed is True
        assert result.remaining == 9
        assert result.retry_after is None

    @pytest.mark.asyncio
    async def test_check_rate_limit_deny(self, token_bucket_config, mock_storage):
        """Test rate limit check denying request."""
        limiter = TokenBucketRateLimiter(token_bucket_config, mock_storage)

        # Mock bucket with no tokens
        mock_storage.get.return_value = {
            "tokens": 0,
            "last_refill": time.time(),
        }

        result = await limiter.check_rate_limit("test-key")

        assert result.allowed is False
        assert result.remaining == 0
        assert result.retry_after > 0

    @pytest.mark.asyncio
    async def test_token_refill(self, token_bucket_config, mock_storage):
        """Test token bucket refill mechanism."""
        limiter = TokenBucketRateLimiter(token_bucket_config, mock_storage)

        # Mock bucket from 2 seconds ago with 0 tokens
        past_time = time.time() - 2.0
        mock_storage.get.return_value = {
            "tokens": 0,
            "last_refill": past_time,
        }

        result = await limiter.check_rate_limit("test-key")

        # Should have refilled tokens (10 tokens/sec * 2 sec = 20 tokens max capacity)
        assert result.allowed is True
        assert result.remaining > 0

    @pytest.mark.asyncio
    async def test_new_bucket_creation(self, token_bucket_config, mock_storage):
        """Test creation of new token bucket."""
        limiter = TokenBucketRateLimiter(token_bucket_config, mock_storage)

        # Mock no existing bucket
        mock_storage.get.return_value = None

        result = await limiter.check_rate_limit("new-key")

        # New bucket should start with full capacity minus one
        assert result.allowed is True
        assert result.remaining == token_bucket_config.burst_capacity - 1

    @pytest.mark.asyncio
    async def test_get_metrics(self, token_bucket_config, mock_storage):
        """Test metrics collection."""
        limiter = TokenBucketRateLimiter(token_bucket_config, mock_storage)

        # Simulate some requests
        await limiter.check_rate_limit("test-key-1")
        await limiter.check_rate_limit("test-key-2")

        metrics = limiter.get_metrics()

        assert "total_requests" in metrics
        assert "allowed_requests" in metrics
        assert "denied_requests" in metrics
        assert "unique_keys" in metrics


class TestSlidingWindowRateLimiter:
    """Test cases for SlidingWindowRateLimiter."""

    @pytest.mark.asyncio
    async def test_check_rate_limit_allow(self, sliding_window_config, mock_storage):
        """Test rate limit check allowing request."""
        limiter = SlidingWindowRateLimiter(sliding_window_config, mock_storage)

        # Mock low request count in window
        mock_storage.get.return_value = {
            "count": 50,
            "window_start": time.time() - 30,  # 30 seconds ago
        }

        result = await limiter.check_rate_limit("test-key")

        assert result.allowed is True
        assert result.remaining == 49  # 100 - 50 - 1
        assert result.retry_after is None

    @pytest.mark.asyncio
    async def test_check_rate_limit_deny(self, sliding_window_config, mock_storage):
        """Test rate limit check denying request."""
        limiter = SlidingWindowRateLimiter(sliding_window_config, mock_storage)

        # Mock request count at limit
        mock_storage.get.return_value = {
            "count": 100,
            "window_start": time.time() - 30,  # 30 seconds ago
        }

        result = await limiter.check_rate_limit("test-key")

        assert result.allowed is False
        assert result.remaining == 0
        assert result.retry_after > 0

    @pytest.mark.asyncio
    async def test_window_reset(self, sliding_window_config, mock_storage):
        """Test sliding window reset."""
        limiter = SlidingWindowRateLimiter(sliding_window_config, mock_storage)

        # Mock old window (past window size)
        past_time = time.time() - sliding_window_config.window_size_seconds - 10
        mock_storage.get.return_value = {
            "count": 100,
            "window_start": past_time,
        }

        result = await limiter.check_rate_limit("test-key")

        # Window should reset, allowing request
        assert result.allowed is True
        assert result.remaining == sliding_window_config.requests_per_window - 1

    @pytest.mark.asyncio
    async def test_new_window_creation(self, sliding_window_config, mock_storage):
        """Test creation of new sliding window."""
        limiter = SlidingWindowRateLimiter(sliding_window_config, mock_storage)

        # Mock no existing window
        mock_storage.get.return_value = None

        result = await limiter.check_rate_limit("new-key")

        # New window should allow request
        assert result.allowed is True
        assert result.remaining == sliding_window_config.requests_per_window - 1

    @pytest.mark.asyncio
    async def test_concurrent_requests(self, sliding_window_config, mock_storage):
        """Test handling concurrent requests."""
        limiter = SlidingWindowRateLimiter(sliding_window_config, mock_storage)

        # Mock near-limit scenario
        mock_storage.get.return_value = {
            "count": 99,
            "window_start": time.time() - 30,
        }

        # Simulate concurrent requests
        tasks = [
            limiter.check_rate_limit("concurrent-key")
            for _ in range(5)
        ]

        results = await asyncio.gather(*tasks)

        # Only one should be allowed due to rate limiting
        allowed_count = sum(1 for result in results if result.allowed)
        assert allowed_count == 1


class TestRateLimiter:
    """Test cases for main RateLimiter class."""

    @pytest.mark.asyncio
    async def test_check_rate_limit_with_tenant(self, token_bucket_config, mock_storage):
        """Test rate limiting with tenant isolation."""
        limiter = RateLimiter(token_bucket_config, mock_storage)

        # Mock different buckets for different tenants
        def mock_get(key):
            if "tenant1" in key:
                return {"tokens": 10, "last_refill": time.time()}
            elif "tenant2" in key:
                return {"tokens": 0, "last_refill": time.time()}
            return None

        mock_storage.get.side_effect = mock_get

        # Test different tenants
        result1 = await limiter.check_rate_limit("127.0.0.1", "tenant1")
        result2 = await limiter.check_rate_limit("127.0.0.1", "tenant2")

        # Same IP, different tenants should have different limits
        assert result1.allowed is True
        assert result2.allowed is False

    @pytest.mark.asyncio
    async def test_check_rate_limit_disabled(self, token_bucket_config, mock_storage):
        """Test rate limiting when disabled."""
        token_bucket_config.enabled = False
        limiter = RateLimiter(token_bucket_config, mock_storage)

        result = await limiter.check_rate_limit("any-key")

        # Should always allow when disabled
        assert result.allowed is True
        assert result.remaining is None

    @pytest.mark.asyncio
    async def test_cleanup(self, token_bucket_config, mock_storage):
        """Test rate limiter cleanup."""
        limiter = RateLimiter(token_bucket_config, mock_storage)
        mock_storage.cleanup = AsyncMock()

        await limiter.cleanup()

        mock_storage.cleanup.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_health(self, token_bucket_config, mock_storage):
        """Test health status."""
        limiter = RateLimiter(token_bucket_config, mock_storage)

        health = await limiter.get_health()

        assert health["status"] == "healthy"
        assert health["algorithm"] == token_bucket_config.algorithm.value
        assert health["enabled"] == token_bucket_config.enabled

    @pytest.mark.asyncio
    async def test_get_metrics(self, token_bucket_config, mock_storage):
        """Test metrics collection."""
        limiter = RateLimiter(token_bucket_config, mock_storage)

        # Simulate some requests
        await limiter.check_rate_limit("key1")
        await limiter.check_rate_limit("key2")

        metrics = await limiter.get_metrics()

        assert "algorithm" in metrics
        assert "total_requests" in metrics
        assert "allowed_requests" in metrics
        assert "denied_requests" in metrics

    def test_generate_key(self, token_bucket_config, mock_storage):
        """Test key generation for rate limiting."""
        limiter = RateLimiter(token_bucket_config, mock_storage)

        # Test with tenant
        key1 = limiter._generate_key("127.0.0.1", "tenant1")
        key2 = limiter._generate_key("127.0.0.1", "tenant2")

        assert key1 != key2
        assert "127.0.0.1" in key1
        assert "tenant1" in key1

        # Test without tenant
        key3 = limiter._generate_key("192.168.1.1", None)
        assert "192.168.1.1" in key3