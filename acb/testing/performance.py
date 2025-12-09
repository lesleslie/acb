"""ACB Performance Testing Utilities.

Provides performance testing tools, benchmarking utilities, and
load testing capabilities specifically designed for ACB applications.

Features:
- Performance timers and measurement
- Benchmark runners with statistical analysis
- Load testing and stress testing
- Memory usage profiling
- Metrics collection and analysis
"""

import os
import time
from statistics import mean, median, stdev

import asyncio
import psutil
import typing as t
from contextlib import asynccontextmanager, contextmanager
from dataclasses import dataclass, field


@dataclass
class PerformanceMetrics:
    """Container for performance metrics."""

    execution_time: float
    memory_before: int
    memory_after: int
    memory_peak: int
    cpu_percent: float
    timestamp: float = field(default_factory=time.time)

    @property
    def memory_delta(self) -> int:
        """Memory usage delta in bytes."""
        return self.memory_after - self.memory_before

    @property
    def memory_delta_mb(self) -> float:
        """Memory usage delta in MB."""
        return self.memory_delta / 1024 / 1024


class PerformanceTimer:
    """High-precision timer for measuring execution time."""

    def __init__(self) -> None:
        self.start_time: float = 0
        self.end_time: float = 0
        self.elapsed: float = 0

    def start(self) -> None:
        """Start the timer."""
        self.start_time = time.perf_counter()

    def stop(self) -> float:
        """Stop the timer and return elapsed time."""
        self.end_time = time.perf_counter()
        self.elapsed = self.end_time - self.start_time
        return self.elapsed

    def __enter__(self) -> "PerformanceTimer":
        self.start()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: t.Any,
    ) -> None:
        self.stop()

    async def __aenter__(self) -> "PerformanceTimer":
        self.start()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: t.Any,
    ) -> None:
        self.stop()


class BenchmarkRunner:
    """Run benchmark tests with statistical analysis."""

    def __init__(
        self,
        warmup_rounds: int = 3,
        test_rounds: int = 10,
        collect_memory: bool = True,
    ) -> None:
        self.warmup_rounds = warmup_rounds
        self.test_rounds = test_rounds
        self.collect_memory = collect_memory
        self.results: list[dict[str, t.Any]] = []

    async def _execute_function(
        self,
        func: t.Callable[..., t.Any],
        *args: t.Any,
        **kwargs: t.Any,
    ) -> None:
        """Execute function (async or sync)."""
        if asyncio.iscoroutinefunction(func):
            await func(*args, **kwargs)
        else:
            func(*args, **kwargs)

    async def _run_warmup_rounds(
        self,
        func: t.Callable[..., t.Any],
        *args: t.Any,
        **kwargs: t.Any,
    ) -> None:
        """Run warmup rounds before benchmark."""
        for _ in range(self.warmup_rounds):
            await self._execute_function(func, *args, **kwargs)

    async def _execute_test_round(
        self,
        func: t.Callable[..., t.Any],
        process: psutil.Process,
        baseline_memory: int,
        execution_times: list[float],
        memory_deltas: list[int],
        memory_peaks: list[int],
        *args: t.Any,
        **kwargs: t.Any,
    ) -> None:
        """Execute a single test round and collect metrics."""
        memory_before = process.memory_info().rss if self.collect_memory else 0

        with PerformanceTimer() as timer:
            await self._execute_function(func, *args, **kwargs)

        memory_after = process.memory_info().rss if self.collect_memory else 0
        memory_peak = memory_after  # Simplified peak detection

        execution_times.append(timer.elapsed)
        if self.collect_memory:
            memory_deltas.append(memory_after - memory_before)
            memory_peaks.append(memory_peak - baseline_memory)

    def _calculate_execution_stats(
        self,
        test_name: str,
        execution_times: list[float],
    ) -> dict[str, t.Any]:
        """Calculate execution statistics."""
        return {
            "name": test_name,
            "warmup_rounds": self.warmup_rounds,
            "test_rounds": self.test_rounds,
            "execution_times": execution_times,
            "stats": {
                "mean_time": mean(execution_times),
                "median_time": median(execution_times),
                "min_time": min(execution_times),
                "max_time": max(execution_times),
                "std_dev": stdev(execution_times) if len(execution_times) > 1 else 0,
                "ops_per_second": 1.0 / mean(execution_times) if execution_times else 0,
            },
            "timestamp": time.time(),
        }

    def _add_memory_stats(
        self,
        result: dict[str, t.Any],
        memory_deltas: list[int],
        memory_peaks: list[int],
    ) -> None:
        """Add memory statistics to result."""
        if self.collect_memory and memory_deltas:
            result["memory_stats"] = {
                "mean_delta_mb": mean(memory_deltas) / 1024 / 1024,
                "median_delta_mb": median(memory_deltas) / 1024 / 1024,
                "min_delta_mb": min(memory_deltas) / 1024 / 1024,
                "max_delta_mb": max(memory_deltas) / 1024 / 1024,
                "mean_peak_mb": mean(memory_peaks) / 1024 / 1024,
            }

    async def run_benchmark(
        self,
        func: t.Callable[..., t.Any],
        *args: t.Any,
        name: str | None = None,
        **kwargs: t.Any,
    ) -> dict[str, t.Any]:
        """Run a benchmark test with statistical analysis."""
        test_name = name or func.__name__
        process = psutil.Process(os.getpid())

        # Warmup rounds
        await self._run_warmup_rounds(func, *args, **kwargs)

        # Collect baseline memory
        baseline_memory = process.memory_info().rss if self.collect_memory else 0

        # Test rounds
        execution_times: list[float] = []
        memory_deltas: list[int] = []
        memory_peaks: list[int] = []

        for _ in range(self.test_rounds):
            await self._execute_test_round(
                func,
                process,
                baseline_memory,
                execution_times,
                memory_deltas,
                memory_peaks,
                *args,
                **kwargs,
            )

        # Calculate statistics
        result = self._calculate_execution_stats(test_name, execution_times)
        self._add_memory_stats(result, memory_deltas, memory_peaks)

        self.results.append(result)
        return result

    def compare_benchmarks(
        self,
        baseline_name: str,
        comparison_name: str,
    ) -> dict[str, t.Any]:
        """Compare two benchmark results."""
        baseline = next((r for r in self.results if r["name"] == baseline_name), None)
        comparison = next(
            (r for r in self.results if r["name"] == comparison_name),
            None,
        )

        if not baseline or not comparison:
            msg = "Benchmark results not found for comparison"
            raise ValueError(msg)

        baseline_time = baseline["stats"]["mean_time"]
        comparison_time = comparison["stats"]["mean_time"]

        speedup = baseline_time / comparison_time if comparison_time > 0 else 0
        percentage_change = ((comparison_time - baseline_time) / baseline_time) * 100

        return {
            "baseline": baseline_name,
            "comparison": comparison_name,
            "baseline_time": baseline_time,
            "comparison_time": comparison_time,
            "speedup": speedup,
            "percentage_change": percentage_change,
            "faster": comparison_time < baseline_time,
        }


