"""Tests for the Memory Cache adapter."""

import pytest
from tests.test_interfaces import CacheTestInterface, MockCache


@pytest.fixture
async def cache():
    mock_cache = MockCache()
    await mock_cache.init()
    return mock_cache


@pytest.mark.unit
class TestMemoryCache(CacheTestInterface):
    pass
