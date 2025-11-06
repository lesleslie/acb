"""Unit tests for monitoring health utilities."""

from __future__ import annotations

import time

import pytest

from acb.monitoring.health import (
    ComponentHealth,
    HealthCheckResponse,
    HealthStatus,
)


@pytest.mark.unit
def test_health_status_ordering() -> None:
    assert HealthStatus.HEALTHY < HealthStatus.DEGRADED
    assert HealthStatus.DEGRADED < HealthStatus.UNHEALTHY
    assert HealthStatus.UNHEALTHY > HealthStatus.HEALTHY


@pytest.mark.unit
def test_component_health_to_dict_rounding_and_metadata() -> None:
    ch = ComponentHealth(
        name="database",
        status=HealthStatus.DEGRADED,
        message="slow",
        latency_ms=12.3456,
        metadata={"connections": 10},
    )
    d = ch.to_dict()
    assert d["name"] == "database"
    assert d["status"] == "degraded"
    assert d["message"] == "slow"
    # latency is rounded to 2 decimals
    assert d["latency_ms"] == 12.35
    assert d["metadata"] == {"connections": 10}


@pytest.mark.unit
def test_health_check_response_create_no_components_and_to_dict() -> None:
    start = time.time() - 3.5
    resp = HealthCheckResponse.create(
        components=[],
        version="1.2.3",
        start_time=start,
    )
    assert resp.status == HealthStatus.HEALTHY
    assert resp.version == "1.2.3"
    td = resp.to_dict()
    assert td["status"] == "healthy"
    assert isinstance(td["uptime_seconds"], float)
    assert td["uptime_seconds"] >= 0.0
    assert td["components"] == []
    # timestamp is ISO format
    assert "T" in td["timestamp"]


@pytest.mark.unit
def test_health_check_response_aggregation_and_metadata() -> None:
    components = [
        ComponentHealth("cache", HealthStatus.HEALTHY),
        ComponentHealth("db", HealthStatus.DEGRADED),
        ComponentHealth("mq", HealthStatus.UNHEALTHY),
    ]
    resp = HealthCheckResponse.create(
        components=components,
        version="9.9.9",
        start_time=time.time(),
        metadata={"env": "test"},
    )
    assert resp.status == HealthStatus.UNHEALTHY
    td = resp.to_dict()
    assert td["metadata"] == {"env": "test"}
    assert len(td["components"]) == 3
    assert any(c["status"] == "unhealthy" for c in td["components"])


@pytest.mark.unit
def test_is_healthy_and_is_ready() -> None:
    resp_ok = HealthCheckResponse(
        status=HealthStatus.HEALTHY,
        timestamp="t",
        version="v",
        components=[],
        uptime_seconds=0.0,
    )
    resp_bad = HealthCheckResponse(
        status=HealthStatus.UNHEALTHY,
        timestamp="t",
        version="v",
        components=[],
        uptime_seconds=0.0,
    )

    assert resp_ok.is_healthy() is True
    assert resp_ok.is_ready() is True
    assert resp_bad.is_healthy() is False
    assert resp_bad.is_ready() is False
