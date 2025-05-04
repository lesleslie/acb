import os
import typing as t
from contextlib import asynccontextmanager
from pathlib import Path
from types import TracebackType
from typing import Optional, Type
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import SecretStr
from acb.adapters.ftpd._base import FileInfo, FtpdBase, FtpdBaseSettings
from acb.adapters.ftpd.ftp import Ftpd as FTPAdapter
from acb.adapters.ftpd.ftp import FtpdSettings as FTPSettings
from acb.adapters.ftpd.sftp import Ftpd as SFTPAdapter
from acb.adapters.ftpd.sftp import FtpdSettings as SFTPSettings


class MockFtpdBase(FtpdBase):
    def __init__(self) -> None:
        self.config = MagicMock()
        self.logger = MagicMock()
        self._files: dict[str, bytes] = {}
        self._dirs: set[str] = {"/"}

    async def start(self) -> None:
        self.logger.info("Mock FTP/SFTP server started")

    async def stop(self) -> None:
        self.logger.info("Mock FTP/SFTP server stopped")

    async def upload(self, local_path: Path, remote_path: str) -> None:
        mock_content = b"Mock file content"
        await self.write_bytes(remote_path, mock_content)

    async def download(self, remote_path: str, local_path: Path) -> None:
        await self.read_bytes(remote_path)

    async def list_dir(self, path: str) -> t.List[FileInfo]:
        if path not in self._dirs:
            raise FileNotFoundError(f"Directory not found: {path}")

        result = []
        for file_path, content in self._files.items():
            dir_name = os.path.dirname(file_path)
            if dir_name == path:
                file_name = os.path.basename(file_path)
                info = FileInfo(name=file_name, size=len(content))
                result.append(info)

        for dir_path in self._dirs:
            if dir_path != path and os.path.dirname(dir_path) == path:
                dir_name = os.path.basename(dir_path)
                info = FileInfo(name=dir_name, is_dir=True, is_file=False)
                result.append(info)

        return result

    async def mkdir(self, path: str) -> None:
        self._dirs.add(path)
        parent = os.path.dirname(path)
        if parent and parent != "/" and parent not in self._dirs:
            await self.mkdir(parent)

    async def rmdir(self, path: str, recursive: bool = False) -> None:
        if path not in self._dirs:
            raise FileNotFoundError(f"Directory not found: {path}")

        if recursive:
            for file_path in list(self._files.keys()):
                if os.path.dirname(file_path) == path:
                    del self._files[file_path]

            for dir_path in list(self._dirs):
                if dir_path != path and dir_path.startswith(path + "/"):
                    self._dirs.remove(dir_path)

        self._dirs.remove(path)

    async def delete(self, path: str) -> None:
        if path not in self._files:
            raise FileNotFoundError(f"File not found: {path}")
        del self._files[path]

    async def rename(self, old_path: str, new_path: str) -> None:
        if old_path in self._files:
            self._files[new_path] = self._files[old_path]
            del self._files[old_path]
        elif old_path in self._dirs:
            self._dirs.add(new_path)
            self._dirs.remove(old_path)

            for file_path in list(self._files.keys()):
                if file_path.startswith(old_path + "/"):
                    new_file_path = new_path + file_path[len(old_path) :]
                    self._files[new_file_path] = self._files[file_path]
                    del self._files[file_path]

            for dir_path in list(self._dirs):
                if dir_path.startswith(old_path + "/"):
                    new_dir_path = new_path + dir_path[len(old_path) :]
                    self._dirs.add(new_dir_path)
                    self._dirs.remove(dir_path)
        else:
            raise FileNotFoundError(f"Path not found: {old_path}")

    async def exists(self, path: str) -> bool:
        return path in self._files or path in self._dirs

    async def stat(self, path: str) -> FileInfo:
        if path in self._files:
            return FileInfo(
                name=os.path.basename(path),
                size=len(self._files[path]),
            )
        elif path in self._dirs:
            return FileInfo(
                name=os.path.basename(path) or path, is_dir=True, is_file=False
            )
        else:
            raise FileNotFoundError(f"Path not found: {path}")

    async def read_text(self, path: str) -> str:
        return (await self.read_bytes(path)).decode()

    async def read_bytes(self, path: str) -> bytes:
        if path not in self._files:
            raise FileNotFoundError(f"File not found: {path}")
        return self._files[path]

    async def write_text(self, path: str, content: str) -> None:
        await self.write_bytes(path, content.encode())

    async def write_bytes(self, path: str, content: bytes) -> None:
        parent = os.path.dirname(path)
        if parent and parent != "/" and parent not in self._dirs:
            await self.mkdir(parent)
        self._files[path] = content

    async def __aenter__(self) -> t.Any:
        return self

    async def __aexit__(
        self,
        _exc_type: Optional[Type[BaseException]],
        _exc_val: Optional[BaseException],
        _exc_tb: Optional[TracebackType],
    ) -> None:
        pass

    @asynccontextmanager
    async def connect(self) -> "t.AsyncGenerator[FtpdBase, None]":
        yield self


