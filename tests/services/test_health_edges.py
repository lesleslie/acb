"""Additional edge tests for health reporter/system summarization."""

from __future__ import annotations

import pytest

from acb.services.health import (
    HealthCheckResult,
    HealthCheckType,
    HealthReporter,
    HealthReporterSettings,
    HealthStatus,
)


@pytest.mark.unit
def test_get_system_health_with_fresh_results_paths() -> None:
    reporter = HealthReporter(HealthReporterSettings())

    # No components registered
    system = reporter.get_system_health()
    assert system["components"]["total"] == 0

    # Feed fresh results to exercise critical/unhealthy/degraded branches
    fresh = {
        "a": HealthCheckResult(
            component_id="a",
            component_name="A",
            status=HealthStatus.CRITICAL,
            check_type=HealthCheckType.LIVENESS,
        ),
        "b": HealthCheckResult(
            component_id="b",
            component_name="B",
            status=HealthStatus.UNHEALTHY,
            check_type=HealthCheckType.LIVENESS,
        ),
        "c": HealthCheckResult(
            component_id="c",
            component_name="C",
            status=HealthStatus.DEGRADED,
            check_type=HealthCheckType.LIVENESS,
        ),
    }
    system2 = reporter.get_system_health(fresh)
    # Critical present -> critical system
    assert system2["system_status"] == "critical"
    assert system2["components"]["critical"] == 1
    assert system2["components"]["unhealthy"] == 1
    assert system2["components"]["degraded"] == 1
