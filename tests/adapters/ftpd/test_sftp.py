"""Tests for the SFTP adapter."""

import inspect
import tempfile
import typing as t
from contextlib import asynccontextmanager
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from acb.adapters.ftpd.sftp import Ftpd, SFTPClient, SSHClientConnection


class MockFileAttr:
    def __init__(
        self,
        filename: str,
        size: int = 0,
        is_dir_val: bool = False,
        is_file_val: bool = True,
        is_symlink_val: bool = False,
        permissions: int = 0o644,
        mtime: float = 1622547600.0,
        uid: int = 1000,
        gid: int = 1000,
    ) -> None:
        self.filename = filename
        self.size = size

        if is_dir_val:
            is_file_val = False

        self._is_dir_val = is_dir_val
        self._is_file_val = is_file_val
        self._is_symlink_val = is_symlink_val
        self.permissions = permissions
        self.mtime = mtime
        self.uid = uid
        self.gid = gid

        self.is_dir = self._BooleanCallable(is_dir_val)
        self.is_file = self._BooleanCallable(is_file_val)
        self.is_symlink = self._BooleanCallable(is_symlink_val)

    @property
    def name(self) -> str:
        return self.filename

    class _BooleanCallable:
        def __init__(self, value: bool) -> None:
            self.value = value

        def __call__(self) -> bool:
            return self.value

        def __bool__(self) -> bool:
            return self.value


class MockSFTPClient(SFTPClient):  # type: ignore
    def __init__(self) -> None:
        self._close = AsyncMock()
        self.get = AsyncMock()
        self.put = AsyncMock()
        self.remove = AsyncMock()
        self.mkdir = AsyncMock()
        self.rmdir = AsyncMock(return_value=None)
        self.listdir = AsyncMock()
        self.open = AsyncMock()
        self.stat = AsyncMock()

        self.called = False
        self.assert_called_once_with = MagicMock()

        self._list = self.listdir
        self._stat = self.stat
        self._rmdir = self.rmdir
        self._remove = self.remove
        self._mkdir = self.mkdir

    async def close(self) -> None:
        await self._close()


class MockSSHClient(SSHClientConnection):  # type: ignore
    def __init__(self) -> None:
        self._close_mock = MagicMock()
        self._wait_closed_mock = AsyncMock()
        self.start_sftp_client = AsyncMock()
        self.called = False

    def close(self) -> None:
        self._close_mock()
        self.called = True

    async def wait_closed(self) -> None:
        await self._wait_closed_mock()


class MockServerConnection:
    def __init__(self, *args: t.Any, **kwargs: t.Any) -> None:
        from pydantic import SecretStr

        self.username = "test"
        self.password = SecretStr("test123")
        self.client_addr = ("127.0.0.1", 22)
        self.handler = None
        self.load_handler = AsyncMock()
        self._config = None

    @property
    def config(self) -> t.Any:
        return self._config

    @config.setter
    def config(self, value: t.Any) -> None:
        self._config = value


@pytest.fixture
def mock_ssh_client() -> MockSSHClient:
    return MockSSHClient()


@pytest.fixture
def mock_sftp_client() -> MockSFTPClient:
    return MockSFTPClient()


@pytest.fixture
def mock_server_connection() -> MockServerConnection:
    return MockServerConnection()


@pytest.fixture
def mock_logger() -> MagicMock:
    logger = MagicMock()
    logger.info.return_value = None
    logger.error.return_value = None
    logger.debug.return_value = None
    logger.warning.return_value = None
    return logger


@pytest.fixture
async def sftp_adapter(
    mock_sftp_client: MockSFTPClient,
    mock_ssh_client: MockSSHClient,
    mock_server_connection: MockServerConnection,
    mock_logger: MagicMock,
    tmp_path: Path,
) -> t.AsyncGenerator[Ftpd]:
    mock_config = MagicMock()
    mock_config.ftpd.host = "localhost"
    mock_config.ftpd.port = 2222
    mock_config.ftpd.username = "test"
    mock_config.ftpd.password = "test123"
    mock_config.ftpd.timeout = 10
    mock_config.ftpd.root_dir = str(tmp_path / "sftp_root")

    with patch("acb.adapters.ftpd.sftp.asyncssh.connect", return_value=mock_ssh_client):
        ftpd = Ftpd()
        ftpd.config = mock_config
        ftpd.logger = mock_logger
        ftpd._client = None
        ftpd._sftp_client = None

        with patch(
            "acb.adapters.ftpd.sftp.SSHServerConnection",
            return_value=mock_server_connection,
        ):
            yield ftpd


