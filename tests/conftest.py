"""Test configuration and fixtures for the ACB project.

This file contains fixtures and configuration for pytest tests. It follows a mocking approach
to avoid creating actual files, directories, or settings during test execution.

Key fixtures:
- temp_dir: Returns a mock Path object instead of creating an actual directory
- mock_config: Provides a mocked Config object with mock paths
- mock_file_system: In-memory file system for tests
- patch_file_operations: Patches pathlib.Path operations to use the mock file system
- mock_async_file_system: In-memory async file system for tests
- patch_async_file_operations: Patches anyio.Path operations to use the mock async file system
- mock_settings: Provides mock settings without creating actual settings files

Tests should use these fixtures to avoid creating actual files or directories.
"""

import asyncio
import os
import signal
import sys
from collections.abc import Generator
from contextlib import suppress
from pathlib import Path
from typing import Any, AsyncGenerator, Final, NoReturn, TypeAlias, cast
from unittest.mock import MagicMock, patch

import pytest
from _pytest.config import Config
from _pytest.config.argparsing import Parser
from _pytest.main import Session
from _pytest.monkeypatch import MonkeyPatch

TaskSet: TypeAlias = set[asyncio.Task[object]]
MarkerTuple: TypeAlias = tuple[str, str]

pytest_plugins: Final[list[str]] = [
    "pytest_asyncio",
]


@pytest.fixture(scope="module")
def anyio_backend() -> str:
    return "asyncio"


def pytest_configure(config: Config) -> None:
    markers: list[MarkerTuple] = [
        ("unit", "Mark test as a unit test"),
        ("integration", "Mark test as an integration test"),
        ("async_test", "Mark test as an async test"),
        ("slow", "Mark test as a slow running test"),
        ("cache", "Mark test as a cache adapter test"),
        ("storage", "Mark test as a storage adapter test"),
        ("sql", "Mark test as a SQL adapter test"),
        ("nosql", "Mark test as a NoSQL adapter test"),
        ("secret", "Mark test as a secret adapter test"),
        ("benchmark", "Mark test as a benchmark test"),
        ("property", "Mark test as a property-based test"),
        ("concurrency", "Mark test as a concurrency test"),
        ("fault_tolerance", "Mark test as a fault tolerance test"),
        ("security", "Mark test as a security test"),
    ]
    for marker, help_text in markers:
        config.addinivalue_line("markers", f"{marker}: {help_text}")


@pytest.fixture(autouse=True)
async def cleanup_async_tasks() -> AsyncGenerator[None, None]:
    yield
    current_task: asyncio.Task[object] | None = asyncio.current_task()
    tasks: TaskSet = {task for task in asyncio.all_tasks() if task is not current_task}
    if tasks:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)


def pytest_sessionfinish(session: Session, exitstatus: int | pytest.ExitCode) -> None:
    sys.stdout.flush()
    sys.stderr.flush()

    if (
        "crackerjack" in sys.modules
        or os.environ.get("RUNNING_UNDER_CRACKERJACK") == "1"
    ):
        return

    def kill_process() -> NoReturn:
        os.kill(os.getpid(), signal.SIGTERM)
        raise SystemExit(exitstatus)

    loop: asyncio.AbstractEventLoop = asyncio.get_event_loop()
    loop.call_later(1.0, kill_process)

    with suppress(Exception):
        loop.run_until_complete(asyncio.sleep(0.5))


def pytest_addoption(parser: Parser) -> None:
    parser.addoption(
        "--run-slow", action="store_true", default=False, help="run slow tests"
    )


def pytest_collection_modifyitems(config: Config, items: list[pytest.Item]) -> None:
    if not config.getoption("--run-slow"):
        skip_slow = pytest.mark.skip(reason="need --run-slow option to run")
        for item in items:
            if "slow" in item.keywords:
                item.add_marker(skip_slow)


@pytest.fixture
def temp_dir() -> Path:
    mock_path: MagicMock = MagicMock(spec=Path)
    setattr(
        mock_path.__truediv__,
        "side_effect",
        lambda other: Path(str(mock_path) + "/" + str(other)),
    )
    setattr(mock_path.exists, "return_value", True)
    setattr(mock_path.is_dir, "return_value", True)
    setattr(mock_path.mkdir, "return_value", None)
    setattr(mock_path.write_text, "return_value", None)
    setattr(mock_path.write_bytes, "return_value", None)
    setattr(mock_path.read_text, "return_value", "")
    setattr(mock_path.read_bytes, "return_value", b"")
    setattr(mock_path.unlink, "return_value", None)
    return cast(Path, mock_path)


