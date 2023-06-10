import typing as t
from ipaddress import IPv4Address

from acb import ac
from acb import AppSettings
from acb.actions import dump
from acb.actions import load
from cashews import cache
from cashews.serialize import register_type


class CacheSettings(AppSettings):
    namespace = ac.app.name
    default_timeout = 86400
    template_timeout = 300 if ac.deployed else 1
    media_timeout = 15_768_000
    media_control = f"max-age={media_timeout} public"
    secret_key = ac.secrets.app_secret_key or None
    secure_salt = ac.secrets.app_secure_salt or None
    host: IPv4Address = ac.secrets.redis_host if ac.deployed else ac.app.localhost
    password: str = ac.secrets.redis_password or ""
    port = 6379
    db = 1
    health_check_interval = 15

    async def encoder(self, value: t.Any, *args, **kwargs) -> bytes:
        return await dump.msgpack(
            value, secret_key=self.secret_key, secure_salt=self.secure_salt
        )

    async def decoder(self, value: bytes, *args, **kwargs) -> t.Any:
        return await load.msgpack(
            value, secret_key=self.secret_key, secure_salt=self.secure_salt
        )

    def __init__(self, **data: t.Any) -> None:
        super().__init__(**data)
        self.password = self.password if ac.deployed else ""
        self.url = f"redis://{self.host}:{self.port}/{self.db}"
        cache.setup(
            self.url,
            password=self.password,
            client_side=True,
            client_side_prefix=f"{ac.app.name}:",
        )
        register_type(t.Any, self.encoder, self.decoder)
