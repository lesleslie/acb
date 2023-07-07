from acb.config import Settings
from pydantic import field_validator


class RequestsBaseSettings(Settings):
    cache_db: int = 2

    @field_validator("cache_db")
    def cache_db_less_than_three(cls, v) -> int:
        if v < 3 and v != 2:
            raise ValueError("must be greater than 2 (0-2 are reserved)")
        return 2


# requests = load_adapter("requests")