@pytest.fixture
def mock_config() -> Any:
    from unittest.mock import MagicMock, PropertyMock

    from acb.config import Config

    mock_config = MagicMock(spec=Config)

    root_path_mock = PropertyMock(return_value=Path("/mock/root"))
    type(mock_config).root_path = root_path_mock

    settings_path_mock = PropertyMock(return_value=Path("/mock/settings"))
    type(mock_config).settings_path = settings_path_mock

    secrets_path_mock = PropertyMock(return_value=Path("/mock/secrets"))
    type(mock_config).secrets_path = secrets_path_mock

    tmp_path_mock = PropertyMock(return_value=Path("/mock/tmp"))
    type(mock_config).tmp_path = tmp_path_mock

    mock_config.deployed = False

    return mock_config


class SimpleFileStorage:
    def __init__(self) -> None:
        self.files: dict[str, bytes] = {}
        self.directories: set[str] = {"/"}

    def write_bytes(self, path: Any, content: bytes) -> None:
        self.files[str(path)] = content

    def read_bytes(self, path: Any) -> bytes:
        return self.files.get(str(path), b"")

    def exists(self, path: Any) -> bool:
        return str(path) in self.files or str(path) in self.directories

    def is_dir(self, path: Any) -> bool:
        return str(path) in self.directories

    write_text: Any
    read_text: Any
    mkdir: Any
    unlink: Any
    rmdir: Any


@pytest.fixture
def mock_file_system() -> SimpleFileStorage:
    fs = SimpleFileStorage()

    fs.write_text = lambda path, content, encoding=None: fs.write_bytes(
        path, content.encode("utf-8" if encoding is None else encoding)
    )

    fs.read_text = lambda path, encoding=None: fs.read_bytes(path).decode(
        "utf-8" if encoding is None else encoding
    )

    fs.mkdir = lambda path, parents=False, exist_ok=False: fs.directories.add(str(path))

    fs.unlink = lambda path, missing_ok=False: fs.files.pop(str(path), None)

    fs.rmdir = (
        lambda path: fs.directories.remove(str(path))
        if str(path) in fs.directories
        else None
    )

    return fs


@pytest.fixture
def patch_file_operations(
    mock_file_system: SimpleFileStorage,
) -> Generator[None, None, None]:
    patches = [
        patch("pathlib.Path.exists", mock_file_system.exists),
        patch("pathlib.Path.is_dir", mock_file_system.is_dir),
        patch("pathlib.Path.mkdir", mock_file_system.mkdir),
        patch("pathlib.Path.write_bytes", mock_file_system.write_bytes),
        patch("pathlib.Path.write_text", mock_file_system.write_text),
        patch("pathlib.Path.read_bytes", mock_file_system.read_bytes),
        patch("pathlib.Path.read_text", mock_file_system.read_text),
        patch("pathlib.Path.unlink", mock_file_system.unlink),
        patch("pathlib.Path.rmdir", mock_file_system.rmdir),
        patch("tempfile.mkdtemp", lambda: "/mock/temp/dir"),
        patch("tempfile.mktemp", lambda: "/mock/temp/file"),
        patch("tempfile.gettempdir", lambda: "/mock/temp"),
    ]

    for p in patches:
        p.start()

    yield

    for p in patches:
        p.stop()


class SimpleAsyncFileStorage:
    def __init__(self) -> None:
        self.files: dict[str, bytes] = {}
        self.directories: set[str] = {"/"}

    async def write_bytes(self, path: Any, content: bytes) -> None:
        self.files[str(path)] = content

    async def read_bytes(self, path: Any) -> bytes:
        return self.files.get(str(path), b"")

    async def exists(self, path: Any) -> bool:
        return str(path) in self.files or str(path) in self.directories

    async def is_dir(self, path: Any) -> bool:
        return str(path) in self.directories

    write_text: Any
    read_text: Any
    mkdir: Any
    unlink: Any
    rmdir: Any


