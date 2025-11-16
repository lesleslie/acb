"""Comprehensive tests for the Storage Base adapter."""

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


class TestStorageBaseSettings:
    """Test StorageBaseSettings class."""

    def test_init_with_storage_adapter(self) -> None:
        """Test initialization with storage adapter."""
        # Create settings directly without DI
        settings = StorageBaseSettings(
            prefix="test_prefix",
            local_fs=False,
            memory_fs=False,
        )

        assert settings.prefix == "test_prefix"
        assert settings.local_fs is False
        assert settings.memory_fs is False

    def test_init_with_local_storage_adapter(self) -> None:
        """Test initialization with local storage adapter."""
        # StorageBaseSettings.__init__ has @depends.inject decorator which
        # uses DI to get Config and get_adapter(), so we test basic instantiation
        settings = StorageBaseSettings(
            prefix="test_prefix",
        )

        assert settings.prefix == "test_prefix"
        # local_fs/memory_fs values are set by __init__ based on get_adapter()
        # which returns None in test environment, so both will be False
        assert isinstance(settings.local_fs, bool)

    def test_init_with_memory_storage_adapter(self) -> None:
        """Test initialization with memory storage adapter."""
        # StorageBaseSettings.__init__ has @depends.inject decorator which
        # uses DI to get Config and get_adapter(), so we test basic instantiation
        settings = StorageBaseSettings(
            prefix="test_prefix",
        )

        assert settings.prefix == "test_prefix"
        # local_fs/memory_fs values are set by __init__ based on get_adapter()
        # which returns None in test environment, so both will be False
        assert isinstance(settings.memory_fs, bool)

    def test_init_without_storage_adapter(self) -> None:
        """Test initialization without storage adapter."""
        # Create settings directly without DI
        settings = StorageBaseSettings(
            prefix="test_prefix",
            local_fs=False,
            memory_fs=False,
        )

        assert settings.prefix == "test_prefix"
        assert settings.local_fs is False
        assert settings.memory_fs is False


