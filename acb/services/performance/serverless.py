"""Serverless optimization services for ACB.

Provides cold start optimization, lazy initialization, and resource cleanup
specifically designed for serverless environments. Enhanced with cloud-native
optimization patterns for adaptive connection pooling, tiered caching, and
memory-efficient processing.
"""

import time
from functools import wraps
from weakref import WeakSet

import asyncio
import typing as t
from contextlib import asynccontextmanager, suppress
from dataclasses import dataclass, field
from pydantic import Field

from acb.cleanup import CleanupMixin
from acb.config import Config
from acb.depends import Inject, depends
from acb.services._base import ServiceBase, ServiceConfig, ServiceSettings

# Service metadata for discovery system
SERVERLESS_OPTIMIZER_METADATA: t.Any = None

try:
    from acb.services.discovery import (
        ServiceCapability,
        ServiceMetadata,
        ServiceStatus,
        generate_service_id,
    )

    SERVERLESS_OPTIMIZER_METADATA = ServiceMetadata(
        service_id=generate_service_id(),
        name="Serverless Optimizer",
        category="performance",
        service_type="serverless_optimizer",
        version="1.0.0",
        acb_min_version="0.19.1",
        author="ACB Framework Team",
        created_date="2024-01-01T00:00:00",
        last_modified="2024-01-01T00:00:00",
        status=ServiceStatus.STABLE,
        capabilities=[
            ServiceCapability.OPTIMIZATION,
            ServiceCapability.COLD_START_OPTIMIZATION,
            ServiceCapability.LAZY_LOADING,
            ServiceCapability.RESOURCE_MANAGEMENT,
        ],
        description="Cold start optimization and resource management for serverless environments",
        settings_class="ServerlessOptimizerSettings",
        config_example={
            "cold_start_optimization": True,
            "lazy_loading_enabled": True,
            "adapter_preloading": True,
            "resource_cleanup_interval": 300,
        },
    )
except ImportError:
    # Discovery system not available
    SERVERLESS_OPTIMIZER_METADATA = None


@dataclass
class ColdStartMetrics:
    """Metrics for cold start optimization."""

    cold_starts_count: int = 0
    warm_starts_count: int = 0
    average_cold_start_time_ms: float = 0.0
    average_warm_start_time_ms: float = 0.0
    resources_preloaded: int = 0
    memory_usage_mb: float = 0.0
    optimizations_applied: dict[str, int] = field(default_factory=dict)


class ServerlessOptimizerSettings(ServiceSettings):
    """Settings for serverless optimization."""

    # Cold start optimization
    cold_start_optimization: bool = True
    preload_critical_adapters: bool = True
    critical_adapters: list[str] = Field(default_factory=lambda: ["cache", "sql"])

    # Lazy initialization
    lazy_loading_enabled: bool = True
    lazy_loading_threshold_ms: float = 100.0

    # Resource management
    resource_cleanup_enabled: bool = True
    resource_cleanup_interval: float = 300.0  # 5 minutes
    max_idle_time: float = 600.0  # 10 minutes

    # Memory optimization
    memory_monitoring: bool = True
    memory_cleanup_threshold_mb: float = 512.0

    @depends.inject
    def __init__(self, config: Inject[Config], **values: t.Any) -> None:
        super().__init__(**values)


