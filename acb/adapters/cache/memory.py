import typing as t

from aiocache.backends.memory import SimpleMemoryCache
from aiocache.serializers import PickleSerializer
from acb.depends import depends

from ._base import CacheBase, CacheBaseSettings


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


depends.set(Cache)
