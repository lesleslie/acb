import typing as t
from enum import Enum

from acb.config import Settings
from pydantic import BaseModel


class LoggerLevel(str, Enum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class ExternalLogger(BaseModel):
    name: str
    package: str
    module: str
    level: LoggerLevel = LoggerLevel.WARNING


class LoggerBaseSettings(Settings):
    verbose: bool = False
    deployed_level: str = "ERROR"
    external_loggers: t.Optional[list[ExternalLogger]] = []


class LoggerBase:
    ...
