import os
import tempfile
from collections.abc import Generator
from pathlib import Path
from unittest.mock import MagicMock, PropertyMock

import asyncio
import pytest
import typing as t
from _pytest.config.argparsing import Parser
from _pytest.main import Session
from _pytest.monkeypatch import MonkeyPatch
from contextlib import suppress
from typing import Any, TypeAlias, cast

from acb.config import Config

TaskSet: TypeAlias = set[asyncio.Task[object]]
MarkerTuple: TypeAlias = tuple[str, str]

original_exists = os.path.exists


def create_mock_config(**kwargs: t.Any) -> MagicMock:
    mock_config = MagicMock(spec=Config)
    for key, value in kwargs.items():
        setattr(mock_config, key, value)
    return mock_config


def mock_exists(path: t.Any, mock_base_path: str | None = None) -> bool:
    base = mock_base_path or str(Path(tempfile.gettempdir()) / "mock")
    if str(path).startswith(base):
        return True
    return original_exists(path)


original_isdir = os.path.isdir


def mock_isdir(path: t.Any, mock_base_path: str | None = None) -> bool:
    base = mock_base_path or str(Path(tempfile.gettempdir()) / "mock")
    if str(path).startswith(base):
        return True
    return original_isdir(path)


original_isfile = os.path.isfile


def mock_isfile(path: t.Any, mock_base_path: str | None = None) -> bool:
    base = mock_base_path or str(Path(tempfile.gettempdir()) / "mock")
    if str(path).startswith(base):
        return True
    return original_isfile(path)


original_open = open


def mock_open(
    file: t.Any,
    *args: t.Any,
    mock_base_path: str | None = None,
    **kwargs: t.Any,
) -> MagicMock:
    base = mock_base_path or str(Path(tempfile.gettempdir()) / "mock")
    if str(file).startswith(base):
        mock_file = MagicMock()
        enter_mock = cast("MagicMock", mock_file.__enter__)
        enter_mock.return_value = mock_file
        mock_file.read.return_value = "mocked content"
        mock_file.write.return_value = None
        return mock_file
    return original_open(file, *args, **kwargs)


class MockAsyncPath:
    def __init__(
        self,
        path: str | None = None,
        mock_base_path: str | None = None,
    ) -> None:
        base = mock_base_path or str(Path(tempfile.gettempdir()) / "mock/async/path")
        self._path_str = path or base
        self._content = ""
        self._bytes_content = b""
        self._exists = True
        self._is_dir = self._path_str.endswith("/")

    async def write_text(self, content: str, encoding: str = "utf-8") -> None:
        self._content = content
        self._bytes_content = content.encode(encoding)
        self._exists = True

    async def write_bytes(self, content: bytes) -> None:
        self._bytes_content = content
        try:
            self._content = content.decode()
        except Exception:
            self._content = ""
        self._exists = True
        self._is_dir = False

    async def read_text(self) -> str:
        return self._content

    async def read_bytes(self) -> bytes:
        return self._bytes_content

    async def exists(self) -> bool:
        return self._exists

    async def is_dir(self) -> bool:
        return self._is_dir

    async def is_file(self) -> bool:
        return self._exists and not self._is_dir

    async def mkdir(self) -> None:
        self._exists = True
        self._is_dir = True

    async def unlink(self) -> None:
        self._exists = False

    def __truediv__(self, other: str) -> "MockAsyncPath":
        return MockAsyncPath(f"{self._path_str.rstrip('/')}/{other}")

    @property
    def parent(self) -> "MockAsyncPath":
        parent_str = "/".join(self._path_str.rstrip("/").split("/")[:-1]) or "/"
        return MockAsyncPath(parent_str)


@pytest.fixture
def mock_async_path(mock_base_path: str) -> type[MockAsyncPath]:
    class CustomMockAsyncPath(MockAsyncPath):
        def __init__(self, path: str | None = None) -> None:
            super().__init__(path, mock_base_path)

    return CustomMockAsyncPath


@pytest.fixture
def mock_path_constructor(mock_base_path: str) -> t.Callable[..., MagicMock]:
    def constructor(*args: t.Any, **kwargs: t.Any) -> MagicMock:
        mock = MagicMock(spec=Path)
        mock.__truediv__.side_effect = (
            lambda other: constructor(f"{args[0]}/{other}")
            if args
            else constructor(f"/{other}")
        )
        return mock

    return constructor