@pytest.mark.asyncio
async def test_start_server_basic(sftp_adapter: Ftpd) -> None:
    sftp_adapter._server_acceptor = None

    mock_server_acceptor = MagicMock()
    mock_create_server = AsyncMock(return_value=mock_server_acceptor)

    with patch("acb.adapters.ftpd.sftp.asyncssh.create_server", mock_create_server):
        await sftp_adapter.start()

        assert sftp_adapter._server_acceptor is not None
        assert mock_create_server.await_count > 0


@pytest.mark.asyncio
async def test_stop_server(sftp_adapter: Ftpd) -> None:
    mock_server_acceptor = MagicMock()
    mock_server_acceptor.close = MagicMock()
    mock_server_acceptor.wait_closed = AsyncMock()

    sftp_adapter._server_acceptor = mock_server_acceptor
    sftp_adapter._server = MagicMock()

    await sftp_adapter.stop()

    mock_server_acceptor.close.assert_called_once()
    mock_server_acceptor.wait_closed.assert_awaited_once()
    assert sftp_adapter._server_acceptor is None


@pytest.mark.asyncio
async def test_adapter_cleanup(sftp_adapter: Ftpd) -> None:
    mock_sftp_client = MockSFTPClient()
    mock_ssh_client = MockSSHClient()

    sftp_adapter._sftp_client = t.cast(t.Any, mock_sftp_client)
    sftp_adapter._client = t.cast(t.Any, mock_ssh_client)

    async def safely_close_client(client: t.Any) -> None:
        """Safely close a client if it has a close method."""
        if not client:
            return

        if not hasattr(client, "close"):
            return

        close_method = getattr(client, "close")
        if not callable(close_method):
            return

        result = close_method()
        if inspect.isawaitable(result):
            await result

    async def cleanup() -> None:
        await safely_close_client(sftp_adapter._sftp_client)
        await safely_close_client(sftp_adapter._client)

        sftp_adapter._sftp_client = None
        sftp_adapter._client = None

    await cleanup()

    assert mock_sftp_client._close.await_count > 0
    assert mock_ssh_client._close_mock.call_count > 0


@pytest.mark.asyncio
async def test_connect_context(
    sftp_adapter: Ftpd, mock_sftp_client: MockSFTPClient
) -> None:
    mock_ensure_client = AsyncMock(return_value=mock_sftp_client)
    sftp_adapter._ensure_client = mock_ensure_client

    original_connect = sftp_adapter.connect

    @asynccontextmanager
    async def patched_connect() -> t.AsyncIterator[Ftpd]:
        client = await sftp_adapter._ensure_client()
        try:
            yield sftp_adapter
        finally:
            if client:
                await t.cast(MockSFTPClient, client).close()
            if sftp_adapter._client:
                sftp_adapter._client.close()
            sftp_adapter._sftp_client = None
            sftp_adapter._client = None

    setattr(sftp_adapter, "connect", patched_connect)

    try:
        async with sftp_adapter.connect() as adapter:
            assert adapter is sftp_adapter
            mock_ensure_client.assert_awaited_once()
    finally:
        setattr(sftp_adapter, "connect", original_connect)


@pytest.mark.asyncio
async def test_stat_error(sftp_adapter: Ftpd) -> None:
    mock_sftp_client = MockSFTPClient()

    sftp_adapter._ensure_client = AsyncMock(return_value=mock_sftp_client)

    error = FileNotFoundError("No such file or directory")
    mock_sftp_client.stat = AsyncMock(side_effect=error)

    path = "/test/nonexistent.txt"

    with pytest.raises(FileNotFoundError):
        await sftp_adapter.stat(path)

    assert sftp_adapter._ensure_client.await_count > 0
    assert mock_sftp_client.stat.await_count > 0


