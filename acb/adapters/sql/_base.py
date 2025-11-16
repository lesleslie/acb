import typing as t
from contextlib import asynccontextmanager
from pydantic import SecretStr
from sqlalchemy import log as sqlalchemy_log
from sqlalchemy import pool, text
from sqlalchemy.engine import URL
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, create_async_engine
from sqlalchemy_utils import create_database, database_exists
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

from acb.adapters import import_adapter

# Removed complex enterprise mixins - simplified SQL adapters
from acb.cleanup import CleanupMixin
from acb.config import AdapterBase, Config, Settings, gen_password
from acb.debug import debug
from acb.depends import Inject, depends
from acb.ssl_config import SSLConfigMixin


class SqlBaseSettings(Settings, SSLConfigMixin):
    _driver: str
    _async_driver: str
    port: int | None = 3306
    pool_pre_ping: bool | None = False
    poolclass: t.Any | None = None
    host: SecretStr = SecretStr("127.0.0.1")
    local_host: str = "127.0.0.1"
    user: SecretStr = SecretStr("root")
    password: SecretStr = SecretStr(gen_password())
    _url: URL | None = None
    _async_url: URL | None = None
    engine_kwargs: dict[str, t.Any] = {}
    backup_enabled: bool = False
    backup_bucket: str | None = None
    cloudsql_instance: str | None = None
    cloudsql_proxy: bool | None = False
    cloudsql_proxy_port: int | None = None

    auth_token: SecretStr | None = None
    token_type: str = "Bearer"

    # SSL/TLS Configuration
    ssl_mode: str = "preferred"
    ssl_cert_path: str | None = None
    ssl_key_path: str | None = None
    ssl_ca_path: str | None = None
    ssl_verify_cert: bool = True
    ssl_ciphers: str | None = None
    tls_version: str = "TLSv1.2"

    connect_timeout: float | None = 30.0
    command_timeout: float | None = 30.0
    pool_timeout: float | None = 30.0

    def _build_ssl_params(self) -> dict[str, t.Any]:
        ssl_params = {}
        if self.ssl_enabled:
            ssl_params["ssl_mode"] = self.ssl_mode
            if self.ssl_cert_path:
                ssl_params["ssl_cert"] = self.ssl_cert_path
            if self.ssl_key_path:
                ssl_params["ssl_key"] = self.ssl_key_path
            if self.ssl_ca_path:
                ssl_params["ssl_ca"] = self.ssl_ca_path
            if self.ssl_ciphers:
                ssl_params["ssl_ciphers"] = self.ssl_ciphers
            ssl_params["ssl_verify_cert"] = str(self.ssl_verify_cert).lower()
            ssl_params["tls_version"] = self.tls_version
        if self.connect_timeout:
            ssl_params["connect_timeout"] = str(int(self.connect_timeout))

        return ssl_params

    @depends.inject
    def __init__(self, config: Inject[Config], **values: t.Any) -> None:
        super().__init__(**values)
        if self.cloudsql_proxy:
            self.port = self.cloudsql_proxy_port if not config.deployed else self.port
        self.poolclass = getattr(pool, self.poolclass) if self.poolclass else None
        ssl_params = self._build_ssl_params()
        self._url = URL.create(
            drivername=self._driver,
            username=str(self.user.get_secret_value()) if self.user else None,
            password=str(self.password.get_secret_value()) if self.password else None,
            host=self.local_host
            if not config.deployed
            else str(self.host.get_secret_value())
            if self.host
            else None,
            port=int(self.port) if self.port else None,
            database=str(config.app.name) if config.app else "default",
            query=ssl_params,
        )
        self._async_url = URL.create(
            drivername=self._async_driver,
            username=str(self.user.get_secret_value()) if self.user else None,
            password=str(self.password.get_secret_value()) if self.password else None,
            host=self.local_host
            if not config.deployed
            else str(self.host.get_secret_value())
            if self.host
            else None,
            port=int(self.port) if self.port else None,
            database=str(config.app.name) if config.app else "default",
            query=ssl_params,
        )
        self.engine_kwargs["echo"] = (
            "debug" if config.logger.verbose else getattr(config.debug, "sql", False)
        )
        self.engine_kwargs["echo_pool"] = (
            "debug" if config.logger.verbose else getattr(config.debug, "sql", False)
        )
        ssl_engine_kwargs = {}
        if self.ssl_enabled:
            ssl_engine_kwargs.update(ssl_params)
        if self.pool_timeout:
            ssl_engine_kwargs["pool_timeout"] = self.pool_timeout
        if self.command_timeout:
            ssl_engine_kwargs["connect_args"] = {
                "command_timeout": str(int(self.command_timeout)),
            }
        self.engine_kwargs = (
            {
                "poolclass": self.poolclass,
                "pool_pre_ping": self.pool_pre_ping,
            }
            | self.engine_kwargs
            | ssl_engine_kwargs
        )