@pytest.fixture
def mock_secrets_path() -> MagicMock:
    mock_path = MagicMock(spec=Path)
    mock_path.mkdir = MagicMock()
    return mock_path


@pytest.fixture
def mock_config(
    mock_path_constructor: t.Callable[..., MagicMock],
    tmp_path: Path,
) -> MagicMock:
    from acb.config import Config

    mock_config = MagicMock(spec=Config)

    root_path = tmp_path / "mock_root"
    root_path.mkdir(exist_ok=True)
    settings_path = tmp_path / "mock_settings"
    settings_path.mkdir(exist_ok=True)
    secrets_path = tmp_path / "mock_secrets"
    secrets_path.mkdir(exist_ok=True)
    tmp_path_dir = tmp_path / "mock_tmp"
    tmp_path_dir.mkdir(exist_ok=True)

    root_path_mock = PropertyMock(return_value=root_path)
    type(mock_config).root_path = root_path_mock

    settings_path_mock = PropertyMock(return_value=settings_path)
    type(mock_config).settings_path = settings_path_mock

    secrets_path_mock = PropertyMock(return_value=secrets_path)
    type(mock_config).secrets_path = secrets_path_mock

    tmp_path_mock = PropertyMock(return_value=tmp_path_dir)
    type(mock_config).tmp_path = tmp_path_mock

    mock_config.deployed = False

    return mock_config


@pytest.fixture(scope="module")
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture(autouse=True)
def cleanup_async_tasks() -> Generator[None, Any, Any]:
    before_tasks = set()
    with suppress(RuntimeError):
        before_tasks = asyncio.all_tasks()

    yield

    after_tasks = set()
    try:
        after_tasks = asyncio.all_tasks()
    except RuntimeError:
        return

    new_tasks = after_tasks - before_tasks

    if not new_tasks:
        return

    with suppress(Exception):
        current = asyncio.current_task()
        for task in new_tasks:
            if not task.done() and task != current:
                task.cancel()

        with suppress(RuntimeError):
            loop = asyncio.get_event_loop()
            if loop.is_running():
                with suppress(TimeoutError):
                    future = asyncio.wait_for(
                        asyncio.gather(*new_tasks, return_exceptions=True),
                        timeout=2.0,
                    )
                    loop.run_until_complete(future)


def _get_event_loop() -> asyncio.AbstractEventLoop | None:
    """Get the current event loop safely."""
    try:
        return asyncio.get_event_loop()
    except RuntimeError:
        return None


def _cancel_pending_tasks(loop: asyncio.AbstractEventLoop) -> set[asyncio.Task[t.Any]]:
    """Cancel all pending tasks except the current one."""
    tasks = asyncio.all_tasks(loop=loop)
    if not tasks:
        return set()

    current = asyncio.current_task(loop=loop)

    # Cancel all non-current, non-completed tasks
    for task in tasks:
        if task != current and not task.done():
            task.cancel()

    return tasks


def _wait_for_task_completion(
    loop: asyncio.AbstractEventLoop,
    tasks: set[asyncio.Task[t.Any]],
    timeout: float = 3.0,
) -> None:
    """Wait for tasks to complete with timeout."""
    if not tasks or not loop.is_running():
        return

    with suppress(TimeoutError, RuntimeError):
        future = asyncio.wait_for(
            asyncio.gather(*tasks, return_exceptions=True),
            timeout=timeout,
        )
        loop.run_until_complete(future)


def _close_event_loop(loop: asyncio.AbstractEventLoop) -> None:
    """Safely close the event loop."""
    if loop.is_closed():
        return

    # Final pause to allow any remaining callbacks to run
    with suppress(RuntimeError, asyncio.CancelledError):
        loop.run_until_complete(asyncio.sleep(0.1))

    # Close the loop
    with suppress(Exception) as exc:
        loop.close()

    if exc:
        pass


def pytest_sessionfinish(session: Session, exitstatus: int | pytest.ExitCode) -> None:
    """Clean up asyncio resources when pytest session finishes."""
    # Get the event loop
    loop = _get_event_loop()
    if loop is None:
        return

    # Cancel pending tasks
    tasks = _cancel_pending_tasks(loop)

    # Wait for tasks to complete
    _wait_for_task_completion(loop, tasks)

    # Close the event loop
    with suppress(RuntimeError):
        _close_event_loop(loop)


