import typing as t

from aiopath import AsyncPath
from acb.config import AdapterBase, Settings, app_name


class SecretBaseSettings(Settings):
    secrets_path: AsyncPath


class SecretProtocol(t.Protocol):
    async def list(self, adapter: str) -> t.NoReturn: ...

    async def create(self, name: str, value: str) -> t.NoReturn: ...

    async def update(self, name: str, value: str) -> t.NoReturn: ...

    async def get(self, name: str) -> t.NoReturn: ...

    async def delete(self, name: str) -> t.NoReturn: ...


class SecretBase(AdapterBase):
    prefix: str = f"{app_name}_"
