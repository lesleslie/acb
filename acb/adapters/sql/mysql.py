from acb.depends import depends
from ._base import SqlBase
from ._base import SqlBaseSettings


class SqlSettings(SqlBaseSettings):
    _driver: str = "mysql+mysqldb"
    _async_driver: str = "mysql+asyncmy"


class Sql(SqlBase): ...


depends.set(Sql)
