import logging
import sys
import typing as t

from acb import adapter_registry
from acb.config import Config
from acb.config import debug
from acb.depends import depends
from loguru._logger import Core as _Core
from loguru._logger import Logger as _Logger
from ._base import ExternalLogger
from ._base import LoggerBase
from ._base import LoggerBaseSettings


class LoggerSettings(LoggerBaseSettings):
    serialize: t.Optional[bool] = False
    format: t.Optional[dict[str, str]] = dict(
        time="<b><e>[</e> <w>{time:YYYY-MM-DD HH:mm:ss.SSS}</w> <e>]</e></b>",
        level=" <level>{level:>8}</level>",
        sep=" <b><w>in</w></b> ",
        name="{extra[mod_name]:>24}",
        line="<b><e>[</e><w>{line:^5}</w><e>]</e></b>",
        message="  <level>{message}</level>",
    )
    level_per_module: t.Optional[dict[str, str]] = {}
    settings: t.Optional[dict[str, t.Any]] = {}

    @depends.inject
    def __init__(self, **values: t.Any) -> None:
        super().__init__(**values)
        self.level_per_module = {m: "DEBUG" if v else "INFO" for m, v in debug.items()}
        self.settings = dict(
            filter=self.level_per_module,
            format="".join(self.format.values()),
            enqueue=True,
            backtrace=True,
            serialize=self.serialize,
        )


class Logger(_Logger, LoggerBase):
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
        def patch_name(record) -> str:  # type: ignore
            mod_parts = record["name"].split(".")
            mod_name = ".".join(mod_parts)
            if len(mod_name) > 3:
                mod_name = ".".join(mod_parts[:-1])
            return mod_name

        self.remove()
        self.configure(
            patcher=lambda record: record["extra"].update(  # type: ignore
                mod_name=patch_name(record)
            )
        )
        self.add(sys.stderr, **config.logger.settings)
        if config.deployed:
            self.level = config.logger.deployed_level
        if config.debug.logger:
            self.debug("debug")
            self.info("info")
            self.warning("warning")
            self.error("error")
            self.critical("critical")

    @staticmethod
    @depends.inject
    def register_external_loggers(
        loggers: list[ExternalLogger], config: Config = depends()
    ) -> None:
        for external_logger in loggers:
            _logger = logging.getLogger(external_logger.name)
            _logger.handlers.clear()
            _logger.handlers = [InterceptHandler(_logger.name)]
            config.logger.external_loggers.append(external_logger)


depends.set(Logger)


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
            enabled_logger = next(
                (
                    a
                    for a in adapter_registry.get()
                    if a.category == "logger" and a.enabled
                ),
            )
            if enabled_logger and enabled_logger.name == "loguru":
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
