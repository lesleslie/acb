from time import perf_counter

from acb.adapters.logger import Logger
from acb.config import Config
from acb.depends import depends
from ._base import AppBase
from ._base import AppBaseSettings

main_start = perf_counter()


class AppSettings(AppBaseSettings):
    ...


class App(AppBase):
    @depends.inject
    async def init(
        self, config: Config = depends(), logger: Logger = depends()  # type: ignore
    ) -> None:
        logger.info("Application starting...")

        # put app startup code here

        async def post_startup() -> None:
            if not config.deployed:
                from aioconsole import aprint
                from pyfiglet import Figlet

                fig = Figlet(font="slant", width=90, justify="center")
                await aprint(f"\n\n{fig.renderText(config.app.name.upper())}\n")
            if not config.debug.production and config.deployed:
                logger.info("Entering production mode...")

        await post_startup()
        main_start_time = perf_counter() - main_start
        logger.info(f"App started in {main_start_time} s")

    @depends.inject
    async def main(
        self, config: Config = depends(), logger: Logger = depends()  # type: ignore
    ) -> None:
        ...

        # put app main code here


depends.set(App)

app = depends.get(App)
