import typing as t

from acb.adapters import AdapterBase
from acb.config import Settings


class MonitoringBaseSettings(Settings):
    traces_sample_rate: t.Optional[float] = 0


class MonitoringBase(AdapterBase): ...
