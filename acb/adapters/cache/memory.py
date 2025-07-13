import typing as t
from uuid import UUID

from aiocache.backends.memory import SimpleMemoryCache
from aiocache.serializers import PickleSerializer
from acb.adapters import AdapterStatus
from acb.depends import depends

from ._base import CacheBase, CacheBaseSettings

MODULE_ID = UUID("0197ff44-8c12-7f30-af61-2d41c6c89a72")
MODULE_STATUS = AdapterStatus.STABLE


class CacheSettings(CacheBaseSettings): ...


class Cache(CacheBase):
    def __init__(self, **kwargs: t.Any) -> None:
        super().__init__()
        self._init_kwargs = kwargs

    async def _create_client(self) -> SimpleMemoryCache:
        cache = SimpleMemoryCache(
            serializer=PickleSerializer(),
            namespace=f"{self.config.app.name}:",
            **self._init_kwargs,
        )
        cache.timeout = 0.0
        return cache

    async def get_client(self) -> SimpleMemoryCache:
        return await self._ensure_client()

    @property
    def _cache(self) -> SimpleMemoryCache:
        client = getattr(self, "_client", None)
        if client is None:
            cache = SimpleMemoryCache(
                serializer=PickleSerializer(),
                namespace=f"{self.config.app.name}:",
                **self._init_kwargs,
            )
            cache.timeout = 0.0
            self._client = cache
        return self._client

    async def init(self, *args: t.Any, **kwargs: t.Any) -> None:
        self._init_kwargs.update(kwargs)

    async def _set(
        self,
        key: str,
        value: t.Any,
        ttl: int | None = None,
        _cas_token: t.Any = None,
        _conn: t.Any = None,
    ) -> None:
        cache = await self.get_client()
        await cache.set(key, value, ttl=ttl)

    async def _get(
        self,
        key: str,
        encoding: str = "utf-8",
        _conn: t.Any = None,
    ) -> t.Any:
        cache = await self.get_client()
        return await cache.get(key)

    async def _delete(self, key: str, _conn: t.Any = None) -> bool:
        cache = await self.get_client()
        return await cache.delete(key)

    async def _exists(self, key: str, _conn: t.Any = None) -> bool:
        cache = await self.get_client()
        return await cache.exists(key)

    async def _clear(self, namespace: str | None = None, _conn: t.Any = None) -> bool:
        cache = await self.get_client()
        return await cache.clear(namespace=namespace)

    async def _multi_set(
        self,
        pairs: list[tuple[str, t.Any]],
        ttl: int | None = None,
        _conn: t.Any = None,
    ) -> None:
        cache = await self.get_client()
        await cache.multi_set(pairs, ttl=ttl)

    async def _multi_get(
        self,
        keys: list[str],
        encoding: str = "utf-8",
        _conn: t.Any = None,
    ) -> list[t.Any]:
        cache = await self.get_client()
        return await cache.multi_get(keys)

    async def _add(
        self,
        key: str,
        value: t.Any,
        ttl: int | None = None,
        _conn: t.Any = None,
    ) -> bool:
        cache = await self.get_client()
        return await cache.add(key, value, ttl=ttl)

    async def _increment(self, key: str, delta: int = 1, _conn: t.Any = None) -> int:
        cache = await self.get_client()
        return await cache.increment(key, delta=delta)

    async def _expire(self, key: str, ttl: int, _conn: t.Any = None) -> bool:
        cache = await self.get_client()
        return await cache.expire(key, ttl=ttl)


depends.set(Cache)
