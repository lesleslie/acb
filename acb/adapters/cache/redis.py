import asyncio
import typing as t

import asyncio_atexit
from acb.actions import dump
from acb.actions import load
from acb.config import ac
from acb.logger import logger
from cashews.serialize import register_type
from cashews.wrapper import Cache as CashewsCache
from icecream import ic
from pydantic import RedisDsn
from . import CacheBaseSettings


class CacheSettings(CacheBaseSettings):
    def model_post_init(self, __context: t.Any) -> None:
        super().model_post_init(self)
        self._url: RedisDsn = RedisDsn(
            f"redis://{self.host.get_secret_value()}:{self.port}/{self.db}"
        )


class Cache(CashewsCache):
    def __init__(self) -> None:
        async def close_cache_session() -> None:
            logger.debug("Closing cache session...")
            loop = asyncio.get_running_loop()
            ic(loop.is_running())
            await self.close()
            logger.debug("Cache session closed.")

        asyncio_atexit.register(close_cache_session)

        super().__init__()

    @staticmethod
    async def encoder(value: t.Any, *args: object, **kwargs: object) -> bytes:
        return await dump.msgpack(
            value,
            secret_key=ac.app.secret_key,
            secure_salt=ac.app.secure_salt,
        )

    @staticmethod
    async def decoder(value: bytes, *args: object, **kwargs: object) -> t.Any:
        return await load.msgpack(
            value,
            secret_key=ac.app.secret_key,
            secure_salt=ac.app.secure_salt,
        )

    async def init(self, *args: object, **kwargs: object) -> t.NoReturn:
        await super().init(
            str(ac.cache._url),
            password=ac.cache.password.get_secret_value(),
            client_side=True,
            client_side_prefix=f"{ac.app.name}:",
        )
        register_type(t.Any, self.encoder, self.decoder)

        logger.debug("App cache initialized.")


cache: Cache = Cache()
