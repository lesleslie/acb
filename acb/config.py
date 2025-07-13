import asyncio
import os
import sys
import typing as t
from contextlib import suppress
from contextvars import ContextVar
from enum import Enum
from functools import cached_property
from pathlib import Path
from secrets import token_bytes, token_urlsafe
from string import punctuation
from typing import TypeVar
from weakref import WeakKeyDictionary

try:
    import nest_asyncio
except ImportError:
    nest_asyncio = None
import rich.repr
from anyio import Path as AsyncPath
from inflection import titleize, underscore
from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator
from pydantic._internal._utils import deep_update
from pydantic.dataclasses import dataclass
from pydantic.fields import FieldInfo
from pydantic_settings import SettingsConfigDict

T = TypeVar("T")

from .actions.encode import dump, load
from .adapters import (
    _deployed,
    _testing,
    adapter_registry,
    import_adapter,
    root_path,
    secrets_path,
    settings_path,
    tmp_path,
)
from .depends import depends

if not _testing:
    if nest_asyncio:
        nest_asyncio.apply()
project: str = ""
app_name: str = ""
debug: dict[str, bool] = {}
_app_secrets: ContextVar[set[str]] = ContextVar("_app_secrets", default=set())

_config_initialized: bool = False
_library_usage_mode: bool = False


def _detect_library_usage() -> bool:
    if any(cmd in sys.argv[0] for cmd in ("pip", "setup.py", "build", "install")):
        return True
    if _testing or "pytest" in sys.modules:
        return False
    if "ACB_LIBRARY_MODE" in os.environ:
        return os.environ["ACB_LIBRARY_MODE"].lower() == "true"
    return Path.cwd().name != "acb"


def _is_pytest_test_context() -> bool:
    if "pytest" not in sys.modules:
        return False
    from contextlib import suppress

    with suppress(Exception):
        import inspect

        for frame_info in inspect.stack():
            filename = frame_info.filename
            if "acb/tests/" in filename or filename.endswith(
                "/acb/tests/test_config.py",
            ):
                return True
    return False


def _is_main_module_local() -> bool:
    main_module = sys.modules.get("__main__")
    if (
        not main_module
        or not hasattr(main_module, "__file__")
        or main_module.__file__ is None
    ):
        return False
    main_file = Path(main_module.__file__)
    cwd = Path.cwd()
    return main_file.parent == cwd or "acb" in str(main_file)


def _should_initialize_eagerly() -> bool:
    if _is_pytest_test_context():
        return True
    if _testing:
        return True
    if _detect_library_usage():
        return False
    return _is_main_module_local()


_library_usage_mode = _detect_library_usage()


class Platform(str, Enum):
    aws = "aws"
    gcp = "gcp"
    azure = "azure"
    cloudflare = "cloudflare"


async def get_version() -> str:
    pyproject_toml = root_path.parent / "pyproject.toml"
    if await pyproject_toml.exists():
        data = await load.toml(pyproject_toml)
        return data.get("project", {}).get("version", "0.1.0")
    return "0.1.0"


def get_version_default() -> str:
    return asyncio.run(get_version())


def gen_password(size: int = 10) -> str:
    return token_urlsafe(size)


class PydanticSettingsProtocol(t.Protocol):
    adapter_name: str
    secrets_path: AsyncPath
    settings_cls: type["Settings"]
    model_config: SettingsConfigDict

    def __init__(
        self,
        settings_cls: type["Settings"],
        secrets_path: AsyncPath = ...,
    ) -> None: ...
    def get_model_secrets(self) -> dict[str, FieldInfo]: ...
    async def __call__(self) -> dict[str, t.Any]: ...
    def __repr__(self) -> str: ...