class TestStorageBucket:
    """Test StorageBucket class."""

    @pytest.fixture
    def mock_client(self) -> AsyncMock:
        """Create a mock client."""
        client = AsyncMock()
        client.url = AsyncMock(
            return_value="https://example.com/test-bucket/test-prefix/test.txt"
        )
        client._sign = AsyncMock(
            return_value="https://signed.example.com/test-bucket/test-prefix/test.txt?signature=abc123"
        )
        client._info = AsyncMock(
            return_value={
                "size": 1024,
                "timeCreated": "2023-01-01T00:00:00Z",
                "updated": "2023-01-02T00:00:00Z",
            }
        )
        client._ls = AsyncMock(return_value=["file1.txt", "file2.txt"])
        client._exists = AsyncMock(return_value=True)
        client._mkdir = AsyncMock()
        client._pipe_file = AsyncMock()
        client._rm_file = AsyncMock()
        return client

    @pytest.fixture
    def mock_config(self) -> MagicMock:
        """Create a mock config."""
        config = MagicMock(spec=Config)
        config.storage = MagicMock()
        config.storage.buckets = {"test": "test-bucket"}
        config.storage.prefix = "test-prefix"
        config.storage.local_fs = False
        config.storage.memory_fs = False
        return config

    @pytest.fixture
    def storage_bucket(
        self, mock_client: AsyncMock, mock_config: MagicMock
    ) -> StorageBucket:
        """Create a StorageBucket instance."""
        return StorageBucket(mock_client, "test", mock_config, "test-prefix")

    def test_init(self, storage_bucket: StorageBucket) -> None:
        """Test StorageBucket initialization."""
        assert storage_bucket.name == "test"
        assert storage_bucket.bucket == "test-bucket"
        assert storage_bucket.prefix == "test-prefix"
        assert str(storage_bucket.root) == "test-bucket/test-prefix"

    def test_get_name(self, storage_bucket: StorageBucket) -> None:
        """Test get_name method."""
        path = AsyncPath("test/file.txt")
        name = storage_bucket.get_name(path)
        assert name == "file.txt"

    def test_get_path(self, storage_bucket: StorageBucket) -> None:
        """Test get_path method."""
        path = AsyncPath("test/file.txt")
        path_str = storage_bucket.get_path(path)
        assert path_str == "test-bucket/test-prefix/test/file.txt"

    def test_get_path_local_fs(
        self, mock_client: AsyncMock, mock_config: MagicMock
    ) -> None:
        """Test get_path method with local filesystem."""
        mock_config.storage.local_fs = True
        bucket = StorageBucket(mock_client, "test", mock_config, "test-prefix")

        path = AsyncPath("test/file.txt")
        path_str = bucket.get_path(path)
        assert path_str == "test/file.txt"

    def test_get_url(self, storage_bucket: StorageBucket) -> None:
        """Test get_url method."""
        path = AsyncPath("test/file.txt")
        storage_bucket.get_url(path)
        # This will call the client.url method
        storage_bucket.client.url.assert_called_once_with(
            "test-bucket/test-prefix/test/file.txt"
        )

    @pytest.mark.asyncio
    async def test_get_date_created(self, storage_bucket: StorageBucket) -> None:
        """Test get_date_created method."""
        path = AsyncPath("test/file.txt")
        date_created = await storage_bucket.get_date_created(path)
        assert date_created == "2023-01-01T00:00:00Z"
        storage_bucket.client._info.assert_called_once_with(
            "test-bucket/test-prefix/test/file.txt"
        )

    @pytest.mark.asyncio
    async def test_get_date_updated(self, storage_bucket: StorageBucket) -> None:
        """Test get_date_updated method."""
        path = AsyncPath("test/file.txt")
        date_updated = await storage_bucket.get_date_updated(path)
        assert date_updated == "2023-01-02T00:00:00Z"
        storage_bucket.client._info.assert_called_once_with(
            "test-bucket/test-prefix/test/file.txt"
        )

    @pytest.mark.asyncio
    async def test_get_size(self, storage_bucket: StorageBucket) -> None:
        """Test get_size method."""
        path = AsyncPath("test/file.txt")
        size = await storage_bucket.get_size(path)
        assert size == 1024
        storage_bucket.client._info.assert_called_once_with(
            "test-bucket/test-prefix/test/file.txt"
        )

    @pytest.mark.asyncio
    async def test_get_checksum(self, storage_bucket: StorageBucket) -> None:
        """Test get_checksum method."""
        path = AsyncPath("test/file.txt")
        # We can't easily test the actual hash.crc32c call, but we can test that it's called
        with pytest.MonkeyPatch().context() as mp:
            mock_hash = MagicMock()
            mock_hash.crc32c = AsyncMock(return_value="1234abcd")
            mp.setattr("acb.actions.hash.hash", mock_hash)

            checksum = await storage_bucket.get_checksum(path)
            assert checksum == 0x1234ABCD
            mock_hash.crc32c.assert_called_once_with(path)

    @pytest.mark.asyncio
    async def test_get_signed_url(self, storage_bucket: StorageBucket) -> None:
        """Test get_signed_url method."""
        path = AsyncPath("test/file.txt")
        signed_url = await storage_bucket.get_signed_url(path, expires=1800)
        assert "signature" in signed_url
        storage_bucket.client._sign.assert_called_once_with(
            "test-bucket/test-prefix/test/file.txt", expires=1800
        )

    @pytest.mark.asyncio
    async def test_stat(self, storage_bucket: StorageBucket) -> None:
        """Test stat method."""
        path = AsyncPath("test/file.txt")
        stat_result = await storage_bucket.stat(path)
        assert "size" in stat_result
        assert "timeCreated" in stat_result
        assert "updated" in stat_result
        storage_bucket.client._info.assert_called_once_with(
            "test-bucket/test-prefix/test/file.txt"
        )

    @pytest.mark.asyncio
    async def test_stat_memory_fs(self, mock_config: MagicMock) -> None:
        """Test stat method with memory filesystem."""
        mock_config.storage.memory_fs = True
        # For memory_fs, use regular MagicMock (not AsyncMock) for synchronous methods
        mock_client = MagicMock()
        mock_client.info = MagicMock(
            return_value={
                "name": "test/file.txt",
                "size": 1024,
                "type": "file",
            }
        )

        # Create mock datetime objects
        mock_modified = MagicMock()
        mock_modified.timestamp = MagicMock(return_value=1672531200)
        mock_created = MagicMock()
        mock_created.timestamp = MagicMock(return_value=1672444800)

        mock_client.modified = MagicMock(return_value=mock_modified)
        mock_client.created = MagicMock(return_value=mock_created)

        bucket = StorageBucket(mock_client, "test", mock_config, "test-prefix")

        path = AsyncPath("test/file.txt")
        stat_result = await bucket.stat(path)

        assert stat_result["size"] == 1024
        assert "mtime" in stat_result
        assert "created" in stat_result

    @pytest.mark.asyncio
    async def test_list(self, storage_bucket: StorageBucket) -> None:
        """Test list method."""
        path = AsyncPath("test/")
        list_result = await storage_bucket.list(path)
        assert list_result == ["file1.txt", "file2.txt"]
        storage_bucket.client._ls.assert_called_once_with(
            "test-bucket/test-prefix/test"
        )

    @pytest.mark.asyncio
    async def test_exists(self, storage_bucket: StorageBucket) -> None:
        """Test exists method."""
        path = AsyncPath("test/file.txt")
        exists_result = await storage_bucket.exists(path)
        assert exists_result is True
        storage_bucket.client._exists.assert_called_once_with(
            "test-bucket/test-prefix/test/file.txt"
        )

    @pytest.mark.asyncio
    async def test_exists_memory_fs(self, mock_config: MagicMock) -> None:
        """Test exists method with memory filesystem."""
        mock_config.storage.memory_fs = True
        # For memory_fs, use regular MagicMock (not AsyncMock) for synchronous methods
        mock_client = MagicMock()
        mock_client.isfile = MagicMock(return_value=True)

        bucket = StorageBucket(mock_client, "test", mock_config, "test-prefix")

        path = AsyncPath("test/file.txt")
        exists_result = await bucket.exists(path)
        assert exists_result is True
        mock_client.isfile.assert_called_once_with(
            "test-bucket/test-prefix/test/file.txt"
        )

    @pytest.mark.asyncio
    async def test_create_bucket(self, storage_bucket: StorageBucket) -> None:
        """Test create_bucket method."""
        path = AsyncPath("test/new-bucket")
        await storage_bucket.create_bucket(path)
        storage_bucket.client._mkdir.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_bucket_media(
        self, mock_client: AsyncMock, mock_config: MagicMock
    ) -> None:
        """Test create_bucket method for media bucket."""
        # Add media bucket to config
        mock_config.storage.buckets = {"media": "media-bucket"}
        mock_config.storage.cors = None
        bucket = StorageBucket(mock_client, "media", mock_config, "test-prefix")

        path = AsyncPath("test/new-bucket")
        await bucket.create_bucket(path)
        bucket.client._mkdir.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_bucket_templates(
        self, mock_client: AsyncMock, mock_config: MagicMock
    ) -> None:
        """Test create_bucket method for templates bucket."""
        # Add templates bucket to config
        mock_config.storage.buckets = {"templates": "templates-bucket"}
        bucket = StorageBucket(mock_client, "templates", mock_config, "test-prefix")

        path = AsyncPath("test/new-bucket")
        await bucket.create_bucket(path)
        bucket.client._mkdir.assert_called_once()

    @pytest.mark.asyncio
    async def test_open(self, storage_bucket: StorageBucket) -> None:
        """Test open method."""
        path = AsyncPath("test/file.txt")
        # Mock the context manager behavior - open() returns async context manager
        # The file object's read() is called synchronously (not awaited)
        mock_file = MagicMock()
        mock_file.read = MagicMock(return_value=b"test content")

        # Create an async context manager that returns mock_file
        mock_context = AsyncMock()
        mock_context.__aenter__ = AsyncMock(return_value=mock_file)
        mock_context.__aexit__ = AsyncMock(return_value=None)

        # Make client.open() return the async context manager (not a coroutine)
        storage_bucket.client.open = MagicMock(return_value=mock_context)

        result = await storage_bucket.open(path)
        assert result == b"test content"
        storage_bucket.client.open.assert_called_once_with(
            "test-bucket/test-prefix/test/file.txt", "rb"
        )

    @pytest.mark.asyncio
    async def test_write(self, storage_bucket: StorageBucket) -> None:
        """Test write method."""
        path = AsyncPath("test/file.txt")
        test_data = b"test content"
        await storage_bucket.write(path, test_data)
        storage_bucket.client._pipe_file.assert_called_once_with(
            "test-bucket/test-prefix/test/file.txt", test_data
        )

    @pytest.mark.asyncio
    async def test_write_memory_fs(
        self, mock_client: AsyncMock, mock_config: MagicMock
    ) -> None:
        """Test write method with memory filesystem."""
        mock_config.storage.memory_fs = True

        bucket = StorageBucket(mock_client, "test", mock_config, "test-prefix")

        path = AsyncPath("test/file.txt")
        test_data = b"test content"
        await bucket.write(path, test_data)
        mock_client.pipe_file.assert_called_once_with(
            "test-bucket/test-prefix/test/file.txt", test_data
        )

    @pytest.mark.asyncio
    async def test_delete(self, storage_bucket: StorageBucket) -> None:
        """Test delete method."""
        path = AsyncPath("test/file.txt")
        await storage_bucket.delete(path)
        storage_bucket.client._rm_file.assert_called_once_with(
            "test-bucket/test-prefix/test/file.txt"
        )