def pytest_addoption(parser: Parser) -> None:
    parser.addoption(
        "--run-slow",
        action="store_true",
        default=False,
        help="run slow tests",
    )


@pytest.fixture
def mock_tmp_path(tmp_path: Path) -> Path:
    test_dir = tmp_path / "mock_pytest_tmp"

    mock_path = MagicMock(spec=Path)

    mock_path.__str__ = MagicMock(return_value=str(test_dir))
    mock_path.__repr__ = MagicMock(return_value=f"Path('{test_dir}')")

    def path_join(other: str | None) -> MagicMock:
        if other is None:
            return mock_path
        new_path = MagicMock(spec=Path)
        new_path_str = f"{test_dir}/{other}"
        new_path.__str__ = MagicMock(return_value=new_path_str)
        new_path.__repr__ = MagicMock(return_value=f"Path('{new_path_str}')")
        new_path.__truediv__ = MagicMock(
            side_effect=lambda next_part: path_join(f"{other}/{next_part}"),
        )

        new_path.exists = MagicMock(return_value=True)
        new_path.is_dir = MagicMock(return_value=False)
        new_path.is_file = MagicMock(return_value=True)
        new_path.mkdir = MagicMock(return_value=None)
        new_path.write_text = MagicMock(return_value=None)
        new_path.write_bytes = MagicMock(return_value=None)
        new_path.read_text = MagicMock(return_value="")
        new_path.read_bytes = MagicMock(return_value=b"")
        new_path.unlink = MagicMock(return_value=None)

        return new_path

    mock_path.__truediv__ = MagicMock(side_effect=path_join)
    mock_path.exists = MagicMock(return_value=True)
    mock_path.is_dir = MagicMock(return_value=True)
    mock_path.is_file = MagicMock(return_value=False)
    mock_path.mkdir = MagicMock(return_value=None)
    mock_path.write_text = MagicMock(return_value=None)
    mock_path.write_bytes = MagicMock(return_value=None)
    mock_path.read_text = MagicMock(return_value="")
    mock_path.read_bytes = MagicMock(return_value=b"")
    mock_path.unlink = MagicMock(return_value=None)

    return cast("Path", mock_path)


class SimpleFileStorage:
    def __init__(self) -> None:
        self.files: dict[str, bytes] = {}
        self.directories: set[str] = {"/"}

    def write_bytes(self, path: t.Any, content: bytes) -> None:
        self.files[str(path)] = content

    def read_bytes(self, path: t.Any) -> bytes:
        return self.files.get(str(path), b"")

    def exists(self, path: t.Any) -> bool:
        return str(path) in self.files or str(path) in self.directories

    def is_dir(self, path: t.Any) -> bool:
        return str(path) in self.directories

    write_text: Any
    read_text: Any
    mkdir: Any
    unlink: Any
    rmdir: Any


@pytest.fixture
def mock_file_system(tmp_path: Path) -> SimpleFileStorage:
    fs = SimpleFileStorage()

    fs.write_text = lambda path, content, encoding=None: fs.write_bytes(
        path,
        content.encode("utf-8" if encoding is None else encoding),
    )

    fs.read_text = lambda path, encoding=None: fs.read_bytes(path).decode(
        "utf-8" if encoding is None else encoding,
    )

    fs.mkdir = lambda path, parents=False, exist_ok=False: fs.directories.add(str(path))

    fs.unlink = lambda path, missing_ok=False: fs.files.pop(str(path), None)

    fs.rmdir = (
        lambda path: fs.directories.remove(str(path))
        if str(path) in fs.directories
        else None
    )

    return fs


class SimpleAsyncFileStorage:
    def __init__(self) -> None:
        self.files: dict[str, bytes] = {}
        self.directories: set[str] = {"/"}

    async def write_bytes(self, path: t.Any, content: bytes) -> None:
        self.files[str(path)] = content

    async def read_bytes(self, path: t.Any) -> bytes:
        return self.files.get(str(path), b"")

    async def exists(self, path: t.Any) -> bool:
        return str(path) in self.files or str(path) in self.directories

    async def is_dir(self, path: t.Any) -> bool:
        return str(path) in self.directories

    write_text: Any
    read_text: Any
    mkdir: Any
    unlink: Any
    rmdir: Any


