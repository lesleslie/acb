import typing as t

from acb.adapters import AdapterBase
from acb.config import Config
from acb.config import gen_password
from acb.config import Settings
from acb.depends import depends
from cashews.wrapper import Cache
from pydantic import AnyUrl
from pydantic import field_validator
from pydantic import RedisDsn
from pydantic import SecretStr


class CacheBaseSettings(Settings):
    prefix: t.Optional[str] = None
    db: t.Optional[int] = 1
    host: SecretStr = SecretStr("127.0.0.1")
    password: SecretStr = SecretStr(gen_password())
    _url: t.Optional[AnyUrl | RedisDsn] = None
    default_timeout: int = 86400
    template_timeout: int = 300
    media_timeout: int = 15_768_000
    media_control: str = f"max-age={media_timeout} public"
    port: t.Optional[int] = 6379
    health_check_interval: int = 15
    loggers: t.Optional[list[str]] = []

    @depends.inject
    def __init__(self, config: Config = depends(), **values: t.Any) -> None:
        super().__init__(**values)
        self.prefix = self.prefix or f"{config.app.name}:"
        self.host = SecretStr("127.0.0.1") if not config.deployed else self.host
        self.password = SecretStr("") if not config.deployed else self.password
        self.template_timeout = self.template_timeout if config.deployed else 1
        self.default_timeout = self.default_timeout if config.deployed else 1

    @field_validator("db")
    def db_less_than_three(cls, v: int) -> int:
        if v < 3 and v != 1:
            raise ValueError("must be greater than 2 (0-2 are reserved)")
        return 1


class CacheBase(Cache, AdapterBase): ...
