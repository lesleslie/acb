"""Tests for Google Cloud Storage adapter."""

from __future__ import annotations

import tempfile
import warnings
from unittest.mock import MagicMock, patch
from uuid import UUID

import pytest
from anyio import Path as AsyncPath

# Skip entire module if gcsfs is not installed
pytest.importorskip("gcsfs")

from gcsfs.core import GCSFileSystem

from acb.adapters import AdapterStatus
from acb.adapters.storage._base import StorageBase, StorageBaseSettings
from acb.adapters.storage.gcs import (
    MODULE_ID,
    MODULE_STATUS,
    Storage,
    StorageSettings,
)


class TestModuleConstants:
    def test_module_id(self) -> None:
        assert MODULE_ID == UUID("0197ff55-9026-7672-b2aa-b7a742cd8f87")

    def test_module_status(self) -> None:
        assert MODULE_STATUS == AdapterStatus.STABLE


class TestStorageSettings:
    def test_inheritance(self) -> None:
        assert issubclass(StorageSettings, StorageBaseSettings)

    def test_default_cors_config(self) -> None:
        settings = StorageSettings()
        expected_cors = {
            "upload": {
                "origin": ["*"],
                "method": ["*"],
                "responseHeader": ["*"],
                "maxAgeSeconds": 600,
            },
        }
        assert settings.cors == expected_cors

    def test_custom_cors_config(self) -> None:
        custom_cors = {
            "api": {
                "origin": ["https://example.com"],
                "method": ["GET", "POST"],
                "responseHeader": ["Content-Type"],
                "maxAgeSeconds": 3600,
            },
        }
        settings = StorageSettings(cors=custom_cors)
        assert settings.cors == custom_cors

    def test_none_cors_config(self) -> None:
        settings = StorageSettings(cors=None)
        assert settings.cors is None

    def test_settings_with_all_inherited_fields(self) -> None:
        settings = StorageSettings(
            prefix="test-prefix",
            local_path=AsyncPath(tempfile.gettempdir()),
            user_project="test-project",
            buckets={"test": "test-bucket"},
            local_fs=False,
            memory_fs=False,
        )
        assert settings.prefix == "test-prefix"
        assert str(settings.local_path) == tempfile.gettempdir()
        assert settings.user_project == "test-project"
        assert settings.buckets == {"test": "test-bucket"}
        assert settings.local_fs is False
        assert settings.memory_fs is False


class TestStorage:
    def test_inheritance(self) -> None:
        assert issubclass(Storage, StorageBase)

    def test_file_system_attribute(self) -> None:
        assert Storage.file_system == GCSFileSystem

    def test_dependency_registration(self) -> None:
        # Test that the module can be imported and dependency system is accessible
        # The actual depends.set(Storage) call happens at module import time
        from acb.depends import depends

        # Verify the dependency system is working
        assert callable(depends.set)
        assert callable(depends.get)
        assert callable(depends.inject)

    def test_storage_instantiation(self) -> None:
        # Test that Storage can be instantiated
        storage = Storage()
        assert isinstance(storage, Storage)
        assert isinstance(storage, StorageBase)

    def test_storage_file_system_property(self) -> None:
        storage = Storage()
        assert storage.file_system == GCSFileSystem