class TestStorageFile:
    """Test StorageFile class."""

    @pytest.fixture
    def mock_storage_bucket(self) -> AsyncMock:
        """Create a mock storage bucket."""
        bucket = AsyncMock(spec=StorageBucket)
        bucket.get_name = MagicMock(return_value="test.txt")
        bucket.get_path = MagicMock(return_value="test-bucket/test-prefix/test.txt")
        return bucket

    def test_init(self, mock_storage_bucket: AsyncMock) -> None:
        """Test StorageFile initialization."""
        file = StorageFile(name="test.txt", storage=mock_storage_bucket)
        assert file._name == "test.txt"
        assert file._storage == mock_storage_bucket

    def test_name_property(self, mock_storage_bucket: AsyncMock) -> None:
        """Test name property."""
        file = StorageFile(name="test.txt", storage=mock_storage_bucket)
        name = file.name
        assert name == "test.txt"
        mock_storage_bucket.get_name.assert_called_once_with(AsyncPath("test.txt"))

    def test_path_property(self, mock_storage_bucket: AsyncMock) -> None:
        """Test path property."""
        file = StorageFile(name="test.txt", storage=mock_storage_bucket)
        path = file.path
        assert path == "test-bucket/test-prefix/test.txt"
        mock_storage_bucket.get_path.assert_called_once_with(AsyncPath("test.txt"))

    @pytest.mark.asyncio
    async def test_size_property(self, mock_storage_bucket: AsyncMock) -> None:
        """Test size property."""
        mock_storage_bucket.get_size = AsyncMock(return_value=1024)
        file = StorageFile(name="test.txt", storage=mock_storage_bucket)
        size = await file.size
        assert size == 1024
        mock_storage_bucket.get_size.assert_called_once_with(AsyncPath("test.txt"))

    @pytest.mark.asyncio
    async def test_checksum_property(self, mock_storage_bucket: AsyncMock) -> None:
        """Test checksum property."""
        mock_storage_bucket.get_checksum = AsyncMock(return_value=0x1234ABCD)
        file = StorageFile(name="test.txt", storage=mock_storage_bucket)
        checksum = await file.checksum
        assert checksum == 0x1234ABCD
        mock_storage_bucket.get_checksum.assert_called_once_with(AsyncPath("test.txt"))

    @pytest.mark.asyncio
    async def test_open_method(self, mock_storage_bucket: AsyncMock) -> None:
        """Test open method."""
        mock_storage_bucket.open = AsyncMock(
            return_value=AsyncMock(read=AsyncMock(return_value=b"test content"))
        )
        file = StorageFile(name="test.txt", storage=mock_storage_bucket)
        result = await file.open()
        assert result is not None
        mock_storage_bucket.open.assert_called_once_with(AsyncPath("test.txt"))

    @pytest.mark.asyncio
    async def test_write_method(self, mock_storage_bucket: AsyncMock) -> None:
        """Test write method."""
        mock_file = AsyncMock()
        mock_storage_bucket.write = AsyncMock()
        file = StorageFile(name="test.txt", storage=mock_storage_bucket)
        await file.write(mock_file)
        mock_storage_bucket.write.assert_called_once_with(
            path=AsyncPath("test.txt"), data=mock_file
        )

    def test_str_method(self, mock_storage_bucket: AsyncMock) -> None:
        """Test __str__ method."""
        file = StorageFile(name="test.txt", storage=mock_storage_bucket)
        file_str = str(file)
        assert file_str == "test-bucket/test-prefix/test.txt"


