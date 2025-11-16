"""Additional branch tests for error_handling service."""

from __future__ import annotations

import asyncio
import pytest

from acb.services.error_handling import (
    CircuitBreakerConfig,
    ErrorHandlingService,
    RetryConfig,
    bulkhead,
    circuit_breaker,
    fallback,
    retry,
)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_error_service_handlers_metrics_and_status(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    svc = ErrorHandlingService()

    # Register sync and async error handlers
    called: dict[str, int] = {"sync": 0, "async": 0}

    def sync_handler(e: Exception) -> str:
        called["sync"] += 1
        return f"sync:{e}"

    async def async_handler(e: Exception) -> str:
        called["async"] += 1
        return f"async:{e}"

    svc.register_error_handler(ValueError, sync_handler)
    svc.register_error_handler(KeyError, async_handler)

    # handle_error path for sync
    res1 = await svc.handle_error(ValueError("x"))
    assert res1.startswith("sync:") and called["sync"] == 1

    # and async handler
    res2 = await svc.handle_error(KeyError("k"))
    assert res2.startswith("async:") and called["async"] == 1

    # Metrics snapshot includes handler counts
    gm = svc.get_global_metrics()
    assert gm["error_handlers"] >= 2 and gm["total_errors"] >= 2

    # Circuit breaker status/creation/reset
    await svc.with_circuit_breaker("cb1", lambda: asyncio.sleep(0))
    status = svc.get_circuit_breaker_status()
    assert "cb1" in status and status["cb1"]["state"] in ("closed", "half_open", "open")
    assert await svc.reset_circuit_breaker("cb1") is True
    assert await svc.reset_circuit_breaker("nope") is False


@pytest.mark.unit
@pytest.mark.asyncio
async def test_decorators_circuit_retry_fallback_and_bulkhead(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Speed up retries
    async def no_sleep(_: float) -> None:  # noqa: ARG001
        return None

    monkeypatch.setattr(asyncio, "sleep", no_sleep)

    # Circuit breaker decorator should allow successful call
    @circuit_breaker(
        "cb2",
        config=CircuitBreakerConfig(
            failure_threshold=2, success_threshold=1, timeout=0.01
        ),
    )
    async def ok() -> str:
        return "ok"

    assert await ok() == "ok"

    # Retry decorator retries and eventually succeeds
    attempts = {"n": 0}

    @retry(RetryConfig(max_attempts=3, base_delay=0.01))
    async def flaky() -> str:
        attempts["n"] += 1
        if attempts["n"] < 3:
            raise RuntimeError("try again")
        return "done"

    assert await flaky() == "done"

    # Fallback decorator returns value from fallback
    def fb(_: Exception) -> str:
        return "fb"

    @fallback("opx", fallback_handler=fb)
    async def boom() -> str:
        raise RuntimeError("boom")

    assert await boom() == "fb"

    # Bulkhead decorator executes under semaphore
    @bulkhead("bhx", max_concurrent=1)
    async def task(v: int) -> int:
        await asyncio.sleep(0)
        return v * 2

    assert await task(2) == 4
