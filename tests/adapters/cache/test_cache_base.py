"""Tests for the Cache Base adapter."""

import typing as t
from typing import cast
from unittest.mock import AsyncMock, MagicMock

import pytest
from acb.adapters.cache._base import CacheBase, CacheBaseSettings

if t.TYPE_CHECKING:
    from acb.config import Config
    from acb.logger import Logger


async def assert_cache_operations(cache: t.Any, key: str, value: t.Any) -> None:
    await cache.set(key, value)
    if hasattr(cache, "_get") and isinstance(cache._get, AsyncMock):
        cache._get.return_value = value

    result = await cache.get(key)
    assert result == value

    await cache.delete(key)
    if hasattr(cache, "_get") and isinstance(cache._get, AsyncMock):
        cache._get.return_value = None

    result = await cache.get(key)
    assert result is None


class MockCacheBaseSettings(CacheBaseSettings):
    pass


class MockCache(CacheBase):
    some_str_attr: str = ""

    def __init__(self) -> None:
        super().__init__()
        self.config = cast("Config", MagicMock())
        self.logger = cast("Logger", MagicMock())
        self.some_str_attr = ""
        self._get = AsyncMock()
        self._set = AsyncMock()
        self._delete = AsyncMock()
        self._exists = AsyncMock()
        self._clear = AsyncMock()
        self._keys = AsyncMock()
        self._multi_get = AsyncMock()
        self._multi_set = AsyncMock()
        self._multi_delete = AsyncMock()

    async def _create_client(self) -> t.Any:
        return MagicMock()

    async def get(
        self,
        key: str,
        default: t.Any = None,
        loads_fn: t.Callable[..., t.Any] | None = None,
        namespace: str | None = None,
        _conn: t.Any | None = None,
    ) -> t.Any:
        return await self._get(key, encoding=None)

    async def set(
        self,
        key: str,
        value: t.Any,
        ttl: t.Any = None,
        dumps_fn: t.Callable[..., t.Any] | None = None,
        namespace: str | None = None,
        _cas_token: t.Any | None = None,
        _conn: t.Any | None = None,
    ) -> None:
        await self._set(key, value, ttl)

    async def delete(
        self,
        key: str,
        namespace: str | None = None,
        _conn: t.Any | None = None,
    ) -> None:
        await self._delete(key)

    async def exists(
        self,
        key: str,
        namespace: str | None = None,
        _conn: t.Any | None = None,
    ) -> bool:
        return await self._exists(key)

    async def clear(
        self,
        namespace: str | None = None,
        _conn: t.Any | None = None,
    ) -> None:
        await self._clear(namespace)

    async def keys(self) -> list[str]:
        return await self._keys()

    async def multi_get(
        self,
        keys: list[str],
        loads_fn: t.Callable[..., t.Any] | None = None,
        namespace: str | None = None,
        _conn: t.Any | None = None,
        encoding: str | None = None,
    ) -> list[t.Any]:
        return await self._multi_get(keys, encoding=encoding)

    async def multi_set(
        self,
        pairs: dict[str, t.Any],
        ttl: t.Any = None,
        dumps_fn: t.Callable[..., t.Any] | None = None,
        namespace: str | None = None,
        _conn: t.Any | None = None,
    ) -> t.Literal[True]:
        await self._multi_set(pairs, ttl)
        return True

    async def multi_delete(
        self,
        keys: list[str],
        namespace: str | None = None,
        _conn: t.Any | None = None,
    ) -> None:
        await self._multi_delete(keys)


class TestCacheBaseSettings:
    def test_init(self) -> None:
        val: int = 300
        settings: MockCacheBaseSettings = MockCacheBaseSettings(default_ttl=val)
        assert settings.default_ttl == val


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
        cache._get.assert_called_once_with(key, encoding=None)

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
        keys: list[str] = ["key1", "key2"]
        cache._keys = AsyncMock(return_value=keys)  # type: ignore
        result: list[str] = await cache.keys()  # type: ignore
        assert result == keys
        cache._keys.assert_called_once()  # type: ignore

    @pytest.mark.asyncio
    async def test_str_assignment(self, cache: MockCache) -> None:
        val: str = "test_str"
        cache.some_str_attr = val

    @pytest.mark.asyncio
    async def test_cache_operations(self, cache: MockCache) -> None:
        await assert_cache_operations(cache, "test_key", "test_value")
