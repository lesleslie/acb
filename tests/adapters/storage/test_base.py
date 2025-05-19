"""Tests for the storage base components."""

from io import BytesIO
from types import TracebackType
from typing import Optional, Type
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from anyio import Path as AsyncPath
from acb.adapters.storage._base import (
    StorageBase,
    StorageBaseSettings,
    StorageBucket,
    StorageFile,
    StorageImage,
)
from acb.config import Config


@pytest.fixture
def mock_storage_settings() -> MagicMock:
    settings: MagicMock = MagicMock()
    settings.buckets: dict[str, str] = {
        "test": "test-bucket",
        "media": "media-bucket",
        "templates": "templates-bucket",
    }
    settings.prefix: str = "test-prefix"
    mock_path: MagicMock = MagicMock(spec=AsyncPath)
    mock_path.__truediv__.return_value = mock_path
    settings.local_path = mock_path
    settings.local_fs = True
    settings.memory_fs = False
    settings.cors = None
    return settings


@pytest.fixture
def mock_app_settings() -> MagicMock:
    settings: MagicMock = MagicMock()
    settings.name: str = "acb"
    return settings


@pytest.fixture
def mock_config(
    mock_storage_settings: MagicMock, mock_app_settings: MagicMock
) -> MagicMock:
    config: MagicMock = MagicMock(spec=Config)
    type(config).__getattr__ = MagicMock(return_value=mock_storage_settings)
    config.__dict__["storage"] = mock_storage_settings
    config.app = mock_app_settings
    config.deployed = False
    return config


@pytest.fixture
def mock_client() -> AsyncMock:
    client: AsyncMock = AsyncMock()
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

    async_cm: AsyncMock = AsyncMock()
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
def mock_storage_bucket(mock_storage: StorageBase) -> StorageBucket:
    bucket: StorageBucket = TestStorageBucketImpl(mock_storage, "test-bucket")
    bucket.logger = MagicMock()
    bucket.config = MagicMock()
    bucket.config.storage = MagicMock()
    bucket.config.storage.buckets = {"test": "test-bucket"}
    bucket.config.storage.prefix = "test-prefix"
    bucket.path = MagicMock(return_value="test-bucket/test-path")
    bucket.name = MagicMock(return_value="test-bucket")
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
                return self._config_value or super().config

        return TestStorageBase(client=mock_client, bucket=mock_storage_bucket)


class TestStorageBaseSettings:
    def test_init(
        self,
        mock_config: MagicMock,
        mock_storage_settings: MagicMock,
    ) -> None:
        settings: MagicMock = MagicMock(spec=StorageBaseSettings)
        settings.prefix = "test_prefix"
        settings.buckets = {
            "test": "test-bucket",
            "media": "media-bucket",
            "templates": "templates-bucket",
        }
        settings.local_fs = True
        settings.memory_fs = False

        assert settings.prefix is not None
        assert "test" in settings.buckets
        assert "media" in settings.buckets
        assert "templates" in settings.buckets


class TestStorageBucketImpl(StorageBucket):
    def __init__(self, client: StorageBase, bucket: str) -> None:
        super().__init__(client, bucket)
        self.client = client
        self.bucket = bucket
        self.config = MagicMock()
        self.config.storage.buckets = {bucket: bucket}
        self.config.storage.prefix = None
        self.config.storage.local_fs = False
        self.config.storage.memory_fs = False
        self.prefix = None
        self.root = AsyncPath(f"{self.bucket}/{self.prefix}")
        self._path = bucket
        self.logger = MagicMock()

    @property
    def path(self) -> str:
        return self._path

    @path.setter
    def path(self, value: str) -> None:
        self._path = value

    def get_name(self, path: AsyncPath) -> str:
        return path.name

    def get_path(self, path: AsyncPath) -> str:
        return f"{self.bucket}/{path}"

    def get_url(self, path: AsyncPath) -> str:
        return f"https://example.com/{self.bucket}/{path}"

    async def read(self, path: AsyncPath) -> bytes:
        return b"test"

    async def read_text(self, path: AsyncPath) -> str:
        return "test"

    async def write_text(self, path: AsyncPath, data: str) -> None:
        pass

    async def mkdir(self, path: AsyncPath) -> None:
        pass