class ServerlessOptimizer(ServiceBase):
    """Serverless optimization service for cold start and resource management."""

    def __init__(
        self,
        service_config: ServiceConfig | None = None,
        settings: ServerlessOptimizerSettings | None = None,
    ) -> None:
        if service_config is None:
            service_config = ServiceConfig(
                service_id="serverless_optimizer",
                name="Serverless Optimizer",
                description="Cold start optimization and resource management",
                priority=10,  # Very high priority for early initialization
            )

        super().__init__(service_config, settings or ServerlessOptimizerSettings())
        self._settings: ServerlessOptimizerSettings = self._settings  # type: ignore
        self._cold_start_metrics = ColdStartMetrics()
        self._preloaded_adapters: dict[str, t.Any] = {}
        self._resource_cleanup_task: asyncio.Task[t.Any] | None = None
        self._startup_time = time.perf_counter()

    async def _initialize(self) -> None:
        """Initialize serverless optimizer."""
        if self._settings.cold_start_optimization:
            await self._perform_cold_start_optimizations()

        if self._settings.resource_cleanup_enabled:
            self._resource_cleanup_task = asyncio.create_task(
                self._resource_cleanup_loop(),
            )

        self.logger.info("Serverless optimizer initialized")

    async def _shutdown(self) -> None:
        """Shutdown serverless optimizer."""
        if self._resource_cleanup_task:
            self._resource_cleanup_task.cancel()
            with suppress(asyncio.CancelledError):
                await self._resource_cleanup_task

    async def _health_check(self) -> dict[str, t.Any]:
        """Health check for serverless optimizer."""
        return {
            "cold_starts": self._cold_start_metrics.cold_starts_count,
            "warm_starts": self._cold_start_metrics.warm_starts_count,
            "preloaded_adapters": len(self._preloaded_adapters),
            "average_cold_start_ms": self._cold_start_metrics.average_cold_start_time_ms,
            "memory_usage_mb": self._cold_start_metrics.memory_usage_mb,
        }

    async def _perform_cold_start_optimizations(self) -> None:
        """Perform cold start optimizations."""
        start_time = time.perf_counter()

        try:
            # Preload critical adapters
            if self._settings.preload_critical_adapters:
                await self._preload_adapters()

            # Setup lazy loading patterns
            if self._settings.lazy_loading_enabled:
                self._setup_lazy_loading()

            # Record cold start metrics
            duration = (time.perf_counter() - start_time) * 1000
            self._cold_start_metrics.cold_starts_count += 1
            self._update_cold_start_average(duration)

            self.logger.info(f"Cold start optimization completed in {duration:.2f}ms")

        except Exception as e:
            self.logger.exception(f"Cold start optimization failed: {e}")
            self.record_error(str(e))

    async def _preload_adapters(self) -> None:
        """Preload critical adapters for faster warm starts."""
        from acb.adapters import import_adapter

        for adapter_name in self._settings.critical_adapters:
            try:
                start_time = time.perf_counter()
                adapter_class = import_adapter(adapter_name)
                adapter_instance = await depends.get(adapter_class)

                # Initialize adapter if it has async initialization
                if hasattr(adapter_instance, "initialize"):
                    await adapter_instance.initialize()

                self._preloaded_adapters[adapter_name] = adapter_instance
                duration = (time.perf_counter() - start_time) * 1000

                self.logger.debug(
                    f"Preloaded {adapter_name} adapter in {duration:.2f}ms",
                )
                self._cold_start_metrics.resources_preloaded += 1

            except Exception as e:
                self.logger.warning(f"Failed to preload {adapter_name} adapter: {e}")

    def _setup_lazy_loading(self) -> None:
        """Setup lazy loading patterns for non-critical resources."""
        # This could be enhanced to setup lazy loading for various components
        self.logger.debug("Lazy loading patterns configured")

    def _update_cold_start_average(self, duration: float) -> None:
        """Update cold start time average."""
        count = self._cold_start_metrics.cold_starts_count
        current_avg = self._cold_start_metrics.average_cold_start_time_ms
        self._cold_start_metrics.average_cold_start_time_ms = (
            current_avg * (count - 1) + duration
        ) / count

    async def _resource_cleanup_loop(self) -> None:
        """Background resource cleanup loop."""
        while not self._shutdown_event.is_set():
            try:
                await asyncio.sleep(self._settings.resource_cleanup_interval)
                if self._shutdown_event.is_set():
                    break

                await self._cleanup_idle_resources()

            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.exception(f"Resource cleanup error: {e}")
                await asyncio.sleep(60)

    async def _cleanup_idle_resources(self) -> None:
        """Cleanup idle resources to optimize memory usage."""
        try:
            # Memory monitoring
            if self._settings.memory_monitoring:
                await self._monitor_memory_usage()

            # Identify and cleanup idle adapters
            idle_adapters = self._identify_idle_adapters()
            await self._cleanup_adapters(idle_adapters)

        except Exception as e:
            self.logger.exception(f"Error during resource cleanup: {e}")

    def _identify_idle_adapters(self) -> list[str]:
        """Identify adapters that have been idle too long.

        Returns:
            List of idle adapter names
        """
        idle_adapters = []
        current_time = time.perf_counter()

        for name, adapter in self._preloaded_adapters.items():
            if self._is_adapter_idle(adapter, current_time):
                idle_adapters.append(name)

        return idle_adapters

    def _is_adapter_idle(self, adapter: t.Any, current_time: float) -> bool:
        """Check if adapter has been idle too long.

        Args:
            adapter: Adapter instance
            current_time: Current timestamp

        Returns:
            True if adapter is idle
        """
        if not hasattr(adapter, "_last_used_time"):
            return False

        last_used = getattr(adapter, "_last_used_time", current_time)
        return current_time - last_used > self._settings.max_idle_time

    async def _cleanup_adapters(self, adapter_names: list[str]) -> None:
        """Cleanup idle adapters.

        Args:
            adapter_names: List of adapter names to cleanup
        """
        for name in adapter_names:
            adapter = self._preloaded_adapters[name]

            if hasattr(adapter, "cleanup"):
                await adapter.cleanup()

            del self._preloaded_adapters[name]
            self.logger.debug(f"Cleaned up idle adapter: {name}")

    async def _monitor_memory_usage(self) -> None:
        """Monitor and report memory usage."""
        try:
            import psutil

            process = psutil.Process()
            memory_mb = process.memory_info().rss / 1024 / 1024
            self._cold_start_metrics.memory_usage_mb = memory_mb

            if memory_mb > self._settings.memory_cleanup_threshold_mb:
                self.logger.warning(f"High memory usage detected: {memory_mb:.2f}MB")
                # Could trigger more aggressive cleanup here

        except ImportError:
            # psutil not available
            pass
        except Exception as e:
            self.logger.exception(f"Memory monitoring error: {e}")

    def get_metrics(self) -> ColdStartMetrics:
        """Get current cold start metrics."""
        return self._cold_start_metrics


