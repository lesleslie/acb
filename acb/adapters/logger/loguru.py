import logging
import sys
import typing as t

from acb.config import Config
from acb.depends import depends
from loguru import logger as _logger
from loguru._logger import Core as _Core
from loguru._logger import Logger as _Logger
from ._base import LoggerBaseSettings


class LoggerSettings(LoggerBaseSettings):
    format: dict[str, str] = dict(
        time="<b><e>[</e> <w>{time:YYYY-MM-DD HH:mm:ss.SSS}</w> <e>]</e></b>",
        level=" <level>{level:>8}</level>",
        sep=" <b><w>in</w></b> ",
        name="{name:>24}",
        line="<b><e>[</e><w>{line:^5}</w><e>]</e></b>",
        message="  <level>{message}</level>",
    )
    level_per_module: t.Optional[dict[str, str]] = None
    serialize: t.Optional[bool] = False

    @depends.inject
    def model_post_init(self, __context: t.Any, config: Config = depends()) -> None:
        self.level_per_module: dict[str, str] = (
            {
                m: "DEBUG" if v is True else "INFO"
                for (m, v) in config.debug.model_dump().items()
            }
            if not config.deployed
            else "ERROR"
        )


class InterceptHandler(logging.Handler):
    def __init__(self, logger_name: str) -> None:
        super().__init__()
        self.logger_name = logger_name

    def emit(self, record: logging.LogRecord) -> None:
        try:
            level = _logger.level(record.levelname).name
        except ValueError:
            level = record.levelno
        frame, depth = logging.currentframe(), 2
        while frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1
        (
            _logger.patch(
                lambda record: record.update(name=self.logger_name)  # type: ignore
            )
            .opt(
                depth=depth,
                exception=record.exc_info,
            )
            .log(level, record.getMessage())
        )


class Logger(_Logger):
    config: Config = depends()
    settings: t.Optional[dict[str, t.Any]] = None

    def __init__(self):
        super().__init__(
            core=_Core(),
            exception=None,
            depth=0,
            record=False,
            lazy=False,
            colors=False,
            raw=False,
            capture=True,
            patchers=[],
            extra={},
        )

    async def init(self):
        self.remove()
        self.settings = dict(
            filter=self.config.logger.level_per_module,
            format="".join(self.config.logger.format.values()),
            enqueue=True,
            backtrace=True,
            serialize=self.config.logger.serialize,
        )
        self.add(sys.stderr, **self.settings)

        for log in self.config.logger.loggers:
            _log = logging.getLogger(log)
            _log.handlers.clear()
            _log.handlers = [InterceptHandler(log.name)]

        self.info("Logger initialized")

        if self.config.debug.logger:
            self.debug("debug")
            self.info("info")
            self.warning("warning")
            self.error("error")
            self.critical("critical")


depends.set(Logger, Logger())
