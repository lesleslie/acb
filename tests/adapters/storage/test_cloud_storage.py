"""Tests for the Google Cloud Storage adapter."""

import typing as t
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from gcsfs import GCSFileSystem
from acb.adapters.storage.cloud_storage import Storage, StorageSettings
from acb.config import Config


class MockGCSFileSystem(MagicMock):
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

        self.url = MagicMock(return_value="gs://test-bucket/test-file")
        self.asynchronous = True

        self.exists = MagicMock(
            side_effect=lambda path, **kwargs: self._exists(path, **kwargs)
        )
        self.ls = MagicMock(side_effect=lambda path, **kwargs: self._ls(path, **kwargs))
        self.info = MagicMock(
            side_effect=lambda path, **kwargs: self._info(path, **kwargs)
        )


class MockGCSBucket(MagicMock):
    def __init__(self, *args: t.Any, **kwargs: t.Any) -> None:
        super().__init__(*args, **kwargs)
        self.name = "test-bucket"
        self.cors = []
        self.patch = MagicMock()


class MockGCSClient(MagicMock):
    def __init__(self, *args: t.Any, **kwargs: t.Any) -> None:
        super().__init__(*args, **kwargs)
        self.get_bucket = MagicMock(return_value=MockGCSBucket())
        self.bucket = MagicMock(return_value=MockGCSBucket())
        self.create_bucket = MagicMock(return_value=MockGCSBucket())
        self.storage_client = MagicMock()
        self.storage_client.get_bucket = MagicMock(return_value=MockGCSBucket())


class MockStorageBucket(MagicMock):
    def __init__(self, *args: t.Any, **kwargs: t.Any) -> None:
        super().__init__(*args, **kwargs)
        self.create_bucket = AsyncMock()
        self.get_url = MagicMock(return_value="gs://test-bucket/test-file")
        self.stat = AsyncMock(return_value={"size": 100, "type": "file"})
        self.list = AsyncMock(return_value=["file1.txt", "file2.txt"])
        self.exists = AsyncMock(return_value=True)
        self.open = AsyncMock()
        self.write = AsyncMock()
        self.delete = AsyncMock()


class TestGCSStorageSettings:
    def test_settings_structure(self) -> None:
        settings = StorageSettings(prefix="test-prefix")
        assert settings.prefix == "test-prefix"


class TestGCSStorage:
    @pytest.fixture
    def mock_config(self) -> MagicMock:
        mock_config = MagicMock(spec=Config)
        mock_app = MagicMock()
        mock_app.name = "test-app"
        mock_config.app = mock_app

        mock_storage = MagicMock()
        mock_storage.prefix = "test-prefix"
        mock_storage.project = "test-project"
        mock_storage.credentials = "test-credentials"
        mock_storage.buckets = {
            "test": "test-bucket",
            "media": "media-bucket",
            "templates": "templates-bucket",
        }
        mock_config.storage = mock_storage

        return mock_config

    @pytest.fixture
    def mock_gcsfs(self) -> MockGCSFileSystem:
        return MockGCSFileSystem()

    @pytest.fixture
    def mock_gcs_client(self) -> MockGCSClient:
        return MockGCSClient()

    @pytest.fixture
    def storage_adapter(self, mock_config: MagicMock) -> t.Generator[Storage]:
        with patch(
            "acb.adapters.storage.cloud_storage.GCSFileSystem",
            return_value=MockGCSFileSystem(),
        ):
            adapter = Storage()
            adapter.config = mock_config
            adapter.logger = MagicMock()
            yield adapter

    @pytest.mark.asyncio
    async def test_client_property(self, storage_adapter: Storage) -> None:
        mock_gcsfs = MockGCSFileSystem()

        with patch.object(Storage, "client", new=mock_gcsfs):
            client = storage_adapter.client

            assert client is mock_gcsfs

    @pytest.mark.asyncio
    async def test_file_system_type(self) -> None:
        assert Storage.file_system == GCSFileSystem

    @pytest.mark.asyncio
    async def test_get_client_static_method(self) -> None:
        mock_client = MockGCSClient()

        with patch(
            "acb.adapters.storage.cloud_storage.Client", return_value=mock_client
        ) as mock_client_cls:
            mock_config = MagicMock()
            mock_config.app.project = "test-project"

            with patch(
                "acb.adapters.storage.cloud_storage.depends.get",
                return_value=mock_config,
            ):
                client = Storage.get_client()

                assert client == mock_client

                assert mock_client_cls.call_count == 1

    @pytest.mark.asyncio
    async def test_init_method(self, storage_adapter: Storage) -> None:
        mock_client = MockGCSFileSystem()

        with (
            patch.object(
                storage_adapter, "get_client", new=AsyncMock(return_value=mock_client)
            ) as mock_get_client,
            patch("acb.adapters.storage._base.StorageBucket") as mock_bucket_cls,
        ):
            mock_bucket = MockStorageBucket()
            mock_bucket_cls.return_value = mock_bucket

            await storage_adapter.init()

            mock_get_client.assert_called_once()
            mock_bucket_cls.assert_any_call(mock_client, "templates")
            mock_bucket_cls.assert_any_call(mock_client, "test")
            mock_bucket_cls.assert_any_call(mock_client, "media")

            assert storage_adapter.templates == mock_bucket
            assert storage_adapter.test == mock_bucket
            assert storage_adapter.media == mock_bucket

    @pytest.mark.asyncio
    async def test_set_cors(
        self, storage_adapter: Storage, mock_gcs_client: MockGCSClient
    ) -> None:
        with patch.object(Storage, "get_client", return_value=mock_gcs_client):
            cors_config: dict[str, dict[str, list[str] | int]] = {
                "upload": {
                    "origin": ["https://example.com"],
                    "method": ["GET", "POST"],
                    "responseHeader": ["Content-Type"],
                    "maxAgeSeconds": 3600,
                }
            }

            if (
                not hasattr(storage_adapter.config.storage, "cors")
                or storage_adapter.config.storage.cors is None
            ):
                storage_adapter.config.storage.cors = {}

            storage_adapter.config.storage.cors = cors_config

            storage_adapter.set_cors("test-bucket", "upload")

            mock_gcs_client.get_bucket.assert_called_once_with("test-bucket")

            bucket = mock_gcs_client.get_bucket.return_value
            assert len(bucket.cors) == 1
            assert bucket.cors[0] == cors_config["upload"]

            bucket.patch.assert_called_once()

    @pytest.mark.asyncio
    async def test_remove_cors(
        self, storage_adapter: Storage, mock_gcs_client: MockGCSClient
    ) -> None:
        with patch.object(Storage, "get_client", return_value=mock_gcs_client):
            storage_adapter.remove_cors("test-bucket")

            mock_gcs_client.storage_client.get_bucket.assert_called_once_with(
                "test-bucket"
            )

            bucket = mock_gcs_client.storage_client.get_bucket.return_value
            assert bucket.cors == []

            bucket.patch.assert_called_once()
