import logging
import typing as t
from pathlib import Path
from pprint import pformat
from time import perf_counter

from acb.adapters import import_adapter
from acb.config import adapter_registry
from acb.config import Config
from acb.depends import depends
from icecream import colorizedStderrPrint
from icecream import ic as debug

Logger = import_adapter()

config = depends.get(Config)


def get_calling_module() -> Path | None:
    mod = logging.currentframe().f_back.f_back.f_back.f_code.co_filename
    mod = Path(mod).parent
    debug_mod = getattr(config.debug, mod.stem, None)
    return mod if debug_mod else None


@depends.inject
def patch_record(
    mod: Path, msg: str, logger: Logger = depends()  # type: ignore
) -> None:
    if next(
        a
        for a in adapter_registry.get()
        if a.category == "logger" and a.name == "loguru"
    ):
        logger.patch(lambda record: record.update(name=mod.name)).debug(  # type: ignore
            msg
        )


def print_debug_info(msg: str) -> t.Any:
    mod = get_calling_module()
    if mod:
        if config.deployed or config.debug.production:
            patch_record(mod, msg)
        else:
            colorizedStderrPrint(msg)


debug_args = dict(
    outputFunction=print_debug_info,
    argToStringFunction=lambda o: pformat(o, sort_dicts=False),
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


@depends.inject
def timeit(func: t.Any, logger: Logger = depends()) -> t.Any:  # type: ignore
    def wrapped(*args: t.Any, **kwargs: t.Any) -> t.Any:
        start = perf_counter()
        result = func(*args, **kwargs)
        end = perf_counter()
        logger.debug(f"Function '{func.__name__}' executed in {end - start} s")
        return result

    return wrapped
