import typing as t

from acb.config import Config
from acb.depends import depends
from pydantic import SecretStr
from ._base import MonitoringBase
from ._base import MonitoringBaseSettings


class MonitoringSettings(MonitoringBaseSettings):
    enabled: bool = False
    dsn: t.Optional[SecretStr] = None
    sample_rate: float = 0.5

    @depends.inject
    def __init__(self, config: Config = depends(), **values: t.Any) -> None:
        super().__init__(**values)
        self.sample_rate = self.sample_rate if config.deployed else 1.0
        self.enabled = config.deployed or not config.debug.production
        self.dsn = config.secrets.sentry_dsn


class Monitoring(MonitoringBase): ...


depends.set(Monitoring)
