import typing as t
from abc import ABC
from abc import abstractmethod

from acb.adapters import AdapterBase
from acb.config import Settings
from pydantic import field_validator


class RequestsBaseSettings(Settings):
    cache_db: t.Optional[int] = 2
    cache_ttl: int = 3600

    @field_validator("cache_db")
    def cache_db_less_than_three(cls, v: int) -> int:
        if v < 3 and v != 2:
            raise ValueError("must be greater than 2 (0-2 are reserved)")
        return 2


class RequestsBase(AdapterBase, ABC):
    @abstractmethod
    async def get(self, url: str, timeout: int) -> t.Any:
        raise NotImplementedError

    @abstractmethod
    async def post(self, url: str, data: dict[str, t.Any], timeout: int) -> t.Any:
        raise NotImplementedError

    @abstractmethod
    async def put(self, url: str, data: dict[str, t.Any], timeout: int) -> t.Any:
        raise NotImplementedError

    @abstractmethod
    async def delete(self, url: str, timeout: int) -> t.Any:
        raise NotImplementedError
