import typing as t

from acb.config import ac
from pydantic import SecretStr

from . import MonitoringBaseSettings
from . import MonitoringBase


class MonitoringSettings(MonitoringBaseSettings):
    enabled: bool = False
    dsn: t.Optional[SecretStr] = None
    sample_rate: float = 0.5

    def model_post_init(self, __context: t.Any) -> None:
        super().model_post_init(__context)
        self.sample_rate = self.sample_rate if ac.deployed else 1.0
        self.enabled = ac.deployed or not ac.debug.production
        self.dsn = ac.secres.sentry_dsn


class Monitoring(MonitoringBase):
    ...


monitoring: Monitoring = Monitoring()
