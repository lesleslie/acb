from pathlib import Path
from urllib.parse import parse_qs, urlparse
from uuid import UUID

import typing as t
from pydantic import SecretStr, field_validator
from sqlalchemy import text
from sqlalchemy.engine import URL

from acb.adapters import AdapterCapability, AdapterMetadata, AdapterStatus
from acb.depends import depends

from ._base import SqlBase, SqlBaseSettings

MODULE_ID = UUID("0197ff44-e1b4-7f50-b8e1-4c7d8a6f329e")
MODULE_STATUS = AdapterStatus.STABLE

MODULE_METADATA = AdapterMetadata(
    module_id=MODULE_ID,
    name="SQLite",
    category="sql",
    provider="sqlite",
    version="1.1.0",
    acb_min_version="0.18.0",
    author="lesleslie <les@wedgwoodwebworks.com>",
    created_date="2025-01-12",
    last_modified="2025-01-15",
    status=MODULE_STATUS,
    capabilities=[
        AdapterCapability.ASYNC_OPERATIONS,
        AdapterCapability.TRANSACTIONS,
        AdapterCapability.TLS_SUPPORT,
        AdapterCapability.BULK_OPERATIONS,
        AdapterCapability.SCHEMA_VALIDATION,
        AdapterCapability.MIGRATIONS,
    ],
    required_packages=["aiosqlite", "sqlalchemy", "sqlmodel"],
    optional_packages={"libsql": "For Turso remote SQLite with TLS support"},
    description="SQLite adapter with Turso TLS support for remote connections",
    settings_class="SqlSettings",
    config_example={
        "database_url": "sqlite:///data/app.db",
        "ssl_enabled": True,
        "auth_token": "your-turso-token",
    },
)


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
            super().__init__(**values)
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
        query_params_list = []
        if auth_token:
            query_params_list.append(f"authToken={auth_token}")
        if (
            self.ssl_enabled
            or "secure" in query_params
            or "secure=true" in self.database_url
        ):
            query_params_list.append("secure=true")
        if self.tls_version and self.tls_version != "TLSv1.2":
            query_params_list.append(f"tls_version={self.tls_version}")
        if self.connect_timeout:
            query_params_list.append(f"connect_timeout={int(self.connect_timeout)}")
        query_string = ""
        if query_params_list:
            query_string = "?" + "&".join(query_params_list)
        final_url = base_url + query_string
        from sqlalchemy.engine.url import make_url

        self._url = make_url(final_url)
        self._async_url = make_url(final_url)

    def _setup_local_urls(self) -> None:
        # Extract database path, handling various URL formats
        if ":///" in self.database_url:
            # Handle sqlite:/// or sqlite+driver:/// formats
            db_path = self.database_url.split(":///", 1)[1]
        elif "://" in self.database_url:
            # Handle sqlite:// format
            db_path = self.database_url.split("://", 1)[1]
        else:
            # Plain path
            db_path = self.database_url

        # Only create directories for actual file paths
        # Skip :memory:, empty paths, and paths that look like driver names
        should_create_dir = (
            db_path
            and db_path != ":memory:"
            and not db_path.endswith(":")
            and ("/" in db_path or "\\" in db_path)
            and not db_path.startswith("sqlite+")  # Don't create dirs for driver names
        )

        if should_create_dir:
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
            # Extract database path properly
            db_url = self.config.sql.database_url
            if ":///" in db_url:
                db_path_str = db_url.split(":///", 1)[1]
            elif "://" in db_url:
                db_path_str = db_url.split("://", 1)[1]
            else:
                db_path_str = db_url

            # Only create directory for valid file paths
            if (
                db_path_str
                and db_path_str != ":memory:"
                and not db_path_str.startswith("sqlite+")
                and ("/" in db_path_str or "\\" in db_path_str)
            ):
                db_path = Path(db_path_str)
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

        sqlalchemy_log._add_default_handler = lambda logger: None  # type: ignore[assignment,misc]
        if self.config.sql.is_turso:
            ssl_status = (
                "SSL enabled" if self.config.sql.ssl_enabled else "SSL disabled"
            )
            self.logger.info(f"Initializing Turso SQLite connection ({ssl_status})")
        else:
            self.logger.info("Initializing local SQLite connection")
        async with self.get_conn() as conn:
            if getattr(self.config.debug, "sql", False):
                if not self.config.sql.is_turso:
                    pragma_result = await conn.execute(text("PRAGMA journal_mode"))
                    journal_mode = pragma_result.scalar()
                    self.logger.debug(f"SQLite journal mode: {journal_mode}")
                else:
                    self.logger.debug(
                        f"Turso connection URL: {self.config.sql._async_url}",
                    )
            try:
                await conn.run_sync(SQLModel.metadata.drop_all)
                import_adapter("models")
                await conn.run_sync(SQLModel.metadata.create_all)
                self.logger.info("SQLite connection initialized successfully")
            except Exception as e:
                self.logger.exception(e)
                raise


depends.set(Sql, "sqlite")
