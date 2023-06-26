import typing as t
from contextlib import asynccontextmanager
from functools import cached_property
from functools import lru_cache

from acb.actions import dump
from acb.actions import load
from acb.config import ac
from cashews import Cache as CashewsCache
from cashews.serialize import register_type
from pydantic import field_validator
from . import CacheBaseSettings


class CacheSettings(CacheBaseSettings):
    db: int = 1

    @field_validator("db")
    def db_is_zero(cls, v):
        if v == 0:
            raise ValueError("must be greater than 0 (0 reserved for redis_om")
        return v

    @cached_property
    def async_session(self) -> CashewsCache:
        url = f"redis://{self.host.get_secret_value()}:{self.port}/{self.db}"
        cache = CashewsCache()
        cache.setup(
            url,
            password=self.password.get_secret_value(),
            client_side=True,
            client_side_prefix=f"{ac.app.name}:",
        )
        return cache


class Cache:
    @staticmethod
    async def encoder(value: t.Any, *args, **kwargs) -> bytes:
        return await dump.msgpack(
            value, secret_key=ac.app.secret_key.get_secret_value(),
            secure_salt=ac.app.secure_salt.get_secret_value()
        )

    @staticmethod
    async def decoder(value: bytes, *args, **kwargs) -> t.Any:
        return await load.msgpack(
            value, secret_key=ac.app.secret_key.get_secret_value(),
            secure_salt=ac.app.secure_salt.get_secret_value()
        )

    @lru_cache
    def get_async_session(self) -> CashewsCache:
        return ac.cache.async_session

    @asynccontextmanager
    async def session(self) -> t.AsyncGenerator:
        async with self.get_async_session() as sess:
            yield sess

    def __init__(self) -> None:
        register_type(t.Any, self.encoder, self.decoder)


cache = Cache()
