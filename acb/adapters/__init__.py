import asyncio

from acb.config import ac
from acb.config import load_adapter
from acb.config import enabled_adapters

__all__ = []


async def main() -> None:
    await ac.init()
    for adapter in enabled_adapters.get():
        __all__.append(adapter)
        globals()[adapter], module_settings = load_adapter(adapter, settings=True)
        setattr(ac, adapter, module_settings(_secrets_dir=ac.secrets_path))
        await globals()[adapter].init()


loop = asyncio.new_event_loop() or asyncio.get_running_loop()
loop.run_until_complete(main())
