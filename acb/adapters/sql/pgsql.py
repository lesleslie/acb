from acb.depends import depends

from ._base import SqlBase, SqlBaseSettings


class SqlSettings(SqlBaseSettings):
    _driver: str = "postgresql+psycopg2"
    _async_driver: str = "postgresql+asyncpg"


class Sql(SqlBase): ...


depends.set(Sql)
