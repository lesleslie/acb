import asyncio

from acb.config import available_adapters
from acb.config import available_modules
from acb.config import Config
from acb.config import enabled_adapters
from acb.config import loaded_adapters
from acb.config import package_registry
from acb.config import required_adapters
from acb.depends import depends
from icecream import ic
from pluginbase import PluginBase

# from importlib import import_module

__all__: list[str] = []

adapters_base = PluginBase(package="acb.adapters")
adapters_source = adapters_base.make_plugin_source(
    searchpath=[], identifier="acb-adapters"
)


async def load_adapter(adapter: str) -> None:
    adapters_source.searchpath = list(package_registry.get().values())
    ic(adapters_source.searchpath)
    with adapters_source:
        _module = adapters_source.load_plugin(adapter)


@depends.inject
async def main(config: Config = depends()) -> None:
    await config.init()
    for adapter in enabled_adapters.get():
        if adapter in loaded_adapters.get():
            continue
        await load_adapter(adapter)
    ic(available_modules.get())
    ic(available_adapters.get())
    ic(required_adapters.get())
    ic(enabled_adapters.get())
    ic(package_registry.get())


loop = asyncio.new_event_loop() or asyncio.get_running_loop()
loop.run_until_complete(main())  # type: ignore
