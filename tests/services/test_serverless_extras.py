"""Unit tests for serverless extras.

Tests for AdaptiveConnectionPool, DeferredInitializer, and MemoryEfficientProcessor.
"""

from __future__ import annotations

import asyncio
import pytest

from acb.services.performance.serverless import (
    AdaptiveConnectionPool,
    DeferredInitializer,
    MemoryEfficientProcessor,
)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_adaptive_connection_pool_acquire_release_and_scale(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pool = AdaptiveConnectionPool(min_connections=1, max_connections=3)

    class Conn:
        def __init__(self) -> None:
            self.is_closed = False
            self.closed = 0

        async def close(self) -> None:
            self.is_closed = True
            self.closed += 1

    # First acquire should create a connection
    created: list[Conn] = []

    async def factory() -> Conn:
        c = Conn()
        created.append(c)
        return c

    c1 = await pool.acquire(factory)
    stats = pool.get_pool_stats()
    assert stats["active_connections"] == 1 and stats["pooled_connections"] == 0

    # Release healthy connection should return to pool
    await pool.release(c1)
    stats = pool.get_pool_stats()
    assert stats["active_connections"] == 0 and stats["pooled_connections"] == 1

    # Acquire a popped connection, then create a new one and mark it unhealthy
    c_popped = await pool.acquire(factory)  # pops the pooled one
    c2 = await pool.acquire(factory)  # creates a new one since pool is empty
    c2.is_closed = True  # simulate unhealthy
    await pool.release(c2)
    stats = pool.get_pool_stats()
    # Still no pooled connections until we release the healthy popped connection
    assert stats["pooled_connections"] == 0
    await pool.release(c_popped)
    stats = pool.get_pool_stats()
    assert stats["pooled_connections"] == 1

    # Scale down when idle and exceeding min_connections
    # Place an extra idle connection in pool
    c3 = await pool.acquire(factory)
    await pool.release(c3)  # now pool has 2

    # Force last scale time to be sufficiently in the past
    monkeypatch.setattr(pool, "_last_scale_time", 0.0)
    await pool.scale_down_if_needed()
    stats = pool.get_pool_stats()
    # Should keep at least min_connections in pool
    assert stats["pooled_connections"] >= 1


@pytest.mark.unit
@pytest.mark.asyncio
async def test_deferred_initializer_priority_and_concurrency() -> None:
    di = DeferredInitializer()

    order: list[str] = []

    async def mk(name: str) -> str:
        await asyncio.sleep(0)
        order.append(name)
        return f"res:{name}"

    di.register("low", lambda: mk("low"), priority=100)
    di.register("high", lambda: mk("high"), priority=10)

    # Initialize by priority
    await di.initialize_by_priority(max_concurrent=1)
    assert di.is_initialized("high") and di.is_initialized("low")
    # Priority order should place 'high' earlier in initialization_order
    stats = di.get_initialization_stats()
    assert stats["initialization_order"][0] == "high"

    # Concurrency: two gets for same name should only create once
    di2 = DeferredInitializer()
    calls = {"n": 0}

    async def fac() -> str:
        calls["n"] += 1
        await asyncio.sleep(0.01)
        return "only_once"

    di2.register("x", fac, priority=1)
    res1, res2 = await asyncio.gather(di2.get("x"), di2.get("x"))
    assert res1 == res2 == "only_once" and calls["n"] == 1


@pytest.mark.unit
@pytest.mark.asyncio
async def test_memory_efficient_processor_batch_and_stream(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Batch path (items below threshold)
    proc = MemoryEfficientProcessor(
        max_memory_mb=16.0, batch_size=3, stream_threshold=100
    )

    async def processor(batch: list[int]) -> list[int]:
        # Echo results as doubled
        return [x * 2 for x in batch]

    items = list(range(7))
    out: list[int] = []
    async for r in proc.process_items(items, processor):
        out.append(r)
    assert out == [x * 2 for x in items]
    stats = proc.get_processing_stats()
    assert stats["batches_processed"] >= 3 and stats["items_processed"] == 7

    # Streaming path (items above threshold)
    proc2 = MemoryEfficientProcessor(
        max_memory_mb=16.0, batch_size=50, stream_threshold=5
    )
    items2 = list(range(10))
    out2: list[int] = []
    async for r in proc2.process_items(items2, processor):
        out2.append(r)
    assert out2 == [x * 2 for x in items2]
    stats2 = proc2.get_processing_stats()
    assert stats2["streams_processed"] == 1
