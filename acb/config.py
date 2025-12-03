import sys
from contextvars import ContextVar
from enum import Enum
from functools import cached_property
from pathlib import Path
from secrets import token_bytes, token_urlsafe
from string import punctuation
from weakref import WeakKeyDictionary

import asyncio

# Removed nest_asyncio import - not needed in library code
import rich.repr
import typing as t
from anyio import Path as AsyncPath
from contextlib import suppress
from inflection import titleize, underscore
from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator
from pydantic.dataclasses import dataclass
from pydantic.fields import FieldInfo
from pydantic_settings import SettingsConfigDict
from typing import TypeVar

from .actions.encode import dump, load
from .adapters import (
    _deployed,
    _ensure_adapter_registry_initialized,
    _testing,
    import_adapter,
    root_path,
    secrets_path,
    settings_path,
    tmp_path,
)

# Global state is now managed by ACBContext - these are kept for backward compatibility
from .context import get_context
from .depends import Inject, depends, get_container


# Replaced internal pydantic API with public implementation
def deep_update(*dicts: dict[str, t.Any]) -> dict[str, t.Any]:
    """Deep merge multiple dictionaries."""
    result: dict[str, t.Any] = {}
    for d in dicts:
        if isinstance(d, dict):
            for key, value in d.items():
                if (
                    key in result
                    and isinstance(result[key], dict)
                    and isinstance(value, dict)
                ):
                    result[key] = deep_update(result[key], value)
                else:
                    result[key] = value
    return result


T = TypeVar("T")

# Module-level variables that delegate to context
# These maintain backward compatibility
project: str = ""
app_name: str = ""
debug: dict[str, bool] = {}

# Library usage mode detection - determines if ACB is used as a library vs application
_library_usage_mode: bool = (
    _testing or "pytest" in sys.modules or Path.cwd().name != "acb"
)

_app_secrets: ContextVar[set[str]] = ContextVar("_app_secrets", default=set())


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
    context = get_context()
    if context.is_testing_mode():
        return True
    if _testing:
        return True
    if context.is_library_mode():
        return False
    return _is_main_module_local()


# Library usage mode is now handled by ACBContext


class Platform(str, Enum):
    aws = "aws"
    gcp = "gcp"
    azure = "azure"
    cloudflare = "cloudflare"


async def get_version() -> str:
    pyproject_toml = root_path.parent / "pyproject.toml"
    if await pyproject_toml.exists():
        data = await load.toml(pyproject_toml)
        version = data.get("project", {}).get("version", "0.1.0")
        return str(version)
    return "0.1.0"


