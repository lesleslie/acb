from pydantic import field_validator

from ._base import NosqlBase, NosqlBaseSettings


class NosqlSettings(NosqlBaseSettings):
    cache_db: int = 0

    @field_validator("cache_db")
    @classmethod
    def cache_db_not_zero(cls, v: int) -> int:  # noqa: F841
        if v < 3 and v != 0:
            raise ValueError("must be > 3 (0-2 are reserved)")
        return 0


class Nosql(NosqlBase): ...
