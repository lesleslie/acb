import typing as t
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from uuid import UUID

from pydantic import SecretStr, field_validator
from sqlalchemy import text
from sqlalchemy.engine import URL
from acb.adapters import AdapterStatus
from acb.depends import depends

from ._base import SqlBase, SqlBaseSettings

MODULE_ID = UUID("0197ff44-e1b4-7f50-b8e1-4c7d8a6f329e")
MODULE_STATUS = AdapterStatus.STABLE


class SqlSettings(SqlBaseSettings):
    database_url: str = "sqlite:///data/app.db"
    _driver: str = "sqlite+pysqlite"
    _async_driver: str = "sqlite+aiosqlite"
    auth_token: SecretStr | None = None
    wal_mode: bool = True

    port: int | None = None
    host: SecretStr | None = None  # type: ignore[assignment]
    user: SecretStr | None = None  # type: ignore[assignment]
    password: SecretStr | None = None  # type: ignore[assignment]

    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, v: str) -> str:
        if not v.startswith(("sqlite://", "sqlite+", "libsql://", "https://")):
            msg = "Database URL must start with sqlite://, sqlite+, libsql://, or https://"
            raise ValueError(
                msg,
            )
        return v

    def __init__(self, config: t.Any | None = None, **values: t.Any) -> None:
        if config is not None:
            super().__init__(config, **values)
        else:
            from pydantic import BaseModel

            BaseModel.__init__(self, **values)
            self.engine_kwargs = {}
        self._setup_drivers()
        self._setup_urls()

    def _setup_drivers(self) -> None:
        if self._is_turso_url():
            self._driver = "sqlite+libsql"
            self._async_driver = "sqlite+libsql"
        else:
            self._driver = "sqlite+pysqlite"
            self._async_driver = "sqlite+aiosqlite"

    def _is_turso_url(self) -> bool:
        return (
            self.database_url.startswith(("libsql://", "https://"))
            or "turso" in self.database_url
            or "authToken" in self.database_url
        )

    def _setup_urls(self) -> None:
        if self._is_turso_url():
            self._setup_turso_urls()
        else:
            self._setup_local_urls()

    def _setup_turso_urls(self) -> None:
        parsed = urlparse(self.database_url)
        query_params = parse_qs(parsed.query)
        auth_token = None
        if "authToken" in query_params:
            auth_token = query_params["authToken"][0]
        elif self.auth_token:
            auth_token = self.auth_token.get_secret_value()
        if parsed.scheme == "https":
            base_url = f"sqlite+libsql://{parsed.netloc}{parsed.path}"
        else:
            base_url = self.database_url.replace("libsql://", "sqlite+libsql://")
        query_string = ""
        if auth_token:
            query_string = f"?authToken={auth_token}"
            if "secure" in query_params or "secure=true" in self.database_url:
                query_string += "&secure=true"
        final_url = base_url + query_string
        from sqlalchemy.engine.url import make_url

        self._url = make_url(final_url)
        self._async_url = make_url(final_url)

    def _setup_local_urls(self) -> None:
        if self.database_url.startswith("sqlite:///"):
            db_path = self.database_url[10:]
        else:
            db_path = self.database_url
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        query_params = {}
        if self.wal_mode:
            query_params["journal_mode"] = "WAL"
        self._url = URL.create(
            drivername=self._driver,
            database=db_path,
            query=query_params,
        )
        self._async_url = URL.create(
            drivername=self._async_driver,
            database=db_path,
            query=query_params,
        )

    @property
    def driver(self) -> str:
        return self._driver

    @property
    def async_driver(self) -> str:
        return self._async_driver

    @property
    def is_turso(self) -> bool:
        return self._is_turso_url()


class Sql(SqlBase):
    async def _create_client(self) -> t.Any:
        self.logger.debug(self.config.sql._async_url)
        if not self.config.sql.is_turso:
            db_path = Path(self.config.sql.database_url.replace("sqlite:///", ""))
            if not db_path.parent.exists():
                db_path.parent.mkdir(parents=True, exist_ok=True)
        from sqlalchemy.ext.asyncio import create_async_engine

        engine = create_async_engine(
            self.config.sql._async_url,
            **self.config.sql.engine_kwargs,
        )
        if not self.config.sql.is_turso and self.config.sql.wal_mode:
            async with engine.begin() as conn:
                await conn.execute(text("PRAGMA journal_mode=WAL"))

        return engine

    async def init(self) -> None:
        from sqlalchemy import log as sqlalchemy_log
        from sqlmodel import SQLModel
        from acb.adapters import import_adapter

        sqlalchemy_log._add_default_handler = lambda _: None
        async with self.get_conn() as conn:
            if getattr(self.config.debug, "sql", False):
                if not self.config.sql.is_turso:
                    pragma_result = await conn.execute(text("PRAGMA journal_mode"))
                    journal_mode = pragma_result.scalar()
                    self.logger.debug(f"SQLite journal mode: {journal_mode}")
            try:
                await conn.run_sync(SQLModel.metadata.drop_all)
                import_adapter("models")
                await conn.run_sync(SQLModel.metadata.create_all)
            except Exception as e:
                self.logger.exception(e)
                raise


depends.set(Sql)
