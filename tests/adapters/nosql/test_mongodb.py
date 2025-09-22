"""Tests for MongoDB NoSQL adapter."""

from uuid import UUID

from acb.adapters.nosql.mongodb import (
    MODULE_ID,
    MODULE_METADATA,
    MODULE_STATUS,
    NosqlSettings,
)


class TestMongoDBMetadata:
    def test_module_metadata(self) -> None:
        """Test module metadata is properly defined."""
        assert MODULE_ID == UUID("0197ff44-f2c7-7af0-9138-5e6a2b4d8c91")
        assert MODULE_METADATA.name == "MongoDB"
        assert MODULE_METADATA.category == "nosql"
        assert MODULE_METADATA.provider == "mongodb"
        assert MODULE_METADATA.version == "1.1.0"
        assert "motor" in MODULE_METADATA.required_packages
        assert "beanie" in MODULE_METADATA.required_packages

    def test_module_status(self) -> None:
        """Test module status is stable."""
        from acb.adapters import AdapterStatus

        assert MODULE_STATUS == AdapterStatus.STABLE

    def test_adapter_capabilities(self) -> None:
        """Test that adapter has expected capabilities."""
        from acb.adapters import AdapterCapability

        capabilities = MODULE_METADATA.capabilities
        assert AdapterCapability.ASYNC_OPERATIONS in capabilities
        assert AdapterCapability.CONNECTION_POOLING in capabilities
        assert AdapterCapability.TRANSACTIONS in capabilities
        assert AdapterCapability.BULK_OPERATIONS in capabilities
        assert AdapterCapability.SCHEMA_VALIDATION in capabilities


class TestMongoDBSettings:
    def test_settings_init_default(self) -> None:
        """Test NosqlSettings initialization with defaults."""
        settings = NosqlSettings()

        assert hasattr(settings, "host")  # From base settings
        assert hasattr(settings, "port")  # From base settings
        assert hasattr(settings, "database")  # From base settings

    def test_settings_custom_values(self) -> None:
        """Test NosqlSettings with custom values."""
        settings = NosqlSettings(
            database="test_db", collection_prefix="test_", max_pool_size=50
        )

        assert settings.database == "test_db"
        assert settings.collection_prefix == "test_"
        assert settings.max_pool_size == 50


class TestMongoDBAdapterBasic:
    def test_adapter_import(self) -> None:
        """Test that adapter can be imported."""
        from acb.adapters.nosql.mongodb import Nosql

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

        assert "host" in config_example
        assert "port" in config_example
        assert "user" in config_example
        assert "password" in config_example
        assert "database" in config_example
        assert "ssl_enabled" in config_example

    def test_ssl_configuration(self) -> None:
        """Test SSL configuration options."""
        settings = NosqlSettings(
            ssl_enabled=True,
            ssl_cert_path="/path/to/cert.pem",
            ssl_key_path="/path/to/key.pem",
            ssl_ca_path="/path/to/ca.pem",
        )

        assert settings.ssl_enabled is True
        assert settings.ssl_cert_path == "/path/to/cert.pem"
        assert settings.ssl_key_path == "/path/to/key.pem"
        assert settings.ssl_ca_path == "/path/to/ca.pem"
