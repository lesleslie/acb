from importlib import import_module
from ipaddress import IPv4Address
import typing as t

from acb.config import ac
from acb.config import AppSettings
from pydantic import AnyUrl


class CacheSecrets:
    host: t.Optional[str]
    password: t.Optional[str]

class BaseCacheSettings(AppSettings):
    namespace: str = ac.app.name
    default_timeout: int = 86400
    template_timeout: int = 300 if ac.deployed else 1
    media_timeout: int = 15_768_000
    media_control: str = f"max-age={media_timeout} public"
    secret_key: str = ac.secrets.app_secret_key or None
    secure_salt: str = ac.secrets.app_secure_salt or None
    host: IPv4Address | AnyUrl = (
        ac.secrets.cache_host if ac.deployed else ac.app.localhost
    )
    password: str = ac.secrets.cache_password or ""
    port: int = 6379
    db: int = 1
    health_check_interval: int = 15


cache = import_module(ac.adapters.cache)
