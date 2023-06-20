# from redis_om import get_redis_connection
# from redis_om import Migrator

from . import BaseCacheSettings
from acb.config import BaseSettings
from acb.config import ac
from pydantic import field_validator


class CacheDbSettings(BaseCacheSettings):
    db: int = 0

    @field_validator('db')
    def db_greater_than_zero(cls, v):
        if v > 0:
            raise ValueError('db must be 0 (0 reserved for redis_om')
        return 0


class CacheDB:
    ...

    def __init_(self):
        ...
        # Migrator().run()