class TestFtpdBaseSettings:
    def test_init(self) -> None:
        settings = FtpdBaseSettings()

        assert settings.host == "127.0.0.1"
        assert settings.port == 8021
        assert settings.max_connections == 42
        assert settings.username == "ftpuser"
        assert settings.password.get_secret_value() == "ftppass"
        assert settings.anonymous is False
        assert settings.root_dir == "/tmp/ftp"  # nosec B108
        assert settings.use_tls is False
        assert settings.cert_file is None
        assert settings.key_file is None

        settings = FtpdBaseSettings(
            host="custom_host",
            port=2121,
            max_connections=100,
            username="custom_user",
            password=SecretStr("custom_pass"),
            anonymous=True,
            root_dir="/custom/path",
            use_tls=True,
            cert_file="/path/to/cert.pem",
            key_file="/path/to/key.pem",
        )

        assert settings.host == "custom_host"
        assert settings.port == 2121
        assert settings.max_connections == 100
        assert settings.username == "custom_user"
        assert settings.password.get_secret_value() == "custom_pass"
        assert settings.anonymous is True
        assert settings.root_dir == "/custom/path"
        assert settings.use_tls is True
        assert settings.cert_file == "/path/to/cert.pem"
        assert settings.key_file == "/path/to/key.pem"


class TestFileInfo:
    def test_init(self) -> None:
        info = FileInfo(name="test.txt")
        assert info.name == "test.txt"
        assert info.size == 0
        assert not info.is_dir
        assert info.is_file
        assert not info.is_symlink
        assert info.permissions == ""
        assert info.mtime == 0.0
        assert info.owner == ""
        assert info.group == ""

        info = FileInfo(
            name="test.txt",
            size=1024,
            is_dir=True,
            is_file=False,
            is_symlink=True,
            permissions="rwxr-xr-x",
            mtime=1234567890.0,
            owner="user",
            group="group",
        )
        assert info.name == "test.txt"
        assert info.size == 1024
        assert info.is_dir
        assert not info.is_file
        assert info.is_symlink
        assert info.permissions == "rwxr-xr-x"
        assert info.mtime == 1234567890.0
        assert info.owner == "user"
        assert info.group == "group"


class TestMockFtpdBase:
    @pytest.fixture
    def ftpd(self) -> MockFtpdBase:
        return MockFtpdBase()

    @pytest.mark.asyncio
    async def test_start_stop(self, ftpd: MockFtpdBase) -> None:
        await ftpd.start()
        ftpd.logger.info.assert_called_with("Mock FTP/SFTP server started")

        await ftpd.stop()
        ftpd.logger.info.assert_called_with("Mock FTP/SFTP server stopped")

    @pytest.mark.asyncio
    async def test_file_operations(self, ftpd: MockFtpdBase) -> None:
        await ftpd.write_text("/test.txt", "Hello, world!")

        assert await ftpd.exists("/test.txt")

        content = await ftpd.read_text("/test.txt")
        assert content == "Hello, world!"

        info = await ftpd.stat("/test.txt")
        assert info.name == "test.txt"
        assert info.size == 13
        assert info.is_file
        assert not info.is_dir

        await ftpd.rename("/test.txt", "/renamed.txt")
        assert not await ftpd.exists("/test.txt")
        assert await ftpd.exists("/renamed.txt")

        await ftpd.delete("/renamed.txt")
        assert not await ftpd.exists("/renamed.txt")

    @pytest.mark.asyncio
    async def test_directory_operations(self, ftpd: MockFtpdBase) -> None:
        await ftpd.mkdir("/testdir")

        assert await ftpd.exists("/testdir")

        info = await ftpd.stat("/testdir")
        assert info.name == "testdir"
        assert info.is_dir
        assert not info.is_file

        await ftpd.write_text("/testdir/test.txt", "Hello, world!")

        files = await ftpd.list_dir("/")
        assert len(files) == 1
        assert files[0].name == "testdir"
        assert files[0].is_dir

        files = await ftpd.list_dir("/testdir")
        assert len(files) == 1
        assert files[0].name == "test.txt"
        assert files[0].is_file

        await ftpd.rename("/testdir", "/renamed")
        assert not await ftpd.exists("/testdir")
        assert await ftpd.exists("/renamed")
        assert await ftpd.exists("/renamed/test.txt")

        with pytest.raises(Exception):
            await ftpd.rmdir("/renamed")

        await ftpd.rmdir("/renamed", recursive=True)
        assert not await ftpd.exists("/renamed")

    @pytest.mark.asyncio
    async def test_upload_download(self, ftpd: MockFtpdBase) -> None:
        mock_local_path = MagicMock(spec=Path)

        await ftpd.upload(mock_local_path, "/uploaded.txt")

        assert await ftpd.exists("/uploaded.txt")

        content = await ftpd.read_text("/uploaded.txt")
        assert content is not None

        mock_download_path = MagicMock(spec=Path)

        await ftpd.download("/uploaded.txt", mock_download_path)


