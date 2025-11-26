"""Tests for Events discovery system functionality."""

from unittest.mock import Mock, patch
from uuid import UUID

import pytest

from acb.events.discovery import (
    EventCapability,
    EventHandlerDescriptor,
    EventHandlerNotFound,
    EventHandlerNotInstalled,
    EventHandlerStatus,
    EventMetadata,
    apply_event_handler_overrides,
    core_event_handlers,
    create_event_metadata_template,
    disable_event_handler,
    enable_event_handler,
    event_handler_registry,
    generate_event_handler_id,
    get_event_handler_class,
    get_event_handler_descriptor,
    get_event_handler_info,
    get_event_handler_override,
    import_event_handler,
    list_available_event_handlers,
    list_enabled_event_handlers,
    list_event_handlers,
    list_event_handlers_by_capability,
    register_event_handlers,
    try_import_event_handler,
)


class TestEventCapability:
    """Test EventCapability enumeration."""

    def test_event_capabilities(self):
        """Test all event capabilities are available."""
        capabilities = [
            # Core capabilities
            EventCapability.ASYNC_PROCESSING,
            EventCapability.BATCH_PROCESSING,
            EventCapability.SYNC_PROCESSING,
            EventCapability.STREAMING_PROCESSING,
            # Routing capabilities
            EventCapability.TYPE_FILTERING,
            EventCapability.CONTENT_FILTERING,
            EventCapability.PRIORITY_HANDLING,
            EventCapability.ROUTING_KEY_SUPPORT,
            # Delivery capabilities
            EventCapability.AT_LEAST_ONCE,
            EventCapability.EXACTLY_ONCE,
            EventCapability.FIRE_AND_FORGET,
            EventCapability.ORDERED_DELIVERY,
            # Error handling
            EventCapability.RETRY_LOGIC,
            EventCapability.DEAD_LETTER_QUEUE,
            EventCapability.CIRCUIT_BREAKER,
            # Integration
            EventCapability.MESSAGE_QUEUE_INTEGRATION,
            EventCapability.DATABASE_PERSISTENCE,
            # Monitoring
            EventCapability.HEALTH_MONITORING,
            EventCapability.METRICS_COLLECTION,
            EventCapability.TRACING,
            # Security
            EventCapability.RATE_LIMITING,
            EventCapability.ACCESS_CONTROL,
        ]

        for capability in capabilities:
            assert isinstance(capability.value, str)
            assert len(capability.value) > 0


class TestEventHandlerStatus:
    """Test EventHandlerStatus enumeration."""

    def test_event_handler_statuses(self):
        """Test all event handler statuses are available."""
        statuses = [
            EventHandlerStatus.ALPHA,
            EventHandlerStatus.BETA,
            EventHandlerStatus.STABLE,
            EventHandlerStatus.DEPRECATED,
            EventHandlerStatus.EXPERIMENTAL,
        ]

        for status in statuses:
            assert isinstance(status.value, str)
            assert len(status.value) > 0