class LoadTestRunner:
    """Run load tests with concurrent operations."""

    def __init__(self, concurrent_users: int = 10, duration: float = 60.0) -> None:
        self.concurrent_users = concurrent_users
        self.duration = duration
        self.results: list[dict[str, t.Any]] = []

    async def run_load_test(
        self,
        func: t.Callable[..., t.Any],
        *args: t.Any,
        name: str | None = None,
        **kwargs: t.Any,
    ) -> dict[str, t.Any]:
        """Run a load test with concurrent operations."""
        test_name = name or func.__name__
        start_time = time.perf_counter()
        end_time = start_time + self.duration

        # Shared counters
        completed_requests = 0
        failed_requests = 0
        response_times = []
        errors = []

        # Create and run the worker tasks
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
                except Exception as e:
                    failed_requests += 1
                    errors.append(str(e))

                request_end = time.perf_counter()
                response_times.append(request_end - request_start)

                # Small delay to prevent overwhelming
                await asyncio.sleep(0.001)

        # Run concurrent workers
        tasks = [worker() for _ in range(self.concurrent_users)]
        await asyncio.gather(*tasks)

        actual_duration = time.perf_counter() - start_time
        total_requests = completed_requests + failed_requests

        result = self._create_result_dict(
            test_name,
            actual_duration,
            total_requests,
            completed_requests,
            failed_requests,
            response_times,
            errors,
        )

        self.results.append(result)
        return result

    def _create_result_dict(
        self,
        test_name: str,
        actual_duration: float,
        total_requests: int,
        completed_requests: int,
        failed_requests: int,
        response_times: list[float],
        errors: list[str],
    ) -> dict[str, t.Any]:
        """Create the result dictionary for a load test."""
        return {
            "name": test_name,
            "concurrent_users": self.concurrent_users,
            "planned_duration": self.duration,
            "actual_duration": actual_duration,
            "total_requests": total_requests,
            "completed_requests": completed_requests,
            "failed_requests": failed_requests,
            "failure_rate": failed_requests / total_requests
            if total_requests > 0
            else 0,
            "throughput": completed_requests / actual_duration
            if actual_duration > 0
            else 0,
            "response_time_stats": {
                "mean": mean(response_times) if response_times else 0,
                "median": median(response_times) if response_times else 0,
                "min": min(response_times) if response_times else 0,
                "max": max(response_times) if response_times else 0,
                "std_dev": stdev(response_times) if len(response_times) > 1 else 0,
            },
            "errors": errors[:10],  # Store first 10 errors
            "timestamp": time.time(),
        }


