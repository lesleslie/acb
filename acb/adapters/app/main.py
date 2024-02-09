from time import perf_counter

from acb.config import Config
from acb.depends import depends
from ._base import AppBase
from ._base import AppBaseSettings
from acb.adapters import import_adapter

main_start = perf_counter()

Logger = import_adapter()


class AppSettings(AppBaseSettings): ...


class App(AppBase):
    async def init(self) -> None:
        self.logger.info("Application starting...")

        # put app startup code here

        async def post_startup() -> None:
            if not self.config.deployed:
                from aioconsole import aprint
                from pyfiglet import Figlet

                fig = Figlet(font="slant", width=90, justify="center")
                await aprint(f"\n\n{fig.renderText(self.config.app.name.upper())}\n")
            if not self.config.debug.production and self.config.deployed:
                self.logger.info("Entering production mode...")

        await post_startup()
        main_start_time = perf_counter() - main_start
        self.logger.info(f"App started in {main_start_time} s")

    @depends.inject
    async def main(
        self, config: Config = depends(), logger: Logger = depends()  # type: ignore
    ) -> None:
        ...

        # put app main code here


depends.set(App)

app = depends.get(App)
