"""Cache optimization service for ACB performance layer.

Provides intelligent cache optimization strategies and management
with integration to ACB's cache adapters.
"""

import time
from enum import Enum
from operator import itemgetter

import asyncio
import contextlib
import typing as t
from dataclasses import dataclass
from pydantic import Field

from acb.adapters import import_adapter
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
        name="Cache Optimizer",
        category="performance",
        service_type="cache_optimizer",
        version="1.0.0",
        acb_min_version="0.19.1",
        author="ACB Framework Team",
        created_date="2024-01-01T00:00:00",
        last_modified="2024-01-01T00:00:00",
        status=ServiceStatus.STABLE,
        capabilities=[
            ServiceCapability.CACHING,
            ServiceCapability.OPTIMIZATION,
            ServiceCapability.ASYNC_OPERATIONS,
            ServiceCapability.METRICS_COLLECTION,
        ],
        description="Intelligent cache optimization and management service",
        settings_class="CacheOptimizerSettings",
        config_example={
            "default_strategy": "adaptive",
            "optimization_interval": 300.0,
            "enable_background_optimization": True,
            "cache_hit_threshold": 0.8,
        },
    )
except ImportError:
    # Discovery system not available
    SERVICE_METADATA = None


class CacheStrategy(str, Enum):
    """Cache optimization strategies."""

    LRU = "lru"  # Least Recently Used
    LFU = "lfu"  # Least Frequently Used
    TTL = "ttl"  # Time To Live based
    ADAPTIVE = "adaptive"  # Adaptive based on usage patterns


@dataclass
class CacheStats:
    """Cache performance statistics."""

    hits: int = 0
    misses: int = 0
    hit_rate: float = 0.0
    average_response_time: float = 0.0
    evictions: int = 0
    memory_usage_bytes: int = 0


class CacheOptimizerSettings(ServiceSettings):
    """Settings for cache optimizer service."""

    strategy: CacheStrategy = CacheStrategy.ADAPTIVE
    max_memory_usage_mb: int = 256
    cleanup_interval_seconds: float = 300.0  # 5 minutes
    stats_collection_enabled: bool = True
    preload_patterns: list[str] = Field(default_factory=list)

    # TTL optimization
    default_ttl_seconds: int = 3600
    min_ttl_seconds: int = 60
    max_ttl_seconds: int = 86400

    # Adaptive strategy parameters
    usage_threshold_for_promotion: int = 10
    time_window_for_analysis_seconds: int = 3600

    @depends.inject
    def __init__(self, config: Inject[Config], **values: t.Any) -> None:
        super().__init__(**values)


