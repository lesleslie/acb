import typing as t
from uuid import UUID

from pydantic import SecretStr, field_validator
from sentry_sdk import init as sentry_init
from sentry_sdk.integrations.asyncio import AsyncioIntegration
from sentry_sdk.integrations.gcp import GcpIntegration
from acb.adapters import AdapterStatus
from acb.config import Config
from acb.depends import depends

from ._base import MonitoringBase, MonitoringBaseSettings

MODULE_ID = UUID("0197ff55-9026-7672-b2aa-b827edf29f46")
MODULE_STATUS = AdapterStatus.STABLE


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
    def __init__(self, config: Config = depends(), **values: t.Any) -> None:
        super().__init__(**values)
        if "sample_rate" not in values:
            self.sample_rate = self.sample_rate if config.deployed else 1.0


class Monitoring(MonitoringBase):
    async def init(self) -> None:
        sentry_init(
            dsn=self.config.monitoring.sentry_dsn.get_secret_value(),
            server_name=self.config.app.name,
            release=self.config.app.version,
            environment="development" if not self.config.deployed else "production",
            sample_rate=self.config.monitoring.sample_rate,
            debug=self.config.monitoring.debug,
            traces_sample_rate=self.config.monitoring.traces_sample_rate,
            profiles_sample_rate=self.config.monitoring.profiles_sample_rate,
            integrations=[GcpIntegration(), AsyncioIntegration()],
        )


depends.set(Monitoring)
