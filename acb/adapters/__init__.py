import asyncio
import typing as t
from abc import ABC
from abc import abstractmethod
from importlib import import_module
from inspect import currentframe
from inspect import stack
from pathlib import Path

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
        (a for a in adapter_registry.get() if a.category == category and a.enabled),
        None,
    )
    return _adapter


def get_installed_adapters() -> list[Adapter]:
    return [a for a in adapter_registry.get() if a.installed]


def get_module_name(adapter_path: Path) -> str:
    return ".".join(adapter_path.parts[-4:-1])


def import_adapter(adapter_category: t.Optional[str] = None) -> t.Any:
    if not adapter_category:
        adapter_category = (
            stack()[1][4][0].split("=")[0].strip().lower()  # type: ignore
        )
    _adapter_path = get_adapter(adapter_category).path
    _module_name = get_module_name(_adapter_path)
    _adapter_class = getattr(import_module(_module_name), camelize(adapter_category))
    return _adapter_class


def load_adapter(adapter_category: t.Optional[str] = None) -> t.Any:
    _pkg_path = Path(currentframe().f_code.co_filename).parent
    if adapter_category is None:
        adapter_category = Path(currentframe().f_back.f_code.co_filename).parent.stem
    _adapter = get_adapter(adapter_category)
    if _adapter and _adapter.enabled and not _adapter.installed:
        _adapter_class_name = camelize(_adapter.category)
        _adapter_settings_class_name = f"{_adapter_class_name}Settings"
        _module_name = ".".join(_adapter.path.parts[-4:]).removesuffix(".py")
        _imported_module = import_module(_module_name)
        _adapter_class = getattr(_imported_module, _adapter_class_name)
        _adapter_settings_class = getattr(
            _imported_module, _adapter_settings_class_name
        )
        from acb.config import Config

        config = depends.get(Config)
        _adapter_settings = _adapter_settings_class()
        setattr(config, adapter_category, _adapter_settings)
        asyncio.run(depends.get(_adapter_class).init())
        _adapter.installed = True
        _adapter.module = _module_name
        if adapter_category != "logger":
            logger = depends.get(import_adapter("logger"))
        else:
            logger = depends.get(_adapter_class)
        logger.info(f"{_adapter_class_name} adapter loaded")
        return _adapter_class


def path_adapters(path: Path) -> dict[str, list[Path]]:
    return {
        a.stem: [m for m in a.rglob("*.py") if not m.name.startswith("_")]
        for a in path.iterdir()
        if a.is_dir() and not a.name.startswith("__")
    }


def create_adapter(path: Path) -> Adapter:
    pkg = path.parent.parent.parent.stem
    return Adapter(
        name=path.stem,
        category=path.parent.stem,
        pkg=pkg,
        path=AsyncPath(path),
    )


def extract_adapter_modules(modules: list[Path], adapter: str) -> list[Adapter]:
    adapter_modules = [create_adapter(p) for p in modules]
    return [a for a in adapter_modules if a.category == adapter]


def register_adapters() -> None:
    _adapters_path = Path(currentframe().f_back.f_code.co_filename).parent / "adapters"
    base_adapters = path_adapters(Path(base_path / "adapters"))
    pkg_adapters = path_adapters(_adapters_path)
    for adapter_name, modules in (pkg_adapters | base_adapters).items():
        modules = extract_adapter_modules(modules, adapter_name)
        for module in modules:
            adapter_registry.get().append(module)
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


from acb.config import Config  # noqa: E402

Logger = import_adapter()


class AdapterBase(ABC):
    config: Config = depends()
    logger: Logger = depends()  # type: ignore

    @abstractmethod
    async def init(self) -> None:
        raise NotImplementedError
