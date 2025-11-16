"""Tests for the ACB MCP registry module."""

from unittest.mock import Mock, patch

import pytest

from acb.mcp.registry import ComponentRegistry


class TestComponentRegistry:
    """Test the ComponentRegistry class."""

    def test_initialization(self) -> None:
        """Test basic initialization of ComponentRegistry."""
        registry = ComponentRegistry()

        assert registry._actions == {}
        assert registry._adapters == {}
        assert registry._services == {}
        assert registry._events == {}
        assert registry._initialized is False
        assert hasattr(registry, "config")
        assert hasattr(registry, "logger")

    @pytest.mark.asyncio
    async def test_initialize_first_time(self) -> None:
        """Test initializing the registry for the first time."""
        registry = ComponentRegistry()

        # Mock the dependencies to avoid actual dependency injection
        with (
            patch.object(registry, "logger") as mock_logger,
            patch("acb.mcp.registry.import_adapter"),
            patch("acb.mcp.registry.depends"),
        ):
            # Mock the actions imports to work without actual modules
            mock_compress = Mock()
            mock_encode = Mock()
            mock_hash = Mock()

            with (
                patch.dict(
                    "sys.modules",
                    {
                        "acb.actions.compress": mock_compress,
                        "acb.actions.encode": mock_encode,
                        "acb.actions.hash": mock_hash,
                    },
                ),
                patch(
                    "builtins.__import__",
                    side_effect=[
                        Mock(),  # For acb.actions
                        mock_compress,  # For acb.actions.compress
                        Mock(),  # For acb.actions
                        mock_encode,  # For acb.actions.encode
                        Mock(),  # For acb.actions
                        mock_hash,  # For acb.actions.hash
                    ],
                ),
            ):
                await registry.initialize()

                assert registry._initialized is True
                assert "compress" in registry._actions
                assert "encode" in registry._actions
                assert "hash" in registry._actions
                mock_logger.info.assert_called()

    @pytest.mark.asyncio
    async def test_initialize_already_initialized(self) -> None:
        """Test that initialize is skipped when already initialized."""
        registry = ComponentRegistry()
        registry._initialized = True

        with patch.object(registry, "logger") as mock_logger:
            await registry.initialize()
            # The logger should not have been called since it was already initialized
            mock_logger.info.assert_not_called()

    @pytest.mark.asyncio
    async def test_register_builtin_actions_success(self) -> None:
        """Test registering builtin actions successfully."""
        registry = ComponentRegistry()

        # Mock action modules
        mock_compress = Mock()
        mock_encode = Mock()
        mock_hash = Mock()

        with (
            patch("sys.modules", {}),  # Clear the sys.modules cache
            patch(
                "builtins.__import__",
                side_effect=lambda name, *args, **kwargs: {
                    "acb.actions.compress": mock_compress,
                    "acb.actions.encode": mock_encode,
                    "acb.actions.hash": mock_hash,
                }.get(name, Mock()),
            ),
            patch.object(registry, "logger") as mock_logger,
        ):
            await registry._register_builtin_actions()

            assert "compress" in registry._actions
            assert "encode" in registry._actions
            assert "hash" in registry._actions
            mock_logger.debug.assert_called()

    @pytest.mark.asyncio
    async def test_register_builtin_actions_failure(self) -> None:
        """Test handling failures during action registration."""
        registry = ComponentRegistry()

        with (
            patch("builtins.__import__", side_effect=ImportError("Module not found")),
            patch.object(registry, "logger") as mock_logger,
        ):
            await registry._register_builtin_actions()
            mock_logger.warning.assert_called()

    @pytest.mark.asyncio
    async def test_register_configured_adapters(self) -> None:
        """Test registering configured adapters."""
        registry = ComponentRegistry()

        # Mock config to have adapter configurations
        mock_config = Mock()
        mock_config.adapters = {"cache": "memory", "storage": "file"}
        registry.config = mock_config

        # Mock adapter imports and dependencies
        mock_cache_adapter = Mock()
        mock_storage_adapter = Mock()

        with (
            patch(
                "acb.mcp.registry.import_adapter",
                side_effect=[mock_cache_adapter, mock_storage_adapter],
            ),
            patch("acb.mcp.registry.depends") as mock_depends,
            patch.object(registry, "logger") as mock_logger,
        ):
            mock_depends.get.side_effect = [mock_cache_adapter, mock_storage_adapter]

            await registry._register_configured_adapters()

            assert "cache" in registry._adapters
            assert "storage" in registry._adapters
            mock_logger.debug.assert_called()

    @pytest.mark.asyncio
    async def test_register_configured_adapters_with_error(self) -> None:
        """Test handling errors when registering adapters."""
        registry = ComponentRegistry()

        # Mock config to have adapter configurations
        mock_config = Mock()
        mock_config.adapters = {"invalid_adapter": "invalid"}
        registry.config = mock_config

        with (
            patch(
                "acb.mcp.registry.import_adapter", side_effect=ImportError("Not found")
            ),
            patch.object(registry, "logger") as mock_logger,
        ):
            await registry._register_configured_adapters()
            mock_logger.warning.assert_called()

    @pytest.mark.asyncio
    async def test_register_services_placeholder(self) -> None:
        """Test the service registration placeholder."""
        registry = ComponentRegistry()

        with patch.object(registry, "logger") as mock_logger:
            await registry._register_services()
            mock_logger.debug.assert_called_with("Services registration placeholder")

    def test_get_actions(self) -> None:
        """Test getting all actions."""
        registry = ComponentRegistry()
        registry._actions = {"test": Mock()}

        actions = registry.get_actions()
        assert "test" in actions
        # Should be a copy, not the original dict
        assert actions is not registry._actions

    def test_get_action(self) -> None:
        """Test getting a specific action."""
        registry = ComponentRegistry()
        registry._actions = {"test": "value"}

        action = registry.get_action("test")
        assert action == "value"

        missing_action = registry.get_action("missing")
        assert missing_action is None

    def test_get_adapters(self) -> None:
        """Test getting all adapters."""
        registry = ComponentRegistry()
        registry._adapters = {"test": Mock()}

        adapters = registry.get_adapters()
        assert "test" in adapters
        # Should be a copy, not the original dict
        assert adapters is not registry._adapters

    def test_get_adapter(self) -> None:
        """Test getting a specific adapter."""
        registry = ComponentRegistry()
        registry._adapters = {"test": "value"}

        adapter = registry.get_adapter("test")
        assert adapter == "value"

        missing_adapter = registry.get_adapter("missing")
        assert missing_adapter is None

    def test_get_services(self) -> None:
        """Test getting all services."""
        registry = ComponentRegistry()
        registry._services = {"test": Mock()}

        services = registry.get_services()
        assert "test" in services
        # Should be a copy, not the original dict
        assert services is not registry._services

    def test_get_service(self) -> None:
        """Test getting a specific service."""
        registry = ComponentRegistry()
        registry._services = {"test": "value"}

        service = registry.get_service("test")
        assert service == "value"

        missing_service = registry.get_service("missing")
        assert missing_service is None

    def test_get_events(self) -> None:
        """Test getting all events."""
        registry = ComponentRegistry()
        registry._events = {"test": Mock()}

        events = registry.get_events()
        assert "test" in events
        # Should be a copy, not the original dict
        assert events is not registry._events

    def test_get_event(self) -> None:
        """Test getting a specific event."""
        registry = ComponentRegistry()
        registry._events = {"test": "value"}

        event = registry.get_event("test")
        assert event == "value"

        missing_event = registry.get_event("missing")
        assert missing_event is None

    @pytest.mark.asyncio
    async def test_cleanup(self) -> None:
        """Test cleaning up the registry."""
        registry = ComponentRegistry()
        registry._actions = {"test": "value"}
        registry._adapters = {"test": "value"}
        registry._services = {"test": "value"}
        registry._events = {"test": "value"}
        registry._initialized = True

        with patch.object(registry, "logger") as mock_logger:
            await registry.cleanup()

            assert registry._actions == {}
            assert registry._adapters == {}
            assert registry._services == {}
            assert registry._events == {}
            assert registry._initialized is False
            mock_logger.info.assert_called_with("ACB Component Registry cleaned up")
