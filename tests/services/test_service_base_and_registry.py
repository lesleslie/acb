"""Unit tests for ServiceBase lifecycle and ServiceRegistry behavior."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from typing import Any

from acb.services._base import (
    ServiceBase,
    ServiceConfig,
    ServiceSettings,
    ServiceStatus,
)
from acb.services.registry import ServiceNotFoundError, ServiceRegistry


class _DummyService(ServiceBase):
    async def _initialize(self) -> None:  # minimal init
        self.set_custom_metric("ready", True)

    async def _shutdown(self) -> None:  # minimal shutdown
        self.set_custom_metric("ready", False)

    async def _health_check(self) -> dict[str, Any]:
        return {"ok": True}


@pytest.mark.unit
@pytest.mark.asyncio
async def test_service_base_lifecycle_basic() -> None:
    cfg = ServiceConfig(service_id="svc1", name="Svc1")
    st = ServiceSettings(health_check_enabled=False)

    svc = _DummyService(cfg, st)
    # inject a plain logger to avoid DI lookups
    svc.logger = MagicMock()

    await svc.initialize()
    assert svc.status == ServiceStatus.ACTIVE
    assert svc.get_custom_metric("ready") is True

    health = await svc.health_check()
    assert health["healthy"] is True
    assert health["service_specific"] == {"ok": True}

    await svc.shutdown()
    assert svc.status == ServiceStatus.STOPPED
    assert svc.get_custom_metric("ready") is False


@pytest.mark.unit
@pytest.mark.asyncio
async def test_service_registry_register_lookup_health_and_order() -> None:
    reg = ServiceRegistry()

    # Create two services with dependency and priority
    a_cfg = ServiceConfig(service_id="A", name="A", priority=50)
    b_cfg = ServiceConfig(service_id="B", name="B", dependencies=["A"], priority=100)

    a = _DummyService(a_cfg, ServiceSettings(health_check_enabled=False))
    b = _DummyService(b_cfg, ServiceSettings(health_check_enabled=False))
    a.logger = MagicMock()
    b.logger = MagicMock()

    await reg.register_service(a)
    await reg.register_service(b)

    assert set(reg.list_services()) == {"A", "B"}
    assert reg.get_service_config("A").service_id == "A"

    # Initialize all: A must be initialized before B, and both become active
    await reg.initialize_all()
    assert reg.get_service("A").status == ServiceStatus.ACTIVE
    assert reg.get_service("B").status == ServiceStatus.ACTIVE

    health_all = await reg.get_health_status()
    assert health_all["overall_healthy"] is True
    assert health_all["healthy_services"] == 2
    assert health_all["total_services"] == 2

    # Filter by status
    active = reg.get_services_by_status("active")
    assert len(active) == 2
    none_status = reg.get_services_by_status("missing")
    assert none_status == []

    # Shutdown and unregister
    await reg.shutdown_all()
    await reg.unregister_service("A")
    await reg.unregister_service("B")
    assert reg.list_services() == []

    with pytest.raises(ServiceNotFoundError):
        reg.get_service_config("A")