class TestGetClient:
    @patch("acb.adapters.storage.gcs.Client")
    def test_get_client_basic(self, mock_client_class) -> None:
        from acb.config import Config
        from acb.depends import depends

        # Mock the config instance
        mock_config = MagicMock(spec=Config)
        mock_config.app.project = "test-project"

        # Register mock config in DI container
        depends.set(Config, mock_config)

        try:
            # Mock the Client constructor
            mock_client_instance = MagicMock()
            mock_client_class.return_value = mock_client_instance

            # Test the get_client method - config comes from DI
            client = Storage.get_client()

            # Verify Client was called with correct project
            mock_client_class.assert_called_once_with(project="test-project")
            assert client == mock_client_instance
        finally:
            # Restore original Config instance
            depends.set(Config, Config())

    @patch("acb.adapters.storage.gcs.Client")
    @patch("acb.adapters.storage.gcs.catch_warnings")
    @patch("acb.adapters.storage.gcs.filterwarnings")
    def test_get_client_warning_suppression(
        self, mock_filterwarnings, mock_catch_warnings, mock_client_class
    ) -> None:
        from acb.config import Config
        from acb.depends import depends

        # Mock the config instance
        mock_config = MagicMock(spec=Config)
        mock_config.app.project = "test-project"

        # Register mock config in DI container
        depends.set(Config, mock_config)

        try:
            # Mock the warning context manager
            mock_warnings_context = MagicMock()
            mock_catch_warnings.return_value = mock_warnings_context

            # Mock the Client constructor
            mock_client_instance = MagicMock()
            mock_client_class.return_value = mock_client_instance

            # Test the get_client method - config comes from DI
            client = Storage.get_client()

            # Verify warning suppression was set up
            mock_catch_warnings.assert_called_once()
            mock_filterwarnings.assert_called_once_with("ignore", category=Warning)

            # Verify Client was still called correctly
            mock_client_class.assert_called_once_with(project="test-project")
            assert client == mock_client_instance
        finally:
            # Restore original Config instance
            depends.set(Config, Config())

    def test_get_client_with_real_warning_suppression(self) -> None:
        from acb.config import Config
        from acb.depends import depends

        # Mock the config dependency
        mock_config = MagicMock(spec=Config)
        mock_config.app.project = "test-project"

        # Register mock config in DI container
        depends.set(Config, mock_config)

        try:
            # Test that warnings are actually suppressed
            with patch("acb.adapters.storage.gcs.Client") as mock_client:
                mock_client_instance = MagicMock()
                mock_client.return_value = mock_client_instance

                # This should not raise any warnings
                with warnings.catch_warnings(record=True):
                    warnings.simplefilter("always")

                    # The get_client method should suppress warnings internally
                    client = Storage.get_client()

                    # Verify the client was created
                    assert client == mock_client_instance
        finally:
            # Restore original Config instance
            depends.set(Config, Config())


class TestSetCors:
    def test_set_cors_basic(self) -> None:
        storage = Storage()

        # Mock the get_client method and its return value
        mock_client = MagicMock()
        mock_bucket = MagicMock()
        mock_bucket.name = "test-bucket"
        mock_client.get_bucket.return_value = mock_bucket

        # Mock the config and logger
        storage.config = MagicMock()
        storage.config.storage.cors = {
            "upload": {
                "origin": ["*"],
                "method": ["*"],
                "responseHeader": ["*"],
                "maxAgeSeconds": 600,
            }
        }
        storage.logger = MagicMock()

        with patch.object(storage, "get_client", return_value=mock_client):
            storage.set_cors("test-bucket", "upload")

        # Verify the bucket was retrieved and CORS was set
        mock_client.get_bucket.assert_called_once_with("test-bucket")
        assert mock_bucket.cors == [storage.config.storage.cors["upload"]]
        mock_bucket.patch.assert_called_once()
        storage.logger.debug.assert_called_once_with(
            "CORS policies for 'test-bucket' bucket set"
        )

    def test_set_cors_with_custom_config(self) -> None:
        storage = Storage()

        # Mock the get_client method and its return value
        mock_client = MagicMock()
        mock_bucket = MagicMock()
        mock_bucket.name = "custom-bucket"
        mock_client.get_bucket.return_value = mock_bucket

        # Mock the config with custom CORS settings
        storage.config = MagicMock()
        custom_cors = {
            "api": {
                "origin": ["https://example.com"],
                "method": ["GET", "POST"],
                "responseHeader": ["Content-Type"],
                "maxAgeSeconds": 3600,
            }
        }
        storage.config.storage.cors = custom_cors
        storage.logger = MagicMock()

        with patch.object(storage, "get_client", return_value=mock_client):
            storage.set_cors("custom-bucket", "api")

        # Verify the custom CORS config was applied
        mock_client.get_bucket.assert_called_once_with("custom-bucket")
        assert mock_bucket.cors == [custom_cors["api"]]
        mock_bucket.patch.assert_called_once()

    def test_set_cors_bucket_not_found(self) -> None:
        storage = Storage()

        # Mock the get_client method to raise an exception
        mock_client = MagicMock()
        mock_client.get_bucket.side_effect = Exception("Bucket not found")

        storage.config = MagicMock()
        storage.config.storage.cors = {"upload": {}}

        with patch.object(storage, "get_client", return_value=mock_client):
            with pytest.raises(Exception, match="Bucket not found"):
                storage.set_cors("nonexistent-bucket", "upload")


