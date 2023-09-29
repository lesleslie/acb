import sys
import typing as t

from acb.config import Config
from acb.depends import depends
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
    level_per_module: t.Optional[dict[str, str]] | t.Literal["ERROR"] = None
    serialize: t.Optional[bool] = False

    @depends.inject
    def __init__(self, config: Config = depends(), **values: t.Any) -> None:
        super().__init__(**values)
        self.level_per_module = (
            {
                m: "DEBUG" if v is True else "INFO"
                for (m, v) in config.debug.model_dump().items()
            }
            if not config.deployed
            else "ERROR"
        )


class Logger(_Logger):
    config: Config = depends()
    settings: t.Optional[dict[str, t.Any]] = None

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

    async def init(self) -> None:
        self.remove()
        self.settings = dict(
            filter=self.config.logger.level_per_module,
            format="".join(self.config.logger.format.values()),
            enqueue=True,
            backtrace=True,
            serialize=self.config.logger.serialize,
        )
        self.add(sys.stderr, **self.settings)

        self.info("Logger adapter loaded")

        if self.config.debug.logger:
            self.debug("debug")
            self.info("info")
            self.warning("warning")
            self.error("error")
            self.critical("critical")


depends.set(Logger, Logger())
