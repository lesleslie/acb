"""Simple tests for the File Storage adapter."""

import tempfile
from unittest.mock import MagicMock

import pytest

from acb.adapters.storage.file import Storage, StorageSettings


class TestStorageSettings:
    def test_default_values(self) -> None:
        settings = StorageSettings()
        assert settings.local_path is not None
        assert settings.memory_fs is False
        # The local_fs value depends on the storage adapter, so we won't assert it here


class TestStorage:
    @pytest.fixture
    def mock_config(self) -> MagicMock:
        mock = MagicMock()
        mock.app.name = "test_app"
        mock.storage.local_path = tempfile.mkdtemp(prefix="test_storage_")
        return mock

    @pytest.fixture
    def mock_logger(self) -> MagicMock:
        return MagicMock()

    @pytest.mark.asyncio
    async def test_init(self, mock_config: MagicMock, mock_logger: MagicMock) -> None:
        adapter = Storage()
        adapter.config = mock_config
        adapter.logger = mock_logger

        # Test initialization
        await adapter.init()
        assert adapter._initialized is True

    @pytest.mark.asyncio
    async def test_put_get_file(
        self, mock_config: MagicMock, mock_logger: MagicMock
    ) -> None:
        adapter = Storage()
        adapter.config = mock_config
        adapter.logger = mock_logger
        adapter.root_dir = tempfile.mkdtemp(prefix="test_storage_")

        # Test put_file
        result = await adapter.put_file("test.txt", b"test content")
        assert result is True

        # Test get_file
        result = await adapter.get_file("test.txt")
        assert result == b"test content"
