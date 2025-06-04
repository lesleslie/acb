"""Mock implementations of cache adapters for testing."""

import time
import typing as t
from unittest.mock import AsyncMock, MagicMock

from acb.adapters.cache._base import CacheBase


class MockMemoryCache(CacheBase):
    def __init__(self) -> None:
        self._data: dict[str, t.Any] = {}
        self._expires: dict[str, float] = {}
        self._namespace = ""
        self._initialized = True
        self.config = MagicMock()
        self.config.app.name = "test"

    async def get(
        self,
        key: str,
        default: t.Any = None,
        loads_fn: t.Callable[[t.Any], t.Any] | None = None,
        namespace: str | None = None,
        _conn: t.Any = None,
    ) -> t.Any:
        key = f"{self._namespace}{key}"
        self._cleanup_expired()
        return self._data.get(key)

    async def set(
        self,
        key: str,
        value: t.Any,
        ttl: t.Any = None,
        dumps_fn: t.Callable[[t.Any], t.Any] | None = None,
        namespace: str | None = None,
        _cas_token: t.Any = None,
        _conn: t.Any = None,
    ) -> bool:
        key = f"{self._namespace}{key}"
        self._data[key] = value
        if ttl is not None:
            self._expires[key] = time.time() + ttl
        return True

    async def delete(
        self, key: str, namespace: str | None = None, _conn: t.Any = None
    ) -> int:
        key = f"{self._namespace}{key}"
        if key in self._data:
            del self._data[key]
            if key in self._expires:
                del self._expires[key]
            return 1
        return 0

    async def exists(
        self, key: str, namespace: str | None = None, _conn: t.Any = None
    ) -> bool:
        key = f"{self._namespace}{key}"
        self._cleanup_expired()
        return key in self._data

    async def multi_get(
        self,
        keys: list[str],
        loads_fn: t.Callable[[t.Any], t.Any] | None = None,
        namespace: str | None = None,
        _conn: t.Any = None,
    ) -> list[t.Any]:
        return [await self.get(key) for key in keys]

    async def multi_set(
        self,
        pairs: dict[str, t.Any],
        ttl: t.Any = None,
        dumps_fn: t.Callable[[t.Any], t.Any] | None = None,
        namespace: str | None = None,
        _conn: t.Any = None,
    ) -> t.Literal[True]:
        for key, value in pairs.items():
            await self.set(key, value, ttl=ttl)
        return True

    async def clear(self, namespace: str | None = None, _conn: t.Any = None) -> bool:
        if namespace is None:
            namespace = self._namespace
        else:
            namespace = f"{self._namespace}{namespace}:"

        keys_to_delete = [key for key in self._data if key.startswith(namespace)]
        for key in keys_to_delete:
            del self._data[key]
            if key in self._expires:
                del self._expires[key]

        return True

    async def incr(self, key: str, delta: int = 1) -> int:
        key = f"{self._namespace}{key}"
        if key not in self._data:
            self._data[key] = 0

        if not isinstance(self._data[key], int):
            self._data[key] = 0

        self._data[key] += delta
        return self._data[key]

    async def expire(
        self,
        key: str,
        ttl: float,
        namespace: str | None = None,
        _conn: t.Any = None,
    ) -> bool:
        key = f"{self._namespace}{key}"
        if key in self._data:
            self._expires[key] = time.time() + ttl
            return True
        return False

    def namespace(self, namespace: str) -> "MockMemoryCache":
        namespaced_cache = MockMemoryCache()
        namespaced_cache._namespace = f"{self._namespace}{namespace}:"
        return namespaced_cache

    def cached(
        self, ttl: float | None = None
    ) -> t.Callable[[t.Callable[..., t.Any]], t.Callable[..., t.Any]]:
        def decorator(func: t.Callable[..., t.Any]) -> t.Callable[..., t.Any]:
            async def wrapper(*args: t.Any, **kwargs: t.Any) -> t.Any:
                key_parts = [func.__name__]
                key_parts.extend(str(arg) for arg in args)
                key_parts.extend(f"{k}={v}" for k, v in sorted(kwargs.items()))
                cache_key = ":".join(key_parts)

                result = await self.get(cache_key)
                if result is not None:
                    return result

                result = await func(*args, **kwargs)
                await self.set(cache_key, result, ttl=ttl)
                return result

            return wrapper

        return decorator

    def _cleanup_expired(self) -> None:
        now = time.time()
        expired_keys = [key for key, expires in self._expires.items() if expires <= now]
        for key in expired_keys:
            if key in self._data:
                del self._data[key]
            del self._expires[key]

    async def init(self) -> None:
        self._initialized = True