class PydanticSettingsSource:
    adapter_name: str = "app"
    settings_cls: type["Settings"]
    model_config = SettingsConfigDict(arbitrary_types_allowed=True)

    def __init__(
        self,
        settings_cls: type["Settings"],
        secrets_path: AsyncPath | None = None,
    ) -> None:
        from acb.adapters import secrets_path as sp

        self.settings_cls = settings_cls
        self.adapter_name = underscore(
            self.settings_cls.__name__.replace("Settings", ""),
        )
        self.secrets_path = secrets_path if secrets_path is not None else sp
        self.config = settings_cls.model_config

    def get_model_secrets(self) -> dict[str, FieldInfo]:
        return {
            f"{self.adapter_name}_{n}": v
            for n, v in self.settings_cls.model_fields.items()
            if v.annotation is SecretStr
        }

    async def __call__(self) -> dict[str, t.Any]:
        raise NotImplementedError

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(secrets_path={self.secrets_path!r})"


class InitSettingsSource(PydanticSettingsSource):
    def __init__(
        self,
        settings_cls: type["Settings"],
        init_kwargs: dict[str, t.Any],
    ) -> None:
        self.init_kwargs = init_kwargs
        super().__init__(settings_cls=settings_cls)

    async def __call__(self) -> dict[str, t.Any]:
        return self.init_kwargs


