from pydantic import field_validator
from acb.config import AdapterBase, Settings


class MonitoringBaseSettings(Settings):
    traces_sample_rate: float = 0

    @field_validator("traces_sample_rate")
    @classmethod
    def check_traces_sample_rate(cls, v: float) -> float:
        del cls
        if v > 1 or v < 0:
            raise ValueError("sample rate must be between 0 and 1")
        return v


class MonitoringBase(AdapterBase): ...
