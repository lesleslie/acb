"""Tests for the Cache Base adapter."""

import typing as t
from typing import cast
from unittest.mock import AsyncMock, MagicMock

import pytest
from acb.adapters.cache._base import CacheBase, CacheBaseSettings
from acb.config import Config
from acb.logger import Logger


class MockCacheBaseSettings(CacheBaseSettings):
    pass


class MockCache(CacheBase):
    some_str_attr: str = ""

    def __init__(self) -> None:
        super().__init__()
        self.config = cast(Config, MagicMock())
        self.logger = cast(Logger, MagicMock())
        self.some_str_attr = ""


class TestCacheBaseSettings:
    def test_init(self) -> None:
        val: t.Optional[int] = 300
        settings: MockCacheBaseSettings = MockCacheBaseSettings(ttl=val)  # type: ignore
        assert settings.ttl == val


class TestCacheBase:
    @pytest.fixture
    def cache(self) -> MockCache:
        cache: MockCache = MockCache()
        return cache

    @pytest.mark.asyncio
    async def test_get(self, cache: MockCache) -> None:
        key: str = "test_key"
        value: str = "test_value"
        cache._get = AsyncMock(return_value=value)
        result = await cache.get(key)
        assert result is not None
        result_str: str = result
        assert result_str == value
        cache._get.assert_called_once_with(key)

    @pytest.mark.asyncio
    async def test_set(self, cache: MockCache) -> None:
        key: str = "test_key"
        value: str = "test_value"
        ttl: int = 300
        cache._set = AsyncMock()
        await cache.set(key, value, ttl)
        cache._set.assert_called_once_with(key, value, ttl)

    @pytest.mark.asyncio
    async def test_delete(self, cache: MockCache) -> None:
        key: str = "test_key"
        cache._delete = AsyncMock()
        await cache.delete(key)
        cache._delete.assert_called_once_with(key)

    @pytest.mark.asyncio
    async def test_exists(self, cache: MockCache) -> None:
        key: str = "test_key"
        cache._exists = AsyncMock(return_value=True)
        result: bool = await cache.exists(key)
        assert result
        cache._exists.assert_called_once_with(key)

    @pytest.mark.asyncio
    async def test_clear(self, cache: MockCache) -> None:
        cache._clear = AsyncMock()
        await cache.clear()
        cache._clear.assert_called_once()

    @pytest.mark.asyncio
    async def test_keys(self, cache: MockCache) -> None:
        keys: t.List[str] = ["key1", "key2"]
        cache._keys = AsyncMock(return_value=keys)  # type: ignore
        result: t.List[str] = await cache.keys()  # type: ignore
        assert result == keys
        cache._keys.assert_called_once()  # type: ignore

    @pytest.mark.asyncio
    async def test_str_assignment(self, cache: MockCache) -> None:
        val: str = "test_str"
        cache.some_str_attr = val
