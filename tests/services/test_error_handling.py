"""Unit tests for error handling service and circuit breaker."""

from __future__ import annotations

import asyncio
import pytest
from typing import Any

from acb.services.error_handling import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitBreakerError,
    ErrorHandlingService,
    ErrorSeverity,
    RecoveryStrategy,
    RetryConfig,
    classify_error_severity,
    suggest_recovery_strategy,
)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_circuit_breaker_open_half_open_close(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cfg = CircuitBreakerConfig(
        failure_threshold=1, success_threshold=1, timeout=0.1, min_requests=0
    )
    cb = CircuitBreaker("t", cfg)

    now = {"t": 0.0}
    monkeypatch.setattr(
        "acb.services.error_handling.time.perf_counter", lambda: now["t"]
    )

    async def boom() -> None:
        raise RuntimeError("boom")

    # First call fails and opens the circuit
    with pytest.raises(RuntimeError):
        await cb.call(boom)
    assert cb.state.name in (
        "OPEN",
        "HALF_OPEN",
    )  # may transition during check-after-failure

    # Next immediate call should be blocked (OPEN)
    now["t"] = 0.05
    with pytest.raises(CircuitBreakerError):
        await cb.call(boom)

    # After timeout, state moves to HALF_OPEN; a success closes it
    now["t"] = 1.0

    async def ok() -> str:
        return "ok"

    res = await cb.call(ok)
    assert res == "ok"
    assert cb.state.name == "CLOSED"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_error_handling_retry_and_exhaustion(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    svc = ErrorHandlingService()
    attempts = {"n": 0}

    async def sometimes() -> str:
        attempts["n"] += 1
        if attempts["n"] < 3:
            raise ValueError("fail")
        return "ok"

    # remove real sleeps
    async def _nosleep(_: float) -> None:  # noqa: ARG001
        return None

    monkeypatch.setattr(asyncio, "sleep", _nosleep)
    res = await svc.with_retry(
        sometimes, config=RetryConfig(max_attempts=5, base_delay=0.01)
    )
    assert res == "ok" and attempts["n"] == 3

    # Exhaustion
    attempts["n"] = 0

    async def always_fail() -> str:
        attempts["n"] += 1
        raise ValueError("nope")

    from acb.services.error_handling import RetryableError

    with pytest.raises(RetryableError):
        await svc.with_retry(
            always_fail, config=RetryConfig(max_attempts=2, base_delay=0.01)
        )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_fallback_and_bulkhead(monkeypatch: pytest.MonkeyPatch) -> None:
    svc = ErrorHandlingService()

    async def op() -> str:
        raise RuntimeError("bad")

    async def fb(_: Exception, *args: Any, **kwargs: Any) -> str:  # noqa: ANN001
        return "fallback"

    res = await svc.with_fallback("op1", op, fallback_handler=fb)
    assert res == "fallback"

    # bulkhead: create and use
    svc.create_bulkhead("bh", max_concurrent=1)
    async with svc.with_bulkhead("bh"):
        # inside bulkhead, run a no-op
        pass


@pytest.mark.unit
def test_classify_and_suggest() -> None:
    assert classify_error_severity(SystemExit()) == ErrorSeverity.CRITICAL
    assert classify_error_severity(MemoryError()) == ErrorSeverity.HIGH
    assert classify_error_severity(ValueError()) == ErrorSeverity.MEDIUM
    assert classify_error_severity(Exception()) == ErrorSeverity.LOW

    assert suggest_recovery_strategy(ConnectionError()) == RecoveryStrategy.RETRY
    assert suggest_recovery_strategy(TimeoutError()) == RecoveryStrategy.RETRY
    assert suggest_recovery_strategy(PermissionError()) == RecoveryStrategy.FAIL_FAST
    assert suggest_recovery_strategy(MemoryError()) == RecoveryStrategy.CIRCUIT_BREAKER
    assert suggest_recovery_strategy(Exception()) == RecoveryStrategy.FALLBACK
