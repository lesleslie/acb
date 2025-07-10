import asyncio
import os
import sys
import tempfile
import typing as t
from contextvars import ContextVar
from functools import cache
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


class AdapterNotFound(Exception): ...


class AdapterNotInstalled(Exception): ...


class StaticImportError(ImportError):
    pass


AdapterClass = t.TypeVar("AdapterClass")


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
_enabled_adapters_cache: ContextVar[dict[str, Adapter]] = ContextVar(
    "_enabled_adapters_cache", default={}
)
_installed_adapters_cache: ContextVar[dict[str, Adapter]] = ContextVar(
    "_installed_adapters_cache", default={}
)
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


def _update_adapter_caches() -> None:
    enabled_cache = {}
    installed_cache = {}
    for adapter in adapter_registry.get():
        if adapter.enabled:
            enabled_cache[adapter.category] = adapter
        if adapter.installed:
            installed_cache[adapter.category] = adapter
    _enabled_adapters_cache.set(enabled_cache)
    _installed_adapters_cache.set(installed_cache)


adapter_registry.get().extend([*core_adapters])
_update_adapter_caches()


def get_adapter(category: str) -> Adapter | None:
    return _enabled_adapters_cache.get().get(category)


def get_adapters() -> list[Adapter]:
    return list(_enabled_adapters_cache.get().values())


def get_installed_adapter(category: str) -> Adapter | None:
    return _installed_adapters_cache.get().get(category)


def get_installed_adapters() -> list[Adapter]:
    return list(_installed_adapters_cache.get().values())


@cache
def get_adapter_class(category: str, name: str) -> type[t.Any]:
    module_path = f"acb.adapters.{category}.{name}"
    try:
        from importlib import import_module

        from inflection import camelize

        class_name = camelize(category)
        module = import_module(module_path)
        return getattr(module, class_name)
    except (ImportError, AttributeError) as e:
        raise StaticImportError(f"Failed to import {module_path}: {e}")


def try_import_adapter(category: str, name: str | None = None) -> type[t.Any] | None:
    if name is None:
        adapter_info = get_adapter(category)
        if adapter_info:
            name = adapter_info.name
        else:
            return None
    try:
        return get_adapter_class(category, name)
    except StaticImportError:
        return None


def import_adapter_fast(category: str, name: str | None = None) -> type[t.Any]:
    adapter_class = try_import_adapter(category, name)
    if adapter_class is None:
        available_adapters = list(_get_available_adapters(category))
        raise ImportError(
            f"Could not import {category} adapter '{name}'. "
            f"Available: {available_adapters}"
        )
    return adapter_class


def _get_available_adapters(category: str) -> t.Iterator[str]:
    for adapter in adapter_registry.get():
        if adapter.category == category:
            yield adapter.name


_adapter_config_loaded: bool = False


async def _ensure_adapter_configuration() -> None:
    global _adapter_config_loaded
    if _adapter_config_loaded or _should_skip_configuration():
        return
    _adapter_config_loaded = True
    try:
        await _setup_adapter_configuration()
    except Exception as e:
        print(f"ACB: Setup failed: {e}")
        import traceback

        traceback.print_exc()


def _should_skip_configuration() -> bool:
    from ..config import _library_usage_mode

    return _testing or "pytest" in sys.modules or _library_usage_mode


async def _setup_adapter_configuration() -> None:
    cwd_path = AsyncPath(Path.cwd())
    if await _should_skip_project_setup(cwd_path):
        return
    cwd_settings_path = cwd_path / "settings"
    cwd_adapter_settings_path = cwd_settings_path / "adapters.yml"
    await _create_adapter_settings_if_needed(
        cwd_settings_path, cwd_adapter_settings_path
    )
    await _load_and_apply_adapter_settings(cwd_adapter_settings_path)


async def _should_skip_project_setup(cwd_path: AsyncPath) -> bool:
    if cwd_path.stem == "acb":
        return True
    has_pyproject = await (cwd_path / "pyproject.toml").exists()
    if has_pyproject:
        has_src = await (cwd_path / "src").exists()
        has_acb_dir = await (cwd_path / "acb").exists()
        is_acb_package = (
            has_acb_dir and await (cwd_path / "acb" / "__init__.py").exists()
        )
        has_settings = await (cwd_path / "settings").exists()
        if has_settings:
            return False
        has_package_dir = await (cwd_path / cwd_path.stem).exists()
        return has_src or has_package_dir or is_acb_package

    return False


