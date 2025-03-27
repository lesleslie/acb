import asyncio
import logging
from contextlib import suppress
from functools import wraps
from pathlib import Path
from time import perf_counter
from typing import Any, Callable, Protocol, TypeVar, cast

from aioconsole import aprint
from devtools import pformat
from icecream import colorize, supportTerminalColorsInWindows
from icecream import ic as debug
from acb.adapters import import_adapter
from acb.config import adapter_registry
from acb.depends import depends

__all__ = [
    "get_calling_module",
    "patch_record",
    "colorized_stderr_print",
    "print_debug_info",
    "timeit",
    "debug",
]

Logger = import_adapter()

config = depends.get()


def get_calling_module() -> Path | None:
    try:
        mod = logging.currentframe().f_back.f_back.f_back.f_code.co_filename
        mod = Path(mod).parent
        debug_mod = getattr(config.debug, mod.stem, None)
        return mod if debug_mod else None
    except (AttributeError, TypeError):
        return None


@depends.inject
def patch_record(
    mod: Path,
    msg: str,
    logger: Logger = depends(),
) -> None:
    with suppress(Exception):
        has_loguru = any(
            a.category == "logger" and a.name == "loguru"
            for a in adapter_registry.get()
        )
        if has_loguru:
            logger.patch(lambda record: record.update(name=mod.name)).debug(msg)


def colorized_stderr_print(s: str) -> None:
    colored = colorize(s)
    with supportTerminalColorsInWindows():
        asyncio.run(aprint(colored, use_stderr=True))


def print_debug_info(msg: str) -> Any:
    mod = get_calling_module()
    if mod:
        if config.deployed or config.debug.production:
            patch_record(mod, msg)
        else:
            colorized_stderr_print(msg)


debug_args = dict(
    outputFunction=print_debug_info,
    argToStringFunction=lambda o: pformat(o, highlight=False),
)
debug.configureOutput(
    prefix="    debug:  ",
    includeContext=True,
    **debug_args,
)
if config.deployed or config.debug.production:
    debug.configureOutput(
        prefix="",
        includeContext=False,
        **debug_args,
    )


class TimedFunction(Protocol):
    def __call__(self, *args: Any, **kwargs: Any) -> Any: ...


T = TypeVar("T", bound=Callable[..., Any])


@depends.inject
def timeit(func: T, logger: Logger = depends()) -> T:
    @wraps(func)
    def wrapped(*args: Any, **kwargs: Any) -> Any:
        start = perf_counter()
        result = func(*args, **kwargs)
        end = perf_counter()
        logger.debug(f"Function '{func.__name__}' executed in {end - start} s")
        return result

    return cast(T, wrapped)
