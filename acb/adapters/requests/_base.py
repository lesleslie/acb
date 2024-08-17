import typing as t
from abc import ABC, abstractmethod

from acb.adapters import AdapterBase
from acb.config import Settings


class RequestsBaseSettings(Settings):
    cache_ttl: int = 3600


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
