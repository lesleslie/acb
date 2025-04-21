import typing as t
from functools import cached_property
from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from anyio import Path as AsyncPath
from acb.adapters import tmp_path
from acb.config import Config

from ._base import (
    StorageBase,
    StorageBaseSettings,
    StorageBucket,
    StorageFile,
    StorageImage,
)
from .file import Storage as FileStorage
from .memory import Storage as MemoryStorage


@pytest.fixture
def mock_storage_settings() -> MagicMock:
    settings = MagicMock()
    settings.buckets = {
        "test": "test-bucket",
        "media": "media-bucket",
        "templates": "templates-bucket",
    }
    settings.prefix = "test-prefix"
    settings.local_path = tmp_path / "storage"
    settings.local_fs = True
    settings.memory_fs = False
    settings.cors = None
    return settings


@pytest.fixture
def mock_app_settings() -> MagicMock:
    settings = MagicMock()
    settings.name = "acb"
    return settings


@pytest.fixture
def mock_config(
    mock_storage_settings: MagicMock, mock_app_settings: MagicMock
) -> MagicMock:
    config = MagicMock(spec=Config)
    type(config).__getattr__ = MagicMock(return_value=mock_storage_settings)
    config.__dict__["storage"] = mock_storage_settings
    config.app = mock_app_settings
    config.deployed = False
    return config


@pytest.fixture
def mock_client() -> AsyncMock:
    client = AsyncMock()
    client._pipe_file = AsyncMock()
    client._rm_file = AsyncMock()
    client._exists = AsyncMock(return_value=True)
    client._info = AsyncMock(
        return_value={"size": 100, "timeCreated": "2023-01-01", "updated": "2023-01-02"}
    )
    client._ls = AsyncMock(return_value=["file1.txt", "file2.txt"])
    client._mkdir = AsyncMock()
    client._sign = AsyncMock(return_value="https://signed-url.example.com")
    client.url = MagicMock(return_value="https://example.com/file.txt")

    async_cm = AsyncMock()
    async_cm.__aenter__.return_value.read = AsyncMock(return_value=b"test content")
    client.open = MagicMock(return_value=async_cm)

    client.pipe_file = MagicMock()
    client.info = MagicMock(
        return_value={"name": "test.txt", "size": 100, "type": "file"}
    )
    client.modified = MagicMock()
    client.created = MagicMock()
    client.isfile = MagicMock(return_value=True)
    client.set_cors = MagicMock()
    return client


@pytest.fixture
def mock_adapter() -> MagicMock:
    adapter = MagicMock()
    adapter.name = "memory"
    return adapter


@pytest.fixture
def mock_storage_bucket(
    mock_client: AsyncMock,
    mock_config: MagicMock,
) -> StorageBucket:
    with patch("acb.depends.depends.get", return_value=mock_config):

        class TestStorageBucket(StorageBucket):
            _config_value: Config | None = None

            @property
            def config(self) -> Config:  # type: ignore
                if self._config_value is None:
                    self._config_value = mock_config
                return self._config_value

            def get_path(self, path: AsyncPath | str) -> str:
                return f"test-bucket/{path}"

        bucket = TestStorageBucket(mock_client, "test")
        bucket.bucket = "test-bucket"
        return bucket


@pytest.fixture
def mock_storage_base(
    mock_client: AsyncMock, mock_config: MagicMock, mock_storage_bucket: StorageBucket
) -> StorageBase:
    with patch("acb.depends.depends.get", return_value=mock_config):

        class TestStorageBase(StorageBase):
            _config_value: Config | None = None

            @property
            def config(self) -> Config:  # type: ignore
                if self._config_value is None:
                    self._config_value = mock_config
                return self._config_value

            @cached_property
            def client(self) -> Any:
                return mock_client

            async def init(self) -> None:
                self.test = mock_storage_bucket
                self.media = mock_storage_bucket
                self.templates = mock_storage_bucket

        storage = TestStorageBase()
        storage.test = mock_storage_bucket
        storage.media = mock_storage_bucket
        storage.templates = mock_storage_bucket
        return storage


class TestStorageBaseSettings:
    def test_init(
        self,
        mock_config: MagicMock,
        mock_storage_settings: MagicMock,
    ) -> None:
        settings = MagicMock(spec=StorageBaseSettings)
        settings.prefix = "test_prefix"
        settings.local_path = tmp_path / "storage"
        settings.buckets = {
            "test": "test-bucket",
            "media": "media-bucket",
            "templates": "templates-bucket",
        }
        settings.local_fs = True
        settings.memory_fs = False

        assert settings.prefix is not None
        assert settings.local_path == tmp_path / "storage"
        assert "test" in settings.buckets
        assert "media" in settings.buckets
        assert "templates" in settings.buckets


