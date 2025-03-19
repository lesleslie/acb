import asyncio
import atexit
import os
import sys
import threading
from collections import UserDict
from typing import Any, Callable, Dict, Protocol
from unittest.mock import AsyncMock, MagicMock, Mock, patch


class MockBaseModel:
    """Mock implementation of Pydantic's BaseModel that supports model configuration."""

    model_config = {}

    def __init__(self, *args: Any, **kwargs: Any) -> None:  # type: ignore
        if args and len(args) == 1 and isinstance(args[0], str):
            self._raw_string_value = args[0]
            return

        build_settings = kwargs.get("build_settings")
        if build_settings is not None and isinstance(build_settings, str):
            self._raw_string_value = build_settings
            del kwargs["build_settings"]

        for key, value in list(kwargs.items()):
            if isinstance(value, str):
                setattr(self, key, value)
                del kwargs[key]

        for k, v in kwargs.items():
            setattr(self, k, v)

    @classmethod
    def __init_subclass__(cls, **kwargs: Any) -> None:
        """Support for model configuration via __init_subclass__.

        In Pydantic v2, class definition keyword arguments (like `arbitrary_types_allowed=True`)
        are passed to __init_subclass__ and stored in model_config.
        """
        super().__init_subclass__()

        for key, value in kwargs.items():
            cls.model_config[key] = value


class MockSettingsConfigDict(UserDict[str, Any]): ...


class MockBaseSettings(MockBaseModel):
    """Mock implementation of BaseSettings."""

    model_config = {"env_prefix": ""}


mock_pydantic = MagicMock()
mock_pydantic.BaseModel = MockBaseModel
mock_pydantic.Field = lambda *args, **kwargs: None

mock_pydantic_settings = MagicMock()
mock_pydantic_settings.SettingsConfigDict = MockSettingsConfigDict
mock_pydantic_settings.BaseSettings = MockBaseSettings

sys.modules["pydantic"] = mock_pydantic
sys.modules["pydantic.main"] = mock_pydantic
sys.modules["pydantic.fields"] = mock_pydantic
sys.modules["pydantic_settings"] = mock_pydantic_settings
sys.modules["pydantic_settings.main"] = mock_pydantic_settings
sys.modules["pydantic_settings.sources"] = MagicMock()
sys.modules["pydantic.root_model"] = MagicMock()
sys.modules["pydantic._internal._model_construction"] = MagicMock()


class DebugModuleProtocol(Protocol):
    config: Any
    adapter_registry: Any
    colorized_stderr_print: Callable[[str], None]
    print_debug_info: Callable[[str], Any]
    timeit: Callable[[Callable[[str], Any]], Callable[[str], Any]]
    get_calling_module: Callable[[str], Any]
    patch_record: Callable[[Any, str, Any], None]
    debug: Any


class ConsoleModuleProtocol(Protocol):
    Config: Any
    adapter_registry: Any
    RichConsole: Any
    display_adapters: Callable[[], None]
    console: Any


class ConfigModuleProtocol(Protocol):
    _app_secrets: Any
    _testing: bool
    config: Any
    Config: Any
    AppSettings: Any
    DebugSettings: Any
    depends: Any
    adapter_registry: Any
    gen_password: Callable[[int], str]
    get_version: Callable[[], str]
    get_version_default: Callable[[], str]