@pytest.fixture
def mock_async_file_system(tmp_path: Path) -> SimpleAsyncFileStorage:
    fs = SimpleAsyncFileStorage()

    async def write_text(
        path: t.Any,
        content: str,
        encoding: str | None = None,
    ) -> None:
        return await fs.write_bytes(
            path,
            content.encode("utf-8" if encoding is None else encoding),
        )

    fs.write_text = write_text

    async def read_text(path: t.Any, encoding: str | None = None) -> str:
        return (await fs.read_bytes(path)).decode(
            "utf-8" if encoding is None else encoding,
        )

    fs.read_text = read_text

    async def mkdir(path: t.Any, parents: bool = False, exist_ok: bool = False) -> None:
        fs.directories.add(str(path))

    fs.mkdir = mkdir

    async def unlink(path: t.Any, missing_ok: bool = False) -> None:
        if str(path) in fs.files:
            del fs.files[str(path)]

    fs.unlink = unlink

    async def rmdir(path: t.Any) -> None:
        fs.directories.discard(str(path))

    fs.rmdir = rmdir

    return fs


@pytest.fixture
def mock_settings() -> MagicMock:
    settings = MagicMock()
    settings.app = MagicMock()
    settings.app.name = "test_app"
    settings.app.title = "Test App"
    settings.app.timezone = "UTC"
    settings.storage = MagicMock()
    settings.storage.local_fs = True
    settings.storage.local_path = Path(tempfile.mkdtemp(prefix="mock_storage_"))
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
    settings.debug = MagicMock()
    settings.debug.production = False
    settings.debug.secrets = False
    settings.adapters = MagicMock()
    settings.adapters.dns = "mock"
    settings.adapters.smtp = "mock"
    settings.adapters.ftpd = "mock"
    settings.adapters.storage = "mock"
    settings.adapters.sql = "mock"
    settings.adapters.nosql = "mock"
    settings.adapters.secret = "mock"
    settings.adapters.cache = "mock"
    return settings


@pytest.fixture(autouse=True)
def patch_config(
    monkeypatch: MonkeyPatch,
    mock_config: MagicMock,
    mock_settings: MagicMock,
) -> Generator[None, Any, Any]:
    def mock_get_config() -> MagicMock:
        return mock_config

    def mock_get_settings() -> dict[str, Any]:
        return {
            "app": {
                "name": mock_settings.app.name,
                "title": mock_settings.app.title,
                "domain": "example.com",
                "version": "0.1.0",
                "timezone": mock_settings.app.timezone,
            },
            "storage": {
                "local_fs": mock_settings.storage.local_fs,
                "local_path": mock_settings.storage.local_path,
                "memory_fs": mock_settings.storage.memory_fs,
                "buckets": mock_settings.storage.buckets,
            },
            "logger": {
                "log_level": mock_settings.logger.log_level,
                "format": mock_settings.logger.format,
                "level_per_module": mock_settings.logger.level_per_module,
            },
            "debug": {
                "production": mock_settings.debug.production,
                "secrets": mock_settings.debug.secrets,
            },
            "adapters": {
                "dns": mock_settings.adapters.dns,
                "smtp": mock_settings.adapters.smtp,
                "ftpd": mock_settings.adapters.ftpd,
                "storage": mock_settings.adapters.storage,
                "sql": mock_settings.adapters.sql,
                "nosql": mock_settings.adapters.nosql,
                "secret": mock_settings.adapters.secret,
                "cache": mock_settings.adapters.cache,
            },
        }

    with suppress(ImportError, AttributeError):
        import acb.config

        monkeypatch.setattr(acb.config, "get_config", mock_get_config)
        monkeypatch.setattr(acb.config, "get_settings", mock_get_settings)
    yield


@pytest.fixture
def mock_tempfile() -> MagicMock:
    mock: MagicMock = MagicMock()
    temp_dir = tempfile.mkdtemp(prefix="mock_temp_")
    mock.mkdtemp.return_value = temp_dir
    mock.mkstemp.return_value = (1, str(Path(temp_dir) / "file"))
    mock.gettempdir.return_value = temp_dir
    return mock


@pytest.fixture
def patch_tempfile(monkeypatch: MonkeyPatch, mock_tempfile: MagicMock) -> None:
    monkeypatch.setattr("tempfile", mock_tempfile)