class UnifiedSettingsSource(PydanticSettingsSource):
    def __init__(
        self,
        settings_cls: type["Settings"],
        init_kwargs: dict[str, t.Any] | None = None,
        secrets_path: AsyncPath | None = None,
    ) -> None:
        super().__init__(settings_cls, secrets_path)
        self.init_kwargs = init_kwargs or {}

    @cached_property
    def secret_manager(self) -> t.Any:
        try:
            return depends.get()
        except Exception:
            return None

    def _get_test_secret_data(self) -> dict[str, t.Any]:
        data: dict[str, t.Any] = {}
        model_secrets = self.get_model_secrets()
        for field_key, field_info in model_secrets.items():
            field_name = field_key.removeprefix(f"{self.adapter_name}_")
            if hasattr(field_info, "default") and field_info.default is not None:
                data[field_name] = field_info.default
            else:
                data[field_name] = SecretStr(f"test_secret_for_{field_name}")
        return data

    def _get_default_settings(self) -> dict[str, t.Any]:
        return {
            name: info.default
            for name, info in self.settings_cls.model_fields.items()
            if info.annotation is not SecretStr
        }

    def _update_global_variables(self, settings: dict[str, t.Any]) -> None:
        global project, app_name, debug
        if self.adapter_name == "debug":
            debug = settings
        elif self.adapter_name == "app":
            if _testing or _library_usage_mode:
                project = "test_project" if _testing else "library_project"
                app_name = "test_app" if _testing else "library_app"
            else:
                project = settings.get("project", "")
                app_name = settings.get("name", "")

    async def _get_file_secret(self, field_name: str) -> SecretStr | None:
        path = self.secrets_path / field_name
        if await path.is_file():
            return SecretStr((await path.read_text()).strip())
        return None

    async def _get_manager_secret(
        self,
        field_key: str,
        field_info: t.Any,
    ) -> SecretStr | None:
        if not self.secret_manager:
            return None

        stored_field_key = f"{app_name}_{field_key}"
        secret_path = self.secrets_path / field_key

        try:
            manager_secrets = await self.secret_manager.list(self.adapter_name)
            if not await secret_path.exists() and field_key not in manager_secrets:
                await self.secret_manager.create(
                    stored_field_key,
                    field_info.default.get_secret_value(),
                )

            secret = await self.secret_manager.get(stored_field_key)
            await secret_path.write_text(secret)
            return SecretStr(secret)
        except Exception:
            return None

    async def _load_secrets(self) -> dict[str, t.Any]:
        if _testing or _library_usage_mode:
            return self._get_test_secret_data()
        data: dict[str, t.Any] = {}
        model_secrets = self.get_model_secrets()
        self.secrets_path = await AsyncPath(self.secrets_path).expanduser()
        if not await self.secrets_path.exists():
            await self.secrets_path.mkdir(parents=True, exist_ok=True)
        for field_key, field_info in model_secrets.items():
            cleaned_field_key = field_key.removeprefix(f"{app_name}_")
            if cleaned_field_key in _app_secrets.get():
                continue
            field_name = cleaned_field_key.removeprefix(f"{self.adapter_name}_")
            secret_value = await self._get_file_secret(cleaned_field_key)
            if secret_value is None:
                secret_value = await self._get_manager_secret(field_key, field_info)
            if secret_value is not None:
                data[field_name] = secret_value
                _app_secrets.get().add(cleaned_field_key)

        return data

    async def _load_yaml_settings(self) -> dict[str, t.Any]:
        if self.adapter_name == "secret":
            return {}
        if _testing or _library_usage_mode:
            return self._handle_testing_mode()
        yml_path = AsyncPath(settings_path / f"{self.adapter_name}.yml")
        await self._create_default_settings_file(yml_path)
        yml_settings = await self._load_settings_from_file(yml_path)
        yml_settings = self._process_debug_settings(yml_settings)
        await self._update_settings_file(yml_path, yml_settings)
        self._update_global_variables(yml_settings)
        return yml_settings

    def _handle_testing_mode(self) -> dict[str, t.Any]:
        default_settings = self._get_default_settings()
        self._update_global_variables(default_settings)
        return default_settings

    async def _create_default_settings_file(self, yml_path: AsyncPath) -> None:
        if await yml_path.exists() or _deployed:
            return
        dump_settings = self._get_dump_settings()
        if self._should_create_settings_file(dump_settings):
            await dump.yaml(dump_settings, yml_path)

    def _get_dump_settings(self) -> dict[str, t.Any]:
        return {
            name: info.default
            for name, info in self.settings_cls.model_fields.items()
            if info.annotation is not SecretStr
            and "Optional" not in str(info.annotation)
        }

    def _should_create_settings_file(self, dump_settings: dict[str, t.Any]) -> bool:
        return bool(dump_settings) and any(
            value is not None and value not in ({}, [])
            for value in dump_settings.values()
        )

    async def _load_settings_from_file(self, yml_path: AsyncPath) -> dict[str, t.Any]:
        if await yml_path.exists():
            return await load.yaml(yml_path)
        return {}

    def _process_debug_settings(
        self,
        yml_settings: dict[str, t.Any],
    ) -> dict[str, t.Any]:
        if self.adapter_name != "debug":
            return yml_settings

        for adapter in adapter_registry.get():
            if adapter.category not in (yml_settings.keys() or ("config", "logger")):
                yml_settings[adapter.category] = False
        return yml_settings

    async def _update_settings_file(
        self,
        yml_path: AsyncPath,
        yml_settings: dict[str, t.Any],
    ) -> None:
        if not self._should_update_settings_file(yml_settings):
            return
        await dump.yaml(yml_settings, yml_path, sort_keys=True)

    def _should_update_settings_file(self, yml_settings: dict[str, t.Any]) -> bool:
        return (
            not _deployed
            and bool(yml_settings)
            and any(
                value is not None and value not in ({}, [])
                for value in yml_settings.values()
            )
        )

    async def __call__(self) -> dict[str, t.Any]:
        data = {}
        data.update(self.init_kwargs)
        if _testing or _library_usage_mode or Path.cwd().name != "acb":
            yaml_data = await self._load_yaml_settings()
            for field_name, field in yaml_data.items():
                if field is not None:
                    data[field_name] = field
        secrets_data = await self._load_secrets()
        data.update(secrets_data)

        return data


class SettingsProtocol(t.Protocol):
    model_config: t.ClassVar[SettingsConfigDict]

    def __init__(self, _secrets_path: AsyncPath = ..., **values: t.Any) -> None: ...

    _settings_build_values: t.Callable[..., t.Awaitable[dict[str, t.Any]]]
    settings_customize_sources: t.Callable[..., tuple[PydanticSettingsProtocol, ...]]


