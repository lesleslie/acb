"""Tests for the storage base components."""

from io import BytesIO
from types import TracebackType
from typing import Optional, Type
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
def mock_storage() -> StorageBase:
    class TestStorageImpl(StorageBase):
        def __init__(self) -> None:
            self.file_system = MagicMock()
            self.templates = None
            self.media = None
            self.test = None
            self.logger = MagicMock()

            self.config = MagicMock()
            self.config.storage = MagicMock()
            self.config.storage.buckets = {
                "test": "test-bucket",
                "media": "media-bucket",
                "templates": "templates-bucket",
            }
            self.config.storage.prefix = "test-prefix"
            self.config.storage.local_fs = False
            self.config.storage.memory_fs = False

            self._client = MagicMock()
            self._client._exists = AsyncMock(
                side_effect=lambda path: path != "test-bucket/test-prefix/not-found.txt"
            )
            self._client._info = AsyncMock(
                return_value={
                    "size": 100,
                    "timeCreated": "2023-01-01",
                    "updated": "2023-01-02",
                }
            )
            self._client._ls = AsyncMock(return_value=[])
            self._client._sign = AsyncMock(return_value="signed-url")
            self._client.url = MagicMock(return_value="https://example.com/test")
            self._client.read = AsyncMock(return_value=b"test content")
            self._client.read_text = AsyncMock(return_value="test content")
            self._client.write = AsyncMock()
            self._client.write_text = AsyncMock()
            self._client.delete = AsyncMock()
            self._client.mkdir = AsyncMock()

            self._client.write.side_effect = lambda path, data: (
                raise_exception("error.txt" in path, Exception("Write error"))
            )
            self._client.write_text.side_effect = lambda path, data: (
                raise_exception("error.txt" in path, Exception("Write error"))
            )
            self._client.mkdir.side_effect = lambda path: (
                raise_exception("error" in path, Exception("Mkdir error"))
            )

        @property
        def client(self):
            return self._client

    return TestStorageImpl()


@pytest.fixture
def mock_storage_bucket(mock_storage: StorageBase) -> StorageBucket:
    class TestStorageBucketImpl(StorageBucket):
        def __init__(self, storage: StorageBase, bucket_name: str) -> None:
            self.client = storage.client
            self.name = bucket_name
            self.bucket = "test-bucket"
            self.prefix = "test-prefix"
            self.root = AsyncPath(f"{self.bucket}/{self.prefix}")
            self.logger = MagicMock()
            self.config = MagicMock()
            self.config.storage = MagicMock()
            self.config.storage.buckets = {bucket_name: self.bucket}
            self.config.storage.prefix = "test-prefix"
            self.config.storage.local_fs = False
            self.config.storage.memory_fs = False

        def get_name(self, path: AsyncPath) -> str:
            return str(path)

        def get_path(self, path: AsyncPath) -> str:
            return f"{self.bucket}/{self.prefix}/{path}"

        def path(self, path: str) -> AsyncPath:
            return AsyncPath(path)

        def get_url(self, path: AsyncPath) -> str:
            return f"https://storage.example.com/{self.bucket}/{self.prefix}/{path}"

        async def get_signed_url(self, path: AsyncPath, expires: int = 3600) -> str:
            return f"https://storage.example.com/{self.bucket}/{self.prefix}/{path}?signed=true&expires={expires}"

        async def read(self, path: AsyncPath) -> bytes:
            if "not-found" in str(path):
                raise FileNotFoundError(f"File not found: {path}")
            return b"test content"

        async def read_text(self, path: AsyncPath) -> str:
            if "not-found" in str(path):
                raise FileNotFoundError(f"File not found: {path}")
            return "test content"

        async def write(self, path: AsyncPath, data: bytes | BytesIO) -> None:
            if isinstance(data, BytesIO):
                data = data.read()
            pass

        async def write_text(self, path: AsyncPath, text: str) -> None:
            if "error" in str(path):
                raise RuntimeError("Error writing file")
            pass

        async def delete(self, path: AsyncPath) -> None:
            pass

        async def mkdir(self, path: AsyncPath) -> None:
            if "error" in str(path):
                raise RuntimeError("Error creating directory")
            pass

        async def create_bucket(self, path: AsyncPath) -> None:
            pass

        async def stat(self, path: AsyncPath) -> dict:
            return {
                "size": 100,
                "timeCreated": "2021-01-01T00:00:00Z",
                "updated": "2021-01-01T00:00:00Z",
            }

    return TestStorageBucketImpl(mock_storage, "test-bucket")


@pytest.fixture
def mock_storage_base(mock_client: AsyncMock, mock_storage: StorageBase) -> StorageBase:
    return mock_storage