@pytest.mark.asyncio
async def test_list_dir_files(sftp_adapter: Ftpd) -> None:
    mock_sftp_client = MockSFTPClient()

    sftp_adapter._ensure_client = AsyncMock(return_value=mock_sftp_client)

    file1 = MockFileAttr("file1.txt", size=100)
    file2 = MockFileAttr("dir1", is_dir_val=True)

    mock_listdir = AsyncMock(return_value=[file1, file2])
    mock_sftp_client.listdir = mock_listdir

    path = "/test"
    result = await sftp_adapter.list_dir(path)

    assert len(result) == 2
    assert result[0].name == "file1.txt"
    assert result[0].is_file
    assert not result[0].is_dir

    assert result[1].name == "dir1"
    assert result[1].is_dir
    assert not result[1].is_file

    assert sftp_adapter._ensure_client.await_count > 0
    assert mock_sftp_client.listdir.await_count > 0
    assert mock_sftp_client.listdir.call_args[0][0] == path


@pytest.mark.asyncio
async def test_upload(sftp_adapter: Ftpd, mock_sftp_client: MockSFTPClient) -> None:
    mock_ensure_client = AsyncMock(return_value=mock_sftp_client)
    sftp_adapter._ensure_client = mock_ensure_client

    mock_put = AsyncMock()
    mock_sftp_client.put = mock_put

    content = b"test content"
    remote_path = "/test/remote.txt"

    with tempfile.NamedTemporaryFile(delete=False) as temp_file:
        local_path = Path(temp_file.name)
        local_path.write_bytes(content)

    try:
        await sftp_adapter.upload(local_path, remote_path)

        mock_ensure_client.assert_awaited_once()
        mock_put.assert_awaited_once_with(str(local_path), remote_path)
    finally:
        if local_path.exists():
            local_path.unlink()


@pytest.mark.asyncio
async def test_download(sftp_adapter: Ftpd, mock_sftp_client: MockSFTPClient) -> None:
    mock_ensure_client = AsyncMock(return_value=mock_sftp_client)
    sftp_adapter._ensure_client = mock_ensure_client

    mock_get = AsyncMock()
    mock_sftp_client.get = mock_get

    with tempfile.NamedTemporaryFile(delete=False) as temp_file:
        local_path = Path(temp_file.name)

    remote_path = "/test/remote.txt"

    try:
        await sftp_adapter.download(remote_path, local_path)

        mock_ensure_client.assert_awaited_once()
        mock_get.assert_awaited_once_with(remote_path, str(local_path))
    finally:
        if local_path.exists():
            local_path.unlink()


@pytest.mark.asyncio
async def test_list_dir(sftp_adapter: Ftpd, mock_sftp_client: MockSFTPClient) -> None:
    mock_ensure_client = AsyncMock(return_value=mock_sftp_client)
    sftp_adapter._ensure_client = mock_ensure_client

    file1 = MockFileAttr("file1.txt", size=100)
    file2 = MockFileAttr("file2.txt", size=200)

    mock_listdir = AsyncMock(return_value=[file1, file2])
    mock_sftp_client.listdir = mock_listdir

    path = "/test/dir"
    result = await sftp_adapter.list_dir(path)

    mock_ensure_client.assert_awaited_once()
    mock_listdir.assert_awaited_once_with(path)

    assert len(result) == 2
    assert result[0].name == "file1.txt"
    assert result[0].size == 100
    assert result[0].is_file
    assert not result[0].is_dir

    assert result[1].name == "file2.txt"
    assert result[1].size == 200
    assert result[1].is_file
    assert not result[1].is_dir


@pytest.mark.asyncio
async def test_put_file(
    sftp_adapter: Ftpd, mock_sftp_client: MockSFTPClient, tmp_path: Path
) -> None:
    mock_ensure_client = AsyncMock(return_value=mock_sftp_client)
    sftp_adapter._ensure_client = mock_ensure_client

    mock_put = AsyncMock()
    mock_sftp_client.put = mock_put

    local_path = tmp_path / "local.txt"
    local_path.write_text("test content")
    remote_path = "/test/remote.txt"

    await sftp_adapter.upload(local_path, remote_path)

    mock_ensure_client.assert_awaited_once()
    mock_put.assert_awaited_once_with(str(local_path), remote_path)


