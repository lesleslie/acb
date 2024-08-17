import typing as t

from cashews.wrapper import Cache
from pydantic import AnyUrl, RedisDsn, SecretStr
from acb.adapters import AdapterBase, import_adapter
from acb.config import Config, Settings
from acb.depends import depends

Logger = import_adapter()


class CacheBaseSettings(Settings):
    prefix: t.Optional[str] = None
    host: SecretStr = SecretStr("127.0.0.1")
    local_host: str = "127.0.0.1"
    _url: t.Optional[AnyUrl | RedisDsn] = None
    default_timeout: int = 86400
    port: t.Optional[int] = 6379
    health_check_interval: int = 10
    loggers: t.Optional[list[str]] = []

    @depends.inject
    def __init__(self, config: Config = depends(), **values: t.Any) -> None:
        super().__init__(**values)
        self.prefix = self.prefix or f"{config.app.name}:"
        self.host = SecretStr(self.local_host) if not config.deployed else self.host
        self.default_timeout = self.default_timeout if config.deployed else 1


class CacheBase(Cache, AdapterBase): ...
