"""Tests for the Memory Storage adapter."""

from unittest.mock import MagicMock, patch

import pytest
import typing as t

from acb.adapters.storage.memory import Storage
from acb.config import Settings
from tests.test_interfaces import StorageAdapterProtocol, StorageTestInterface


class MockMemoryFileSystem(MagicMock):
    def __init__(self, *args: t.Any, **kwargs: t.Any) -> None:
        super().__init__(*args, **kwargs)
        self._files = {}
        self._directories = set()


@pytest.fixture
def storage_settings() -> Settings:
    return Settings()


@pytest.fixture
def memory_fs() -> MockMemoryFileSystem:
    return MockMemoryFileSystem()


@pytest.fixture
async def storage(
    memory_fs: t.Any,
    storage_settings: t.Any,
) -> t.AsyncGenerator[Storage]:
    with patch("acb.adapters.storage.memory.MemoryFileSystem", return_value=memory_fs):
        storage_instance = Storage(settings=storage_settings)
        storage_instance._files = {}
        storage_instance._directories = set()
        storage_instance._initialized = True
        yield storage_instance


@pytest.mark.unit
class TestMemoryStorage(StorageTestInterface):
    @pytest.mark.asyncio
    async def test_storage_initialization(self, storage: Storage) -> None:
        assert hasattr(storage, "_files")
        assert hasattr(storage, "_directories")
        assert isinstance(storage._files, dict)
        assert isinstance(storage._directories, set)

    @pytest.mark.asyncio
    async def test_init(self, storage: StorageAdapterProtocol) -> None:
        with patch("acb.adapters.storage._base.StorageBase.init") as mock_super_init:
            await storage.init()

            mock_super_init.assert_called_once()

            memory_storage = t.cast("Storage", storage)
            assert memory_storage._initialized
            assert hasattr(memory_storage, "_files")
            assert isinstance(memory_storage._files, dict)
            assert hasattr(memory_storage, "_directories")
            assert isinstance(memory_storage._directories, set)

    @pytest.mark.asyncio
    async def test_put_file_creates_directory_structure(self, storage: Storage) -> None:
        await storage.put_file("nested/path/file.txt", b"content")

        assert await storage.directory_exists("nested/path")
        assert "nested/path" in storage._directories

    @pytest.mark.asyncio
    async def test_multiple_file_operations(self, storage: Storage) -> None:
        await storage.put_file("file1.txt", b"content1")
        await storage.put_file("file2.txt", b"content2")

        assert await storage.file_exists("file1.txt")
        assert await storage.file_exists("file2.txt")

        content1 = await storage.get_file("file1.txt")
        content2 = await storage.get_file("file2.txt")

        assert content1 == b"content1"
        assert content2 == b"content2"

        await storage.delete_file("file1.txt")
        assert not await storage.file_exists("file1.txt")
        assert await storage.file_exists("file2.txt")

    @pytest.mark.asyncio
    async def test_delete_nonexistent_file(self, storage: Storage) -> None:
        result = await storage.delete_file("nonexistent.txt")
        assert not result

    @pytest.mark.asyncio
    async def test_lazy_initialization(
        self,
        storage_settings: Settings,
        memory_fs: MockMemoryFileSystem,
    ) -> None:
        adapter = Storage()
        adapter.config = MagicMock()
        adapter.config.storage = storage_settings
        adapter.logger = MagicMock()

        # Check that the adapter is not yet initialized with file system
        assert not hasattr(adapter, "_files") or not adapter._files

        with patch(
            "acb.adapters.storage.memory.MemoryFileSystem",
            return_value=memory_fs,
        ):
            await adapter.file_exists("test/path")

        assert not adapter._files
