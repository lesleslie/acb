import asyncio
import typing as t

import asyncio_atexit
from acb.actions.encode import dump
from acb.actions.encode import load
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
    def model_post_init(self, __context: t.Any, config: Config = depends()) -> None:
        super().model_post_init(__context)
        self._url = RedisDsn(
            f"redis://{self.host.get_secret_value()}:{self.port}/{self.db}"
        )


class Cache(CashewsCache):
    # config: Config = depends()
    logger: Logger = depends()  # type: ignore

    @depends.inject
    async def encoder(
        self, value: t.Any, config: Config = depends(), *args: t.Any, **kwargs: t.Any
    ) -> (bytes):
        return await dump.msgpack(
            value,
            secret_key=config.app.secret_key,
            secure_salt=config.app.secure_salt,
        )

    @depends.inject
    async def decoder(
        self, value: bytes, config: Config = depends(), *args: t.Any, **kwargs: t.Any
    ) -> t.Any:
        return await load.msgpack(
            value,
            secret_key=config.app.secret_key,
            secure_salt=config.app.secure_salt,
        )

    @depends.inject
    async def init(
        self, config: Config = depends(), *args: t.Any, **kwargs: t.Any
    ) -> t.NoReturn:
        await super().init(
            str(config.cache._url),
            password=config.cache.password.get_secret_value(),
            client_side=True,
            client_side_prefix=f"{config.app.name}:",
        )
        register_type(t.Any, self.encoder, self.decoder)

        async def close_cache_session() -> None:
            self.logger.debug("Closing cache session...")
            loop = asyncio.get_running_loop()
            debug(loop.is_running())
            await self.close()
            self.logger.debug("Cache session closed")

        asyncio_atexit.register(close_cache_session)


depends.set(Cache, Cache())