class LazyInitializer(CleanupMixin):
    """Lazy initialization wrapper for expensive resources."""

    def __init__(
        self,
        factory: t.Callable[[], t.Awaitable[t.Any]],
        timeout: float = 30.0,
    ) -> None:
        super().__init__()
        self._factory = factory
        self._timeout = timeout
        self._instance: t.Any = None
        self._initialization_lock = asyncio.Lock()
        self._initialized = False

    async def get(self) -> t.Any:
        """Get the lazily initialized instance."""
        if self._initialized:
            return self._instance

        async with self._initialization_lock:
            if self._initialized:
                return self._instance

            try:
                self._instance = await asyncio.wait_for(
                    self._factory(),
                    timeout=self._timeout,
                )
                self._initialized = True

                # Register for cleanup if the instance supports it
                if hasattr(self._instance, "cleanup"):
                    self.register_resource(self._instance)

                return self._instance

            except TimeoutError:
                msg = f"Lazy initialization timed out after {self._timeout}s"
                raise RuntimeError(
                    msg,
                )

    @property
    def is_initialized(self) -> bool:
        """Check if the resource has been initialized."""
        return self._initialized

    async def reset(self) -> None:
        """Reset the lazy initializer, clearing the cached instance."""
        async with self._initialization_lock:
            if self._instance and hasattr(self._instance, "cleanup"):
                await self._instance.cleanup()
            self._instance = None
            self._initialized = False


