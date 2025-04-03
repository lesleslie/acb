import logging
import typing as t
from inspect import currentframe

import nest_asyncio
from aioconsole import aprint
from loguru._logger import Core as _Core
from loguru._logger import Logger as _Logger

from .config import Config, Settings, debug
from .depends import depends

nest_asyncio.apply()


class LoggerSettings(Settings):
    verbose: bool = False
    deployed_level: str = "WARNING"
    log_level: t.Optional[str] = "INFO"
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

    def __init__(self, **values: t.Any) -> None:
        super().__init__(**values)
        self.settings = dict(
            format="".join(self.format.values()),
            enqueue=True,
            backtrace=False,
            catch=False,
            serialize=self.serialize,
            diagnose=False,
            colorize=True,
        )


depends.get(Config).logger = LoggerSettings()


@t.runtime_checkable
class LoggerProtocol(t.Protocol):
    def debug(self, msg: str, *args: t.Any, **kwargs: t.Any) -> None: ...

    def info(self, msg: str, *args: t.Any, **kwargs: t.Any) -> None: ...

    def warning(self, msg: str, *args: t.Any, **kwargs: t.Any) -> None: ...

    def error(self, msg: str, *args: t.Any, **kwargs: t.Any) -> None: ...

    def init(self) -> None: ...


class LoggerBase(LoggerProtocol):
    config: Config = depends()


class Logger(_Logger, LoggerBase):
    @depends.inject
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

    def init(self) -> None:
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
            level_ = self.config.logger.log_level
            if name in self.config.logger.level_per_module:
                level_ = self.config.logger.level_per_module[name]
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
            patcher=lambda record: record["extra"].update(mod_name=patch_name(record)),
        )
        self.config.logger.log_level = (
            self.config.logger.deployed_level.upper()
            if self.config.deployed or self.config.debug.production
            else self.config.logger.log_level
        )
        self.config.logger.level_per_module = {
            m: "DEBUG" if v else self.config.logger.log_level for m, v in debug.items()
        }
        self.add(
            self.async_sink,
            filter=filter_by_module,  # type: ignore
            **self.config.logger.settings,
        )
        for level, color in self.config.logger.level_colors.items():
            self.level(level.upper(), color=f"[{color}]")
        if self.config.debug.logger:
            self.debug("debug")
            self.info("info")
            self.warning("warning")
            self.error("error")
            self.critical("critical")
        self.info(f"App path: {self.config.root_path}")
        self.info(f"App deployed: {self.config.deployed}")


depends.set(Logger)
depends.get(Logger).init()


class InterceptHandler(logging.Handler):
    @depends.inject
    def emit(self, record: logging.LogRecord, logger: Logger = depends()) -> None:
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
