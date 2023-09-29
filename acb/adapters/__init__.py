import asyncio

from acb.config import Config
from acb.config import enabled_adapters
from acb.depends import depends
from inflection import camelize
from pluginbase import PluginBase

__all__: list[str] = []

adapters_base = PluginBase(package="acb.adapters")


@depends.inject
async def main(config: Config = depends()) -> None:
    await config.init()
    adapters = enabled_adapters.get()
    adapters_path = config.pkgdir / "adapters"
    adapters_source = adapters_base.make_plugin_source(
        searchpath=[str(adapters_path)], identifier="acb-adapters"
    )
    for adapter_name in adapters:
        adapter_class_name = camelize(adapter_name)
        with adapters_source:
            adapter_module = adapters_source.load_plugin(adapter_name)
        adapter_class = getattr(adapter_module, adapter_class_name)
        adapter_settings = getattr(adapter_module, f"{adapter_class_name}Settings")
        setattr(
            config, adapter_name, adapter_settings(_secrets_dir=config.secrets_path)
        )
        # depends.set(Config, config)
        adapter = depends.get(adapter_class)
        await adapter.init()
        __all__.append(adapter_class_name)
        globals()[adapter_class_name] = adapter_class


loop = asyncio.new_event_loop() or asyncio.get_running_loop()
loop.run_until_complete(main())  # type: ignore
