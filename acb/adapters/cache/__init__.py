from acb.config import load_adapter
from acb.config import ac
from acb.config import Settings
from acb.config import gen_password
from pydantic import SecretStr
from pydantic import field_validator


class CacheBaseSettings(Settings):
    db: int = 1
    host: SecretStr = SecretStr("127.0.0.1")
    password: SecretStr = SecretStr(gen_password(10))
    namespace: str = ac.app.name
    default_timeout: int = 86400
    template_timeout: int = 300 if ac.deployed else 1
    media_timeout: int = 15_768_000
    media_control: str = f"max-age={media_timeout} public"
    port: int = 6379
    health_check_interval: int = 15

    @field_validator("db")
    def db_less_than_three(cls, v) -> int:
        if v < 3 and v != 1:
            raise ValueError("must be greater than 2 (0-2 are reserved)")
        return 1


cache = load_adapter("cache")
