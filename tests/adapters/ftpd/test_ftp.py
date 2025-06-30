"""Tests for the FTP adapter."""

import tempfile
import typing as t
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aioftp import Client as AioFtpClient
from acb.adapters.ftpd._base import FileInfo
from acb.adapters.ftpd.ftp import Ftpd, FtpdSettings


@t.runtime_checkable
class MockFtpClientProtocol(t.Protocol):
    _connect: AsyncMock
    _login: AsyncMock
    _quit: AsyncMock
    _upload: AsyncMock
    _download: AsyncMock
    _list: AsyncMock
    _make_directory: AsyncMock
    _remove_directory: AsyncMock
    _remove_file: AsyncMock
    _rename: AsyncMock
    _stat: AsyncMock

    async def connect(self, host: str, port: int) -> None: ...
    async def login(self, username: str, password: str) -> None: ...
    async def quit(self) -> None: ...
    async def upload(self, local_path: str, remote_path: str) -> None: ...
    async def download(self, remote_path: str, local_path: str) -> None: ...
    def list(self, path: str) -> t.AsyncIterator[tuple[None, dict[str, t.Any]]]: ...
    async def make_directory(self, path: str) -> None: ...
    async def remove_directory(self, path: str) -> None: ...
    async def remove_file(self, path: str) -> None: ...
    async def rename(self, old_path: str, new_path: str) -> None: ...
    async def stat(self, path: str) -> dict[str, t.Any]: ...


class MockFtpClient(MockFtpClientProtocol):
    def __init__(self) -> None:
        self._connect = AsyncMock()
        self._login = AsyncMock()
        self._quit = AsyncMock()
        self._upload = AsyncMock()
        self._download = AsyncMock()
        self._list = AsyncMock()
        self._make_directory = AsyncMock()
        self._remove_directory = AsyncMock()
        self._remove_file = AsyncMock()
        self._rename = AsyncMock()
        self._stat = AsyncMock()

    async def connect(self, host: str, port: int) -> None:
        return await self._connect(host, port)

    async def login(self, username: str, password: str) -> None:
        return await self._login(username, password)

    async def quit(self) -> None:
        return await self._quit()

    async def upload(self, local_path: str, remote_path: str) -> None:
        return await self._upload(local_path, remote_path)

    async def download(self, remote_path: str, local_path: str) -> None:
        return await self._download(remote_path, local_path)

    def list(self, path: str) -> t.AsyncIterator[tuple[None, dict[str, t.Any]]]:
        async def _list_generator() -> t.AsyncIterator[tuple[None, dict[str, t.Any]]]:
            file_infos = await self._list(path)
            for info in file_infos:
                yield info

        return _list_generator()

    async def make_directory(self, path: str) -> None:
        return await self._make_directory(path)

    async def remove_directory(self, path: str) -> None:
        return await self._remove_directory(path)

    async def remove_file(self, path: str) -> None:
        return await self._remove_file(path)

    async def rename(self, old_path: str, new_path: str) -> None:
        return await self._rename(old_path, new_path)

    async def stat(self, path: str) -> dict[str, t.Any]:
        return await self._stat(path)


class MockServer:
    def __init__(self, **kwargs: t.Any) -> None:
        self.kwargs = kwargs
        self._start = AsyncMock()
        self._close = AsyncMock()

    async def start(self) -> None:
        return await self._start()

    async def close(self) -> None:
        return await self._close()


class MockPathIO:
    def __init__(self) -> None:
        pass


@pytest.fixture
def mock_server() -> MockServer:
    return MockServer()


@pytest.fixture
def mock_client() -> MockFtpClient:
    client = MockFtpClient()

    client._connect.return_value = None
    client._login.return_value = None
    client._quit.return_value = None
    client._upload.return_value = None
    client._download.return_value = None
    client._make_directory.return_value = None
    client._remove_directory.return_value = None
    client._remove_file.return_value = None
    client._rename.return_value = None

    file_infos = [
        (
            None,
            {
                "name": "file1.txt",
                "size": 100,
                "type": "file",
                "permissions": "rw-r--r--",
                "modify": 1621234567.0,
                "owner": "user",
                "group": "users",
            },
        ),
        (
            None,
            {
                "name": "folder1",
                "size": 0,
                "type": "dir",
                "permissions": "rwxr-xr-x",
                "modify": 1621234567.0,
                "owner": "user",
                "group": "users",
            },
        ),
    ]
    client._list.return_value = file_infos

    client._stat.return_value = {
        "name": "file.txt",
        "size": 100,
        "type": "file",
        "permissions": "rw-r--r--",
        "modify": 1621234567.0,
        "owner": "user",
        "group": "users",
    }

    return client


