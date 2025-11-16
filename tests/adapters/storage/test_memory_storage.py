"""Tests for Memory Storage adapter."""

from unittest.mock import MagicMock, patch

import pytest
from anyio import Path as AsyncPath

from acb.adapters.storage.memory import Storage, StorageSettings


class TestMemoryStorageSettings:
    """Test Memory Storage settings."""

    def test_init_with_defaults(self, mock_config):
        """Test settings initialization with default values."""
        from acb.config import Config
        from acb.depends import depends

        # Set up mock_config with app.name
        mock_config.app = MagicMock()
        mock_config.app.name = "acb"

        # Register mock_config in DI container
        depends.set(Config, mock_config)

        try:
            settings = StorageSettings()

            # Test inherited defaults from StorageBaseSettings
            assert settings.prefix == "acb"  # From config.app.name
            assert settings.user_project == "acb"
            assert settings.buckets == {"test": "test-bucket"}
            assert settings.local_fs is False
            assert settings.memory_fs is False
        finally:
            # Restore original Config instance
            depends.set(Config, Config())

    def test_init_with_custom_values(self, mock_config):
        """Test settings initialization with custom values."""
        from acb.config import Config
        from acb.depends import depends

        # Set up mock_config with app.name
        mock_config.app = MagicMock()
        mock_config.app.name = "acb"

        # Register mock_config in DI container
        depends.set(Config, mock_config)

        try:
            custom_buckets = {
                "media": "my-media-bucket",
                "templates": "my-templates-bucket",
                "test": "my-test-bucket",
            }

            settings = StorageSettings(
                prefix="my-app",
                user_project="my-project",
                buckets=custom_buckets,
                local_path=AsyncPath("/custom/storage"),
            )

            assert settings.prefix == "my-app"
            assert settings.user_project == "my-project"
            assert settings.buckets == custom_buckets
            assert settings.local_path == AsyncPath("/custom/storage")
        finally:
            # Restore original Config instance
            depends.set(Config, Config())


