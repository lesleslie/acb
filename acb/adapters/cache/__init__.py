from importlib import import_module
from ipaddress import IPv4Address

from acb.config import ac
from acb.config import Settings
from pydantic import SecretStr
from pydantic import AnyUrl


class CacheSettings(Settings):
    db: int
    host: SecretStr
    user: SecretStr
    password: SecretStr
    namespace: str = ac.app.name
    default_timeout: int = 86400
    template_timeout: int = 300 if ac.deployed else 1
    media_timeout: int = 15_768_000
    media_control: str = f"max-age={media_timeout} public"
    port: int = 6379
    health_check_interval: int = 15


cache = import_module(f"acb.adapters.cache.{ac.adapters['cache']}").cache