@pytest.fixture
def mock_async_file_system() -> SimpleAsyncFileStorage:
    fs = SimpleAsyncFileStorage()

    async def write_text(path: Any, content: str, encoding: str | None = None) -> None:
        return await fs.write_bytes(
            path, content.encode("utf-8" if encoding is None else encoding)
        )

    fs.write_text = write_text

    async def read_text(path: Any, encoding: str | None = None) -> str:
        return (await fs.read_bytes(path)).decode(
            "utf-8" if encoding is None else encoding
        )

    fs.read_text = read_text

    async def mkdir(path: Any, parents: bool = False, exist_ok: bool = False) -> None:
        fs.directories.add(str(path))

    fs.mkdir = mkdir

    async def unlink(path: Any, missing_ok: bool = False) -> None:
        if str(path) in fs.files:
            del fs.files[str(path)]

    fs.unlink = unlink

    async def rmdir(path: Any) -> None:
        fs.directories.discard(str(path))

    fs.rmdir = rmdir

    return fs


@pytest.fixture
def patch_async_file_operations(
    mock_async_file_system: SimpleAsyncFileStorage,
) -> Generator[None, None, None]:
    patches = [
        patch("anyio.Path.exists", mock_async_file_system.exists),
        patch("anyio.Path.is_dir", mock_async_file_system.is_dir),
        patch("anyio.Path.mkdir", mock_async_file_system.mkdir),
        patch("anyio.Path.write_bytes", mock_async_file_system.write_bytes),
        patch("anyio.Path.write_text", mock_async_file_system.write_text),
        patch("anyio.Path.read_bytes", mock_async_file_system.read_bytes),
        patch("anyio.Path.read_text", mock_async_file_system.read_text),
        patch("anyio.Path.unlink", mock_async_file_system.unlink),
        patch("anyio.Path.rmdir", mock_async_file_system.rmdir),
    ]

    for p in patches:
        p.start()

    yield

    for p in patches:
        p.stop()


@pytest.fixture
def mock_settings() -> MagicMock:
    settings: MagicMock = MagicMock()

    settings.app = MagicMock()
    settings.app.name = "test_app"
    settings.app.title = "Test App"
    settings.app.timezone = "UTC"

    settings.storage = MagicMock()
    settings.storage.local_fs = True
    settings.storage.local_path = "/mock/storage"
    settings.storage.memory_fs = False
    settings.storage.buckets = {
        "test": "test-bucket",
        "media": "media-bucket",
        "templates": "templates-bucket",
    }

    settings.logger = MagicMock()
    settings.logger.log_level = "INFO"
    settings.logger.format = "simple"
    settings.logger.level_per_module = {}

    return settings


@pytest.fixture
def mock_tmp_path() -> Path:
    mock_path: MagicMock = MagicMock(spec=Path)
    setattr(mock_path.__str__, "return_value", "/mock/pytest/tmp")
    setattr(
        mock_path.__truediv__,
        "side_effect",
        lambda other: Path(str(mock_path) + "/" + str(other)),
    )
    setattr(mock_path.exists, "return_value", True)
    setattr(mock_path.is_dir, "return_value", True)
    return cast(Path, mock_path)


@pytest.fixture
def mock_tempfile() -> MagicMock:
    mock: MagicMock = MagicMock()
    setattr(mock.mkdtemp, "return_value", "/mock/temp/dir")
    setattr(mock.mktemp, "return_value", "/mock/temp/file")
    setattr(mock.gettempdir, "return_value", "/mock/temp")
    return mock


class MockDns:
    async def get_records(self, domain: str, record_type: str) -> list[Any]:
        return []

    async def create_record(self, domain: str, record_type: str, value: str) -> None:
        pass

    async def delete_record(self, domain: str, record_id: str) -> None:
        pass


class MockRequests:
    async def get(self, url: str, headers: dict[str, str] | None = None) -> Any:
        mock_response = MagicMock()
        mock_response.status_code = 200
        setattr(mock_response.json, "return_value", {})
        return mock_response

    async def post(
        self,
        url: str,
        data: Any = None,
        json: Any = None,
        headers: dict[str, str] | None = None,
    ) -> Any:
        mock_response = MagicMock()
        mock_response.status_code = 200
        setattr(mock_response.json, "return_value", {})
        return mock_response


class MockStorage:
    async def upload(self, source: Path, destination: str) -> None:
        pass

    async def download(self, source: str, destination: Path) -> None:
        pass

    async def list_files(self, path: str) -> list[str]:
        return []


def create_mock_import_adapter() -> Any:
    def mock_import_adapter(*args: str) -> tuple[Any, ...]:
        if not args:
            return ()

        result = []
        for arg in args:
            if arg == "dns":
                result.append(MockDns())
            elif arg == "requests":
                result.append(MockRequests())
            elif arg == "storage":
                result.append(MockStorage())
            else:
                result.append(MagicMock())

        return tuple(result)

    return mock_import_adapter


