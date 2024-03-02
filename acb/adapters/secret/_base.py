import typing as t
from abc import ABC
from abc import abstractmethod

from acb.config import Settings


class SecretBaseSettings(Settings):
    requires: t.Optional[list[str]] = ["logger"]


class SecretBase(ABC):
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
