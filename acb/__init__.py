import asyncio
import typing as t
from contextvars import ContextVar
from inspect import currentframe
from pathlib import Path
from warnings import warn

import nest_asyncio
from acb.actions.encode import dump
from acb.actions.encode import load
from acb.depends import depends
from aiopath import AsyncPath
from inflection import camelize
from pluginbase import PluginBase
from pydantic import BaseModel

nest_asyncio.apply()

base_path: AsyncPath = AsyncPath(Path.cwd())
pkg_path: AsyncPath = AsyncPath(__file__).parent
actions_path = pkg_path / "actions"
adapters_path = pkg_path / "adapters"
settings_path: AsyncPath = base_path / "settings"
app_settings_path: AsyncPath = settings_path / "app.yml"
adapter_settings_path: AsyncPath = settings_path / "adapters.yml"

adapters_base = PluginBase(package="acb._adapters")
adapters_source = adapters_base.make_plugin_source(searchpath=[], identifier="adapter")

actions_base = PluginBase(package="acb._actions")
actions_source = actions_base.make_plugin_source(searchpath=[], identifier="action")


class Package(BaseModel, arbitrary_types_allowed=True):
    name: str
    path: AsyncPath


class Adapter(BaseModel, arbitrary_types_allowed=True):
    name: str
    category: str
    pkg: Package
    required: bool = False
    enabled: bool = False
    installed: bool = False
    path: AsyncPath


class Action(BaseModel, arbitrary_types_allowed=True):
    name: str
    pkg: Package
    path: AsyncPath


adapter_registry: ContextVar[list[Adapter]] = ContextVar("adapter_registry", default=[])
action_registry: ContextVar[list[Action]] = ContextVar("action_registry", default=[])
package_registry: ContextVar[list[Package]] = ContextVar("package_registry", default=[])


def get_adapter(name: str) -> Adapter:
    return next(a for a in adapter_registry.get() if a.name == name)


def install_required_adapters(adapter_settings: dict[str, t.Any]) -> None:
    required = getattr(adapter_settings, "requires", [])
    for required_adapter in required:
        _adapter = get_adapter(required_adapter)
        load_adapter(required_adapter.name)
        required_adapter.required = True
        required_adapter.installed = True


def load_adapter(adapter_name: t.Optional[str] = None) -> t.Any:
    _pkg_path = Path(currentframe().f_code.co_filename).parent
    if adapter_name is None:
        adapter_name = Path(currentframe().f_back.f_code.co_filename).parent.stem
    try:
        _adapter = get_adapter(adapter_name)
        if _adapter.enabled and not _adapter.installed:
            _adapter_class_name = camelize(_adapter.name)
            _adapter_settings_class_name = f"{_adapter_class_name}Settings"
            _module_path = _adapter.path
            _module = ".".join(_module_path.parts[-4:]).removesuffix(".py")
            try:
                _imported_module = adapters_source.load_plugin(_adapter.name)
            except ImportError as err:
                return warn(
                    f"\nERROR: could not import {adapter_name!r} adapter: {err}\n"
                )
            _adapter_class = getattr(_imported_module, _adapter_class_name)
            _adapter_settings_class = getattr(
                _imported_module, _adapter_settings_class_name
            )
            _adapter_settings = _adapter_settings_class()
            install_required_adapters(_adapter_settings)
            from acb.config import Config

            config = depends.get(Config)
            setattr(config, adapter_name, _adapter_settings)
            asyncio.run(depends.get(_adapter_class))
            _adapter.installed = True
            if adapter_name != "logger":
                from acb.adapters.logger import Logger

                logger = depends.get(Logger)
                logger.info(f"{_adapter_class_name} adapter loaded")
            else:
                logger = depends.get(_adapter_class)
                logger.info(f"{_adapter_class_name} adapter loaded")
            return _adapter_class
    except KeyError as err:
        if get_adapter(adapter_name).required:
            raise SystemExit(
                f"\nERROR: required adapter {adapter_name!r} not found: {err}\n"
            )
        warn(f"\nERROR: adapter {adapter_name!r} not found: {err}\n")


async def update_adapters(pkg: Package, adapters_path: Path) -> None:
    for adapter, modules in {
        a.stem: [m for m in a.rglob("*.py") if not m.name.startswith("_")]
        for a in adapters_path.iterdir()
        if a.is_dir() and not a.name.startswith("__")
    }.items():
        modules = [
            Adapter(name=m.stem, category=m.parent.stem, pkg=pkg, path=m)
            for m in modules
        ]
        adapter_registry.get().extend(modules)
        if not await adapter_settings_path.exists():
            await settings_path.mkdir(exist_ok=True)
            for adapter in [
                a for a in adapter_registry.get() if a.name in ("logger", "secrets")
            ]:
                adapter.required = True
            required = [a for a in adapter_registry.get() if a.required]
            categories = {a.category for a in adapter_registry.get()}
            await dump.yaml(
                {cat: None for cat in categories}
                | {a.category: a.name for a in required},
                adapter_settings_path,
                sort_keys=True,
            )
    _adapters = await load.yaml(adapter_settings_path)
    _adapters.extend(
        {a.name: None} for a in adapter_registry.get() if a.name not in _adapters
    )
    await dump.yaml(_adapters, adapter_settings_path, sort_keys=True)
    _enabled_adapters = {a: m for a, m in _adapters.items() if m}
    for a in [a for a in adapter_registry.get() if a.name in _enabled_adapters]:
        a.enabled = True


# available_adapters.get().update(_available_adapters)
# for a in required_adapters.get():
#     _enabled_adapters = {a: _enabled_adapters.pop(a)} | _enabled_adapters
# enabled_adapters.get().update(_enabled_adapters)


def update_actions(pkg: Package, actions_path: Path) -> None:
    _actions = {
        a.stem: a
        for a in actions_path.iterdir()
        if a.is_file() and not a.name.startswith("_")
    }
    _pkg_path = actions_path.parent
    for action_name, path in _actions.items():
        _action = next(a for a in action_registry.get() if a.name == action_name)
        if _action:
            del _action
        action_registry.get().append(
            Action(name=action_name, pkg=pkg, path=AsyncPath(path))
        )


def register_package(_pkg_path: Path | None = None) -> None:
    _pkg_path = _pkg_path or Path(currentframe().f_back.f_code.co_filename).parent
    _pkg_name = _pkg_path.name
    _pkg = Package(name=_pkg_name, path=AsyncPath(_pkg_path))
    _actions_path = Path(_pkg_path / "actions")
    _adapters_path = Path(_pkg_path / "adapters")
    if _actions_path.exists():
        update_actions(_pkg, _actions_path)
        actions_source.searchpath.insert(0, _actions_path)
    if _adapters_path.exists():
        asyncio.run(update_adapters(_pkg, _adapters_path))
        adapters_source.searchpath.insert(0, _adapters_path)
    package_registry.get().append(_pkg)


if base_path.name not in ("acb", "crackerjack"):
    register_package()
