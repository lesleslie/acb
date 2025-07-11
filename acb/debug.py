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

from .depends import depends
from .logger import Logger

__all__ = [
    "colorized_stderr_print",
    "debug",
    "get_calling_module",
    "patch_record",
    "print_debug_info",
]
_deployed: bool = os.getenv("DEPLOYED", "False").lower() == "true"


def get_calling_module() -> Path | None:
    with suppress(AttributeError, TypeError):
        config = depends.get("config")
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
    import sys

    try:
        colored = colorize(s)
        with supportTerminalColorsInWindows():
            try:
                asyncio.run(aprint(colored, use_stderr=True))
            except Exception:
                print(colored, file=sys.stderr)
    except ImportError:
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


def init_debug() -> None:
    import warnings

    warnings.filterwarnings("ignore", category=RuntimeWarning, module="icecream")
    try:
        config = depends.get("config")
        debug_args = {
            "outputFunction": print_debug_info,
            "argToStringFunction": lambda o: pformat(o, highlight=False),
        }
        debug.configureOutput(prefix="    debug:  ", includeContext=True, **debug_args)
        is_production = config.deployed
        if config.debug is not None and hasattr(config.debug, "production"):
            is_production = is_production or config.debug.production
        if is_production:
            debug.configureOutput(prefix="", includeContext=False, **debug_args)
    except Exception:
        debug_args = {
            "outputFunction": print_debug_info,
            "argToStringFunction": lambda o: pformat(o, highlight=False),
        }
        debug.configureOutput(prefix="    debug:  ", includeContext=True, **debug_args)


init_debug()