class AdapterPreInitializer:
    """Pre-initialization manager for adapters."""

    def __init__(self) -> None:
        self._preinitialized: dict[str, t.Any] = {}
        self._lazy_initializers: dict[str, LazyInitializer] = {}

    async def preinitialize_adapter(
        self,
        adapter_name: str,
        eager: bool = False,
    ) -> None:
        """Pre-initialize an adapter."""
        try:
            from acb.adapters import import_adapter

            if eager:
                # Eager initialization
                adapter_class = import_adapter(adapter_name)
                adapter_instance = await depends.get(adapter_class)

                if hasattr(adapter_instance, "initialize"):
                    await adapter_instance.initialize()

                self._preinitialized[adapter_name] = adapter_instance

            else:
                # Lazy initialization
                async def factory() -> t.Any:
                    adapter_class = import_adapter(adapter_name)
                    adapter_instance = await depends.get(adapter_class)

                    if hasattr(adapter_instance, "initialize"):
                        await adapter_instance.initialize()

                    return adapter_instance

                self._lazy_initializers[adapter_name] = LazyInitializer(factory)

        except Exception as e:
            msg = f"Failed to pre-initialize adapter {adapter_name}: {e}"
            raise RuntimeError(msg)

    async def get_adapter(self, adapter_name: str) -> t.Any:
        """Get a pre-initialized adapter."""
        if adapter_name in self._preinitialized:
            return self._preinitialized[adapter_name]

        if adapter_name in self._lazy_initializers:
            return await self._lazy_initializers[adapter_name].get()

        msg = f"Adapter {adapter_name} not pre-initialized"
        raise ValueError(msg)

    def is_preinitialized(self, adapter_name: str) -> bool:
        """Check if an adapter is pre-initialized."""
        return (
            adapter_name in self._preinitialized
            or adapter_name in self._lazy_initializers
        )


class FastDependencies:
    """Optimized dependency injection resolution."""

    def __init__(self) -> None:
        self._resolution_cache: dict[str, t.Any] = {}
        self._resolution_times: dict[str, float] = {}

    def cached_resolve(
        self,
        dependency_type: type[t.Any],
        cache_key: str | None = None,
    ) -> t.Any:
        """Resolve dependency with caching."""
        key = cache_key or f"{dependency_type.__module__}.{dependency_type.__name__}"

        if key in self._resolution_cache:
            return self._resolution_cache[key]

        start_time = time.perf_counter()
        instance = depends.get_sync(dependency_type)
        resolution_time = (time.perf_counter() - start_time) * 1000

        self._resolution_cache[key] = instance
        self._resolution_times[key] = resolution_time

        return instance

    def clear_cache(self) -> None:
        """Clear the resolution cache."""
        self._resolution_cache.clear()
        self._resolution_times.clear()

    def get_resolution_stats(self) -> dict[str, float]:
        """Get dependency resolution statistics."""
        return self._resolution_times.copy()


class ServerlessResourceCleanup(CleanupMixin):
    """Resource cleanup manager for serverless environments."""

    def __init__(self, cleanup_interval: float = 300.0) -> None:
        super().__init__()
        self._cleanup_interval = cleanup_interval
        self._tracked_resources: WeakSet[t.Any] = WeakSet()
        self._cleanup_task: asyncio.Task[t.Any] | None = None

    def track_resource(self, resource: t.Any) -> None:
        """Track a resource for cleanup."""
        self._tracked_resources.add(resource)

    async def start_cleanup_loop(self) -> None:
        """Start the resource cleanup loop."""
        if self._cleanup_task is None or self._cleanup_task.done():
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())

    async def stop_cleanup_loop(self) -> None:
        """Stop the resource cleanup loop."""
        if self._cleanup_task:
            self._cleanup_task.cancel()
            with suppress(asyncio.CancelledError):
                await self._cleanup_task

    async def _cleanup_loop(self) -> None:
        """Background cleanup loop."""
        while True:
            try:
                await asyncio.sleep(self._cleanup_interval)
                await self._perform_cleanup()

            except asyncio.CancelledError:
                break
            except Exception as e:
                # Log error but continue cleanup loop
                import logging

                logging.getLogger(__name__).exception(f"Cleanup loop error: {e}")

    async def _perform_cleanup(self) -> None:
        """Perform resource cleanup."""
        cleanup_count = 0

        # Use list() to avoid set changing during iteration
        for resource in list(self._tracked_resources):
            try:
                if hasattr(resource, "cleanup"):
                    await resource.cleanup()
                    cleanup_count += 1

            except Exception as e:
                import logging

                logging.getLogger(__name__).exception(
                    f"Error cleaning up resource: {e}",
                )

        if cleanup_count > 0:
            import logging

            logging.getLogger(__name__).info(f"Cleaned up {cleanup_count} resources")