def get_version_default() -> str:
    """Get version synchronously for default field values.

    Note: This is a fallback for synchronous contexts.
    For proper async usage, use get_version() directly.
    """
    # Fallback to a default version if we can't run async code
    try:
        import asyncio

        asyncio.get_running_loop()
        # If we're in an async context, we shouldn't use this function
        msg = "Use await get_version() in async context"
        raise RuntimeError(msg)
    except RuntimeError:
        # No event loop running, return a sensible default
        return "0.1.0"


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
            return depends.get("secret_manager")
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

    @staticmethod
    def _is_special_mode() -> bool:
        """Check if in testing or library mode (skip YAML settings)."""
        return get_context().is_testing_mode() or get_context().is_library_mode()

    def _update_global_variables(self, settings: dict[str, t.Any]) -> None:
        global project, app_name, debug
        if self.adapter_name == "debug":
            debug = settings
        elif self.adapter_name == "app":
            if self._is_special_mode():
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
        if self._is_special_mode():
            return self._get_test_secret_data()
        data: dict[str, t.Any] = {}
        model_secrets = self.get_model_secrets()
        self.secrets_path: AsyncPath = await AsyncPath(
            str(self.secrets_path),
        ).expanduser()
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
        if self._is_special_mode():
            return self._handle_testing_mode()
        yaml_path = AsyncPath(str(settings_path / f"{self.adapter_name}.yaml"))
        await self._create_default_settings_file(yaml_path)
        yaml_settings = await self._load_settings_from_file(yaml_path)
        yaml_settings = self._process_debug_settings(yaml_settings)
        await self._update_settings_file(yaml_path, yaml_settings)
        self._update_global_variables(yaml_settings)
        return yaml_settings

    def _handle_testing_mode(self) -> dict[str, t.Any]:
        default_settings = self._get_default_settings()
        self._update_global_variables(default_settings)
        return default_settings

    async def _create_default_settings_file(self, yaml_path: AsyncPath) -> None:
        if await yaml_path.exists() or _deployed:
            return
        dump_settings = self._get_dump_settings()
        if self._should_create_settings_file(dump_settings):
            await dump.yaml(dump_settings, yaml_path)

    def _get_dump_settings(self) -> dict[str, t.Any]:
        return {
            name: info.default
            for name, info in self.settings_cls.model_fields.items()
            if info.annotation is not SecretStr
            and "Optional" not in str(info.annotation)
        }

    @staticmethod
    def _has_valid_settings(settings: dict[str, t.Any]) -> bool:
        """Check if settings dict contains any non-empty, non-None values."""
        return bool(settings) and any(
            value is not None and value not in ({}, []) for value in settings.values()
        )

    def _should_create_settings_file(self, dump_settings: dict[str, t.Any]) -> bool:
        return self._has_valid_settings(dump_settings)

    @staticmethod
    async def _load_settings_from_file(yaml_path: AsyncPath) -> dict[str, t.Any]:
        if await yaml_path.exists():
            result = await load.yaml(yaml_path)
            return dict(result) if result else {}
        return {}

    def _process_debug_settings(
        self,
        yaml_settings: dict[str, t.Any],
    ) -> dict[str, t.Any]:
        if self.adapter_name != "debug":
            return yaml_settings

        for adapter in _ensure_adapter_registry_initialized():
            if adapter.category not in (yaml_settings.keys() or ("config", "logger")):
                yaml_settings[adapter.category] = False
        return yaml_settings

    async def _update_settings_file(
        self,
        yaml_path: AsyncPath,
        yaml_settings: dict[str, t.Any],
    ) -> None:
        if self._should_update_settings_file(yaml_settings):
            await dump.yaml(yaml_settings, yaml_path, sort_keys=True)

    def _should_update_settings_file(self, yaml_settings: dict[str, t.Any]) -> bool:
        return not _deployed and self._has_valid_settings(yaml_settings)

    async def __call__(self) -> dict[str, t.Any]:
        data = self.init_kwargs.copy()
        if _testing or _library_usage_mode or Path.cwd().name != "acb":
            yaml_data = await self._load_yaml_settings()
            data.update({k: v for k, v in yaml_data.items() if v is not None})
        data.update(await self._load_secrets())
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
        secrets_dir=Path(str(secrets_path)),
        protected_namespaces=("model_", "settings_"),
    )

    def __init__(
        self,
        _secrets_path: AsyncPath = secrets_path,
        **values: t.Any,
    ) -> None:
        """Initialize Settings synchronously.

        For full async initialization with secrets loading, use:
        settings = await Settings.create_async()
        """
        # For library mode or testing, use simplified initialization
        from .context import get_context

        context = get_context()

        if context.is_library_mode() or context.is_testing_mode():
            # Simple sync initialization for library/testing contexts
            super().__init__(**values)
        else:
            # For application contexts, we need to defer to async initialization
            # This creates a minimal instance that will be properly initialized later
            try:
                import asyncio

                # Check if we're in a running event loop
                asyncio.get_running_loop()
                # If an event loop is already running, fall back to a synchronous
                # initialization to avoid crashes in ASGI startup paths.
                super().__init__(**values)
            except RuntimeError as e:
                if "no running event loop" in str(e):
                    # No event loop - create minimal instance for now
                    super().__init__(**values)
                else:
                    raise

    @classmethod
    async def create_async(
        cls,
        _secrets_path: AsyncPath = secrets_path,
        **values: t.Any,
    ) -> "Settings":
        """Create Settings instance with full async initialization.

        This method properly loads secrets and performs async operations.
        """
        instance = cls.__new__(cls)
        build_settings = await instance._settings_build_values(
            values,
            _secrets_path=_secrets_path,
        )
        BaseModel.__init__(instance, **build_settings)
        return instance

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

    # --- Helpers -------------------------------------------------------------
    def get_data_dir(self, field_name: str) -> Path:
        """Return a directory path from a Path field and ensure it exists.

        Expands '~' and creates the directory if missing. Raises ValueError
        when the field doesn't exist or is not a Path instance.
        """
        if not hasattr(self, field_name):
            msg = f"Settings class has no field '{field_name}'"
            raise ValueError(msg)
        value = getattr(self, field_name)
        if not isinstance(value, Path):
            msg = f"Field '{field_name}' must be a Path, got {type(value).__name__}"
            raise ValueError(
                msg,
            )
        expanded = value.expanduser()
        expanded.mkdir(parents=True, exist_ok=True)
        return expanded


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