class TestStorageBucket:
    @pytest.mark.anyio
    async def test_get_path(
        self,
        mock_storage_bucket: StorageBucket,
    ) -> None:
        path = AsyncPath("test.txt")
        result = mock_storage_bucket.get_path(path)
        assert isinstance(result, str)
        assert "test-bucket" in result

    @pytest.mark.anyio
    async def test_get_url(
        self, mock_storage_bucket: StorageBucket, mock_client: AsyncMock
    ) -> None:
        path = AsyncPath("test.txt")
        url = mock_storage_bucket.get_url(path)
        assert url == "https://example.com/file.txt"
        mock_client.url.assert_called_once()

    @pytest.mark.anyio
    async def test_get_signed_url(
        self, mock_storage_bucket: StorageBucket, mock_client: AsyncMock
    ) -> None:
        path = AsyncPath("test.txt")
        url = await mock_storage_bucket.get_signed_url(path)
        assert url == "https://signed-url.example.com"
        mock_client._sign.assert_called_once()

    @pytest.mark.anyio
    async def test_stat(
        self, mock_storage_bucket: StorageBucket, mock_client: AsyncMock
    ) -> None:
        path = AsyncPath("test.txt")
        stat = await mock_storage_bucket.stat(path)
        assert stat["size"] == 100
        assert "timeCreated" in stat
        assert "updated" in stat
        mock_client._info.assert_called_once()

    @pytest.mark.anyio
    async def test_list(
        self, mock_storage_bucket: StorageBucket, mock_client: AsyncMock
    ) -> None:
        path = AsyncPath("directory/")
        files = await mock_storage_bucket.list(path)
        assert len(files) == 2
        assert "file1.txt" in files
        assert "file2.txt" in files
        mock_client._ls.assert_called_once()

    @pytest.mark.anyio
    async def test_exists(
        self, mock_storage_bucket: StorageBucket, mock_client: AsyncMock
    ) -> None:
        async def mock_exists(path: AsyncPath) -> bool:
            await mock_client._exists(mock_storage_bucket.get_path(path))
            mock_client._exists.assert_called_once()
            return True

        mock_storage_bucket.exists = mock_exists
        path = AsyncPath("test.txt")
        exists = await mock_storage_bucket.exists(path)
        assert exists

    @pytest.mark.anyio
    async def test_create_bucket(
        self, mock_storage_bucket: StorageBucket, mock_client: AsyncMock
    ) -> None:
        path = AsyncPath("new-bucket/")
        await mock_storage_bucket.create_bucket(path)
        mock_client._mkdir.assert_called_once()

    @pytest.mark.anyio
    async def test_open(
        self, mock_storage_bucket: StorageBucket, mock_client: AsyncMock
    ) -> None:
        async def mock_open(path: AsyncPath) -> t.BinaryIO:
            mock_client.open(mock_storage_bucket.get_path(path))
            mock_client.open.assert_called_once()
            return t.cast(t.BinaryIO, b"test content")

        mock_storage_bucket.open = mock_open
        path = AsyncPath("test.txt")
        content = await mock_storage_bucket.open(path)
        assert content == b"test content"

    @pytest.mark.anyio
    async def test_open_file_not_found(
        self, mock_storage_bucket: StorageBucket, mock_client: AsyncMock
    ) -> None:
        async def mock_open_not_found(path: AsyncPath) -> t.BinaryIO:
            raise FileNotFoundError(f"File not found: {path}")

        mock_storage_bucket.open = mock_open_not_found
        path = AsyncPath("nonexistent.txt")
        with pytest.raises(FileNotFoundError):
            await mock_storage_bucket.open(path)

    @pytest.mark.anyio
    async def test_write(
        self, mock_storage_bucket: StorageBucket, mock_client: AsyncMock
    ) -> None:
        async def mock_write(path: AsyncPath, data: bytes) -> None:
            await mock_client._pipe_file(mock_storage_bucket.get_path(path), data)
            mock_client._pipe_file.assert_called_once()
            return None

        mock_storage_bucket.write = mock_write
        path = AsyncPath("test.txt")
        data = b"test content"
        await mock_storage_bucket.write(path, data)

    @pytest.mark.anyio
    async def test_delete(
        self, mock_storage_bucket: StorageBucket, mock_client: AsyncMock
    ) -> None:
        path = AsyncPath("test.txt")
        await mock_storage_bucket.delete(path)
        mock_client._rm_file.assert_called_once()


class TestStorageBase:
    def test_client_property(self, mock_storage_base: StorageBase) -> None:
        mock_client = MagicMock()
        mock_storage_base.client = mock_client

        client = mock_storage_base.client

        assert client is mock_client


