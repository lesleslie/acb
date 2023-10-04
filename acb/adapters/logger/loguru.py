import logging
import sys
import typing as t

from acb.config import Config
from acb.config import enabled_adapters
from acb.config import logger_registry
from acb.depends import depends
from loguru._logger import Core as _Core
from loguru._logger import Logger as _Logger
from ._base import LoggerBaseSettings


class LoggerSettings(LoggerBaseSettings):
    serialize: t.Optional[bool] = False
    format: t.Optional[dict[str, str]] = dict(
        time="<b><e>[</e> <w>{time:YYYY-MM-DD HH:mm:ss.SSS}</w> <e>]</e></b>",
        level=" <level>{level:>8}</level>",
        sep=" <b><w>in</w></b> ",
        name="{name:>28}",
        line="<b><e>[</e><w>{line:^5}</w><e>]</e></b>",
        message="  <level>{message}</level>",
    )
    level_per_module: t.Optional[dict[str, str]] = {}
    settings: t.Optional[dict[str, t.Any]] = {}

    @depends.inject
    def __init__(self, config: Config = depends(), **values: t.Any) -> None:
        super().__init__(**values)
        self.level_per_module = {
            m: "DEBUG" if v is True else "INFO"
            for (m, v) in config.debug.model_dump().items()
        }
        self.settings = dict(
            filter=self.level_per_module,
            format="".join(self.format.values()),
            enqueue=True,
            backtrace=True,
            serialize=self.serialize,
        )


class Logger(_Logger):
    def __init__(self) -> None:
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

    @depends.inject
    async def init(self, config: Config = depends()) -> None:
        # def patching(record) -> None:  # type: ignore
        #     record["extra"]["mod_name"] = ".".join(record["name"].split(".")[0:-1])

        self.remove()
        # self.patch(patching)
        self.add(sys.stderr, **config.logger.settings)
        if config.deployed:
            self.level = config.logger.deployed_level
        self.info("Logger adapter loaded")
        if config.debug.logger:
            self.debug("debug")
            self.info("info")
            self.warning("warning")
            self.error("error")
            self.critical("critical")


depends.set(Logger, Logger())


class InterceptHandler(logging.Handler):
    def __init__(self, logger_name: str) -> None:
        super().__init__()
        self.logger_name = logger_name

    @depends.inject
    def emit(
        self, record: logging.LogRecord, logger: Logger = depends()  # type: ignore
    ) -> None:
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno
        frame, depth = logging.currentframe(), 2
        while frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1
            enabled_logger = enabled_adapters.get()["logger"]
            if enabled_logger == "loguru":
                logger.patch(
                    lambda record: record.update(name=self.logger_name)  # type: ignore
                ).opt(
                    depth=depth,
                    exception=record.exc_info,
                ).log(
                    level, record.getMessage()
                )
            # elif enabled_logger == "structlog":
            #     ...


def register_loggers(loggers: list[str]) -> None:
    for logger in loggers:
        _logger = logging.getLogger(logger)
        _logger.handlers.clear()
        _logger.handlers = [InterceptHandler(_logger.name)]
    return logger_registry.get().update(loggers)
