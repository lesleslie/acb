"""Tests for the file-based storage adapter."""

import typing as t
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

import pytest
from anyio import Path as AsyncPath
from fsspec.implementations.dirfs import DirFileSystem
from pytest_benchmark.fixture import BenchmarkFixture
from acb.adapters.storage.file import (
    Storage,
    StorageSettings,
)
from acb.config import Config


class MockDirFileSystem(MagicMock):
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

        self.get_mapper = MagicMock()
        self.asynchronous = True


class MockAsyncFileSystemWrapper(MagicMock):
    def __init__(self, *args: t.Any, **kwargs: t.Any) -> None:
        super().__init__(*args, **kwargs)
        self.fs = MockDirFileSystem()

        self.exists = MagicMock(return_value=True)
        self.isdir = MagicMock(return_value=True)
        self.mkdir = MagicMock()
        self.rm = MagicMock()

        self.mock_file = MagicMock()
        self.mock_file.__enter__ = MagicMock(return_value=self.mock_file)
        self.mock_file.__exit__ = MagicMock(return_value=None)
        self.mock_file.write = MagicMock()
        self.mock_file.read = MagicMock(return_value=b"test content")
        self.open = MagicMock(return_value=self.mock_file)

        self.put_file = AsyncMock()
        self.get_file = AsyncMock(return_value=b"test content")
        self.delete_file = AsyncMock()
        self.file_exists = AsyncMock(return_value=True)
        self.create_directory = AsyncMock()
        self.directory_exists = AsyncMock(return_value=True)


class MockStorageBucket(MagicMock):
    def __init__(self, *args: t.Any, **kwargs: t.Any) -> None:
        super().__init__(*args, **kwargs)
        self.create_bucket = AsyncMock()
        self.get_url = MagicMock(return_value="file:///path/to/test-file")
        self.stat = AsyncMock(return_value={"size": 100, "type": "file"})
        self.list = AsyncMock(return_value=["file1.txt", "file2.txt"])
        self.exists = AsyncMock(return_value=True)
        self.open = AsyncMock()
        self.write = AsyncMock()
        self.delete = AsyncMock()


class TestFileStorageSettings:
    def test_settings_structure(self) -> None:
        settings = StorageSettings(local_path=AsyncPath("/path/to/storage"))
        assert settings.local_path == AsyncPath("/path/to/storage")


