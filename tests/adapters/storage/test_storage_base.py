"""Tests for the Storage Base adapter."""

from unittest.mock import AsyncMock, MagicMock

import pytest
import typing as t
from contextlib import asynccontextmanager
from typing import Any

from acb.adapters.storage._base import StorageBase, StorageBaseSettings


@asynccontextmanager
async def mock_s3_client() -> t.AsyncGenerator[AsyncMock]:
    with pytest.MonkeyPatch().context() as mp:
        mock_client = AsyncMock()
        mp.setattr(
            "aiobotocore.session.AioSession.create_client.__aenter__",
            lambda *args, **kwargs: mock_client,
        )
        yield mock_client


class MockStorageBaseSettings(StorageBaseSettings):
    def __init__(self, bucket_name: str, region: str, **values: Any) -> None:
        super().__init__(**values)
        self.bucket_name = bucket_name
        self.region = region


class MockStorage(StorageBase):
    def __init__(self, bucket_name: str, region: str) -> None:
        super().__init__()
        self.config = MagicMock()
        self.logger = MagicMock()
        self._upload_file = AsyncMock()
        self._download_file = AsyncMock()
        self._delete_file = AsyncMock()
        self._list_files = AsyncMock()
        self._file_exists = AsyncMock()
        self._get_file_url = AsyncMock()
        self._get_file_metadata = AsyncMock()
        self._copy_file = AsyncMock()
        self._move_file = AsyncMock()
        self.bucket_name = bucket_name
        self.region = region

    async def upload_file(self, local_path: str, remote_path: str) -> None:
        await self._upload_file(local_path, remote_path)

    async def download_file(self, remote_path: str, local_path: str) -> None:
        await self._download_file(remote_path, local_path)

    async def delete_file(self, remote_path: str) -> None:
        await self._delete_file(remote_path)

    async def list_files(self, prefix: str) -> list[str]:
        return await self._list_files(prefix)

    async def file_exists(self, remote_path: str) -> bool:
        return await self._file_exists(remote_path)

    async def get_file_url(self, remote_path: str) -> str:
        return await self._get_file_url(remote_path)

    async def get_file_metadata(self, remote_path: str) -> dict[str, Any]:
        return await self._get_file_metadata(remote_path)

    async def copy_file(self, source_path: str, destination_path: str) -> None:
        await self._copy_file(source_path, destination_path)

    async def move_file(self, source_path: str, destination_path: str) -> None:
        await self._move_file(source_path, destination_path)


class TestStorageBaseSettings:
    def test_init(self) -> None:
        settings: MockStorageBaseSettings = MockStorageBaseSettings(
            bucket_name="test-bucket",
            region="us-west-1",
        )
        assert settings.bucket_name == "test-bucket"
        assert settings.region == "us-west-1"


class TestStorageBase:
    @pytest.fixture
    def storage(self) -> MockStorage:
        storage: MockStorage = MockStorage(
            bucket_name="test-bucket",
            region="us-west-1",
        )
        return storage

    @pytest.mark.asyncio
    async def test_upload_file(self, storage: MockStorage) -> None:
        local_path: str = "/local/test.txt"
        remote_path: str = "test.txt"
        storage._upload_file = AsyncMock()
        await storage.upload_file(local_path, remote_path)
        storage._upload_file.assert_called_once_with(local_path, remote_path)

    @pytest.mark.asyncio
    async def test_download_file(self, storage: MockStorage) -> None:
        remote_path: str = "test.txt"
        local_path: str = "/local/test.txt"
        storage._download_file = AsyncMock()
        await storage.download_file(remote_path, local_path)
        storage._download_file.assert_called_once_with(remote_path, local_path)

    @pytest.mark.asyncio
    async def test_delete_file(self, storage: MockStorage) -> None:
        remote_path: str = "test.txt"
        storage._delete_file = AsyncMock()
        await storage.delete_file(remote_path)
        storage._delete_file.assert_called_once_with(remote_path)

    @pytest.mark.asyncio
    async def test_list_files(self, storage: MockStorage) -> None:
        prefix: str = "test/"
        storage._list_files = AsyncMock(return_value=["file1.txt", "file2.txt"])
        files = await storage.list_files(prefix)
        assert files == ["file1.txt", "file2.txt"]
        storage._list_files.assert_called_once_with(prefix)

    @pytest.mark.asyncio
    async def test_file_exists(self, storage: MockStorage) -> None:
        remote_path: str = "test.txt"
        storage._file_exists = AsyncMock(return_value=True)
        exists = await storage.file_exists(remote_path)
        assert exists
        storage._file_exists.assert_called_once_with(remote_path)

    @pytest.mark.asyncio
    async def test_get_file_url(self, storage: MockStorage) -> None:
        remote_path: str = "test.txt"
        storage._get_file_url = AsyncMock(return_value="https://example.com/test.txt")
        url = await storage.get_file_url(remote_path)
        assert url == "https://example.com/test.txt"
        storage._get_file_url.assert_called_once_with(remote_path)

    @pytest.mark.asyncio
    async def test_get_file_metadata(self, storage: MockStorage) -> None:
        remote_path: str = "test.txt"
        storage._get_file_metadata = AsyncMock(return_value={"size": 100})
        metadata = await storage.get_file_metadata(remote_path)
        assert metadata == {"size": 100}
        storage._get_file_metadata.assert_called_once_with(remote_path)

    @pytest.mark.asyncio
    async def test_copy_file(self, storage: MockStorage) -> None:
        source_path: str = "test.txt"
        destination_path: str = "copy.txt"
        storage._copy_file = AsyncMock()
        await storage.copy_file(source_path, destination_path)
        storage._copy_file.assert_called_once_with(source_path, destination_path)

    @pytest.mark.asyncio
    async def test_move_file(self, storage: MockStorage) -> None:
        source_path: str = "test.txt"
        destination_path: str = "moved.txt"
        storage._move_file = AsyncMock()
        await storage.move_file(source_path, destination_path)
        storage._move_file.assert_called_once_with(source_path, destination_path)
