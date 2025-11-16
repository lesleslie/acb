from uuid import UUID

import typing as t
from pydantic import SecretStr, field_validator

try:
    from sentry_sdk import init as sentry_init
    from sentry_sdk.integrations.asyncio import AsyncioIntegration
    from sentry_sdk.integrations.gcp import GcpIntegration
except Exception:  # pragma: no cover - allow tests without sentry installed
    import os as _os
    import sys as _sys

    if "pytest" in _sys.modules or _os.getenv("TESTING", "False").lower() == "true":
        from unittest.mock import MagicMock

        sentry_init = MagicMock()  # type: ignore[assignment, no-redef]
        AsyncioIntegration = MagicMock  # type: ignore[assignment, no-redef]
        GcpIntegration = MagicMock  # type: ignore[assignment, no-redef]
    else:
        raise
from acb.adapters import AdapterCapability, AdapterMetadata, AdapterStatus
from acb.config import Config
from acb.depends import Inject, depends

from ._base import MonitoringBase, MonitoringBaseSettings

MODULE_ID = UUID("0197ff55-9026-7672-b2aa-b827edf29f46")
MODULE_STATUS = AdapterStatus.STABLE

MODULE_METADATA = AdapterMetadata(
    module_id=MODULE_ID,
    name="Sentry Monitoring",
    category="monitoring",
    provider="sentry",
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
    required_packages=["sentry-sdk[loguru]"],
    description="Sentry error tracking and performance monitoring",
    settings_class="MonitoringSettings",
    config_example={
        "sentry_dsn": "https://key@sentry.io/project",  # pragma: allowlist secret
        "sample_rate": 1.0,
        "debug": False,
        "profiles_sample_rate": 0.1,
    },
)


class MonitoringSettings(MonitoringBaseSettings):
    sentry_dsn: SecretStr = SecretStr("https://")
    sample_rate: float | None = 1.0
    debug: bool | None = False
    profiles_sample_rate: float | None = 0

    @field_validator("sample_rate", "profiles_sample_rate")
    @classmethod
    def check_sentry_sample_rates(cls, v: float) -> float:
        if v > 1 or v < 0:
            msg = "sample rate must be between 0 and 1"
            raise ValueError(msg)
        return v

    @depends.inject
    def __init__(self, config: Inject[Config], **values: t.Any) -> None:
        super().__init__(**values)
        if "sample_rate" not in values:
            self.sample_rate = self.sample_rate if config.deployed else 1.0


class Monitoring(MonitoringBase):
    async def init(self) -> None:
        sentry_init(
            dsn=self.config.monitoring.sentry_dsn.get_secret_value(),
            server_name=self.config.app.name if self.config.app else "unknown",
            release=self.config.app.version if self.config.app else "unknown",
            environment="development" if not self.config.deployed else "production",
            sample_rate=self.config.monitoring.sample_rate,
            debug=self.config.monitoring.debug,
            traces_sample_rate=self.config.monitoring.traces_sample_rate,
            profiles_sample_rate=self.config.monitoring.profiles_sample_rate,
            integrations=[GcpIntegration(), AsyncioIntegration()],
        )


depends.set(Monitoring, "sentry")