class TestEventMetadata:
    """Test EventMetadata functionality."""

    def test_event_metadata_creation(self):
        """Test creating event metadata."""
        metadata = EventMetadata(
            handler_id=generate_event_handler_id(),
            name="Test Publisher",
            category="publisher",
            handler_type="messaging",
            version="1.0.0",
            acb_min_version="0.19.1",
            author="Test Author",
            created_date="2024-01-01",
            last_modified="2024-01-01",
            status=EventHandlerStatus.STABLE,
            description="Test event handler",
            settings_class="TestSettings",
        )

        assert isinstance(metadata.handler_id, UUID)
        assert metadata.name == "Test Publisher"
        assert metadata.category == "publisher"
        assert metadata.handler_type == "messaging"
        assert metadata.version == "1.0.0"
        assert metadata.acb_min_version == "0.19.1"
        assert metadata.author == "Test Author"
        assert metadata.status == EventHandlerStatus.STABLE.value
        assert metadata.description == "Test event handler"
        assert metadata.settings_class == "TestSettings"

    def test_event_metadata_with_capabilities(self):
        """Test event metadata with capabilities."""
        capabilities = [
            EventCapability.MESSAGE_QUEUE_INTEGRATION,
            EventCapability.TYPE_FILTERING,
            EventCapability.ASYNC_PROCESSING,
        ]

        metadata = EventMetadata(
            handler_id=generate_event_handler_id(),
            name="Advanced Publisher",
            category="publisher",
            handler_type="messaging",
            version="2.0.0",
            acb_min_version="0.19.1",
            author="Test Author",
            created_date="2024-01-01",
            last_modified="2024-01-01",
            status=EventHandlerStatus.STABLE,
            capabilities=capabilities,
            description="Advanced event handler",
            settings_class="AdvancedSettings",
        )

        # Capabilities are stored as values due to use_enum_values=True
        assert metadata.capabilities == [c.value for c in capabilities]
        assert EventCapability.MESSAGE_QUEUE_INTEGRATION.value in metadata.capabilities
        assert EventCapability.TYPE_FILTERING.value in metadata.capabilities
        assert EventCapability.ASYNC_PROCESSING.value in metadata.capabilities

    def test_event_metadata_with_packages(self):
        """Test event metadata with package requirements."""
        required_packages = ["redis>=4.0.0", "aioredis>=2.0.0"]
        optional_packages = {
            "msgpack": "High-performance serialization",
            "ujson": "Fast JSON serialization",
        }

        metadata = EventMetadata(
            handler_id=generate_event_handler_id(),
            name="Redis Publisher",
            category="publisher",
            handler_type="messaging",
            version="1.0.0",
            acb_min_version="0.19.1",
            author="Test Author",
            created_date="2024-01-01",
            last_modified="2024-01-01",
            status=EventHandlerStatus.STABLE,
            required_packages=required_packages,
            optional_packages=optional_packages,
            description="Redis-based event handler",
            settings_class="RedisSettings",
        )

        assert metadata.required_packages == required_packages
        assert metadata.optional_packages == optional_packages


class TestEventHandlerDescriptor:
    """Test EventHandlerDescriptor functionality."""

    def test_handler_descriptor_creation(self):
        """Test creating an event handler descriptor."""
        metadata = create_event_metadata_template(
            "Test Publisher",
            "publisher",
            "messaging",
            "Test Author",
            "Test event publisher",
        )

        descriptor = EventHandlerDescriptor(
            name="test_publisher",
            class_name="TestPublisher",
            category="publisher",
            module="acb.events.test_publisher",
            enabled=True,
            installed=True,
            metadata=metadata,
        )

        assert descriptor.name == "test_publisher"
        assert descriptor.class_name == "TestPublisher"
        assert descriptor.category == "publisher"
        assert descriptor.module == "acb.events.test_publisher"
        assert descriptor.enabled is True
        assert descriptor.installed is True
        assert descriptor.metadata == metadata

    def test_handler_descriptor_hashing(self):
        """Test event handler descriptor hashing."""
        metadata = create_event_metadata_template(
            "Test Publisher",
            "publisher",
            "messaging",
            "Test Author",
            "Test event publisher",
        )

        descriptor1 = EventHandlerDescriptor(
            name="test_publisher",
            class_name="TestPublisher",
            category="publisher",
            module="acb.events.test_publisher",
            metadata=metadata,
        )

        descriptor2 = EventHandlerDescriptor(
            name="test_publisher",
            class_name="TestPublisher",
            category="publisher",
            module="acb.events.test_publisher",
            metadata=metadata,
        )

        # Same descriptors should be equal and have same hash
        assert descriptor1 == descriptor2
        assert hash(descriptor1) == hash(descriptor2)

        # Different descriptors should not be equal
        descriptor3 = EventHandlerDescriptor(
            name="different_publisher",
            class_name="DifferentPublisher",
            category="publisher",
            module="acb.events.different_publisher",
        )

        assert descriptor1 != descriptor3
        assert hash(descriptor1) != hash(descriptor3)


class TestEventHandlerIdGeneration:
    """Test event handler ID generation."""

    def test_generate_event_handler_id(self):
        """Test generating event handler IDs."""
        handler_id = generate_event_handler_id()

        assert isinstance(handler_id, UUID)
        assert handler_id.version in [4, 7]  # UUID4 or UUID7

    def test_unique_handler_ids(self):
        """Test that generated handler IDs are unique."""
        id1 = generate_event_handler_id()
        id2 = generate_event_handler_id()

        assert id1 != id2


