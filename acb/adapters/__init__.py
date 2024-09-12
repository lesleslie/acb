import asyncio
import sys
import typing as t
from abc import ABC, abstractmethod
from importlib import import_module, util
from inspect import currentframe, stack
from pathlib import Path

from aiopath import AsyncPath
from inflection import camelize
from msgspec.yaml import decode as yaml_decode
from acb import Adapter, adapter_registry, base_path
from acb.actions.encode import yaml_encode
from acb.depends import depends

settings_path: Path = Path(base_path / "settings")
app_settings_path: Path = settings_path / "app.yml"
adapter_settings_path: Path = settings_path / "adapters.yml"


class AdapterNotFound(Exception):
    pass


def get_adapter(category: str) -> Adapter | None:
    adapter = next(
        (a for a in adapter_registry.get() if a.category == category and a.enabled),
        None,
    )
    return adapter


def get_enabled_adapters() -> list[Adapter]:
    return [a for a in adapter_registry.get() if a.enabled]


def get_installed_adapters() -> list[Adapter]:
    return [a for a in adapter_registry.get() if a.installed]


async def _import_adapter(adapter_category: str, config: t.Any) -> t.Any:
    try:
        adapter = get_adapter(adapter_category)
    except AttributeError:
        raise AdapterNotFound(
            f"{adapter_category} adapter not found - please make sure one is "
            f" configured in app.yml"
        )
    try:
        module = import_module(adapter.module)
    except ModuleNotFoundError:
        spec = util.spec_from_file_location(adapter.path.stem, adapter.path)
        module = util.module_from_spec(spec)  # type: ignore
        spec.loader.exec_module(module)
        sys.modules[adapter.name] = module
    adapter_class = getattr(module, adapter.class_name)
    if not adapter.installed:
        adapter_settings_class_name = f"{adapter.class_name}Settings"
        adapter_class = getattr(module, adapter.class_name)
        adapter_settings_class = getattr(module, adapter_settings_class_name)
        adapter_settings = adapter_settings_class()
        setattr(config, adapter_category, adapter_settings)
        await depends.get(adapter_class).init()
        adapter.installed = True
        if adapter_category != "logger":
            logger = depends.get(import_adapter("logger"))
        else:
            logger = depends.get(adapter_class)
        logger.info(f"{adapter.class_name} adapter installed")
    return adapter_class


def import_adapter(adapter_categories: t.Optional[str | list[str]] = None) -> t.Any:
    from acb.config import Config

    config = depends.get(Config)
    if isinstance(adapter_categories, str):
        adapter_categories = [adapter_categories]
    if not adapter_categories:
        adapter_categories = [
            c.strip()
            for c in (
                stack()[1][4][0].split("=")[0].strip().lower()  # type: ignore
            ).split(",")
        ]
    classes = asyncio.run(
        asyncio.gather(  # type: ignore
            *[_import_adapter(c, config) for c in adapter_categories]
        )
    )
    if len(adapter_categories) < 2:
        return classes[0]
    return classes


def path_adapters(path: Path) -> dict[str, list[Path]]:
    return {
        a.stem: [m for m in a.rglob("*.py") if not m.name.startswith("_")]
        for a in path.iterdir()
        if a.is_dir() and not a.name.startswith("__")
    }


def create_adapter(path: Path) -> Adapter:
    return Adapter(
        name=path.stem,
        class_name=camelize(path.parent.stem),
        category=path.parent.stem,
        module=".".join(path.parts[-4:]).removesuffix(".py"),
        pkg=path.parent.parent.parent.stem,
        path=AsyncPath(path),
    )


def extract_adapter_modules(modules: list[Path], adapter: str) -> list[Adapter]:
    adapter_modules = [create_adapter(p) for p in modules]
    return [a for a in adapter_modules if a.category == adapter]


def register_adapters() -> None:
    adapters_path = Path(currentframe().f_back.f_code.co_filename).parent / "adapters"
    base_adapters = path_adapters(Path(base_path / "adapters"))
    pkg_adapters = path_adapters(adapters_path)
    for adapter_name, modules in (pkg_adapters | base_adapters).items():
        modules = extract_adapter_modules(modules, adapter_name)
        for module in modules:
            adapter_registry.get().append(module)
    if not adapter_settings_path.exists():
        settings_path.mkdir(exist_ok=True)
        categories = {a.category for a in adapter_registry.get()}
        adapter_settings_path.write_bytes(
            yaml_encode(
                {cat: None for cat in categories},
                sort_keys=True,
            )
        )
    adapters = yaml_decode(adapter_settings_path.read_text())
    adapters.update(
        {a.category: None for a in adapter_registry.get() if a.category not in adapters}
    )
    adapter_settings_path.write_bytes(yaml_encode(adapters, sort_keys=True))
    enabled_adapters = {a: m for a, m in adapters.items() if m}
    for a in [
        a for a in adapter_registry.get() if enabled_adapters.get(a.category) == a.name
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
