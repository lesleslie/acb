from acb.config import AdapterBase, Settings


class ModelsBaseSettings(Settings): ...


class ModelsBase(AdapterBase):
    class SqlModels: ...

    sql = SqlModels()

    class NosqlModels: ...

    nosql = NosqlModels()
