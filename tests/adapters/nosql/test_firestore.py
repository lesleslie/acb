"""Tests for Firestore NoSQL adapter."""

from uuid import UUID

from acb.adapters.nosql.firestore import (
    MODULE_ID,
    MODULE_METADATA,
    MODULE_STATUS,
    NosqlSettings,
)


class TestFirestoreMetadata:
    def test_module_metadata(self) -> None:
        """Test module metadata is properly defined."""
        assert MODULE_ID == UUID("0197ff45-0a82-7e10-bb46-9d3c8f15a7e2")
        assert MODULE_METADATA.name == "Firestore"
        assert MODULE_METADATA.category == "nosql"
        assert MODULE_METADATA.provider == "firestore"
        assert MODULE_METADATA.version == "1.1.0"
        assert "google-cloud-firestore" in MODULE_METADATA.required_packages

    def test_module_status(self) -> None:
        """Test module status is stable."""
        from acb.adapters import AdapterStatus

        assert MODULE_STATUS == AdapterStatus.STABLE

    def test_adapter_capabilities(self) -> None:
        """Test that adapter has expected capabilities."""
        from acb.adapters import AdapterCapability

        capabilities = MODULE_METADATA.capabilities
        assert AdapterCapability.ASYNC_OPERATIONS in capabilities
        assert AdapterCapability.TRANSACTIONS in capabilities
        assert AdapterCapability.BULK_OPERATIONS in capabilities
        assert AdapterCapability.SCHEMA_VALIDATION in capabilities


class TestFirestoreSettings:
    def test_settings_init_default(self) -> None:
        """Test NosqlSettings initialization with defaults."""
        settings = NosqlSettings()

        assert settings.project_id is None
        assert settings.credentials_path is None
        assert hasattr(settings, "host")  # From base settings

    def test_settings_custom_values(self) -> None:
        """Test NosqlSettings with custom values."""
        settings = NosqlSettings(
            project_id="test-project",
            credentials_path="/path/to/creds.json",
            emulator_host="localhost:8080",
        )

        assert settings.project_id == "test-project"
        assert settings.credentials_path == "/path/to/creds.json"
        assert settings.emulator_host == "localhost:8080"


class TestFirestoreAdapterBasic:
    def test_adapter_import(self) -> None:
        """Test that adapter can be imported."""
        from acb.adapters.nosql.firestore import Nosql

        # Basic import test
        assert Nosql is not None

    def test_settings_inheritance(self) -> None:
        """Test that settings inherit from base properly."""
        from acb.adapters.nosql._base import NosqlBaseSettings

        settings = NosqlSettings()
        assert isinstance(settings, NosqlBaseSettings)

    def test_module_config_example(self) -> None:
        """Test that module config example is properly defined."""
        config_example = MODULE_METADATA.config_example

        assert "project_id" in config_example
        assert "credentials_path" in config_example
        assert "emulator_host" in config_example
        assert "ssl_enabled" in config_example