class TestFTPAdapter:
    @pytest.fixture
    def ftpd(self) -> FTPAdapter:
        adapter = FTPAdapter()
        adapter.config = MagicMock()
        adapter.config.ftpd = FTPSettings(
            host="127.0.0.1",
            port=8021,
            username="ftpuser",
            password=SecretStr("ftppass"),
            root_dir="/mock/ftp",
        )
        adapter.logger = MagicMock()
        return adapter

    def test_server_property(self, ftpd: FTPAdapter) -> None:
        with patch("os.makedirs") as mock_makedirs:
            server = ftpd.server

            mock_makedirs.assert_called_once_with("/mock/ftp", exist_ok=True)
            assert server is not None

            server2 = ftpd.server
            assert server2 is server

    @pytest.mark.asyncio
    async def test_start(self, ftpd: FTPAdapter) -> None:
        with patch.object(ftpd, "server") as mock_server:
            mock_server.start = AsyncMock()

            await ftpd.start()

            mock_server.start.assert_called_once()
            ftpd.logger.info.assert_called_once()

    @pytest.mark.asyncio
    async def test_stop(self, ftpd: FTPAdapter) -> None:
        with patch.object(ftpd, "server") as mock_server:
            mock_server.close = AsyncMock()

            await ftpd.stop()

            mock_server.close.assert_called_once()
            ftpd.logger.info.assert_called_once()


class TestSFTPAdapter:
    @pytest.fixture
    def ftpd(self) -> SFTPAdapter:
        adapter = SFTPAdapter()
        adapter.config = MagicMock()
        adapter.config.ftpd = SFTPSettings(
            host="127.0.0.1",
            port=8022,
            username="ftpuser",
            password=SecretStr("ftppass"),
            root_dir="/mock/sftp",
            server_host_keys=["ssh_host_key"],
            authorized_client_keys="authorized_keys",
        )
        adapter.logger = MagicMock()
        return adapter

    def test_server_factory_property(self, ftpd: SFTPAdapter) -> None:
        factory = ftpd.server_factory
        assert factory is not None

        factory2 = ftpd.server_factory
        assert factory2 is factory

    @pytest.mark.asyncio
    async def test_start(self, ftpd: SFTPAdapter) -> None:
        with (
            patch("os.makedirs") as mock_makedirs,
            patch(
                "asyncssh.create_server", new_callable=AsyncMock
            ) as mock_create_server,
        ):
            mock_server = MagicMock()
            mock_create_server.return_value = mock_server

            await ftpd.start()

            mock_makedirs.assert_called_once_with("/mock/sftp", exist_ok=True)
            mock_create_server.assert_called_once()
            ftpd.logger.info.assert_called_once()
            assert ftpd._server is mock_server

    @pytest.mark.asyncio
    async def test_stop(self, ftpd: SFTPAdapter) -> None:
        mock_server = MagicMock()
        mock_server.close = MagicMock()
        mock_server.wait_closed = AsyncMock()
        ftpd._server = mock_server

        await ftpd.stop()

        mock_server.close.assert_called_once()
        mock_server.wait_closed.assert_called_once()
        ftpd.logger.info.assert_called_once()
        assert ftpd._server is None

    def test_create_server_connection(self, ftpd: SFTPAdapter) -> None:
        connection = ftpd._create_server_connection()
        assert connection is not None

    def test_process_factory(self, ftpd: SFTPAdapter) -> None:
        mock_process = MagicMock()
        mock_process.exit = MagicMock()

        ftpd._process_factory(mock_process)

        mock_process.exit.assert_called_once_with(0)
