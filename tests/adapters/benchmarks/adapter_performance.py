"""Performance benchmarks for ACB adapters.

These benchmarks measure adapter performance characteristics to help
identify bottlenecks and track performance improvements over time.
"""

from __future__ import annotations

import time

import asyncio
import pytest
import typing as t

from acb.adapters import import_adapter
from acb.depends import depends


class CacheBenchmarks:
    """Benchmarks for cache adapter performance."""

    @pytest.fixture
    def cache_adapter(self) -> t.Any:
        """Get cache adapter instance."""
        Cache = import_adapter("cache")
        return depends.get(Cache)

    def test_cache_set_operation(self, benchmark: t.Any, cache_adapter: t.Any) -> None:
        """Benchmark single cache set operation.

        Measures: Time to set a single key-value pair in cache.
        Typical: <1ms for memory cache
        """

        async def async_set() -> None:
            await cache_adapter.set("benchmark:key", "benchmark_value", ttl=60)

        def sync_wrapper() -> None:
            asyncio.run(async_set())

        result = benchmark(sync_wrapper)
        assert result is None  # Just verify it completes

    def test_cache_get_operation(self, benchmark: t.Any, cache_adapter: t.Any) -> None:
        """Benchmark single cache get operation.

        Measures: Time to retrieve a value from cache.
        Typical: <1ms for memory cache
        """
        # Pre-populate cache
        asyncio.run(cache_adapter.set("benchmark:key", "benchmark_value", ttl=60))

        async def async_get() -> t.Any:
            return await cache_adapter.get("benchmark:key")

        def sync_wrapper() -> t.Any:
            return asyncio.run(async_get())

        result = benchmark(sync_wrapper)
        assert result == "benchmark_value"

    def test_cache_delete_operation(
        self, benchmark: t.Any, cache_adapter: t.Any
    ) -> None:
        """Benchmark cache delete operation.

        Measures: Time to delete a key from cache.
        Typical: <1ms for memory cache
        """
        # Pre-populate cache
        asyncio.run(cache_adapter.set("benchmark:key", "benchmark_value", ttl=60))

        async def async_delete() -> None:
            await cache_adapter.delete("benchmark:key")

        def sync_wrapper() -> None:
            asyncio.run(async_delete())

        benchmark(sync_wrapper)

    def test_cache_multi_set_bulk_operation(
        self, benchmark: t.Any, cache_adapter: t.Any
    ) -> None:
        """Benchmark bulk set operation with multiple items.

        Measures: Time to set 100 key-value pairs at once.
        Typical: <10ms for memory cache
        """

        async def async_multi_set() -> None:
            items = {f"benchmark:bulk:{i}": f"value:{i}" for i in range(100)}
            await cache_adapter.multi_set(items)

        def sync_wrapper() -> None:
            asyncio.run(async_multi_set())

        benchmark(sync_wrapper)

    def test_cache_concurrent_operations(
        self, benchmark: t.Any, cache_adapter: t.Any
    ) -> None:
        """Benchmark concurrent cache operations.

        Measures: Time for 10 concurrent operations.
        Typical: <10ms for memory cache
        """

        async def concurrent_ops() -> None:
            tasks = []
            for i in range(10):
                tasks.append(cache_adapter.set(f"concurrent:{i}", f"value:{i}", ttl=60))
            await asyncio.gather(*tasks)

        def sync_wrapper() -> None:
            asyncio.run(concurrent_ops())

        benchmark(sync_wrapper)


class AdapterOperationBenchmarks:
    """Benchmarks for various adapter operations."""

    @pytest.fixture
    def cache_adapter(self) -> t.Any:
        """Get cache adapter instance."""
        Cache = import_adapter("cache")
        return depends.get(Cache)

    def test_adapter_initialization_time(self, benchmark: t.Any) -> None:
        """Benchmark adapter initialization.

        Measures: Time to import and initialize adapter.
        Typical: <100ms
        """

        def init_adapter() -> t.Any:
            Cache = import_adapter("cache")
            return depends.get(Cache)

        result = benchmark(init_adapter)
        assert result is not None

    def test_serialization_performance(
        self, benchmark: t.Any, cache_adapter: t.Any
    ) -> None:
        """Benchmark serialization of complex objects.

        Measures: Time to serialize and store a complex object.
        Typical: <5ms
        """
        complex_obj = {
            "user": {"id": 1, "name": "Test", "email": "test@example.com"},
            "metadata": [1, 2, 3, 4, 5],
            "nested": {"level1": {"level2": {"level3": "deep"}}},
        }

        async def serialize_and_store() -> None:
            await cache_adapter.set("complex:object", complex_obj, ttl=60)

        def sync_wrapper() -> None:
            asyncio.run(serialize_and_store())

        benchmark(sync_wrapper)

    def test_cache_with_large_values(
        self, benchmark: t.Any, cache_adapter: t.Any
    ) -> None:
        """Benchmark cache operations with large values.

        Measures: Time to cache a large string (1MB).
        Typical: <20ms for memory cache
        """
        large_value = "x" * (1024 * 1024)  # 1MB string

        async def cache_large() -> None:
            await cache_adapter.set("large:value", large_value, ttl=60)
            await cache_adapter.get("large:value")

        def sync_wrapper() -> None:
            asyncio.run(cache_large())

        benchmark(sync_wrapper)


class AdapterThroughputBenchmarks:
    """Benchmarks for adapter throughput characteristics."""

    @pytest.fixture
    def cache_adapter(self) -> t.Any:
        """Get cache adapter instance."""
        Cache = import_adapter("cache")
        return depends.get(Cache)

    def test_operations_per_second(self, cache_adapter: t.Any) -> float:
        """Measure cache operations per second.

        Shows: How many cache operations can be performed per second.
        Typical: 10,000+ ops/sec for memory cache
        """

        async def run_operations(num_ops: int) -> None:
            for i in range(num_ops):
                await cache_adapter.set(f"throughput:{i}", f"value:{i}", ttl=1)

        start = time.perf_counter()
        asyncio.run(run_operations(1000))
        elapsed = time.perf_counter() - start

        ops_per_sec = 1000 / elapsed
        # Just record, don't assert on specific value (varies by system)
        return ops_per_sec

    def test_batch_operations_efficiency(self, cache_adapter: t.Any) -> None:
        """Compare batch vs individual operations.

        Shows: Whether batch operations are more efficient than individual ones.
        """

        async def individual_ops() -> None:
            for i in range(100):
                await cache_adapter.set(f"individual:{i}", f"value:{i}", ttl=60)

        async def batch_ops() -> None:
            items = {f"batch:{i}": f"value:{i}" for i in range(100)}
            await cache_adapter.multi_set(items)

        # Time individual operations
        start_individual = time.perf_counter()
        asyncio.run(individual_ops())
        time_individual = time.perf_counter() - start_individual

        # Time batch operations
        start_batch = time.perf_counter()
        asyncio.run(batch_ops())
        time_batch = time.perf_counter() - start_batch

        # Batch should generally be faster (though not always for memory cache)
        # This is informational, not a strict assertion
        assert time_batch is not None
        assert time_individual is not None


# Fixture for pytest-benchmark integration
@pytest.fixture(scope="session")
def benchmark_results() -> dict[str, float]:
    """Collect benchmark results for reporting.

    Returns: Dictionary of benchmark names to results.
    """
    return {}
