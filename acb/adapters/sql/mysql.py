import typing as t
from pprint import pprint

from acb.config import ac
from pydantic import SecretStr
from sqlalchemy.pool import NullPool
from . import SqlBaseDatabase
from . import SqlBaseSettings


# class MysqlSecrets(SqlBaseSecrets):
#     def __init__(self, **values: t.Any):
#         super().__init__(**values)
#         pprint(self.model_dump())


class MysqlSettings(SqlBaseSettings):
    # host: SecretStr = ac.secrets.sql_host
    # user: SecretStr = ac.secrets.sql_username
    # password: SecretStr = ac.secrets.sql_password
    driver: str = "mysql+mysqldb"
    async_driver: str = "mysql+asyncmy"
    port: int = 3306

    # def __init__(self, **data: t.Any):
    #     super().__init__(**data)
    #     # self.engine_kwargs = dict(poolclass=NullPool, pool_pre_ping=True)
    #     self.host: SecretStr = ac.secrets.sql_host
    #     self.user: SecretStr = ac.secrets.sql_username
    #     self.password: SecretStr = ac.secrets.sql_password
    #     self.host = self.host if ac.deployed else "127.0.0.1"
    #     pprint(self.model_dump())


class MysqlDatabase(SqlBaseDatabase):
    ...


sql = MysqlDatabase()
