from uuid import UUID

import typing as t

from acb.adapters import AdapterCapability, AdapterMetadata, AdapterStatus
from acb.config import Config
from acb.depends import Inject, depends

from ._base import SqlBase, SqlBaseSettings

MODULE_ID = UUID("0197ff44-c5a3-7040-8d7e-3b17c8e54691")
MODULE_STATUS = AdapterStatus.STABLE

MODULE_METADATA = AdapterMetadata(
    module_id=MODULE_ID,
    name="MySQL",
    category="sql",
    provider="mysql",
    version="1.1.0",
    acb_min_version="0.18.0",
    author="lesleslie <les@wedgwoodwebworks.com>",
    created_date="2025-01-12",
    last_modified="2025-01-15",
    status=MODULE_STATUS,
    capabilities=[
        AdapterCapability.ASYNC_OPERATIONS,
        AdapterCapability.CONNECTION_POOLING,
        AdapterCapability.TRANSACTIONS,
        AdapterCapability.TLS_SUPPORT,
        AdapterCapability.BULK_OPERATIONS,
        AdapterCapability.SCHEMA_VALIDATION,
        AdapterCapability.MIGRATIONS,
    ],
    required_packages=["PyMySQL", "aiomysql", "sqlalchemy", "sqlmodel"],
    description="MySQL SQL adapter with comprehensive SSL/TLS support",
    settings_class="SqlSettings",
    config_example={
        "host": "localhost",
        "port": 3306,
        "user": "admin",
        "password": "your-db-password",  # pragma: allowlist secret
        "ssl_enabled": True,
        "ssl_mode": "required",
        "ssl_cert_path": "/path/to/cert.pem",
        "ssl_key_path": "/path/to/key.pem",
        "ssl_ca_path": "/path/to/ca.pem",
    },
)


class SqlSettings(SqlBaseSettings):
    _driver: str = "mysql+pymysql"
    _async_driver: str = "mysql+aiomysql"
    pool_size: int = 20
    max_overflow: int = 30
    pool_recycle: int = 3600
    pool_pre_ping: bool | None = True

    @property
    def driver(self) -> str:
        return self._driver

    @property
    def async_driver(self) -> str:
        return self._async_driver

    def _build_ssl_params(self) -> dict[str, t.Any]:
        """Build SSL params using unified SSL configuration."""
        ssl_config = self._get_ssl_config()
        return dict(ssl_config.to_mysql_kwargs())

    @depends.inject
    def __init__(self, config: Inject[Config], **values: t.Any) -> None:
        super().__init__(**values)
        mysql_ssl_params = self._build_ssl_params()
        if mysql_ssl_params:
            connect_args = self.engine_kwargs.get("connect_args", {})
            connect_args.update(mysql_ssl_params)
            self.engine_kwargs["connect_args"] = connect_args
        self.engine_kwargs.update(
            {
                "pool_size": self.pool_size,
                "max_overflow": self.max_overflow,
                "pool_recycle": self.pool_recycle,
            },
        )


class Sql(SqlBase): ...


depends.set(Sql, "mysql")
