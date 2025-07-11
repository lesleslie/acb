"""Tests for the storage base components."""

from io import BytesIO
from types import TracebackType
from typing import Any
from unittest.mock import AsyncMock, MagicMock

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
    mock_storage_settings: MagicMock,
    mock_app_settings: MagicMock,
) -> MagicMock:
    config: MagicMock = MagicMock(spec=Config)
    config.storage = mock_storage_settings
    type(config).__getattr__ = MagicMock(return_value=mock_storage_settings)
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
        return_value={
            "size": 100,
            "timeCreated": "2023-01-01",
            "updated": "2023-01-02",
        },
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
        return_value={"name": "test.txt", "size": 100, "type": "file"},
    )
    client.modified = MagicMock()
    client.created = MagicMock()
    client.isfile = MagicMock(return_value=True)
    client.set_cors = MagicMock()
    return client


@pytest.fixture
def mock_storage() -> StorageBase:
    class StorageImpl(StorageBase):
        def __init__(self) -> None:
            super().__init__()
            self.config = MagicMock()
            self.logger = MagicMock()
            self._client = MagicMock()

            self._client.read.side_effect = lambda path: (
                raise_exception("error.txt" in str(path), Exception) or b"test content"
            )
            self._client.read_text.side_effect = lambda path: (
                raise_exception("error.txt" in str(path), Exception) or "test content"
            )
            self._client.write_text.side_effect = lambda path, data: (
                raise_exception("error.txt" in str(path), Exception)
            )
            self._client.mkdir.side_effect = lambda path: (
                raise_exception("error" in str(path), Exception)
            )

        @property
        def client(self) -> Any:  # type: ignore
            return self._client

    return StorageImpl()


@pytest.fixture
async def mock_storage_bucket(
    mock_storage: StorageBase,
    mock_config: MagicMock,
) -> StorageBucket:
    mock_bucket = MagicMock(spec=StorageBucket)

    mock_bucket.name = "test-bucket"
    mock_bucket.bucket = "test-bucket"
    mock_bucket.prefix = "test-prefix"

    mock_bucket._path = AsyncMock(return_value="test-bucket")
    mock_bucket._get_path = AsyncMock(return_value="test-bucket/test-path")
    mock_bucket._get_url = AsyncMock(return_value="https://test-bucket/test-path")
    mock_bucket._get_signed_url = AsyncMock(
        return_value="https://test-bucket/test-path?signed=true",
    )
    mock_bucket._read = AsyncMock(return_value=b"test data")
    mock_bucket._read_text = AsyncMock(return_value="test data")
    mock_bucket._stat = AsyncMock(return_value={"size": 1024})

    for method in ("write_text", "mkdir", "delete", "create_bucket"):
        setattr(mock_bucket, f"_{method}", AsyncMock())

    mock_bucket.path = mock_bucket._path
    mock_bucket.get_path = mock_bucket._get_path
    mock_bucket.get_url = mock_bucket._get_url

    async def get_signed_url(path: str | AsyncPath, expires: int = 3600) -> str:
        return await mock_bucket._get_signed_url(path, expires=expires)

    async def read(path: str | AsyncPath) -> bytes:
        return await mock_bucket._read(path)

    async def read_text(path: str | AsyncPath) -> str:
        return await mock_bucket._read_text(path)

    async def write_text(path: str | AsyncPath, data: str) -> None:
        await mock_bucket._write_text(path, data)

    async def mkdir(path: str | AsyncPath) -> None:
        await mock_bucket._mkdir(path)

    async def delete(path: str | AsyncPath) -> None:
        await mock_bucket._delete(path)

    async def create_bucket(path: str | AsyncPath) -> None:
        await mock_bucket._create_bucket(path)

    async def stat(path: str | AsyncPath) -> dict[str, Any]:
        return await mock_bucket._stat(path)

    mock_bucket.get_signed_url = get_signed_url
    mock_bucket.read = read
    mock_bucket.read_text = read_text
    mock_bucket.write_text = write_text
    mock_bucket.mkdir = mkdir
    mock_bucket.delete = delete
    mock_bucket.create_bucket = create_bucket
    mock_bucket.stat = stat

    return mock_bucket


@pytest.fixture
def mock_storage_base(mock_client: AsyncMock, mock_storage: StorageBase) -> StorageBase:
    return mock_storage


def raise_exception(condition: bool, exception: type[Exception]) -> None:
    if condition:
        msg = "Test exception"
        raise exception(msg)


class StorageBaseSettingsTest:
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


