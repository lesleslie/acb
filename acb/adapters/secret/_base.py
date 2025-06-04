import builtins
from abc import abstractmethod

from anyio import Path as AsyncPath
from acb.config import AdapterBase, Settings, app_name


class SecretBaseSettings(Settings):
    secrets_path: AsyncPath


class SecretBase(AdapterBase):
    prefix: str = f"{app_name}_"

    @abstractmethod
    async def list(self, adapter: str | None = None) -> list[str]:
        pass

    @abstractmethod
    async def create(self, name: str, value: str) -> None:
        pass

    @abstractmethod
    async def update(self, name: str, value: str) -> None:
        pass

    @abstractmethod
    async def get(self, name: str, version: str | None = None) -> str | None:
        pass

    @abstractmethod
    async def delete(self, name: str) -> None:
        pass

    @abstractmethod
    async def list_versions(self, name: str) -> builtins.list[str]:
        pass
