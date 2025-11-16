"""Tests for the FTPD Base adapter."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest
import typing as t
from contextlib import asynccontextmanager

from acb.adapters.ftpd._base import FileInfo, FtpdBase, FtpdBaseSettings


class MockFtpdBaseSettings(FtpdBaseSettings):
    pass


class MockFtpd(FtpdBase):
    def __init__(self) -> None:
        super().__init__()
        self.config = MagicMock()
        self.logger = MagicMock()

    async def disconnect(self) -> None:
        pass

    async def list_files(self, path: str) -> list[str]:
        return ["file1.txt", "file2.txt"]

    async def upload_file(self, local_path: str, remote_path: str) -> None:
        pass

    async def download_file(self, remote_path: str, local_path: str) -> None:
        pass

    async def delete_file(self, path: str) -> None:
        pass

    async def create_directory(self, path: str) -> None:
        pass

    async def remove_directory(self, path: str) -> None:
        pass

    async def rename(self, old_path: str, new_path: str) -> None:
        pass

    async def start(self) -> None:
        pass

    async def stop(self) -> None:
        pass

    async def upload(self, local_path: Path, remote_path: str) -> None:
        pass

    async def download(self, remote_path: str, local_path: Path) -> None:
        pass

    async def list_dir(self, path: str) -> list[FileInfo]:
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
    async def connect(self) -> t.AsyncGenerator["FtpdBase"]:
        yield self


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
        return MockFtpd()

    @pytest.mark.asyncio
    async def test_connect(self, ftpd: MockFtpd) -> None:
        async with ftpd.connect() as client:
            assert client is ftpd

    @pytest.mark.asyncio
    async def test_disconnect(self, ftpd: MockFtpd) -> None:
        await ftpd.disconnect()

    @pytest.mark.asyncio
    async def test_list_files(self, ftpd: MockFtpd) -> None:
        path = "/test"
        expected_files = ["file1.txt", "file2.txt"]

        result = await ftpd.list_files(path)

        assert result == expected_files

    @pytest.mark.asyncio
    async def test_upload_file(self, ftpd: MockFtpd) -> None:
        local_path = "/local/test.txt"
        remote_path = "/remote/test.txt"

        await ftpd.upload_file(local_path, remote_path)

    @pytest.mark.asyncio
    async def test_download_file(self, ftpd: MockFtpd) -> None:
        remote_path = "/remote/test.txt"
        local_path = "/local/test.txt"

        await ftpd.download_file(remote_path, local_path)

    @pytest.mark.asyncio
    async def test_delete_file(self, ftpd: MockFtpd) -> None:
        path = "/test/file.txt"

        await ftpd.delete_file(path)

    @pytest.mark.asyncio
    async def test_create_directory(self, ftpd: MockFtpd) -> None:
        path = "/test/dir"

        await ftpd.create_directory(path)

    @pytest.mark.asyncio
    async def test_remove_directory(self, ftpd: MockFtpd) -> None:
        path = "/test/dir"

        await ftpd.remove_directory(path)

    @pytest.mark.asyncio
    async def test_rename(self, ftpd: MockFtpd) -> None:
        old_path = "/test/old.txt"
        new_path = "/test/new.txt"

        await ftpd.rename(old_path, new_path)
