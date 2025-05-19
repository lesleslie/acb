"""Tests for the FTPD Base adapter."""

import typing as t
from contextlib import asynccontextmanager
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from acb.adapters.ftpd._base import FileInfo, FtpdBase, FtpdBaseSettings


class MockFtpdBaseSettings(FtpdBaseSettings):
    pass


class MockFtpd(FtpdBase):
    def __init__(self) -> None:
        super().__init__()
        self.config = MagicMock()
        self.logger = MagicMock()
        self._connect = AsyncMock()
        self._disconnect = AsyncMock()
        self._list_files = AsyncMock()
        self._upload_file = AsyncMock()
        self._download_file = AsyncMock()
        self._delete_file = AsyncMock()
        self._create_directory = AsyncMock()
        self._remove_directory = AsyncMock()
        self._rename = AsyncMock()

    async def disconnect(self) -> None:
        await self._disconnect()

    async def list_files(self, path: str) -> list[str]:
        return await self._list_files(path)

    async def upload_file(self, local_path: str, remote_path: str) -> None:
        await self._upload_file(local_path, remote_path)

    async def download_file(self, remote_path: str, local_path: str) -> None:
        await self._download_file(remote_path, local_path)

    async def delete_file(self, path: str) -> None:
        await self._delete_file(path)

    async def create_directory(self, path: str) -> None:
        await self._create_directory(path)

    async def remove_directory(self, path: str) -> None:
        await self._remove_directory(path)

    async def rename(self, old_path: str, new_path: str) -> None:
        await self._rename(old_path, new_path)

    async def start(self) -> None:
        pass

    async def stop(self) -> None:
        pass

    async def upload(self, local_path: Path, remote_path: str) -> None:
        pass

    async def download(self, remote_path: str, local_path: Path) -> None:
        pass

    async def list_dir(self, path: str) -> t.List[FileInfo]:
        return []

    async def mkdir(self, path: str) -> None:
        pass

    async def rmdir(self, path: str, recursive: bool = False) -> None:
        pass

    async def delete(self, path: str) -> None:
        pass

    async def exists(self, path: str) -> bool:
        return False

    async def stat(self, path: str) -> FileInfo:
        return FileInfo("test")

    async def read_text(self, path: str) -> str:
        return ""

    async def read_bytes(self, path: str) -> bytes:
        return b""

    async def write_text(self, path: str, content: str) -> None:
        pass

    async def write_bytes(self, path: str, content: bytes) -> None:
        pass

    @asynccontextmanager
    async def connect(self) -> t.AsyncGenerator["FtpdBase", None]:
        await self._connect()
        yield self
        await self._disconnect()


class TestFtpdBaseSettings:
    def test_init(self) -> None:
        from pydantic import SecretStr

        settings = MockFtpdBaseSettings(
            host="localhost",
            port=21,
            username="user",
            password=SecretStr("pass"),
        )
        assert settings.host == "localhost"
        assert settings.port == 21
        assert settings.username == "user"
        assert settings.password.get_secret_value() == "pass"


class TestFtpdBase:
    @pytest.fixture
    def ftpd(self) -> MockFtpd:
        ftpd = MockFtpd()
        ftpd._connect.reset_mock()
        ftpd._disconnect.reset_mock()
        ftpd._list_files.reset_mock()
        ftpd._upload_file.reset_mock()
        ftpd._download_file.reset_mock()
        ftpd._delete_file.reset_mock()
        ftpd._create_directory.reset_mock()
        ftpd._remove_directory.reset_mock()
        ftpd._rename.reset_mock()
        return ftpd

    @pytest.mark.asyncio
    async def test_connect(self, ftpd: MockFtpd) -> None:
        async with ftpd.connect() as client:
            assert client is ftpd

        ftpd._connect.assert_called_once()
        ftpd._disconnect.assert_called_once()

    @pytest.mark.asyncio
    async def test_disconnect(self, ftpd: MockFtpd) -> None:
        await ftpd.disconnect()

        ftpd._disconnect.assert_called_once()

    @pytest.mark.asyncio
    async def test_list_files(self, ftpd: MockFtpd) -> None:
        path = "/test"
        expected_files = ["file1.txt", "file2.txt"]
        ftpd._list_files = AsyncMock(return_value=expected_files)

        result = await ftpd.list_files(path)

        assert result == expected_files
        ftpd._list_files.assert_called_once_with(path)

    @pytest.mark.asyncio
    async def test_upload_file(self, ftpd: MockFtpd) -> None:
        local_path = "/local/test.txt"
        remote_path = "/remote/test.txt"

        await ftpd.upload_file(local_path, remote_path)

        ftpd._upload_file.assert_called_once_with(local_path, remote_path)

    @pytest.mark.asyncio
    async def test_download_file(self, ftpd: MockFtpd) -> None:
        remote_path = "/remote/test.txt"
        local_path = "/local/test.txt"

        await ftpd.download_file(remote_path, local_path)

        ftpd._download_file.assert_called_once_with(remote_path, local_path)

    @pytest.mark.asyncio
    async def test_delete_file(self, ftpd: MockFtpd) -> None:
        path = "/test/file.txt"

        await ftpd.delete_file(path)

        ftpd._delete_file.assert_called_once_with(path)

    @pytest.mark.asyncio
    async def test_create_directory(self, ftpd: MockFtpd) -> None:
        path = "/test/dir"

        await ftpd.create_directory(path)

        ftpd._create_directory.assert_called_once_with(path)

    @pytest.mark.asyncio
    async def test_remove_directory(self, ftpd: MockFtpd) -> None:
        path = "/test/dir"

        await ftpd.remove_directory(path)

        ftpd._remove_directory.assert_called_once_with(path)

    @pytest.mark.asyncio
    async def test_rename(self, ftpd: MockFtpd) -> None:
        old_path = "/test/old.txt"
        new_path = "/test/new.txt"

        await ftpd.rename(old_path, new_path)

        ftpd._rename.assert_called_once_with(old_path, new_path)

    @pytest.mark.asyncio
    async def test_context_manager(self, ftpd: MockFtpd) -> None:
        async with ftpd.connect() as client:
            assert client is ftpd

        ftpd._connect.assert_called_once()
        ftpd._disconnect.assert_called_once()
