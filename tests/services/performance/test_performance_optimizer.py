"""Unit tests for PerformanceOptimizer helpers."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from acb.services.performance.optimizer import (
    PerformanceOptimizer,
    PerformanceOptimizerSettings,
)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_optimize_cache_operation_hit_miss_and_decorator(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    po = PerformanceOptimizer(settings=PerformanceOptimizerSettings())
    po.logger = MagicMock()
    fake_cache = AsyncMock()
    # First call: miss -> set; Second call: hit
    fake_cache.get = AsyncMock(side_effect=[None, "VAL"])
    fake_cache.set = AsyncMock()
    po._cache_adapter = fake_cache

    async def operation() -> str:
        return "VAL"

    # Miss path
    res_miss = await po.optimize_cache_operation("k", operation, ttl=5)
    assert res_miss.success and res_miss.operation.endswith("miss")
    # Hit path
    res_hit = await po.optimize_cache_operation("k", operation)
    assert res_hit.success and res_hit.operation.endswith("hit")

    # Decorator uses the same flow
    called = {"n": 0}

    @po.optimize_function(ttl=5)
    async def f(a: int) -> str:
        called["n"] += 1
        return f"R{a}"

    # First call -> miss (calls function), second -> hit (not call function again)
    fake_cache.get = AsyncMock(side_effect=[None, "R1"])
    await f(1)
    v = await f(1)
    assert v == "R1" and called["n"] == 1


@pytest.mark.unit
@pytest.mark.asyncio
async def test_optimize_query_batch_error_and_success() -> None:
    po = PerformanceOptimizer(settings=PerformanceOptimizerSettings())
    po.logger = MagicMock()

    # No SQL adapter -> error result
    res_err = await po.optimize_query_batch(["select 1"])
    assert not res_err.success and res_err.error

    # Provide a fake SQL adapter
    fake_sql = AsyncMock()
    fake_sql.execute = AsyncMock(return_value={"ok": True})
    po._sql_adapter = fake_sql
    res_ok = await po.optimize_query_batch(
        ["select 1", "select 2"], parameters=[{"a": 1}, {"b": 2}]
    )
    assert res_ok.success and res_ok.metadata["queries_count"] == 2
