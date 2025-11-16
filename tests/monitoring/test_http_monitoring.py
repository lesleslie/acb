"""Unit tests for HTTP monitoring helpers without real network calls."""

from __future__ import annotations

import pytest
from typing import Any

import acb.monitoring.http as http_mod


class _Resp:
    def __init__(self, status: int) -> None:
        self.status_code = status


class _FakeRequests:
    def __init__(self, behavior: Any) -> None:
        # behavior can be: int status, Exception instance/type, or callable
        self._behavior = behavior

    async def get(self, url: str, timeout: int) -> _Resp:  # type: ignore[override]
        b = self._behavior
        if isinstance(b, int):
            return _Resp(b)
        if isinstance(b, type) and issubclass(b, Exception):
            raise b()  # raise provided exception type
        if isinstance(b, Exception):
            raise b
        if callable(b):
            result = b(url, timeout)
            if isinstance(result, int):
                return _Resp(result)
            if isinstance(result, Exception):
                raise result
        return _Resp(200)


def _set_perf_counter(
    monkeypatch: pytest.MonkeyPatch, start: float, end: float
) -> None:
    seq = iter((start, end))

    def _pc() -> float:
        return next(seq)

    monkeypatch.setattr(http_mod.time, "perf_counter", _pc)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_check_http_client_health_init_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(http_mod, "import_adapter", lambda *_: object())

    def _fail_get_sync(*_: Any, **__: Any) -> Any:
        raise RuntimeError("no adapter")

    monkeypatch.setattr(http_mod.depends, "get_sync", _fail_get_sync)
    res = await http_mod.check_http_client_health()
    assert res.status == http_mod.HealthStatus.UNHEALTHY
    assert "Failed to initialize" in (res.message or "")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_check_http_client_health_no_test_url_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(http_mod, "import_adapter", lambda *_: object())
    monkeypatch.setattr(http_mod.depends, "get_sync", lambda *_: _FakeRequests(200))
    _set_perf_counter(monkeypatch, 100.0, 100.1)  # 100ms
    res = await http_mod.check_http_client_health()
    assert res.status == http_mod.HealthStatus.HEALTHY
    assert "initialized and ready" in (res.message or "")
    assert (res.latency_ms or 0) > 0


@pytest.mark.unit
@pytest.mark.asyncio
async def test_check_http_client_health_http_error_status(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(http_mod, "import_adapter", lambda *_: object())
    monkeypatch.setattr(http_mod.depends, "get_sync", lambda *_: _FakeRequests(503))
    _set_perf_counter(monkeypatch, 10.0, 10.2)
    res = await http_mod.check_http_client_health(test_url="https://e/health")
    assert res.status == http_mod.HealthStatus.DEGRADED
    assert res.metadata.get("status_code") == 503


@pytest.mark.unit
@pytest.mark.asyncio
async def test_check_http_client_health_high_latency(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(http_mod, "import_adapter", lambda *_: object())
    monkeypatch.setattr(http_mod.depends, "get_sync", lambda *_: _FakeRequests(200))
    _set_perf_counter(monkeypatch, 1.0, 1.3)  # 300ms
    res = await http_mod.check_http_client_health(test_url="https://ok", timeout_ms=50)
    assert res.status == http_mod.HealthStatus.DEGRADED
    assert "High latency" in (res.message or "")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_check_http_client_health_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Ensure timeout branch triggers with a controllable exception type
    class _TO(Exception):
        pass

    monkeypatch.setattr(http_mod, "HTTPTimeoutError", _TO)
    monkeypatch.setattr(http_mod, "import_adapter", lambda *_: object())
    monkeypatch.setattr(http_mod.depends, "get_sync", lambda *_: _FakeRequests(_TO))
    _set_perf_counter(monkeypatch, 5.0, 5.5)
    res = await http_mod.check_http_client_health(test_url="https://t")
    assert res.status == http_mod.HealthStatus.DEGRADED
    assert "timeout" in (res.message or "").lower()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_check_http_client_health_generic_exception(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(http_mod, "import_adapter", lambda *_: object())
    monkeypatch.setattr(
        http_mod.depends, "get_sync", lambda *_: _FakeRequests(RuntimeError("boom"))
    )
    _set_perf_counter(monkeypatch, 2.0, 2.2)
    res = await http_mod.check_http_client_health(test_url="https://e")
    assert res.status == http_mod.HealthStatus.DEGRADED
    assert "error" in (res.message or "").lower()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_check_http_connectivity_paths(monkeypatch: pytest.MonkeyPatch) -> None:
    # init failure
    monkeypatch.setattr(http_mod, "import_adapter", lambda *_: object())

    def _fail(*_: Any, **__: Any) -> Any:
        raise RuntimeError("no req")

    monkeypatch.setattr(http_mod.depends, "get_sync", _fail)
    bad = await http_mod.check_http_connectivity("https://x")
    assert bad.status == http_mod.HealthStatus.UNHEALTHY

    # status mismatch -> DEGRADED
    monkeypatch.setattr(http_mod.depends, "get_sync", lambda *_: _FakeRequests(500))
    _set_perf_counter(monkeypatch, 1.0, 1.01)
    mismatch = await http_mod.check_http_connectivity("https://x", expected_status=200)
    assert mismatch.status == http_mod.HealthStatus.DEGRADED

    # high latency -> DEGRADED
    monkeypatch.setattr(http_mod.depends, "get_sync", lambda *_: _FakeRequests(200))
    _set_perf_counter(monkeypatch, 1.0, 1.5)
    slow = await http_mod.check_http_connectivity(
        "https://x", expected_status=200, timeout_ms=50
    )
    assert slow.status == http_mod.HealthStatus.DEGRADED

    # success -> HEALTHY
    _set_perf_counter(monkeypatch, 1.0, 1.01)
    ok = await http_mod.check_http_connectivity("https://x", expected_status=200)
    assert ok.status == http_mod.HealthStatus.HEALTHY

    # timeout -> UNHEALTHY
    class _TO(Exception):
        pass

    monkeypatch.setattr(http_mod, "HTTPTimeoutError", _TO)
    monkeypatch.setattr(http_mod.depends, "get_sync", lambda *_: _FakeRequests(_TO))
    _set_perf_counter(monkeypatch, 1.0, 1.2)
    tout = await http_mod.check_http_connectivity("https://x")
    assert tout.status == http_mod.HealthStatus.UNHEALTHY

    # HTTP error -> UNHEALTHY
    monkeypatch.setattr(
        http_mod.depends,
        "get_sync",
        lambda *_: _FakeRequests(http_mod.HTTPRequestError("fail")),
    )
    _set_perf_counter(monkeypatch, 1.0, 1.05)
    herr = await http_mod.check_http_connectivity("https://x")
    assert herr.status == http_mod.HealthStatus.UNHEALTHY

    # generic error -> UNHEALTHY
    monkeypatch.setattr(
        http_mod.depends, "get_sync", lambda *_: _FakeRequests(RuntimeError("bad"))
    )
    _set_perf_counter(monkeypatch, 1.0, 1.05)
    gerr = await http_mod.check_http_connectivity("https://x")
    assert gerr.status == http_mod.HealthStatus.UNHEALTHY
