import logging
import typing as t
from pathlib import Path
from pprint import pformat

from acb.adapters.logger import Logger
from acb.config import Config
from acb.config import enabled_adapters
from acb.depends import depends
from icecream import colorizedStderrPrint

config = depends.get(Config)
logger = depends.get(Logger)


def get_calling_module() -> Path | None:
    mod = logging.currentframe().f_back.f_back.f_back.f_code.co_filename
    mod = Path(mod).parent
    debug_mod = getattr(config.debug, mod.stem, None) or (
        mod.stem == config.app.name and config.debug.main
    )
    return mod if debug_mod else None


def patch_record(mod: Path, msg: str) -> None:
    if enabled_adapters.get()["logger"] == "loguru":
        logger.patch(
            lambda record: record.update(name=mod.name),  # type: ignore
        ).debug(msg)


def print_debug_info(msg: str) -> t.Any:
    mod = get_calling_module()
    if mod:
        if config.deployed or config.debug.production:
            patch_record(mod, msg)
        else:
            colorizedStderrPrint(msg)


try:
    from icecream import ic as debug

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

except ImportError:

    def debug(*a: t.Any) -> t.Any:
        fake_ic = a[0] if len(a) == 1 else a
        return None if not a else fake_ic
