from sqlalchemy.pool import NullPool
from . import SqlBase
from . import SqlBaseSettings
import typing as t


class SqlSettings(SqlBaseSettings):
    driver: str = "mysql+mysqldb"
    async_driver: str = "mysql+asyncmy"
    port: int = 3306
    pool_pre_ping: bool = True
    # poolclass: t.Any = None

    def model_post_init(self, __context: t.Any) -> None:
        self.poolclass = NullPool
        self.engine_kwargs = dict(
            poolclass=self.poolclass, pool_pre_ping=self.pool_pre_ping
        )


class Sql(SqlBase):
    ...


sql = Sql()
