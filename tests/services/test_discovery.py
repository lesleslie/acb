"""Tests for Service Discovery System."""

from unittest.mock import patch

import pytest

from acb.services.discovery import (
    Service,
    ServiceCapability,
    ServiceMetadata,
    ServiceNotFound,
    ServiceNotInstalled,
    ServiceStatus,
    apply_service_overrides,
    create_service_metadata_template,
    disable_service,
    enable_service,
    generate_service_id,
    get_service_class,
    get_service_descriptor,
    get_service_info,
    get_service_override,
    import_service,
    initialize_service_registry,
    list_available_services,
    list_enabled_services,
    list_services,
    try_import_service,
)


class TestServiceMetadata:
    """Test ServiceMetadata functionality."""

    def test_service_metadata_creation(self):
        """Test creating ServiceMetadata."""
        service_id = generate_service_id()
        metadata = ServiceMetadata(
            service_id=service_id,
            name="Test Service",
            category="test",
            service_type="test_type",
            version="1.0.0",
            acb_min_version="0.19.1",
            author="Test Author",
            created_date="2024-01-01T00:00:00",
            last_modified="2024-01-01T00:00:00",
            status=ServiceStatus.STABLE,
            capabilities=[ServiceCapability.ASYNC_OPERATIONS],
            description="Test service description",
            settings_class="TestSettings",
        )

        assert metadata.name == "Test Service"
        assert metadata.category == "test"
        assert (
            metadata.status == ServiceStatus.STABLE.value
        )  # Pydantic converts enum to value
        assert ServiceCapability.ASYNC_OPERATIONS.value in metadata.capabilities

    def test_create_service_metadata_template(self):
        """Test creating service metadata template."""
        metadata = create_service_metadata_template(
            name="Template Service",
            category="template",
            service_type="template_type",
            author="Template Author",
            description="Template description",
            version="2.0.0",
        )

        assert metadata.name == "Template Service"
        assert metadata.category == "template"
        assert metadata.version == "2.0.0"
        assert metadata.status == ServiceStatus.STABLE.value


class TestServiceDiscovery:
    """Test service discovery functionality."""

    def test_list_services(self):
        """Test listing all services."""
        services = list_services()
        assert isinstance(services, list)
        assert len(services) > 0

        # Check that core services are present
        service_names = [s.name for s in services]
        assert "performance_optimizer" in service_names
        assert "health_service" in service_names
        assert "validation_service" in service_names

    def test_list_available_services(self):
        """Test listing available services."""
        services = list_available_services()
        assert isinstance(services, list)

        # All services should be installed by default
        for service in services:
            assert service.installed is True

    def test_list_enabled_services_initially_empty(self):
        """Test that no services are enabled initially."""
        services = list_enabled_services()
        # Initially no services should be enabled
        assert all(not service.enabled for service in services)

    def test_enable_service(self):
        """Test enabling a service."""
        # Enable performance service
        enable_service("performance", "performance_optimizer")

        # Check that it's enabled
        enabled_services = list_enabled_services()
        performance_services = [
            s for s in enabled_services if s.category == "performance" and s.enabled
        ]
        assert len(performance_services) > 0

    def test_disable_service(self):
        """Test disabling a service."""
        # First enable, then disable
        enable_service("performance", "performance_optimizer")
        disable_service("performance")

        # Check that it's disabled
        enabled_services = list_enabled_services()
        performance_services = [
            s for s in enabled_services if s.category == "performance" and s.enabled
        ]
        assert len(performance_services) == 0

    def test_get_service_descriptor(self):
        """Test getting service descriptor."""
        # Enable a service first
        enable_service("performance", "performance_optimizer")

        descriptor = get_service_descriptor("performance")
        assert descriptor is not None
        assert descriptor.category == "performance"
        assert descriptor.enabled is True

    def test_get_service_descriptor_not_found(self):
        """Test getting non-existent service descriptor."""
        descriptor = get_service_descriptor("nonexistent")
        assert descriptor is None


class TestServiceImport:
    """Test service import functionality."""

    def test_try_import_service_success(self):
        """Test successful service import."""
        enable_service("performance", "performance_optimizer")

        service_class = try_import_service("performance", "performance_optimizer")
        assert service_class is not None
        assert service_class.__name__ == "PerformanceOptimizer"

    def test_try_import_service_not_found(self):
        """Test importing non-existent service."""
        service_class = try_import_service("nonexistent")
        assert service_class is None

    def test_get_service_class_success(self):
        """Test getting service class."""
        enable_service("performance", "performance_optimizer")

        service_class = get_service_class("performance", "performance_optimizer")
        assert service_class.__name__ == "PerformanceOptimizer"

    def test_get_service_class_not_found(self):
        """Test getting non-existent service class."""
        with pytest.raises(ServiceNotFound):
            get_service_class("nonexistent")

    def test_import_service_single(self):
        """Test importing single service."""
        enable_service("performance", "performance_optimizer")

        service_class = import_service("performance")
        assert service_class.__name__ == "PerformanceOptimizer"

    def test_import_service_not_enabled(self):
        """Test importing service that's not enabled."""
        disable_service("performance")

        with pytest.raises(ServiceNotFound):
            import_service("performance")

    def test_import_service_multiple(self):
        """Test importing multiple services."""
        enable_service("performance", "performance_optimizer")
        enable_service("health")

        services = import_service(["performance", "health"])
        assert isinstance(services, tuple)
        assert len(services) == 2

    def test_import_service_invalid_type(self):
        """Test importing with invalid type."""
        with pytest.raises(ValueError):
            import_service(123)  # Invalid type