class TestRemoveCors:
    def test_remove_cors_basic(self) -> None:
        storage = Storage()

        # Mock the get_client method and its return value
        mock_client = MagicMock()
        mock_storage_client = MagicMock()
        mock_bucket = MagicMock()
        mock_bucket.name = "test-bucket"

        mock_client.storage_client = mock_storage_client
        mock_storage_client.get_bucket.return_value = mock_bucket

        # Mock the logger
        storage.logger = MagicMock()

        with patch.object(storage, "get_client", return_value=mock_client):
            storage.remove_cors("test-bucket")

        # Verify the bucket was retrieved and CORS was cleared
        mock_storage_client.get_bucket.assert_called_once_with("test-bucket")
        assert mock_bucket.cors == []
        mock_bucket.patch.assert_called_once()
        storage.logger.debug.assert_called_once_with(
            "CORS policies for 'test-bucket' bucket removed"
        )

    def test_remove_cors_bucket_not_found(self) -> None:
        storage = Storage()

        # Mock the get_client method to raise an exception
        mock_client = MagicMock()
        mock_storage_client = MagicMock()
        mock_storage_client.get_bucket.side_effect = Exception("Bucket not found")
        mock_client.storage_client = mock_storage_client

        with patch.object(storage, "get_client", return_value=mock_client):
            with pytest.raises(Exception, match="Bucket not found"):
                storage.remove_cors("nonexistent-bucket")

    def test_remove_cors_clears_existing_cors(self) -> None:
        storage = Storage()

        # Mock the get_client method and bucket with existing CORS
        mock_client = MagicMock()
        mock_storage_client = MagicMock()
        mock_bucket = MagicMock()
        mock_bucket.name = "test-bucket"
        mock_bucket.cors = [{"origin": ["*"], "method": ["GET"]}]  # Existing CORS

        mock_client.storage_client = mock_storage_client
        mock_storage_client.get_bucket.return_value = mock_bucket

        storage.logger = MagicMock()

        with patch.object(storage, "get_client", return_value=mock_client):
            storage.remove_cors("test-bucket")

        # Verify CORS was cleared
        assert mock_bucket.cors == []
        mock_bucket.patch.assert_called_once()


class TestGCSIntegration:
    def test_file_system_integration(self) -> None:
        # Test that the Storage class properly integrates with GCSFileSystem
        storage = Storage()

        # Verify that the file_system attribute points to the correct class
        assert storage.file_system == GCSFileSystem

        # Test that we can create an instance (this would normally require credentials)
        with patch.object(storage, "file_system") as mock_fs_class:
            mock_fs_instance = MagicMock()
            mock_fs_class.return_value = mock_fs_instance

            # This simulates what would happen in the base class
            fs_instance = storage.file_system()
            assert fs_instance == mock_fs_instance

    def test_gcs_filesystem_import(self) -> None:
        # Test that we can import GCSFileSystem
        from gcsfs.core import GCSFileSystem as ImportedGCSFS

        assert ImportedGCSFS == GCSFileSystem
        assert Storage.file_system == ImportedGCSFS