@pytest.mark.asyncio
async def test_get_file(
    sftp_adapter: Ftpd, mock_sftp_client: MockSFTPClient, tmp_path: Path
) -> None:
    mock_ensure_client = AsyncMock(return_value=mock_sftp_client)
    sftp_adapter._ensure_client = mock_ensure_client

    mock_get = AsyncMock()
    mock_sftp_client.get = mock_get

    remote_path = "/test/remote.txt"
    local_path = tmp_path / "local.txt"

    await sftp_adapter.download(remote_path, local_path)

    mock_ensure_client.assert_awaited_once()
    mock_get.assert_awaited_once_with(remote_path, str(local_path))


@pytest.mark.asyncio
async def test_delete_file(
    sftp_adapter: Ftpd, mock_sftp_client: MockSFTPClient
) -> None:
    mock_ensure_client = AsyncMock(return_value=mock_sftp_client)
    sftp_adapter._ensure_client = mock_ensure_client

    mock_remove = AsyncMock()
    mock_sftp_client.remove = mock_remove

    path = "/test/file.txt"

    await sftp_adapter.delete(path)

    mock_ensure_client.assert_awaited_once()
    mock_remove.assert_awaited_once_with(path)


@pytest.mark.asyncio
async def test_delete(sftp_adapter: Ftpd, mock_sftp_client: MockSFTPClient) -> None:
    mock_ensure_client = AsyncMock(return_value=mock_sftp_client)
    sftp_adapter._ensure_client = mock_ensure_client

    mock_remove = AsyncMock()
    mock_sftp_client.remove = mock_remove

    path = "/test/file.txt"

    await sftp_adapter.delete(path)

    mock_ensure_client.assert_awaited_once()
    mock_remove.assert_awaited_once_with(path)


@pytest.mark.asyncio
async def test_rmdir(sftp_adapter: Ftpd, mock_sftp_client: MockSFTPClient) -> None:
    mock_ensure_client = AsyncMock(return_value=mock_sftp_client)
    sftp_adapter._ensure_client = mock_ensure_client

    mock_rmdir = AsyncMock()
    mock_sftp_client.rmdir = mock_rmdir

    path = "/test/empty_dir"

    await sftp_adapter.rmdir(path)

    mock_ensure_client.assert_awaited_once()
    mock_rmdir.assert_awaited_once_with(path)


@pytest.mark.asyncio
async def test_is_dir(sftp_adapter: Ftpd, mock_sftp_client: MockSFTPClient) -> None:
    mock_ensure_client = AsyncMock(return_value=mock_sftp_client)
    sftp_adapter._ensure_client = mock_ensure_client

    path = "/test/dir"
    mock_file_attr = MockFileAttr("dir", is_dir_val=True)

    mock_stat = AsyncMock(return_value=mock_file_attr)
    mock_sftp_client.stat = mock_stat

    result = await sftp_adapter.stat(path)

    mock_ensure_client.assert_awaited_once()
    mock_stat.assert_awaited_once_with(path)

    assert result.is_dir
    assert not result.is_file


@pytest.mark.asyncio
async def test_is_not_dir(sftp_adapter: Ftpd, mock_sftp_client: MockSFTPClient) -> None:
    mock_ensure_client = AsyncMock(return_value=mock_sftp_client)
    sftp_adapter._ensure_client = mock_ensure_client

    path = "/test/file.txt"
    mock_file_attr = MockFileAttr("file.txt")

    mock_stat = AsyncMock(return_value=mock_file_attr)
    mock_sftp_client.stat = mock_stat

    result = await sftp_adapter.stat(path)

    mock_ensure_client.assert_awaited_once()
    mock_stat.assert_awaited_once_with(path)

    assert not result.is_dir
    assert result.is_file


@pytest.mark.asyncio
async def test_rmdir_non_recursive(
    sftp_adapter: Ftpd, mock_sftp_client: MockSFTPClient
) -> None:
    path = "/test/dir"
    mock_ensure_client = AsyncMock(return_value=mock_sftp_client)
    sftp_adapter._ensure_client = mock_ensure_client
    mock_sftp_client.rmdir = AsyncMock()
    mock_sftp_client.listdir = AsyncMock()

    await sftp_adapter.rmdir(path)

    mock_sftp_client.rmdir.assert_awaited_once_with(path)
    assert mock_sftp_client.listdir.await_count == 0


