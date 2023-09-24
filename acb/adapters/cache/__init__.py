import typing as t

from acb.config import ac
from acb.config import gen_password
from acb.config import Settings
from pydantic import field_validator
from pydantic import SecretStr
from pydantic import AnyUrl


class CacheBaseSettings(Settings):
    namespace: t.Optional[str] = None
    db: int = 1
    host: SecretStr = SecretStr("127.0.0.1")
    password: SecretStr = SecretStr(gen_password(10))
    _url: t.Optional[AnyUrl] = None
    default_timeout: int = 86400
    # template_timeout: int = 300 if ac.deployed else 1
    media_timeout: int = 15_768_000
    media_control: str = f"max-age={media_timeout} public"
    port: int = 6379
    health_check_interval: int = 15

    def model_post_init(self, __context: t.Any) -> None:
        self.namespace = self.namespace or ac.app.name or ""
        self.host = SecretStr("127.0.0.1") if not ac.deployed else self.host
        self.password = SecretStr("") if not ac.deployed else self.password

    @field_validator("db")
    def db_less_than_three(cls, v: int) -> int:
        if v < 3 and v != 1:
            raise ValueError("must be greater than 2 (0-2 are reserved)")
        return 1
