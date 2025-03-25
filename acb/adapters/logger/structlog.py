from acb.depends import depends

from .loguru import Logger as LoguruLogger
from .loguru import LoggerSettings as LoguruSettings


class LoggerSettings(LoguruSettings):
    serialize: bool | None = True


class Logger(LoguruLogger): ...


depends.set(Logger)
