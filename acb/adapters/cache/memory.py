import typing as t

from aiocache.backends.memory import SimpleMemoryCache
from aiocache.serializers import PickleSerializer
from acb.depends import depends

from ._base import CacheBase, CacheBaseSettings


class CacheSettings(CacheBaseSettings): ...


class Cache(CacheBase):
    async def init(self, *args: t.Any, **kwargs: t.Any) -> None:
        self._cache = SimpleMemoryCache(
            serializer=PickleSerializer(),
            namespace=f"{self.config.app.name}:",
            **kwargs,
        )
        self._cache.timeout = 0.0


depends.set(Cache)
