import asyncio
import logging
import os
import typing as t
from contextlib import suppress
from pathlib import Path

from aioconsole import aprint
from devtools import pformat
from icecream import colorize, supportTerminalColorsInWindows
from icecream import ic as debug

from .config import Config
from .depends import depends
from .logger import Logger

__all__ = [
    "get_calling_module",
    "patch_record",
    "colorized_stderr_print",
    "print_debug_info",
    "debug",
]
_deployed: bool = os.getenv("DEPLOYED", "False").lower() == "true"


@depends.inject
def get_calling_module(config: Config = depends()) -> Path | None:
    with suppress(AttributeError, TypeError):
        mod = logging.currentframe().f_back.f_back.f_back.f_code.co_filename
        mod = Path(mod).parent
        if config.debug is not None:
            debug_mod = getattr(config.debug, mod.stem, None)
            return mod if debug_mod else None
        return None


@depends.inject
def patch_record(mod: Path | None, msg: str, logger: Logger = depends()) -> None:
    with suppress(Exception):
        if mod is not None:
            logger.patch(lambda record: record.update(name=mod.name)).debug(msg)
        else:
            logger.debug(msg)


def colorized_stderr_print(s: str) -> None:
    try:
        colored = colorize(s)
        with supportTerminalColorsInWindows():
            try:
                asyncio.run(aprint(colored, use_stderr=True))
            except Exception:
                import sys

                print(colored, file=sys.stderr)
    except ImportError:
        import sys

        print(s, file=sys.stderr)


def print_debug_info(msg: str) -> t.Any:
    mod = get_calling_module()
    if mod:
        if _deployed:
            patch_record(mod, msg)
        else:
            colorized_stderr_print(msg)
    return None


async def pprint(obj: t.Any) -> None:
    await aprint(pformat(obj), use_stderr=True)


@depends.inject
def init_debug(config: Config = depends()) -> None:
    debug_args = dict(
        outputFunction=print_debug_info,
        argToStringFunction=lambda o: pformat(o, highlight=False),
    )
    debug.configureOutput(prefix="    debug:  ", includeContext=True, **debug_args)
    is_production = config.deployed
    if config.debug is not None and hasattr(config.debug, "production"):
        is_production = is_production or config.debug.production
    if is_production:
        debug.configureOutput(prefix="", includeContext=False, **debug_args)


init_debug()
