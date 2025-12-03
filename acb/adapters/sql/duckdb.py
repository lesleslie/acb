"""DuckDB SQL adapter implementation."""

from __future__ import annotations

from pathlib import Path
from uuid import UUID

import typing as t
from pydantic import Field, SecretStr, field_validator
from sqlalchemy import text
from sqlalchemy.engine.url import make_url
from sqlalchemy.pool import NullPool

from acb.adapters import AdapterCapability, AdapterMetadata, AdapterStatus
from acb.depends import depends

from ._base import SqlBase, SqlBaseSettings

if t.TYPE_CHECKING:
    from sqlalchemy.engine import URL

MODULE_ID = UUID("019a1b1a-7a1a-76d7-8d8b-9b1f8f7d6c0e")
MODULE_STATUS = AdapterStatus.BETA

MODULE_METADATA = AdapterMetadata(
    module_id=MODULE_ID,
    name="DuckDB",
    category="sql",
    provider="duckdb",
    version="0.1.0",
    acb_min_version="0.19.0",
    author="lesleslie <les@wedgwoodwebworks.com>",
    created_date="2025-02-15",
    last_modified="2025-02-15",
    status=MODULE_STATUS,
    capabilities=[
        AdapterCapability.ASYNC_OPERATIONS,
        AdapterCapability.TRANSACTIONS,
        AdapterCapability.BULK_OPERATIONS,
        AdapterCapability.SCHEMA_VALIDATION,
        AdapterCapability.MIGRATIONS,
    ],
    required_packages=[
        "duckdb",
        "duckdb-engine",
        "sqlalchemy",
        "sqlmodel",
    ],
    optional_packages={
        "duckdb-engine[arrow]": "Enable Arrow-based fast paths for analytics workloads",
    },
    description=(
        "DuckDB adapter optimized for analytical workloads, in-memory processing, "
        "and on-disk columnar databases."
    ),
    settings_class="SqlSettings",
    config_example={
        "database_url": "duckdb:///data/warehouse.duckdb",
        "threads": 4,
        "extensions": ["httpfs", "postgres_scanner"],
        "pragmas": {"memory_limit": "4GB"},
    },
)


class SqlSettings(SqlBaseSettings):
    """DuckDB-specific SQL settings."""

    database_url: str = "duckdb:///data/app.duckdb"
    _driver: str = "duckdb"
    _async_driver: str = "duckdb+async"

    read_only: bool = False
    threads: int | None = None
    pragmas: dict[str, str] = Field(default_factory=dict)
    extensions: list[str] = Field(default_factory=list)
    temp_directory: str | None = None

    port: int | None = None
    host: SecretStr | None = None  # type: ignore[assignment]
    user: SecretStr | None = None  # type: ignore[assignment]
    password: SecretStr | None = None  # type: ignore[assignment]

    _url: URL | None = None
    _async_url: URL | None = None

    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, value: str) -> str:
        if not value.startswith(("duckdb://", "duckdb+async://")):
            msg = "Database URL must start with duckdb:// or duckdb+async://"
            raise ValueError(msg)
        return value

    def __init__(self, config: t.Any | None = None, **values: t.Any) -> None:
        # When instantiated via DI the config is injected automatically.
        if config is not None:
            super().__init__(**values)
        else:
            from pydantic import BaseModel

            BaseModel.__init__(self, **values)
            self.engine_kwargs = {}

        self._initialise_urls()
        self._configure_engine_kwargs()

    def _initialise_urls(self) -> None:
        """Normalise URLs for sync and async engines."""
        raw_url = make_url(self.database_url)
        # Ensure directories exist for on-disk databases.
        if raw_url.database and raw_url.database != ":memory:":
            db_path = Path(raw_url.database)
            if not db_path.parent.exists():
                db_path.parent.mkdir(parents=True, exist_ok=True)

        query = dict(raw_url.query)
        if self.read_only:
            query.setdefault("read_only", "true")
        if self.temp_directory:
            query.setdefault("temp_directory", self.temp_directory)

        sync_driver = self._driver
        async_driver = self._async_driver

        self._url = raw_url.set(drivername=sync_driver, query=query)
        async_query = query.copy()
        if self.threads is not None:
            async_query.setdefault("threads", str(self.threads))
        self._async_url = raw_url.set(drivername=async_driver, query=async_query)

    def _configure_engine_kwargs(self) -> None:
        """Configure SQLAlchemy engine keyword arguments."""
        self.engine_kwargs["poolclass"] = NullPool
        self.engine_kwargs.setdefault("pool_pre_ping", False)
        connect_args = dict(self.engine_kwargs.get("connect_args", {}))
        if self.read_only:
            connect_args.setdefault("read_only", True)
        if self.threads is not None:
            connect_args.setdefault("threads", self.threads)
        if self.temp_directory:
            connect_args.setdefault("temp_directory", self.temp_directory)
        if connect_args:
            self.engine_kwargs["connect_args"] = connect_args

    @property
    def driver(self) -> str:
        return self._driver

    @property
    def async_driver(self) -> str:
        return self._async_driver

    @property
    def database_path(self) -> Path | None:
        if not self._url or not self._url.database or self._url.database == ":memory:":
            return None
        return Path(self._url.database)


