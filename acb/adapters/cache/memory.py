import typing as t
from functools import cached_property

from aiocache.backends.memory import SimpleMemoryCache
from aiocache.serializers import PickleSerializer
from acb.depends import depends

from ._base import CacheBase, CacheBaseSettings


class CacheSettings(CacheBaseSettings): ...


class Cache(CacheBase):
    def __init__(self, **kwargs: t.Any) -> None:
        super().__init__()
        self._init_kwargs = kwargs

    @cached_property
    def _cache(self) -> SimpleMemoryCache:
        cache = SimpleMemoryCache(
            serializer=PickleSerializer(),
            namespace=f"{self.config.app.name}:",
            **self._init_kwargs,
        )
        cache.timeout = 0.0
        return cache

    async def init(self, *args: t.Any, **kwargs: t.Any) -> None:
        self._init_kwargs.update(kwargs)
        pass


depends.set(Cache)
