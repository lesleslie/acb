import typing as t

from pydantic import SecretStr, field_validator
from sentry_sdk import init as sentry_init
from sentry_sdk.integrations.asyncio import AsyncioIntegration
from sentry_sdk.integrations.gcp import GcpIntegration
from acb.config import Config
from acb.depends import depends
from ._base import MonitoringBase, MonitoringBaseSettings


class MonitoringSettings(MonitoringBaseSettings):
    sentry_dsn: SecretStr = SecretStr("https://")
    sample_rate: t.Optional[float] = 1.0
    debug: t.Optional[bool] = False
    profiles_sample_rate: t.Optional[float] = 0

    @field_validator("sample_rate", "profiles_sample_rate")
    @classmethod
    def check_sentry_sample_rates(cls, v: float) -> float:  # noqa: F841
        if v > 1 or v < 0:
            raise ValueError("sample rate must be between 0 and 1")
        return v

    @depends.inject
    def __init__(self, config: Config = depends(), **values: t.Any) -> None:
        super().__init__(**values)
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
            integrations=[
                GcpIntegration(),
                AsyncioIntegration(),
            ],
        )


depends.set(Monitoring)
