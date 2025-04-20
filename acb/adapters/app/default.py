from time import perf_counter

from acb.depends import depends

from ._base import AppBase, AppBaseSettings

main_start = perf_counter()


class AppSettings(AppBaseSettings): ...


class App(AppBase):
    async def post_startup(self) -> None:
        if not self.config.deployed:
            from aioconsole import aprint
            from pyfiglet import Figlet

            fig = Figlet(font="slant", width=90, justify="center")
            await aprint(f"\n\n{fig.renderText(self.config.app.name.upper())}\n")
        if not self.config.debug.production and self.config.deployed:
            self.logger.info("Entering production mode...")

    async def init(self) -> None:
        self.logger.info("Application starting...")

        await self.post_startup()
        main_start_time = perf_counter() - main_start
        self.logger.info(f"App started in {main_start_time} s")

    async def main(self) -> None: ...


depends.set(App)
