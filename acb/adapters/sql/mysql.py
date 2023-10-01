import typing as t

from acb.depends import depends
from sqlalchemy.pool import NullPool
from ._base import SqlBase
from ._base import SqlBaseSettings


class SqlSettings(SqlBaseSettings):
    _driver: str = "mysql+mysqldb"
    _async_driver: str = "mysql+asyncmy"

    def model_post_init(self, __context: t.Any) -> None:
        self.port = 3306
        self.poolclass = NullPool
        self.pool_pre_ping = True
        self.engine_kwargs = dict(
            poolclass=self.poolclass, pool_pre_ping=self.pool_pre_ping
        )


class Sql(SqlBase):
    ...


depends.set(Sql, Sql())
