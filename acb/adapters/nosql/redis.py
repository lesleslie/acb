# from redis_om import get_redis_connection
# from redis_om import Migrator

from . import NosqlBaseSettings
from pydantic import field_validator


class NosqlSettings(NosqlBaseSettings):
    cache_db: int = 0

    @field_validator("cache_db")
    def cache_db_not_zero(cls, v) -> int:
        if v < 3 and v != 0:
            raise ValueError("must be > 3 (0-2 are reserved)")
        return 0


class Nosql:
    def __init_(self) -> None:
        ...
        # Migrator().run()