class TestStorageFile:
    def test_init(self, mock_storage_bucket: StorageBucket) -> None:
        file = StorageFile(name="test.txt", storage=mock_storage_bucket)
        assert file._storage == mock_storage_bucket
        assert file._name == "test.txt"

    def test_name_property(self, mock_storage_bucket: StorageBucket) -> None:
        file = StorageFile(name="test.txt", storage=mock_storage_bucket)
        assert file.name == "test.txt"

    def test_path_property(
        self,
        mock_storage_bucket: StorageBucket,
    ) -> None:
        mock_storage_bucket.get_path = lambda path: f"test-bucket/{path}"  # type: ignore[assignment]
        file = StorageFile(name="test.txt", storage=mock_storage_bucket)
        assert isinstance(file.path, str)
        assert "test-bucket" in file.path

    @pytest.mark.anyio
    async def test_size_property(
        self, mock_storage_bucket: StorageBucket, mock_client: AsyncMock
    ) -> None:
        mock_client._info.return_value = {"size": 100}
        file = StorageFile(name="test.txt", storage=mock_storage_bucket)
        size = await file.size
        assert size == 100

    @pytest.mark.anyio
    async def test_open_method(
        self, mock_storage_bucket: StorageBucket, mock_client: AsyncMock
    ) -> None:
        async def mock_open(path: AsyncPath) -> t.BinaryIO:
            return t.cast(t.BinaryIO, b"test content")

        mock_storage_bucket.open = mock_open
        file = StorageFile(name="test.txt", storage=mock_storage_bucket)
        content = await file.open()
        assert content == b"test content"

    @pytest.mark.anyio
    async def test_write_method(
        self, mock_storage_bucket: StorageBucket, mock_client: AsyncMock
    ) -> None:
        write_called: bool = False

        async def mock_write(path: AsyncPath, data: bytes) -> None:
            nonlocal write_called
            write_called = True
            return None

        mock_storage_bucket.write = mock_write
        file = StorageFile(name="test.txt", storage=mock_storage_bucket)
        data = b"test content"
        await file.write(cast(t.BinaryIO, data))
        assert write_called


class TestStorageImage:
    def test_init(self, mock_storage_bucket: StorageBucket) -> None:
        image = StorageImage(
            name="image.jpg", storage=mock_storage_bucket, height=100, width=200
        )
        assert image._storage == mock_storage_bucket
        assert image._name == "image.jpg"
        assert image._height == 100
        assert image._width == 200

    def test_height_property(self, mock_storage_bucket: StorageBucket) -> None:
        image = StorageImage(
            name="image.jpg", storage=mock_storage_bucket, height=100, width=200
        )
        assert image.height == 100

    def test_width_property(self, mock_storage_bucket: StorageBucket) -> None:
        image = StorageImage(
            name="image.jpg", storage=mock_storage_bucket, height=100, width=200
        )
        assert image.width == 200


class TestFileStorage:
    def test_init(self) -> None:
        with patch("acb.adapters.storage.file.DirFileSystem") as mock_dir_fs:
            mock_dir_fs.__name__ = "DirFileSystem"

            storage = FileStorage()

            storage.file_system = mock_dir_fs

            assert storage.file_system.__name__ == "DirFileSystem"


class TestMemoryStorage:
    def test_init(self) -> None:
        with patch("acb.adapters.storage.memory.MemoryFileSystem") as mock_memory_fs:
            storage = MemoryStorage()

            storage.file_system = mock_memory_fs

            assert storage.file_system == mock_memory_fs


@pytest.mark.anyio
async def test_integration_memory_storage(
    mock_config: MagicMock,
) -> None:
    with patch("acb.depends.depends.get", return_value=mock_config):

        class SimpleMemoryStorage:
            def __init__(self) -> None:
                self.files: dict[str, bytes] = {}
                self.test = self

            async def write(self, path: AsyncPath, data: bytes) -> None:
                self.files[str(path)] = data

            async def exists(self, path: AsyncPath) -> bool:
                return str(path) in self.files

            async def open(self, path: AsyncPath) -> bytes:
                if str(path) not in self.files:
                    raise FileNotFoundError(f"File not found: {path}")
                return self.files[str(path)]

            async def stat(self, path: AsyncPath) -> dict[str, int]:
                if str(path) not in self.files:
                    raise FileNotFoundError(f"File not found: {path}")
                return {"size": len(self.files[str(path)])}

            async def list(self, path: AsyncPath) -> list[str]:
                return list(self.files.keys())

            async def delete(self, path: AsyncPath) -> None:
                if str(path) in self.files:
                    del self.files[str(path)]

        storage = SimpleMemoryStorage()

        test_data: bytes = b"Hello, World!"
        test_path: AsyncPath = AsyncPath("test.txt")

        await storage.write(test_path, test_data)
        assert await storage.exists(test_path)

        content = await storage.open(test_path)
        assert content == test_data

        stat = await storage.stat(test_path)
        assert stat["size"] == len(test_data)

        files = await storage.list(AsyncPath("/"))
        assert "test.txt" in files

        await storage.delete(test_path)
        with pytest.raises(FileNotFoundError):
            await storage.open(test_path)
