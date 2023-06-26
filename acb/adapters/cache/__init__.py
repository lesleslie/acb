from importlib import import_module

from acb.config import ac
from acb.config import Settings
from acb.config import gen_password
from pydantic import SecretStr


class CacheBaseSettings(Settings):
    db: int
    host: SecretStr = SecretStr("127.0.0.1")
    password: SecretStr = SecretStr(gen_password(10))
    namespace: str = ac.app.name
    default_timeout: int = 86400
    template_timeout: int = 300 if ac.deployed else 1
    media_timeout: int = 15_768_000
    media_control: str = f"max-age={media_timeout} public"
    port: int = 6379
    health_check_interval: int = 15


cache = import_module(f"acb.adapters.cache.{ac.adapters['cache']}").cache