@rich.repr.auto
class Settings(BaseModel):
    model_config = SettingsConfigDict(
        extra="allow",
        arbitrary_types_allowed=True,
        validate_default=True,
        secrets_dir=Path(secrets_path),
        protected_namespaces=("model_", "settings_"),
    )

    def __init__(
        self,
        _secrets_path: AsyncPath = secrets_path,
        **values: t.Any,
    ) -> None:
        build_settings_coro = self._settings_build_values(
            values,
            _secrets_path=_secrets_path,
        )
        build_settings = asyncio.run(build_settings_coro)
        super().__init__(**build_settings)

    async def _settings_build_values(
        self,
        init_kwargs: dict[str, t.Any],
        _secrets_path: AsyncPath = secrets_path,
    ) -> dict[str, t.Any]:
        unified_source = UnifiedSettingsSource(
            self.__class__,
            init_kwargs=init_kwargs,
            secrets_path=_secrets_path,
        )
        sources = self.settings_customize_sources(
            settings_cls=self.__class__,
            unified_source=t.cast("PydanticSettingsProtocol", unified_source),
        )
        return deep_update(*reversed([await source() for source in sources]))

    @classmethod
    def settings_customize_sources(
        cls,
        settings_cls: type["Settings"],
        unified_source: PydanticSettingsProtocol,
    ) -> tuple[PydanticSettingsProtocol, ...]:
        return (unified_source,)


class DebugSettings(Settings):
    production: bool = False
    secrets: bool = False
    logger: bool = False


class AppSettings(Settings):
    name: str = root_path.stem
    secret_key: SecretStr = SecretStr(token_urlsafe(32))
    secure_salt: SecretStr = SecretStr(str(token_bytes(32)))
    title: str | None = None
    domain: str | None = None
    platform: Platform | None = None
    project: str | None = None
    region: str | None = None
    timezone: str | None = "US/Pacific"
    version: str | None = Field(default_factory=get_version_default)

    def __init__(self, **values: t.Any) -> None:
        super().__init__(**values)
        self.title = self.title or titleize(self.name)

    @field_validator("name")
    @classmethod
    def cloud_compliant_app_name(cls, v: str) -> str:
        not_ok = [" ", "_", "."]
        _name = v
        for p in not_ok:
            _name = _name.replace(p, "-")
        for p in punctuation.replace("-", ""):
            _name = _name.replace(p, "")
        app_name = _name.strip("-").lower()
        if len(app_name) < 3:
            msg = "App name to short"
            raise SystemExit(msg)
        if len(app_name) > 63:
            msg = "App name to long"
            raise SystemExit(msg)
        return app_name


class _LibraryDebugSettings:
    def __init__(self) -> None:
        self.production = False
        self.secrets = False
        self.logger = False


class _LibraryAppSettings:
    def __init__(self, name: str = "library_app") -> None:
        self.name = name
        self.secret_key = SecretStr(token_urlsafe(32))
        self.secure_salt = SecretStr(str(token_bytes(32)))
        self.title = titleize(name)
        self.domain = None
        self.platform = None
        self.project = None
        self.region = None
        self.timezone = "US/Pacific"
        self.version = "0.1.0"


_adapter_instances: dict[type, t.Any] = {}


def get_singleton_instance[T](cls: type[T], *args: t.Any, **kwargs: t.Any) -> T:
    if cls not in _adapter_instances:
        _adapter_instances[cls] = cls(*args, **kwargs)
    return _adapter_instances[cls]


@t.runtime_checkable
class ConfigProtocol(t.Protocol):
    deployed: bool
    root_path: AsyncPath
    secrets_path: AsyncPath
    settings_path: AsyncPath
    tmp_path: AsyncPath
    debug: DebugSettings | None
    app: AppSettings | None

    def init(self) -> None: ...


