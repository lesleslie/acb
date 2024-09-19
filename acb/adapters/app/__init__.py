from acb.adapters import import_adapter
from acb.config import Config
from acb.depends import depends

Logger = import_adapter()


@depends.inject
async def post_startup(config: Config = depends(), logger: Logger = depends()) -> None:  # type: ignore
    if not config.deployed:
        from aioconsole import aprint
        from pyfiglet import Figlet

        fig = Figlet(font="slant", width=90, justify="center")
        await aprint(f"\n\n{fig.renderText(config.app.name.upper())}\n")
    if not config.debug.production and config.deployed:
        logger.info("Entering production mode...")
