"""Tests for Gateway Discovery functionality."""

import pytest
from unittest.mock import MagicMock, patch

from acb.gateway.discovery import (
    GatewayCapability,
    GatewayMetadata,
    GatewayStatus,
    generate_gateway_id,
    get_gateway_descriptor,
    import_gateway,
    list_available_gateways,
    list_enabled_gateways,
    list_gateways,
)


class TestGatewayDiscovery:
    """Test cases for Gateway Discovery."""

    def test_generate_gateway_id(self):
        """Test gateway ID generation."""
        from uuid import UUID

        gateway_id = generate_gateway_id()

        assert isinstance(gateway_id, UUID)
        assert str(gateway_id)  # Can be converted to string

    def test_gateway_metadata_creation(self):
        """Test GatewayMetadata creation."""
        metadata = GatewayMetadata(
            gateway_id="test_gateway",
            name="Test Gateway",
            description="A test gateway",
            version="1.0.0",
            status=GatewayStatus.ENABLED,
            capabilities=[GatewayCapability.RATE_LIMITING, GatewayCapability.AUTHENTICATION],
            tags=["test", "api"],
        )

        assert metadata.gateway_id == "test_gateway"
        assert metadata.name == "Test Gateway"
        assert metadata.status == GatewayStatus.ENABLED
        assert GatewayCapability.RATE_LIMITING in metadata.capabilities
        assert "test" in metadata.tags

    def test_gateway_capability_enum(self):
        """Test GatewayCapability enum values."""
        assert GatewayCapability.RATE_LIMITING.value == "rate_limiting"
        assert GatewayCapability.AUTHENTICATION.value == "authentication"
        assert GatewayCapability.CACHING.value == "caching"
        assert GatewayCapability.ROUTING.value == "routing"
        assert GatewayCapability.ANALYTICS.value == "analytics"
        assert GatewayCapability.SECURITY.value == "security"
        assert GatewayCapability.VALIDATION.value == "validation"

    def test_gateway_status_enum(self):
        """Test GatewayStatus enum values."""
        assert GatewayStatus.ENABLED.value == "enabled"
        assert GatewayStatus.DISABLED.value == "disabled"
        assert GatewayStatus.ERROR.value == "error"
        assert GatewayStatus.MAINTENANCE.value == "maintenance"

    @patch('acb.gateway.discovery._discover_gateways')
    def test_list_available_gateways(self, mock_discover):
        """Test listing available gateways."""
        mock_gateways = [
            GatewayMetadata(
                gateway_id="gateway1",
                name="Gateway 1",
                description="First gateway",
                version="1.0.0",
                status=GatewayStatus.ENABLED,
                capabilities=[GatewayCapability.RATE_LIMITING],
            ),
            GatewayMetadata(
                gateway_id="gateway2",
                name="Gateway 2",
                description="Second gateway",
                version="2.0.0",
                status=GatewayStatus.DISABLED,
                capabilities=[GatewayCapability.AUTHENTICATION],
            ),
        ]
        mock_discover.return_value = mock_gateways

        gateways = list_available_gateways()

        assert len(gateways) == 2
        assert gateways[0].gateway_id == "gateway1"
        assert gateways[1].gateway_id == "gateway2"

    @patch('acb.gateway.discovery._discover_gateways')
    def test_list_enabled_gateways(self, mock_discover):
        """Test listing enabled gateways only."""
        mock_gateways = [
            GatewayMetadata(
                gateway_id="enabled_gateway",
                name="Enabled Gateway",
                description="An enabled gateway",
                version="1.0.0",
                status=GatewayStatus.ENABLED,
                capabilities=[GatewayCapability.RATE_LIMITING],
            ),
            GatewayMetadata(
                gateway_id="disabled_gateway",
                name="Disabled Gateway",
                description="A disabled gateway",
                version="1.0.0",
                status=GatewayStatus.DISABLED,
                capabilities=[GatewayCapability.AUTHENTICATION],
            ),
        ]
        mock_discover.return_value = mock_gateways

        enabled_gateways = list_enabled_gateways()

        assert len(enabled_gateways) == 1
        assert enabled_gateways[0].gateway_id == "enabled_gateway"
        assert enabled_gateways[0].status == GatewayStatus.ENABLED

    @patch('acb.gateway.discovery._discover_gateways')
    def test_list_gateways_with_filters(self, mock_discover):
        """Test listing gateways with capability filters."""
        mock_gateways = [
            GatewayMetadata(
                gateway_id="rate_limit_gateway",
                name="Rate Limit Gateway",
                description="Gateway with rate limiting",
                version="1.0.0",
                status=GatewayStatus.ENABLED,
                capabilities=[GatewayCapability.RATE_LIMITING, GatewayCapability.ANALYTICS],
            ),
            GatewayMetadata(
                gateway_id="auth_gateway",
                name="Auth Gateway",
                description="Gateway with authentication",
                version="1.0.0",
                status=GatewayStatus.ENABLED,
                capabilities=[GatewayCapability.AUTHENTICATION, GatewayCapability.SECURITY],
            ),
        ]
        mock_discover.return_value = mock_gateways

        # Filter by rate limiting capability
        rate_limit_gateways = list_gateways(
            status_filter=GatewayStatus.ENABLED,
            capability_filter=GatewayCapability.RATE_LIMITING
        )

        assert len(rate_limit_gateways) == 1
        assert rate_limit_gateways[0].gateway_id == "rate_limit_gateway"

        # Filter by authentication capability
        auth_gateways = list_gateways(
            capability_filter=GatewayCapability.AUTHENTICATION
        )

        assert len(auth_gateways) == 1
        assert auth_gateways[0].gateway_id == "auth_gateway"

    @patch('acb.gateway.discovery._get_gateway_metadata')
    def test_get_gateway_descriptor(self, mock_get_metadata):
        """Test getting gateway descriptor."""
        mock_metadata = GatewayMetadata(
            gateway_id="test_gateway",
            name="Test Gateway",
            description="A test gateway",
            version="1.0.0",
            status=GatewayStatus.ENABLED,
            capabilities=[GatewayCapability.RATE_LIMITING],
        )
        mock_get_metadata.return_value = mock_metadata

        descriptor = get_gateway_descriptor("test_gateway")

        assert descriptor is not None
        assert descriptor.gateway_id == "test_gateway"
        assert descriptor.name == "Test Gateway"

    @patch('acb.gateway.discovery._get_gateway_metadata')
    def test_get_gateway_descriptor_not_found(self, mock_get_metadata):
        """Test getting descriptor for non-existent gateway."""
        mock_get_metadata.return_value = None

        descriptor = get_gateway_descriptor("nonexistent_gateway")

        assert descriptor is None

    @patch('acb.gateway.discovery._import_gateway_module')
    def test_import_gateway_success(self, mock_import):
        """Test successful gateway import."""
        mock_gateway_class = MagicMock()
        mock_import.return_value = mock_gateway_class

        gateway = import_gateway("test_gateway")

        assert gateway == mock_gateway_class
        mock_import.assert_called_once_with("test_gateway")

    @patch('acb.gateway.discovery._import_gateway_module')
    def test_import_gateway_failure(self, mock_import):
        """Test gateway import failure."""
        mock_import.side_effect = ImportError("Gateway module not found")

        with pytest.raises(ImportError):
            import_gateway("nonexistent_gateway")

    def test_gateway_metadata_validation(self):
        """Test gateway metadata validation."""
        # Test with valid data
        metadata = GatewayMetadata(
            gateway_id="valid_gateway",
            name="Valid Gateway",
            description="A valid gateway",
            version="1.0.0",
            status=GatewayStatus.ENABLED,
            capabilities=[GatewayCapability.RATE_LIMITING],
        )

        assert metadata.gateway_id == "valid_gateway"

        # Test with invalid status
        with pytest.raises(ValueError):
            GatewayMetadata(
                gateway_id="invalid_gateway",
                name="Invalid Gateway",
                description="An invalid gateway",
                version="1.0.0",
                status="invalid_status",  # Invalid status
                capabilities=[GatewayCapability.RATE_LIMITING],
            )

    def test_gateway_metadata_default_values(self):
        """Test gateway metadata default values."""
        metadata = GatewayMetadata(
            gateway_id="minimal_gateway",
            name="Minimal Gateway",
            description="A minimal gateway",
            version="1.0.0",
        )

        assert metadata.status == GatewayStatus.ENABLED  # Default status
        assert metadata.capabilities == []  # Default empty capabilities
        assert metadata.tags == []  # Default empty tags
        assert metadata.config == {}  # Default empty config

    def test_gateway_metadata_serialization(self):
        """Test gateway metadata serialization."""
        metadata = GatewayMetadata(
            gateway_id="serializable_gateway",
            name="Serializable Gateway",
            description="A gateway for serialization testing",
            version="1.0.0",
            status=GatewayStatus.ENABLED,
            capabilities=[GatewayCapability.RATE_LIMITING, GatewayCapability.AUTHENTICATION],
            tags=["test", "serialization"],
            config={"setting1": "value1", "setting2": 42},
        )

        # Convert to dict
        metadata_dict = metadata.model_dump()

        assert metadata_dict["gateway_id"] == "serializable_gateway"
        assert metadata_dict["status"] == "enabled"
        assert "rate_limiting" in metadata_dict["capabilities"]
        assert "authentication" in metadata_dict["capabilities"]
        assert metadata_dict["tags"] == ["test", "serialization"]
        assert metadata_dict["config"]["setting1"] == "value1"

        # Recreate from dict
        recreated_metadata = GatewayMetadata(**metadata_dict)
        assert recreated_metadata.gateway_id == metadata.gateway_id
        assert recreated_metadata.status == metadata.status
        assert recreated_metadata.capabilities == metadata.capabilities

    @patch('acb.gateway.discovery._discover_gateways')
    def test_list_gateways_empty_result(self, mock_discover):
        """Test listing gateways when none are found."""
        mock_discover.return_value = []

        gateways = list_available_gateways()

        assert len(gateways) == 0
        assert isinstance(gateways, list)

    @patch('acb.gateway.discovery._discover_gateways')
    def test_list_gateways_with_tags_filter(self, mock_discover):
        """Test listing gateways with tag filters."""
        mock_gateways = [
            GatewayMetadata(
                gateway_id="prod_gateway",
                name="Production Gateway",
                description="Production gateway",
                version="1.0.0",
                status=GatewayStatus.ENABLED,
                capabilities=[GatewayCapability.RATE_LIMITING],
                tags=["production", "stable"],
            ),
            GatewayMetadata(
                gateway_id="dev_gateway",
                name="Development Gateway",
                description="Development gateway",
                version="0.1.0",
                status=GatewayStatus.ENABLED,
                capabilities=[GatewayCapability.AUTHENTICATION],
                tags=["development", "experimental"],
            ),
        ]
        mock_discover.return_value = mock_gateways

        # Filter by production tag
        prod_gateways = list_gateways(tag_filter="production")

        assert len(prod_gateways) == 1
        assert prod_gateways[0].gateway_id == "prod_gateway"
        assert "production" in prod_gateways[0].tags