# Use PEP 695 generic function syntax (Python 3.13+)


def get_singleton_instance[T](cls: type[T], *args: t.Any, **kwargs: t.Any) -> T:
    """Get or create a singleton instance of a class."""
    if cls not in _adapter_instances:
        _adapter_instances[cls] = cls(*args, **kwargs)
    return t.cast(T, _adapter_instances[cls])


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
        # Remove undefined global reference
        # global _config_initialized
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
                    return adapter.settings[item]
        msg = f"'Config' object has no attribute '{item}'"
        raise AttributeError(msg)


depends.set(Config, get_singleton_instance(Config))
get_container().add("config", get_singleton_instance(Config))

# Ensure basic logging is available even if adapter system fails
try:
    from .adapters.logger.loguru import Logger

    # Only try to register if the logger adapter is available
    if Logger:
        pass  # Will be registered when imported properly
except ImportError:
    # If logger can't be imported, register a fallback
    import logging

    fallback_logger = logging.getLogger("acb_fallback")
    get_container().add(logging.getLogger().__class__, fallback_logger)


def _initialize_config_eagerly_sync() -> None:
    config = depends.get_sync(Config)
    config.init()


if _should_initialize_eagerly():
    _initialize_config_eagerly_sync()

_ADAPTER_LOCKS: WeakKeyDictionary[t.Any, t.Any] = WeakKeyDictionary()


@rich.repr.auto
class AdapterBase:
    config: Inject[Config]

    @property
    def logger(self) -> t.Any:
        if not hasattr(self, "_logger"):
            try:
                Logger = import_adapter("logger")
                # In test mode, import_adapter returns MagicMock, so we need to check
                from unittest.mock import MagicMock

                # Check if import_adapter returned an empty tuple (dependency not properly registered)
                if (isinstance(Logger, tuple) and len(Logger) == 0) or isinstance(
                    Logger,
                    MagicMock,
                ):
                    import logging

                    self._logger = logging.getLogger(self.__class__.__name__)
                else:
                    logger_instance = depends.get_sync(Logger)
                    # Check if the logger_instance has the required methods
                    if (
                        hasattr(logger_instance, "debug")
                        and hasattr(logger_instance, "exception")
                        and not isinstance(logger_instance, tuple)
                    ):
                        self._logger = logger_instance
                    else:
                        import logging

                        self._logger = logging.getLogger(self.__class__.__name__)
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
        self._cleaned_up = False
        self._cleanup_lock = asyncio.Lock()
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
        """Enhanced resource cleanup with comprehensive error handling."""
        errors = []

        # Clean up cached resources first
        for resource_name, resource in list(self._resource_cache.items()):
            try:
                await self._cleanup_single_resource(resource)
            except Exception as e:
                errors.append(f"Failed to cleanup resource '{resource_name}': {e}")

        self._resource_cache.clear()

        # Clean up main client
        if self._client is not None:
            try:
                await self._cleanup_single_resource(self._client)
                self._client = None
            except Exception as e:
                errors.append(f"Failed to cleanup main client: {e}")

        if errors:
            self.logger.warning(f"Resource cleanup errors: {'; '.join(errors)}")

    async def _cleanup_single_resource(self, resource: t.Any) -> None:
        """Clean up a single resource using common cleanup patterns."""
        if resource is None:
            return

        # Try common cleanup methods in order of preference
        cleanup_methods = [
            "close",
            "aclose",
            "disconnect",
            "shutdown",
            "dispose",
            "terminate",
            "quit",
            "release",
        ]

        for method_name in cleanup_methods:
            if hasattr(resource, method_name):
                try:
                    method = getattr(resource, method_name)
                    if asyncio.iscoroutinefunction(method):
                        await method()
                    else:
                        method()
                    self.logger.debug(f"Cleaned up resource using {method_name}()")
                    return
                except Exception as e:
                    self.logger.debug(f"Failed to cleanup using {method_name}(): {e}")
                    continue

        self.logger.debug(
            f"No cleanup method found for resource type: {type(resource)}",
        )

    async def cleanup(self) -> None:
        """Public cleanup method with idempotency and error handling."""
        async with self._cleanup_lock:
            if self._cleaned_up:
                return

            try:
                await self._cleanup_resources()
                self._cleaned_up = True
                self.logger.debug(f"Successfully cleaned up {self.__class__.__name__}")
            except Exception as e:
                self.logger.exception(
                    f"Failed to cleanup {self.__class__.__name__}: {e}",
                )
                raise

    async def __aenter__(self) -> "AdapterBase":
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type: t.Any, exc_val: t.Any, exc_tb: t.Any) -> None:
        """Async context manager exit with cleanup."""
        await self.cleanup()

    async def init(self) -> None:
        pass


