from time import time
from contextlib import suppress

import anyio
from acb import register_package
from acb.adapters.logger import Logger
from acb.config import Config
from acb.depends import depends
from ._base import AppBase
from ._base import AppBaseSettings

main_start = time()

register_package()


class AppSettings(AppBaseSettings):
    ...


class App(AppBase):
    @depends.inject
    async def init(
        self, config: Config = depends(), logger: Logger = depends()  # type: ignore
    ) -> None:
        logger.info("Application starting...")

        async def post_startup() -> None:
            if not config.deployed:
                from aioconsole import aprint
                from pyfiglet import Figlet

                fig = Figlet(font="slant", width=90, justify="center")
                await aprint(f"\n\n{fig.renderText(config.app.name.upper())}\n")
            if not config.debug.production and config.deployed:
                logger.info("Entering production mode...")

        await post_startup()
        main_start_time = time() - main_start
        logger.info(f"App started in {main_start_time} s")

    @staticmethod
    @depends.inject
    async def task(number: int, logger: Logger = depends()) -> None:  # type: ignore
        logger.info("Task", number, "started")
        await anyio.sleep(2)
        logger.info("Task", number, "finished")

    @staticmethod
    @depends.inject
    async def main(self, logger: Logger = depends()):  # type: ignore
        start = anyio.current_time()
        try:
            async with anyio.create_task_group() as tg:
                for i in range(5):
                    tg.start_soon(self.task, i)
        except BaseException:
            with suppress(ImportError):
                from acb.adapters.cache import Cache

                cache = depends.get(Cache)
                await cache.close()
            runtime = anyio.current_time() - start
            logger.info(f"App ran {runtime:.2f}s")
            logger.critical("Application shut down")
            raise SystemExit(0)


depends.set(App, App())
app = depends.get(App)
anyio.run(app.main())