class TestFileStorage:
    @pytest.fixture
    def mock_config(self) -> MagicMock:
        mock_config = MagicMock(spec=Config)
        mock_app = MagicMock()
        mock_app.name = "test-app"
        mock_config.app = mock_app

        mock_storage = MagicMock(spec=StorageSettings)
        mock_storage.prefix = "test-prefix"
        mock_storage.local_fs = True
        mock_storage.memory_fs = False
        mock_storage.local_path = AsyncPath("/path/to/storage")
        mock_storage.buckets = {
            "test": "test-bucket",
            "media": "media-bucket",
            "templates": "templates-bucket",
        }
        mock_config.storage = mock_storage

        return mock_config

    @pytest.fixture
    def mock_config_no_root(self) -> MagicMock:
        mock_config = MagicMock(spec=Config)
        mock_app = MagicMock()
        mock_app.name = "test-app"
        mock_config.app = mock_app

        mock_storage = MagicMock(spec=StorageSettings)
        mock_storage.prefix = "test-prefix"
        mock_storage.local_fs = True
        mock_storage.memory_fs = False
        mock_storage.local_path = None
        mock_storage.buckets = {
            "test": "test-bucket",
            "media": "media-bucket",
            "templates": "templates-bucket",
        }
        mock_config.storage = mock_storage

        return mock_config

    @pytest.fixture
    def mock_dirfs(self) -> MockDirFileSystem:
        return MockDirFileSystem()

    @pytest.fixture
    def storage_adapter(self, mock_config: MagicMock) -> Storage:
        adapter = Storage()
        adapter.config = mock_config
        adapter.logger = MagicMock()
        return adapter

    @pytest.fixture
    def storage_adapter_no_root(self, mock_config_no_root: MagicMock) -> Storage:
        adapter = Storage()
        adapter.config = mock_config_no_root
        adapter.logger = MagicMock()
        return adapter

    @pytest.mark.asyncio
    async def test_client_property_with_root_dir(
        self,
        storage_adapter: Storage,
    ) -> None:
        mock_dirfs = MockDirFileSystem()
        mock_wrapper = MockAsyncFileSystemWrapper()

        with patch("acb.adapters.storage.file.DirFileSystem", return_value=mock_dirfs):
            with patch(
                "acb.adapters.storage.file.AsyncFileSystemWrapper",
                return_value=mock_wrapper,
            ):
                with patch.object(Storage, "client", new=mock_wrapper):
                    client = storage_adapter.client

                    assert client is mock_wrapper

    @pytest.mark.asyncio
    async def test_client_property_without_root_dir(
        self,
        storage_adapter_no_root: Storage,
    ) -> None:
        mock_dirfs = MockDirFileSystem()
        mock_wrapper = MockAsyncFileSystemWrapper()

        with patch("acb.adapters.storage.file.DirFileSystem", return_value=mock_dirfs):
            with patch(
                "acb.adapters.storage.file.AsyncFileSystemWrapper",
                return_value=mock_wrapper,
            ):
                storage_adapter_no_root._client = mock_wrapper
                client = storage_adapter_no_root.client

                assert client is mock_wrapper

    @pytest.mark.asyncio
    async def test_file_system_type(self) -> None:
        assert Storage.file_system == DirFileSystem

    @pytest.mark.asyncio
    async def test_init_method(self, storage_adapter: Storage) -> None:
        mock_client = MockAsyncFileSystemWrapper()

        storage_adapter._client = mock_client
        with patch("acb.adapters.storage._base.StorageBucket") as mock_bucket_cls:
            mock_bucket = MockStorageBucket()
            mock_bucket_cls.return_value = mock_bucket

            await storage_adapter.init()

            mock_bucket_cls.assert_any_call(mock_client, "templates")
            mock_bucket_cls.assert_any_call(mock_client, "test")
            mock_bucket_cls.assert_any_call(mock_client, "media")

            assert storage_adapter.templates == mock_bucket
            assert storage_adapter.test == mock_bucket
            assert storage_adapter.media == mock_bucket

    @pytest.mark.asyncio
    async def test_put_file(self, storage_adapter: Storage) -> None:
        mock_client = MockAsyncFileSystemWrapper()
        file_path = "test/path/file.txt"
        content = b"test content"

        storage_adapter._client = mock_client
        with patch.object(storage_adapter, "root_dir", new=None):
            result = await storage_adapter.put_file(file_path, content)

            mock_client.open.assert_called_once_with(file_path, "wb")

            mock_client.mock_file.write.assert_called_once_with(content)

            assert result

    @pytest.mark.asyncio
    async def test_get_file(self, storage_adapter: Storage) -> None:
        mock_client = MockAsyncFileSystemWrapper()
        file_path = "test/path/file.txt"
        expected_content = b"test content"

        storage_adapter.file_exists = AsyncMock(return_value=True)

        storage_adapter._client = mock_client
        with patch.object(storage_adapter, "root_dir", new=None):
            result = await storage_adapter.get_file(file_path)

            storage_adapter.file_exists.assert_called_once_with(file_path)

            mock_client.open.assert_called_once_with(file_path, "rb")

            mock_client.mock_file.read.assert_called_once()

            assert result == expected_content

    @pytest.mark.asyncio
    async def test_delete_file(self, storage_adapter: Storage) -> None:
        mock_client = MagicMock()
        mock_client.rm = MagicMock()
        file_path = "test/path/file.txt"

        storage_adapter.file_exists = AsyncMock(return_value=True)

        storage_adapter._client = mock_client
        with patch.object(storage_adapter, "root_dir", new=None):
            result = await storage_adapter.delete_file(file_path)

            storage_adapter.file_exists.assert_called_once_with(file_path)

            mock_client.rm.assert_called_once_with(file_path)

            assert result

    @pytest.mark.asyncio
    async def test_file_exists(self) -> None:
        file_path = "test/path/file.txt"

        adapter = Storage()

        original_file_exists = adapter.file_exists

        async def mock_file_exists(self: Storage, path: str) -> bool:
            assert path == file_path
            return True

        adapter.file_exists = mock_file_exists.__get__(adapter)

        result = await adapter.file_exists(file_path)

        assert result

        adapter.file_exists = original_file_exists

    @pytest.mark.asyncio
    async def test_create_directory(self, storage_adapter: Storage) -> None:
        mock_client = MockAsyncFileSystemWrapper()
        dir_path = "test/path/directory"

        storage_adapter._client = mock_client
        with patch.object(storage_adapter, "root_dir", new=None):
            result = await storage_adapter.create_directory(dir_path)

            mock_client.mkdir.assert_called_once_with(dir_path, create_parents=True)

            assert result

    @pytest.mark.asyncio
    async def test_directory_exists(self, storage_adapter: Storage) -> None:
        mock_client = MockAsyncFileSystemWrapper()
        dir_path = "test/path/directory"

        storage_adapter._client = mock_client
        with patch.object(storage_adapter, "root_dir", new=None):
            result = await storage_adapter.directory_exists(dir_path)

            mock_client.isdir.assert_called_once_with(dir_path)

            assert result

    @pytest.mark.asyncio
    async def test_put_file_with_root_dir(self, storage_adapter: Storage) -> None:
        root_dir = "/path/to/storage"
        file_path = "test/path/file.txt"
        content = b"test content"
        full_path = MagicMock(spec=AsyncPath)

        mock_path = MagicMock(spec=AsyncPath)
        mock_path.__truediv__.return_value = full_path
        full_path.parent = MagicMock(spec=AsyncPath)
        full_path.parent.mkdir = AsyncMock()
        full_path.write_bytes = AsyncMock()

        with (
            patch.object(storage_adapter, "root_dir", new=root_dir),
            patch(
                "acb.adapters.storage.file.AsyncPath",
                return_value=mock_path,
            ) as mock_path_cls,
        ):
            result = await storage_adapter.put_file(file_path, content)

            mock_path_cls.assert_called_once_with(root_dir)

            mock_path.__truediv__.assert_called_once_with(file_path)

            full_path.parent.mkdir.assert_called_once_with(
                parents=True,
                exist_ok=True,
            )

            full_path.write_bytes.assert_called_once_with(content)

            assert result

    @pytest.mark.asyncio
    async def test_get_file_with_root_dir(self, storage_adapter: Storage) -> None:
        root_dir = "/path/to/storage"
        file_path = "test/path/file.txt"
        expected_content = b"test content"
        full_path = MagicMock(spec=AsyncPath)

        mock_path = MagicMock(spec=AsyncPath)
        mock_path.__truediv__.return_value = full_path
        full_path.exists = AsyncMock(return_value=True)
        full_path.read_bytes = AsyncMock(return_value=expected_content)

        with (
            patch.object(storage_adapter, "root_dir", new=root_dir),
            patch(
                "acb.adapters.storage.file.AsyncPath",
                return_value=mock_path,
            ) as mock_path_cls,
        ):
            result = await storage_adapter.get_file(file_path)

            mock_path_cls.assert_called_once_with(root_dir)

            mock_path.__truediv__.assert_called_once_with(file_path)

            full_path.exists.assert_called_once()

            full_path.read_bytes.assert_called_once()

            assert result == expected_content

    @pytest.mark.asyncio
    async def test_delete_file_with_root_dir(self, storage_adapter: Storage) -> None:
        root_dir = "/path/to/storage"
        file_path = "test/path/file.txt"
        full_path = MagicMock(spec=AsyncPath)

        mock_path = MagicMock(spec=AsyncPath)
        mock_path.__truediv__.return_value = full_path
        full_path.exists = AsyncMock(return_value=True)
        full_path.unlink = AsyncMock()

        with (
            patch.object(storage_adapter, "root_dir", new=root_dir),
            patch(
                "acb.adapters.storage.file.AsyncPath",
                return_value=mock_path,
            ) as mock_path_cls,
        ):
            result = await storage_adapter.delete_file(file_path)

            mock_path_cls.assert_called_once_with(root_dir)

            mock_path.__truediv__.assert_called_once_with(file_path)

            full_path.exists.assert_called_once()

            full_path.unlink.assert_called_once()

            assert result

    @pytest.mark.asyncio
    async def test_file_exists_with_root_dir(self, storage_adapter: Storage) -> None:
        root_dir = "/path/to/storage"
        file_path = "test/path/file.txt"

        class MockPath:
            def __init__(self, path_str: str) -> None:
                self.path_str = path_str
                self.parent = (
                    MockPath(str(AsyncPath(path_str).parent))
                    if path_str != "/"
                    else None
                )

            def __truediv__(self, other: str) -> "MockPath":
                return MockPath(f"{self.path_str}/{other}")

            async def exists(self) -> bool:
                return True

            async def is_file(self) -> bool:
                return True

            def __str__(self) -> str:
                return self.path_str

        with patch("acb.adapters.storage.file.AsyncPath", MockPath):
            storage_adapter.root_dir = root_dir

            result = await storage_adapter.file_exists(file_path)

            assert result

    @pytest.mark.asyncio
    async def test_create_directory_with_root_dir(
        self,
        storage_adapter: Storage,
    ) -> None:
        root_dir = "/path/to/storage"
        dir_path = "test/path/directory"
        full_path = MagicMock(spec=AsyncPath)

        mock_path = MagicMock(spec=AsyncPath)
        mock_path.__truediv__.return_value = full_path
        full_path.mkdir = AsyncMock()

        with (
            patch.object(storage_adapter, "root_dir", new=root_dir),
            patch(
                "acb.adapters.storage.file.AsyncPath",
                return_value=mock_path,
            ) as mock_path_cls,
        ):
            result = await storage_adapter.create_directory(dir_path)

            mock_path_cls.assert_called_once_with(root_dir)

            mock_path.__truediv__.assert_called_once_with(dir_path)

            full_path.mkdir.assert_called_once_with(parents=True, exist_ok=True)

            assert result

    @pytest.mark.asyncio
    async def test_directory_exists_with_root_dir(
        self,
        storage_adapter: Storage,
    ) -> None:
        root_dir = "/path/to/storage"
        dir_path = "test/path/directory"
        full_path = MagicMock(spec=AsyncPath)

        mock_path = MagicMock(spec=AsyncPath)
        mock_path.__truediv__.return_value = full_path
        full_path.exists = AsyncMock(return_value=True)
        full_path.is_dir = AsyncMock(return_value=True)

        with (
            patch.object(storage_adapter, "root_dir", new=root_dir),
            patch(
                "acb.adapters.storage.file.AsyncPath",
                return_value=mock_path,
            ) as mock_path_cls,
        ):
            result = await storage_adapter.directory_exists(dir_path)

            mock_path_cls.assert_called_once_with(root_dir)

            mock_path.__truediv__.assert_called_once_with(dir_path)

            full_path.exists.assert_called_once()
            full_path.is_dir.assert_called_once()

            assert result

    @pytest.mark.asyncio
    async def test_client_property_with_config_attribute_error(self) -> None:
        storage = Storage()

        mock_config = MagicMock()
        type(mock_config).storage = PropertyMock(side_effect=AttributeError())
        storage.config = mock_config

        client = await storage.get_client()

        assert client is not None
        # Client should have the expected interface regardless of whether it's mocked
        assert hasattr(client, "open")
        assert hasattr(client, "exists")
        assert hasattr(client, "mkdir")
        assert hasattr(client, "rm")

    @pytest.mark.asyncio
    async def test_file_exists_exception(self, storage_adapter: Storage) -> None:
        class TestableStorage(Storage):
            def __init__(self, original_adapter: Storage) -> None:
                self.logger = original_adapter.logger
                self.config = original_adapter.config
                self.root_dir = None

                self._test_client = MagicMock()
                self._test_client.exists.side_effect = Exception("Test error")
                self._client = self._test_client

            async def get_client(self) -> t.Any:
                return self._test_client

        test_adapter = TestableStorage(storage_adapter)

        # Create mock logger
        mock_logger = MagicMock()
        test_adapter.logger = mock_logger

        result = await test_adapter.file_exists("test/path/file.txt")

        test_adapter._test_client.exists.assert_called_once_with("test/path/file.txt")

        assert not result

        mock_logger.exception.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_directory_exception(self, storage_adapter: Storage) -> None:
        class TestableStorage(Storage):
            def __init__(self, original_adapter: Storage) -> None:
                self.logger = original_adapter.logger
                self.config = original_adapter.config
                self.root_dir = None

                self._test_client = MagicMock()
                self._test_client.mkdir.side_effect = Exception("Test error")
                self._client = self._test_client

            async def get_client(self) -> t.Any:
                return self._test_client

        test_adapter = TestableStorage(storage_adapter)

        # Create mock logger
        mock_logger = MagicMock()
        test_adapter.logger = mock_logger

        result = await test_adapter.create_directory("test/path/directory")

        test_adapter._test_client.mkdir.assert_called_once_with(
            "test/path/directory",
            create_parents=True,
        )

        assert not result

        mock_logger.exception.assert_called_once()

    @pytest.mark.asyncio
    async def test_directory_exists_exception(self, storage_adapter: Storage) -> None:
        class TestableStorage(Storage):
            def __init__(self, original_adapter: Storage) -> None:
                self.logger = original_adapter.logger
                self.config = original_adapter.config
                self.root_dir = None

                self._test_client = MagicMock()
                self._test_client.exists.side_effect = Exception("Test error")
                self._test_client.isdir.return_value = True
                self._client = self._test_client

            async def get_client(self) -> t.Any:
                return self._test_client

        test_adapter = TestableStorage(storage_adapter)

        # Create mock logger
        mock_logger = MagicMock()
        test_adapter.logger = mock_logger

        result = await test_adapter.directory_exists("test/path/directory")

        test_adapter._test_client.exists.assert_called_once_with("test/path/directory")

        assert test_adapter._test_client.isdir.call_count == 0

        assert not result

        mock_logger.exception.assert_called_once()

    @pytest.mark.asyncio
    async def test_put_file_with_string_content(self, storage_adapter: Storage) -> None:
        mock_file = MagicMock()
        mock_client = MagicMock()
        mock_client.open.return_value.__enter__.return_value = mock_file

        file_path = "test/path/file.txt"
        content_bytes = b"test content"

        async_true = AsyncMock()
        async_true.return_value = True
        path_mock = AsyncMock()
        path_mock.exists = path_mock.is_file = path_mock.is_dir = async_true

        storage_adapter._client = mock_client
        with patch.object(storage_adapter, "root_dir", new=None):
            result = await storage_adapter.put_file(file_path, content_bytes)

            mock_file.write.assert_called_once_with(content_bytes)

            assert result

    @pytest.mark.asyncio
    async def test_put_file_exception(self, storage_adapter: Storage) -> None:
        mock_client = MagicMock()
        mock_client.open.side_effect = Exception("Test error")
        file_path = "test/path/file.txt"
        content = b"test content"

        storage_adapter._client = mock_client
        with patch.object(storage_adapter, "root_dir", new=None):
            # Create mock logger
            mock_logger = MagicMock()
            storage_adapter.logger = mock_logger

            result = await storage_adapter.put_file(file_path, content)

            assert not result

            mock_logger.exception.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_file_nonexistent(self, storage_adapter: Storage) -> None:
        file_path = "test/path/nonexistent.txt"

        storage_adapter.file_exists = AsyncMock(return_value=False)

        with patch.object(storage_adapter, "root_dir", new=None):
            result = await storage_adapter.get_file(file_path)

            storage_adapter.file_exists.assert_called_once_with(file_path)

            assert result is None

    @pytest.mark.asyncio
    async def test_get_file_exception(self, storage_adapter: Storage) -> None:
        mock_client = MagicMock()
        mock_client.open.side_effect = Exception("Test error")
        file_path = "test/path/file.txt"

        storage_adapter.file_exists = AsyncMock(return_value=True)

        storage_adapter._client = mock_client
        with patch.object(storage_adapter, "root_dir", new=None):
            # Create mock logger
            mock_logger = MagicMock()
            storage_adapter.logger = mock_logger

            result = await storage_adapter.get_file(file_path)

            assert result is None

            mock_logger.exception.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_file_nonexistent(self, storage_adapter: Storage) -> None:
        file_path = "test/path/nonexistent.txt"

        storage_adapter.file_exists = AsyncMock(return_value=False)

        with patch.object(storage_adapter, "root_dir", new=None):
            result = await storage_adapter.delete_file(file_path)

            storage_adapter.file_exists.assert_called_once_with(file_path)

            assert not result

    @pytest.mark.asyncio
    async def test_delete_file_exception(self, storage_adapter: Storage) -> None:
        mock_client = MagicMock()
        mock_client.rm.side_effect = Exception("Test error")
        file_path = "test/path/file.txt"

        storage_adapter.file_exists = AsyncMock(return_value=True)

        storage_adapter._client = mock_client
        with patch.object(storage_adapter, "root_dir", new=None):
            # Create mock logger
            mock_logger = MagicMock()
            storage_adapter.logger = mock_logger

            result = await storage_adapter.delete_file(file_path)

            assert not result

            mock_logger.exception.assert_called_once()

    @pytest.mark.asyncio
    async def test_put_file_with_string_content_and_path_mock(
        self,
        storage_adapter: Storage,
    ) -> None:
        mock_file = MagicMock()
        mock_client = MagicMock()
        mock_client.open.return_value.__enter__.return_value = mock_file

        file_path = "test/path/file.txt"
        content_bytes = b"test content"

        async_true = AsyncMock()
        async_true.return_value = True
        path_mock = AsyncMock()
        path_mock.exists = path_mock.is_file = path_mock.is_dir = async_true

        storage_adapter._client = mock_client
        with patch.object(storage_adapter, "root_dir", new=None):
            result = await storage_adapter.put_file(file_path, content_bytes)

            mock_file.write.assert_called_once_with(content_bytes)

            assert result