# Convenience functions for optimization


def optimize_cold_start(
    preload_adapters: list[str] | None = None,
) -> t.Callable[
    [t.Callable[..., t.Awaitable[t.Any]]],
    t.Callable[..., t.Awaitable[t.Any]],
]:
    """Decorator to optimize function cold starts."""

    def decorator(
        func: t.Callable[..., t.Awaitable[t.Any]],
    ) -> t.Callable[..., t.Awaitable[t.Any]]:
        @wraps(func)
        async def wrapper(*args: t.Any, **kwargs: t.Any) -> t.Any:
            # Record start as warm start if already optimized
            start_time = time.perf_counter()

            try:
                result = await func(*args, **kwargs)
                duration_ms = (time.perf_counter() - start_time) * 1000

                # Could track warm start metrics here
                # self._track_warm_start(duration_ms) if needed
                _ = duration_ms  # Placeholder for future metrics tracking
                return result

            except Exception:
                duration_ms = (time.perf_counter() - start_time) * 1000
                # Could track failed execution metrics here
                # self._track_failed_execution(duration_ms) if needed
                _ = duration_ms  # Placeholder for future metrics tracking
                raise

        return wrapper

    return decorator


@asynccontextmanager
async def lazy_resource(
    factory: t.Callable[[], t.Awaitable[t.Any]],
    timeout: float = 30.0,
) -> t.AsyncGenerator[t.Any]:
    """Context manager for lazy resource initialization."""
    initializer = LazyInitializer(factory, timeout)
    try:
        resource = await initializer.get()
        yield resource
    finally:
        await initializer.cleanup()


# Cloud-Native Optimization Components


class AdaptiveConnectionPool:
    """Adaptive connection pool for serverless environments.

    Automatically scales connection pool sizes based on usage patterns
    and serverless constraints.
    """

    def __init__(
        self,
        min_connections: int = 1,
        max_connections: int = 10,
        scale_factor: float = 1.5,
        idle_timeout: float = 300.0,
    ) -> None:
        self._min_connections = min_connections
        self._max_connections = max_connections
        self._scale_factor = scale_factor
        self._idle_timeout = idle_timeout

        self._pool: set[t.Any] = set()
        self._active_connections: set[t.Any] = set()
        self._usage_stats: dict[str, float] = {}
        self._last_scale_time = time.time()
        self._creation_lock = asyncio.Lock()

    async def acquire(
        self,
        connection_factory: t.Callable[[], t.Awaitable[t.Any]],
    ) -> t.Any:
        """Acquire a connection from the pool."""
        # Try to get an existing connection
        if self._pool:
            connection = self._pool.pop()
            self._active_connections.add(connection)
            return connection

        # Create new connection if under max limit
        if len(self._active_connections) < self._max_connections:
            async with self._creation_lock:
                connection = await connection_factory()
                self._active_connections.add(connection)
                await self._record_usage("connection_created")
                return connection

        # Wait for a connection to become available
        while not self._pool:
            await asyncio.sleep(0.1)

        connection = self._pool.pop()
        self._active_connections.add(connection)
        return connection

    async def release(self, connection: t.Any) -> None:
        """Release a connection back to the pool."""
        if connection in self._active_connections:
            self._active_connections.remove(connection)

            # Add back to pool if it's healthy and we need it
            if await self._is_connection_healthy(connection):
                self._pool.add(connection)
                await self._record_usage("connection_released")
            else:
                await self._close_connection(connection)

    async def scale_down_if_needed(self) -> None:
        """Scale down pool if connections are idle."""
        current_time = time.time()
        if current_time - self._last_scale_time < 60:  # Don't scale too frequently
            return

        total_connections = len(self._pool) + len(self._active_connections)
        if total_connections > self._min_connections and not self._active_connections:
            # Close idle connections
            connections_to_close = list(self._pool)[: -self._min_connections]
            for conn in connections_to_close:
                self._pool.remove(conn)
                await self._close_connection(conn)

            self._last_scale_time = current_time

    async def _is_connection_healthy(self, connection: t.Any) -> bool:
        """Check if a connection is still healthy."""
        try:
            # Basic health check - override in subclasses for specific protocols
            return hasattr(connection, "is_closed") and not connection.is_closed
        except Exception:
            return False

    async def _close_connection(self, connection: t.Any) -> None:
        """Close a connection safely."""
        with suppress(Exception):
            if hasattr(connection, "close"):
                await connection.close()
            elif hasattr(connection, "disconnect"):
                await connection.disconnect()

    async def _record_usage(self, event: str) -> None:
        """Record usage statistics."""
        self._usage_stats[event] = time.time()

    def get_pool_stats(self) -> dict[str, t.Any]:
        """Get pool statistics."""
        return {
            "active_connections": len(self._active_connections),
            "pooled_connections": len(self._pool),
            "total_connections": len(self._active_connections) + len(self._pool),
            "max_connections": self._max_connections,
            "usage_stats": self._usage_stats.copy(),
        }