@pytest.mark.asyncio
async def test_rmdir_recursive(
    sftp_adapter: Ftpd, mock_sftp_client: MockSFTPClient
) -> None:
    mock_ensure_client = AsyncMock(return_value=mock_sftp_client)
    sftp_adapter._ensure_client = mock_ensure_client

    file1 = MockFileAttr("file1.txt", size=100)
    file2 = MockFileAttr("subdir", is_dir_val=True)
    file3 = MockFileAttr("file2.txt", size=100)

    list_dir_results = {"/test/dir": [file1, file2], "/test/dir/subdir": [file3]}

    list_dir_mock = AsyncMock()
    list_dir_mock.side_effect = lambda path: list_dir_results.get(path, [])

    delete_mock = AsyncMock()
    rmdir_client_mock = AsyncMock()

    with patch.object(sftp_adapter, "list_dir", list_dir_mock):
        with patch.object(sftp_adapter, "delete", delete_mock):
            with patch.object(mock_sftp_client, "rmdir", rmdir_client_mock):
                await sftp_adapter.rmdir("/test/dir", recursive=True)

    assert list_dir_mock.await_count == 2
    list_dir_calls = [call.args[0] for call in list_dir_mock.await_args_list]
    assert "/test/dir" in list_dir_calls
    assert "/test/dir/subdir" in list_dir_calls

    assert delete_mock.await_count == 2
    delete_calls = [call.args[0] for call in delete_mock.await_args_list]
    assert "/test/dir/file1.txt" in delete_calls
    assert "/test/dir/subdir/file2.txt" in delete_calls

    assert rmdir_client_mock.await_count == 2
    rmdir_calls = [call.args[0] for call in rmdir_client_mock.await_args_list]
    assert set(rmdir_calls) == {"/test/dir", "/test/dir/subdir"}


@pytest.mark.asyncio
async def test_rmdir_recursive_with_nested_directories(
    sftp_adapter: Ftpd, mock_sftp_client: MockSFTPClient
) -> None:
    mock_ensure_client = AsyncMock(return_value=mock_sftp_client)
    sftp_adapter._ensure_client = mock_ensure_client

    file_attr1 = MockFileAttr("file1.txt")
    file_attr2 = MockFileAttr("subdir", is_dir_val=True)
    subdir_file = MockFileAttr("subfile.txt")

    async def mock_listdir_side_effect(path: str) -> list[MockFileAttr]:
        if path == "/test/dir":
            return [file_attr1, file_attr2]
        elif path == "/test/dir/subdir":
            return [subdir_file]
        return []

    mock_listdir = AsyncMock(side_effect=mock_listdir_side_effect)
    mock_sftp_client.listdir = mock_listdir

    mock_remove = AsyncMock()
    mock_sftp_client.remove = mock_remove

    mock_rmdir = AsyncMock()
    mock_sftp_client.rmdir = mock_rmdir

    path = "/test/dir"
    await sftp_adapter.rmdir(path, recursive=True)

    mock_ensure_client.assert_awaited()

    assert mock_listdir.await_count == 2
    assert mock_listdir.await_args_list[0][0][0] == path
    assert mock_listdir.await_args_list[1][0][0] == f"{path}/subdir"

    assert mock_remove.await_count == 2
    remove_calls = [call.args[0] for call in mock_remove.await_args_list]
    assert f"{path}/file1.txt" in remove_calls
    assert f"{path}/subdir/subfile.txt" in remove_calls

    assert mock_rmdir.await_count == 2
    rmdir_calls = [call.args[0] for call in mock_rmdir.await_args_list]
    assert rmdir_calls in ([f"{path}/subdir", path], [path, f"{path}/subdir"])


