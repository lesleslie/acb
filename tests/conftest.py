import sys
import typing as t
from contextvars import ContextVar
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from aiopath import AsyncPath
from acb.adapters import Adapter, adapter_registry


def create_logger_adapter() -> Adapter:
    return Adapter(
        name="loguru",
        class_name="Logger",
        category="logger",
        pkg="acb",
        module="acb.adapters.logger.loguru",
        enabled=True,
        installed=True,
        path=AsyncPath(
            Path(__file__).parent.parent / "acb" / "adapters" / "logger" / "loguru.py"
        ),
    )


def create_mock_logger() -> MagicMock:
    mock_logger = MagicMock()

    for method in ("info", "debug", "warning", "error", "critical", "log"):
        setattr(mock_logger, method, MagicMock())

    mock_logger.patch = MagicMock(return_value=mock_logger)
    mock_logger.opt = MagicMock(return_value=mock_logger)

    async def mock_init():
        return None

    mock_logger.init = mock_init

    mock_level = MagicMock()
    mock_level.name = "DEBUG"
    mock_level.no = 10
    mock_logger.level.return_value = mock_level

    return mock_logger


def is_test_adapters_file() -> bool:
    return "test_adapters.py" in sys._getframe(1).f_code.co_filename


def patch_import_adapter(mock_logger: MagicMock) -> None:
    def mock_import_adapter(category: t.Optional[str] = None) -> t.Any:
        if is_test_adapters_file():
            from acb.adapters import import_adapter as original_import_adapter

            return original_import_adapter(category)
        if category == "logger" or category is None:
            return mock_logger.__class__
        return None

    patch("acb.adapters.import_adapter", side_effect=mock_import_adapter).start()


def patch_import_adapter_coro(mock_logger: MagicMock) -> None:
    async def mock_import_adapter_coro(
        category: str, config: t.Any
    ) -> t.Optional[t.Any]:
        if is_test_adapters_file():
            return None
        if category == "logger":
            return mock_logger.__class__
        return None

    patch("acb.adapters._import_adapter", side_effect=mock_import_adapter_coro).start()


def patch_asyncio_run(mock_logger: MagicMock) -> None:
    def mock_asyncio_run(coro: t.Any) -> t.Any:
        if is_test_adapters_file():
            import asyncio

            return asyncio.get_event_loop().run_until_complete(coro)
        if hasattr(coro, "__name__") and coro.__name__ == "mock_import_adapter_coro":
            return mock_logger.__class__
        return [mock_logger.__class__]

    patch("asyncio.run", side_effect=mock_asyncio_run).start()


def patch_get_adapter(logger_adapter: Adapter) -> None:
    def mock_get_adapter(category: str) -> t.Optional[Adapter]:
        if is_test_adapters_file():
            return None
        if category == "logger":
            return logger_adapter
        return None

    patch("acb.adapters.get_adapter", side_effect=mock_get_adapter).start()


def create_test_adapter_config() -> MagicMock:
    from acb.config import Config

    mock_config = MagicMock(spec=Config)
    mock_config.deployed = False
    return mock_config


def create_full_mock_config() -> MagicMock:
    from acb.config import Config

    mock_config = MagicMock(spec=Config)
    mock_config.deployed = False
    mock_config.debug = MagicMock()
    mock_config.debug.production = False
    mock_config.debug.module = True

    mock_logger_config = MagicMock()
    mock_logger_config.log_level = "DEBUG"
    mock_logger_config.deployed_level = "WARNING"
    mock_logger_config.level_per_module = {}
    mock_logger_config.settings = {}
    mock_logger_config.level_colors = {}
    mock_config.logger = mock_logger_config

    mock_app_config = MagicMock()
    mock_app_config.name = "acb-test"
    mock_config.app = mock_app_config

    return mock_config


def patch_depends_get(mock_logger: MagicMock, mock_adapter_class: MagicMock) -> None:
    def mock_depends_get(
        dependency: t.Optional[str | t.Type[t.Any]] = None,
        *args: t.Any,
        **kwargs: t.Any,
    ) -> t.Any:
        if is_test_adapters_file():
            if dependency == "config" or (
                isinstance(dependency, type)
                and hasattr(dependency, "__name__")
                and "Config" in dependency.__name__
            ):
                return create_test_adapter_config()
            return MagicMock()

        if dependency == "logger" or (
            isinstance(dependency, type)
            and hasattr(dependency, "__name__")
            and dependency.__name__ == "Logger"
        ):
            return mock_logger

        if dependency == "config" or (
            isinstance(dependency, type)
            and hasattr(dependency, "__name__")
            and "Config" in dependency.__name__
        ):
            return create_full_mock_config()

        if dependency is not None and hasattr(dependency, "__name__"):
            return mock_adapter_class

        if dependency == "actions":
            from acb.actions import actions

            return actions

        return MagicMock()

    patch("acb.depends.depends.get", side_effect=mock_depends_get).start()


