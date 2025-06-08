import asyncio
import os
import sys
import tempfile
import typing as t
from contextvars import ContextVar
from importlib import import_module, util
from inspect import stack
from pathlib import Path

import nest_asyncio
import rich.repr
from anyio import Path as AsyncPath
from inflection import camelize
from msgspec.yaml import decode as yaml_decode
from pydantic import BaseModel, ConfigDict

from ..actions.encode import yaml_encode
from ..depends import depends

nest_asyncio.apply()
_deployed: bool = os.getenv("DEPLOYED", "False").lower() == "true"
_testing: bool = os.getenv("TESTING", "False").lower() == "true"
root_path: AsyncPath = AsyncPath(Path.cwd())
tmp_path: AsyncPath = root_path / "tmp"
adapters_path: AsyncPath = root_path / "adapters"
actions_path: AsyncPath = root_path / "actions"
settings_path: AsyncPath = root_path / "settings"
app_settings_path: AsyncPath = settings_path / "app.yml"
debug_settings_path: AsyncPath = settings_path / "debug.yml"
adapter_settings_path: AsyncPath = settings_path / "adapters.yml"
secrets_path: AsyncPath = (
    AsyncPath(Path(tempfile.mkdtemp(prefix="mock_secrets_")))
    if _testing or "pytest" in sys.modules
    else tmp_path / "secrets"
)
_install_lock: ContextVar[list[str]] = ContextVar("install_lock", default=[])
_adapter_import_locks: ContextVar[dict[str, asyncio.Lock]] = ContextVar(
    "_adapter_import_locks", default={}
)
default_adapters = dict(app="default", storage="file", cache="memory")


class AdapterNotFound(Exception): ...


class AdapterNotInstalled(Exception): ...


@t.runtime_checkable
class AdapterProtocol(t.Protocol):
    config: t.Any = None
    logger: t.Any = None

    async def init(self) -> None: ...


@rich.repr.auto
class Adapter(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    name: str
    class_name: str
    category: str
    pkg: str = "acb"
    module: str = ""
    enabled: bool = False
    installed: bool = False
    path: AsyncPath = AsyncPath(__file__)

    def __str__(self) -> str:
        return self.__repr__()

    def __hash__(self) -> int:
        return hash((self.name, self.class_name, self.category, self.pkg, self.module))

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Adapter):
            return False
        return (
            self.name == other.name
            and self.class_name == other.class_name
            and (self.category == other.category)
            and (self.pkg == other.pkg)
            and (self.module == other.module)
        )


adapter_registry: ContextVar[list[Adapter]] = ContextVar("adapter_registry", default=[])
core_adapters = [
    Adapter(
        name="config",
        module="acb.config",
        class_name="Config",
        category="config",
        enabled=True,
        installed=True,
        path=AsyncPath(__file__).parent / "config.py",
    ),
    Adapter(
        name="loguru",
        module="acb.logger",
        class_name="Logger",
        category="logger",
        enabled=True,
        installed=True,
        path=AsyncPath(__file__).parent / "logger.py",
    ),
]
adapter_registry.get().extend([*core_adapters])


def get_adapter(category: str) -> Adapter | None:
    adapter = next(
        (a for a in adapter_registry.get() if a.category == category and a.enabled),
        None,
    )
    return adapter


def get_adapters() -> list[Adapter]:
    return [a for a in adapter_registry.get() if a.enabled]


def get_installed_adapter(category: str) -> Adapter | None:
    adapter = next(
        (a for a in adapter_registry.get() if a.category == category and a.installed),
        None,
    )
    return adapter


def get_installed_adapters() -> list[Adapter]:
    return [a for a in adapter_registry.get() if a.installed]


async def _import_adapter(adapter_category: str) -> t.Any:
    if _testing or "pytest" in sys.modules:
        from unittest.mock import MagicMock

        return MagicMock()
    try:
        adapter = get_adapter(adapter_category)
        if adapter is None:
            raise AdapterNotFound(
                f"{adapter_category} adapter not found – check adapters.yml"
            )
    except AttributeError:
        raise AdapterNotFound(
            f"{adapter_category} adapter not found – check adapters.yml"
        )
    try:
        module = import_module(adapter.module)
    except ModuleNotFoundError:
        spec = util.spec_from_file_location(adapter.path.stem, adapter.path)
        if spec is None:
            raise AdapterNotFound(f"Failed to create module spec for {adapter.module}")
        module = util.module_from_spec(spec)
        if spec.loader is not None:
            spec.loader.exec_module(module)
        sys.modules[adapter.name] = module
    adapter_class: t.Any = getattr(module, adapter.class_name)
    if adapter.installed:
        return adapter_class
    async with _adapter_import_locks.get()[adapter_category]:
        if adapter.installed:
            return adapter_class
        try:
            adapter.installed = True
            adapter_settings_class_name = f"{adapter.class_name}Settings"
            adapter_settings_class = getattr(module, adapter_settings_class_name)
            adapter_settings = adapter_settings_class()
            from ..config import Config
            from ..logger import Logger

            config = depends.get(Config)
            setattr(config, adapter_category, adapter_settings)
            instance = depends.get(adapter_class)
            await instance.init()
            logger = depends.get(Logger)
            logger.info(f"Adapter initialized: {adapter.class_name}")
        except Exception as e:
            adapter.installed = False
            raise AdapterNotInstalled(
                f"Failed to install {adapter.class_name} adapter: {e}"
            )
    return adapter_class