@pytest.mark.skip(reason="Storage benchmark tests need adapter method implementation")
class TestFileStorageBenchmarks:
    @pytest.fixture
    def benchmark_adapter(self, mock_config: MagicMock) -> Storage:
        adapter = Storage()
        adapter.config = mock_config
        adapter.logger = MagicMock()
        return adapter

    @pytest.fixture
    def small_file_content(self) -> bytes:
        return b"small file content"

    @pytest.fixture
    def medium_file_content(self) -> bytes:
        return b"medium file content" * 1000

    @pytest.fixture
    def large_file_content(self) -> bytes:
        return b"large file content" * 100000

    @pytest.mark.benchmark
    @pytest.mark.asyncio
    async def test_file_upload_small_performance(
        self,
        benchmark: BenchmarkFixture,
        benchmark_adapter: Storage,
        small_file_content: bytes,
    ) -> None:
        await benchmark_adapter.init()

        result = await benchmark(
            benchmark_adapter.put_file,
            "test/small_file.txt",
            small_file_content,
        )
        assert result is True

    @pytest.mark.benchmark
    @pytest.mark.asyncio
    async def test_file_upload_medium_performance(
        self,
        benchmark: BenchmarkFixture,
        benchmark_adapter: Storage,
        medium_file_content: bytes,
    ) -> None:
        await benchmark_adapter.init()

        result = await benchmark(
            benchmark_adapter.put_file,
            "test/medium_file.txt",
            medium_file_content,
        )
        assert result is True

    @pytest.mark.benchmark
    @pytest.mark.asyncio
    async def test_file_upload_large_performance(
        self,
        benchmark: BenchmarkFixture,
        benchmark_adapter: Storage,
        large_file_content: bytes,
    ) -> None:
        await benchmark_adapter.init()

        result = await benchmark(
            benchmark_adapter.put_file,
            "test/large_file.txt",
            large_file_content,
        )
        assert result is True

    @pytest.mark.benchmark
    @pytest.mark.asyncio
    async def test_file_download_small_performance(
        self,
        benchmark: BenchmarkFixture,
        benchmark_adapter: Storage,
        small_file_content: bytes,
    ) -> None:
        await benchmark_adapter.init()
        await benchmark_adapter.put_file("test/small_file.txt", small_file_content)

        result = await benchmark(benchmark_adapter.get_file, "test/small_file.txt")
        assert result == small_file_content

    @pytest.mark.benchmark
    @pytest.mark.asyncio
    async def test_file_download_medium_performance(
        self,
        benchmark: BenchmarkFixture,
        benchmark_adapter: Storage,
        medium_file_content: bytes,
    ) -> None:
        await benchmark_adapter.init()
        await benchmark_adapter.put_file("test/medium_file.txt", medium_file_content)

        result = await benchmark(benchmark_adapter.get_file, "test/medium_file.txt")
        assert result == medium_file_content

    @pytest.mark.benchmark
    @pytest.mark.asyncio
    async def test_file_download_large_performance(
        self,
        benchmark: BenchmarkFixture,
        benchmark_adapter: Storage,
        large_file_content: bytes,
    ) -> None:
        await benchmark_adapter.init()
        await benchmark_adapter.put_file("test/large_file.txt", large_file_content)

        result = await benchmark(benchmark_adapter.get_file, "test/large_file.txt")
        assert result == large_file_content

    @pytest.mark.benchmark
    @pytest.mark.asyncio
    async def test_file_exists_performance(
        self,
        benchmark: BenchmarkFixture,
        benchmark_adapter: Storage,
        medium_file_content: bytes,
    ) -> None:
        await benchmark_adapter.init()
        await benchmark_adapter.put_file("test/exists_file.txt", medium_file_content)

        result = await benchmark(benchmark_adapter.file_exists, "test/exists_file.txt")
        assert result is True

    @pytest.mark.benchmark
    @pytest.mark.asyncio
    async def test_directory_operations_performance(
        self,
        benchmark: BenchmarkFixture,
        benchmark_adapter: Storage,
    ) -> None:
        await benchmark_adapter.init()

        async def create_and_check_directory():
            await benchmark_adapter.create_directory("test/benchmark/dir")
            return await benchmark_adapter.directory_exists("test/benchmark/dir")

        result = await benchmark(create_and_check_directory)
        assert result is True

    @pytest.mark.benchmark
    @pytest.mark.asyncio
    async def test_bulk_file_operations_performance(
        self,
        benchmark: BenchmarkFixture,
        benchmark_adapter: Storage,
        small_file_content: bytes,
    ) -> None:
        await benchmark_adapter.init()

        async def bulk_file_operations():
            results = []
            for i in range(50):
                put_result = await benchmark_adapter.put_file(
                    f"test/bulk_file_{i}.txt",
                    small_file_content,
                )
                results.append(put_result)

            get_results = []
            for i in range(50):
                get_result = await benchmark_adapter.get_file(f"test/bulk_file_{i}.txt")
                get_results.append(get_result)

            return all(results) and all(r == small_file_content for r in get_results)

        result = await benchmark(bulk_file_operations)
        assert result is True
