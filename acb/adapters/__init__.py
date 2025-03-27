import asyncio
import os
import sys
import typing as t
from contextvars import ContextVar
from importlib import import_module, util
from inspect import currentframe, stack
from pathlib import Path

from aiopath import AsyncPath
from inflection import camelize
from msgspec.yaml import decode as yaml_decode
from pydantic import BaseModel
from acb.actions.encode import yaml_encode
from acb.depends import depends

root_path: AsyncPath = AsyncPath(Path.cwd())
tmp_path: AsyncPath = root_path / "tmp"


class Adapter(BaseModel, arbitrary_types_allowed=True):
    name: str
    class_name: str
    category: str
    pkg: str = "acb"
    module: str = ""
    enabled: bool = False
    installed: bool = False
    path: AsyncPath = AsyncPath(Path(__file__) / "adapters")

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
            and self.category == other.category
            and self.pkg == other.pkg
            and self.module == other.module
        )


@t.runtime_checkable
class AdapterProtocol(t.Protocol):
    async def init(self) -> None: ...


adapter_registry: ContextVar[list[Adapter]] = ContextVar("adapter_registry", default=[])
_install_lock: ContextVar[list[str]] = ContextVar("install_lock", default=[])
_deployed: bool = os.getenv("DEPLOYED", "False").lower() == "true"
_testing: bool = os.getenv("TESTING", "False").lower() == "true"
settings_path: Path = Path(root_path / "settings")
app_settings_path: Path = settings_path / "app.yml"
adapter_settings_path: Path = settings_path / "adapters.yml"


class AdapterNotFound(Exception): ...


class AdapterNotInstalled(Exception): ...


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


async def _import_adapter(
    adapter_category: str, config: AdapterProtocol
) -> type[AdapterProtocol] | None:
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
        module = util.module_from_spec(spec)  # type: ignore
        spec.loader.exec_module(module)
        sys.modules[adapter.name] = module

    adapter_class: type[AdapterProtocol] = getattr(module, adapter.class_name)

    if not adapter.installed and adapter.category not in _install_lock.get():
        _install_lock.get().append(adapter.category)
        try:
            adapter_settings_class_name = f"{adapter.class_name}Settings"
            adapter_settings_class = getattr(module, adapter_settings_class_name)
            adapter_settings = adapter_settings_class()
            setattr(config, adapter_category, adapter_settings)
            await depends.get(adapter_class).init()
        except Exception as e:
            raise AdapterNotInstalled(
                f"Failed to install {adapter.class_name} adapter: {e}"
            )
        else:
            adapter.installed = True
            if adapter_category != "logger":
                logger = depends.get()
                logger.info(f"{adapter.class_name} adapter installed")
        finally:
            _install_lock.get().remove(adapter.category)

    return adapter_class


def import_adapter(
    adapter_categories: t.Optional[str | list[str]] = None,
) -> (
    AdapterProtocol
    | list[AdapterProtocol | Exception | str]
    | str
    | Exception
    | list[str | Exception]
):
    config = depends.get()

    if isinstance(adapter_categories, str):
        adapter_categories = [adapter_categories]
    if not adapter_categories:
        try:
            adapter_categories = [
                c.strip()
                for c in (
                    stack()[1][4][0].split("=")[0].strip().lower()  # type: ignore
                ).split(",")
            ]
        except (IndexError, AttributeError, TypeError):
            raise ValueError(
                "Could not determine adapter categories from calling context"
            )
    try:
        imports: list[t.Coroutine[t.Any, t.Any, t.Type[AdapterProtocol] | None]] = [
            _import_adapter(c, config) for c in adapter_categories
        ]
        # classes = asyncio.run(asyncio.gather(*imports, return_exceptions=True))  # type: ignore
        classes = asyncio.run(asyncio.gather(*imports))  # type: ignore
        if isinstance(classes, str | Exception):
            classes = [classes]
        return classes[0] if len(adapter_categories) < 2 else classes
    except Exception as err:
        raise AdapterNotInstalled(err)


def path_adapters(path: Path) -> dict[str, list[Path]]:
    return {
        a.stem: [
            m for m in a.iterdir() if not m.name.startswith("_") and m.suffix == ".py"
        ]
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


def register_adapters() -> list[Adapter]:
    adapters_path = (
        Path(currentframe().f_back.f_back.f_code.co_filename).parent / "adapters"
    )
    pkg_adapters = path_adapters(adapters_path)
    adapters: list[Adapter] = []
    for adapter_name, modules in pkg_adapters.items():
        _modules = extract_adapter_modules(modules, adapter_name)
        adapters.extend(_modules)
    if (
        not adapter_settings_path.exists()
        and not _deployed
        and not _testing
        and root_path.stem != "acb"
    ):
        settings_path.mkdir(exist_ok=True)
        categories = set()
        categories.update(a.category for a in adapter_registry.get() + adapters)
        adapter_settings_path.write_bytes(
            yaml_encode(
                {cat: None for cat in categories},
                sort_keys=True,
            )
        )
    _adapters = (
        {}
        if _testing or root_path.stem == "acb"
        else yaml_decode(adapter_settings_path.read_text())
    )
    _adapters.update(
        {a.category: None for a in adapters if a.category not in _adapters}
    )
    if not _testing and not root_path.stem == "acb":
        adapter_settings_path.write_bytes(yaml_encode(_adapters, sort_keys=True))
    enabled_adapters = {a: m for a, m in _adapters.items() if m}
    for a in [a for a in adapters if enabled_adapters.get(a.category) == a.name]:
        a.enabled = True
    registry = adapter_registry.get()
    for a in adapters:
        module = ".".join(a.module.split(".")[-2:])
        remove = next(
            (
                _a
                for _a in registry
                if ".".join(_a.module.split(".")[-2:]) == module and _a.pkg == "acb"
            ),
            None,
        )
        if remove:
            registry.remove(remove)
        if module in [".".join(_a.module.split(".")[-2:]) for _a in registry]:
            continue
        registry.append(a)
    return adapters