def raise_exception(condition, exception):
    if condition:
        raise exception


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
    def test_init(self, mock_storage_bucket: StorageBucket) -> None:
        assert mock_storage_bucket.bucket == "test-bucket"
        assert mock_storage_bucket.prefix == "test-prefix"
        assert mock_storage_bucket.root == AsyncPath("test-bucket/test-prefix")

    def test_name_property(self, mock_storage_bucket: StorageBucket) -> None:
        assert mock_storage_bucket.name == "test-bucket"

    def test_path_property(self, mock_storage_bucket: StorageBucket) -> None:
        path = mock_storage_bucket.path("test.txt")
        assert path == AsyncPath("test.txt")

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
        path = AsyncPath("test.txt")
        url = mock_storage_bucket.get_url(path)
        assert url == "https://storage.example.com/test-bucket/test-prefix/test.txt"

    @pytest.mark.anyio
    async def test_get_signed_url(
        self,
        mock_storage_bucket: StorageBucket,
    ) -> None:
        path = AsyncPath("test.txt")
        url = await mock_storage_bucket.get_signed_url(path)
        assert (
            url
            == "https://storage.example.com/test-bucket/test-prefix/test.txt?signed=true&expires=3600"
        )

    @pytest.mark.anyio
    async def test_read(
        self,
        mock_storage_bucket: StorageBucket,
    ) -> None:
        path = AsyncPath("test.txt")
        content = await mock_storage_bucket.read(path)
        assert content == b"test content"

    @pytest.mark.anyio
    async def test_read_text(
        self,
        mock_storage_bucket: StorageBucket,
    ) -> None:
        path = AsyncPath("test.txt")
        content = await mock_storage_bucket.read_text(path)
        assert content == "test content"

    @pytest.mark.anyio
    async def test_write(
        self,
        mock_storage_bucket: StorageBucket,
    ) -> None:
        path = AsyncPath("test.txt")
        await mock_storage_bucket.write(path, b"test content")

    @pytest.mark.anyio
    async def test_write_text(
        self,
        mock_storage_bucket: StorageBucket,
    ) -> None:
        path = AsyncPath("test.txt")
        await mock_storage_bucket.write_text(path, "test content")

    @pytest.mark.anyio
    async def test_delete(
        self,
        mock_storage_bucket: StorageBucket,
    ) -> None:
        path = AsyncPath("test.txt")
        await mock_storage_bucket.delete(path)

    @pytest.mark.anyio
    async def test_mkdir(
        self,
        mock_storage_bucket: StorageBucket,
    ) -> None:
        path = AsyncPath("test_dir")
        await mock_storage_bucket.mkdir(path)

    @pytest.mark.anyio
    async def test_create_bucket(
        self,
        mock_storage_bucket: StorageBucket,
    ) -> None:
        path = AsyncPath("test")
        await mock_storage_bucket.create_bucket(path)

    @pytest.mark.anyio
    async def test_read_not_found(
        self,
        mock_storage_bucket: StorageBucket,
    ) -> None:
        path = AsyncPath("not-found.txt")
        with pytest.raises(FileNotFoundError):
            await mock_storage_bucket.read(path)

    @pytest.mark.anyio
    async def test_read_text_not_found(
        self,
        mock_storage_bucket: StorageBucket,
    ) -> None:
        path = AsyncPath("not-found.txt")
        with pytest.raises(FileNotFoundError):
            await mock_storage_bucket.read_text(path)

    @pytest.mark.anyio
    async def test_write_text_error(
        self,
        mock_storage_bucket: StorageBucket,
    ) -> None:
        path = AsyncPath("error.txt")
        with pytest.raises(RuntimeError):
            await mock_storage_bucket.write_text(path, "error")

    @pytest.mark.anyio
    async def test_mkdir_error(
        self,
        mock_storage_bucket: StorageBucket,
    ) -> None:
        path = AsyncPath("error")
        with pytest.raises(RuntimeError):
            await mock_storage_bucket.mkdir(path)


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

    async def read(self) -> bytes:
        return await self._storage.read(AsyncPath(self._name))

    async def read_text(self) -> str:
        return await self._storage.read_text(AsyncPath(self._name))

    @property
    def path(self) -> str:
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

    async def size(self) -> tuple[int, int]:
        return (self.width, self.height)

    @property
    def path(self) -> str:
        return self._name


class TestStorageImageTests:
    def test_init(self, mock_storage_bucket: StorageBucket) -> None:
        image: TestStorageImage = TestStorageImage(
            name="test.jpg", storage=mock_storage_bucket, height=100, width=200
        )
        assert image.name == "test.jpg"
        assert image._storage == mock_storage_bucket
        assert image._height == 100
        assert image._width == 200

    @pytest.mark.anyio
    async def test_height_property(self, mock_storage_bucket: StorageBucket) -> None:
        image: TestStorageImage = TestStorageImage(
            name="test.jpg", storage=mock_storage_bucket, height=100, width=200
        )

        assert image.height == 100

    @pytest.mark.anyio
    async def test_width_property(self, mock_storage_bucket: StorageBucket) -> None:
        image: TestStorageImage = TestStorageImage(
            name="test.jpg", storage=mock_storage_bucket, height=100, width=200
        )

        assert image.width == 200

    @pytest.mark.anyio
    async def test_size_property(
        self, mock_storage_bucket: StorageBucket, mock_client: AsyncMock
    ) -> None:
        image: TestStorageImage = TestStorageImage(
            name="test.jpg", storage=mock_storage_bucket, height=100, width=200
        )

        size = await image.size()
        assert size == (200, 100)
