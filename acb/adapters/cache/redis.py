import asyncio
import typing as t

import asyncio_atexit
from acb.actions import dump
from acb.actions import load
from acb.adapters.logger import Logger
from acb.config import Config
from acb.debug import debug
from acb.depends import depends
from cashews.serialize import register_type
from cashews.wrapper import Cache as CashewsCache
from pydantic import RedisDsn
from ._base import CacheBaseSettings


class CacheSettings(CacheBaseSettings):
    @depends.inject
    def model_post_init(self, __context: t.Any, ac: Config = depends()) -> None:
        super().model_post_init(self)
        self._url: RedisDsn = RedisDsn(
            f"redis://{self.host.get_secret_value()}:{self.port}/{self.db}"
        )


class Cache(CashewsCache):
    config: Config = depends()
    logger: Logger = depends()

    def __init__(self) -> None:
        async def close_cache_session() -> None:
            self.logger.debug("Closing cache session...")
            loop = asyncio.get_running_loop()
            debug(loop.is_running())
            await self.close()
            self.logger.debug("Cache session closed.")

        asyncio_atexit.register(close_cache_session)
        super().__init__()

    async def encoder(self, value: t.Any, *args: object, **kwargs: object) -> bytes:
        return await dump.msgpack(
            value,
            secret_key=self.config.app.secret_key,
            secure_salt=self.config.app.secure_salt,
        )

    async def decoder(self, value: bytes, *args: object, **kwargs: object) -> t.Any:
        return await load.msgpack(
            value,
            secret_key=self.config.app.secret_key,
            secure_salt=self.config.app.secure_salt,
        )

    async def init(self, *args: object, **kwargs: object) -> t.NoReturn:
        await super().init(
            str(self.config.cache._url),
            password=self.config.cache.password.get_secret_value(),
            client_side=True,
            client_side_prefix=f"{self.config.app.name}:",
        )
        register_type(t.Any, self.encoder, self.decoder)
        self.logger.debug("App cache initialized.")


depends.set(Cache, Cache())
