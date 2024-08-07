import typing as t

from cashews.serialize import Serializer, register_type
from pydantic import RedisDsn
from acb.actions.encode import dump, load
from acb.config import Config
from acb.depends import depends
from ._base import CacheBase, CacheBaseSettings


class CacheSettings(CacheBaseSettings):
    socket_timeout: t.Optional[float] = 0.5
    disable: t.Optional[bool] = False

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
            # password=self.config.cache.password.get_secret_value(),
            client_side=True,
            client_side_prefix=self.config.cache.prefix,
            socket_timeout=self.config.cache.socket_timeout,
            disable=self.config.cache.disable,
        )
        register_type(Serializer, self.encoder, self.decoder)
        if not self.config.cache.disable:
            self.logger.debug(f"Ping:  {(await self.ping()).decode()}")


depends.set(Cache)
