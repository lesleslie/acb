import logging
import sys
import typing as t
from pprint import pformat
from time import perf_counter

from acb.config import ac
from aioconsole import aprint
from aiopath import AsyncPath
from icecream import colorizedStderrPrint
from icecream import install
from loguru import logger


def patch_record(mod: AsyncPath, msg: str) -> None:
    logger.patch(lambda record: record.update(name=mod.name)).debug(msg)  # type:ignore


def log_debug(msg: str) -> t.Any:
    mod = get_mod()
    if mod:
        if ac.deployed or ac.debug.production:
            patch_record(mod, msg)
        else:
            colorizedStderrPrint(msg)


try:
    from icecream import ic as debug

    install()
    debug.configureOutput(
        prefix="    debug:  ", includeContext=True, outputFunction=log_debug
    )
    if ac.deployed or ac.debug.production:
        debug.configureOutput(prefix="", includeContext=False, outputFunction=log_debug)

except ImportError:  # Graceful fallback if IceCream isn't installed.

    def debug(*a: t.Any) -> t.Any:
        fake_ic = a[0] if len(a) == 1 else a
        return None if not a else fake_ic


def get_mod() -> AsyncPath | None:
    mod = logging.currentframe().f_back.f_back.f_back.f_code.co_filename
    mod = AsyncPath(mod).parent
    debug_mod = getattr(ac.debug, mod.stem, None) or (
        mod.stem == ac.app.name and ac.debug.main
    )
    return mod if debug_mod else None


async def apprint(obj: t.Any, sort_dicts: bool = False) -> t.Any:  # make purple
    mod = get_mod()
    if mod and not ac.deployed and not ac.debug.production:
        await aprint(pformat(obj, sort_dicts=sort_dicts))


def timeit(func: t.Any) -> t.Any:
    def wrapped(*args: t.Any, **kwargs: t.Any) -> t.Any:
        start = perf_counter()
        result = func(*args, **kwargs)
        end = perf_counter()
        logger.debug(f"Function '{func.__name__}' executed in {end - start} s")
        return result

    return wrapped


class InterceptHandler(logging.Handler):
    def __init__(self, logger_name: str) -> None:
        super().__init__()
        self.log_name = logger_name

    def emit(self, record: logging.LogRecord) -> None:
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno
        frame, depth = logging.currentframe(), 2
        while frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1
        (
            logger.patch(
                lambda record: record.update(name=self.log_name)  # type: ignore
            )
            .opt(
                depth=depth,
                exception=record.exc_info,
            )
            .log(level, record.getMessage())
        )


logger_format: dict[str, str] = dict(
    time="<b><e>[</e> <w>{time:YYYY-MM-DD HH:mm:ss.SSS}</w> <e>]</e></b>",
    level=" <level>{level:>8}</level>",
    sep=" <b><w>in</w></b> ",
    name="{name:>24}",
    line="<b><e>[</e><w>{line:^5}</w><e>]</e></b>",
    message="  <level>{message}</level>",
)

level_per_module: dict[str, str] = {
    m: "DEBUG" if v is True else "INFO" for (m, v) in ac.debug.model_dump().items()
}

log_format = "".join(logger_format.values())
configs: dict[str, t.Any] = dict(
    filter=level_per_module,
    format=log_format,
    enqueue=True,
    backtrace=True,
)
logger.remove()
logger.add(sys.stderr, **configs)
logger.level("DEBUG", color="<cyan>")
_loggers: list[str] = []
if ac.debug.sql:
    _loggers.extend(
        [
            "sqlalchemy.engine",
            "sqlalchemy.orm",
            "sqlalchemy.pool",
            "sqlalchemy.dialects",
        ]
    )
if ac.debug.requests:
    _loggers.extend(["httpx_caching"])


def load_loggers(loggers: list[str]) -> None:
    for _logger in loggers:
        _logger = logging.getLogger(_logger)
        _logger.handlers.clear()
        _logger.handlers = [InterceptHandler(_logger.name)]


load_loggers(_loggers)

if ac.debug.logger:
    logger.debug("debug")
    logger.info("info")
    logger.warning("warning")
    logger.error("error")
    logger.critical("critical")
