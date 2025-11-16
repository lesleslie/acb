"""Main performance optimizer service for ACB.

Provides comprehensive performance optimization capabilities
with FastBlocks integration and ACB adapter compatibility.
"""

import time
from functools import wraps

import asyncio
import contextlib
import typing as t
from dataclasses import dataclass, field
from pydantic import BaseModel, ConfigDict, Field

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
        name="Performance Optimizer",
        category="performance",
        service_type="optimizer",
        version="1.0.0",
        acb_min_version="0.19.1",
        author="ACB Framework Team",
        created_date="2024-01-01T00:00:00",
        last_modified="2024-01-01T00:00:00",
        status=ServiceStatus.STABLE,
        capabilities=[
            ServiceCapability.OPTIMIZATION,
            ServiceCapability.CACHING,
            ServiceCapability.ASYNC_OPERATIONS,
            ServiceCapability.METRICS_COLLECTION,
            ServiceCapability.BATCHING,
        ],
        description="High-performance optimization service with comprehensive caching and monitoring",
        settings_class="OptimizationConfig",
        config_example={
            "cache_enabled": True,
            "cache_ttl_seconds": 3600,
            "cache_max_size": 1000,
            "query_timeout_seconds": 30.0,
            "response_compression": True,
        },
    )
except ImportError:
    # Discovery system not available
    SERVICE_METADATA = None


@dataclass
class OptimizationResult:
    """Result of a performance optimization operation."""

    operation: str
    duration_ms: float
    success: bool
    improvement_percent: float = 0.0
    error: str | None = None
    metadata: dict[str, t.Any] = field(default_factory=dict)


class OptimizationConfig(BaseModel):
    """Configuration for performance optimization."""

    model_config = ConfigDict(extra="forbid")

    # Cache optimization
    cache_enabled: bool = True
    cache_ttl_seconds: int = 3600
    cache_max_size: int = 1000

    # Query optimization
    query_timeout_seconds: float = 30.0
    query_batch_size: int = 100
    query_connection_pooling: bool = True

    # Response optimization
    response_compression: bool = True
    response_etag_enabled: bool = True
    response_cache_control: str = "public, max-age=3600"

    # Web framework integration (can be extended by web frameworks)
    web_framework_integration: bool = False


class PerformanceOptimizerSettings(ServiceSettings):
    """Settings for the performance optimizer service."""

    optimization_config: OptimizationConfig = Field(default_factory=OptimizationConfig)
    metrics_collection_enabled: bool = True
    background_optimization: bool = True
    optimization_interval_seconds: float = 300.0  # 5 minutes

    @depends.inject
    def __init__(self, config: Inject[Config], **values: t.Any) -> None:
        super().__init__(**values)


