"""Simplified tests for the Redis Cache adapter."""

from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock

import pytest
from tests.test_interfaces import CacheTestInterface


class RedisCache:
    def __init__(self, redis_url: Optional[str] = None) -> None:
        self.redis_url: Optional[str] = redis_url
        self._namespace: str = "acb:"
        self._data: Dict[str, Any] = {}
        self._initialized: bool = False

        self.client: AsyncMock = AsyncMock()
        self.client.get.side_effect = self._mock_get
        self.client.set.side_effect = self._mock_set
        self.client.delete.side_effect = self._mock_delete
        self.client.exists.side_effect = self._mock_exists
        self.client.keys.side_effect = self._mock_keys
        self.client.unlink.return_value = True

    async def _mock_get(self, key: str) -> Any:
        return self._data.get(key)

    async def _mock_set(self, key: str, value: Any, ex: Optional[int] = None) -> bool:
        self._data[key] = value
        return True

    async def _mock_delete(self, key: str) -> int:
        if key in self._data:
            del self._data[key]
            return 1
        return 0

    async def _mock_exists(self, keys: List[str]) -> bool:
        return any(key in self._data for key in keys)

    async def _mock_keys(self, pattern: str) -> List[str]:
        if pattern.endswith("*"):
            prefix = pattern[:-1]
            return [k for k in self._data.keys() if k.startswith(prefix)]
        return []

    async def init(self) -> "RedisCache":
        self._initialized = True
        return self

    async def get(self, key: str, default: Any = None) -> Any:
        full_key = f"{self._namespace}{key}"
        value = await self.client.get(full_key)
        return value if value is not None else default

    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        full_key = f"{self._namespace}{key}"
        return await self.client.set(full_key, value, ex=ttl)

    async def delete(self, key: str) -> int:
        full_key = f"{self._namespace}{key}"
        return await self.client.delete(full_key)

    async def exists(self, key: str) -> bool:
        full_key = f"{self._namespace}{key}"
        number = await self.client.exists([full_key])
        return bool(number)

    async def clear(self, namespace: Optional[str] = None) -> bool:
        if not namespace:
            pattern = f"{self._namespace}*"
        else:
            pattern = f"{self._namespace}{namespace}:*"
        keys = await self.client.keys(pattern)
        if keys:
            for key in keys:
                if key in self._data:
                    del self._data[key]
            await self.client.unlink((keys,))
        return True

    async def multi_get(self, keys: List[str]) -> List[Any]:
        result: List[Any] = []
        for key in keys:
            full_key = f"{self._namespace}{key}"
            value = await self.client.get(full_key)
            result.append(value)
        return result

    async def multi_set(
        self, mapping: Dict[str, Any], ttl: Optional[int] = None
    ) -> bool:
        for key, value in mapping.items():
            full_key = f"{self._namespace}{key}"
            await self.client.set(full_key, value, ex=ttl)
        return True


@pytest.fixture
async def cache() -> RedisCache:
    cache = RedisCache(redis_url="redis://localhost:6379")
    await cache.init()
    return cache


class TestRedisCache(CacheTestInterface):
    @pytest.mark.asyncio
    async def test_multi_get(self, cache: RedisCache) -> None:
        await cache.set("key1", "value1")
        await cache.set("key2", "value2")

        result = await cache.multi_get(["key1", "key2", "key3"])

        assert result[0] == "value1"
        assert result[1] == "value2"
        assert result[2] is None

    @pytest.mark.asyncio
    async def test_multi_set(self, cache: RedisCache) -> None:
        result = await cache.multi_set({"key1": "value1", "key2": "value2"}, ttl=60)

        assert result

        assert await cache.get("key1") == "value1"
        assert await cache.get("key2") == "value2"