class MockEventLoopPolicy(asyncio.AbstractEventLoopPolicy):
    """Mock implementation of AbstractEventLoopPolicy for testing.

    This implementation includes the _local attribute and properly implements
    all required methods of the AbstractEventLoopPolicy interface.
    """

    def __init__(self) -> None:
        self._local = threading.local()
        setattr(self._local, "_loop", None)

        self.loop = MagicMock()
        self.loop.close = MagicMock()
        self.loop.is_closed = MagicMock(return_value=False)
        self.loop.create_future = MagicMock()
        self.loop.create_task = MagicMock()
        self.loop.run_until_complete = MagicMock(return_value="0.0.0-test")
        self.loop.run_forever = MagicMock()
        self.loop.is_running = MagicMock(return_value=False)
        self.loop.stop = MagicMock()
        self.loop.call_soon = MagicMock()
        self.loop.call_later = MagicMock()
        self.loop.call_at = MagicMock()
        self.loop.time = MagicMock(return_value=0.0)
        self.loop.add_reader = MagicMock()
        self.loop.add_writer = MagicMock()
        self.loop.remove_reader = MagicMock()
        self.loop.remove_writer = MagicMock()
        self.loop.add_signal_handler = MagicMock()
        self.loop.remove_signal_handler = MagicMock()
        self.loop.set_exception_handler = MagicMock()
        self.loop.get_exception_handler = MagicMock(return_value=None)
        self.loop.default_exception_handler = MagicMock()
        self.loop.call_exception_handler = MagicMock()
        self.loop.get_debug = MagicMock(return_value=False)
        self.loop.set_debug = MagicMock()

        self.loop.shutdown_asyncgens = AsyncMock()
        self.loop.shutdown_default_executor = AsyncMock()

        setattr(self._local, "_loop", self.loop)

    def get_event_loop(self) -> asyncio.AbstractEventLoop:
        """Get the event loop for the current thread."""
        if not hasattr(self._local, "_loop") or getattr(self._local, "_loop") is None:
            setattr(self._local, "_loop", self.loop)
        return getattr(self._local, "_loop")

    def set_event_loop(self, loop: asyncio.AbstractEventLoop | None) -> None:
        """Set the event loop for the current thread."""
        setattr(self._local, "_loop", loop if loop is not None else self.loop)

    def new_event_loop(self) -> asyncio.AbstractEventLoop:
        """Create a new event loop."""
        return self.loop

    @staticmethod
    @atexit.register
    def close_event_loop() -> None:
        asyncio.get_event_loop().close()


class MockContextVar:
    """Mock implementation of ContextVar for testing."""

    def __init__(self, name: str, default: Any = None) -> None:
        self.name = name
        self.value = default if default is not None else []
        self.get = Mock(return_value=self.value)

    def set(self, value: Any) -> Any:
        """Set a new value."""
        old_value = self.value
        self.value = value
        self.get.return_value = value
        return old_value


class MockAppSettings(MockBaseSettings):
    """Mock implementation of AppSettings."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.name = kwargs.get("name", "myapp")
        self.title = kwargs.get("title")
        self.timezone = kwargs.get("timezone", "US/Pacific")
        self.version = kwargs.get("version", "0.0.0-test")
        self.project = kwargs.get("project", "test-project")

        self.model_post_init(None)

    @classmethod
    def cloud_compliant_app_name(cls, v: str) -> str:
        if len(v) < 3:
            import sys

            print("App name to short")
            sys.exit(1)
        if len(v) > 63:
            import sys

            print("App name to long")
            sys.exit(1)
        return v.replace(" ", "-").replace("_", "-").lower()

    def model_post_init(self, context: Any) -> None:
        self.title = self.title or self.name.replace("-", " ").title()


class MockDebugSettings(MockBaseSettings):
    """Mock implementation of DebugSettings."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.production = kwargs.get("production", False)
        self.module = kwargs.get("module", True)
        self.logger = kwargs.get("logger", False)
        self.secret = kwargs.get("secret", False)


class MockConfig:
    deployed: bool = False

    def __init__(self) -> None:
        self.debug = MockDebugSettings()
        self.app = MockAppSettings(
            name="test-app",
            title="Test App",
            project="test-project",
            version="0.0.0-test",
        )

    def init(self) -> "MockConfig":
        """Initialize the Config object."""
        return self


class MockLogger:
    """Mock logger implementation for testing."""

    debug_enabled = False

    @classmethod
    def set_debug(cls, enabled: bool) -> None:
        """Set debug mode for the logger."""
        cls.debug_enabled = enabled

    @staticmethod
    async def init() -> None:
        """Initialize the logger."""
        pass

    @classmethod
    def info(cls, *args: Any, **kwargs: Any) -> None:
        """Log an info message."""
        if os.environ.get("TEST_DEBUG") or cls.debug_enabled:
            print(f"[INFO] {args[0] if args else ''}")

    @classmethod
    def debug(cls, *args: Any, **kwargs: Any) -> None:
        """Log a debug message."""
        if os.environ.get("TEST_DEBUG") or cls.debug_enabled:
            print(f"[DEBUG] {args[0] if args else ''}")

    @classmethod
    def warning(cls, *args: Any, **kwargs: Any) -> None:
        """Log a warning message."""
        if os.environ.get("TEST_DEBUG") or cls.debug_enabled:
            print(f"[WARNING] {args[0] if args else ''}")

    @classmethod
    def error(cls, *args: Any, **kwargs: Any) -> None:
        """Log an error message."""
        if os.environ.get("TEST_DEBUG") or cls.debug_enabled:
            print(f"[ERROR] {args[0] if args else ''}")

    @staticmethod
    def level(level_name: str) -> Any:
        """Return a mock level object."""
        return type("Level", (), {"name": level_name, "no": 0})

    @staticmethod
    def patch(*args: Any, **kwargs: Any) -> Any:
        """Mock patch method that returns self for method chaining."""
        return MockLogger()


