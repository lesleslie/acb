import typing as t
from contextlib import asynccontextmanager
from functools import cached_property

from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

from acb.adapters.logger import Logger
from acb.config import Config
from acb.config import gen_password
from acb.config import Settings
from acb.debug import debug
from acb.depends import depends
from aioconsole import ainput
from aioconsole import aprint
from pydantic import SecretStr
from sqlalchemy import inspect
from sqlalchemy.engine import URL
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncConnection
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy_utils import create_database
from sqlalchemy_utils import database_exists
from sqlalchemy_utils import drop_database


class SqlBaseSettings(Settings):
    requires: t.Optional[list[str]] = ["models"]
    _driver: str
    _async_driver: str
    port: t.Optional[int] = 3306
    pool_pre_ping: t.Optional[bool] = False
    poolclass: t.Optional[t.Any] = None
    host: SecretStr = SecretStr("127.0.0.1")
    user: SecretStr = SecretStr("root")
    password: SecretStr = SecretStr(gen_password())
    _url: t.Optional[URL] = None
    _async_url: t.Optional[URL] = None
    engine_kwargs: t.Optional[dict[str, t.Any]] = {}
    backup_enabled: bool = False
    backup_bucket: str | None = None
    loggers: t.Optional[list[str]] = [
        "sqlalchemy.engine",
        "sqlalchemy.orm",
        "sqlalchemy.pool",
        "sqlalchemy.dialects",
    ]

    @depends.inject
    def __init__(self, config: Config = depends(), **values: t.Any) -> None:
        super().__init__(**values)
        if self.backup_enabled:
            self.requires.append("storage")
        url_kwargs = dict(
            drivername=self._driver,
            username=self.user.get_secret_value(),
            password=self.password.get_secret_value(),
            host=("127.0.0.1" if not config.deployed else self.host.get_secret_value()),
            port=self.port,
            database=config.app.name,
        )
        self._url = URL.create(**url_kwargs)  # type: ignore
        async_url_kwargs = dict(drivername=self._async_driver)
        self._async_url = URL.create(**(url_kwargs | async_url_kwargs))  # type: ignore


class SqlBase:
    config: Config = depends()
    logger: Logger = depends()  # type: ignore

    @cached_property
    def engine(self) -> AsyncEngine:
        return create_async_engine(
            self.config.sql._async_url, **self.config.sql.engine_kwargs
        )

    @cached_property
    def session(self) -> AsyncSession:
        return AsyncSession(self.engine, expire_on_commit=False)

    async def create(self, demo: bool = False) -> None:
        try:
            exists = database_exists(self.config.sql._url)
            if exists:
                self.logger.debug("Sql database exists")
        except OperationalError:
            exists = False

        if (
            self.config.debug.sql
            and not (self.config.deployed or self.config.debug.production)
            and exists
        ):
            msg = (
                "\n\nRESETTING THE SQL DATABASE WILL CAUSE ALL OF YOUR"
                " CURRENT DATA TO BE LOST!\n"
            )
            if demo:
                msg = (
                    "\nBy running this module,\n\nYOUR SQL DATABASE WILL BE DELETED "
                    "AND "
                    "REPLACED WITH DEMO DATA.\nALL OF YOUR CURRENT DATA WILL BE LOST!\n"
                )
            await aprint(msg)
            delete_db = await ainput("Would you like to reset the database? (y/N) ")
            await aprint()
            if delete_db.upper().strip() == "Y":
                drop_database(self.config.sql._url)
                self.logger.warning("Sql database dropped")
                exists = database_exists(self.config.sql._url)
        if not exists:
            create_database(self.config.sql._url)
            self.logger.debug("Sql database created")

    @asynccontextmanager
    async def get_session(self) -> t.AsyncGenerator[AsyncSession, None]:
        async with self.session as sess:
            yield sess

    @asynccontextmanager
    async def get_conn(self) -> t.AsyncGenerator[AsyncConnection, None]:
        async with self.engine.begin() as conn:
            yield conn

    @staticmethod
    def get_table_names(conn: object) -> list[str]:
        inspector = inspect(conn)
        return inspector.get_table_names() or []

    async def init(
        self,
        demo: bool = False,
    ) -> None:
        await self.create(demo)
        async with self.get_conn() as conn:
            # if self.config.debug.sql:
            #     sql = text("DROP TABLE IF EXISTS alembic_version")
            #     await conn.execute(sql)
            self.logger.debug("Creating database tables...")
            await conn.run_sync(SQLModel.metadata.create_all)
            if self.config.debug.sql:
                table_names = await conn.run_sync(self.get_table_names)
                debug(table_names)
