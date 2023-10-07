import typing as t
from abc import ABC
from abc import abstractmethod

from acb.config import Settings


class SecretsBaseSettings(Settings):
    requires: list[str] = ["logger"]


class SecretsBase(ABC):
    @abstractmethod
    async def init(self) -> t.NoReturn:
        raise NotImplementedError

    @abstractmethod
    async def list(self, adapter: str) -> t.NoReturn:
        raise NotImplementedError

    @abstractmethod
    async def create(self, name: str, value: str) -> t.NoReturn:
        raise NotImplementedError

    @abstractmethod
    async def update(self, name: str, value: str) -> t.NoReturn:
        raise NotImplementedError

    @abstractmethod
    async def get(self, name: str) -> t.NoReturn:
        raise NotImplementedError

    @abstractmethod
    async def delete(self, name: str) -> t.NoReturn:
        raise NotImplementedError
