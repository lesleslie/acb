import typing as t

from acb.config import Config
from pydantic import SecretStr
from acb.depends import depends

from ._base import MonitoringBaseSettings
from ._base import MonitoringBase


class MonitoringSettings(MonitoringBaseSettings):
    enabled: bool = False
    dsn: t.Optional[SecretStr] = None
    sample_rate: float = 0.5

    @depends.inject
    def model_post_init(self, __context: t.Any, config: Config = depends()) -> None:
        super().model_post_init(__context)
        self.sample_rate = self.sample_rate if self.config.deployed else 1.0
        self.enabled = self.config.deployed or not self.config.debug.production
        self.dsn = self.config.secres.sentry_dsn


class Monitoring(MonitoringBase):
    ...


monitoring: Monitoring = Monitoring()