async def _create_adapter_settings_if_needed(
    cwd_settings_path: AsyncPath, cwd_adapter_settings_path: AsyncPath
) -> None:
    if _testing or "pytest" in sys.modules:
        return

    from ..config import _library_usage_mode

    if _library_usage_mode:
        return

    if not await cwd_adapter_settings_path.exists() and not _deployed:
        await cwd_settings_path.mkdir(exist_ok=True)
        categories = {a.category for a in adapter_registry.get()}
        settings_dict = {
            cat: None for cat in categories if cat not in ("logger", "config")
        }
        await cwd_adapter_settings_path.write_bytes(
            yaml_encode(settings_dict, sort_keys=True)
        )


async def _load_and_apply_adapter_settings(
    cwd_adapter_settings_path: AsyncPath,
) -> None:
    if not await cwd_adapter_settings_path.exists():
        return

    enabled_adapters = await _load_enabled_adapters(cwd_adapter_settings_path)
    await _ensure_package_registration()
    all_adapters = await _collect_all_adapters()
    _enable_configured_adapters(all_adapters, enabled_adapters)
    _update_adapter_caches()


async def _load_enabled_adapters(
    cwd_adapter_settings_path: AsyncPath,
) -> dict[str, str]:
    _adapters = yaml_decode(await cwd_adapter_settings_path.read_text())
    return {a: m for a, m in _adapters.items() if m}


async def _ensure_package_registration() -> None:
    from .. import ensure_registration_async, pkg_registry

    await ensure_registration_async()
    for pkg in pkg_registry.get():
        if not pkg.adapters:
            from contextlib import suppress

            with suppress(Exception):
                await register_adapters(pkg.path)


async def _collect_all_adapters() -> list[Adapter]:
    from .. import pkg_registry

    all_adapters = list(adapter_registry.get())
    for pkg in pkg_registry.get():
        for adapter in pkg.adapters:
            if adapter not in all_adapters:
                adapter_registry.get().append(adapter)
                all_adapters.append(adapter)

    return all_adapters


def _enable_configured_adapters(
    all_adapters: list[Adapter], enabled_adapters: dict[str, str]
) -> None:
    for adapter in all_adapters:
        if enabled_adapters.get(adapter.category) == adapter.name:
            adapter.enabled = True


async def _import_adapter_module_for_deps(adapter_category: str) -> None:
    from contextlib import suppress

    if adapter_category == "app":
        for adapter in adapter_registry.get():
            if adapter.category == adapter_category:
                with suppress(ImportError, AdapterNotFound, AdapterNotInstalled):
                    import_module(adapter.module)
                break


async def _find_adapter(adapter_category: str) -> Adapter:
    try:
        adapter = get_adapter(adapter_category)
        if adapter is not None:
            return adapter
        from contextlib import suppress

        current_path = AsyncPath(Path.cwd())
        for pkg_path in (current_path, current_path.parent):
            adapters_dir = pkg_path / "adapters"
            if await adapters_dir.exists():
                with suppress(Exception):
                    await register_adapters(pkg_path)
                    await _ensure_adapter_configuration()
                    adapter = get_adapter(adapter_category)
                    if adapter is not None:
                        return adapter
        raise AdapterNotFound(
            f"{adapter_category} adapter not found – check adapters.yml and ensure package registration"
        )
    except AttributeError:
        raise AdapterNotFound(
            f"{adapter_category} adapter not found – check adapters.yml"
        )


async def _load_module(adapter: Adapter) -> t.Any:
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
    return module