class TestEventMetadataTemplate:
    """Test event metadata template creation."""

    def test_create_basic_template(self):
        """Test creating a basic metadata template."""
        template = create_event_metadata_template(
            "Test Publisher",
            "publisher",
            "messaging",
            "Test Author",
            "Test event publisher",
        )

        assert template.name == "Test Publisher"
        assert template.category == "publisher"
        assert template.handler_type == "messaging"
        assert template.author == "Test Author"
        assert template.description == "Test event publisher"
        assert template.version == "1.0.0"  # Default
        assert template.acb_min_version == "0.19.1"  # Default
        assert template.status == EventHandlerStatus.STABLE.value  # Default
        assert (
            template.settings_class == "Test PublisherSettings"
        )  # Auto-generated from name

    def test_create_template_with_kwargs(self):
        """Test creating a template with additional kwargs."""
        template = create_event_metadata_template(
            "Advanced Publisher",
            "publisher",
            "messaging",
            "Advanced Author",
            "Advanced event publisher",
            version="2.0.0",
            status=EventHandlerStatus.BETA,
            capabilities=[EventCapability.MESSAGE_QUEUE_INTEGRATION],
            required_packages=["redis>=4.0.0"],
        )

        assert template.version == "2.0.0"
        assert template.status == EventHandlerStatus.BETA.value
        assert template.capabilities == [
            EventCapability.MESSAGE_QUEUE_INTEGRATION.value
        ]
        assert template.required_packages == ["redis>=4.0.0"]


class TestEventHandlerRegistry:
    """Test event handler registry functionality."""

    def test_core_event_handlers_exist(self):
        """Test that core event handlers are defined."""
        assert len(core_event_handlers) > 0

        # Check that event publisher and subscriber are in core handlers
        handler_names = [handler.name for handler in core_event_handlers]
        assert "event_publisher" in handler_names
        assert "event_subscriber" in handler_names

    def test_list_event_handlers(self):
        """Test listing all event handlers."""
        handlers = list_event_handlers()

        assert len(handlers) > 0
        assert all(isinstance(handler, EventHandlerDescriptor) for handler in handlers)

    def test_list_available_event_handlers(self):
        """Test listing available (installed) event handlers."""
        available_handlers = list_available_event_handlers()

        assert len(available_handlers) >= 0
        assert all(handler.installed for handler in available_handlers)

    def test_list_enabled_event_handlers(self):
        """Test listing enabled event handlers."""
        enabled_handlers = list_enabled_event_handlers()

        assert len(enabled_handlers) >= 0
        assert all(handler.enabled for handler in enabled_handlers)

    def test_list_event_handlers_by_capability(self):
        """Test listing event handlers by capability."""
        # Test with a common capability
        async_handlers = list_event_handlers_by_capability(
            EventCapability.ASYNC_PROCESSING
        )

        assert len(async_handlers) >= 0
        for handler in async_handlers:
            if handler.metadata:
                assert EventCapability.ASYNC_PROCESSING in handler.metadata.capabilities

    def test_get_event_handler_descriptor(self):
        """Test getting event handler descriptor by category."""
        # This might return None if no handlers are enabled
        descriptor = get_event_handler_descriptor("publisher")

        if descriptor:
            assert descriptor.category == "publisher"
            assert descriptor.enabled is True

    def test_get_event_handler_descriptor_not_found(self):
        """Test getting non-existent event handler descriptor."""
        descriptor = get_event_handler_descriptor("non_existent_category")
        assert descriptor is None