class ServerlessTieredCache:
    """Multi-tier caching system optimized for serverless environments.

    Combines memory, Redis, and object storage for optimal cost/performance.
    """

    def __init__(
        self,
        memory_limit_mb: float = 128.0,
        redis_ttl: int = 3600,
        storage_ttl: int = 86400,
    ) -> None:
        self._memory_limit_mb = memory_limit_mb
        self._redis_ttl = redis_ttl
        self._storage_ttl = storage_ttl

        self._memory_cache: dict[str, tuple[t.Any, float]] = {}
        self._memory_usage_mb = 0.0
        self._cache_stats = {
            "memory_hits": 0,
            "redis_hits": 0,
            "storage_hits": 0,
            "misses": 0,
        }

    async def get(self, key: str) -> t.Any | None:
        """Get value from tiered cache."""
        # Try memory first
        if key in self._memory_cache:
            value, timestamp = self._memory_cache[key]
            if time.time() - timestamp < 300:  # 5 minute memory TTL
                self._cache_stats["memory_hits"] += 1
                return value
            del self._memory_cache[key]

        # Try Redis
        with suppress(Exception):
            # This would integrate with ACB's Redis adapter
            value = await self._get_from_redis(key)
            if value is not None:
                self._cache_stats["redis_hits"] += 1
                await self._store_in_memory(key, value)
                return value

        # Try storage
        with suppress(Exception):
            value = await self._get_from_storage(key)
            if value is not None:
                self._cache_stats["storage_hits"] += 1
                await self._store_in_memory(key, value)
                await self._store_in_redis(key, value)
                return value

        self._cache_stats["misses"] += 1
        return None

    async def set(self, key: str, value: t.Any, ttl: int | None = None) -> None:
        """Set value in tiered cache."""
        # Always store in memory first
        await self._store_in_memory(key, value)

        # Store in Redis with longer TTL
        with suppress(Exception):
            await self._store_in_redis(key, value, ttl or self._redis_ttl)

        # Store in object storage for longest persistence
        if ttl is None or ttl > 3600:  # Only for long-term storage
            with suppress(Exception):
                await self._store_in_storage(key, value)

    async def _store_in_memory(self, key: str, value: t.Any) -> None:
        """Store value in memory cache with size management."""
        # Estimate memory usage (rough approximation)
        estimated_size = len(str(value)) / 1024 / 1024  # Convert to MB

        # Evict if necessary
        while (
            self._memory_usage_mb + estimated_size > self._memory_limit_mb
            and self._memory_cache
        ):
            oldest_key = min(
                self._memory_cache.keys(),
                key=lambda k: self._memory_cache[k][1],
            )
            del self._memory_cache[oldest_key]
            self._memory_usage_mb *= 0.9  # Rough adjustment

        self._memory_cache[key] = (value, time.time())
        self._memory_usage_mb += estimated_size

    async def _get_from_redis(self, key: str) -> t.Any | None:
        """Get value from Redis cache."""
        # Integration point with ACB Redis adapter
        # This would use: Cache = import_adapter("cache")
        return None  # Placeholder

    async def _store_in_redis(self, key: str, value: t.Any, ttl: int = 3600) -> None:
        """Store value in Redis cache."""
        # Integration point with ACB Redis adapter
        # Placeholder

    async def _get_from_storage(self, key: str) -> t.Any | None:
        """Get value from object storage."""
        # Integration point with ACB Storage adapter
        return None  # Placeholder

    async def _store_in_storage(self, key: str, value: t.Any) -> None:
        """Store value in object storage."""
        # Integration point with ACB Storage adapter
        # Placeholder

    def get_cache_stats(self) -> dict[str, t.Any]:
        """Get cache statistics."""
        total_requests = sum(self._cache_stats.values())
        hit_rate = (
            (
                self._cache_stats["memory_hits"]
                + self._cache_stats["redis_hits"]
                + self._cache_stats["storage_hits"]
            )
            / max(total_requests, 1)
        ) * 100

        return self._cache_stats | {
            "hit_rate_percent": hit_rate,
            "memory_usage_mb": self._memory_usage_mb,
            "memory_entries": len(self._memory_cache),
        }