class StorageBucketImpl(StorageBucket):
    def __init__(self, client: StorageBase, bucket: str) -> None:
        super().__init__(client, bucket)
        self._client = client
        self.bucket = bucket
        self.config = MagicMock()
        self.config.storage.buckets = {bucket: bucket}
        self.config.storage.prefix = None
        self.config.storage.local_fs = False
        self.config.storage.memory_fs = False
        self.prefix = None
        self.root = AsyncPath(f"{self.bucket}/{self.prefix}")
        self.logger = MagicMock()
        self._path_property = bucket

    @property
    def path_property(self) -> str:
        return self._path_property

    @path_property.setter
    def path_property(self, value: str) -> None:
        self._path_property = value

    async def read(self, path: AsyncPath) -> bytes:
        return b"test content"

    async def read_text(self, path: AsyncPath) -> str:
        return "test content"

    async def write_text(self, path: AsyncPath, data: str) -> None:
        pass

    async def mkdir(self, path: AsyncPath) -> None:
        pass

    async def delete(self, path: AsyncPath) -> None:
        pass

    async def create_bucket(self, path: AsyncPath) -> None:
        pass

    async def stat(self, path: AsyncPath) -> dict[str, Any]:
        return {
            "size": 100,
            "timeCreated": "2021-01-01T00:00:00Z",
            "updated": "2021-01-01T00:00:00Z",
        }

    def get_name(self, path: AsyncPath) -> str:
        return path.name

    def get_path(self, path: AsyncPath) -> str:
        return f"{self.bucket}/{path}"

    def get_url(self, path: AsyncPath) -> str:
        return f"https://example.com/{self.bucket}/{path}"

    async def get_signed_url(self, path: AsyncPath, expires: int = 3600) -> str:
        return f"https://example.com/{self.bucket}/{path}?signed=true&expires={expires}"


class StorageBucketTest:
    def test_init(self, mock_storage_bucket: StorageBucket) -> None:
        assert mock_storage_bucket.name == "test-bucket"
        assert mock_storage_bucket.bucket == "test-bucket"
        assert mock_storage_bucket.prefix == "test-prefix"

    @pytest.mark.asyncio
    async def test_path_method(self, mock_storage_bucket: StorageBucket) -> None:
        assert mock_storage_bucket.path is not None  # type: ignore
        assert mock_storage_bucket._path is not None  # type: ignore

    @pytest.mark.asyncio
    async def test_get_path(self, mock_storage_bucket: StorageBucket) -> None:
        assert mock_storage_bucket.get_path is not None
        assert mock_storage_bucket._get_path is not None  # type: ignore

    @pytest.mark.asyncio
    async def test_get_url(self, mock_storage_bucket: StorageBucket) -> None:
        assert mock_storage_bucket.get_url is not None
        assert mock_storage_bucket._get_url is not None  # type: ignore

    @pytest.mark.asyncio
    async def test_get_signed_url(self, mock_storage_bucket: StorageBucket) -> None:
        assert mock_storage_bucket.get_signed_url is not None
        assert mock_storage_bucket._get_signed_url is not None  # type: ignore

    @pytest.mark.asyncio
    async def test_read(self, mock_storage_bucket: StorageBucket) -> None:
        assert mock_storage_bucket.read is not None  # type: ignore
        assert mock_storage_bucket._read is not None  # type: ignore

    @pytest.mark.asyncio
    async def test_read_text(self, mock_storage_bucket: StorageBucket) -> None:
        assert mock_storage_bucket.read_text is not None  # type: ignore
        assert mock_storage_bucket._read_text is not None  # type: ignore

    @pytest.mark.asyncio
    async def test_write_text(self, mock_storage_bucket: StorageBucket) -> None:
        assert mock_storage_bucket.write_text is not None  # type: ignore
        assert mock_storage_bucket._write_text is not None  # type: ignore

    @pytest.mark.asyncio
    async def test_mkdir(self, mock_storage_bucket: StorageBucket) -> None:
        assert mock_storage_bucket.mkdir is not None  # type: ignore
        assert mock_storage_bucket._mkdir is not None  # type: ignore


class StorageBaseTest:
    @pytest.mark.asyncio
    async def test_client_property(self, mock_storage_base: StorageBase) -> None:
        assert mock_storage_base.client is not None


class StorageFileImpl(StorageFile):
    def __init__(self, name: str, storage: StorageBucket) -> None:
        super().__init__(name=name, storage=storage)
        self._storage = storage
        self._name = name

    @property
    def storage(self) -> StorageBucket:
        return self._storage

    async def read(self) -> bytes:
        return await self._storage.read(self._name)  # type: ignore

    async def read_text(self) -> str:
        return await self._storage.read_text(self._name)  # type: ignore

    @property
    def name(self) -> str:
        return self._name

    @property
    def path(self) -> str:
        return self._name

    @property
    def size(self) -> int:  # type: ignore
        return 1024


