import asyncio
import typing as t
from importlib import import_module
from inspect import currentframe
from pathlib import Path
from warnings import warn

import nest_asyncio
from acb import Adapter
from acb import adapter_registry
from acb import base_path
from acb.actions.encode import yaml_encode
from acb.depends import depends
from aiopath import AsyncPath
from inflection import camelize
from msgspec.yaml import decode as yaml_decode

nest_asyncio.apply()

settings_path: Path = Path(base_path / "settings")
app_settings_path: Path = settings_path / "app.yml"
adapter_settings_path: Path = settings_path / "adapters.yml"


def get_adapter(category: str) -> Adapter | None:
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
        if _adapter and _adapter.enabled and not _adapter.installed:
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


def register_adapters() -> None:
    _adapters_path = Path.cwd() / "adapters"
    _pkg = _adapters_path.parent.name
    for adapter, modules in {
        a.stem: [m for m in a.rglob("*.py") if not m.name.startswith("_")]
        for a in _adapters_path.iterdir()
        if a.is_dir() and not a.name.startswith("__")
    }.items():
        modules = [
            Adapter(name=m.stem, category=m.parent.stem, path=AsyncPath(m))
            for m in modules
        ]
        current_adapter = next(
            (a for a in adapter_registry.get() if a.category == adapter and a.enabled),
            None,
        )
        if current_adapter:
            adapter_registry.get().remove(current_adapter)
        adapter_registry.get().extend(modules)
    if not adapter_settings_path.exists():
        settings_path.mkdir(exist_ok=True)
        for i, adapter in enumerate(
            [a for a in adapter_registry.get() if a.category in ("logger", "secrets")]
        ):
            adapter.required = True
            _adapter = adapter_registry.get().pop(i)
            adapter_registry.get().insert(0, _adapter)
        required = [a for a in adapter_registry.get() if a.required]
        categories = {a.category for a in adapter_registry.get()}
        adapter_settings_path.write_bytes(
            yaml_encode(
                {cat: None for cat in categories}
                | {a.category: a.name for a in required},
                sort_keys=True,
            )
        )
    _adapters = yaml_decode(adapter_settings_path.read_text())
    _adapters.update(
        {
            a.category: None
            for a in adapter_registry.get()
            if a.category not in _adapters
        }
    )
    adapter_settings_path.write_bytes(yaml_encode(_adapters, sort_keys=True))
    _enabled_adapters = {a: m for a, m in _adapters.items() if m}
    for a in [
        a for a in adapter_registry.get() if _enabled_adapters.get(a.category) == a.name
    ]:
        a.enabled = True
    if _pkg != "acb":
        adapters_init = _adapters_path / "__init__.py"
        init_all = []
        init_all.extend([a.category for a in adapter_registry.get() if a.enabled])
        with adapters_init.open("w") as f:
            for adapter in [a for a in adapter_registry.get() if a.enabled]:
                if adapter.pkg == _pkg:
                    f.write(f"from . import {adapter.category}\n")
                else:
                    f.write(f"from {adapter.pkg}.adapters import {adapter.category}\n")
            f.write(f"\n__all__: list[str] = {init_all!r}\n")


register_adapters()
