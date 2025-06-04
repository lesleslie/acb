from acb.depends import depends

from ._base import SqlBase, SqlBaseSettings


class SqlSettings(SqlBaseSettings):
    _driver: str = "postgresql+psycopg2"
    _async_driver: str = "postgresql+asyncpg"

    @property
    def driver(self) -> str:
        return self._driver

    @property
    def async_driver(self) -> str:
        return self._async_driver


class Sql(SqlBase): ...


depends.set(Sql)
