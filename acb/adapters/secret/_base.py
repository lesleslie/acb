import typing as t

from anyio import Path as AsyncPath
from acb.config import AdapterBase, Settings, app_name


class SecretBaseSettings(Settings):
    secrets_path: AsyncPath


class SecretProtocol(t.Protocol):
    async def list(self, adapter: str) -> None: ...

    async def create(self, name: str, value: str) -> None: ...

    async def update(self, name: str, value: str) -> None: ...

    async def get(self, name: str) -> None: ...

    async def delete(self, name: str) -> None: ...


class SecretBase(AdapterBase, SecretProtocol):
    prefix: str = f"{app_name}_"
