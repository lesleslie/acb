import asyncio
import typing as t
from contextlib import suppress
from contextvars import ContextVar
from importlib import import_module
from inspect import currentframe
from pathlib import Path
from warnings import warn

from aiopath import AsyncPath
from inflection import camelize
from .actions.encode import dump
from .actions.encode import load
from .depends import depends

pkg_path: AsyncPath = AsyncPath(__file__)
base_path: AsyncPath = AsyncPath.cwd()

settings_path: AsyncPath = base_path / "settings"
app_settings_path: AsyncPath = settings_path / "app.yml"
adapter_settings_path: AsyncPath = settings_path / "adapters.yml"
adapters_path = pkg_path / "adapters"

available_adapters: ContextVar[dict[str, dict[str, AsyncPath]]] = ContextVar(
    "available_adapters", default={}
)
required_adapters: ContextVar[dict[str, str]] = ContextVar(
    "required_adapters", default={"secrets": "secret_manager", "logger": "loguru"}
)
enabled_adapters: ContextVar[dict[str, dict]] = ContextVar(
    "enabled_adapters", default={}
)
package_registry: ContextVar[dict[str, str]] = ContextVar(
    "package_registry", default={}
)
adapter_registry: ContextVar[set[str]] = ContextVar("adapter_registry", default=set())
logger_registry: ContextVar[set[str]] = ContextVar("logger_registry", default=set())


async def update_adapters(
    adapters_path: AsyncPath,
) -> dict[str, dict[str, AsyncPath]]:
    _available_adapters = available_adapters.get()
    for adapter, module in {
        a.stem: {m.stem: m async for m in a.rglob("*.py") if not m.name.startswith("_")}
        async for a in adapters_path.iterdir()
        if await a.is_dir() and not a.name.startswith("__")
    }.items():
        _available_adapters.update({adapter: module})
    if not await adapter_settings_path.exists():
        await dump.yaml(
            {cat: None for cat in _available_adapters} | required_adapters.get(),
            adapter_settings_path,
        )
    _adapters = await load.yaml(adapter_settings_path)
    newly_available_adapters = {
        a: None for a in _available_adapters if a not in _adapters
    }
    _adapters.update(newly_available_adapters)
    for adapter in [n for n in newly_available_adapters if n in adapter_registry.get()]:
        adapter_registry.get().discard(adapter)
    await dump.yaml(_adapters, adapter_settings_path)
    _enabled_adapters = enabled_adapters.get()
    _enabled_adapters.update(
        {
            a: dict(module=_adapters[a], path=_available_adapters[a][_adapters[a]])
            for a in _available_adapters
            if _adapters.get(a)
        }
    )
    available_adapters.set(_available_adapters)
    for a in required_adapters.get():
        _enabled_adapters = {a: _enabled_adapters.pop(a)} | _enabled_adapters
    del _enabled_adapters["secrets"]
    enabled_adapters.set(_enabled_adapters)
    return _available_adapters


def register_package() -> None:
    _packages = package_registry.get()
    _pkg_path = Path(currentframe().f_back.f_code.co_filename).parent
    _pkg_name = _pkg_path.name
    _adapters_path = Path(_pkg_path / "adapters")
    _available_adapters = available_adapters.get()
    if _adapters_path.exists():
        _adapters_path = AsyncPath(_adapters_path)
        _available_adapters = asyncio.run(update_adapters(_adapters_path))
    package_registry.get().update({_pkg_name: str(_pkg_path)} | _packages)


def install_required_adapters(module: t.Any) -> None:
    required = getattr(module, "requires", [])
    for required_adapter in required:
        if required_adapter not in adapter_registry.get():
            load_adapter(required_adapter)
            required_adapters.get().update(required_adapter)


def load_adapter(adapter_name: t.Optional[str] = None) -> t.Any:
    if adapter_name not in adapter_registry.get():
        with suppress(KeyError):
            _pkg_path = Path(currentframe().f_code.co_filename).parent
            if adapter_name is None:
                adapter_name = Path(
                    currentframe().f_back.f_code.co_filename
                ).parent.stem
            _adapter_class_name = camelize(adapter_name)
            _adapter_settings_class_name = f"{_adapter_class_name}Settings"
            _module_path = enabled_adapters.get()[adapter_name]["path"]
            _module = ".".join(_module_path.parts[-4:]).removesuffix(".py")
            _imported_module = import_module(_module)
            install_required_adapters(_imported_module)
            _adapter_settings_class = getattr(
                _imported_module, _adapter_settings_class_name
            )
            _adapter_class = getattr(_imported_module, _adapter_class_name)
            if adapter_name != "secrets":
                from acb.config import Config

                config = depends.get(Config)
                setattr(config, adapter_name, _adapter_settings_class())
            adapter = depends.get(_adapter_class)
            asyncio.run(adapter.init())
            adapter_registry.get().add(adapter_name)
            if adapter_name != "logger":
                from acb.adapters.logger import Logger

                logger = depends.get(Logger)
                logger.info(f"{_adapter_class_name} adapter loaded")
            return _adapter_class, _adapter_settings_class
        if adapter_name in required_adapters.get():
            raise SystemExit(f"Required adapter {adapter_name!r} not found.")
        warn(f"Adapter {adapter_name!r} not found.")


register_package()