async def _initialize_adapter(
    adapter: Adapter, module: t.Any, adapter_category: str
) -> t.Any:
    from contextlib import suppress

    adapter_class: t.Any = getattr(module, adapter.class_name)
    adapter_settings = None
    adapter_settings_class_name = f"{adapter.class_name}Settings"
    if hasattr(module, adapter_settings_class_name):
        adapter_settings_class = getattr(module, adapter_settings_class_name)
        with suppress(Exception):
            adapter_settings = adapter_settings_class()
    if adapter_settings is not None:
        from ..config import Config

        config = depends.get(Config)
        setattr(config, adapter_category, adapter_settings)
    instance = depends.get(adapter_class)
    if hasattr(instance, "init"):
        init_result = instance.init()
        if hasattr(init_result, "__await__"):
            await init_result
    from ..logger import Logger

    logger = depends.get(Logger)
    logger.info(f"Adapter initialized: {adapter.class_name}")
    return adapter_class


async def _import_adapter(adapter_category: str) -> t.Any:
    if _testing or "pytest" in sys.modules:
        from unittest.mock import MagicMock

        return MagicMock()
    await _ensure_adapter_configuration()
    await _import_adapter_module_for_deps(adapter_category)
    adapter = await _find_adapter(adapter_category)
    module = await _load_module(adapter)
    adapter_class: t.Any = getattr(module, adapter.class_name)
    if adapter.installed:
        return adapter_class
    locks = _adapter_import_locks.get()
    if adapter_category not in locks:
        locks[adapter_category] = asyncio.Lock()
    async with locks[adapter_category]:
        if adapter.installed:
            return adapter_class
        try:
            adapter.installed = True
            return await _initialize_adapter(adapter, module, adapter_category)
        except Exception as e:
            adapter.installed = False
            raise AdapterNotInstalled(
                f"Failed to install {adapter.class_name} adapter: {e}"
            )


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
    if isinstance(adapter_categories, str):
        adapter_info = get_adapter(adapter_categories)
        adapter_name = adapter_info.name if adapter_info else None
        adapter_class = try_import_adapter(adapter_categories, adapter_name)
        if adapter_class:
            return adapter_class

        return import_adapter_with_context([adapter_categories])

    return import_adapter_with_context(adapter_categories)


def _extract_adapter_categories_from_stack() -> list[str]:
    frame_idx = 1
    for i in range(1, min(4, len(stack()))):
        frame_context = str(stack()[i][4]) if stack()[i][4] else ""
        if "import_adapter_with_context" in frame_context:
            frame_idx = i + 1
            break
    context = stack()[frame_idx][4]
    return [
        c.strip()
        for c in (context[0] if context else "")
        .split("=")[0]
        .strip()
        .lower()
        .split(",")
    ]


def _handle_testing_mode(adapter_categories: str | list[str] | None) -> t.Any:
    from unittest.mock import MagicMock

    if isinstance(adapter_categories, str):
        return MagicMock()
    if not adapter_categories:
        try:
            adapter_categories = _extract_adapter_categories_from_stack()
        except (IndexError, AttributeError, TypeError):
            return MagicMock()

    return tuple(MagicMock() for _ in adapter_categories)


def _normalize_adapter_categories(
    adapter_categories: str | list[str] | None,
) -> list[str]:
    if isinstance(adapter_categories, str):
        return [adapter_categories]

    if not adapter_categories:
        try:
            return _extract_adapter_categories_from_stack()
        except (IndexError, AttributeError, TypeError):
            raise ValueError(
                "Could not determine adapter categories from calling context"
            )

    return adapter_categories


def import_adapter_with_context(
    adapter_categories: str | list[str] | None = None,
) -> t.Any:
    if _testing or "pytest" in sys.modules:
        return _handle_testing_mode(adapter_categories)

    normalized_categories = _normalize_adapter_categories(adapter_categories)

    try:
        imported_adapters = asyncio.run(gather_imports(normalized_categories))
    except Exception as e:
        raise AdapterNotInstalled(
            f"Failed to install adapters {normalized_categories}: {e}"
        )

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
    registry = adapter_registry.get()
    for a in adapters:
        module = ".".join(a.module.split(".")[-2:])
        remove = next(
            (_a for _a in registry if ".".join(_a.module.split(".")[-2:]) == module),
            None,
        )
        if remove:
            registry.remove(remove)
        registry.append(a)
        _adapter_import_locks.get()[a.category] = asyncio.Lock()
    _update_adapter_caches()
    return adapters
