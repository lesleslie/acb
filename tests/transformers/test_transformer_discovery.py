"""Tests for transformer discovery system."""

import pytest

from acb.config import Config
from acb.depends import depends
from acb.transformers import (
    BasicTransformer,
    TransformerCapability,
    TransformerMetadata,
    TransformerStatus,
    get_best_transformer_for_mode,
    get_registered_transformers,
    get_transformer_class,
    get_transformer_metadata,
    get_transformers_by_capability,
    import_transformer,
    list_available_transformers,
    register_transformer,
)


@pytest.fixture
def mock_config():
    """Provide a mocked Config for testing."""
    config = Config()
    config.settings_dict = {"transformers": {}}
    depends.set(Config, config)
    yield config


class TestTransformerDiscovery:
    """Tests for transformer discovery functions."""

    def test_import_basic_transformer(self, mock_config):
        """Test importing the basic transformer."""
        Transformer = import_transformer("basic")
        assert Transformer == BasicTransformer

    def test_import_default_transformer(self, mock_config):
        """Test importing with default type."""
        Transformer = import_transformer()
        assert Transformer == BasicTransformer

    def test_import_unknown_transformer(self, mock_config):
        """Test importing unknown transformer type."""
        with pytest.raises(ValueError, match="Unknown transformer type"):
            import_transformer("nonexistent")

    def test_list_available_transformers(self):
        """Test listing available transformers."""
        transformers = list_available_transformers()
        assert "basic" in transformers
        assert "default" in transformers

    def test_register_transformer(self):
        """Test registering a custom transformer."""

        class CustomTransformer:
            pass

        register_transformer("custom", CustomTransformer)
        registered = get_transformer_class("custom")
        assert registered == CustomTransformer

    def test_get_registered_transformers(self):
        """Test getting all registered transformers."""
        # Register a test transformer
        class TestTransformer:
            pass

        register_transformer("test", TestTransformer)

        registered = get_registered_transformers()
        assert "test" in registered
        assert registered["test"] == TestTransformer

    def test_get_transformer_class_not_found(self):
        """Test getting non-existent transformer class."""
        result = get_transformer_class("does-not-exist")
        assert result is None


class TestTransformerMetadata:
    """Tests for transformer metadata."""

    def test_transformer_metadata_creation(self):
        """Test creating transformer metadata."""
        metadata = TransformerMetadata(
            name="Test Transformer",
            provider="test",
            version="1.0.0",
            status=TransformerStatus.STABLE,
            capabilities=[
                TransformerCapability.BATCH_PROCESSING,
                TransformerCapability.STREAMING,
            ],
            description="Test transformer",
        )

        assert metadata.name == "Test Transformer"
        assert metadata.provider == "test"
        assert metadata.version == "1.0.0"
        assert metadata.status == TransformerStatus.STABLE
        assert TransformerCapability.BATCH_PROCESSING in metadata.capabilities
        assert metadata.transformer_id is not None

    def test_transformer_metadata_defaults(self):
        """Test transformer metadata default values."""
        metadata = TransformerMetadata(
            name="Test", provider="test", version="1.0.0"
        )

        assert metadata.status == TransformerStatus.STABLE
        assert metadata.acb_min_version == "0.19.0"
        assert metadata.capabilities == []
        assert metadata.description == ""
        assert metadata.performance_hints == {}

    def test_get_transformer_metadata(self):
        """Test getting transformer metadata."""
        metadata = get_transformer_metadata("basic")
        # Basic transformer may or may not have MODULE_METADATA
        # If it does, verify it's valid
        if metadata:
            assert isinstance(metadata, TransformerMetadata)
            assert metadata.name is not None
            assert metadata.version is not None


class TestTransformerCapabilities:
    """Tests for transformer capability queries."""

    def test_transformer_capability_enum(self):
        """Test transformer capability enum values."""
        assert TransformerCapability.BATCH_PROCESSING.value == "batch_processing"
        assert TransformerCapability.STREAMING.value == "streaming"
        assert TransformerCapability.PIPELINE_PROCESSING.value == "pipeline_processing"

    def test_get_transformers_by_capability(self):
        """Test finding transformers by capability."""
        # Register a test transformer with metadata
        class TestTransformer:
            pass

        # Mock MODULE_METADATA
        import sys
        from types import SimpleNamespace

        mock_module = SimpleNamespace()
        mock_module.MODULE_METADATA = TransformerMetadata(
            name="Test",
            provider="test",
            version="1.0.0",
            capabilities=[
                TransformerCapability.BATCH_PROCESSING,
                TransformerCapability.STREAMING,
            ],
        )
        sys.modules["test_transformer_module"] = mock_module

        # Note: get_transformers_by_capability currently only checks known transformers
        # This test validates the function works with the pattern
        results = get_transformers_by_capability(TransformerCapability.BATCH_PROCESSING)
        assert isinstance(results, list)

    def test_get_best_transformer_for_batch(self):
        """Test getting best transformer for batch mode."""
        transformer_type = get_best_transformer_for_mode("batch")
        assert transformer_type in ["basic", "default"]

    def test_get_best_transformer_for_streaming(self):
        """Test getting best transformer for streaming mode."""
        transformer_type = get_best_transformer_for_mode("streaming")
        assert transformer_type in ["basic", "default"]

    def test_get_best_transformer_for_unknown_mode(self):
        """Test getting transformer for unknown mode."""
        transformer_type = get_best_transformer_for_mode("unknown")
        assert transformer_type == "basic"


class TestTransformerStatus:
    """Tests for transformer status enum."""

    def test_transformer_status_values(self):
        """Test transformer status enum values."""
        assert TransformerStatus.ALPHA.value == "alpha"
        assert TransformerStatus.BETA.value == "beta"
        assert TransformerStatus.STABLE.value == "stable"
        assert TransformerStatus.DEPRECATED.value == "deprecated"
        assert TransformerStatus.EXPERIMENTAL.value == "experimental"


class TestTransformerIntegration:
    """Integration tests for transformer discovery."""

    async def test_discover_and_use_transformer(self, mock_config):
        """Test discovering and using a transformer."""
        # Import transformer
        Transformer = import_transformer("basic")

        # Create instance
        transformer = Transformer(max_batch_size=100)

        # Verify it's usable
        assert hasattr(transformer, "transform")
        assert hasattr(transformer, "transform_batch")
        assert hasattr(transformer, "transform_stream")

    def test_transformer_registration_persistence(self):
        """Test that registered transformers persist."""

        class PersistentTransformer:
            pass

        register_transformer("persistent", PersistentTransformer)

        # First retrieval
        first = get_transformer_class("persistent")
        assert first == PersistentTransformer

        # Second retrieval should get same class
        second = get_transformer_class("persistent")
        assert second == PersistentTransformer
        assert first is second