class Sql(SqlBase):
    """DuckDB adapter implementation."""

    async def _set_threads(self, conn: t.Any) -> None:
        if self.config.sql.threads is None:
            return
        threads = int(self.config.sql.threads)
        await conn.execute(text(f"PRAGMA threads={threads}"))

    async def _apply_pragmas(self, conn: t.Any) -> None:
        if not self.config.sql.pragmas:
            return
        for pragma, value in self.config.sql.pragmas.items():
            value_str = value if isinstance(value, str) else str(value)
            numeric_check = value_str.lstrip("-+").replace(".", "", 1).isdigit()
            if isinstance(value, (int, float)) or numeric_check:
                clause = value_str
            else:
                escaped = value_str.replace("'", "''")
                clause = f"'{escaped}'"
            await conn.execute(text(f"PRAGMA {pragma}={clause}"))

    async def _install_extensions(self, conn: t.Any) -> None:
        if not self.config.sql.extensions or self.config.sql.read_only:
            return
        for extension in self.config.sql.extensions:
            safe_ext = extension.replace('"', "").replace("'", "")
            await conn.execute(text(f"INSTALL {safe_ext}"))
            await conn.execute(text(f"LOAD {safe_ext}"))

    async def _set_temp_directory(self, conn: t.Any) -> None:
        if not self.config.sql.temp_directory:
            return
        await conn.execute(
            text("SET temp_directory=:temp_directory").bindparams(
                temp_directory=self.config.sql.temp_directory,
            ),
        )

    async def _create_client(self) -> t.Any:
        from sqlalchemy.ext.asyncio import create_async_engine

        engine = create_async_engine(
            self.config.sql._async_url,
            **self.config.sql.engine_kwargs,
        )

        async with engine.begin() as conn:
            await self._set_threads(conn)
            await self._apply_pragmas(conn)
            await self._install_extensions(conn)
            await self._set_temp_directory(conn)

        return engine

    async def init(self) -> None:
        from sqlalchemy import log as sqlalchemy_log
        from sqlmodel import SQLModel

        from acb.adapters import import_adapter

        if self.config.sql.read_only:
            self.logger.info(
                "DuckDB adapter running in read-only mode; skipping schema sync",
            )
            return

        sqlalchemy_log._add_default_handler = lambda logger: None  # type: ignore[assignment,misc]
        self.logger.info("Initializing DuckDB connection")
        async with self.get_conn() as conn:
            try:
                # Drop and recreate schema to align with current models
                await conn.run_sync(SQLModel.metadata.drop_all)
                import_adapter("models")
                await conn.run_sync(SQLModel.metadata.create_all)
                self.logger.info("DuckDB schema synchronized successfully")
            except Exception as exc:  # pragma: no cover - propagated upstream
                self.logger.exception(exc)
                raise


depends.set(Sql, "duckdb")
