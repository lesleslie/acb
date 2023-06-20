import typing as t

from acb.actions import dump
from acb.actions import load
from acb.config import ac
from cashews import cache as cashews_cache
from cashews.serialize import register_type
from pydantic import field_validator
from . import BaseCacheSettings


class CacheSettings(BaseCacheSettings):
    db: int = 1

    @field_validator("db")
    def db_is_zero(cls, v):
        if v == 0:
            raise ValueError("must be greater than 0 (0 reserved for redis_om")
        return v


class Cache:
    @staticmethod
    async def encoder(value: t.Any, *args, **kwargs) -> bytes:
        return await dump.msgpack(
            value, secret_key=ac.secrets.secret_key, secure_salt=ac.secrets.secure_salt
        )

    @staticmethod
    async def decoder(value: bytes, *args, **kwargs) -> t.Any:
        return await load.msgpack(
            value, secret_key=ac.cache.secret_key, secure_salt=ac.cache.secure_salt
        )

    def __init__(self, **data: t.Any) -> None:
        super().__init__(**data)
        self.url = f"redis://{ac.cache.host}:{ac.cache.port}/{ac.cache.db}"
        cashews_cache.setup(
            ac.cache.url,
            password=ac.cache.password,
            client_side=True,
            client_side_prefix=f"{ac.app.name}:",
        )
        register_type(t.Any, self.encoder, self.decoder)
