from uuid import UUID

from acb.adapters import AdapterStatus
from acb.depends import depends

from ._base import SqlBase, SqlBaseSettings

MODULE_ID = UUID("0197ff44-c5a3-7040-8d7e-3b17c8e54691")
MODULE_STATUS = AdapterStatus.STABLE


class SqlSettings(SqlBaseSettings):
    _driver: str = "mysql+pymysql"
    _async_driver: str = "mysql+aiomysql"
    pool_size: int = 20
    max_overflow: int = 30
    pool_recycle: int = 3600
    pool_pre_ping: bool | None = True

    @property
    def driver(self) -> str:
        return self._driver

    @property
    def async_driver(self) -> str:
        return self._async_driver


class Sql(SqlBase): ...


depends.set(Sql)