def patch_base_adapter_modules() -> None:
    for module_name in (
        "acb.adapters.dns",
        "acb.adapters.requests",
        "acb.adapters.storage",
    ):
        if module_name not in sys.modules:
            mock_module = MagicMock()
            sys.modules[module_name] = mock_module


def patch_specific_adapter_modules(
    monkeypatch: MonkeyPatch, mock_import_adapter: Any
) -> None:
    import importlib

    for module_name in (
        "acb.adapters.smtp.gmail",
        "acb.adapters.smtp.mailgun",
        "acb.adapters.ftpd.ftp",
        "acb.adapters.ftpd.sftp",
    ):
        try:
            module = importlib.import_module(module_name)
            monkeypatch.setattr(module, "import_adapter", mock_import_adapter)
        except (ImportError, AttributeError):
            if module_name not in sys.modules:
                mock_module = MagicMock()
                mock_module.import_adapter = mock_import_adapter
                sys.modules[module_name] = mock_module


def patch_main_adapter_import(
    monkeypatch: MonkeyPatch, mock_import_adapter: Any
) -> None:
    with suppress(ImportError, AttributeError):
        import acb.adapters

        monkeypatch.setattr(acb.adapters, "import_adapter", mock_import_adapter)


@pytest.fixture(autouse=True)
def patch_adapter_imports(monkeypatch: MonkeyPatch) -> None:
    with suppress(Exception):
        mock_import_adapter = create_mock_import_adapter()
        patch_base_adapter_modules()
        patch_specific_adapter_modules(monkeypatch, mock_import_adapter)
        patch_main_adapter_import(monkeypatch, mock_import_adapter)


@pytest.fixture(autouse=True)
def patch_config(monkeypatch: MonkeyPatch) -> None:
    class MockConfig:
        def __init__(self) -> None:
            self.app = MagicMock()
            self.app.name = "test_app"
            self.app.title = "Test App"
            self.app.domain = "example.com"
            self.app.version = "0.1.0"
            self.app.timezone = "UTC"

            self.storage = MagicMock()
            self.storage.local_fs = True
            self.storage.local_path = "/mock/storage"
            self.storage.memory_fs = False
            self.storage.buckets = {
                "test": "test-bucket",
                "media": "media-bucket",
                "templates": "templates-bucket",
            }

            self.logger = MagicMock()
            self.logger.log_level = "INFO"
            self.logger.format = "simple"
            self.logger.level_per_module = {}

            self.debug = MagicMock()
            self.debug.production = False
            self.debug.secrets = False

            self.adapters = MagicMock()
            self.adapters.dns = "mock"
            self.adapters.smtp = "mock"
            self.adapters.ftpd = "mock"
            self.adapters.storage = "mock"
            self.adapters.sql = "mock"
            self.adapters.nosql = "mock"
            self.adapters.secret = "mock"
            self.adapters.cache = "mock"

            self.root_path = Path("/mock/root")
            self.settings_path = Path("/mock/settings")
            self.secrets_path = Path("/mock/secrets")
            self.tmp_path = Path("/mock/tmp")

            self.deployed = False

    def mock_get_config() -> MockConfig:
        return MockConfig()

    def mock_get_settings() -> dict[str, Any]:
        return {
            "app": {
                "name": "test_app",
                "title": "Test App",
                "domain": "example.com",
                "version": "0.1.0",
                "timezone": "UTC",
            },
            "storage": {
                "local_fs": True,
                "local_path": "/mock/storage",
                "memory_fs": False,
                "buckets": {
                    "test": "test-bucket",
                    "media": "media-bucket",
                    "templates": "templates-bucket",
                },
            },
            "logger": {
                "log_level": "INFO",
                "format": "simple",
                "level_per_module": {},
            },
            "debug": {
                "production": False,
                "secrets": False,
            },
            "adapters": {
                "dns": "mock",
                "smtp": "mock",
                "ftpd": "mock",
                "storage": "mock",
                "sql": "mock",
                "nosql": "mock",
                "secret": "mock",
                "cache": "mock",
            },
        }

    with suppress(ImportError, AttributeError):
        import acb.config

        monkeypatch.setattr(acb.config, "get_config", mock_get_config)
        monkeypatch.setattr(acb.config, "get_settings", mock_get_settings)
        monkeypatch.setattr(acb.config, "Config", MockConfig)
