import typing as t

from acb.config import ac
from pydantic import HttpUrl

from . import MonitoringBaseSettings


class MonitoringSettings(MonitoringBaseSettings):
    enabled: bool = ac.deployed or not ac.debug.production
    # dsn = "https://ea3f99402f144c2badf512c55d3d7bb7@o310698.ingest.sentry.io/1777286"
    dsn: HttpUrl
    sample_rate: int = 0.5

    def __init__(self, **values: t.Any) -> None:
        super().__init__(**values)
        self.sample_rate = self.sample_rate if ac.deployed else 1.0
