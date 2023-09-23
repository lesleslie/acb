from acb.config import Settings
from pydantic import field_validator
from abc import ABC
from abc import abstractmethod
from requests import Response
from httpx import Response as HttpxResponse


class RequestBaseSettings(Settings):
    cache_db: int = 2

    @field_validator("cache_db")
    def cache_db_less_than_three(cls, v) -> int:
        if v < 3 and v != 2:
            raise ValueError("must be greater than 2 (0-2 are reserved)")
        return 2


class RequestBase(ABC):
    @abstractmethod
    async def init(self) -> None:
        ...

    @abstractmethod
    async def get(self, url: str) -> Response | HttpxResponse:
        ...

    @abstractmethod
    async def post(self, url: str, data: dict) -> Response | HttpxResponse:
        ...

    @abstractmethod
    async def put(self, url: str, data: dict) -> Response | HttpxResponse:
        ...

    @abstractmethod
    async def delete(self, url: str) -> Response | HttpxResponse:
        ...
