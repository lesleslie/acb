import typing as t

from acb.config import Settings


class SecretBaseSettings(Settings):
    requires: t.Optional[list[str]] = ["logger"]


class SecretBase(t.Protocol):
    async def list(self, adapter: str) -> t.NoReturn: ...

    async def create(self, name: str, value: str) -> t.NoReturn: ...

    async def update(self, name: str, value: str) -> t.NoReturn: ...

    async def get(self, name: str) -> t.NoReturn: ...

    async def delete(self, name: str) -> t.NoReturn: ...