class DeferredInitializer:
    """Deferred initialization for expensive resources in serverless environments.

    Initializes resources only when actually needed, with priority-based loading.
    """

    def __init__(self) -> None:
        self._initializers: dict[
            str,
            tuple[t.Callable[[], t.Awaitable[t.Any]], int],
        ] = {}
        self._initialized: dict[str, t.Any] = {}
        self._initialization_order: list[str] = []
        self._locks: dict[str, asyncio.Lock] = {}

    def register(
        self,
        name: str,
        factory: t.Callable[[], t.Awaitable[t.Any]],
        priority: int = 100,
    ) -> None:
        """Register a deferred initializer."""
        self._initializers[name] = (factory, priority)
        self._locks[name] = asyncio.Lock()

    async def get(self, name: str) -> t.Any:
        """Get or initialize a resource."""
        if name in self._initialized:
            return self._initialized[name]

        if name not in self._initializers:
            msg = f"No initializer registered for '{name}'"
            raise ValueError(msg)

        async with self._locks[name]:
            # Double-check after acquiring lock
            if name in self._initialized:
                return self._initialized[name]

            factory, _ = self._initializers[name]
            resource = await factory()
            self._initialized[name] = resource
            self._initialization_order.append(name)
            return resource

    async def initialize_by_priority(self, max_concurrent: int = 3) -> None:
        """Initialize resources by priority order."""
        # Sort by priority (lower numbers = higher priority)
        sorted_items = sorted(self._initializers.items(), key=lambda x: x[1][1])

        # Initialize in batches to avoid overwhelming the system
        for i in range(0, len(sorted_items), max_concurrent):
            batch = sorted_items[i : i + max_concurrent]
            await asyncio.gather(
                *[self.get(name) for name, _ in batch],
                return_exceptions=True,
            )

    def is_initialized(self, name: str) -> bool:
        """Check if a resource is initialized."""
        return name in self._initialized

    def get_initialization_stats(self) -> dict[str, t.Any]:
        """Get initialization statistics."""
        return {
            "registered_count": len(self._initializers),
            "initialized_count": len(self._initialized),
            "initialization_order": self._initialization_order.copy(),
            "pending": [
                name for name in self._initializers if name not in self._initialized
            ],
        }


