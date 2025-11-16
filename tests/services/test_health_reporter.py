"""Unit tests for HealthReporter and HealthService summaries."""

from __future__ import annotations

import pytest

from acb.services.health import (
    HealthCheckMixin,
    HealthCheckResult,
    HealthCheckType,
    HealthReporter,
    HealthService,
    HealthStatus,
)


class _DummyComponent(HealthCheckMixin):
    def __init__(self, comp_id: str, status: HealthStatus) -> None:
        super().__init__()
        self._cid = comp_id
        self._st = status

    @property
    def component_id(self) -> str:  # override for stability
        return self._cid

    @property
    def component_name(self) -> str:
        return f"comp-{self._cid}"

    async def _perform_health_check(
        self, check_type: HealthCheckType
    ) -> HealthCheckResult:  # type: ignore[override]
        return HealthCheckResult(
            component_id=self.component_id,
            component_name=self.component_name,
            status=self._st,
            check_type=check_type,
            message="ok" if self._st == HealthStatus.HEALTHY else "warn",
        )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_health_reporter_registration_and_summary() -> None:
    rep = HealthReporter()
    a = _DummyComponent("a", HealthStatus.HEALTHY)
    b = _DummyComponent("b", HealthStatus.DEGRADED)
    c = _DummyComponent("c", HealthStatus.UNHEALTHY)
    rep.register_component(a)
    rep.register_component(b)
    rep.register_component(c)

    results = await rep.check_all_components(HealthCheckType.LIVENESS)
    assert set(results.keys()) == {"a", "b", "c"}
    assert results["a"].is_healthy and not results["c"].is_healthy

    summary = rep.get_system_health(results)
    assert summary["components"]["total"] == 3
    assert summary["components"]["healthy"] >= 1
    assert summary["system_status"] in ("degraded", "unhealthy", "critical")

    hist = rep.get_component_history("a", limit=1)
    assert len(hist) == 1 and hist[0].component_id == "a"

    # History limit behavior and cached system health (no fresh_results)
    # Push multiple entries
    for _ in range(6):
        rep._update_history("a", results["a"])  # type: ignore[attr-defined]
    limited = rep.get_component_history("a", limit=3)
    assert len(limited) == 3
    cached_summary = rep.get_system_health()
    assert cached_summary["components"]["total"] == 3


@pytest.mark.unit
@pytest.mark.asyncio
async def test_health_service_check_system_health() -> None:
    svc = HealthService()
    # register via service API to reporter
    svc.register_component(_DummyComponent("x", HealthStatus.HEALTHY))
    svc.register_component(_DummyComponent("y", HealthStatus.UNHEALTHY))

    system = await svc.check_system_health()
    assert "component_results" in system
    assert system["components"]["total"] == 2
    assert system["system_status"] in ("degraded", "unhealthy")

    # Not found component check returns None
    not_found = await svc.check_component_health("missing")
    assert not_found is None