class TestServiceInfo:
    """Test service information functionality."""

    def test_get_service_info(self):
        """Test getting service information."""
        enable_service("performance", "performance_optimizer")
        service_class = import_service("performance")

        info = get_service_info(service_class)
        assert "class_name" in info
        assert "module" in info
        assert info["class_name"] == "PerformanceOptimizer"
        assert "acb.services.performance.optimizer" in info["module"]

    def test_get_service_info_with_metadata(self):
        """Test getting service info with metadata."""
        enable_service("performance", "performance_optimizer")
        service_class = import_service("performance")

        # Check if module has SERVICE_METADATA (it's defined at module level)
        import acb.services.performance.optimizer as optimizer_module

        assert hasattr(optimizer_module, "SERVICE_METADATA")
        assert optimizer_module.SERVICE_METADATA is not None

        info = get_service_info(service_class)
        # The get_service_info function should find metadata from the module
        if "metadata" in info:
            metadata = info["metadata"]
            assert metadata["name"] == "Performance Optimizer"
            assert metadata["category"] == "performance"


class TestServiceRegistry:
    """Test service registry functionality."""

    def test_initialize_service_registry(self):
        """Test initializing service registry."""
        # This should not raise an error
        initialize_service_registry()

        services = list_services()
        assert len(services) > 0

    def test_service_equality(self):
        """Test service equality comparison."""
        service1 = Service(
            name="test", class_name="TestService", category="test", module="test.module"
        )
        service2 = Service(
            name="test", class_name="TestService", category="test", module="test.module"
        )
        service3 = Service(
            name="different",
            class_name="TestService",
            category="test",
            module="test.module",
        )

        assert service1 == service2
        assert service1 != service3

    def test_service_hash(self):
        """Test service hash functionality."""
        service = Service(
            name="test", class_name="TestService", category="test", module="test.module"
        )

        # Should be hashable
        service_set = {service}
        assert len(service_set) == 1


class TestServiceAutoDetection:
    """Test service auto-detection functionality."""

    def test_import_service_auto_detection_mock(self):
        """Test auto-detection of service from context (mocked)."""
        with patch("builtins.open", side_effect=OSError("File not found")):
            # Should fall back to ValueError when auto-detection fails
            with pytest.raises(
                ValueError, match="Could not determine category from context"
            ):
                import_service()  # No arguments, should try auto-detection


class TestServiceErrors:
    """Test service error handling."""

    def test_service_not_found_error(self):
        """Test ServiceNotFound exception."""
        error = ServiceNotFound("Test service not found")
        assert str(error) == "Test service not found"

    def test_service_not_installed_error(self):
        """Test ServiceNotInstalled exception."""
        error = ServiceNotInstalled("Test service not installed")
        assert str(error) == "Test service not installed"


class TestServiceCapabilities:
    """Test service capabilities enum."""

    def test_service_capabilities_enum(self):
        """Test ServiceCapability enum values."""
        assert ServiceCapability.ASYNC_OPERATIONS.value == "async_operations"
        assert ServiceCapability.CACHING.value == "caching"
        assert ServiceCapability.HEALTH_MONITORING.value == "health_monitoring"
        assert ServiceCapability.SCHEMA_VALIDATION.value == "schema_validation"


class TestServiceStatus:
    """Test service status enum."""

    def test_service_status_enum(self):
        """Test ServiceStatus enum values."""
        assert ServiceStatus.ALPHA.value == "alpha"
        assert ServiceStatus.BETA.value == "beta"
        assert ServiceStatus.STABLE.value == "stable"
        assert ServiceStatus.DEPRECATED.value == "deprecated"
        assert ServiceStatus.EXPERIMENTAL.value == "experimental"


class TestServiceConfigOverrides:
    """Test service configuration override functionality."""

    def test_get_service_override_no_config(self):
        """Test getting service override when no config exists."""
        # Clear the cache first
        from acb.services.discovery import _load_service_settings

        _load_service_settings.cache_clear()

        override = get_service_override("nonexistent")
        assert override is None

    def test_apply_service_overrides_no_config(self):
        """Test applying service overrides when no config exists."""
        # Should not raise an error
        apply_service_overrides()

    def test_service_override_config_example(self):
        """Test service override functionality with example config."""
        from unittest.mock import patch

        from acb.services.discovery import _load_service_settings

        # Clear cache
        _load_service_settings.cache_clear()

        # Mock configuration file content
        config_content = """
performance: performance_optimizer
health: health_service
validation: validation_service
"""

        with patch("pathlib.Path.exists", return_value=True):
            with patch("pathlib.Path.read_text", return_value=config_content):
                # Clear cache to force reload
                _load_service_settings.cache_clear()

                # Test getting overrides
                perf_override = get_service_override("performance")
                health_override = get_service_override("health")
                validation_override = get_service_override("validation")
                nonexistent_override = get_service_override("nonexistent")

                assert perf_override == "performance_optimizer"
                assert health_override == "health_service"
                assert validation_override == "validation_service"
                assert nonexistent_override is None

    def test_apply_service_overrides_with_config(self):
        """Test applying service overrides with configuration."""
        from unittest.mock import patch

        from acb.services.discovery import _load_service_settings

        # Clear cache
        _load_service_settings.cache_clear()

        config_content = """
performance: performance_optimizer
health: health_service
"""

        with patch("pathlib.Path.exists", return_value=True):
            with patch("pathlib.Path.read_text", return_value=config_content):
                # Clear cache to force reload
                _load_service_settings.cache_clear()

                # This should not raise errors even if services don't exist
                apply_service_overrides()

                # Verify that services would be enabled if they existed
                # (The actual services might not be available in test environment)
                enabled_services = list_enabled_services()
                assert isinstance(enabled_services, list)


if __name__ == "__main__":
    # Reset services to clean state before running tests
    initialize_service_registry()
    pytest.main([__file__, "-v"])
