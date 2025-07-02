"""Tests for the Redis Cache adapter using optimized test infrastructure."""

import typing as t
from unittest.mock import AsyncMock

import pytest

from .test_cache_base import assert_cache_operations


class RedisCache:
    def __init__(self, redis_url: str | None = None) -> None:
        self.redis_url: str | None = redis_url
        self._namespace: str = "acb:"
        self._data: dict[str, t.Any] = {}
        self._initialized: bool = False

        self.client: AsyncMock = AsyncMock()
        self.client.get.side_effect = self._mock_get
        self.client.set.side_effect = self._mock_set
        self.client.delete.side_effect = self._mock_delete
        self.client.exists.side_effect = self._mock_exists
        self.client.keys.side_effect = self._mock_keys
        self.client.unlink.return_value = True

    async def _mock_get(self, key: str) -> t.Any:
        return self._data.get(key)

    async def _mock_set(self, key: str, value: t.Any, ex: int | None = None) -> bool:
        self._data[key] = value
        return True

    async def _mock_delete(self, key: str) -> int:
        if key in self._data:
            del self._data[key]
            return 1
        return 0

    async def _mock_exists(self, keys: list[str]) -> bool:
        return any(key in self._data for key in keys)

    async def _mock_keys(self, pattern: str) -> list[str]:
        if pattern.endswith("*"):
            prefix = pattern[:-1]
            return [k for k in self._data.keys() if k.startswith(prefix)]
        return []

    async def init(self) -> "RedisCache":
        self._initialized = True
        return self

    async def get(self, key: str, default: t.Any = None) -> t.Any:
        full_key: str = f"{self._namespace}{key}"
        value: t.Any = await self.client.get(full_key)
        return value if value is not None else default

    async def set(self, key: str, value: t.Any, ttl: int | None = None) -> bool:
        full_key: str = f"{self._namespace}{key}"
        return await self.client.set(full_key, value, ex=ttl)

    async def delete(self, key: str) -> int:
        full_key: str = f"{self._namespace}{key}"
        return await self.client.delete(full_key)

    async def exists(self, key: str) -> bool:
        full_key: str = f"{self._namespace}{key}"
        number: bool = await self.client.exists([full_key])
        return number

    async def clear(self, namespace: str | None = None) -> bool:
        if not namespace:
            pattern: str = f"{self._namespace}*"
        else:
            pattern = f"{self._namespace}{namespace}:*"
        keys: list[str] = await self.client.keys(pattern)
        if keys:
            for key in keys:
                if key in self._data:
                    del self._data[key]
            await self.client.unlink((keys,))
        return True

    async def multi_get(self, keys: list[str]) -> list[t.Any]:
        result: list[t.Any] = []
        for key in keys:
            full_key: str = f"{self._namespace}{key}"
            value: t.Any = await self.client.get(full_key)
            result.append(value)
        return result

    async def multi_set(
        self, mapping: dict[str, t.Any], ttl: int | None = None
    ) -> bool:
        for key, value in mapping.items():
            full_key: str = f"{self._namespace}{key}"
            await self.client.set(full_key, value, ex=ttl)
        return True


@pytest.fixture
async def redis_cache() -> RedisCache:
    cache: RedisCache = RedisCache(redis_url="redis://localhost:6379")
    await cache.init()
    return cache


@pytest.mark.asyncio
async def test_redis_cache_operations(redis_cache: RedisCache) -> None:
    await assert_cache_operations(redis_cache, "test_key", "test_value")


@pytest.mark.asyncio
async def test_multi_get(redis_cache: RedisCache) -> None:
    redis_cache._data["acb:key1"] = "value1"
    redis_cache._data["acb:key2"] = "value2"

    result: list[t.Any] = await redis_cache.multi_get(["key1", "key2", "key3"])

    assert result[0] == "value1"
    assert result[1] == "value2"
    assert result[2] is None


@pytest.mark.asyncio
async def test_multi_set(redis_cache: RedisCache) -> None:
    result: bool = await redis_cache.multi_set(
        {"key1": "value1", "key2": "value2"}, ttl=60
    )

    assert result
    assert redis_cache._data["acb:key1"] == "value1"
    assert redis_cache._data["acb:key2"] == "value2"
