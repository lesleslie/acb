import typing as t

from acb.depends import depends
from sqlalchemy.pool import NullPool
from ._base import SqlBase
from ._base import SqlBaseSettings


class SqlSettings(SqlBaseSettings):
    driver: str = "mysql+mysqldb"
    async_driver: str = "mysql+asyncmy"
    port: int = 3306
    pool_pre_ping: bool = True

    def model_post_init(self, __context: t.Any) -> None:
        super().model_post_init(self)
        self.poolclass = NullPool
        self.engine_kwargs = dict(
            poolclass=self.poolclass, pool_pre_ping=self.pool_pre_ping
        )


class Sql(SqlBase):
    ...


depends.set(Sql, Sql())