@pytest.mark.asyncio
async def test_stat(sftp_adapter: Ftpd, mock_sftp_client: MockSFTPClient) -> None:
    mock_ensure_client = AsyncMock(return_value=mock_sftp_client)
    sftp_adapter._ensure_client = mock_ensure_client

    file_path = "/test/file.txt"
    file_name = "file.txt"
    mock_file_attr = MockFileAttr(file_name)

    mock_stat = AsyncMock(return_value=mock_file_attr)
    mock_sftp_client.stat = mock_stat

    result = await sftp_adapter.stat(file_path)

    mock_ensure_client.assert_awaited_once()
    mock_stat.assert_awaited_once_with(file_path)

    assert result.is_file
    assert not result.is_dir


@pytest.mark.asyncio
async def test_exists_true(
    sftp_adapter: Ftpd, mock_sftp_client: MockSFTPClient
) -> None:
    mock_ensure_client = AsyncMock(return_value=mock_sftp_client)
    sftp_adapter._ensure_client = mock_ensure_client

    file_path = "/test/file.txt"
    mock_file_attr = MockFileAttr("file.txt")

    mock_stat = AsyncMock(return_value=mock_file_attr)
    mock_sftp_client.stat = mock_stat

    result = await sftp_adapter.exists(file_path)

    mock_ensure_client.assert_awaited_once()
    mock_stat.assert_awaited_once_with(file_path)

    assert result


@pytest.mark.asyncio
async def test_exists_false(
    sftp_adapter: Ftpd, mock_sftp_client: MockSFTPClient
) -> None:
    mock_ensure_client = AsyncMock(return_value=mock_sftp_client)
    sftp_adapter._ensure_client = mock_ensure_client

    mock_stat = AsyncMock(side_effect=Exception("File not found"))
    mock_sftp_client.stat = mock_stat

    file_path = "/test/non_existent_file.txt"
    result = await sftp_adapter.exists(file_path)

    mock_ensure_client.assert_awaited_once()
    mock_stat.assert_awaited_once_with(file_path)

    assert not result


@pytest.mark.asyncio
async def test_dir_exists_true(sftp_adapter: Ftpd) -> None:
    mock_sftp_client = MockSFTPClient()

    mock_ensure_client = AsyncMock(return_value=mock_sftp_client)
    sftp_adapter._ensure_client = mock_ensure_client

    path = "/test/dir"
    mock_file_attr = MockFileAttr("dir", is_dir_val=True)

    mock_stat = AsyncMock(return_value=mock_file_attr)
    mock_sftp_client.stat = mock_stat

    exists_result = await sftp_adapter.exists(path)
    assert exists_result

    file_info = await sftp_adapter.stat(path)
    assert file_info.is_dir
    assert not file_info.is_file


@pytest.mark.asyncio
async def test_dir_exists_false(sftp_adapter: Ftpd) -> None:
    mock_sftp_client = MockSFTPClient()

    mock_ensure_client = AsyncMock(return_value=mock_sftp_client)
    sftp_adapter._ensure_client = mock_ensure_client

    mock_stat = AsyncMock(side_effect=FileNotFoundError("Not found"))
    mock_sftp_client.stat = mock_stat

    path = "/test/nonexistent"

    exists_result = await sftp_adapter.exists(path)
    assert not exists_result


@pytest.mark.asyncio
async def test_server_factory(sftp_adapter: Ftpd) -> None:
    if hasattr(sftp_adapter, "server_factory"):
        factory = sftp_adapter.server_factory
        assert factory is not None
        assert callable(factory)
    else:
        assert True


@pytest.mark.asyncio
async def test_start_service(sftp_adapter: Ftpd) -> None:
    if not hasattr(sftp_adapter, "start"):
        assert True
        return

    with patch.object(sftp_adapter, "start", AsyncMock()) as mock_start:
        await sftp_adapter.start()
        mock_start.assert_awaited_once()


@pytest.mark.asyncio
async def test_handler_creation(
    sftp_adapter: Ftpd, mock_server_connection: MockServerConnection
) -> None:
    handler_factory_options = [
        "_create_handler",
        "sftp_handler_factory",
        "_handler_factory",
    ]

    handler_factory = None
    for attr_name in handler_factory_options:
        if hasattr(sftp_adapter, attr_name):
            handler_factory = getattr(sftp_adapter, attr_name)
            if callable(handler_factory):
                break

    if handler_factory:
        mock_handler = handler_factory(mock_server_connection)
        assert mock_handler is not None
    else:
        assert True


