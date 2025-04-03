from time import perf_counter

from acb.depends import depends

from . import post_startup
from ._base import AppBase, AppBaseSettings

main_start = perf_counter()


class AppSettings(AppBaseSettings): ...


class App(AppBase):
    async def init(self) -> None:
        self.logger.info("Application starting...")

        await post_startup()
        main_start_time = perf_counter() - main_start
        self.logger.info(f"App started in {main_start_time} s")

    async def main(self) -> None: ...


depends.set(App)