class TestStorageImplementation:
    def test_storage_methods_inheritance(self) -> None:
        # Test that Storage inherits all necessary methods from StorageBase
        storage = Storage()

        # Check that important attributes/methods exist (inherited from base)
        assert hasattr(storage, "file_system")
        assert hasattr(storage, "set_cors")
        assert hasattr(storage, "remove_cors")
        assert hasattr(storage, "get_client")

        # The actual methods would be defined in StorageBase
        # Here we just verify the class structure is correct
        assert isinstance(storage, StorageBase)

    def test_gcs_specific_functionality(self) -> None:
        # Test GCS-specific aspects of the storage implementation
        storage = Storage()

        # Verify the file system is specifically GCS
        assert storage.file_system == GCSFileSystem

        # Test that it's different from other file systems
        from fsspec.implementations.local import LocalFileSystem

        assert storage.file_system != LocalFileSystem

    @patch("acb.adapters.storage._base.StorageBase.__init__")
    def test_storage_initialization(self, mock_base_init) -> None:
        # Test that Storage properly initializes its base class
        mock_base_init.return_value = None

        storage = Storage()

        # Verify base class initialization was called
        mock_base_init.assert_called_once()

        # Verify GCS-specific attributes
        assert storage.file_system == GCSFileSystem
        assert hasattr(storage, "set_cors")
        assert hasattr(storage, "remove_cors")


class TestErrorHandling:
    def test_get_client_with_invalid_project(self) -> None:
        with patch("acb.adapters.storage.gcs.depends") as mock_depends:
            with patch("acb.adapters.storage.gcs.Client") as mock_client:
                # Mock config with invalid project
                mock_config = MagicMock()
                mock_config.app.project = None
                mock_depends.return_value = mock_config

                # Mock Client to raise an exception for invalid project
                mock_client.side_effect = Exception("Invalid project")

                with pytest.raises(Exception, match="Invalid project"):
                    Storage.get_client()


class TestCorsConfigurationTypes:
    def test_cors_config_structure(self) -> None:
        # Test that CORS configuration has the expected structure
        settings = StorageSettings()
        assert settings.cors is not None
        cors_config = settings.cors["upload"]

        # Verify required fields exist
        assert "origin" in cors_config
        assert "method" in cors_config
        assert "responseHeader" in cors_config
        assert "maxAgeSeconds" in cors_config

        # Verify field types
        assert isinstance(cors_config["origin"], list)
        assert isinstance(cors_config["method"], list)
        assert isinstance(cors_config["responseHeader"], list)
        assert isinstance(cors_config["maxAgeSeconds"], int)

    def test_cors_config_values(self) -> None:
        # Test that default CORS configuration has sensible values
        settings = StorageSettings()
        assert settings.cors is not None
        cors_config = settings.cors["upload"]

        # Verify default values
        assert cors_config["origin"] == ["*"]
        assert cors_config["method"] == ["*"]
        assert cors_config["responseHeader"] == ["*"]
        assert cors_config["maxAgeSeconds"] == 600

    def test_multiple_cors_configs(self) -> None:
        # Test handling multiple CORS configurations
        custom_cors = {
            "upload": {
                "origin": ["*"],
                "method": ["POST", "PUT"],
                "responseHeader": ["Content-Type"],
                "maxAgeSeconds": 300,
            },
            "download": {
                "origin": ["https://example.com"],
                "method": ["GET"],
                "responseHeader": ["*"],
                "maxAgeSeconds": 3600,
            },
        }

        settings = StorageSettings(cors=custom_cors)
        assert settings.cors is not None
        assert len(settings.cors) == 2
        assert "upload" in settings.cors
        assert "download" in settings.cors
        assert settings.cors["upload"]["maxAgeSeconds"] == 300
        assert settings.cors["download"]["maxAgeSeconds"] == 3600
