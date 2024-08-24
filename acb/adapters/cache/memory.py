import typing as t

from aiocache.backends.memory import SimpleMemoryCache
from aiocache.serializers import PickleSerializer
from acb.depends import depends
from ._base import CacheBase, CacheBaseSettings


class CacheSettings(CacheBaseSettings): ...


class Cache(CacheBase, SimpleMemoryCache):  # type: ignore
    async def init(self, *args: t.Any, **kwargs: t.Any) -> t.NoReturn:
        super().__init__(
            serializer=PickleSerializer(),
            namespace=f"{self.config.app.name}:",
            **kwargs,
        )


depends.set(Cache)