@rich.repr.auto
@dataclass(config=ConfigDict(arbitrary_types_allowed=True, extra="allow"))
class Config:
    deployed: bool = _deployed
    root_path: AsyncPath = root_path
    secrets_path: AsyncPath = secrets_path
    settings_path: AsyncPath = settings_path
    tmp_path: AsyncPath = tmp_path
    _debug: DebugSettings | None = None
    _app: AppSettings | None = None
    _initialized: bool = False

    def init(self, force: bool = False) -> None:
        global _config_initialized
        if _library_usage_mode and not force and not _testing:
            return
        if self._initialized and not force:
            return
        self._debug = DebugSettings()
        self._app = AppSettings()
        self._initialized = True
        _config_initialized = True

    def ensure_initialized(self) -> None:
        if not self._initialized:
            if _library_usage_mode:
                self._debug = t.cast("DebugSettings", _LibraryDebugSettings())
                self._app = t.cast("AppSettings", _LibraryAppSettings())
                self._initialized = True
            else:
                self.init(force=True)

    @property
    def debug(self) -> DebugSettings | None:
        if self._debug is None and not self._initialized:
            self.ensure_initialized()
        return self._debug

    @property
    def app(self) -> AppSettings | None:
        if self._app is None and not self._initialized:
            self.ensure_initialized()
        return self._app

    @app.setter
    def app(self, value: AppSettings | None) -> None:
        self._app = value

    def __getattr__(self, item: str) -> t.Any:
        if item in self.__dict__:
            return self.__dict__[item]
        if "." in item:
            parts = item.split(".")
            current_level = self
            for part in parts:
                if hasattr(current_level, part):
                    current_level = getattr(current_level, part)
            return current_level
        if item not in ("debug", "app") and not item.startswith("_"):
            with suppress(Exception):
                from .adapters import get_adapter

                adapter = get_adapter(item)
                if adapter and hasattr(adapter, "settings"):
                    return adapter.settings  # type: ignore[misc]
        msg = f"'Config' object has no attribute '{item}'"
        raise AttributeError(msg)


depends.set(Config, get_singleton_instance(Config))

if _should_initialize_eagerly():
    depends.get(Config).init()

_ADAPTER_LOCKS: WeakKeyDictionary[t.Any, t.Any] = WeakKeyDictionary()

Logger = None


@rich.repr.auto
class AdapterBase:
    config: Config = depends()

    @property
    def logger(self) -> t.Any:
        if not hasattr(self, "_logger"):
            try:
                Logger = import_adapter("logger")
                self._logger = depends.get(Logger)
            except Exception:
                import logging

                self._logger = logging.getLogger(self.__class__.__name__)
        return self._logger

    @logger.setter
    def logger(self, value: t.Any) -> None:
        self._logger = value

    @logger.deleter
    def logger(self) -> None:
        if hasattr(self, "_logger"):
            delattr(self, "_logger")

    def __init__(self, **kwargs: t.Any) -> None:
        self._client = None
        self._resource_cache: dict[str, t.Any] = {}
        self._initialization_args = kwargs
        if self not in _ADAPTER_LOCKS:
            _ADAPTER_LOCKS[self] = asyncio.Lock()

    async def _ensure_client(self) -> t.Any:
        if self._client is None:
            lock = _ADAPTER_LOCKS[self]
            async with lock:
                if self._client is None:
                    self._client = await self._create_client()
        return self._client

    async def _create_client(self) -> t.Any:
        msg = "Subclasses must implement _create_client()"
        raise NotImplementedError(msg)

    async def _ensure_resource(
        self,
        resource_name: str,
        factory_func: t.Callable[[], t.Awaitable[t.Any]],
    ) -> t.Any:
        if resource_name not in self._resource_cache:
            lock = _ADAPTER_LOCKS[self]
            async with lock:
                if resource_name not in self._resource_cache:
                    self._resource_cache[resource_name] = await factory_func()
        return self._resource_cache[resource_name]

    async def _cleanup_resources(self) -> None:
        if self._client is not None:
            if hasattr(self._client, "close"):
                await self._client.close()
            elif hasattr(self._client, "aclose"):
                await self._client.aclose()
        for resource in self._resource_cache.values():
            if hasattr(resource, "close"):
                try:
                    await resource.close()
                except Exception as e:
                    self.logger.warning(f"Error closing resource: {e}")

    async def init(self) -> None:
        pass