async def gather_imports(adapter_categories: list[str]) -> t.Any:
    imports = [_import_adapter(category) for category in adapter_categories]
    _imports = await asyncio.gather(*imports, return_exceptions=True)
    results = []
    for result in _imports:
        if isinstance(result, Exception):
            raise result
        results.append(result)
    return results


def import_adapter(adapter_categories: str | list[str] | None = None) -> t.Any:
    if _testing or "pytest" in sys.modules:
        from unittest.mock import MagicMock

        if isinstance(adapter_categories, str):
            return MagicMock()
        if not adapter_categories:
            try:
                context = stack()[1][4]
                adapter_categories = [
                    c.strip()
                    for c in (context[0] if context else "")
                    .split("=")[0]
                    .strip()
                    .lower()
                    .split(",")
                ]
            except (IndexError, AttributeError, TypeError):
                return MagicMock()
        return tuple(MagicMock() for _ in adapter_categories)
    if isinstance(adapter_categories, str):
        adapter_categories = [adapter_categories]
    if not adapter_categories:
        try:
            context = stack()[1][4]
            adapter_categories = [
                c.strip()
                for c in (context[0] if context else "")
                .split("=")[0]
                .strip()
                .lower()
                .split(",")
            ]
        except (IndexError, AttributeError, TypeError):
            raise ValueError(
                "Could not determine adapter categories from calling context"
            )
    try:
        imported_adapters = asyncio.run(gather_imports(adapter_categories))
    except Exception as e:
        raise AdapterNotInstalled(f"Failed to install adapters: {e}")
    return (
        imported_adapters[0]
        if len(imported_adapters) == 1
        else tuple(imported_adapters)
    )


async def path_adapters(path: AsyncPath) -> dict[str, list[AsyncPath]]:
    return {
        a.stem: [
            m
            async for m in a.iterdir()
            if not m.name.startswith("_") and m.suffix == ".py"
        ]
        async for a in path.iterdir()
        if await a.is_dir() and (not a.name.startswith("__"))
    }


def create_adapter(
    path: AsyncPath,
    name: str | None = None,
    module: str | None = None,
    class_name: str | None = None,
    category: str | None = None,
    pkg: str | None = None,
    enabled: bool = False,
    installed: bool = False,
) -> Adapter:
    return Adapter(
        path=path,
        name=name or path.stem,
        class_name=class_name or camelize(path.parent.stem),
        category=category or path.parent.stem,
        module=module or ".".join(path.parts[-4:]).removesuffix(".py"),
        pkg=pkg or path.parent.parent.parent.stem,
        enabled=enabled,
        installed=installed,
    )


def extract_adapter_modules(modules: list[AsyncPath], adapter: str) -> list[Adapter]:
    adapter_modules = [create_adapter(p) for p in modules]
    return [a for a in adapter_modules if a.category == adapter]


async def register_adapters(path: AsyncPath) -> list[Adapter]:
    if _testing or "pytest" in sys.modules:
        return []
    adapters_path = path / "adapters"
    if not await adapters_path.exists():
        return []
    pkg_adapters = await path_adapters(adapters_path)
    adapters: list[Adapter] = []
    for adapter_name, modules in pkg_adapters.items():
        _modules = extract_adapter_modules(modules, adapter_name)
        adapters.extend(_modules)
    if (
        not await adapter_settings_path.exists()
        and (not _deployed)
        and (not _testing)
        and (root_path.stem != "acb")
    ):
        await settings_path.mkdir(exist_ok=True)
        categories = set()
        categories.update(a.category for a in adapter_registry.get() + adapters)
        await adapter_settings_path.write_bytes(
            yaml_encode(
                {cat: None for cat in categories if cat not in ("logger", "config")}
                | default_adapters,
                sort_keys=True,
            )
        )
    _adapters = (
        {}
        if _testing or root_path.stem == "acb"
        else yaml_decode(await adapter_settings_path.read_text())
    )
    _adapters.update(
        {a.category: None for a in adapters if a.category not in _adapters}
    )
    if not _testing and (not root_path.stem == "acb") and (not _deployed):
        await adapter_settings_path.write_bytes(yaml_encode(_adapters, sort_keys=True))
    enabled_adapters = {a: m for a, m in _adapters.items() if m}
    for a in [a for a in adapters if enabled_adapters.get(a.category) == a.name]:
        a.enabled = True
    registry = adapter_registry.get()
    for a in adapters:
        module = ".".join(a.module.split(".")[-2:])
        remove = next(
            (_a for _a in registry if ".".join(_a.module.split(".")[-2:]) == module),
            None,
        )
        if remove:
            registry.remove(remove)
        if module in [".".join(_a.module.split(".")[-2:]) for _a in registry]:
            continue
        registry.append(a)
        _adapter_import_locks.get()[a.category] = asyncio.Lock()
    return adapters
