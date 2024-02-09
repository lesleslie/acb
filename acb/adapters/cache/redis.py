import typing as t

from acb.actions.encode import dump
from acb.actions.encode import load
from acb.config import Config
from acb.depends import depends
from cashews.serialize import register_type
from pydantic import RedisDsn
from ._base import CacheBase
from ._base import CacheBaseSettings
from cashews.serialize import Serializer


class CacheSettings(CacheBaseSettings):
    @depends.inject
    def __init__(self, config: Config = depends(), **values: t.Any) -> None:
        super().__init__(config, **values)
        self._url = RedisDsn(  # type: ignore
            f"redis://{self.host.get_secret_value()}:{self.port}/{self.db}"
        )


class Cache(CacheBase):
    async def encoder(self, value: t.Any, *args: t.Any, **kwargs: t.Any) -> bytes:
        return await dump.msgpack(
            value,
            secret_key=self.config.app.secret_key,
            secure_salt=self.config.app.secure_salt,
        )

    async def decoder(self, value: bytes, *args: t.Any, **kwargs: t.Any) -> t.Any:
        return await load.msgpack(
            value,
            secret_key=self.config.app.secret_key,
            secure_salt=self.config.app.secure_salt,
        )

    async def init(self, *args: t.Any, **kwargs: t.Any) -> t.NoReturn:
        await super().init(
            str(self.config.cache._url),
            password=self.config.cache.password.get_secret_value(),
            client_side=True,
            client_side_prefix=self.config.cache.prefix,
        )
        register_type(Serializer, self.encoder, self.decoder)
        self.logger.debug(f"Ping:  {(await self.ping()).decode()}")


depends.set(Cache)
