"""Tests for the cleanup module."""

import logging
from unittest.mock import AsyncMock, MagicMock

import asyncio
import pytest

from acb.cleanup import CleanupMixin


class TestCleanupMixin:
    """Test CleanupMixin class."""

    class MockAdapter(CleanupMixin):
        """Mock adapter class for testing."""

        def __init__(self) -> None:
            super().__init__()

    @pytest.fixture
    def cleanup_mixin(self) -> CleanupMixin:
        """Create a CleanupMixin instance for testing."""
        return self.MockAdapter()

    def test_initialization(self, cleanup_mixin: CleanupMixin) -> None:
        """Test mixin initialization."""
        assert isinstance(cleanup_mixin._resources, list)
        assert len(cleanup_mixin._resources) == 0
        assert cleanup_mixin._cleaned_up is False
        assert cleanup_mixin._cleanup_lock is None

    def test_register_resource(self, cleanup_mixin: CleanupMixin) -> None:
        """Test registering resources."""
        resource1 = MagicMock()
        resource2 = MagicMock()

        cleanup_mixin.register_resource(resource1)
        assert len(cleanup_mixin._resources) == 1
        assert cleanup_mixin._resources[0] is resource1

        # Register the same resource again - should not duplicate
        cleanup_mixin.register_resource(resource1)
        assert len(cleanup_mixin._resources) == 1

        # Register a different resource
        cleanup_mixin.register_resource(resource2)
        assert len(cleanup_mixin._resources) == 2
        assert cleanup_mixin._resources[1] is resource2

    @pytest.mark.asyncio
    async def test_cleanup_resource_with_close_method(
        self, cleanup_mixin: CleanupMixin
    ) -> None:
        """Test cleaning up a resource with close method."""
        resource = MagicMock()
        resource.close = MagicMock()

        await cleanup_mixin.cleanup_resource(resource)
        resource.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_cleanup_resource_with_aclose_method(
        self, cleanup_mixin: CleanupMixin
    ) -> None:
        """Test cleaning up a resource with aclose method."""
        resource = AsyncMock()
        resource.close = None  # Remove sync close method
        resource.aclose = AsyncMock()

        await cleanup_mixin.cleanup_resource(resource)
        resource.aclose.assert_called_once()

    @pytest.mark.asyncio
    async def test_cleanup_resource_with_disconnect_method(
        self, cleanup_mixin: CleanupMixin
    ) -> None:
        """Test cleaning up a resource with disconnect method."""
        resource = MagicMock()
        resource.close = None  # Remove sync close method
        resource.aclose = None  # Remove async close method
        resource.disconnect = MagicMock()

        await cleanup_mixin.cleanup_resource(resource)
        resource.disconnect.assert_called_once()

    @pytest.mark.asyncio
    async def test_cleanup_resource_with_shutdown_method(
        self, cleanup_mixin: CleanupMixin
    ) -> None:
        """Test cleaning up a resource with shutdown method."""
        resource = MagicMock()
        for method in ["close", "aclose", "disconnect"]:
            setattr(resource, method, None)
        resource.shutdown = MagicMock()

        await cleanup_mixin.cleanup_resource(resource)
        resource.shutdown.assert_called_once()

    @pytest.mark.asyncio
    async def test_cleanup_resource_with_dispose_method(
        self, cleanup_mixin: CleanupMixin
    ) -> None:
        """Test cleaning up a resource with dispose method."""
        resource = MagicMock()
        for method in ["close", "aclose", "disconnect", "shutdown"]:
            setattr(resource, method, None)
        resource.dispose = MagicMock()

        await cleanup_mixin.cleanup_resource(resource)
        resource.dispose.assert_called_once()

    @pytest.mark.asyncio
    async def test_cleanup_resource_with_terminate_method(
        self, cleanup_mixin: CleanupMixin
    ) -> None:
        """Test cleaning up a resource with terminate method."""
        resource = MagicMock()
        for method in ["close", "aclose", "disconnect", "shutdown", "dispose"]:
            setattr(resource, method, None)
        resource.terminate = MagicMock()

        await cleanup_mixin.cleanup_resource(resource)
        resource.terminate.assert_called_once()

    @pytest.mark.asyncio
    async def test_cleanup_resource_with_quit_method(
        self, cleanup_mixin: CleanupMixin
    ) -> None:
        """Test cleaning up a resource with quit method."""
        resource = MagicMock()
        for method in [
            "close",
            "aclose",
            "disconnect",
            "shutdown",
            "dispose",
            "terminate",
        ]:
            setattr(resource, method, None)
        resource.quit = MagicMock()

        await cleanup_mixin.cleanup_resource(resource)
        resource.quit.assert_called_once()

    @pytest.mark.asyncio
    async def test_cleanup_resource_with_release_method(
        self, cleanup_mixin: CleanupMixin
    ) -> None:
        """Test cleaning up a resource with release method."""
        resource = MagicMock()
        for method in [
            "close",
            "aclose",
            "disconnect",
            "shutdown",
            "dispose",
            "terminate",
            "quit",
        ]:
            setattr(resource, method, None)
        resource.release = MagicMock()

        await cleanup_mixin.cleanup_resource(resource)
        resource.release.assert_called_once()

    @pytest.mark.asyncio
    async def test_cleanup_resource_none(self, cleanup_mixin: CleanupMixin) -> None:
        """Test cleaning up a None resource."""
        await cleanup_mixin.cleanup_resource(None)
        # Should not raise any exception

    @pytest.mark.asyncio
    async def test_cleanup_resource_method_exception(
        self, cleanup_mixin: CleanupMixin, caplog
    ) -> None:
        """Test cleaning up a resource when methods raise exceptions."""
        resource = MagicMock()
        resource.close = MagicMock(side_effect=Exception("Close failed"))
        resource.aclose = MagicMock(side_effect=Exception("Async close failed"))

        with caplog.at_level(logging.DEBUG):
            await cleanup_mixin.cleanup_resource(resource)

        # Should try multiple methods and not raise exception
        assert "Failed to cleanup using close()" in caplog.text

    @pytest.mark.asyncio
    async def test_cleanup_multiple_resources(
        self, cleanup_mixin: CleanupMixin
    ) -> None:
        """Test cleaning up multiple resources."""
        resource1 = MagicMock()
        resource1.close = MagicMock()
        resource2 = MagicMock()
        resource2.close = MagicMock()

        cleanup_mixin.register_resource(resource1)
        cleanup_mixin.register_resource(resource2)

        await cleanup_mixin.cleanup()

        resource1.close.assert_called_once()
        resource2.close.assert_called_once()
        assert len(cleanup_mixin._resources) == 0
        assert cleanup_mixin._cleaned_up is True

    @pytest.mark.asyncio
    async def test_cleanup_idempotent(self, cleanup_mixin: CleanupMixin) -> None:
        """Test that cleanup is idempotent."""
        resource = MagicMock()
        resource.close = MagicMock()

        cleanup_mixin.register_resource(resource)

        # First cleanup
        await cleanup_mixin.cleanup()
        resource.close.assert_called_once()

        # Second cleanup should not call close again
        resource.close.reset_mock()
        await cleanup_mixin.cleanup()
        resource.close.assert_not_called()

    @pytest.mark.asyncio
    async def test_cleanup_with_resource_exception(
        self, cleanup_mixin: CleanupMixin
    ) -> None:
        """Test cleanup when a resource raises an exception."""
        # Just test that the method doesn't crash when there are exceptions
        resource1 = MagicMock()
        resource1.close = MagicMock(side_effect=Exception("Resource 1 failed"))
        resource2 = MagicMock()
        resource2.close = MagicMock()

        cleanup_mixin.register_resource(resource1)
        cleanup_mixin.register_resource(resource2)

        # This should not raise an exception
        await cleanup_mixin.cleanup()

        resource1.close.assert_called_once()
        resource2.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_cleanup_concurrent_safe(self, cleanup_mixin: CleanupMixin) -> None:
        """Test that concurrent cleanup calls are safe."""
        resource = MagicMock()
        resource.close = MagicMock()

        cleanup_mixin.register_resource(resource)

        # Run cleanup concurrently
        tasks = [
            asyncio.create_task(cleanup_mixin.cleanup()),
            asyncio.create_task(cleanup_mixin.cleanup()),
            asyncio.create_task(cleanup_mixin.cleanup()),
        ]

        await asyncio.gather(*tasks)

        # Should only be called once despite multiple concurrent calls
        resource.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_async_context_manager(self, cleanup_mixin: CleanupMixin) -> None:
        """Test using the mixin as an async context manager."""
        resource = MagicMock()
        resource.close = MagicMock()

        async with cleanup_mixin as adapter:
            adapter.register_resource(resource)
            assert adapter is cleanup_mixin

        # Resources should be cleaned up when exiting context
        resource.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_cleanup_logging_warnings(
        self, cleanup_mixin: CleanupMixin, caplog
    ) -> None:
        """Test that cleanup logs warnings when resources fail to cleanup."""
        resource = MagicMock()
        resource.close = MagicMock(side_effect=Exception("Cleanup failed"))

        cleanup_mixin.register_resource(resource)

        # Mock cleanup_resource to raise an exception
        original_cleanup_resource = cleanup_mixin.cleanup_resource

        async def mock_cleanup_resource_raises(resource):
            raise Exception("Cleanup resource failed")

        cleanup_mixin.cleanup_resource = mock_cleanup_resource_raises

        # Capture logs from all loggers
        with caplog.at_level(logging.WARNING):
            await cleanup_mixin.cleanup()

        # Restore original method
        cleanup_mixin.cleanup_resource = original_cleanup_resource

        # Check that warning was logged
        warning_logged = any(
            "Resource cleanup errors" in record.message for record in caplog.records
        )
        assert warning_logged, (
            f"Expected warning message not found in logs: {[record.message for record in caplog.records]}"
        )

    @pytest.mark.asyncio
    async def test_cleanup_resource_logging_debug(
        self, cleanup_mixin: CleanupMixin, caplog
    ) -> None:
        """Test that cleanup logs debug messages when resources are cleaned up."""
        resource = MagicMock()
        resource.close = MagicMock()

        with caplog.at_level(logging.DEBUG):
            await cleanup_mixin.cleanup_resource(resource)

        assert "Cleaned up resource using close()" in caplog.text

    @pytest.mark.asyncio
    async def test_cleanup_lock_initialization(
        self, cleanup_mixin: CleanupMixin
    ) -> None:
        """Test that cleanup lock is properly initialized."""
        assert cleanup_mixin._cleanup_lock is None

        # After first call to cleanup, lock should be initialized
        await cleanup_mixin.cleanup()
        assert cleanup_mixin._cleanup_lock is not None
