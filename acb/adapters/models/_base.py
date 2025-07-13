from __future__ import annotations

import typing as t

from acb.config import AdapterBase, Settings


class ModelsBaseSettings(Settings):
    sqlmodel: bool = True
    sqlalchemy: bool = True
    pydantic: bool = True
    redis_om: bool = False
    msgspec: bool = True
    attrs: bool = False


class ModelsProtocol(t.Protocol):
    sql: t.Any
    nosql: t.Any

    class SqlModels:
        def __getattr__(self, name: str) -> t.Any: ...

    class NosqlModels:
        def __getattr__(self, name: str) -> t.Any: ...


class ModelsBase(AdapterBase):
    class SqlModels:
        def __getattr__(self, name: str) -> t.Any: ...

    sql = SqlModels()

    class NosqlModels:
        def __getattr__(self, name: str) -> t.Any: ...

    nosql = NosqlModels()