class TestStorageBucket:
    def test_init(self, mock_storage: StorageBase) -> None:
        bucket: StorageBucket = StorageBucket(mock_storage, "test-bucket")
        assert bucket.client == mock_storage
        assert bucket.name == "test-bucket"

    def test_name_property(self, mock_storage: StorageBase) -> None:
        bucket: StorageBucket = StorageBucket(mock_storage, "test-bucket")
        assert bucket.name == "test-bucket"

    def test_path_property(self, mock_storage: StorageBase) -> None:
        bucket: StorageBucket = StorageBucket(mock_storage, "test-bucket")
        assert bucket.path == "test-bucket"  # type: ignore

    @pytest.mark.anyio
    async def test_get_path(
        self,
        mock_storage_bucket: StorageBucket,
    ) -> None:
        path: AsyncPath = AsyncPath("test.txt")
        result: str = mock_storage_bucket.get_path(path)
        assert isinstance(result, str)
        assert "test-bucket" in result

    @pytest.mark.anyio
    async def test_get_url(
        self,
        mock_storage_bucket: StorageBucket,
    ) -> None:
        path: AsyncPath = AsyncPath("test.txt")
        result: str = mock_storage_bucket.get_url(path)
        assert isinstance(result, str)
        assert "test-bucket" in result
        assert "https://" in result

    @pytest.mark.anyio
    async def test_get_signed_url(
        self,
        mock_storage_bucket: StorageBucket,
    ) -> None:
        path: AsyncPath = AsyncPath("test.txt")
        result: str = await mock_storage_bucket.get_signed_url(path)
        assert isinstance(result, str)
        assert "test-bucket" in result
        assert "https://" in result

    @pytest.mark.anyio
    async def test_read(
        self,
        mock_storage_bucket: StorageBucket,
    ) -> None:
        path: AsyncPath = AsyncPath("test.txt")
        result: bytes = await mock_storage_bucket.read(path)  # type: ignore
        assert isinstance(result, bytes)
        assert result == b"test"

    @pytest.mark.anyio
    async def test_read_text(
        self,
        mock_storage_bucket: StorageBucket,
    ) -> None:
        path: AsyncPath = AsyncPath("test.txt")
        result: str = await mock_storage_bucket.read_text(path)  # type: ignore
        assert isinstance(result, str)
        assert result == "test"

    @pytest.mark.anyio
    async def test_write(
        self,
        mock_storage_bucket: StorageBucket,
    ) -> None:
        path: AsyncPath = AsyncPath("test.txt")
        data: bytes = b"test"
        await mock_storage_bucket.write(path, data)

    @pytest.mark.anyio
    async def test_write_text(
        self,
        mock_storage_bucket: StorageBucket,
    ) -> None:
        path: AsyncPath = AsyncPath("test.txt")
        data: str = "test"
        await mock_storage_bucket.write_text(path, data)  # type: ignore

    @pytest.mark.anyio
    async def test_delete(
        self,
        mock_storage_bucket: StorageBucket,
    ) -> None:
        path: AsyncPath = AsyncPath("test.txt")
        await mock_storage_bucket.delete(path)

    @pytest.mark.anyio
    async def test_mkdir(
        self,
        mock_storage_bucket: StorageBucket,
    ) -> None:
        path: AsyncPath = AsyncPath("test")
        await mock_storage_bucket.mkdir(path)  # type: ignore

    @pytest.mark.anyio
    async def test_create_bucket(
        self,
        mock_storage_bucket: StorageBucket,
    ) -> None:
        path: AsyncPath = AsyncPath("test")
        await mock_storage_bucket.create_bucket(path)

    @pytest.mark.anyio
    async def test_read_not_found(
        self,
        mock_storage_bucket: StorageBucket,
    ) -> None:
        path: AsyncPath = AsyncPath("not-found.txt")
        with pytest.raises(FileNotFoundError):
            await mock_storage_bucket.read(path)  # type: ignore

    @pytest.mark.anyio
    async def test_read_text_not_found(
        self,
        mock_storage_bucket: StorageBucket,
    ) -> None:
        path: AsyncPath = AsyncPath("not-found.txt")
        with pytest.raises(FileNotFoundError):
            await mock_storage_bucket.read_text(path)  # type: ignore

    @pytest.mark.anyio
    async def test_write_text_error(
        self,
        mock_storage_bucket: StorageBucket,
    ) -> None:
        path: AsyncPath = AsyncPath("error.txt")
        with pytest.raises(Exception):
            await mock_storage_bucket.write_text(path, "error")  # type: ignore

    @pytest.mark.anyio
    async def test_mkdir_error(
        self,
        mock_storage_bucket: StorageBucket,
    ) -> None:
        path: AsyncPath = AsyncPath("error")
        with pytest.raises(Exception):
            await mock_storage_bucket.mkdir(path)  # type: ignore


class TestStorageBase:
    def test_client_property(self, mock_storage_base: StorageBase) -> None:
        assert mock_storage_base.client is not None


class TestStorageFile(StorageFile):
    def __init__(self, name: str, storage: StorageBucket) -> None:
        super().__init__(name=name, storage=storage)
        self._storage = storage
        self._name = name

    @property
    def storage(self) -> StorageBucket:
        return self._storage

    @property
    def name(self) -> str:
        return self._name


