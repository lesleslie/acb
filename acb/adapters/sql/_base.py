import typing as t
from contextlib import asynccontextmanager
from functools import cached_property

from pydantic import SecretStr
from sqlalchemy import log as sqlalchemy_log
from sqlalchemy import pool, text
from sqlalchemy.engine import URL
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, create_async_engine
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession
from acb.adapters import import_adapter
from acb.config import AdapterBase, Config, Settings, gen_password
from acb.debug import debug
from acb.depends import depends


class SqlBaseSettings(Settings):
    _driver: str
    _async_driver: str
    port: t.Optional[int] = 3306
    pool_pre_ping: t.Optional[bool] = False
    poolclass: t.Optional[t.Any] = None
    host: SecretStr = SecretStr("127.0.0.1")
    local_host: str = "127.0.0.1"
    user: SecretStr = SecretStr("root")
    password: SecretStr = SecretStr(gen_password())
    _url: t.Optional[URL] = None
    _async_url: t.Optional[URL] = None
    engine_kwargs: dict[str, t.Any] = {}
    backup_enabled: bool = False
    backup_bucket: str | None = None
    cloudsql_instance: t.Optional[str] = None

    @depends.inject
    def __init__(self, config: Config = depends(), **values: t.Any) -> None:
        super().__init__(**values)
        url_kwargs = dict(
            drivername=self._driver,
            username=self.user.get_secret_value(),
            password=self.password.get_secret_value(),
            host=(
                self.local_host if not config.deployed else self.host.get_secret_value()
            ),
            port=self.port,
            database=config.app.name,
        )
        self.poolclass = getattr(pool, self.poolclass) if self.poolclass else None
        self._url = URL.create(**url_kwargs)  # type: ignore
        async_url_kwargs = dict(drivername=self._async_driver)
        self._async_url = URL.create(**(url_kwargs | async_url_kwargs))  # type: ignore
        self.engine_kwargs["echo"] = (
            "debug" if config.logger.verbose else config.debug.sql
        )
        self.engine_kwargs["echo_pool"] = (
            "debug" if config.logger.verbose else config.debug.sql
        )
        self.engine_kwargs = (  # type: ignore
            dict(poolclass=self.poolclass, pool_pre_ping=self.pool_pre_ping)
            | self.engine_kwargs
        )


class SqlBase(AdapterBase):
    exists: bool = False

    @cached_property
    def engine(self) -> AsyncEngine:
        return create_async_engine(
            self.config.sql._async_url, **self.config.sql.engine_kwargs
        )

    @cached_property
    def session(self) -> AsyncSession:
        return AsyncSession(self.engine, expire_on_commit=False)

    @asynccontextmanager
    async def get_session(self) -> t.AsyncGenerator[AsyncSession, None]:
        async with self.session as sess:
            yield sess

    @asynccontextmanager
    async def get_conn(self) -> t.AsyncGenerator[AsyncConnection, None]:
        async with self.engine.begin() as conn:
            yield conn

    async def init(
        self,
    ) -> None:
        sqlalchemy_log._add_default_handler = lambda _: None  # type: ignore
        async with self.get_conn() as conn:
            if self.config.debug.sql:
                ps = await conn.execute(text("SHOW FULL PROCESSLIST"))
                show_ps = [p for p in ps]
                debug(show_ps)
                ids = [
                    a[0]
                    for a in show_ps
                    if (
                        a[1] == self.config.sql.user.get_secret_value()
                        and a[3] == self.config.app.name
                    )
                ]
                debug(ids)
            try:
                await conn.run_sync(SQLModel.metadata.drop_all)
                import_adapter("models")
                await conn.run_sync(SQLModel.metadata.create_all)
            except Exception as e:
                self.logger.error(e)
