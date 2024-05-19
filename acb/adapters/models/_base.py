from acb.adapters import AdapterBase
from acb.config import Settings


class ModelsBaseSettings(Settings): ...


class ModelsBase(AdapterBase):
    class SqlModels: ...

    sql = SqlModels()

    class NosqlModels: ...

    nosql = NosqlModels()