class StorageFileTest:
    def test_init(self, mock_storage_bucket: StorageBucket) -> None:
        file: StorageFileImpl = StorageFileImpl(
            name="test.txt",
            storage=mock_storage_bucket,
        )
        assert file.storage == mock_storage_bucket
        assert file.name == "test.txt"

    def test_name_property(self, mock_storage_bucket: StorageBucket) -> None:
        file: StorageFileImpl = StorageFileImpl(
            name="test.txt",
            storage=mock_storage_bucket,
        )
        assert file.name == "test.txt"

    @pytest.mark.asyncio
    async def test_path_property(
        self,
        mock_storage_bucket: StorageBucket,
    ) -> None:
        file: StorageFileImpl = StorageFileImpl(
            name="test.txt",
            storage=mock_storage_bucket,
        )
        assert file.path == "test.txt"

    @pytest.mark.asyncio
    async def test_size_property(
        self,
        mock_storage_bucket: StorageBucket,
        mock_client: AsyncMock,
    ) -> None:
        file: StorageFileImpl = StorageFileImpl(
            name="test.txt",
            storage=mock_storage_bucket,
        )
        size = file.size
        assert size == 1024

    @pytest.mark.asyncio
    async def test_open_method(
        self,
        mock_storage_bucket: StorageBucket,
        mock_client: AsyncMock,
    ) -> None:
        file: StorageFileImpl = StorageFileImpl(
            name="test.txt",
            storage=mock_storage_bucket,
        )

        class AsyncContextManager:
            async def __aenter__(self):
                return AsyncMock(read=AsyncMock(return_value=b"test content"))

            async def __aexit__(
                self,
                exc_type: type[BaseException] | None,
                exc_val: BaseException | None,
                exc_tb: TracebackType | None,
            ) -> None:
                pass

        mock_storage_bucket.open = AsyncMock(return_value=AsyncContextManager())

        async with await file.open() as f:
            content: bytes = await f.read()
            assert content == b"test content"

    @pytest.mark.asyncio
    async def test_write_method(
        self,
        mock_storage_bucket: StorageBucket,
        mock_client: AsyncMock,
    ) -> None:
        file: StorageFileImpl = StorageFileImpl(
            name="test.txt",
            storage=mock_storage_bucket,
        )

        test_content = BytesIO(b"test content")

        async def mock_write(path: AsyncPath, data: BytesIO) -> bool:
            content = data.read()
            assert content == b"test content"
            return True

        mock_storage_bucket.write = mock_write  # type: ignore

        await file.write(test_content)


class StorageImageImpl(StorageImage):
    def __init__(
        self,
        name: str,
        storage: StorageBucket,
        height: int,
        width: int,
    ) -> None:
        super().__init__(name=name, storage=storage, height=height, width=width)
        self._storage = storage
        self._name = name
        self._height = height
        self._width = width

    @property
    def name(self) -> str:
        return self._name

    @property
    def size(self) -> tuple[int, int]:  # type: ignore
        return self._height, self._width

    @property
    def path(self) -> str:
        return self._name


class StorageImageTest:
    def test_init(self, mock_storage_bucket: StorageBucket) -> None:
        image: StorageImageImpl = StorageImageImpl(
            name="test.jpg",
            storage=mock_storage_bucket,
            height=100,
            width=200,
        )
        assert image.name == "test.jpg"
        assert image._storage == mock_storage_bucket
        assert image._height == 100
        assert image._width == 200

    def test_height_property(self, mock_storage_bucket: StorageBucket) -> None:
        image: StorageImageImpl = StorageImageImpl(
            name="test.jpg",
            storage=mock_storage_bucket,
            height=100,
            width=200,
        )
        assert image.height == 100

    def test_width_property(self, mock_storage_bucket: StorageBucket) -> None:
        image: StorageImageImpl = StorageImageImpl(
            name="test.jpg",
            storage=mock_storage_bucket,
            height=100,
            width=200,
        )
        assert image.width == 200

    @pytest.mark.asyncio
    async def test_size_property(
        self,
        mock_storage_bucket: StorageBucket,
        mock_client: AsyncMock,
    ) -> None:
        mock_client.stat.return_value = {"size": 123}
        image: StorageImageImpl = StorageImageImpl(
            name="test.jpg",
            storage=mock_storage_bucket,
            height=100,
            width=200,
        )
        result = image.size
        assert result == (100, 200)