class TestEventHandlerImport:
    """Test event handler import functionality."""

    def test_try_import_event_handler_not_found(self):
        """Test trying to import non-existent event handler."""
        handler_class = try_import_event_handler("non_existent_category")
        assert handler_class is None

    def test_get_event_handler_class_not_found(self):
        """Test getting non-existent event handler class."""
        with pytest.raises(EventHandlerNotFound):
            get_event_handler_class("non_existent_category")

    def test_import_event_handler_not_found(self):
        """Test importing non-existent event handler."""
        with pytest.raises(EventHandlerNotFound):
            import_event_handler("non_existent_category")

    def test_import_event_handler_list_not_found(self):
        """Test importing list with non-existent event handler."""
        with pytest.raises(EventHandlerNotFound):
            import_event_handler(["publisher", "non_existent_category"])

    def test_import_event_handler_invalid_type(self):
        """Test importing with invalid type."""
        with pytest.raises(ValueError):
            import_event_handler(123)  # Invalid type

    @patch("acb.events.discovery.try_import_event_handler")
    def test_import_event_handler_with_mock(self, mock_try_import):
        """Test importing event handler with mocked import."""
        # Mock a successful import
        mock_class = Mock()
        mock_try_import.return_value = mock_class

        # Mock the descriptor lookup
        with patch(
            "acb.events.discovery.get_event_handler_descriptor"
        ) as mock_get_descriptor:
            mock_descriptor = Mock()
            mock_descriptor.name = "test_publisher"
            mock_get_descriptor.return_value = mock_descriptor

            result = import_event_handler("publisher")
            assert result == mock_class

    @patch("acb.events.discovery.try_import_event_handler")
    def test_import_multiple_event_handlers_with_mock(self, mock_try_import):
        """Test importing multiple event handlers with mocked import."""
        # Mock successful imports
        mock_class1 = Mock()
        mock_class2 = Mock()
        mock_try_import.side_effect = [mock_class1, mock_class2]

        result = import_event_handler(["publisher", "subscriber"])
        assert result == (mock_class1, mock_class2)

    @patch("acb.events.discovery.try_import_event_handler")
    def test_import_single_handler_from_list_with_mock(self, mock_try_import):
        """Test importing single handler from list with mocked import."""
        mock_class = Mock()
        mock_try_import.return_value = mock_class

        result = import_event_handler(["publisher"])
        assert result == mock_class  # Single item, not tuple


class TestEventHandlerManagement:
    """Test event handler enable/disable functionality."""

    def test_enable_event_handler(self):
        """Test enabling an event handler."""
        # This function modifies the registry state
        enable_event_handler("publisher", "event_publisher")

        # Check if the handler is enabled
        descriptor = get_event_handler_descriptor("publisher")
        if descriptor:
            assert descriptor.enabled is True

    def test_disable_event_handler(self):
        """Test disabling an event handler."""
        # First enable, then disable
        enable_event_handler("publisher", "event_publisher")
        disable_event_handler("publisher")

        # Check if the handler is disabled
        descriptor = get_event_handler_descriptor("publisher")
        if descriptor:
            assert descriptor.enabled is False


class TestEventHandlerInfo:
    """Test event handler information retrieval."""

    def test_get_event_handler_info(self):
        """Test getting event handler information."""

        # Create a mock class with metadata
        class MockEventHandler:
            EVENT_METADATA = create_event_metadata_template(
                "Mock Handler",
                "mock",
                "test",
                "Test Author",
                "Mock event handler for testing",
            )

        info = get_event_handler_info(MockEventHandler)

        assert info["class_name"] == "MockEventHandler"
        assert "module" in info
        assert "metadata" in info
        assert isinstance(info["metadata"], dict)

    def test_get_event_handler_info_without_metadata(self):
        """Test getting info for handler without metadata."""

        class PlainEventHandler:
            pass

        info = get_event_handler_info(PlainEventHandler)

        assert info["class_name"] == "PlainEventHandler"
        assert "module" in info
        assert "metadata" not in info


class TestEventHandlerOverrides:
    """Test event handler override functionality."""

    @patch("acb.events.discovery._load_event_handler_settings")
    def test_get_event_handler_override(self, mock_load_settings):
        """Test getting event handler override."""
        mock_load_settings.return_value = {
            "publisher": "redis_publisher",
            "subscriber": "kafka_subscriber",
        }

        override = get_event_handler_override("publisher")
        assert override == "redis_publisher"

        override = get_event_handler_override("non_existent")
        assert override is None

    @patch("acb.events.discovery._load_event_handler_settings")
    def test_apply_event_handler_overrides(self, mock_load_settings):
        """Test applying event handler overrides."""
        mock_load_settings.return_value = {
            "publisher": "redis_publisher",
            "subscriber": "kafka_subscriber",
        }

        # Apply overrides (this would normally enable specific handlers)
        apply_event_handler_overrides()

        # The function should have been called to load settings
        mock_load_settings.assert_called_once()

    @patch("acb.events.discovery._load_event_handler_settings")
    def test_apply_empty_overrides(self, mock_load_settings):
        """Test applying empty event handler overrides."""
        mock_load_settings.return_value = {}

        # Should not raise any errors
        apply_event_handler_overrides()

        mock_load_settings.assert_called_once()


