"""Tests for Azure storage adapter."""

from __future__ import annotations

import tempfile
from unittest.mock import MagicMock, patch
from uuid import UUID

import pytest
from adlfs import AzureBlobFileSystem
from anyio import Path as AsyncPath
from pydantic import SecretStr, ValidationError
from acb.adapters import AdapterStatus
from acb.adapters.storage._base import StorageBase, StorageBaseSettings
from acb.adapters.storage.azure import (
    MODULE_ID,
    MODULE_STATUS,
    Storage,
    StorageSettings,
)


class TestModuleConstants:
    def test_module_id(self) -> None:
        assert MODULE_ID == UUID("0197ff55-9026-7672-b2aa-b7bbc11f7b4c")

    def test_module_status(self) -> None:
        assert MODULE_STATUS == AdapterStatus.STABLE


class TestStorageSettings:
    def test_inheritance(self) -> None:
        assert issubclass(StorageSettings, StorageBaseSettings)

    def test_connection_string_field(self) -> None:
        # Test that connection_string is required and is a SecretStr
        with pytest.raises(ValidationError, match="Field required"):
            StorageSettings()  # type: ignore[call-arg]

    def test_connection_string_secret(self) -> None:
        settings = StorageSettings(
            connection_string=SecretStr("test-connection-string")
        )
        assert isinstance(settings.connection_string, SecretStr)
        assert settings.connection_string.get_secret_value() == "test-connection-string"

    def test_settings_with_all_fields(self) -> None:
        settings = StorageSettings(
            connection_string=SecretStr("test-connection"),
            prefix="test-prefix",
            local_path=AsyncPath(tempfile.gettempdir()),
            user_project="test-project",
            buckets={"test": "test-bucket"},
            cors={"test": {"origins": ["*"], "max_age": 3600}},
            local_fs=False,
            memory_fs=False,
        )
        assert settings.connection_string.get_secret_value() == "test-connection"
        assert settings.prefix == "test-prefix"
        assert str(settings.local_path) == tempfile.gettempdir()
        assert settings.user_project == "test-project"
        assert settings.buckets == {"test": "test-bucket"}
        assert settings.cors == {"test": {"origins": ["*"], "max_age": 3600}}
        assert settings.local_fs is False
        assert settings.memory_fs is False


class TestStorage:
    def test_inheritance(self) -> None:
        assert issubclass(Storage, StorageBase)

    def test_file_system_attribute(self) -> None:
        assert Storage.file_system == AzureBlobFileSystem

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
        assert storage.file_system == AzureBlobFileSystem

    @patch("acb.adapters.storage._base.depends")
    def test_storage_with_mocked_dependencies(self, mock_depends: MagicMock) -> None:
        # Mock the dependencies that would be injected
        mock_config = MagicMock()
        mock_config.app.name = "test-app"
        mock_depends.return_value = mock_config

        storage = Storage()
        assert storage.file_system == AzureBlobFileSystem


class TestAzureIntegration:
    def test_file_system_integration(self) -> None:
        # Test that the Storage class properly integrates with AzureBlobFileSystem
        storage = Storage()

        # Verify that the file_system attribute points to the correct class
        assert storage.file_system == AzureBlobFileSystem

        # Test that we can create an instance (this would normally require credentials)
        with patch.object(storage, "file_system") as mock_fs_class:
            mock_fs_instance = MagicMock()
            mock_fs_class.return_value = mock_fs_instance

            # This simulates what would happen in the base class
            fs_instance = storage.file_system()
            assert fs_instance == mock_fs_instance

    def test_azure_filesystem_import(self) -> None:
        # Test that we can import AzureBlobFileSystem
        from adlfs import AzureBlobFileSystem as ImportedAzureFS

        assert ImportedAzureFS == AzureBlobFileSystem
        assert Storage.file_system == ImportedAzureFS


