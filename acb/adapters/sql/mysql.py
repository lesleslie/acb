import typing as t

from acb.config import Config
from acb.depends import depends
from sqlalchemy.pool import NullPool
from ._base import SqlBase
from ._base import SqlBaseSettings


class SqlSettings(SqlBaseSettings):
    _driver: str = "mysql+mysqldb"
    _async_driver: str = "mysql+asyncmy"

    @depends.inject
    def __init__(self, config: Config = depends(), **values: t.Any) -> None:
        super().__init__(config, **values)
        self.poolclass = NullPool
        self.pool_pre_ping = True
        self.engine_kwargs = dict(
            poolclass=self.poolclass, pool_pre_ping=self.pool_pre_ping
        )


class Sql(SqlBase):
    ...


depends.set(Sql)