class TestMemoryStorage:
    """Test Memory Storage adapter."""

    @pytest.fixture
    def mock_storage_settings(self, mock_config):
        """Mock storage settings for testing."""
        from acb.config import Config
        from acb.depends import depends

        # Set up mock_config with app.name
        mock_config.app = MagicMock()
        mock_config.app.name = "acb"

        # Register mock_config in DI container
        depends.set(Config, mock_config)

        mock_config.storage = StorageSettings(
            prefix="test-app",
            user_project="test-project",
            local_path=AsyncPath("/tmp/test-storage"),
            buckets={
                "test": "test-bucket",
                "media": "media-bucket",
                "templates": "templates-bucket",
            },
        )
        return mock_config

    def test_init_defaults(self, mock_storage_settings):
        """Test adapter initialization with default values."""
        storage = Storage()
        storage.config = mock_storage_settings

        # Check that file_system is set to MemoryFileSystem
        from fsspec.implementations.memory import MemoryFileSystem

        assert storage.file_system == MemoryFileSystem
        assert storage._client is None

    async def test_init_method(self, mock_storage_settings):
        """Test initialization method."""
        storage = Storage()
        storage.config = mock_storage_settings
        storage.logger = MagicMock()

        # Mock get_client to avoid actual client creation for this test
        with (
            patch.object(storage, "get_client", return_value=MagicMock()),
            patch("acb.adapters.storage._base.StorageBucket") as mock_bucket_class,
        ):
            mock_bucket = MagicMock()
            mock_bucket_class.return_value = mock_bucket

            await storage.init()

            # Check that memory storage internal structures are initialized
            assert storage._initialized is True
            assert hasattr(storage, "_files")
            assert hasattr(storage, "_directories")
            assert isinstance(storage._files, dict)
            assert isinstance(storage._directories, set)

            # Check that bucket attributes were created via super().init()
            assert hasattr(storage, "test")
            assert hasattr(storage, "media")
            assert hasattr(storage, "templates")

    async def test_put_file_success(self, mock_storage_settings):
        """Test putting file successfully."""
        storage = Storage()
        storage.config = mock_storage_settings

        content = b"test file content"

        result = await storage.put_file("test/file.txt", content)

        assert result is True
        assert storage._files["test/file.txt"] == content
        assert "test" in storage._directories

    async def test_put_file_root_path(self, mock_storage_settings):
        """Test putting file with root path (no directory)."""
        storage = Storage()
        storage.config = mock_storage_settings

        content = b"root file content"

        result = await storage.put_file("rootfile.txt", content)

        assert result is True
        assert storage._files["rootfile.txt"] == content
        # No directory should be added for root files

    async def test_put_file_without_init(self, mock_storage_settings):
        """Test putting file before init (should create internal structures)."""
        storage = Storage()
        storage.config = mock_storage_settings

        content = b"test content"

        # Files dict doesn't exist yet
        assert not hasattr(storage, "_files")
        assert not hasattr(storage, "_directories")

        result = await storage.put_file("test/file.txt", content)

        assert result is True
        assert hasattr(storage, "_files")
        assert hasattr(storage, "_directories")
        assert storage._files["test/file.txt"] == content

    async def test_put_file_nested_directory(self, mock_storage_settings):
        """Test putting file in nested directory structure."""
        storage = Storage()
        storage.config = mock_storage_settings

        content = b"nested file content"

        result = await storage.put_file("path/to/nested/file.txt", content)

        assert result is True
        assert storage._files["path/to/nested/file.txt"] == content
        assert "path/to/nested" in storage._directories

    async def test_get_file_success(self, mock_storage_settings):
        """Test getting file successfully."""
        storage = Storage()
        storage.config = mock_storage_settings

        content = b"test file content"
        await storage.put_file("test/file.txt", content)

        result = await storage.get_file("test/file.txt")

        assert result == content

    async def test_get_file_not_found(self, mock_storage_settings):
        """Test getting file that doesn't exist."""
        storage = Storage()
        storage.config = mock_storage_settings

        result = await storage.get_file("nonexistent/file.txt")

        assert result is None

    async def test_get_file_without_init(self, mock_storage_settings):
        """Test getting file before init (should create internal structures)."""
        storage = Storage()
        storage.config = mock_storage_settings

        # Files dict doesn't exist yet
        assert not hasattr(storage, "_files")

        result = await storage.get_file("nonexistent.txt")

        assert result is None
        assert hasattr(storage, "_files")
        assert isinstance(storage._files, dict)

    async def test_delete_file_success(self, mock_storage_settings):
        """Test deleting file successfully."""
        storage = Storage()
        storage.config = mock_storage_settings

        content = b"test file content"
        await storage.put_file("test/file.txt", content)

        # Verify file exists
        assert await storage.file_exists("test/file.txt") is True

        result = await storage.delete_file("test/file.txt")

        assert result is True
        assert await storage.file_exists("test/file.txt") is False

    async def test_delete_file_not_found(self, mock_storage_settings):
        """Test deleting file that doesn't exist."""
        storage = Storage()
        storage.config = mock_storage_settings

        result = await storage.delete_file("nonexistent/file.txt")

        assert result is False

    async def test_delete_file_without_init(self, mock_storage_settings):
        """Test deleting file before init (should create internal structures)."""
        storage = Storage()
        storage.config = mock_storage_settings

        # Files dict doesn't exist yet
        assert not hasattr(storage, "_files")

        result = await storage.delete_file("nonexistent.txt")

        assert result is False
        assert hasattr(storage, "_files")
        assert isinstance(storage._files, dict)

    async def test_file_exists_true(self, mock_storage_settings):
        """Test file_exists returns True for existing file."""
        storage = Storage()
        storage.config = mock_storage_settings

        content = b"test file content"
        await storage.put_file("test/file.txt", content)

        result = await storage.file_exists("test/file.txt")

        assert result is True

    async def test_file_exists_false(self, mock_storage_settings):
        """Test file_exists returns False for non-existing file."""
        storage = Storage()
        storage.config = mock_storage_settings

        result = await storage.file_exists("nonexistent/file.txt")

        assert result is False

    async def test_file_exists_without_init(self, mock_storage_settings):
        """Test file_exists before init (should create internal structures)."""
        storage = Storage()
        storage.config = mock_storage_settings

        # Files dict doesn't exist yet
        assert not hasattr(storage, "_files")

        result = await storage.file_exists("nonexistent.txt")

        assert result is False
        assert hasattr(storage, "_files")
        assert isinstance(storage._files, dict)

    async def test_create_directory_success(self, mock_storage_settings):
        """Test creating directory successfully."""
        storage = Storage()
        storage.config = mock_storage_settings

        result = await storage.create_directory("test/directory")

        assert result is True
        assert "test/directory" in storage._directories

    async def test_create_directory_without_init(self, mock_storage_settings):
        """Test creating directory before init (should create internal structures)."""
        storage = Storage()
        storage.config = mock_storage_settings

        # Directories set doesn't exist yet
        assert not hasattr(storage, "_directories")

        result = await storage.create_directory("test/directory")

        assert result is True
        assert hasattr(storage, "_directories")
        assert isinstance(storage._directories, set)
        assert "test/directory" in storage._directories

    async def test_directory_exists_true(self, mock_storage_settings):
        """Test directory_exists returns True for existing directory."""
        storage = Storage()
        storage.config = mock_storage_settings

        await storage.create_directory("test/directory")

        result = await storage.directory_exists("test/directory")

        assert result is True

    async def test_directory_exists_false(self, mock_storage_settings):
        """Test directory_exists returns False for non-existing directory."""
        storage = Storage()
        storage.config = mock_storage_settings

        result = await storage.directory_exists("nonexistent/directory")

        assert result is False

    async def test_directory_exists_without_init(self, mock_storage_settings):
        """Test directory_exists before init (should create internal structures and return False)."""
        storage = Storage()
        storage.config = mock_storage_settings

        # Directories set doesn't exist yet
        assert not hasattr(storage, "_directories")

        result = await storage.directory_exists("nonexistent/directory")

        assert result is False
        assert hasattr(storage, "_directories")
        assert isinstance(storage._directories, set)

    async def test_comprehensive_workflow(self, mock_storage_settings):
        """Test comprehensive workflow with all operations."""
        storage = Storage()
        storage.config = mock_storage_settings
        storage.logger = MagicMock()

        # Mock get_client for init
        with (
            patch.object(storage, "get_client", return_value=MagicMock()),
            patch("acb.adapters.storage._base.StorageBucket"),
        ):
            # Initialize storage
            await storage.init()

            # Test directory operations
            assert await storage.create_directory("test") is True
            assert await storage.directory_exists("test") is True
            assert await storage.directory_exists("nonexistent") is False

            # Test file operations
            content = b"comprehensive test content"

            # Put file
            assert await storage.put_file("test/file.txt", content) is True

            # Check file exists
            assert await storage.file_exists("test/file.txt") is True
            assert await storage.file_exists("nonexistent.txt") is False

            # Get file
            result_content = await storage.get_file("test/file.txt")
            assert result_content == content

            # Get non-existent file
            assert await storage.get_file("nonexistent.txt") is None

            # Delete file
            assert await storage.delete_file("test/file.txt") is True
            assert await storage.file_exists("test/file.txt") is False

            # Try to delete again
            assert await storage.delete_file("test/file.txt") is False

    async def test_multiple_files_and_directories(self, mock_storage_settings):
        """Test handling multiple files and directories."""
        storage = Storage()
        storage.config = mock_storage_settings

        # Create multiple directories
        await storage.create_directory("dir1")
        await storage.create_directory("dir2")
        await storage.create_directory("nested/dir")

        # Add multiple files
        await storage.put_file("file1.txt", b"content1")
        await storage.put_file("dir1/file2.txt", b"content2")
        await storage.put_file("dir2/file3.txt", b"content3")
        await storage.put_file("nested/dir/file4.txt", b"content4")

        # Verify all exist
        assert await storage.directory_exists("dir1") is True
        assert await storage.directory_exists("dir2") is True
        assert await storage.directory_exists("nested/dir") is True

        assert await storage.file_exists("file1.txt") is True
        assert await storage.file_exists("dir1/file2.txt") is True
        assert await storage.file_exists("dir2/file3.txt") is True
        assert await storage.file_exists("nested/dir/file4.txt") is True

        # Verify contents
        assert await storage.get_file("file1.txt") == b"content1"
        assert await storage.get_file("dir1/file2.txt") == b"content2"
        assert await storage.get_file("dir2/file3.txt") == b"content3"
        assert await storage.get_file("nested/dir/file4.txt") == b"content4"

        # Check internal structure
        assert len(storage._files) == 4
        assert len(storage._directories) >= 3  # At least the ones we created explicitly

    async def test_overwrite_file(self, mock_storage_settings):
        """Test overwriting existing file."""
        storage = Storage()
        storage.config = mock_storage_settings

        original_content = b"original content"
        new_content = b"new content"

        # Put original file
        await storage.put_file("test/file.txt", original_content)
        assert await storage.get_file("test/file.txt") == original_content

        # Overwrite file
        await storage.put_file("test/file.txt", new_content)
        assert await storage.get_file("test/file.txt") == new_content

        # Should still have only one file
        assert len(storage._files) == 1

    async def test_empty_content_file(self, mock_storage_settings):
        """Test handling files with empty content."""
        storage = Storage()
        storage.config = mock_storage_settings

        empty_content = b""

        # Put empty file
        await storage.put_file("empty.txt", empty_content)

        # Should exist and return empty content
        assert await storage.file_exists("empty.txt") is True
        assert await storage.get_file("empty.txt") == empty_content

    async def test_directory_creation_from_file_path(self, mock_storage_settings):
        """Test that directories are automatically created from file paths."""
        storage = Storage()
        storage.config = mock_storage_settings

        # Put file in nested path
        await storage.put_file("very/deep/nested/path/file.txt", b"content")

        # The immediate parent directory should be created
        assert "very/deep/nested/path" in storage._directories

        # Verify file exists
        assert await storage.file_exists("very/deep/nested/path/file.txt") is True

    def test_module_status_and_id(self):
        """Test module metadata constants."""
        from uuid import UUID

        from acb.adapters import AdapterStatus
        from acb.adapters.storage.memory import MODULE_ID, MODULE_STATUS

        assert isinstance(MODULE_ID, UUID)
        assert MODULE_STATUS == AdapterStatus.STABLE

    def test_depends_registration(self):
        """Test that Storage class is registered with dependency injection."""
        from acb.depends import depends

        # This should not raise an exception if properly registered
        storage_class = depends.get(Storage)
        assert storage_class is not None

    def test_inheritance_structure(self):
        """Test that Memory Storage properly inherits from StorageBase."""
        from acb.adapters.storage._base import StorageBase

        storage = Storage()

        # Test inheritance
        assert isinstance(storage, StorageBase)

        # Test that file_system is properly overridden
        from fsspec.implementations.memory import MemoryFileSystem

        assert storage.file_system == MemoryFileSystem

    async def test_concurrent_operations(self, mock_storage_settings):
        """Test that memory operations work correctly with multiple concurrent calls."""
        storage = Storage()
        storage.config = mock_storage_settings

        # Simulate concurrent file operations
        files_content = {f"file{i}.txt": f"content{i}".encode() for i in range(10)}

        # Put all files
        for path, content in files_content.items():
            await storage.put_file(path, content)

        # Verify all files exist and have correct content
        for path, expected_content in files_content.items():
            assert await storage.file_exists(path) is True
            assert await storage.get_file(path) == expected_content

        # Delete every other file
        for i, path in enumerate(files_content.keys()):
            if i % 2 == 0:
                await storage.delete_file(path)

        # Verify deletion
        for i, path in enumerate(files_content.keys()):
            if i % 2 == 0:
                assert await storage.file_exists(path) is False
            else:
                assert await storage.file_exists(path) is True

    async def test_edge_cases(self, mock_storage_settings):
        """Test edge cases and boundary conditions."""
        storage = Storage()
        storage.config = mock_storage_settings

        # Test empty path names
        assert await storage.put_file("", b"empty path") is True
        assert await storage.file_exists("") is True
        assert await storage.get_file("") == b"empty path"

        # Test path with only slashes
        await storage.put_file("///", b"slash content")
        assert await storage.file_exists("///") is True

        # Test very long path
        long_path = "a" * 1000
        await storage.put_file(long_path, b"long path content")
        assert await storage.file_exists(long_path) is True
        assert await storage.get_file(long_path) == b"long path content"

        # Test special characters in path
        special_path = "file with spaces & symbols!@#$%^&*().txt"
        await storage.put_file(special_path, b"special content")
        assert await storage.file_exists(special_path) is True

    async def test_memory_isolation(self, mock_storage_settings):
        """Test that different storage instances are isolated."""
        storage1 = Storage()
        storage1.config = mock_storage_settings

        storage2 = Storage()
        storage2.config = mock_storage_settings

        # Put file in storage1
        await storage1.put_file("test.txt", b"storage1 content")

        # storage2 should not see the file
        assert await storage1.file_exists("test.txt") is True
        assert await storage2.file_exists("test.txt") is False

        # Put different file in storage2
        await storage2.put_file("test2.txt", b"storage2 content")

        # storage1 should not see storage2's file
        assert await storage2.file_exists("test2.txt") is True
        assert await storage1.file_exists("test2.txt") is False