class TestEventHandlerRegistration:
    """Test event handler registration functionality."""

    def test_register_event_handlers(self):
        """Test registering event handlers from a path."""
        # This function currently has no implementation
        # Just test that it doesn't raise errors
        register_event_handlers("/some/path")
        register_event_handlers()  # None path


class TestEventHandlerExceptions:
    """Test event handler exception classes."""

    def test_event_handler_not_found(self):
        """Test EventHandlerNotFound exception."""
        exception = EventHandlerNotFound("Handler not found")
        assert str(exception) == "Handler not found"
        assert isinstance(exception, Exception)

    def test_event_handler_not_installed(self):
        """Test EventHandlerNotInstalled exception."""
        exception = EventHandlerNotInstalled("Handler not installed")
        assert str(exception) == "Handler not installed"
        assert isinstance(exception, Exception)


class TestEventHandlerSettings:
    """Test event handler settings loading."""

    @patch("acb.events.discovery.yaml")
    @patch("acb.events.discovery.Path")
    def test_load_event_handler_settings_success(self, mock_path, mock_yaml):
        """Test successful loading of event handler settings."""
        # Mock file existence and content
        mock_file = Mock()
        mock_file.exists.return_value = True
        mock_file.read_text.return_value = "publisher: redis_publisher"
        mock_path.return_value = mock_file

        mock_yaml.safe_load.return_value = {"publisher": "redis_publisher"}

        from acb.events.discovery import _load_event_handler_settings

        # Clear the cache first
        _load_event_handler_settings.cache_clear()

        settings = _load_event_handler_settings()
        assert settings == {"publisher": "redis_publisher"}

    @patch("acb.events.discovery.yaml")
    @patch("acb.events.discovery.Path")
    def test_load_event_handler_settings_no_file(self, mock_path, mock_yaml):
        """Test loading settings when no file exists."""
        # Mock no file existence
        mock_file = Mock()
        mock_file.exists.return_value = False
        mock_path.return_value = mock_file

        from acb.events.discovery import _load_event_handler_settings

        # Clear the cache first
        _load_event_handler_settings.cache_clear()

        settings = _load_event_handler_settings()
        assert settings == {}

    @patch("acb.events.discovery.yaml")
    @patch("acb.events.discovery.Path")
    def test_load_event_handler_settings_yaml_error(self, mock_path, mock_yaml):
        """Test loading settings with YAML error."""
        # Mock file existence but YAML error
        mock_file = Mock()
        mock_file.exists.return_value = True
        mock_file.read_text.return_value = "invalid: yaml: content:"
        mock_path.return_value = mock_file

        mock_yaml.safe_load.side_effect = Exception("Invalid YAML")

        from acb.events.discovery import _load_event_handler_settings

        # Clear the cache first
        _load_event_handler_settings.cache_clear()

        # Should return empty dict on error
        settings = _load_event_handler_settings()
        assert settings == {}


class TestEventHandlerRegistryState:
    """Test event handler registry state management."""

    def test_registry_initialization(self):
        """Test that registry is properly initialized."""
        # Registry should be initialized with core handlers
        registry = event_handler_registry.get()
        assert len(registry) > 0

        # Should contain core event handlers
        handler_names = [handler.name for handler in registry]
        assert "event_publisher" in handler_names
        assert "event_subscriber" in handler_names

    def test_registry_context_isolation(self):
        """Test that registry changes are properly isolated."""
        # Get current registry state
        original_registry = event_handler_registry.get()
        original_length = len(original_registry)

        # Create a new context (this is simplified - actual ContextVar usage is more complex)
        # In real usage, this would be in different async contexts
        new_handler = EventHandlerDescriptor(
            name="test_handler",
            class_name="TestHandler",
            category="test",
            module="test.module",
        )

        # Modify registry
        modified_registry = original_registry + [new_handler]
        event_handler_registry.set(modified_registry)

        # Check modification
        current_registry = event_handler_registry.get()
        assert len(current_registry) == original_length + 1

        # Reset to original
        event_handler_registry.set(original_registry)
        assert len(event_handler_registry.get()) == original_length