@pytest.fixture
async def ftpd_adapter(
    mock_client: MockFtpClient, mock_server: MockServer
) -> t.AsyncGenerator[Ftpd]:
    with (
        patch("aioftp.Client", return_value=mock_client),
        patch("aioftp.Server", return_value=mock_server),
    ):
        mock_config = MagicMock()
        mock_config.ftpd.root_directory = tempfile.gettempdir()
        mock_config.ftpd.host = "127.0.0.1"
        mock_config.ftpd.port = 8021
        mock_config.ftpd.username = "user"
        mock_config.ftpd.password = MagicMock()
        mock_config.ftpd.password.get_secret_value.return_value = "password"
        mock_config.ftpd.passive_ports_min = 50000
        mock_config.ftpd.passive_ports_max = 50100
        mock_config.ftpd.timeout = 30
        mock_config.ftpd.anonymous = False
        mock_config.ftpd.root_dir = tempfile.gettempdir()

        adapter = Ftpd()
        adapter.config = mock_config
        adapter._client = mock_client

        adapter.__class__.server = property(lambda self: mock_server)

        yield adapter


class TestFtpdSettings:
    def test_default_values(self) -> None:
        settings = FtpdSettings()

        assert settings.port == 8021
        assert settings.passive_ports_min == 50000
        assert settings.passive_ports_max == 50100
        assert settings.timeout == 30


@pytest.mark.asyncio
async def test_start_server(ftpd_adapter: Ftpd, mock_server: MockServer) -> None:
    mock_logger = MagicMock()

    await ftpd_adapter.start(logger=mock_logger)

    mock_server._start.assert_called_once()
    mock_logger.info.assert_called_once()

    mock_server._start.side_effect = Exception("Server start error")

    with pytest.raises(Exception, match="Server start error"):
        await ftpd_adapter.start(logger=mock_logger)

    mock_server._close.assert_called_once()
    mock_logger.error.assert_called_once()


@pytest.mark.asyncio
async def test_stop_server(ftpd_adapter: Ftpd, mock_server: MockServer) -> None:
    mock_logger = MagicMock()

    await ftpd_adapter.stop(logger=mock_logger)

    mock_server._close.assert_called_once()
    mock_logger.info.assert_called_once_with("FTP server stopped")

    mock_server._close.side_effect = Exception("Server stop error")
    mock_logger.reset_mock()

    with pytest.raises(Exception, match="Server stop error"):
        await ftpd_adapter.stop(logger=mock_logger)

    mock_logger.error.assert_called_once()


@pytest.mark.asyncio
async def test_ensure_client(ftpd_adapter: Ftpd, mock_client: MockFtpClient) -> None:
    ftpd_adapter._client = None

    async def mock_ensure_client() -> AioFtpClient:
        ftpd_adapter._client = t.cast(AioFtpClient, mock_client)
        return t.cast(AioFtpClient, mock_client)

    original_ensure_client = ftpd_adapter._ensure_client

    try:
        ftpd_adapter._ensure_client = mock_ensure_client

        path = "/test_path"
        await ftpd_adapter.list_dir(path)

        mock_client._list.assert_called_once_with(path)
    finally:
        ftpd_adapter._ensure_client = original_ensure_client


@pytest.mark.asyncio
async def test_upload(ftpd_adapter: Ftpd, mock_client: MockFtpClient) -> None:
    temp_dir = tempfile.gettempdir()
    local_path = Path(temp_dir) / "local_file.txt"
    remote_path = "/remote/file.txt"

    await ftpd_adapter.upload(local_path, remote_path)

    mock_client._upload.assert_called_once_with(str(local_path), remote_path)


@pytest.mark.asyncio
async def test_download(ftpd_adapter: Ftpd, mock_client: MockFtpClient) -> None:
    remote_path = "/remote/file.txt"
    temp_dir = tempfile.gettempdir()
    local_path = Path(temp_dir) / "local_file.txt"

    await ftpd_adapter.download(remote_path, local_path)

    mock_client._download.assert_called_once_with(remote_path, str(local_path))


@pytest.mark.asyncio
async def test_list_dir(ftpd_adapter: Ftpd, mock_client: MockFtpClient) -> None:
    path = "/remote"

    result = await ftpd_adapter.list_dir(path)

    mock_client._list.assert_called_once_with(path)
    assert len(result) == 2
    assert isinstance(result[0], FileInfo)
    assert result[0].name == "file1.txt"
    assert result[1].name == "folder1"


@pytest.mark.asyncio
async def test_mkdir(ftpd_adapter: Ftpd, mock_client: MockFtpClient) -> None:
    path = "/remote/new_dir"

    await ftpd_adapter.mkdir(path)

    mock_client._make_directory.assert_called_once_with(path)


@pytest.mark.asyncio
async def test_rmdir_non_recursive(
    ftpd_adapter: Ftpd, mock_client: MockFtpClient
) -> None:
    path = "/remote/empty_dir"

    await ftpd_adapter.rmdir(path)

    mock_client._remove_directory.assert_called_once_with(path)
    mock_client._list.assert_not_called()