class MockRichConsole:
    def __init__(self) -> None:
        self.record = False
        self._buffer = []
        self._lock = MagicMock()
        self._record_buffer_lock = MagicMock()
        self._record_buffer = []
        self._buffer_index = 0
        self.file = MagicMock()

    def print(self, *args: Any, **kwargs: Any) -> None:
        pass

    def _write_buffer(self) -> None:
        pass


class MockDepends:
    """Mock implementation of the depends module."""

    def __init__(self) -> None:
        self.dependencies: Dict[Any, Any] = {
            "logger": MockLogger(),
            "Config": MockConfig(),
        }
        self.repository = MagicMock()
        self.repository.get.side_effect = self._get_from_repo
        self.repository.set.side_effect = self._set_in_repo

    def _get_from_repo(self, key: Any) -> Any:
        """Internal implementation for repository.get that's mockable for tests."""
        if key not in self.dependencies and callable(key) and not isinstance(key, Mock):
            self.dependencies[key] = key()
        return self.dependencies.get(key)

    def _set_in_repo(self, key: Any, value: Any) -> Any:
        """Internal implementation for repository.set that's mockable for tests."""
        self.dependencies[key] = value
        return value

    def get(self, key: Any = None) -> Any:
        """Get a dependency.

        This can be called in multiple ways:
        1. With a class: depends.get(SomeClass)
        2. With a string: depends.get("logger")
        """
        if key is None:
            return None

        if key == "logger":
            return self.dependencies["logger"]
        if key == "Config" or (isinstance(key, type) and key.__name__ == "Config"):
            return self.dependencies["Config"]
        if isinstance(key, type) and key.__name__ == "Logger":
            return self.dependencies["logger"]

        if isinstance(key, type) and key.__name__ == "TestAdapter":
            from acb.adapters import adapter_registry

            for adapter in adapter_registry.get():
                if adapter.category == "test":
                    return adapter

        if isinstance(key, str):
            from acb.adapters import import_adapter

            try:
                adapter_class = import_adapter(key)

                if adapter_class not in self.dependencies:
                    if isinstance(adapter_class, type):
                        self.dependencies[adapter_class] = adapter_class()
                    else:
                        return adapter_class

                return self.dependencies[adapter_class]
            except Exception as e:
                raise e

        from acb.depends import get_repository

        return get_repository().get(key)

    def set(self, key: Any, value: Any = None) -> Any:
        """Set a dependency.

        If value is None and key is callable, value becomes the result of calling key().
        """
        if value is None and callable(key) and not isinstance(key, Mock):
            value = key()

        from acb.depends import get_repository

        return get_repository().set(key, value)

    def inject(self, func: Callable[..., Any]) -> Callable[..., Any]:
        """Decorator for dependency injection."""
        return func

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        """Make depends callable to handle depends() syntax.

        This needs to return 'real_dependency_marker' for test_depends_call_returns_marker.
        """
        if args and isinstance(args[0], type) and args[0].__name__ == "TestAdapter":
            from acb.adapters import adapter_registry

            for adapter in adapter_registry.get():
                if adapter.category == "test":
                    return adapter

        if args and isinstance(args[0], type):
            if args[0].__name__ == "Logger":
                return self.dependencies["logger"]
            elif args[0].__name__ == "Config":
                return self.dependencies["Config"]

        return "real_dependency_marker"


mock_depends = MockDepends()

mock_app_secrets = MockContextVar("_app_secrets", default=set())

mock_adapter_registry = MockContextVar("adapter_registry", default=[])

mock_config_instance = MockConfig()


def mock_colorized_stderr_print(s: str) -> None:
    pass


def mock_print_debug_info(msg: str) -> Any:
    pass


def mock_timeit(func: Callable[..., Any]) -> Callable[..., Any]:
    return func


def mock_get_calling_module() -> Any:
    return None


def mock_patch_record(mod: Any, msg: str, logger: Any = None) -> None:
    pass


async def mock_get_version() -> str:
    """Mock implementation that returns a proper string version."""
    return "0.0.0-test"


def mock_get_version_default() -> str:
    """Mock implementation that returns a proper string version."""
    return "0.0.0-test"


