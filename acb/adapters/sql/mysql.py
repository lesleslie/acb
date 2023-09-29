import typing as t

from acb.depends import depends
from sqlalchemy.pool import NullPool
from ._base import SqlBase
from ._base import SqlBaseSettings


class SqlSettings(SqlBaseSettings):
    driver: str = "mysql+mysqldb"
    async_driver: str = "mysql+asyncmy"
    port: int = 3306

    def model_post_init(self, __context: t.Any) -> None:
        self.poolclass = NullPool
        self.pool_pre_ping = True
        self.engine_kwargs = dict(
            poolclass=self.poolclass, pool_pre_ping=self.pool_pre_ping
        )


class Sql(SqlBase):
    ...


depends.set(Sql, Sql())