class CacheOptimizer(ServiceBase):
    """Service for optimizing cache operations and performance.

    Provides intelligent cache management, optimization strategies,
    and performance monitoring for ACB applications.
    """

    def __init__(
        self,
        service_config: ServiceConfig | None = None,
        settings: CacheOptimizerSettings | None = None,
    ) -> None:
        if service_config is None:
            service_config = ServiceConfig(
                service_id="cache_optimizer",
                name="Cache Optimizer",
                description="Intelligent cache optimization and management service",
                dependencies=["cache"],
                priority=20,  # Start after cache adapter
            )

        super().__init__(service_config, settings or CacheOptimizerSettings())
        self._settings: CacheOptimizerSettings = self._settings  # type: ignore

        self._cache_adapter: t.Any = None
        self._stats = CacheStats()
        self._optimization_task: asyncio.Task[t.Any] | None = None
        self._usage_patterns: dict[str, dict[str, t.Any]] = {}

    async def _initialize(self) -> None:
        """Initialize the cache optimizer."""
        # Get cache adapter
        try:
            Cache = import_adapter("cache")
            self._cache_adapter = depends.get(Cache)
        except Exception as e:
            self.logger.exception(f"Failed to get cache adapter: {e}")
            raise

        # Start optimization task
        self._optimization_task = asyncio.create_task(self._optimization_loop())

        self.logger.info("Cache optimizer initialized")

    async def _shutdown(self) -> None:
        """Shutdown the cache optimizer."""
        if self._optimization_task:
            self._optimization_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._optimization_task

    async def _health_check(self) -> dict[str, t.Any]:
        """Health check for cache optimizer."""
        return {
            "cache_adapter_available": self._cache_adapter is not None,
            "hit_rate": self._stats.hit_rate,
            "total_operations": self._stats.hits + self._stats.misses,
            "optimization_running": (
                self._optimization_task is not None
                and not self._optimization_task.done()
            ),
            "patterns_tracked": len(self._usage_patterns),
        }

    async def get_optimized(
        self,
        key: str,
        fetch_function: t.Callable[[], t.Awaitable[t.Any]],
        ttl: int | None = None,
        tags: list[str] | None = None,
    ) -> t.Any:
        """Get value with intelligent optimization.

        Args:
            key: Cache key
            fetch_function: Function to fetch value on cache miss
            ttl: Optional TTL override
            tags: Optional tags for categorization

        Returns:
            Cached or fetched value
        """
        start_time = time.perf_counter()

        try:
            # Try cache first
            value = await self._cache_adapter.get(key)

            if value is not None:
                # Cache hit
                self._stats.hits += 1
                self._update_usage_pattern(key, "hit", tags)

                duration = (time.perf_counter() - start_time) * 1000
                self._update_stats(duration)

                return value

            # Cache miss - fetch and store
            self._stats.misses += 1
            value = await fetch_function()

            # Determine optimal TTL
            optimal_ttl = self._calculate_optimal_ttl(key, ttl)

            # Store with optimization
            await self._cache_adapter.set(key, value, ttl=optimal_ttl)

            self._update_usage_pattern(key, "miss", tags)

            duration = (time.perf_counter() - start_time) * 1000
            self._update_stats(duration)

            return value

        except Exception as e:
            self.record_error(str(e))
            # Fallback to direct fetch
            return await fetch_function()

    async def preload_cache(self, patterns: list[str] | None = None) -> int:
        """Preload cache with common patterns.

        Args:
            patterns: Optional list of key patterns to preload

        Returns:
            Number of items preloaded
        """
        patterns = patterns or self._settings.preload_patterns
        if not patterns:
            return 0

        preloaded_count = 0

        for pattern in patterns:
            try:
                # This would implement pattern-based preloading
                # For now, we'll log the intention
                self.logger.debug(f"Preloading cache pattern: {pattern}")
                preloaded_count += 1

            except Exception as e:
                self.logger.warning(f"Failed to preload pattern {pattern}: {e}")

        self.set_custom_metric("preloaded_items", preloaded_count)
        return preloaded_count

    async def clear_expired(self) -> int:
        """Clear expired cache entries.

        Returns:
            Number of expired entries cleared
        """
        try:
            # This would implement expired key cleanup
            # The actual implementation depends on cache adapter capabilities
            cleared_count = 0

            if hasattr(self._cache_adapter, "clear_expired"):
                cleared_count = await self._cache_adapter.clear_expired()
            else:
                self.logger.debug("Cache adapter does not support expired key cleanup")

            self.set_custom_metric("expired_keys_cleared", cleared_count)
            return cleared_count

        except Exception as e:
            self.logger.exception(f"Failed to clear expired cache entries: {e}")
            return 0

    async def optimize_memory_usage(self) -> dict[str, t.Any]:
        """Optimize cache memory usage based on configured strategy.

        Returns:
            Optimization results
        """
        try:
            optimization_results = {
                "strategy_used": self._settings.strategy.value,
                "keys_evicted": 0,
                "memory_freed_bytes": 0,
                "optimization_time_ms": 0,
            }

            start_time = time.perf_counter()

            if self._settings.strategy == CacheStrategy.ADAPTIVE:
                # Implement adaptive optimization based on usage patterns
                evicted = await self._adaptive_eviction()
                optimization_results["keys_evicted"] = evicted

            elif self._settings.strategy == CacheStrategy.LRU:
                # Implement LRU-based eviction
                evicted = await self._lru_eviction()
                optimization_results["keys_evicted"] = evicted

            elif self._settings.strategy == CacheStrategy.TTL:
                # Clear expired entries
                evicted = await self.clear_expired()
                optimization_results["keys_evicted"] = evicted

            optimization_results["optimization_time_ms"] = (
                time.perf_counter() - start_time
            ) * 1000

            return optimization_results

        except Exception as e:
            self.logger.exception(f"Memory optimization failed: {e}")
            return {"error": str(e)}

    def get_cache_stats(self) -> CacheStats:
        """Get current cache statistics.

        Returns:
            Current cache performance statistics
        """
        # Update hit rate
        total_operations = self._stats.hits + self._stats.misses
        if total_operations > 0:
            self._stats.hit_rate = (self._stats.hits / total_operations) * 100

        return self._stats

    def _calculate_optimal_ttl(self, key: str, requested_ttl: int | None) -> int:
        """Calculate optimal TTL based on usage patterns and strategy.

        Args:
            key: Cache key
            requested_ttl: Requested TTL value

        Returns:
            Optimal TTL in seconds
        """
        if requested_ttl is not None:
            return max(
                self._settings.min_ttl_seconds,
                min(requested_ttl, self._settings.max_ttl_seconds),
            )

        # Use usage patterns for adaptive TTL
        if key in self._usage_patterns:
            pattern = self._usage_patterns[key]
            access_frequency = pattern.get("access_count", 0)

            if access_frequency > self._settings.usage_threshold_for_promotion:
                # Frequently accessed - longer TTL
                return self._settings.max_ttl_seconds
            # Less frequently accessed - shorter TTL
            return self._settings.default_ttl_seconds

        return self._settings.default_ttl_seconds

    def _update_usage_pattern(
        self,
        key: str,
        operation: str,
        tags: list[str] | None = None,
    ) -> None:
        """Update usage patterns for a cache key.

        Args:
            key: Cache key
            operation: Operation type (hit/miss)
            tags: Optional tags
        """
        if key not in self._usage_patterns:
            self._usage_patterns[key] = {
                "access_count": 0,
                "hit_count": 0,
                "miss_count": 0,
                "last_accessed": time.time(),
                "tags": tags or [],
            }

        pattern = self._usage_patterns[key]
        pattern["access_count"] += 1
        pattern["last_accessed"] = time.time()

        if operation == "hit":
            pattern["hit_count"] += 1
        else:
            pattern["miss_count"] += 1

    def _update_stats(self, response_time_ms: float) -> None:
        """Update cache statistics.

        Args:
            response_time_ms: Response time in milliseconds
        """
        # Update average response time with exponential smoothing
        alpha = 0.1  # Smoothing factor
        if self._stats.average_response_time == 0:
            self._stats.average_response_time = response_time_ms
        else:
            self._stats.average_response_time = (
                alpha * response_time_ms
                + (1 - alpha) * self._stats.average_response_time
            )

    async def _adaptive_eviction(self) -> int:
        """Perform adaptive cache eviction based on usage patterns.

        Returns:
            Number of keys evicted
        """
        # Find least valuable keys based on patterns
        candidates_for_eviction = []
        current_time = time.time()

        for key, pattern in self._usage_patterns.items():
            # Calculate value score based on access frequency and recency
            access_frequency = pattern["access_count"]
            time_since_access = current_time - pattern["last_accessed"]
            hit_rate = pattern["hit_count"] / max(pattern["access_count"], 1)

            # Lower score = higher priority for eviction
            value_score = (access_frequency * hit_rate) / (time_since_access + 1)
            candidates_for_eviction.append((key, value_score))

        # Sort by value score (lowest first)
        candidates_for_eviction.sort(key=itemgetter(1))

        # Evict bottom 20% of keys
        evict_count = max(1, len(candidates_for_eviction) // 5)
        evicted = 0

        for key, _ in candidates_for_eviction[:evict_count]:
            try:
                await self._cache_adapter.delete(key)
                del self._usage_patterns[key]
                evicted += 1
            except Exception as e:
                self.logger.warning(f"Failed to evict key {key}: {e}")

        return evicted

    async def _lru_eviction(self) -> int:
        """Perform LRU-based cache eviction.

        Returns:
            Number of keys evicted
        """
        # Sort by last accessed time
        sorted_patterns = sorted(
            self._usage_patterns.items(),
            key=lambda x: x[1]["last_accessed"],
        )

        # Evict oldest 20%
        evict_count = max(1, len(sorted_patterns) // 5)
        evicted = 0

        for key, _ in sorted_patterns[:evict_count]:
            try:
                await self._cache_adapter.delete(key)
                del self._usage_patterns[key]
                evicted += 1
            except Exception as e:
                self.logger.warning(f"Failed to evict key {key}: {e}")

        return evicted

    async def _optimization_loop(self) -> None:
        """Main cache optimization loop."""
        while not self._shutdown_event.is_set():
            try:
                await asyncio.sleep(self._settings.cleanup_interval_seconds)
                if self._shutdown_event.is_set():
                    break

                # Perform periodic optimization
                await self.optimize_memory_usage()
                await self.clear_expired()

            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.exception(f"Cache optimization loop error: {e}")
                await asyncio.sleep(60)  # Wait before retrying
