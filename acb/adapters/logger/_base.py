import typing as t

from acb.config import Settings


class LoggerBaseSettings(Settings):
    verbose: bool = False
    deployed_level: str = "WARNING"
    log_level: t.Optional[str] = "INFO"


class LoggerBase: ...