class SqlProtocol(t.Protocol):
    def engine(self) -> AsyncEngine: ...

    def session(self) -> AsyncSession: ...

    def get_session(self) -> t.AsyncGenerator[AsyncSession]: ...

    async def init(self) -> None: ...


class SqlBase(AdapterBase, CleanupMixin):  # type: ignore[misc]
    def __init__(self, **kwargs: t.Any) -> None:
        super().__init__(**kwargs)
        self._engine: AsyncEngine | None = None
        self._session: AsyncSession | None = None

    async def _create_client(self) -> AsyncEngine:
        self.logger.debug(self.config.sql._async_url)
        if not database_exists(self.config.sql._url):
            self.logger.debug(self.config.sql._async_url)
            create_database(self.config.sql._url)
        return create_async_engine(
            self.config.sql._async_url,
            **self.config.sql.engine_kwargs,
        )

    async def get_engine(self) -> AsyncEngine:
        engine = await self._ensure_client()
        return t.cast("AsyncEngine", engine)  # type: ignore[no-any-return]

    @property
    def engine(self) -> AsyncEngine:
        if self._engine is None:
            msg = "Engine not initialized. Call get_engine() first."
            raise RuntimeError(msg)
        return self._engine

    async def _ensure_session(self) -> AsyncSession:
        if self._session is None:
            engine = await self.get_engine()
            self._session = AsyncSession(engine, expire_on_commit=False)
        return self._session

    @property
    def session(self) -> AsyncSession:
        if self._session is None:
            msg = "Session not initialized. Call _ensure_session() first."
            raise RuntimeError(msg)
        return self._session

    @asynccontextmanager
    async def get_session(self) -> t.AsyncGenerator[AsyncSession]:
        session = await self._ensure_session()
        async with session as sess:
            yield sess

    @asynccontextmanager
    async def get_conn(self) -> t.AsyncGenerator[AsyncConnection]:
        engine = await self.get_engine()
        async with engine.begin() as conn:
            yield conn

    async def _cleanup_resources(self) -> None:
        """Enhanced SQL resource cleanup."""
        errors = []

        # Clean up session first
        if self._session is not None:
            try:
                await self._session.close()
                self._session = None
                self.logger.debug("Successfully closed SQL session")
            except Exception as e:
                errors.append(f"Failed to close session: {e}")

        # Clean up engine
        if self._client is not None:  # Engine is stored in _client
            try:
                await self._client.dispose()
                self.logger.debug("Successfully disposed SQL engine")
            except Exception as e:
                errors.append(f"Failed to dispose engine: {e}")

        # Clear resource cache manually (parent functionality)
        self._resource_cache.clear()

        if errors:
            self.logger.warning(f"SQL resource cleanup errors: {'; '.join(errors)}")

    # Simplified SQL base - removed complex enterprise features
    # Core functionality remains in individual SQL adapters

    async def init(self) -> None:
        sqlalchemy_log._add_default_handler = lambda logger: None  # type: ignore[misc,assignment]
        async with self.get_conn() as conn:
            if getattr(self.config.debug, "sql", False):
                ps = await conn.execute(text("SHOW FULL PROCESSLIST"))
                show_ps = list(ps)
                debug(show_ps)
                ids = [
                    a[0]
                    for a in show_ps
                    if len(a) > 3
                    and a[1] == self.config.sql.user.get_secret_value()
                    and (a[3] == self.config.app.name if self.config.app else "")
                ]
                debug(ids)
            try:
                await conn.run_sync(SQLModel.metadata.drop_all)
                import_adapter("models")
                await conn.run_sync(SQLModel.metadata.create_all)
            except Exception as e:
                self.logger.exception(e)
                raise
