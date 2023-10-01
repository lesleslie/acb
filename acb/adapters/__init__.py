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
from inflection import camelize
from pluginbase import PluginBase

# from importlib import import_module

__all__: list[str] = []

adapters_base = PluginBase(package="acb.adapters")
adapters_source = adapters_base.make_plugin_source(
    searchpath=[], identifier="acb-adapters"
)


@depends.inject
async def load_adapter(adapter_name: str, config: Config = depends()) -> None:
    adapter_class_name = camelize(adapter_name)
    adapters_source.searchpath = list(package_registry.get().values())
    ic("loading adapter")
    ic(adapters_source.searchpath)
    with adapters_source:
        adapter_module = adapters_source.load_plugin(adapter_name)
    ic(adapter_module)
    # adapter_module = import_module()
    required = getattr(adapter_module, "required_adapters", [])
    for required_adapter in required:
        if required_adapter not in loaded_adapters.get():
            await load_adapter(required_adapter)
            required_adapters.get().update(required_adapter)
    ic()
    adapter_class = getattr(adapter_module, adapter_class_name)
    adapter_settings = getattr(adapter_module, f"{adapter_class_name}Settings")
    setattr(config, adapter_name, adapter_settings())
    adapter = depends.get(adapter_class)
    await adapter.init()


@depends.inject
async def main(config: Config = depends()) -> None:
    await config.init()
    for adapter_name in enabled_adapters.get():
        if adapter_name in loaded_adapters.get():
            continue
        await load_adapter(adapter_name)
    ic(available_modules.get())
    ic(available_adapters.get())
    ic(required_adapters.get())
    ic(enabled_adapters.get())
    ic(package_registry.get())


loop = asyncio.new_event_loop() or asyncio.get_running_loop()
loop.run_until_complete(main())  # type: ignore