class MetricsCollector:
    """Collect and analyze performance metrics."""

    def __init__(self) -> None:
        self.metrics: dict[str, list[dict[str, t.Any]]] = {}
        self.start_time = time.perf_counter()

    def record_metric(
        self,
        name: str,
        value: float,
        tags: dict[str, t.Any] | None = None,
    ) -> None:
        """Record a performance metric."""
        if name not in self.metrics:
            self.metrics[name] = []

        timestamp = time.perf_counter() - self.start_time
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
        if not values:
            return None

        return {
            "count": len(values),
            "mean": mean(values),
            "median": median(values),
            "min": min(values),
            "max": max(values),
            "std_dev": stdev(values) if len(values) > 1 else 0,
            "latest": values[-1],
        }

    def get_all_metrics(self) -> dict[str, dict[str, t.Any]]:
        """Get all metrics summaries."""
        summaries = {}
        for name in self.metrics:
            summary = self.get_metric_summary(name)
            if summary is not None:
                summaries[name] = summary
        return summaries

    @contextmanager
    def measure_operation(self, operation_name: str) -> t.Iterator[None]:
        """Context manager to measure an operation."""
        start_time = time.perf_counter()
        try:
            yield
        finally:
            end_time = time.perf_counter()
            self.record_metric(f"{operation_name}_duration", end_time - start_time)


def assert_performance_threshold(
    execution_time: float,
    max_time: float,
    memory_usage: int | None = None,
    max_memory: int | None = None,
    ops_per_second: float | None = None,
    min_ops_per_second: float | None = None,
) -> None:
    """Assert that performance metrics meet specified thresholds."""
    assert execution_time <= max_time, (
        f"Execution time {execution_time:.4f}s exceeds threshold {max_time:.4f}s"
    )

    if memory_usage is not None and max_memory is not None:
        assert memory_usage <= max_memory, (
            f"Memory usage {memory_usage / 1024 / 1024:.2f}MB exceeds threshold {max_memory / 1024 / 1024:.2f}MB"
        )

    if ops_per_second is not None and min_ops_per_second is not None:
        assert ops_per_second >= min_ops_per_second, (
            f"Operations per second {ops_per_second:.2f} below threshold {min_ops_per_second:.2f}"
        )


def measure_execution_time(func: t.Callable[..., t.Any]) -> t.Callable[..., t.Any]:
    """Decorator to measure function execution time."""
    if asyncio.iscoroutinefunction(func):

        async def async_wrapper(*args: t.Any, **kwargs: t.Any) -> t.Any:
            async with PerformanceTimer():
                return await func(*args, **kwargs)

        return async_wrapper

    def sync_wrapper(*args: t.Any, **kwargs: t.Any) -> t.Any:
        with PerformanceTimer():
            return func(*args, **kwargs)

    return sync_wrapper


def profile_memory_usage(func: t.Callable[..., t.Any]) -> t.Callable[..., t.Any]:
    """Decorator to profile memory usage."""

    def wrapper(*args: t.Any, **kwargs: t.Any) -> t.Any:
        process = psutil.Process(os.getpid())
        memory_before = process.memory_info().rss

        result = func(*args, **kwargs)

        memory_after = process.memory_info().rss
        _memory_delta = memory_after - memory_before  # Store for potential logging

        return result

    return wrapper


@asynccontextmanager
async def performance_monitor(
    name: str,
    thresholds: dict[str, t.Any] | None = None,
) -> t.AsyncIterator[MetricsCollector]:
    """Context manager for comprehensive performance monitoring."""
    process = psutil.Process(os.getpid())
    metrics_collector = MetricsCollector()

    # Record baseline
    memory_before = process.memory_info().rss
    cpu_before = process.cpu_percent()

    start_time = time.perf_counter()

    try:
        yield metrics_collector
    finally:
        end_time = time.perf_counter()
        execution_time = end_time - start_time

        # Record final metrics
        memory_after = process.memory_info().rss
        cpu_after = process.cpu_percent()

        # Store performance report (could be logged or returned)
        _performance_report = {
            "name": name,
            "execution_time": execution_time,
            "memory_before_mb": memory_before / 1024 / 1024,
            "memory_after_mb": memory_after / 1024 / 1024,
            "memory_delta_mb": (memory_after - memory_before) / 1024 / 1024,
            "cpu_before": cpu_before,
            "cpu_after": cpu_after,
            "metrics": metrics_collector.get_all_metrics(),
            "timestamp": time.time(),
        }

        # Check thresholds if provided
        if thresholds:
            if "max_time" in thresholds:
                assert_performance_threshold(execution_time, thresholds["max_time"])

            if "max_memory_mb" in thresholds:
                memory_delta_mb = (memory_after - memory_before) / 1024 / 1024
                assert memory_delta_mb <= thresholds["max_memory_mb"], (
                    f"Memory usage {memory_delta_mb:.2f}MB exceeds threshold {thresholds['max_memory_mb']:.2f}MB"
                )