class TestStorageFileTests:
    def test_init(self, mock_storage_bucket: StorageBucket) -> None:
        file: TestStorageFile = TestStorageFile(
            name="test.txt", storage=mock_storage_bucket
        )
        assert file.storage == mock_storage_bucket
        assert file.name == "test.txt"

    def test_name_property(self, mock_storage_bucket: StorageBucket) -> None:
        file: TestStorageFile = TestStorageFile(
            name="test.txt", storage=mock_storage_bucket
        )
        assert file.name == "test.txt"

    def test_path_property(
        self,
        mock_storage_bucket: StorageBucket,
    ) -> None:
        file: TestStorageFile = TestStorageFile(
            name="test.txt", storage=mock_storage_bucket
        )
        assert file.path == "test.txt"

    @pytest.mark.anyio
    async def test_size_property(
        self, mock_storage_bucket: StorageBucket, mock_client: AsyncMock
    ) -> None:
        file: TestStorageFile = TestStorageFile(
            name="test.txt", storage=mock_storage_bucket
        )
        size = await file.size
        assert size == 100

    @pytest.mark.anyio
    async def test_open_method(
        self, mock_storage_bucket: StorageBucket, mock_client: AsyncMock
    ) -> None:
        file: TestStorageFile = TestStorageFile(
            name="test.txt", storage=mock_storage_bucket
        )

        class AsyncContextManager:
            async def __aenter__(self):
                return AsyncMock(read=AsyncMock(return_value=b"test content"))

            async def __aexit__(
                self,
                exc_type: Optional[Type[BaseException]],
                exc_val: Optional[BaseException],
                exc_tb: Optional[TracebackType],
            ) -> None:
                pass

        mock_storage_bucket.open = AsyncMock(return_value=AsyncContextManager())

        async with await file.open() as f:
            content: bytes = await f.read()
            assert content == b"test content"

    @pytest.mark.anyio
    async def test_write_method(
        self, mock_storage_bucket: StorageBucket, mock_client: AsyncMock
    ) -> None:
        file: TestStorageFile = TestStorageFile(
            name="test.txt", storage=mock_storage_bucket
        )

        test_content = BytesIO(b"test content")

        async def mock_write(path: AsyncPath, data: BytesIO) -> bool:
            content = data.read()
            assert content == b"test content"
            return True

        mock_storage_bucket.write = mock_write  # type: ignore

        await file.write(test_content)


class TestStorageImage(StorageImage):
    def __init__(
        self, name: str, storage: StorageBucket, height: int, width: int
    ) -> None:
        super().__init__(name=name, storage=storage, height=height, width=width)
        self._storage = storage
        self._name = name
        self._height = height
        self._width = width

    @property
    def storage(self) -> StorageBucket:
        return self._storage

    @property
    def name(self) -> str:
        return self._name

    @property
    def height(self) -> int:
        return self._height

    @property
    def width(self) -> int:
        return self._width


class TestStorageImageTests:
    def test_init(self, mock_storage_bucket: StorageBucket) -> None:
        image: TestStorageImage = TestStorageImage(
            name="test.jpg", storage=mock_storage_bucket, height=100, width=200
        )
        assert image.storage == mock_storage_bucket
        assert image.name == "test.jpg"

    @pytest.mark.anyio
    async def test_height_property(self, mock_storage_bucket: StorageBucket) -> None:
        image: TestStorageImage = TestStorageImage(
            name="test.jpg", storage=mock_storage_bucket, height=100, width=200
        )

        setattr(image, "read", AsyncMock(return_value=b"test image data"))

        with patch("PIL.Image.open") as mock_image_open:
            mock_image = MagicMock()
            mock_image.size = (200, 100)
            mock_image_open.return_value = mock_image

            height = image.height
            assert height == 100

    @pytest.mark.anyio
    async def test_width_property(self, mock_storage_bucket: StorageBucket) -> None:
        image: TestStorageImage = TestStorageImage(
            name="test.jpg", storage=mock_storage_bucket, height=100, width=200
        )

        setattr(image, "read", AsyncMock(return_value=b"test image data"))

        with patch("PIL.Image.open") as mock_image_open:
            mock_image = MagicMock()
            mock_image.size = (200, 100)
            mock_image_open.return_value = mock_image

            width = image.width
            assert width == 200

    @pytest.mark.anyio
    async def test_size_property(
        self, mock_storage_bucket: StorageBucket, mock_client: AsyncMock
    ) -> None:
        image: TestStorageImage = TestStorageImage(
            name="test.jpg", storage=mock_storage_bucket, height=100, width=200
        )

        size = await image.size
        assert size == 100
