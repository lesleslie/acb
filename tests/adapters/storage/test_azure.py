"""Tests for the Azure Blob Storage adapter."""

import typing as t
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from adlfs import AzureBlobFileSystem
from acb.adapters.storage.azure import Storage, StorageSettings
from acb.config import Config


class MockAzureBlobFileSystem(MagicMock):
    def __init__(self, *args: t.Any, **kwargs: t.Any) -> None:
        super().__init__(*args, **kwargs)
        self._exists = AsyncMock(return_value=True)
        self._ls = AsyncMock(return_value=["file1.txt", "file2.txt"])
        self._info = AsyncMock(return_value={"size": 100, "type": "file"})
        self._pipe_file = AsyncMock()
        self._rm_file = AsyncMock()
        self._mkdir = AsyncMock()
        self._sign = AsyncMock()

        self.open = MagicMock()
        mock_file = MagicMock()
        mock_file.__enter__ = MagicMock(return_value=mock_file)
        mock_file.__exit__ = MagicMock(return_value=None)
        mock_file.read = MagicMock(return_value=b"test content")
        self.open.return_value = mock_file

        self.url = MagicMock(
            return_value="https://storageaccount.blob.core.windows.net/container/blob"
        )
        self.asynchronous = True


class MockStorageBucket(MagicMock):
    def __init__(self, *args: t.Any, **kwargs: t.Any) -> None:
        super().__init__(*args, **kwargs)
        self.create_bucket = AsyncMock()
        self.get_url = MagicMock(
            return_value="https://storageaccount.blob.core.windows.net/container/blob"
        )
        self.stat = AsyncMock(return_value={"size": 100, "type": "file"})
        self.list = AsyncMock(return_value=["file1.txt", "file2.txt"])
        self.exists = AsyncMock(return_value=True)
        self.open = AsyncMock()
        self.write = AsyncMock()
        self.delete = AsyncMock()


class TestAzureBlobStorageSettings:
    def test_settings_structure(self) -> None:
        from pydantic import SecretStr

        settings = StorageSettings(
            connection_string=SecretStr(
                "DefaultEndpointsProtocol=https;AccountName=teststorage;AccountKey=testkey;EndpointSuffix=core.windows.net"
            ),
            prefix="test-prefix",
        )
        assert isinstance(settings.connection_string, SecretStr)
        assert (
            settings.connection_string.get_secret_value()
            == "DefaultEndpointsProtocol=https;AccountName=teststorage;AccountKey=testkey;EndpointSuffix=core.windows.net"
        )
        assert settings.prefix == "test-prefix"


class TestAzureBlobStorage:
    @pytest.fixture
    def mock_config(self) -> MagicMock:
        mock_config = MagicMock(spec=Config)
        mock_app = MagicMock()
        mock_app.name = "test-app"
        mock_config.app = mock_app

        mock_storage = MagicMock()
        mock_storage.prefix = "test-prefix"
        mock_storage.connection_string = "DefaultEndpointsProtocol=https;AccountName=teststorage;AccountKey=testkey;EndpointSuffix=core.windows.net"
        mock_storage.buckets = {
            "test": "test-container",
            "media": "media-container",
            "templates": "templates-container",
        }
        mock_config.storage = mock_storage

        return mock_config

    @pytest.fixture
    def mock_azure_fs(self) -> MockAzureBlobFileSystem:
        return MockAzureBlobFileSystem()

    @pytest.fixture
    def storage_adapter(self, mock_config: MagicMock) -> t.Generator[Storage]:
        with patch(
            "acb.adapters.storage.azure.AzureBlobFileSystem",
            return_value=MockAzureBlobFileSystem(),
        ):
            adapter = Storage()
            adapter.config = mock_config
            adapter.logger = MagicMock()
            yield adapter

    @pytest.mark.asyncio
    async def test_client_property(self, storage_adapter: Storage) -> None:
        mock_azure_fs = MockAzureBlobFileSystem()

        with patch(
            "acb.adapters.storage.azure.AzureBlobFileSystem", return_value=mock_azure_fs
        ):
            with patch.object(Storage, "client", new_callable=lambda: mock_azure_fs):
                client = storage_adapter.client

                assert client is not None
                assert client == mock_azure_fs

    @pytest.mark.asyncio
    async def test_file_system_type(self) -> None:
        assert Storage.file_system == AzureBlobFileSystem

    @pytest.mark.asyncio
    async def test_init_method(self, storage_adapter: Storage) -> None:
        mock_client = MockAzureBlobFileSystem()
        mock_bucket = MockStorageBucket()

        storage_adapter._client = mock_client
        with patch(
            "acb.adapters.storage._base.StorageBucket", return_value=mock_bucket
        ) as mock_bucket_cls:
            await storage_adapter.init()

            mock_bucket_cls.assert_any_call(mock_client, "templates")
            mock_bucket_cls.assert_any_call(mock_client, "test")
            mock_bucket_cls.assert_any_call(mock_client, "media")

            assert storage_adapter.templates == mock_bucket
            assert storage_adapter.test == mock_bucket
            assert storage_adapter.media == mock_bucket
