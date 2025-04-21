import typing as t

from acb.config import AdapterBase, Settings


class ModelsBaseSettings(Settings): ...


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
