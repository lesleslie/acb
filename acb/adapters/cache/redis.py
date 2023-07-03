import typing as t

from acb.actions import dump
from acb.actions import load
from acb.config import ac
from cashews import Cache as CashewsCache
from cashews.serialize import register_type
from pydantic import RedisDsn
from . import CacheBaseSettings


class CacheSettings(CacheBaseSettings):
    def model_post_init(self, __context: t.Any) -> None:
        super().model_post_init(self)
        self.namespace = ac.app.name
        self._url: RedisDsn = (
            f"redis://{self.host.get_secret_value()}:{self.port}/{self.db}"
        )


class Cache(CashewsCache):
    @staticmethod
    async def encoder(value: t.Any, *args, **kwargs) -> bytes:
        return await dump.msgpack(
            value,
            secret_key=ac.app.secret_key.get_secret_value(),
            secure_salt=ac.app.secure_salt.get_secret_value(),
        )

    @staticmethod
    async def decoder(value: bytes, *args, **kwargs) -> t.Any:
        return await load.msgpack(
            value,
            secret_key=ac.app.secret_key.get_secret_value(),
            secure_salt=ac.app.secure_salt.get_secret_value(),
        )

    async def init(self, *args, **kwargs) -> None:
        await super().init(
            ac.cache._url,
            password=ac.cache.password.get_secret_value(),
            client_side=True,
            client_side_prefix=f"{ac.app.name}:",
        )
        register_type(t.Any, self.encoder, self.decoder)


cache = Cache()
