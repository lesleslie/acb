import logging
import typing as t
from pprint import pformat

from acb.config import Config
from acb.config import enabled_adapters
from acb.depends import depends
from aioconsole import aprint
from aiopath import AsyncPath
from icecream import colorizedStderrPrint
from icecream import install
from loguru import logger as loguru_logger


class Debug:
    config: Config = depends()

    def get_calling_module(self) -> AsyncPath | None:
        mod = logging.currentframe().f_back.f_back.f_back.f_code.co_filename
        mod = AsyncPath(mod).parent
        debug_mod = getattr(self.config.debug, mod.stem, None) or (
            mod.stem == self.config.app.name and self.config.debug.main
        )
        return mod if debug_mod else None

    def patch_record(self, mod: AsyncPath, msg: str) -> None:
        if enabled_adapters.get()["logger"] == "loguru":
            loguru_logger.patch(
                lambda record: record.update(name=mod.name),
            ).debug(msg)

    # def print_debug_info(self, msg: str) -> t.Any:
    def __call__(self, msg: str) -> t.Any:
        mod = self.get_calling_module()
        if mod:
            if self.config.deployed or self.config.debug.production:
                self.patch_record(mod, msg)
            else:
                colorizedStderrPrint(msg)

    async def pprint(self, obj: t.Any, sort_dicts: bool = False) -> t.Any:  # make
        # purple
        mod = self.get_calling_module()
        if mod and not self.config.deployed and not self.config.debug.production:
            await aprint(pformat(obj, sort_dicts=sort_dicts))

    def __init__(self):
        try:
            from icecream import ic

            install()
            ic.configureOutput(
                prefix="    debug:  ",
                includeContext=True,
                outputFunction=self.__call__,
            )
            if self.config.deployed or self.config.debug.production:
                ic.configureOutput(
                    prefix="",
                    includeContext=False,
                    outputFunction=self.__call__,
                )

        except ImportError:  # Graceful fallback if IceCream isn't installed.

            def ic(*a: t.Any) -> t.Any:
                fake_ic = a[0] if len(a) == 1 else a
                return None if not a else fake_ic


debug = Debug()
