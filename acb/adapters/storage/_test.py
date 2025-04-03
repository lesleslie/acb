from io import BytesIO
from unittest.mock import MagicMock

import pytest
from anyio import Path as AsyncPath
from fsspec.implementations.memory import MemoryFileSystem
from acb.adapters.storage._base import (
    StorageBase,
    StorageBaseSettings,
    StorageBucket,
    StorageFile,
    StorageImage,
)
from acb.config import Config


@pytest.fixture
def config() -> Config:
    config = Config()
    config.storage = StorageBaseSettings(buckets={"test": "test-bucket"})  # type: ignore
    return config


@pytest.fixture
def memory_fs() -> MemoryFileSystem:
    return MemoryFileSystem()


@pytest.fixture
def storage_base(config: Config, memory_fs: MemoryFileSystem) -> StorageBase:
    storage = StorageBase()
    storage.file_system = MemoryFileSystem  # type: ignore
    storage.client = memory_fs  # type: ignore
    return storage


@pytest.fixture
def storage_bucket(config: Config, memory_fs: MemoryFileSystem) -> StorageBucket:
    return StorageBucket(client=memory_fs, bucket="test")


@pytest.mark.asyncio
async def test_storage_base_init(storage_base: StorageBase, config: Config) -> None:
    await storage_base.init()
    assert storage_base.test is not None
    assert isinstance(storage_base.test, StorageBucket)
    assert storage_base.test.name == "test"
    assert storage_base.test.bucket == "test-bucket"


@pytest.mark.asyncio
async def test_storage_bucket_get_path(
    storage_bucket: StorageBucket, config: Config
) -> None:
    path = AsyncPath("test_file.txt")
    expected_path = "test-bucket/test_file.txt"
    assert storage_bucket.get_path(path) == expected_path
    config.storage.local_fs = True
    assert storage_bucket.get_path(path) == str(path)


@pytest.mark.asyncio
async def test_storage_bucket_get_name(storage_bucket: StorageBucket) -> None:
    path = AsyncPath("test_file.txt")
    assert storage_bucket.get_name(path) == "test_file.txt"


@pytest.mark.asyncio
async def test_storage_bucket_get_url(storage_bucket: StorageBucket) -> None:
    path = AsyncPath("test_file.txt")
    storage_bucket.client.url = MagicMock(return_value="test_url")
    assert storage_bucket.get_url(path) == "test_url"


@pytest.mark.asyncio
async def test_storage_bucket_stat(
    storage_bucket: StorageBucket, memory_fs: MemoryFileSystem
) -> None:
    path = AsyncPath("test_file.txt")
    memory_fs.pipe_file("test-bucket/test_file.txt", b"test data")
    stat = await storage_bucket.stat(path)
    assert stat["name"] == "test-bucket/test_file.txt"
    assert stat["size"] == 9
    assert stat["type"] == "file"


@pytest.mark.asyncio
async def test_storage_bucket_list(
    storage_bucket: StorageBucket, memory_fs: MemoryFileSystem
) -> None:
    path = AsyncPath("test_dir")
    memory_fs.mkdir("test-bucket/test_dir")
    memory_fs.pipe_file("test-bucket/test_dir/test_file.txt", b"test data")
    result = await storage_bucket.list(path)
    assert result == ["test-bucket/test_dir/test_file.txt"]


@pytest.mark.asyncio
async def test_storage_bucket_exists(
    storage_bucket: StorageBucket, memory_fs: MemoryFileSystem
) -> None:
    path = AsyncPath("test_file.txt")
    memory_fs.pipe_file("test-bucket/test_file.txt", b"test data")
    assert await storage_bucket.exists(path) is True
    assert await storage_bucket.exists(AsyncPath("nonexistent.txt")) is False


@pytest.mark.asyncio
async def test_storage_bucket_create_bucket(
    storage_bucket: StorageBucket, memory_fs: MemoryFileSystem
) -> None:
    path = AsyncPath("test_dir")
    await storage_bucket.create_bucket(path)
    assert memory_fs.exists("test-bucket/test_dir") is True


@pytest.mark.asyncio
async def test_storage_bucket_open(
    storage_bucket: StorageBucket, memory_fs: MemoryFileSystem
) -> None:
    path = AsyncPath("test_file.txt")
    memory_fs.pipe_file("test-bucket/test_file.txt", b"test data")
    data = await storage_bucket.open(path)
    assert data == b"test data"
    with pytest.raises(FileNotFoundError):
        await storage_bucket.open(AsyncPath("nonexistent.txt"))


@pytest.mark.asyncio
async def test_storage_bucket_write(
    storage_bucket: StorageBucket, memory_fs: MemoryFileSystem
) -> None:
    path = AsyncPath("test_file.txt")
    await storage_bucket.write(path, b"test data")
    assert memory_fs.cat("test-bucket/test_file.txt") == b"test data"


@pytest.mark.asyncio
async def test_storage_bucket_delete(
    storage_bucket: StorageBucket, memory_fs: MemoryFileSystem
) -> None:
    path = AsyncPath("test_file.txt")
    memory_fs.pipe_file("test-bucket/test_file.txt", b"test data")
    await storage_bucket.delete(path)
    assert memory_fs.exists("test-bucket/test_file.txt") is False


@pytest.mark.asyncio
async def test_storage_file_properties(
    storage_bucket: StorageBucket, memory_fs: MemoryFileSystem
) -> None:
    memory_fs.pipe_file("test-bucket/test_file.txt", b"test data")
    storage_file = StorageFile(name="test_file.txt", storage=storage_bucket)
    assert storage_file.name == "test_file.txt"
    assert storage_file.path == "test-bucket/test_file.txt"
    assert await storage_file.size == 9
    assert isinstance(await storage_file.checksum, int)


@pytest.mark.asyncio
async def test_storage_file_open(
    storage_bucket: StorageBucket, memory_fs: MemoryFileSystem
) -> None:
    memory_fs.pipe_file("test-bucket/test_file.txt", b"test data")
    storage_file = StorageFile(name="test_file.txt", storage=storage_bucket)
    data = await storage_file.open()
    assert data == b"test data"


@pytest.mark.asyncio
async def test_storage_file_write(
    storage_bucket: StorageBucket, memory_fs: MemoryFileSystem
) -> None:
    storage_file = StorageFile(name="test_file.txt", storage=storage_bucket)
    await storage_file.write(BytesIO(b"test data"))
    assert memory_fs.cat("test-bucket/test_file.txt") == b"test data"


@pytest.mark.asyncio
async def test_storage_image_properties(
    storage_bucket: StorageBucket, memory_fs: MemoryFileSystem
) -> None:
    memory_fs.pipe_file("test-bucket/test_image.jpg", b"test data")
    storage_image = StorageImage(
        name="test_image.jpg", storage=storage_bucket, height=100, width=200
    )
    assert storage_image.name == "test_image.jpg"
    assert storage_image.path == "test-bucket/test_image.jpg"
    assert storage_image.height == 100
    assert storage_image.width == 200