@pytest.mark.asyncio
async def test_rmdir_recursive(ftpd_adapter: Ftpd, mock_client: MockFtpClient) -> None:
    original_list_dir = ftpd_adapter.list_dir
    original_delete = ftpd_adapter.delete

    try:
        call_tracker = {"list_dir": [], "delete": [], "rmdir": []}

        async def mock_list_dir(path: str) -> list[FileInfo]:
            call_tracker["list_dir"].append(path)
            if path == "/test/dir":
                return [
                    FileInfo(
                        name="file1.txt",
                        size=100,
                        permissions="rw-r--r--",
                        mtime=1621234567.0,
                    ),
                    FileInfo(
                        name="subdir",
                        is_file=False,
                        is_dir=True,
                        permissions="rwxr-xr-x",
                        mtime=1621234567.0,
                    ),
                ]
            return []

        async def mock_delete(path: str) -> None:
            call_tracker["delete"].append(path)
            return None

        async def mock_rmdir_non_recursive(path: str) -> None:
            call_tracker["rmdir"].append(path)
            return None

        ftpd_adapter.list_dir = mock_list_dir
        ftpd_adapter.delete = mock_delete

        async def mock_rmdir(path: str, recursive: bool = False) -> None:
            if recursive:
                files = await ftpd_adapter.list_dir(path)
                for file in files:
                    full_path = f"{path}/{file.name}"
                    if file.is_dir:
                        await mock_rmdir(full_path, recursive=True)
                    else:
                        await ftpd_adapter.delete(full_path)
                await mock_rmdir_non_recursive(path)
            else:
                await mock_rmdir_non_recursive(path)

        ftpd_adapter.rmdir = mock_rmdir

        path = "/test/dir"
        await ftpd_adapter.rmdir(path, recursive=True)

        assert call_tracker["list_dir"] == ["/test/dir", "/test/dir/subdir"]
        assert call_tracker["delete"] == ["/test/dir/file1.txt"]
        assert call_tracker["rmdir"] == ["/test/dir/subdir", "/test/dir"]
    finally:
        ftpd_adapter.list_dir = original_list_dir
        ftpd_adapter.delete = original_delete


@pytest.mark.asyncio
async def test_delete(ftpd_adapter: Ftpd, mock_client: MockFtpClient) -> None:
    path = "/remote/file.txt"

    await ftpd_adapter.delete(path)

    mock_client._remove_file.assert_called_once_with(path)


@pytest.mark.asyncio
async def test_rename(ftpd_adapter: Ftpd, mock_client: MockFtpClient) -> None:
    old_path = "/remote/old.txt"
    new_path = "/remote/new.txt"

    await ftpd_adapter.rename(old_path, new_path)

    mock_client._rename.assert_called_once_with(old_path, new_path)


@pytest.mark.asyncio
async def test_exists_true(ftpd_adapter: Ftpd, mock_client: MockFtpClient) -> None:
    path = "/remote/file.txt"

    result = await ftpd_adapter.exists(path)

    mock_client._stat.assert_called_once_with(path)
    assert result


@pytest.mark.asyncio
async def test_exists_false(ftpd_adapter: Ftpd, mock_client: MockFtpClient) -> None:
    path = "/remote/nonexistent.txt"
    mock_client._stat.side_effect = Exception("File not found")

    result = await ftpd_adapter.exists(path)

    mock_client._stat.assert_called_once_with(path)
    assert not result


@pytest.mark.asyncio
async def test_stat(ftpd_adapter: Ftpd, mock_client: MockFtpClient) -> None:
    path = "/remote/file.txt"

    result = await ftpd_adapter.stat(path)

    mock_client._stat.assert_called_once_with(path)
    assert isinstance(result, FileInfo)
    assert result.name == "file.txt"
    assert result.size == 100
    assert result.is_file
    assert not result.is_dir


@pytest.mark.asyncio
async def test_read_text(ftpd_adapter: Ftpd, mock_client: MockFtpClient) -> None:
    with (
        patch("tempfile.mkdtemp") as mock_mkdtemp,
        patch("acb.adapters.ftpd.ftp.Path") as mock_path,
        patch("acb.adapters.ftpd.ftp.AsyncPath") as mock_async_path,
        patch("acb.adapters.ftpd.ftp.os"),
    ):
        temp_dir = tempfile.gettempdir()
        safe_temp_dir = f"{temp_dir}/temp_dir"
        mock_mkdtemp_typed: t.Any = mock_mkdtemp
        mock_mkdtemp_typed.return_value = safe_temp_dir

        mock_temp_path = MagicMock()
        mock_path_typed: t.Any = mock_path
        mock_path_typed.return_value = mock_temp_path

        truediv_method: t.Any = mock_temp_path.__truediv__
        truediv_method.return_value = mock_temp_path

        str_method: t.Any = mock_temp_path.__str__
        str_method.return_value = f"{safe_temp_dir}/file.txt"

        mock_temp_path.exists = MagicMock(return_value=True)
        mock_temp_path.unlink = MagicMock()

        # Mock AsyncPath and its read_text method
        mock_async_path_instance = MagicMock()
        mock_async_path.return_value = mock_async_path_instance
        mock_async_path_instance.read_text = AsyncMock(return_value="file contents")

        path = "/remote/file.txt"
        result = await ftpd_adapter.read_text(path)

        assert result == "file contents"
        mock_async_path_instance.read_text.assert_called_once()
        mock_client._download.assert_called_once()
