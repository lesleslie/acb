"""Tests for the FTPD Base adapter."""

import typing as t
from contextlib import asynccontextmanager
from types import TracebackType
from typing import Optional, Type
from unittest.mock import AsyncMock, MagicMock

import pytest
from acb.adapters.ftpd._base import FtpdBase, FtpdBaseSettings


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

        self.disconnect = AsyncMock()
        self.list_files = AsyncMock()
        self.upload_file = AsyncMock()
        self.download_file = AsyncMock()
        self.delete_file = AsyncMock()
        self.create_directory = AsyncMock()
        self.remove_directory = AsyncMock()
        self.rename = AsyncMock()

        self.connect = self._mock_connect

    @asynccontextmanager
    async def _mock_connect(self) -> t.AsyncGenerator["FtpdBase", None]:
        await self._connect()
        yield self
        await self._disconnect()

    async def __aenter__(self):
        await self._connect()
        return self

    async def __aexit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[TracebackType],
    ):
        await self.disconnect()
        return None


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
        async with ftpd._mock_connect() as client:
            assert client is ftpd

        ftpd._connect.assert_called_once()
        ftpd._disconnect.assert_called_once()