class MockDns:
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.records: dict[str, list[dict[str, Any]]] = {}
        self.zones: dict[str, dict[str, Any]] = {}

    async def get_records(
        self,
        domain: str | None,
        record_type: str | None = None,
    ) -> list[dict[str, Any]]:
        if domain is None:
            return []
        key = f"{domain}:{record_type}" if record_type else domain
        return self.records.get(key, [])

    async def create_record(
        self,
        domain: str | None,
        record_type: str | None,
        value: str | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        if domain is None or record_type is None or value is None:
            return {}
        key = f"{domain}:{record_type}"
        if key not in self.records:
            self.records[key] = []

        record = {
            "id": f"record_{len(self.records[key])}",
            "type": record_type,
            "name": domain,
            "value": value,
        } | kwargs

        self.records[key].append(record)
        return record

    async def delete_record(self, domain: str | None, record_id: str | None) -> bool:
        if domain is None or record_id is None:
            return False
        for key, records in self.records.items():
            if key.startswith(f"{domain}:"):
                for i, record in enumerate(records):
                    if record.get("id") == record_id:
                        del records[i]
                        return True
        return False

    async def create_zone(self, domain: str | None, **kwargs: Any) -> dict[str, Any]:
        if domain is None:
            return {}
        if domain in self.zones:
            return self.zones[domain]

        zone = {"id": f"zone_{len(self.zones)}", "name": domain} | kwargs

        self.zones[domain] = zone
        return zone

    async def get_zone_id(self, domain: str | None) -> str:
        if domain is None:
            return ""
        if domain in self.zones:
            return self.zones[domain]["id"]
        return ""

    async def list_records(
        self,
        domain: str | None,
        record_type: str | None = None,
    ) -> list[dict[str, Any]]:
        return await self.get_records(domain, record_type)

    async def find_existing_record(
        self,
        domain: str | None,
        record_type: str | None,
        value: str | None = None,
    ) -> dict[str, Any]:
        if domain is None or record_type is None:
            return {}
        key = f"{domain}:{record_type}"
        if key in self.records:
            for record in self.records[key]:
                if value is None or record.get("value") == value:
                    return record
        return {}


class MockRequests:
    async def get(self, url: str | None, headers: dict[str, str] | None = None) -> Any:
        if url is None:
            return None
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {}
        return mock_response

    async def post(
        self,
        url: str | None,
        data: Any = None,
        json: Any = None,
        headers: dict[str, str] | None = None,
    ) -> Any:
        if url is None:
            return None
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {}
        return mock_response


class MockStorage:
    async def upload(self, source: Path, destination: str | None) -> None:
        if destination is None:
            return

    async def download(self, source: str | None, destination: Path) -> None:
        if source is None:
            return

    async def list_files(self, path: str | None) -> list[str]:
        if path is None:
            return []
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


@pytest.fixture
def patch_adapter_imports(monkeypatch: MonkeyPatch) -> None:
    with suppress(Exception):
        mock_import_adapter = create_mock_import_adapter()
        import acb.adapters

        monkeypatch.setattr(acb.adapters, "import_adapter", mock_import_adapter)


def configure_mock_for_adapter_test(
    mock_obj: MagicMock,
    methods: list[str] | None = None,
    properties: dict[str, Any] | None = None,
) -> MagicMock:
    init_mock = MagicMock(return_value=None)
    mock_obj.__init__ = init_mock

    if methods:
        for method_name in methods:
            if (
                not hasattr(mock_obj, method_name)
                or getattr(mock_obj, method_name) is None
            ):
                method_mock = MagicMock()
                setattr(mock_obj, method_name, method_mock)

    if properties:
        for prop_name, prop_value in properties.items():
            prop_mock = PropertyMock(return_value=prop_value)
            setattr(type(mock_obj), prop_name, prop_mock)

    return mock_obj


@pytest.fixture(autouse=True, scope="session")
def set_acb_test_secret_path_env() -> Generator[None, Any, Any]:
    temp_dir = tempfile.mkdtemp(prefix="acb_test_secret_")
    os.environ["ACB_TEST_SECRET_PATH"] = temp_dir
    yield


@pytest.fixture(scope="session")
def mock_base_path(tmp_path_factory: t.Any) -> str:
    tmp_path = tmp_path_factory.mktemp("mock_base")
    return str(tmp_path)