class ConfigHotReload:
    """Simple configuration hot-reloading capability."""

    def __init__(self, config: Config, check_interval: float = 5.0) -> None:
        self.config = config
        self.check_interval = check_interval
        self._running = False
        self._task: asyncio.Task[None] | None = None
        self._last_modified: dict[Path, float] = {}

    async def start(self) -> None:
        """Start monitoring configuration files for changes."""
        if self._running:
            return

        self._running = True
        self._task = asyncio.create_task(self._monitor_loop())

    async def stop(self) -> None:
        """Stop monitoring configuration files."""
        self._running = False
        if self._task:
            self._task.cancel()
            with suppress(asyncio.CancelledError):
                await self._task

    async def _monitor_loop(self) -> None:
        """Main monitoring loop."""
        while self._running:
            try:
                await self._check_for_changes()
                await asyncio.sleep(self.check_interval)
            except asyncio.CancelledError:
                break
            except Exception:
                # Log error but continue monitoring
                await asyncio.sleep(self.check_interval)

    async def _check_for_changes(self) -> None:
        """Check if any configuration files have changed."""
        config_files = [
            Path("settings/app.yaml"),
            Path("settings/adapters.yaml"),
            Path("settings/debug.yaml"),
            Path("settings/models.yaml"),
        ]

        for config_file in config_files:
            if config_file.exists():
                try:
                    current_mtime = config_file.stat().st_mtime
                    last_mtime = self._last_modified.get(config_file, 0)

                    if current_mtime > last_mtime:
                        self._last_modified[config_file] = current_mtime
                        if last_mtime > 0:  # Skip initial load
                            await self._reload_config()
                            break

                except OSError:
                    # File might be temporarily unavailable
                    continue

    async def _reload_config(self) -> None:
        """Reload the configuration."""
        with suppress(Exception):
            # Create a new config instance and replace the old one
            new_config = Config()

            # Update the global config instance
            # This is a simplified approach - in production you might want
            # to update specific attributes rather than replace the whole object
            for attr in dir(new_config):
                if not attr.startswith("_") and hasattr(self.config, attr):
                    with suppress(AttributeError):
                        setattr(self.config, attr, getattr(new_config, attr))


# Global hot-reload instance (optional)
_hot_reload: ConfigHotReload | None = None


async def enable_config_hot_reload(
    config: Config,
    check_interval: float = 5.0,
) -> ConfigHotReload:
    """Enable configuration hot-reloading for the given config instance."""
    global _hot_reload

    if _hot_reload:
        await _hot_reload.stop()

    _hot_reload = ConfigHotReload(config, check_interval)
    await _hot_reload.start()
    return _hot_reload


async def disable_config_hot_reload() -> None:
    """Disable configuration hot-reloading."""
    global _hot_reload

    if _hot_reload:
        await _hot_reload.stop()
        _hot_reload = None