class TestStorageConfiguration:
    def test_settings_validation(self) -> None:
        # Test that StorageSettings properly validates Azure-specific fields

        # Valid configuration
        valid_settings = StorageSettings(
            connection_string=SecretStr(
                "DefaultEndpointsProtocol=https;AccountName=test;AccountKey=key;"
            )
        )
        assert valid_settings.connection_string.get_secret_value().startswith(
            "DefaultEndpointsProtocol"
        )

    def test_connection_string_formats(self) -> None:
        # Test different valid connection string formats

        # Standard connection string
        settings1 = StorageSettings(
            connection_string=SecretStr(
                "DefaultEndpointsProtocol=https;AccountName=test;AccountKey=key;"
            )
        )
        assert "AccountName=test" in settings1.connection_string.get_secret_value()

        # SAS token format
        settings2 = StorageSettings(
            connection_string=SecretStr(
                "BlobEndpoint=https://test.blob.core.windows.net/;SharedAccessSignature=sv=..."
            )
        )
        assert "BlobEndpoint" in settings2.connection_string.get_secret_value()

    def test_secret_str_behavior(self) -> None:
        settings = StorageSettings(
            connection_string=SecretStr("secret-connection-string")
        )

        # Test that the secret is properly hidden in string representation
        settings_str = str(settings.connection_string)
        assert "secret-connection-string" not in settings_str
        assert "SecretStr" in settings_str or "**" in settings_str

        # Test that we can retrieve the actual value
        assert (
            settings.connection_string.get_secret_value() == "secret-connection-string"
        )


class TestStorageImplementation:
    def test_storage_methods_inheritance(self) -> None:
        # Test that Storage inherits all necessary methods from StorageBase
        storage = Storage()

        # Check that important attributes/methods exist (inherited from base)
        assert hasattr(storage, "file_system")

        # The actual methods would be defined in StorageBase
        # Here we just verify the class structure is correct
        assert isinstance(storage, StorageBase)

    def test_azure_specific_functionality(self) -> None:
        # Test Azure-specific aspects of the storage implementation
        storage = Storage()

        # Verify the file system is specifically Azure
        assert storage.file_system == AzureBlobFileSystem

        # Test that it's different from other file systems
        from fsspec.implementations.local import LocalFileSystem

        assert storage.file_system != LocalFileSystem

    @patch("acb.adapters.storage._base.StorageBase.__init__")
    def test_storage_initialization(self, mock_base_init: MagicMock) -> None:
        # Test that Storage properly initializes its base class
        mock_base_init.return_value = None

        storage = Storage()

        # Verify base class initialization was called
        mock_base_init.assert_called_once()

        # Verify Azure-specific attributes
        assert storage.file_system == AzureBlobFileSystem


class TestErrorHandling:
    def test_missing_connection_string(self) -> None:
        # Test error handling when connection_string is missing
        with pytest.raises(ValidationError, match="Field required"):
            StorageSettings()  # type: ignore[call-arg]

    def test_invalid_connection_string_type(self) -> None:
        # Test error handling for invalid connection string type
        with pytest.raises((ValueError, ValidationError)):
            StorageSettings(connection_string=12345)  # type: ignore[arg-type]

    def test_none_connection_string(self) -> None:
        # Test error handling for None connection string
        with pytest.raises((ValueError, ValidationError)):
            StorageSettings(connection_string=None)  # type: ignore[arg-type]


class TestStorageIntegrationWithBase:
    @patch("acb.adapters.storage._base.get_adapter")
    @patch("acb.adapters.storage._base.depends")
    def test_storage_with_base_settings(
        self, mock_depends: MagicMock, mock_get_adapter: MagicMock
    ) -> None:
        # Mock the config and adapter
        mock_config = MagicMock()
        mock_config.app.name = "test-app"
        mock_depends.return_value = mock_config

        mock_adapter = MagicMock()
        mock_adapter.name = "azure"
        mock_get_adapter.return_value = mock_adapter

        # Test creating storage settings
        settings = StorageSettings(connection_string=SecretStr("test-connection"))

        # Verify inheritance works correctly
        assert isinstance(settings, StorageBaseSettings)
        assert settings.connection_string.get_secret_value() == "test-connection"
