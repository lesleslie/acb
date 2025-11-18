"""Tests for S3 Storage adapter."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from anyio import Path as AsyncPath
from pydantic import SecretStr

# Skip entire module if s3fs is not installed
pytest.importorskip("s3fs")

from acb.adapters.storage.s3 import Storage, StorageSettings


class TestS3StorageSettings:
    """Test S3 Storage settings."""

    def test_init_with_required_values(self, mock_config):
        """Test settings initialization with required values."""
        settings = StorageSettings(
            access_key_id=SecretStr("test-access-key"),
            secret_access_key=SecretStr("test-secret-key"),
        )

        assert settings.access_key_id.get_secret_value() == "test-access-key"
        assert settings.secret_access_key.get_secret_value() == "test-secret-key"
        # Test inherited defaults from StorageBaseSettings
        # prefix gets set from config.app.name in the base class
        assert settings.prefix == "acb"
        assert settings.user_project == "acb"
        assert settings.buckets == {"test": "test-bucket"}
        assert settings.local_fs is False
        assert settings.memory_fs is False

    def test_init_with_custom_values(self, mock_config):
        """Test settings initialization with custom values."""
        custom_buckets = {
            "media": "my-media-bucket",
            "templates": "my-templates-bucket",
            "test": "my-test-bucket",
        }

        settings = StorageSettings(
            access_key_id=SecretStr("custom-access-key"),
            secret_access_key=SecretStr("custom-secret-key"),
            prefix="my-app",
            user_project="my-project",
            buckets=custom_buckets,
            local_path=AsyncPath("/custom/storage"),
        )

        assert settings.access_key_id.get_secret_value() == "custom-access-key"
        assert settings.secret_access_key.get_secret_value() == "custom-secret-key"
        assert settings.prefix == "my-app"
        assert settings.user_project == "my-project"
        assert settings.buckets == custom_buckets
        assert settings.local_path == AsyncPath("/custom/storage")


class TestS3Storage:
    """Test S3 Storage adapter."""

    @pytest.fixture
    def mock_storage_settings(self, mock_config):
        """Mock storage settings for testing."""
        mock_config.storage = StorageSettings(
            access_key_id=SecretStr("test-access-key"),
            secret_access_key=SecretStr("test-secret-key"),
            prefix="test-app",
            user_project="test-project",
            buckets={
                "test": "test-bucket",
                "media": "media-bucket",
                "templates": "templates-bucket",
            },
        )
        return mock_config

    @pytest.fixture
    def mock_s3_client(self):
        """Mock S3FileSystem client."""
        client = AsyncMock()

        # Mock common S3FileSystem methods
        client.url = MagicMock()
        client._sign = AsyncMock()
        client._info = AsyncMock()
        client._ls = AsyncMock()
        client._exists = AsyncMock()
        client._mkdir = AsyncMock()
        client.open = AsyncMock()
        client._pipe_file = AsyncMock()
        client._rm_file = AsyncMock()
        client.set_cors = MagicMock()

        return client

    def test_init(self, mock_storage_settings):
        """Test adapter initialization."""
        storage = Storage()
        storage.config = mock_storage_settings

        # Check that file_system is set to S3FileSystem
        from s3fs import S3FileSystem

        assert storage.file_system == S3FileSystem
        assert storage._client is None

    async def test_create_client(self, mock_storage_settings, mock_s3_client):
        """Test S3 client creation via StorageBase._create_client."""
        storage = Storage()
        storage.config = mock_storage_settings

        # Mock the file_system class to return our mock client
        with patch.object(
            storage, "file_system", return_value=mock_s3_client
        ) as mock_fs:
            client = await storage._create_client()

            mock_fs.assert_called_once_with(asynchronous=True)
            assert client == mock_s3_client

    async def test_get_client(self, mock_storage_settings, mock_s3_client):
        """Test client getter with lazy initialization."""
        storage = Storage()
        storage.config = mock_storage_settings

        with patch.object(
            storage, "_create_client", return_value=mock_s3_client
        ) as mock_create:
            client = await storage.get_client()

            mock_create.assert_called_once()
            assert storage._client == client
            assert client == mock_s3_client

            # Second call should not create again
            client2 = await storage.get_client()
            assert client == client2
            assert mock_create.call_count == 1

    def test_client_property_not_initialized(self, mock_storage_settings):
        """Test client property when not initialized."""
        storage = Storage()
        storage.config = mock_storage_settings

        with pytest.raises(RuntimeError, match="Client not initialized"):
            _ = storage.client

    def test_client_property_initialized(self, mock_storage_settings, mock_s3_client):
        """Test client property when initialized."""
        storage = Storage()
        storage.config = mock_storage_settings
        storage._client = mock_s3_client

        assert storage.client == mock_s3_client

    async def test_init_method(self, mock_storage_settings, mock_s3_client):
        """Test initialization method that creates bucket objects."""
        storage = Storage()
        storage.config = mock_storage_settings

        # Mock the logger which comes from AdapterBase
        mock_logger = MagicMock()
        storage.logger = mock_logger

        with (
            patch.object(storage, "get_client", return_value=mock_s3_client),
            patch("acb.adapters.storage._base.StorageBucket") as mock_bucket_class,
        ):
            mock_bucket = MagicMock()
            mock_bucket_class.return_value = mock_bucket

            await storage.init()

            # Check that bucket attributes were created
            assert hasattr(storage, "test")
            assert hasattr(storage, "media")
            assert hasattr(storage, "templates")

            # Check that StorageBucket was called for each bucket
            assert mock_bucket_class.call_count == 3

            # Check logger calls
            assert mock_logger.debug.call_count == 3
            debug_calls = [call.args[0] for call in mock_logger.debug.call_args_list]
            assert "Test storage bucket initialized" in debug_calls
            assert "Media storage bucket initialized" in debug_calls
            assert "Templates storage bucket initialized" in debug_calls

    async def test_bucket_operations(self, mock_storage_settings, mock_s3_client):
        """Test bucket-level operations through StorageBucket."""
        storage = Storage()
        storage.config = mock_storage_settings
        storage.logger = MagicMock()  # Mock logger

        # Mock StorageBucket creation
        with (
            patch.object(storage, "get_client", return_value=mock_s3_client),
            patch("acb.adapters.storage._base.StorageBucket") as mock_bucket_class,
        ):
            mock_bucket = MagicMock()
            mock_bucket_class.return_value = mock_bucket

            await storage.init()

            # Verify StorageBucket was created for each bucket
            assert mock_bucket_class.call_count == 3

            # Check the buckets were created with correct parameters
            calls = mock_bucket_class.call_args_list
            bucket_names = [call.args[1] for call in calls]
            assert "test" in bucket_names
            assert "media" in bucket_names
            assert "templates" in bucket_names

    async def test_bucket_access_after_init(
        self, mock_storage_settings, mock_s3_client
    ):
        """Test accessing bucket attributes after initialization."""
        storage = Storage()
        storage.config = mock_storage_settings
        storage.logger = MagicMock()  # Mock logger

        with (
            patch.object(storage, "get_client", return_value=mock_s3_client),
            patch("acb.adapters.storage._base.StorageBucket") as mock_bucket_class,
        ):
            mock_test_bucket = MagicMock()
            mock_media_bucket = MagicMock()
            mock_templates_bucket = MagicMock()

            # Configure the mock to return different buckets for different calls
            mock_bucket_class.side_effect = [
                mock_test_bucket,
                mock_media_bucket,
                mock_templates_bucket,
            ]

            await storage.init()

            # Test bucket access
            assert storage.test == mock_test_bucket
            assert storage.media == mock_media_bucket
            assert storage.templates == mock_templates_bucket

    def test_file_system_attribute(self, mock_storage_settings):
        """Test that file_system attribute is correctly set."""
        storage = Storage()
        storage.config = mock_storage_settings

        from s3fs import S3FileSystem

        assert storage.file_system == S3FileSystem

        # Test that it's the class, not an instance
        assert callable(storage.file_system)

    async def test_s3_specific_configuration(
        self, mock_storage_settings, mock_s3_client
    ):
        """Test S3-specific configuration and features."""
        storage = Storage()
        storage.config = mock_storage_settings

        # Mock the file_system to capture initialization parameters
        with patch.object(
            storage, "file_system", return_value=mock_s3_client
        ) as mock_fs:
            await storage._create_client()

            # Verify file_system was called with asynchronous=True
            mock_fs.assert_called_once_with(asynchronous=True)

    async def test_inheritance_from_storage_base(self, mock_storage_settings):
        """Test that S3 adapter properly inherits from StorageBase."""
        storage = Storage()
        storage.config = mock_storage_settings

        # Test that inherited methods exist
        assert hasattr(storage, "get_client")
        assert hasattr(storage, "_create_client")
        assert hasattr(storage, "init")

        # Test that properties exist
        assert hasattr(storage, "file_system")
        assert hasattr(storage, "templates")
        assert hasattr(storage, "media")
        assert hasattr(storage, "test")

    async def test_error_handling_in_client_creation(self, mock_storage_settings):
        """Test error handling during client creation."""
        storage = Storage()
        storage.config = mock_storage_settings

        with patch.object(
            storage, "file_system", side_effect=Exception("S3 connection failed")
        ):
            with pytest.raises(Exception, match="S3 connection failed"):
                await storage._create_client()

    async def test_error_handling_in_init(self, mock_storage_settings):
        """Test error handling during initialization."""
        storage = Storage()
        storage.config = mock_storage_settings

        with patch.object(storage, "get_client", side_effect=Exception("Init failed")):
            with pytest.raises(Exception, match="Init failed"):
                await storage.init()

    def test_module_status_and_id(self):
        """Test module metadata constants."""
        from uuid import UUID

        from acb.adapters import AdapterStatus
        from acb.adapters.storage.s3 import MODULE_ID, MODULE_STATUS

        assert isinstance(MODULE_ID, UUID)
        assert MODULE_STATUS == AdapterStatus.STABLE

    def test_depends_registration(self):
        """Test that Storage class is registered with dependency injection."""
        from acb.depends import depends

        # This should not raise an exception if properly registered
        storage_class = depends.get(Storage)
        assert storage_class is not None

    async def test_comprehensive_workflow(self, mock_storage_settings, mock_s3_client):
        """Test a comprehensive workflow with storage operations."""
        storage = Storage()
        storage.config = mock_storage_settings

        # Mock logger
        mock_logger = MagicMock()
        storage.logger = mock_logger

        with (
            patch.object(storage, "get_client", return_value=mock_s3_client),
            patch("acb.adapters.storage._base.StorageBucket") as mock_bucket_class,
        ):
            mock_bucket = MagicMock()
            mock_bucket_class.return_value = mock_bucket

            # Initialize storage
            await storage.init()

            # Verify get_client was called (the _client is set via _ensure_client mechanism)
            # Since we're mocking get_client, we just verify the mock was called
            assert hasattr(storage, "test")
            assert hasattr(storage, "media")
            assert hasattr(storage, "templates")

            # Verify all bucket types were created
            assert mock_bucket_class.call_count == 3

            # Check logger messages
            assert mock_logger.debug.call_count == 3

    def test_settings_secret_handling(self, mock_config):
        """Test that secrets are properly handled."""
        settings = StorageSettings(
            access_key_id=SecretStr("secret-access-key"),
            secret_access_key=SecretStr("secret-secret-key"),
        )

        # Test that secrets are properly masked
        assert "secret-access-key" not in str(settings)
        assert "secret-secret-key" not in str(settings)

        # But can be retrieved when needed
        assert settings.access_key_id.get_secret_value() == "secret-access-key"
        assert settings.secret_access_key.get_secret_value() == "secret-secret-key"

    async def test_multiple_bucket_configurations(self, mock_config, mock_s3_client):
        """Test storage with different bucket configurations."""
        # Test with minimal buckets
        minimal_config = mock_config
        minimal_config.storage = StorageSettings(
            access_key_id=SecretStr("test-key"),
            secret_access_key=SecretStr("test-secret"),
            buckets={"test": "minimal-bucket"},
        )

        storage = Storage()
        storage.config = minimal_config

        # Mock logger
        mock_logger = MagicMock()
        storage.logger = mock_logger

        with (
            patch.object(storage, "get_client", return_value=mock_s3_client),
            patch("acb.adapters.storage._base.StorageBucket"),
        ):
            await storage.init()

            # Should only have test bucket
            assert hasattr(storage, "test")
            assert mock_logger.debug.call_count == 1

    def test_inheritance_structure(self):
        """Test that S3 Storage properly inherits from StorageBase."""
        from acb.adapters.storage._base import StorageBase

        storage = Storage()

        # Test inheritance
        assert isinstance(storage, StorageBase)

        # Test that file_system is properly overridden
        from s3fs import S3FileSystem

        assert storage.file_system == S3FileSystem
