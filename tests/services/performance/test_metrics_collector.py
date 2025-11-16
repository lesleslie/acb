"""Unit tests for MetricsCollector helper summaries."""

from __future__ import annotations

import time
from unittest.mock import MagicMock

import pytest

from acb.services.performance.metrics import MetricsCollector


@pytest.mark.unit
@pytest.mark.asyncio
async def test_metrics_record_and_summary(monkeypatch: pytest.MonkeyPatch) -> None:
    mc = MetricsCollector()
    mc.logger = MagicMock()
    now = {"t": time.time()}
    monkeypatch.setattr("acb.services.performance.metrics.time.time", lambda: now["t"])

    # Record response times and errors
    await mc.record_response_time(100.0, endpoint="/x")
    await mc.record_response_time(300.0, endpoint="/x")
    await mc.record_error_metric("500", endpoint="/x")

    # Record cache ops: two hits, one miss
    await mc.record_cache_operation(True)
    await mc.record_cache_operation(True)
    await mc.record_cache_operation(False)

    # Database query
    await mc.record_database_query_time(50.0, query_type="SELECT")

    # Summary should compute hit rate and error rate
    summary = mc.get_metrics_summary("response_time")
    assert summary and summary.count >= 2 and summary.max >= 300.0

    perf = mc.get_current_performance_metrics()
    assert perf.response_times and perf.database_query_times
    assert perf.cache_hit_rates and perf.cache_hit_rates[0] >= 66.0
    assert perf.error_rates and perf.error_rates[0] > 0.0


@pytest.mark.unit
def test_percentile_and_cleanup(monkeypatch: pytest.MonkeyPatch) -> None:
    from acb.services.performance.metrics import PerformanceMetric

    mc = MetricsCollector()
    # Percentile edge cases
    assert mc._percentile([], 95) == 0.0  # type: ignore[attr-defined]
    assert mc._percentile([10], 95) == 10  # type: ignore[attr-defined]
    # Interpolated
    assert mc._percentile([0, 10, 20], 50) == 10  # type: ignore[attr-defined]
    p90 = mc._percentile([0, 10, 20], 90)  # type: ignore[attr-defined]
    assert 18.0 <= p90 <= 20.0

    # Cleanup old metrics
    import asyncio

    now = time.time()
    old = now - (mc._settings.metrics_retention_hours * 3600 + 10)  # type: ignore[attr-defined]
    recent = now
    q = mc._metrics_data["custom"]  # type: ignore[attr-defined]
    q.append(PerformanceMetric(name="custom", value=1.0, timestamp=old))
    q.append(PerformanceMetric(name="custom", value=2.0, timestamp=recent))
    # Run cleanup
    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(mc._cleanup_old_metrics())  # type: ignore[attr-defined]
    finally:
        loop.close()
    assert len(mc._metrics_data["custom"]) == 1  # type: ignore[attr-defined]
