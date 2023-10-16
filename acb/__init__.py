import asyncio
import typing as t
from contextvars import ContextVar
from importlib import import_module
from inspect import currentframe
from pathlib import Path
from warnings import warn

import nest_asyncio
from acb.actions.encode import dump
from acb.actions.encode import load
from acb.depends import depends
from aiopath import AsyncPath
from inflection import camelize
from pydantic import BaseModel

nest_asyncio.apply()

base_path: AsyncPath = AsyncPath(Path.cwd())
pkg_path: AsyncPath = AsyncPath(__file__).parent
actions_path = pkg_path / "actions"
adapters_path = pkg_path / "adapters"
tmp_path = base_path / "tmp"
settings_path: AsyncPath = base_path / "settings"
app_settings_path: AsyncPath = settings_path / "app.yml"
adapter_settings_path: AsyncPath = settings_path / "adapters.yml"


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


def get_adapter(category: str) -> Adapter:
    _adapter = next(
        (
            a
            for a in adapter_registry.get()
            if a.category == category and a.enabled is True
        ),
        None,
    )
    return _adapter


def install_required_adapters(adapter_settings: dict[str, t.Any]) -> None:
    required = getattr(adapter_settings, "requires")
    if isinstance(required, list) and len(required):
        for adapter in required:
            _adapter = get_adapter(adapter)
            load_adapter(_adapter.category)
            _adapter.required = True


def load_adapter(adapter_category: t.Optional[str] = None) -> t.Any:
    _pkg_path = Path(currentframe().f_code.co_filename).parent
    if adapter_category is None:
        adapter_category = Path(currentframe().f_back.f_code.co_filename).parent.stem
    try:
        _adapter = get_adapter(adapter_category)
        if _adapter.enabled and not _adapter.installed:
            _adapter_class_name = camelize(_adapter.category)
            _adapter_settings_class_name = f"{_adapter_class_name}Settings"
            _module = ".".join(_adapter.path.parts[-4:]).removesuffix(".py")
            try:
                _imported_module = import_module(_module)
            except ImportError as err:
                return warn(
                    f"\n\nERROR: could not import {adapter_category!r} adapter: {err}\n"
                )
            _adapter_class = getattr(_imported_module, _adapter_class_name)
            _adapter_settings_class = getattr(
                _imported_module, _adapter_settings_class_name
            )
            from acb.config import Config

            config = depends.get(Config)
            _adapter_settings = _adapter_settings_class()
            setattr(config, adapter_category, _adapter_settings)
            install_required_adapters(_adapter_settings)
            asyncio.run(depends.get(_adapter_class).init())
            _adapter.installed = True
            if adapter_category != "logger":
                from acb.adapters.logger import Logger

                logger = depends.get(Logger)
            else:
                logger = depends.get(_adapter_class)
            logger.info(f"{_adapter_class_name} adapter loaded")
            return _adapter_class
    except KeyError as err:
        if get_adapter(adapter_category).required:
            raise SystemExit(
                f"\n\nERROR: required adapter {adapter_category!r} not found: {err}\n"
            )
        warn(f"\n\nERROR: adapter {adapter_category!r} not found: {err}\n")


async def update_adapters(pkg: Package, adapters_path: Path) -> None:
    for adapter, modules in {
        a.stem: [m for m in a.rglob("*.py") if not m.name.startswith("_")]
        for a in adapters_path.iterdir()
        if a.is_dir() and not a.name.startswith("__")
    }.items():
        modules = [
            Adapter(name=m.stem, category=m.parent.stem, pkg=pkg, path=AsyncPath(m))
            for m in modules
        ]
        current_adapter = next(
            (a for a in adapter_registry.get() if a.category == adapter and a.enabled),
            None,
        )
        if current_adapter:
            adapter_registry.get().remove(current_adapter)
        adapter_registry.get().extend(modules)
    if not await adapter_settings_path.exists():
        await settings_path.mkdir(exist_ok=True)
        for i, adapter in enumerate(
            [a for a in adapter_registry.get() if a.category in ("logger", "secrets")]
        ):
            adapter.required = True
            _adapter = adapter_registry.get().pop(i)
            adapter_registry.get().insert(0, _adapter)
        required = [a for a in adapter_registry.get() if a.required]
        categories = {a.category for a in adapter_registry.get()}
        await dump.yaml(
            {cat: None for cat in categories} | {a.category: a.name for a in required},
            adapter_settings_path,
            sort_keys=True,
        )
    _adapters = await load.yaml(adapter_settings_path)
    _adapters.update(
        {
            a.category: None
            for a in adapter_registry.get()
            if a.category not in _adapters
        }
    )
    await dump.yaml(_adapters, adapter_settings_path, sort_keys=True)
    _enabled_adapters = {a: m for a, m in _adapters.items() if m}
    for a in [
        a for a in adapter_registry.get() if _enabled_adapters.get(a.category) == a.name
    ]:
        a.enabled = True
    if pkg.name != "acb":
        adapters_init = adapters_path / "__init__.py"
        init_all = []
        init_all.extend([a.category for a in adapter_registry.get() if a.enabled])
        with open(adapters_init, "w") as f:
            for adapter in [a for a in adapter_registry.get() if a.enabled]:
                if adapter.pkg.name == pkg.name:
                    f.write(f"from . import {adapter.category}\n")
                else:
                    f.write(
                        f"from {adapter.pkg.name}.adapters import"
                        f" {adapter.category}\n"
                    )
            f.write(f"\n__all__: list[str] = {init_all!r}\n")


def update_actions(pkg: Package, actions_path: Path) -> None:
    _actions = {
        a.stem: a
        for a in actions_path.iterdir()
        if a.is_file() and not a.name.startswith("_")
    }
    _pkg_path = actions_path.parent
    for action_name, path in _actions.items():
        _action = next(
            (a for a in action_registry.get() if a.name == action_name), None
        )
        if _action:
            del _action
        action_registry.get().append(
            Action(name=action_name, pkg=pkg, path=AsyncPath(path))
        )
    if pkg.name != "acb":
        actions_init = actions_path / "__init__.py"
        init_all = []
        init_all.extend([a.name for a in action_registry.get()])
        with open(actions_init, "w") as f:
            for action in action_registry.get():
                f.write(f"from {action.pkg.name}.actions import {action.name}\n")
            f.write(f"\n__all__: list[str] = {init_all!r}\n")


def register_package(_pkg_path: Path | None = None) -> None:
    _pkg_path = _pkg_path or Path(currentframe().f_back.f_code.co_filename).parent
    _pkg_name = _pkg_path.name
    _pkg = Package(name=_pkg_name, path=AsyncPath(_pkg_path))
    _actions_path = Path(_pkg_path / "actions")
    _adapters_path = Path(_pkg_path / "adapters")
    if _actions_path.exists():
        update_actions(_pkg, _actions_path)
    if _adapters_path.exists():
        asyncio.run(update_adapters(_pkg, _adapters_path))
    package_registry.get().append(_pkg)


if base_path.name not in ("acb", "crackerjack"):
    register_package()

# ic(adapter_registry.get())
# ic(action_registry.get())
# ic(package_registry.get())
