import logging
import sys
import typing as t
from inspect import currentframe

from acb.config import Config
from acb.config import debug
from acb.depends import depends
from loguru._logger import Core as _Core
from loguru._logger import Logger as _Logger
from ._base import LoggerBase
from ._base import LoggerBaseSettings


class LoggerSettings(LoggerBaseSettings):
    serialize: t.Optional[bool] = False
    format: t.Optional[dict[str, str]] = dict(
        time="<b><e>[</e> <w>{time:YYYY-MM-DD HH:mm:ss.SSS}</w> <e>]</e></b>",
        level=" <level>{level:>8}</level>",
        sep=" <b><w>in</w></b> ",
        name="<b>{extra[mod_name]:>18}</b>",
        line="<b><e>[</e><w>{line:^5}</w><e>]</e></b>",
        message="  <level>{message}</level>",
    )
    level_per_module: t.Optional[dict[str, str]] = {}
    level_colors: t.Optional[dict[str, str]] = {}
    settings: t.Optional[dict[str, t.Any]] = {}

    @depends.inject
    def __init__(self, config: Config = depends(), **values: t.Any) -> None:
        super().__init__(**values)
        self.serialize = True if config.deployed else False
        self.level_per_module = {m: "DEBUG" if v else "INFO" for m, v in debug.items()}
        self.settings = dict(
            filter=self.level_per_module,
            format="".join(self.format.values()),
            enqueue=True,
            backtrace=True,
            catch=True,
            serialize=self.serialize,
            diagnose=False,
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
            mod_name = ".".join(mod_parts[:-1])
            if len(mod_parts) > 3:
                mod_name = ".".join(mod_parts[1:-1])
            return mod_name

        self.remove()
        self.configure(
            patcher=lambda record: record["extra"].update(  # type: ignore
                mod_name=patch_name(record)
            )
        )
        self.add(sys.stdout, **config.logger.settings)
        for level, color in config.logger.level_colors.items():
            self.level(level.upper(), color=f"<{color}>")
        if config.deployed:
            self.level = config.logger.deployed_level
        if config.debug.logger:
            self.debug("debug")
            self.info("info")
            self.warning("warning")
            self.error("error")
            self.critical("critical")


depends.set(Logger)


class InterceptHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        logger = depends.get(Logger)
        level: str | int
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        frame, depth = currentframe(), 0
        while frame and (depth == 0 or frame.f_code.co_filename == logging.__file__):
            frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(
            level, record.getMessage()
        )


logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)
