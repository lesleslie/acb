import typing as t

from acb.config import Config
from acb.config import gen_password
from acb.config import Settings
from acb.depends import depends
from pydantic import AnyUrl
from pydantic import field_validator
from pydantic import SecretStr


class CacheBaseSettings(Settings):
    namespace: t.Optional[str] = None
    db: int = 1
    host: SecretStr = SecretStr("127.0.0.1")
    password: SecretStr = SecretStr(gen_password(10))
    _url: t.Optional[AnyUrl] = None
    default_timeout: int = 86400
    template_timeout: t.Optional[int] = 300
    media_timeout: int = 15_768_000
    media_control: str = f"max-age={media_timeout} public"
    port: int = 6379
    health_check_interval: int = 15

    @depends.inject
    def model_post_init(self, __context: t.Any, config: Config = depends()) -> None:
        super().model_post_init(__context)
        self.namespace = self.namespace or config.app.name or ""
        self.host = SecretStr("127.0.0.1") if not config.deployed else self.host
        self.password = SecretStr("") if not config.deployed else self.password
        self.template_timeout = self.template_timeout if config.deployed else 1

    @field_validator("db")
    def db_less_than_three(cls, v: int) -> int:
        if v < 3 and v != 1:
            raise ValueError("must be greater than 2 (0-2 are reserved)")
        return 1
