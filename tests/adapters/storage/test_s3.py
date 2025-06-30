"""Tests for the S3 storage adapter."""

import typing as t
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import SecretStr
from s3fs import S3FileSystem
from acb.adapters.storage.s3 import Storage, StorageSettings
from acb.config import Config


class MockS3FileSystem(MagicMock):
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

        self.url = MagicMock(return_value="s3://test-bucket/test-file")
        self.asynchronous = True

        self.exists = MagicMock(
            side_effect=lambda path, **kwargs: self._exists(path, **kwargs)
        )
        self.ls = MagicMock(side_effect=lambda path, **kwargs: self._ls(path, **kwargs))
        self.info = MagicMock(
            side_effect=lambda path, **kwargs: self._info(path, **kwargs)
        )


class MockStorageBucket(MagicMock):
    def __init__(self, *args: t.Any, **kwargs: t.Any) -> None:
        super().__init__(*args, **kwargs)
        self.create_bucket = AsyncMock()
        self.get_url = MagicMock(return_value="s3://test-bucket/test-file")
        self.stat = AsyncMock(return_value={"size": 100, "type": "file"})
        self.list = AsyncMock(return_value=["file1.txt", "file2.txt"])
        self.exists = AsyncMock(return_value=True)
        self.open = AsyncMock()
        self.write = AsyncMock()
        self.delete = AsyncMock()


class TestS3StorageSettings:
    def test_settings_structure(self) -> None:
        settings = StorageSettings(
            access_key_id=SecretStr("test-key"),
            secret_access_key=SecretStr("test-secret"),
            prefix="test-prefix",
        )
        assert settings.access_key_id.get_secret_value() == "test-key"
        assert settings.secret_access_key.get_secret_value() == "test-secret"
        assert settings.prefix == "test-prefix"


class TestS3Storage:
    @pytest.fixture
    def mock_config(self) -> MagicMock:
        mock_config = MagicMock(spec=Config)
        mock_app = MagicMock()
        mock_app.name = "test-app"
        mock_config.app = mock_app

        mock_storage = MagicMock()
        mock_storage.prefix = "test-prefix"
        mock_storage.access_key_id = "test-key"
        mock_storage.secret_access_key = "test-secret"
        mock_storage.endpoint_url = "https://s3.test-region.amazonaws.com"
        mock_storage.region_name = "test-region"
        mock_storage.buckets = {
            "test": "test-bucket",
            "media": "media-bucket",
            "templates": "templates-bucket",
        }
        mock_config.storage = mock_storage

        return mock_config

    @pytest.fixture
    def mock_s3fs(self) -> MockS3FileSystem:
        return MockS3FileSystem()

    @pytest.fixture
    def storage_adapter(self, mock_config: MagicMock) -> t.Generator[Storage]:
        with patch(
            "acb.adapters.storage.s3.S3FileSystem", return_value=MockS3FileSystem()
        ):
            adapter = Storage()
            adapter.config = mock_config
            adapter.logger = MagicMock()
            yield adapter

    @pytest.mark.asyncio
    async def test_client_property(self, storage_adapter: Storage) -> None:
        mock_s3fs = MockS3FileSystem()
        storage_adapter._client = mock_s3fs

        client = await storage_adapter.get_client()

        assert client is not None
        assert client == mock_s3fs

    @pytest.mark.asyncio
    async def test_file_system_type(self) -> None:
        assert Storage.file_system == S3FileSystem

    @pytest.mark.asyncio
    async def test_init_method(self, storage_adapter: Storage) -> None:
        mock_client = MockS3FileSystem()
        storage_adapter._client = mock_client

        with patch("acb.adapters.storage._base.StorageBucket") as mock_bucket_cls:
            mock_test_bucket = MockStorageBucket()
            mock_media_bucket = MockStorageBucket()
            mock_templates_bucket = MockStorageBucket()

            mock_bucket_cls.side_effect = [
                mock_test_bucket,
                mock_media_bucket,
                mock_templates_bucket,
            ]

            await storage_adapter.init()

            assert mock_bucket_cls.call_count == 3

            calls = mock_bucket_cls.call_args_list

            assert calls[0].args[0] == mock_client
            assert calls[0].args[1] == "test"

            assert calls[1].args[0] == mock_client
            assert calls[1].args[1] == "media"

            assert calls[2].args[0] == mock_client
            assert calls[2].args[1] == "templates"

            assert storage_adapter.test == mock_test_bucket
            assert storage_adapter.media == mock_media_bucket
            assert storage_adapter.templates == mock_templates_bucket
