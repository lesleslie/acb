import typing as t

from cashews.serialize import Serializer, register_type
from msgspec import msgpack
from acb.depends import depends
from ._base import CacheBase, CacheBaseSettings


class CacheSettings(CacheBaseSettings): ...


class Cache(CacheBase):
    @staticmethod
    async def encoder(value: t.Any, *args: t.Any, **kwargs: t.Any) -> bytes:
        return msgpack.encode(value)

    @staticmethod
    async def decoder(value: bytes, *args: t.Any, **kwargs: t.Any) -> t.Any:
        return msgpack.decode(value)

    async def init(self, *args: t.Any, **kwargs: t.Any) -> t.NoReturn:
        await super().init(
            "mem://",
            prefix=self.config.cache.prefix,
        )
        register_type(Serializer, self.encoder, self.decoder)


depends.set(Cache)