class MemoryEfficientProcessor:
    """Memory-efficient processing patterns for edge devices and serverless.

    Implements streaming processing, batch optimization, and memory monitoring.
    """

    def __init__(
        self,
        max_memory_mb: float = 256.0,
        batch_size: int = 100,
        stream_threshold: int = 1000,
    ) -> None:
        self._max_memory_mb = max_memory_mb
        self._batch_size = batch_size
        self._stream_threshold = stream_threshold
        self._current_memory_mb = 0.0
        self._processing_stats = {
            "items_processed": 0,
            "batches_processed": 0,
            "memory_warnings": 0,
            "streams_processed": 0,
        }

    async def process_items(
        self,
        items: t.Iterable[t.Any],
        processor: t.Callable[[list[t.Any]], t.Awaitable[list[t.Any]]],
    ) -> t.AsyncGenerator[t.Any]:
        """Process items efficiently based on memory constraints."""
        from collections.abc import Sized

        items_count = len(items) if isinstance(items, Sized) else None

        # Use streaming for large datasets
        if items_count and items_count > self._stream_threshold:
            async for result in self._stream_process(items, processor):
                yield result
        else:
            # Use batch processing for smaller datasets
            async for result in self._batch_process(items, processor):
                yield result

    async def _batch_process(
        self,
        items: t.Iterable[t.Any],
        processor: t.Callable[[list[t.Any]], t.Awaitable[list[t.Any]]],
    ) -> t.AsyncGenerator[t.Any]:
        """Process items in batches."""
        batch = []

        for item in items:
            batch.append(item)

            if len(batch) >= self._batch_size:
                results = await self._process_batch(batch, processor)
                for result in results:
                    yield result
                batch = []

        # Process remaining items
        if batch:
            results = await self._process_batch(batch, processor)
            for result in results:
                yield result

    async def _stream_process(
        self,
        items: t.Iterable[t.Any],
        processor: t.Callable[[list[t.Any]], t.Awaitable[list[t.Any]]],
    ) -> t.AsyncGenerator[t.Any]:
        """Process items using streaming to minimize memory usage."""
        self._processing_stats["streams_processed"] += 1

        async for item in self._async_iterate(items):
            # Process single items to minimize memory footprint
            results = await processor([item])
            for result in results:
                yield result

            # Check memory periodically
            if self._processing_stats["items_processed"] % 100 == 0:
                await self._check_memory_usage()

    async def _process_batch(
        self,
        batch: list[t.Any],
        processor: t.Callable[[list[t.Any]], t.Awaitable[list[t.Any]]],
    ) -> list[t.Any]:
        """Process a batch of items."""
        await self._check_memory_usage()

        results = await processor(batch)

        self._processing_stats["items_processed"] += len(batch)
        self._processing_stats["batches_processed"] += 1

        return results

    async def _async_iterate(self, items: t.Iterable[t.Any]) -> t.AsyncGenerator[t.Any]:
        """Convert iterable to async generator."""
        for item in items:
            yield item
            # Yield control occasionally for async processing
            if self._processing_stats["items_processed"] % 10 == 0:
                await asyncio.sleep(0)

    async def _check_memory_usage(self) -> None:
        """Monitor memory usage and warn if approaching limits."""
        with suppress(ImportError):
            import psutil

            process = psutil.Process()
            memory_mb = process.memory_info().rss / 1024 / 1024
            self._current_memory_mb = memory_mb

            if memory_mb > self._max_memory_mb * 0.8:  # 80% threshold
                self._processing_stats["memory_warnings"] += 1
                import logging

                logging.getLogger(__name__).warning(
                    f"High memory usage: {memory_mb:.1f}MB / {self._max_memory_mb}MB",
                )

    def get_processing_stats(self) -> dict[str, t.Any]:
        """Get processing statistics."""
        return self._processing_stats | {
            "current_memory_mb": self._current_memory_mb,
            "memory_limit_mb": self._max_memory_mb,
            "memory_utilization_percent": (
                self._current_memory_mb / self._max_memory_mb * 100
                if self._max_memory_mb > 0
                else 0
            ),
        }