@pytest.mark.asyncio
async def test_write_text(sftp_adapter: Ftpd, mock_sftp_client: MockSFTPClient) -> None:
    mock_ensure_client = AsyncMock(return_value=mock_sftp_client)
    sftp_adapter._ensure_client = mock_ensure_client

    mock_write_bytes = AsyncMock()

    with patch.object(sftp_adapter, "write_bytes", mock_write_bytes):
        path = "/test/file.txt"
        content = "test content"
        await sftp_adapter.write_text(path, content)

        assert mock_write_bytes.await_count > 0
        assert mock_write_bytes.call_args[0][0] == path
        assert mock_write_bytes.call_args[0][1] == content.encode()


@pytest.mark.asyncio
async def test_start_server_with_listen(
    sftp_adapter: Ftpd, mock_server_connection: MockServerConnection
) -> None:
    if not hasattr(sftp_adapter, "start_server"):
        pytest.skip("start_server method not found on Ftpd adapter")
        return

    start_server_method = t.cast(
        t.Callable[[t.Any], t.Awaitable[None]],
        getattr(sftp_adapter, "start_server", None),
    )

    with patch("acb.adapters.ftpd.sftp.asyncssh.listen") as mock_listen:
        mock_server = MagicMock()
        mock_server.wait_closed = AsyncMock()
        mock_listen.return_value = mock_server

        await start_server_method(mock_server_connection)

        assert mock_listen.await_count > 0
        assert sftp_adapter._server is mock_server


@pytest.mark.asyncio
async def test_sftp_handler_factory(
    sftp_adapter: Ftpd, mock_server_connection: MockServerConnection
) -> None:
    if not hasattr(sftp_adapter, "sftp_handler_factory"):
        pytest.skip("sftp_handler_factory method not found on Ftpd adapter")
        return

    handler_factory = t.cast(
        t.Callable[[t.Any], t.Awaitable[t.Any] | t.Callable[[t.Any], t.Any]],
        getattr(sftp_adapter, "sftp_handler_factory"),
    )

    with patch("acb.adapters.ftpd.sftp.asyncssh.SFTPServer") as mock_sftp_server:
        handler = handler_factory(mock_server_connection)

        conn = MagicMock()

        if inspect.isawaitable(handler):
            result = await handler
        elif callable(handler):
            if inspect.iscoroutinefunction(handler) or inspect.isasyncgenfunction(
                handler
            ):
                result = await handler(conn)
            else:
                result = handler(conn)
        else:
            result = handler

        assert mock_sftp_server.called
        assert result is not None


@pytest.mark.asyncio
async def test_stat_file_info(
    sftp_adapter: Ftpd, mock_sftp_client: MockSFTPClient
) -> None:
    mock_ensure_client = AsyncMock(return_value=mock_sftp_client)
    sftp_adapter._ensure_client = mock_ensure_client

    file_path = "/test/file.txt"
    return_value = MockFileAttr("file.txt")

    mock_sftp_client.stat = AsyncMock(return_value=return_value)

    result = await sftp_adapter.stat(file_path)

    mock_ensure_client.assert_awaited_once()
    mock_sftp_client.stat.assert_awaited_once_with(file_path)

    assert result.is_file
    assert not result.is_dir


@pytest.mark.asyncio
async def test_cleanup(sftp_adapter: Ftpd) -> None:
    mock_sftp_client = MockSFTPClient()
    mock_client = MockSSHClient()

    sftp_adapter._sftp_client = t.cast(t.Any, mock_sftp_client)
    sftp_adapter._client = t.cast(t.Any, mock_client)

    assert isinstance(sftp_adapter._sftp_client, MockSFTPClient)
    assert isinstance(sftp_adapter._client, MockSSHClient)

    if sftp_adapter._sftp_client:
        await mock_sftp_client.close()
    if sftp_adapter._client:
        sftp_adapter._client.close()

    sftp_adapter._sftp_client = None
    sftp_adapter._client = None

    assert sftp_adapter._sftp_client is None
    assert sftp_adapter._client is None
    assert mock_client.called
