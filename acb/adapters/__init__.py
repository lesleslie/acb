import asyncio

from acb.config import ac
from acb.config import load_adapter
from icecream import ic

__all__ = []


async def main() -> None:
    await ac.init()
    for adapter in ac.enabled_adapters:
        __all__.append(adapter)
        globals()[adapter], module_settings = load_adapter(adapter, settings=True)
        setattr(ac, adapter, module_settings(_secrets_dir=ac.secrets_path))
        await globals()[adapter].init()


loop = asyncio.new_event_loop() or asyncio.get_running_loop()
loop.run_until_complete(main())
