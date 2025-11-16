from collections.abc import AsyncGenerator

from typing import Any

"""Performance Test Provider for ACB Testing.

Provides performance testing utilities, benchmarking tools, and
load testing capabilities for ACB applications.

Features:
- Performance benchmarking and profiling
- Load testing and stress testing
- Memory usage monitoring
- Execution time measurement
- Throughput and latency analysis
"""

import time

import asyncio
import typing as t
from contextlib import asynccontextmanager

from acb.testing.discovery import (
    TestProviderCapability,
    create_test_provider_metadata_template,
)

# Provider metadata
PROVIDER_METADATA = create_test_provider_metadata_template(
    name="Performance Test Provider",
    category="performance",
    provider_type="performance_test",
    author="ACB Testing Team",
    description="Performance testing and benchmarking utilities for ACB applications",
    version="1.0.0",
    capabilities=[
        TestProviderCapability.PERFORMANCE_TESTING,
        TestProviderCapability.LOAD_TESTING,
        TestProviderCapability.BENCHMARKING,
        TestProviderCapability.PROFILING,
        TestProviderCapability.MEMORY_TESTING,
        TestProviderCapability.CONCURRENT_TESTING,
    ],
    settings_class="PerformanceTestProviderSettings",
)


class PerformanceTestProvider:
    """Provider for performance testing utilities."""

    PROVIDER_METADATA = PROVIDER_METADATA

    def __init__(self) -> None:
        self._benchmarks: dict[str, t.Any] = {}
        self._load_tests: dict[str, t.Any] = {}
        self._profiles: dict[str, t.Any] = {}

    class PerformanceTimer:
        """Context manager for measuring execution time."""

        def __init__(self) -> None:
            self.start_time: float = 0
            self.end_time: float = 0
            self.elapsed: float = 0

        def __enter__(self) -> "PerformanceTestProvider.PerformanceTimer":
            self.start_time = time.perf_counter()
            return self

        def __exit__(
            self,
            exc_type: type[BaseException] | None,
            exc_val: BaseException | None,
            exc_tb: Any,
        ) -> None:
            self.end_time = time.perf_counter()
            self.elapsed = self.end_time - self.start_time

        async def __aenter__(self) -> "PerformanceTestProvider.PerformanceTimer":
            self.start_time = time.perf_counter()
            return self

        async def __aexit__(
            self,
            exc_type: type[BaseException] | None,
            exc_val: BaseException | None,
            exc_tb: Any,
        ) -> None:
            self.end_time = time.perf_counter()
            self.elapsed = self.end_time - self.start_time

    class BenchmarkRunner:
        """Benchmark runner for performance testing."""

        def __init__(self, warmup_rounds: int = 3, test_rounds: int = 10) -> None:
            self.warmup_rounds = warmup_rounds
            self.test_rounds = test_rounds
            self.results: list[t.Any] = []

        async def run_benchmark(
            self,
            func: t.Callable[..., Any],
            *args: Any,
            **kwargs: Any,
        ) -> dict[str, t.Any]:
            """Run a benchmark test."""
            # Warmup rounds
            for _ in range(self.warmup_rounds):
                if asyncio.iscoroutinefunction(func):
                    await func(*args, **kwargs)
                else:
                    func(*args, **kwargs)

            # Test rounds
            times = []
            for _ in range(self.test_rounds):
                timer = PerformanceTestProvider.PerformanceTimer()
                with timer:
                    if asyncio.iscoroutinefunction(func):
                        await func(*args, **kwargs)
                    else:
                        func(*args, **kwargs)
                times.append(timer.elapsed)

            # Calculate statistics
            avg_time = sum(times) / len(times)
            min_time = min(times)
            max_time = max(times)
            std_dev = (sum((t - avg_time) ** 2 for t in times) / len(times)) ** 0.5

            result = {
                "function": func.__name__,
                "warmup_rounds": self.warmup_rounds,
                "test_rounds": self.test_rounds,
                "times": times,
                "avg_time": avg_time,
                "min_time": min_time,
                "max_time": max_time,
                "std_dev": std_dev,
                "ops_per_second": 1.0 / avg_time if avg_time > 0 else 0,
            }

            self.results.append(result)
            return result

    class LoadTestRunner:
        """Load testing runner for stress testing."""

        def __init__(self, concurrent_users: int = 10, duration: float = 60.0) -> None:
            self.concurrent_users = concurrent_users
            self.duration = duration
            self.results: list[t.Any] = []

        async def run_load_test(
            self,
            func: t.Callable[..., Any],
            *args: Any,
            **kwargs: Any,
        ) -> dict[str, t.Any]:
            """Run a load test."""
            start_time = time.perf_counter()
            end_time = start_time + self.duration

            # Track results
            completed_requests = 0
            failed_requests = 0
            response_times = []

            async def worker() -> None:
                nonlocal completed_requests, failed_requests

                while time.perf_counter() < end_time:
                    request_start = time.perf_counter()
                    try:
                        if asyncio.iscoroutinefunction(func):
                            await func(*args, **kwargs)
                        else:
                            func(*args, **kwargs)
                        completed_requests += 1
                    except Exception:
                        failed_requests += 1

                    request_end = time.perf_counter()
                    response_times.append(request_end - request_start)

                    # Small delay to prevent overwhelming
                    await asyncio.sleep(0.001)

            # Run concurrent workers
            tasks = [worker() for _ in range(self.concurrent_users)]
            await asyncio.gather(*tasks)

            actual_duration = time.perf_counter() - start_time
            total_requests = completed_requests + failed_requests

            # Calculate statistics
            avg_response_time = (
                sum(response_times) / len(response_times) if response_times else 0
            )
            throughput = (
                completed_requests / actual_duration if actual_duration > 0 else 0
            )

            result = {
                "concurrent_users": self.concurrent_users,
                "duration": actual_duration,
                "total_requests": total_requests,
                "completed_requests": completed_requests,
                "failed_requests": failed_requests,
                "failure_rate": failed_requests / total_requests
                if total_requests > 0
                else 0,
                "throughput": throughput,
                "avg_response_time": avg_response_time,
                "min_response_time": min(response_times) if response_times else 0,
                "max_response_time": max(response_times) if response_times else 0,
            }

            self.results.append(result)
            return result

    class MetricsCollector:
        """Collect performance metrics during testing."""

        def __init__(self) -> None:
            self.metrics: dict[str, t.Any] = {}
            self.start_time = time.perf_counter()

        def record_metric(
            self,
            name: str,
            value: float,
            tags: dict[str, Any] | None = None,
        ) -> None:
            """Record a performance metric."""
            timestamp = time.perf_counter() - self.start_time

            if name not in self.metrics:
                self.metrics[name] = []

            self.metrics[name].append(
                {
                    "value": value,
                    "timestamp": timestamp,
                    "tags": tags or {},
                },
            )

        def get_metric_summary(self, name: str) -> dict[str, t.Any] | None:
            """Get summary statistics for a metric."""
            if name not in self.metrics:
                return None

            values = [entry["value"] for entry in self.metrics[name]]
            return {
                "count": len(values),
                "avg": sum(values) / len(values),
                "min": min(values),
                "max": max(values),
                "latest": values[-1] if values else 0,
            }

        def get_all_metrics(self) -> dict[str, dict[str, Any]]:
            """Get all metrics summaries."""
            return {
                name: summary
                for name in self.metrics
                if (summary := self.get_metric_summary(name)) is not None
            }

    def measure_execution_time(
        self, func: t.Callable[..., Any]
    ) -> t.Callable[..., Any]:
        """Decorator to measure function execution time."""
        if asyncio.iscoroutinefunction(func):

            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                async with self.PerformanceTimer():
                    return await func(*args, **kwargs)

            return async_wrapper

        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            with self.PerformanceTimer():
                return func(*args, **kwargs)

        return sync_wrapper

    def profile_memory_usage(self, func: t.Callable[..., Any]) -> t.Callable[..., Any]:
        """Decorator to profile memory usage (simplified for testing)."""

        def wrapper(*args: Any, **kwargs: Any) -> Any:
            # Simplified memory profiling simulation
            import os

            import psutil

            process = psutil.Process(os.getpid())
            memory_before = process.memory_info().rss

            result = func(*args, **kwargs)

            memory_after = process.memory_info().rss
            _ = memory_after - memory_before  # Memory delta for profiling

            return result

        return wrapper

    def assert_performance_threshold(
        self,
        execution_time: float,
        max_time: float,
        memory_usage: int | None = None,
        max_memory: int | None = None,
    ) -> None:
        """Assert that performance is within acceptable thresholds."""
        assert execution_time <= max_time, (
            f"Execution time {execution_time:.4f}s exceeds threshold {max_time:.4f}s"
        )

        if memory_usage is not None and max_memory is not None:
            assert memory_usage <= max_memory, (
                f"Memory usage {memory_usage} exceeds threshold {max_memory}"
            )

    @asynccontextmanager
    async def performance_test_context(
        self, test_name: str
    ) -> AsyncGenerator[MetricsCollector]:
        """Context manager for performance testing."""
        metrics = self.MetricsCollector()
        start_time = time.perf_counter()

        try:
            yield metrics
        finally:
            end_time = time.perf_counter()
            execution_time = end_time - start_time

            # Store test results
            self._benchmarks[test_name] = {
                "execution_time": execution_time,
                "metrics": metrics.get_all_metrics(),
                "timestamp": "2024-01-01T12:00:00Z",
            }

    def get_benchmark_results(self, test_name: str) -> dict[str, t.Any] | None:
        """Get benchmark results for a specific test."""
        return self._benchmarks.get(test_name)

    def get_all_benchmark_results(self) -> dict[str, dict[str, Any]]:
        """Get all benchmark results."""
        return self._benchmarks.copy()

    def reset_benchmarks(self) -> None:
        """Reset all benchmark data."""
        self._benchmarks.clear()
        self._load_tests.clear()
        self._profiles.clear()
