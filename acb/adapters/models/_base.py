import typing as t

from acb.config import AdapterBase, Settings


class ModelsBaseSettings(Settings): ...


class ModelsProtocol(t.Protocol):
    sql: t.Any = ...
    nosql: t.Any = ...

    class SqlModels: ...

    class NosqlModels: ...


class ModelsBase(AdapterBase):
    class SqlModels: ...

    sql = SqlModels()

    class NosqlModels: ...

    nosql = NosqlModels()
