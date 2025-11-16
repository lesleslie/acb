"""Unit tests for CacheOptimizer helpers and stats."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from acb.services.performance.cache import (
    CacheOptimizer,
    CacheOptimizerSettings,
    CacheStrategy,
)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_optimized_hit_miss_and_stats(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Setup optimizer with fake cache adapter
    settings = CacheOptimizerSettings()
    opt = CacheOptimizer(settings=settings)
    opt.logger = MagicMock()

    fake_cache = AsyncMock()
    fake_cache.get = AsyncMock(side_effect=["cached", None])
    fake_cache.set = AsyncMock()
    fake_cache.delete = AsyncMock()
    opt._cache_adapter = fake_cache

    # First call: hit
    async def fetch() -> str:
        return "fetched"

    v1 = await opt.get_optimized("k", fetch)
    assert v1 == "cached"
    stats1 = opt.get_cache_stats()
    assert stats1.hits == 1 and stats1.misses == 0 and stats1.hit_rate == 100.0

    # Second call: miss → fetch + set
    v2 = await opt.get_optimized("k", fetch, ttl=10)
    assert v2 == "fetched"
    stats2 = opt.get_cache_stats()
    assert stats2.hits == 1 and stats2.misses == 1 and stats2.hit_rate == 50.0
    fake_cache.set.assert_awaited()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_clear_expired_and_optimize_memory(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    opt = CacheOptimizer(settings=CacheOptimizerSettings(strategy=CacheStrategy.TTL))
    opt.logger = MagicMock()
    fake_cache = AsyncMock()
    fake_cache.clear_expired = AsyncMock(return_value=3)
    opt._cache_adapter = fake_cache

    cleared = await opt.clear_expired()
    assert cleared == 3

    res = await opt.optimize_memory_usage()
    assert res["strategy_used"] == "ttl" and res["keys_evicted"] >= 3


@pytest.mark.unit
@pytest.mark.asyncio
async def test_calculate_ttl_and_evictions(monkeypatch: pytest.MonkeyPatch) -> None:
    import time

    st = CacheOptimizerSettings(
        min_ttl_seconds=5,
        max_ttl_seconds=100,
        default_ttl_seconds=60,
        usage_threshold_for_promotion=1,
    )
    opt = CacheOptimizer(settings=st)
    # clamp requested ttl
    assert opt._calculate_optimal_ttl("k", requested_ttl=1) == 5
    assert opt._calculate_optimal_ttl("k", requested_ttl=1000) == 100
    assert opt._calculate_optimal_ttl("k", requested_ttl=None) == 60
    # usage pattern promotion
    opt._usage_patterns["hot"] = {
        "access_count": 10,
        "hit_count": 5,
        "miss_count": 5,
        "last_accessed": time.time(),
        "tags": [],
    }
    assert opt._calculate_optimal_ttl("hot", None) == 100

    # Eviction helpers
    from unittest.mock import AsyncMock

    opt._cache_adapter = AsyncMock()
    now = time.time()
    # create patterns for adaptive and lru eviction
    for i in range(5):
        opt._usage_patterns[f"k{i}"] = {
            "access_count": i + 1,
            "hit_count": i,
            "miss_count": 1,
            "last_accessed": now - i * 10,
            "tags": [],
        }
    ev1 = await opt._adaptive_eviction()
    ev2 = await opt._lru_eviction()
    assert ev1 >= 1 and ev2 >= 1
