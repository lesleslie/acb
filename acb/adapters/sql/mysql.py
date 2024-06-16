from acb.depends import depends
from ._base import SqlBase, SqlBaseSettings


class SqlSettings(SqlBaseSettings):
    _driver: str = "mysql+pymysql"
    _async_driver: str = "mysql+aiomysql"


class Sql(SqlBase): ...


depends.set(Sql)