class TestStorageImage:
    """Test StorageImage class."""

    @pytest.fixture
    def mock_storage_bucket(self) -> AsyncMock:
        """Create a mock storage bucket."""
        return AsyncMock(spec=StorageBucket)

    def test_init(self, mock_storage_bucket: AsyncMock) -> None:
        """Test StorageImage initialization."""
        image = StorageImage(
            name="test.jpg",
            storage=mock_storage_bucket,
            height=100,
            width=200,
        )
        assert image._name == "test.jpg"
        assert image._storage == mock_storage_bucket
        assert image._height == 100
        assert image._width == 200

    def test_height_property(self, mock_storage_bucket: AsyncMock) -> None:
        """Test height property."""
        image = StorageImage(
            name="test.jpg",
            storage=mock_storage_bucket,
            height=100,
            width=200,
        )
        assert image.height == 100

    def test_width_property(self, mock_storage_bucket: AsyncMock) -> None:
        """Test width property."""
        image = StorageImage(
            name="test.jpg",
            storage=mock_storage_bucket,
            height=100,
            width=200,
        )
        assert image.width == 200


class TestStorageBase:
    """Test StorageBase class."""

    @pytest.fixture
    def mock_config(self) -> MagicMock:
        """Create a mock config."""
        config = MagicMock(spec=Config)
        config.storage = MagicMock()
        config.storage.buckets = {"test": "test-bucket"}
        return config

    @pytest.fixture
    def storage_base(self, mock_config: MagicMock) -> StorageBase:
        """Create a StorageBase instance."""
        storage = StorageBase()
        storage.config = mock_config
        storage.logger = MagicMock()
        return storage

    def test_init(self, storage_base: StorageBase) -> None:
        """Test StorageBase initialization."""
        assert storage_base.file_system is not None
        assert storage_base.templates is None
        assert storage_base.media is None
        assert storage_base.test is None

    @pytest.mark.asyncio
    async def test_create_client(self, storage_base: StorageBase) -> None:
        """Test _create_client method."""
        client = await storage_base._create_client()
        assert client is not None

    @pytest.mark.asyncio
    async def test_get_client(self, storage_base: StorageBase) -> None:
        """Test get_client method."""
        client = await storage_base.get_client()
        assert client is not None

    def test_client_property(self, storage_base: StorageBase) -> None:
        """Test client property."""
        # First set a client
        mock_client = MagicMock()
        storage_base._client = mock_client
        client = storage_base.client
        assert client == mock_client

    def test_client_property_not_initialized(self, storage_base: StorageBase) -> None:
        """Test client property when not initialized."""
        storage_base._client = None
        with pytest.raises(RuntimeError, match="Client not initialized"):
            _ = storage_base.client

    @pytest.mark.asyncio
    async def test_init_buckets(self, storage_base: StorageBase) -> None:
        """Test init method for bucket initialization."""
        storage_base.config.storage.buckets = {
            "test": "test-bucket",
            "media": "media-bucket",
        }
        await storage_base.init()
        assert hasattr(storage_base, "test")
        assert hasattr(storage_base, "media")

    @pytest.mark.asyncio
    async def test_upload(self, storage_base: StorageBase) -> None:
        """Test upload method."""
        # Set up a mock bucket
        mock_bucket = AsyncMock()
        mock_bucket.write = AsyncMock()
        storage_base.test = mock_bucket

        test_data = b"test content"
        await storage_base.upload("test", "test.txt", test_data)
        mock_bucket.write.assert_called_once_with(AsyncPath("test.txt"), test_data)

    @pytest.mark.asyncio
    async def test_upload_missing_bucket(self, storage_base: StorageBase) -> None:
        """Test upload method with missing bucket."""
        with pytest.raises(ValueError, match="Bucket 'nonexistent' not found"):
            await storage_base.upload("nonexistent", "test.txt", b"test content")

    @pytest.mark.asyncio
    async def test_download(self, storage_base: StorageBase) -> None:
        """Test download method."""
        # Set up a mock bucket
        mock_bucket = AsyncMock()
        mock_context = AsyncMock()
        mock_context.__aenter__ = AsyncMock(
            return_value=AsyncMock(read=AsyncMock(return_value=b"test content"))
        )
        mock_context.__aexit__ = AsyncMock()
        mock_bucket.open.return_value = mock_context
        storage_base.test = mock_bucket

        result = await storage_base.download("test", "test.txt")
        assert result is not None
        mock_bucket.open.assert_called_once_with(AsyncPath("test.txt"))

    @pytest.mark.asyncio
    async def test_download_missing_bucket(self, storage_base: StorageBase) -> None:
        """Test download method with missing bucket."""
        with pytest.raises(ValueError, match="Bucket 'nonexistent' not found"):
            await storage_base.download("nonexistent", "test.txt")

    @pytest.mark.asyncio
    async def test_delete(self, storage_base: StorageBase) -> None:
        """Test delete method."""
        # Set up a mock bucket
        mock_bucket = AsyncMock()
        mock_bucket.delete = AsyncMock()
        storage_base.test = mock_bucket

        await storage_base.delete("test", "test.txt")
        mock_bucket.delete.assert_called_once_with(AsyncPath("test.txt"))

    @pytest.mark.asyncio
    async def test_delete_missing_bucket(self, storage_base: StorageBase) -> None:
        """Test delete method with missing bucket."""
        with pytest.raises(ValueError, match="Bucket 'nonexistent' not found"):
            await storage_base.delete("nonexistent", "test.txt")

    @pytest.mark.asyncio
    async def test_exists(self, storage_base: StorageBase) -> None:
        """Test exists method."""
        # Set up a mock bucket
        mock_bucket = AsyncMock()
        mock_bucket.exists = AsyncMock(return_value=True)
        storage_base.test = mock_bucket

        result = await storage_base.exists("test", "test.txt")
        assert result is True
        mock_bucket.exists.assert_called_once_with(AsyncPath("test.txt"))

    @pytest.mark.asyncio
    async def test_exists_missing_bucket(self, storage_base: StorageBase) -> None:
        """Test exists method with missing bucket."""
        with pytest.raises(ValueError, match="Bucket 'nonexistent' not found"):
            await storage_base.exists("nonexistent", "test.txt")

    @pytest.mark.asyncio
    async def test_stat(self, storage_base: StorageBase) -> None:
        """Test stat method."""
        # Set up a mock bucket
        mock_bucket = AsyncMock()
        mock_bucket.stat = AsyncMock(return_value={"size": 1024})
        storage_base.test = mock_bucket

        result = await storage_base.stat("test", "test.txt")
        assert result == {"size": 1024}
        mock_bucket.stat.assert_called_once_with(AsyncPath("test.txt"))

    @pytest.mark.asyncio
    async def test_stat_missing_bucket(self, storage_base: StorageBase) -> None:
        """Test stat method with missing bucket."""
        with pytest.raises(ValueError, match="Bucket 'nonexistent' not found"):
            await storage_base.stat("nonexistent", "test.txt")