class MockRedisCache(CacheBase):
    def __init__(self, redis_url: str = "redis://localhost:6379") -> None:
        self._data: dict[str, t.Any] = {}
        self._expires: dict[str, float] = {}
        self._namespace = ""
        self._initialized = True
        self.config = MagicMock()
        self.config.app.name = "test"
        self.redis_url = redis_url
        self.client = AsyncMock()

    async def get(
        self,
        key: str,
        default: t.Any = None,
        loads_fn: t.Callable[[t.Any], t.Any] | None = None,
        namespace: str | None = None,
        _conn: t.Any = None,
    ) -> t.Any:
        key = f"{self._namespace}{key}"
        self._cleanup_expired()
        return self._data.get(key)

    async def set(
        self,
        key: str,
        value: t.Any,
        ttl: t.Any = None,
        dumps_fn: t.Callable[[t.Any], t.Any] | None = None,
        namespace: str | None = None,
        _cas_token: t.Any = None,
        _conn: t.Any = None,
    ) -> bool:
        key = f"{self._namespace}{key}"
        self._data[key] = value
        if ttl is not None:
            self._expires[key] = time.time() + ttl
        return True

    async def delete(
        self, key: str, namespace: str | None = None, _conn: t.Any = None
    ) -> int:
        key = f"{self._namespace}{key}"
        if key in self._data:
            del self._data[key]
            if key in self._expires:
                del self._expires[key]
            return 1
        return 0

    async def exists(
        self, key: str, namespace: str | None = None, _conn: t.Any = None
    ) -> bool:
        key = f"{self._namespace}{key}"
        self._cleanup_expired()
        return key in self._data

    async def multi_get(
        self,
        keys: list[str],
        loads_fn: t.Callable[[t.Any], t.Any] | None = None,
        namespace: str | None = None,
        _conn: t.Any = None,
    ) -> list[t.Any]:
        return [await self.get(key) for key in keys]

    async def multi_set(
        self,
        pairs: dict[str, t.Any],
        ttl: t.Any = None,
        dumps_fn: t.Callable[[t.Any], t.Any] | None = None,
        namespace: str | None = None,
        _conn: t.Any = None,
    ) -> t.Literal[True]:
        for key, value in pairs.items():
            await self.set(key, value, ttl=ttl)
        return True

    async def clear(self, namespace: str | None = None, _conn: t.Any = None) -> bool:
        if namespace is None:
            namespace = self._namespace
        else:
            namespace = f"{self._namespace}{namespace}:"

        keys_to_delete = [key for key in self._data if key.startswith(namespace)]
        for key in keys_to_delete:
            del self._data[key]
            if key in self._expires:
                del self._expires[key]

        return True

    async def incr(self, key: str, delta: int = 1) -> int:
        key = f"{self._namespace}{key}"
        if key not in self._data:
            self._data[key] = 0

        if not isinstance(self._data[key], int):
            self._data[key] = 0

        self._data[key] += delta
        return self._data[key]

    async def expire(
        self,
        key: str,
        ttl: float,
        namespace: str | None = None,
        _conn: t.Any = None,
    ) -> bool:
        key = f"{self._namespace}{key}"
        if key in self._data:
            self._expires[key] = time.time() + ttl
            return True
        return False

    def namespace(self, namespace: str) -> "MockRedisCache":
        namespaced_cache = MockRedisCache(redis_url=self.redis_url)
        namespaced_cache._namespace = f"{self._namespace}{namespace}:"
        return namespaced_cache

    def cached(
        self, ttl: float | None = None
    ) -> t.Callable[[t.Callable[..., t.Any]], t.Callable[..., t.Any]]:
        def decorator(func: t.Callable[..., t.Any]) -> t.Callable[..., t.Any]:
            async def wrapper(*args: t.Any, **kwargs: t.Any) -> t.Any:
                key_parts = [func.__name__]
                key_parts.extend(str(arg) for arg in args)
                key_parts.extend(f"{k}={v}" for k, v in sorted(kwargs.items()))
                cache_key = ":".join(key_parts)

                result = await self.get(cache_key)
                if result is not None:
                    return result

                result = await func(*args, **kwargs)
                await self.set(cache_key, result, ttl=ttl)
                return result

            return wrapper

        return decorator

    def _cleanup_expired(self) -> None:
        now = time.time()
        expired_keys = [key for key, expires in self._expires.items() if expires <= now]
        for key in expired_keys:
            if key in self._data:
                del self._data[key]
            del self._expires[key]

    async def init(self) -> None:
        self._initialized = True
