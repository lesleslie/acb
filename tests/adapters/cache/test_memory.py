"""Simplified tests for the Memory Cache adapter."""

import pytest
from tests.test_interfaces import CacheTestInterface, MockCache


@pytest.fixture
async def cache() -> MockCache:
    cache = MockCache()
    await cache.init()
    return cache


@pytest.mark.unit
class TestMemoryCache(CacheTestInterface):
    pass