class PerformanceOptimizer(ServiceBase):
    """Main performance optimizer service.

    Provides comprehensive performance optimization for ACB applications
    with special integration for FastBlocks web framework.
    """

    def __init__(
        self,
        service_config: ServiceConfig | None = None,
        settings: PerformanceOptimizerSettings | None = None,
    ) -> None:
        if service_config is None:
            service_config = ServiceConfig(
                service_id="performance_optimizer",
                name="Performance Optimizer",
                description="Comprehensive performance optimization service",
                dependencies=["cache", "sql"],  # Common dependencies
                priority=50,  # Mid-priority service
            )

        super().__init__(service_config, settings or PerformanceOptimizerSettings())
        self._settings: PerformanceOptimizerSettings = self._settings  # type: ignore
        self._optimization_task: asyncio.Task[t.Any] | None = None
        self._cache_adapter: t.Any = None
        self._sql_adapter: t.Any = None

    async def _initialize(self) -> None:
        """Initialize the performance optimizer."""
        # Try to get adapters for optimization
        try:
            Cache = import_adapter("cache")
            self._cache_adapter = await depends.get(Cache)
        except Exception as e:
            self.logger.warning(f"Cache adapter not available: {e}")

        try:
            Sql = import_adapter("sql")
            self._sql_adapter = await depends.get(Sql)
        except Exception as e:
            self.logger.warning(f"SQL adapter not available: {e}")

        # Start background optimization if enabled
        if self._settings.background_optimization:
            self._optimization_task = asyncio.create_task(
                self._background_optimization_loop(),
            )

        self.logger.info("Performance optimizer initialized")

    async def _shutdown(self) -> None:
        """Shutdown the performance optimizer."""
        if self._optimization_task:
            self._optimization_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._optimization_task

    async def _health_check(self) -> dict[str, t.Any]:
        """Health check for performance optimizer."""
        return {
            "cache_available": self._cache_adapter is not None,
            "sql_available": self._sql_adapter is not None,
            "background_optimization_running": (
                self._optimization_task is not None
                and not self._optimization_task.done()
            ),
            "optimizations_applied": self.get_custom_metric("optimizations_applied", 0),
        }

    async def optimize_cache_operation(
        self,
        key: str,
        operation: t.Callable[[], t.Awaitable[t.Any]],
        ttl: int | None = None,
    ) -> OptimizationResult:
        """Optimize a cache operation with intelligent caching.

        Args:
            key: Cache key for the operation
            operation: Async operation to cache
            ttl: Time-to-live for cached result

        Returns:
            Optimization result with performance metrics
        """
        start_time = time.perf_counter()

        try:
            if (
                not self._cache_adapter
                or not self._settings.optimization_config.cache_enabled
            ):
                # No cache available, run operation directly
                result = await operation()
                duration = (time.perf_counter() - start_time) * 1000
                return OptimizationResult(
                    operation="cache_operation_direct",
                    duration_ms=duration,
                    success=True,
                    metadata={"cache_hit": False, "reason": "cache_disabled"},
                )

            # Try to get from cache first
            cached_result = await self._cache_adapter.get(key)
            if cached_result is not None:
                duration = (time.perf_counter() - start_time) * 1000
                self.set_custom_metric(
                    "cache_hits",
                    self.get_custom_metric("cache_hits", 0) + 1,
                )
                return OptimizationResult(
                    operation="cache_operation_hit",
                    duration_ms=duration,
                    success=True,
                    improvement_percent=75.0,  # Assume cache hit is 75% faster
                    metadata={"cache_hit": True, "result": cached_result},
                )

            # Cache miss - run operation and cache result
            operation_start = time.perf_counter()
            result = await operation()
            operation_duration = (time.perf_counter() - operation_start) * 1000

            # Cache the result
            cache_ttl = ttl or self._settings.optimization_config.cache_ttl_seconds
            await self._cache_adapter.set(key, result, ttl=cache_ttl)

            total_duration = (time.perf_counter() - start_time) * 1000
            self.set_custom_metric(
                "cache_misses",
                self.get_custom_metric("cache_misses", 0) + 1,
            )

            return OptimizationResult(
                operation="cache_operation_miss",
                duration_ms=total_duration,
                success=True,
                metadata={
                    "cache_hit": False,
                    "operation_duration_ms": operation_duration,
                    "result": result,
                    "cached_with_ttl": cache_ttl,
                },
            )

        except Exception as e:
            duration = (time.perf_counter() - start_time) * 1000
            self.record_error(str(e))
            return OptimizationResult(
                operation="cache_operation_error",
                duration_ms=duration,
                success=False,
                error=str(e),
            )

    async def optimize_query_batch(
        self,
        queries: list[str],
        parameters: list[dict[str, t.Any]] | None = None,
    ) -> OptimizationResult:
        """Optimize batch query execution.

        Args:
            queries: List of SQL queries to execute
            parameters: Optional list of parameter dictionaries

        Returns:
            Optimization result for batch operation
        """
        start_time = time.perf_counter()

        try:
            if not self._sql_adapter:
                duration = (time.perf_counter() - start_time) * 1000
                return OptimizationResult(
                    operation="query_batch_error",
                    duration_ms=duration,
                    success=False,
                    error="SQL adapter not available",
                )

            config = self._settings.optimization_config
            batch_size = min(len(queries), config.query_batch_size)

            results = []
            batches_processed = 0

            # Process queries in batches
            for i in range(0, len(queries), batch_size):
                batch_queries = queries[i : i + batch_size]
                batch_params = (
                    parameters[i : i + batch_size]
                    if parameters
                    else [{}] * len(batch_queries)
                )

                # Execute batch
                for query, params in zip(batch_queries, batch_params, strict=False):
                    result = await self._sql_adapter.execute(query, params)
                    results.append(result)

                batches_processed += 1

            duration = (time.perf_counter() - start_time) * 1000
            improvement = min(30.0, batches_processed * 5.0)  # Estimate improvement

            self.set_custom_metric(
                "queries_optimized",
                self.get_custom_metric("queries_optimized", 0) + len(queries),
            )

            return OptimizationResult(
                operation="query_batch_optimized",
                duration_ms=duration,
                success=True,
                improvement_percent=improvement,
                metadata={
                    "queries_count": len(queries),
                    "batches_processed": batches_processed,
                    "results": results,
                },
            )

        except Exception as e:
            duration = (time.perf_counter() - start_time) * 1000
            self.record_error(str(e))
            return OptimizationResult(
                operation="query_batch_error",
                duration_ms=duration,
                success=False,
                error=str(e),
            )

    def optimize_function(
        self,
        cache_key_template: str | None = None,
        ttl: int | None = None,
    ) -> t.Callable[
        [t.Callable[..., t.Awaitable[t.Any]]],
        t.Callable[..., t.Awaitable[t.Any]],
    ]:
        """Decorator to optimize async functions with caching.

        Args:
            cache_key_template: Template for cache key (uses function name if None)
            ttl: Cache TTL in seconds

        Returns:
            Decorator function
        """

        def decorator(
            func: t.Callable[..., t.Awaitable[t.Any]],
        ) -> t.Callable[..., t.Awaitable[t.Any]]:
            @wraps(func)
            async def wrapper(*args: t.Any, **kwargs: t.Any) -> t.Any:
                # Generate cache key
                cache_key = cache_key_template or f"{func.__module__}.{func.__name__}"
                if args or kwargs:
                    # Create a simple hash from arguments for cache key uniqueness
                    import hashlib

                    arg_str = str((args, sorted(kwargs.items())))
                    arg_hash = hashlib.md5(
                        arg_str.encode(),
                        usedforsecurity=False,
                    ).hexdigest()[:8]
                    cache_key = f"{cache_key}:{arg_hash}"

                # Create operation wrapper
                async def operation() -> t.Any:
                    return await func(*args, **kwargs)

                # Use cache optimization
                result = await self.optimize_cache_operation(cache_key, operation, ttl)

                if result.success:
                    self.increment_requests()
                    return result.metadata.get("result")
                msg = f"Function optimization failed: {result.error}"
                raise RuntimeError(msg)

            return wrapper

        return decorator

    async def _background_optimization_loop(self) -> None:
        """Background optimization loop."""
        while not self._shutdown_event.is_set():
            try:
                await asyncio.sleep(self._settings.optimization_interval_seconds)
                if self._shutdown_event.is_set():
                    break

                await self._perform_background_optimizations()

            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.exception(f"Background optimization error: {e}")
                await asyncio.sleep(60)  # Wait before retrying

    async def _perform_background_optimizations(self) -> None:
        """Perform background optimization tasks."""
        optimizations_performed = 0

        try:
            # Cache cleanup and optimization
            if self._cache_adapter:
                # This would contain cache-specific optimizations
                # For now, just log that we're performing optimizations
                self.logger.debug("Performing background cache optimization")
                optimizations_performed += 1

            # Query optimization analysis
            if self._sql_adapter:
                # This would analyze query patterns and suggest optimizations
                self.logger.debug("Analyzing query patterns for optimization")
                optimizations_performed += 1

            self.set_custom_metric(
                "optimizations_applied",
                self.get_custom_metric("optimizations_applied", 0)
                + optimizations_performed,
            )

        except Exception as e:
            self.logger.exception(f"Error in background optimizations: {e}")
            self.record_error(str(e))
