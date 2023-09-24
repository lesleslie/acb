from acb.config import Settings
from pydantic import field_validator
from abc import ABC
from abc import abstractmethod
from requests import Response
from httpx import Response as HttpxResponse
import typing as t


class RequestsBaseSettings(Settings):
    cache_db: int = 2

    @field_validator("cache_db")
    def cache_db_less_than_three(cls, v: int) -> int:
        if v < 3 and v != 2:
            raise ValueError("must be greater than 2 (0-2 are reserved)")
        return 2


class RequestsBase(ABC):
    @abstractmethod
    async def init(self) -> None:
        ...

    @abstractmethod
    async def get(self, url: str) -> Response | HttpxResponse:
        ...

    @abstractmethod
    async def post(self, url: str, data: dict[str, t.Any]) -> Response | HttpxResponse:
        ...

    @abstractmethod
    async def put(self, url: str, data: dict[str, t.Any]) -> Response | HttpxResponse:
        ...

    @abstractmethod
    async def delete(self, url: str) -> Response | HttpxResponse:
        ...