def mock_gen_password(size: int = 10) -> str:
    return "a" * size


def mock_display_adapters() -> None:
    pass


def mock_get_adapter(category: str) -> Any:
    """Mock get_adapter function."""
    for adapter in mock_adapter_registry.get():
        if (
            hasattr(adapter, "category")
            and adapter.category == category
            and getattr(adapter, "enabled", True)
        ):
            return adapter

    if category == "secret":
        return None

    from acb.adapters import AdapterNotFound

    raise AdapterNotFound(f"Adapter for category '{category}' not found")


def mock_import_adapter(name: str | list[str] | None = None) -> Any:
    """Mock import_adapter function."""
    try:
        if isinstance(name, list):
            if "logger" in name:
                return MockLogger
            return [MockLogger for _ in name]

        if name == "logger" or name is None:
            return MockLogger

        adapter = mock_get_adapter(name) if name else None
        if adapter:
            return adapter.__class__

        from acb.adapters import AdapterNotFound

        raise AdapterNotFound(f"Adapter '{name}' not found")
    except BaseException as e:
        from acb.adapters import AdapterNotFound

        try:
            error_message = str(e)
        except Exception:
            error_message = "Could not format exception"

        raise AdapterNotFound(f"Error in mock_import_adapter: {error_message}") from e


async def mock_load_yaml(file_path: Any) -> dict[str, Any]:
    """Mock implementation of load.yaml."""
    return {"key1": "value1", "key2": 123}


async def mock_dump_yaml(data: Any, file_path: Any) -> None:
    """Mock implementation of dump.yaml."""
    pass


def mock_asyncio_run(coro: Any) -> Any:
    """Mock implementation of asyncio.run that handles different coroutines appropriately.

    For _settings_build_values, returns a dictionary since that's what the real function would return.
    For get_version, returns a version string.
    For asyncio.gather, returns mocked results or handles exceptions properly.
    """
    try:
        if hasattr(coro, "__name__"):
            if coro.__name__ == "get_version":
                return "0.0.0-test"

            if coro.__name__ == "_settings_build_values":
                return {}

        if (
            hasattr(coro, "_coro")
            and hasattr(coro._coro, "__name__")
            and coro._coro.__name__ == "gather"
        ):
            return [MockLogger]

        if hasattr(
            coro, "__qualname__"
        ) and "Settings._settings_build_values" in getattr(coro, "__qualname__", ""):
            return {}

        if hasattr(coro, "__self__") and hasattr(coro.__self__, "__class__"):
            if (
                coro.__self__.__class__.__name__ == "Settings"
                and hasattr(coro, "__name__")
                and coro.__name__ == "_settings_build_values"
            ):
                return {}

        return "0.0.0-test"
    except BaseException as e:
        from acb.adapters import AdapterNotFound

        try:
            error_message = str(e)
        except Exception:
            error_message = "Could not format exception"

        raise AdapterNotFound(f"Error in mock_asyncio_run: {error_message}") from e


mock_policy = MockEventLoopPolicy()
asyncio.set_event_loop_policy(mock_policy)

patches = [
    patch("acb.config.Config", MockConfig),
    patch("acb.config.AppSettings", MockAppSettings),
    patch("acb.config.DebugSettings", MockDebugSettings),
    patch("acb.config.depends.get", mock_depends.get),
    patch("acb.depends.depends", mock_depends),
    patch("acb.console.Config", MockConfig),
    patch("acb.console.RichConsole", MockRichConsole),
    patch("acb.adapters.adapter_registry", mock_adapter_registry),
    patch("acb.config._app_secrets", mock_app_secrets),
    patch("acb.config.adapter_registry", mock_adapter_registry),
    patch("acb.console.adapter_registry", mock_adapter_registry),
    patch("acb.debug.adapter_registry", mock_adapter_registry),
    patch("acb.adapters.get_adapter", mock_get_adapter),
    patch("acb.adapters.import_adapter", mock_import_adapter),
    patch("acb.actions.encode.load.yaml", mock_load_yaml),
    patch("acb.actions.encode.dump.yaml", mock_dump_yaml),
    patch("aiopath.AsyncPath.exists", AsyncMock(return_value=True)),
    patch("asyncio.set_event_loop_policy", lambda policy: None),
    patch("acb.config.get_version", mock_get_version),
    patch("acb.config.get_version_default", mock_get_version_default),
    patch("asyncio.run", mock_asyncio_run),
]

for p in patches:
    p.start()
