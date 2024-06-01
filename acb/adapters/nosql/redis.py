# from redis_om import get_redis_connection
# from redis_om import Migrator

from pydantic import field_validator
from ._base import NosqlBase, NosqlBaseSettings


class NosqlSettings(NosqlBaseSettings):
    cache_db: int = 0

    @field_validator("cache_db")
    def cache_db_not_zero(cls, v: int) -> int:
        if v < 3 and v != 0:
            raise ValueError("must be > 3 (0-2 are reserved)")
        return 0


class Nosql(NosqlBase):
    def __init__(self) -> None:
        ...
        # Migrator().run()
