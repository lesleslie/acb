from uuid import UUID

from typing import TYPE_CHECKING

try:
    from logfire import (
        configure,
        instrument_httpx,
        instrument_pydantic,
        instrument_redis,
        instrument_sqlalchemy,
        instrument_system_metrics,
        loguru_handler,
    )
except Exception:  # pragma: no cover - allow tests without logfire deps
    import os as _os
    import sys as _sys

    if "pytest" in _sys.modules or _os.getenv("TESTING", "False").lower() == "true":
        from unittest.mock import MagicMock

        configure = MagicMock()  # type: ignore[assignment]
        instrument_httpx = MagicMock()  # type: ignore[assignment]
        instrument_pydantic = MagicMock()  # type: ignore[assignment]
        instrument_redis = MagicMock()  # type: ignore[assignment]
        instrument_sqlalchemy = MagicMock()  # type: ignore[assignment]
        instrument_system_metrics = MagicMock()  # type: ignore[assignment]
        loguru_handler = MagicMock()  # type: ignore[assignment]
    else:
        raise
from pydantic import SecretStr

from acb.adapters import (
    AdapterCapability,
    AdapterMetadata,
    AdapterStatus,
    get_installed_adapters,
)
from acb.depends import depends

from ._base import MonitoringBase, MonitoringBaseSettings

if TYPE_CHECKING:
    from acb.adapters.sql._base import SqlBase

MODULE_ID = UUID("0197ff55-9026-7672-b2aa-b81656dc7888")
MODULE_STATUS = AdapterStatus.STABLE

MODULE_METADATA = AdapterMetadata(
    module_id=MODULE_ID,
    name="Logfire Monitoring",
    category="monitoring",
    provider="logfire",
    version="1.0.0",
    acb_min_version="0.18.0",
    author="lesleslie <les@wedgwoodwebworks.com>",
    created_date="2025-01-12",
    last_modified="2025-01-20",
    status=MODULE_STATUS,
    capabilities=[
        AdapterCapability.ASYNC_OPERATIONS,
        AdapterCapability.METRICS,
        AdapterCapability.TRACING,
        AdapterCapability.LOGGING,
    ],
    required_packages=["logfire[system-metrics]"],
    description="Logfire observability with auto-instrumentation",
    settings_class="MonitoringSettings",
    config_example={
        "logfire_token": "your-logfire-token",  # pragma: allowlist secret
    },
)


class MonitoringSettings(MonitoringBaseSettings):
    logfire_token: SecretStr = SecretStr("secret")


class Monitoring(MonitoringBase):
    async def init(self) -> None:
        configure(
            token=self.config.monitoring.logfire_token.get_secret_value(),
            service_name=self.config.app.name if self.config.app else "unknown",
            service_version=self.config.app.version if self.config.app else "unknown",
        )
        instrument_pydantic(record="all")
        for adapter in [a.name for a in get_installed_adapters()]:
            match adapter:
                case "loguru":
                    from loguru import logger

                    logger.configure(handlers=[loguru_handler()])
                case "httpx":
                    instrument_httpx()
                case "redis":
                    instrument_redis()
                case "sqlalchemy":
                    sql: SqlBase = depends.get_sync(category="sql")
                    instrument_sqlalchemy(engine=sql.engine)
                case _:
                    pass
        instrument_system_metrics()


depends.set(Monitoring, "logfire")