def create_mock_adapter_class(mock_logger: MagicMock) -> MagicMock:
    mock_adapter_class = MagicMock()
    mock_adapter_class.return_value = mock_logger
    return mock_adapter_class


def apply_patches(
    mock_logger: MagicMock, logger_adapter: Adapter, mock_adapter_class: MagicMock
) -> None:
    patch_import_adapter(mock_logger)
    patch_import_adapter_coro(mock_logger)
    patch_asyncio_run(mock_logger)
    patch_get_adapter(logger_adapter)
    patch_depends_get(mock_logger, mock_adapter_class)


def setup_patches(logger_adapter: Adapter, mock_logger: MagicMock) -> None:
    mock_adapter_class = create_mock_adapter_class(mock_logger)

    apply_patches(mock_logger, logger_adapter, mock_adapter_class)


def setup_adapter_registry() -> None:
    logger_adapter = create_logger_adapter()
    adapter_registry.set([logger_adapter])

    mock_logger = create_mock_logger()

    setup_patches(logger_adapter, mock_logger)


patch("acb.register_pkg", return_value=None).start()

patch("acb.adapters.register_adapters", return_value=[]).start()

mock_pkg = MagicMock()
mock_pkg.name = "acb"
mock_pkg.path = Path(__file__).parent.parent / "acb"
mock_pkg.actions = []
mock_pkg.adapters = []
mock_pkg_registry = ContextVar("pkg_registry", default=[mock_pkg])
patch("acb.pkg_registry", mock_pkg_registry).start()

mock_pkg_class = MagicMock()
mock_pkg_class.return_value = mock_pkg
patch("acb.Pkg", mock_pkg_class).start()

setup_adapter_registry()


@pytest.fixture(scope="session", autouse=True)
def patch_adapter_system() -> t.Generator[None, None, None]:
    async def mock_async_exists(self: t.Any) -> bool:
        if "adapters.yml" in str(self):
            return True
        return False

    def mock_sync_exists(self: t.Any) -> bool:
        if "adapters.yml" in str(self):
            return True
        return False

    async def mock_async_read_text(self: t.Any, *args: t.Any, **kwargs: t.Any) -> str:
        if "adapters.yml" in str(self):
            return "logger: loguru"
        return ""

    def mock_sync_read_text(self: t.Any, *args: t.Any, **kwargs: t.Any) -> str:
        if "adapters.yml" in str(self):
            return "logger: loguru"
        return ""

    def mock_yaml_decode(text: str) -> t.Dict[str, str]:
        if "logger: loguru" in text:
            return {"logger": "loguru"}
        return {}

    with (
        patch("pathlib.Path.exists", mock_sync_exists),
        patch("pathlib.Path.read_text", mock_sync_read_text),
        patch("aiopath.AsyncPath.exists", mock_async_exists),
        patch("aiopath.AsyncPath.read_text", mock_async_read_text),
        patch("acb.adapters.yaml_decode", side_effect=mock_yaml_decode),
        patch("msgspec.yaml.decode", side_effect=mock_yaml_decode),
    ):
        yield


@pytest.fixture(autouse=True)
def setup_test_environment(
    monkeypatch: pytest.MonkeyPatch, patch_adapter_system: None
) -> t.Generator[None, None, None]:
    monkeypatch.setenv("TESTING", "True")
    yield


@pytest.fixture
def mock_logger_adapter() -> t.Optional[Adapter]:
    registry = adapter_registry.get()
    return next((a for a in registry if a.category == "logger"), None)


@pytest.fixture
def mock_adapter_registry() -> t.List[Adapter]:
    from pathlib import Path

    from aiopath import AsyncPath
    from acb.adapters import Adapter

    logger_adapter = Adapter(
        name="loguru",
        class_name="Logger",
        category="logger",
        pkg="acb",
        module="acb.adapters.logger.loguru",
        enabled=True,
        installed=True,
        path=AsyncPath(
            Path(__file__).parent.parent / "acb" / "adapters" / "logger" / "loguru.py"
        ),
    )

    return [logger_adapter]


@pytest.fixture
def mock_logger() -> MagicMock:
    from acb.depends import depends

    return depends.get("logger")


@pytest.fixture
def mock_config() -> MagicMock:
    from acb.config import Config
    from acb.depends import depends

    return depends.get(Config)
