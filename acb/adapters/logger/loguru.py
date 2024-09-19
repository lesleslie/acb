import logging
import typing as t
from inspect import currentframe

from aioconsole import aprint
from loguru._logger import Core as _Core
from loguru._logger import Logger as _Logger
from acb.config import Config, debug
from acb.depends import depends
from ._base import LoggerBase, LoggerBaseSettings


class LoggerSettings(LoggerBaseSettings):
    serialize: t.Optional[bool] = False
    format: t.Optional[dict[str, str]] = dict(
        time="<b><e>[</e> <w>{time:YYYY-MM-DD HH:mm:ss.SSS}</w> <e>]</e></b>",
        level=" <level>{level:>8}</level>",
        sep=" <b><w>in</w></b> ",
        name="<b>{extra[mod_name]:>20}</b>",
        line="<b><e>[</e><w>{line:^5}</w><e>]</e></b>",
        message="  <level>{message}</level>",
    )
    level_per_module: t.Optional[dict[str, str | None]] = {}
    level_colors: t.Optional[dict[str, str]] = {}
    settings: t.Optional[dict[str, t.Any]] = {}

    @depends.inject
    def __init__(self, config: Config = depends(), **values: t.Any) -> None:
        super().__init__(**values)
        # self.serialize = True if config.deployed else False
        self.log_level = (
            self.deployed_level.upper()
            if config.deployed or config.debug.production
            else self.log_level
        )
        self.level_per_module = {
            m: "DEBUG" if v else self.log_level for m, v in debug.items()
        }
        self.settings = dict(
            format="".join(self.format.values()),
            enqueue=True,
            backtrace=False,
            catch=False,
            serialize=self.serialize,
            diagnose=False,
            colorize=True,
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

    @staticmethod
    async def async_sink(message: str) -> None:
        await aprint(message, end="")

    @depends.inject
    async def init(self, config: Config = depends()) -> None:
        def patch_name(record: dict[str, t.Any]) -> str:  # type: ignore
            mod_parts = record["name"].split(".")
            mod_name = ".".join(mod_parts[:-1])
            if len(mod_parts) > 3:
                mod_name = ".".join(mod_parts[1:-1])
            return mod_name.replace("_sdk", "")

        def filter_by_module(record: dict[str, t.Any]) -> bool:
            try:
                name = record["name"].split(".")[-2]
            except IndexError:
                name = record["name"]
            level_ = config.logger.log_level
            if name in config.logger.level_per_module:
                level_ = config.logger.level_per_module[name]
            try:
                levelno_ = self.level(level_).no
            except ValueError:
                raise ValueError(
                    f"The filter dict contains a module '{name}' associated to a level "
                    f" name which does not exist: '{level_}'"
                )
            if level_ is False:
                return False
            return record["level"].no >= levelno_

        self.remove()
        self.configure(
            patcher=lambda record: record["extra"].update(  # type: ignore
                mod_name=patch_name(record)
            ),
        )
        self.add(
            self.async_sink,
            filter=filter_by_module,  # type: ignore
            **config.logger.settings,
        )
        for level, color in config.logger.level_colors.items():
            self.level(level.upper(), color=f"[{color}]")
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
