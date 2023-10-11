import asyncio
import typing as t
from contextlib import suppress
from contextvars import ContextVar
from importlib import import_module
from inspect import currentframe
from pathlib import Path
from warnings import warn

from acb.actions.encode import dump
from acb.actions.encode import load
from acb.depends import depends
from aiopath import AsyncPath
from inflection import camelize
from pydantic import BaseModel

pkg_path: AsyncPath = AsyncPath(__file__).parent
base_path: AsyncPath = AsyncPath.cwd()
actions_path = pkg_path / "actions"
adapters_path = pkg_path / "adapters"
settings_path: AsyncPath = base_path / "settings"
app_settings_path: AsyncPath = settings_path / "app.yml"
adapter_settings_path: AsyncPath = settings_path / "adapters.yml"


class AdapterModule(BaseModel, arbitrary_types_allowed=True):
    name: str
    package: str
    path: AsyncPath


class Action(BaseModel, arbitrary_types_allowed=True):
    package: str
    path: AsyncPath


available_adapters: ContextVar[dict[str, list[AdapterModule]]] = ContextVar(
    "available_adapters", default={}
)
required_adapters: ContextVar[dict[str, AdapterModule]] = ContextVar(
    "required_adapters",
    default=dict(
        secrets=AdapterModule(
            name="secret_manager",
            package="acb",
            path=adapters_path / "secrets/secret_manager.py",
        ),
        logger=AdapterModule(
            name="loguru", package="acb", path=adapters_path / "logger/loguru.py"
        ),
    ),
)
enabled_adapters: ContextVar[dict[str, AdapterModule]] = ContextVar(
    "enabled_adapters", default={}
)
adapter_registry: ContextVar[dict[str, AdapterModule]] = ContextVar(
    "adapter_registry", default={}
)
action_registry: ContextVar[dict[str, Action]] = ContextVar(
    "action_registry", default={}
)
package_registry: ContextVar[dict[str, AsyncPath]] = ContextVar(
    "package_registry", default={}
)
enabled_adapters.get().update(required_adapters.get())


def install_required_adapters(adapter_settings: t.Any) -> None:
    required = getattr(adapter_settings, "requires", [])
    for required_adapter in required:
        if required_adapter not in adapter_registry.get():
            load_adapter(required_adapter)
            required_adapters.get().update(required_adapter)


def load_adapter(adapter_name: t.Optional[str] = None) -> t.Any:
    _pkg_path = Path(currentframe().f_code.co_filename).parent
    if adapter_name is None:
        adapter_name = Path(currentframe().f_back.f_code.co_filename).parent.stem
    try:
        initialize = False
        if adapter_name not in adapter_registry.get():
            adapter_registry.get().update(
                {adapter_name: enabled_adapters.get()[adapter_name]}
            )
            initialize = True
        _adapter_class_name = camelize(adapter_name)
        _adapter_settings_class_name = f"{_adapter_class_name}Settings"
        _module_path = enabled_adapters.get()[adapter_name].path
        _module = ".".join(_module_path.parts[-4:]).removesuffix(".py")
        try:
            _imported_module = import_module(_module)
        except ImportError as e:
            return warn(f"Error importing {adapter_name!r} adapter: {e}")
        _adapter_class = getattr(_imported_module, _adapter_class_name)
        if initialize:
            _adapter_settings_class = getattr(
                _imported_module, _adapter_settings_class_name
            )
            _adapter_settings = _adapter_settings_class()
            install_required_adapters(_adapter_settings)
            from acb.config import Config

            config = depends.get(Config)
            setattr(config, adapter_name, _adapter_settings)
            _adapter = depends.get(_adapter_class)
            asyncio.run(_adapter.init())
            if adapter_name != "logger":
                from acb.adapters.logger import Logger

                logger = depends.get(Logger)
                logger.info(f"{_adapter_class_name} adapter loaded")
            else:
                logger = depends.get(_adapter_class)
                logger.info(f"{_adapter_class_name} adapter loaded")
            return _adapter_class
        return _adapter_class
    except KeyError:
        if adapter_name in required_adapters.get():
            raise SystemExit(f"Required adapter {adapter_name!r} not found")
        warn(f"Adapter {adapter_name!r} not found")


async def update_adapters(_adapters_path: AsyncPath) -> None:
    _pkg = _adapters_path.parent.stem
    _available_adapters = available_adapters.get()
    for adapter, modules in {
        a.stem: [m async for m in a.rglob("*.py") if not m.name.startswith("_")]
        async for a in _adapters_path.iterdir()
        if await a.is_dir() and not a.name.startswith("__")
    }.items():
        modules = [AdapterModule(name=m.stem, package=_pkg, path=m) for m in modules]
        _available_adapters.update({adapter: modules})
    if not await adapter_settings_path.exists():
        await settings_path.mkdir(exist_ok=True)
        # await adapter_settings_path.touch(exist_ok=True)
        required = {a: m.name for a, m in required_adapters.get().items()}
        await dump.yaml(
            {cat: None for cat in _available_adapters} | required,
            adapter_settings_path,
            sort_keys=True,
        )
    _adapters = await load.yaml(adapter_settings_path)
    newly_available_adapters = {
        a: None for a in _available_adapters if a not in _adapters
    }
    _adapters.update(newly_available_adapters)
    for adapter in [n for n in newly_available_adapters if n in adapter_registry.get()]:
        del adapter_registry.get()[adapter]
    await dump.yaml(_adapters, adapter_settings_path, sort_keys=True)
    _enabled_adapters = enabled_adapters.get()
    _enabled_adapters.update(
        {
            a: [m for m in modules if m.name == _adapters.get(a)][0]
            for a, modules in _available_adapters.items()
            if _adapters.get(a)
        }
    )
    available_adapters.get().update(_available_adapters)
    for a in required_adapters.get():
        _enabled_adapters = {a: _enabled_adapters.pop(a)} | _enabled_adapters
    enabled_adapters.get().update(_enabled_adapters)


async def update_actions(
    _actions_path: AsyncPath,
) -> None:
    _actions = {
        a.stem: a
        async for a in _actions_path.iterdir()
        if await a.is_file() and not a.name.startswith("_")
    }
    _pkg_path = actions_path.parent
    for action_name, path in _actions.items():
        with suppress(KeyError):
            del action_registry.get()[action_name]
        action_registry.get().update(
            {action_name: Action(package=_pkg_path.name, path=path)}
        )


def register_package(_pkg_path: Path | None = None) -> None:
    _packages = package_registry.get()
    _pkg_path = _pkg_path or Path(currentframe().f_back.f_code.co_filename).parent
    _pkg_name = _pkg_path.name
    _actions_path = Path(_pkg_path / "actions")
    _adapters_path = Path(_pkg_path / "adapters")
    if _actions_path.exists():
        asyncio.run(update_actions(AsyncPath(_actions_path)))
    if _adapters_path.exists():
        asyncio.run(update_adapters(AsyncPath(_adapters_path)))
    package_registry.get().update({_pkg_name: AsyncPath(_pkg_path)} | _packages)


if base_path.name not in ("acb", "crackerjack"):
    register_package()
