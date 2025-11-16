"""Tests for State Management Service."""

from unittest.mock import AsyncMock, patch

import asyncio
import pytest

from acb.services.state import (
    InMemoryStateManager,
    PersistentStateManager,
    StateEntry,
    StateManagerService,
    StateManagerSettings,
    StateStatus,
    StateType,
    delete_state,
    get_state,
    get_state_service,
    managed_state,
    set_state,
)


class TestInMemoryStateManager:
    """Test InMemoryStateManager functionality."""

    def setup_method(self):
        """Setup test fixtures."""
        self.settings = StateManagerSettings(
            default_ttl_seconds=60, max_memory_entries=100
        )
        self.manager = InMemoryStateManager(self.settings)

    @pytest.mark.asyncio
    async def test_basic_state_operations(self):
        """Test basic get/set/delete operations."""
        # Test set and get
        await self.manager.set("test_key", "test_value")
        value = await self.manager.get("test_key")
        assert value == "test_value"

        # Test exists
        assert await self.manager.exists("test_key")
        assert not await self.manager.exists("nonexistent_key")

        # Test delete
        assert await self.manager.delete("test_key")
        assert not await self.manager.exists("test_key")
        assert await self.manager.get("test_key") is None

    @pytest.mark.asyncio
    async def test_state_with_ttl(self):
        """Test state with TTL expiration."""
        # Set state with very short TTL
        await self.manager.set("ttl_key", "ttl_value", ttl_seconds=0.1)

        # Should exist immediately
        assert await self.manager.exists("ttl_key")
        assert await self.manager.get("ttl_key") == "ttl_value"

        # Wait for expiration
        await asyncio.sleep(0.2)

        # Should be expired
        assert not await self.manager.exists("ttl_key")
        assert await self.manager.get("ttl_key") is None

    @pytest.mark.asyncio
    async def test_state_types(self):
        """Test different state types."""
        # Test different state types
        await self.manager.set("transient", "value1", state_type=StateType.TRANSIENT)
        await self.manager.set("persistent", "value2", state_type=StateType.PERSISTENT)
        await self.manager.set("session", "value3", state_type=StateType.SESSION)

        # All should be accessible
        assert await self.manager.get("transient") == "value1"
        assert await self.manager.get("persistent") == "value2"
        assert await self.manager.get("session") == "value3"

    @pytest.mark.asyncio
    async def test_keys_listing(self):
        """Test listing keys with patterns."""
        # Set multiple keys
        await self.manager.set("prefix_1", "value1")
        await self.manager.set("prefix_2", "value2")
        await self.manager.set("other_key", "value3")

        # Test listing all keys
        all_keys = await self.manager.keys()
        assert len(all_keys) == 3
        assert "prefix_1" in all_keys
        assert "prefix_2" in all_keys
        assert "other_key" in all_keys

        # Test pattern matching
        prefix_keys = await self.manager.keys("prefix_*")
        assert len(prefix_keys) == 2
        assert "prefix_1" in prefix_keys
        assert "prefix_2" in prefix_keys
        assert "other_key" not in prefix_keys

    @pytest.mark.asyncio
    async def test_clear_operations(self):
        """Test clearing state entries."""
        # Set different types of state
        await self.manager.set("trans1", "value1", state_type=StateType.TRANSIENT)
        await self.manager.set("trans2", "value2", state_type=StateType.TRANSIENT)
        await self.manager.set("persist1", "value3", state_type=StateType.PERSISTENT)

        # Clear transient state only
        cleared = await self.manager.clear(StateType.TRANSIENT)
        assert cleared == 2

        # Only persistent should remain
        assert await self.manager.get("trans1") is None
        assert await self.manager.get("trans2") is None
        assert await self.manager.get("persist1") == "value3"

        # Clear all
        cleared = await self.manager.clear()
        assert cleared == 1
        assert await self.manager.get("persist1") is None

    @pytest.mark.asyncio
    async def test_memory_limits(self):
        """Test memory limit enforcement."""
        # Set manager with very low limit
        small_settings = StateManagerSettings(max_memory_entries=3)
        small_manager = InMemoryStateManager(small_settings)

        # Add more entries than limit
        for i in range(5):
            await small_manager.set(f"key_{i}", f"value_{i}")

        # Should only have 3 entries (limit enforced)
        keys = await small_manager.keys()
        assert len(keys) <= 3

        # Newer entries should be preserved
        assert await small_manager.get("key_4") == "value_4"

    @pytest.mark.asyncio
    async def test_metadata_support(self):
        """Test state entry metadata."""
        metadata = {"source": "test", "priority": "high"}
        await self.manager.set("meta_key", "meta_value", metadata=metadata)

        # Check that metadata is stored
        entry = self.manager._state.get("meta_key")
        assert entry is not None
        assert entry.metadata == metadata

    @pytest.mark.asyncio
    async def test_memory_stats(self):
        """Test memory statistics."""
        # Add some entries
        await self.manager.set("key1", "value1", state_type=StateType.TRANSIENT)
        await self.manager.set("key2", "value2", state_type=StateType.PERSISTENT)

        stats = self.manager.get_memory_stats()
        assert stats["entries_count"] == 2
        assert stats["memory_size_bytes"] > 0
        assert stats["by_type"][StateType.TRANSIENT.value] == 1
        assert stats["by_type"][StateType.PERSISTENT.value] == 1


class TestPersistentStateManager:
    """Test PersistentStateManager functionality."""

    def setup_method(self):
        """Setup test fixtures."""
        self.settings = StateManagerSettings()
        self.manager = PersistentStateManager(self.settings)

    @pytest.mark.asyncio
    async def test_basic_operations_with_mock_repository(self):
        """Test basic operations with mock repository."""
        # The manager will use MockRepositoryService fallback
        await self.manager.set("persist_key", "persist_value")
        value = await self.manager.get("persist_key")
        assert value == "persist_value"

        assert await self.manager.exists("persist_key")
        assert await self.manager.delete("persist_key")
        assert not await self.manager.exists("persist_key")

    @pytest.mark.asyncio
    async def test_persistent_state_with_ttl(self):
        """Test persistent state with TTL."""
        # Set with short TTL
        await self.manager.set("ttl_persist_key", "ttl_value", ttl_seconds=0.1)

        # Should exist immediately
        assert await self.manager.exists("ttl_persist_key")

        # Wait for expiration
        await asyncio.sleep(0.2)

        # Should be expired
        assert not await self.manager.exists("ttl_persist_key")

    @pytest.mark.asyncio
    async def test_keys_and_clear_operations(self):
        """Test keys listing and clear operations."""
        # Set multiple entries
        await self.manager.set("key1", "value1", state_type=StateType.PERSISTENT)
        await self.manager.set("key2", "value2", state_type=StateType.SHARED)

        # Test keys listing
        keys = await self.manager.keys()
        assert "key1" in keys
        assert "key2" in keys

        # Test clear by type
        cleared = await self.manager.clear(StateType.PERSISTENT)
        assert cleared == 1

        # Test clear all
        cleared = await self.manager.clear()
        assert cleared >= 0  # Remaining entries


class TestStateManagerService:
    """Test StateManagerService functionality."""

    def setup_method(self):
        """Setup test fixtures."""
        self.settings = StateManagerSettings(
            cleanup_interval_seconds=0.1,  # Fast cleanup for testing
            enable_persistent_storage=False,  # Disable for unit tests
        )
        self.service = StateManagerService(self.settings)

    @pytest.mark.asyncio
    async def test_service_initialization(self):
        """Test service initialization and shutdown."""
        await self.service.initialize()
        assert self.service.status.value == "active"

        # Test health check
        health = await self.service.health_check()
        assert "service_specific" in health
        assert "memory_state" in health["service_specific"]

        await self.service.shutdown()
        assert self.service.status.value == "stopped"

    @pytest.mark.asyncio
    async def test_service_state_operations(self):
        """Test service-level state operations."""
        await self.service.initialize()

        # Test basic operations
        await self.service.set("service_key", "service_value")
        value = await self.service.get("service_key")
        assert value == "service_value"

        assert await self.service.exists("service_key")
        assert await self.service.delete("service_key")
        assert not await self.service.exists("service_key")

        await self.service.shutdown()

    @pytest.mark.asyncio
    async def test_batch_operations(self):
        """Test batch state operations."""
        await self.service.initialize()

        # Test multi-set
        items = {"batch1": "value1", "batch2": "value2", "batch3": "value3"}
        await self.service.set_multi(items)

        # Test multi-get
        results = await self.service.get_multi(["batch1", "batch2", "batch3"])
        assert results == items

        # Test multi-delete
        deleted_count = await self.service.delete_multi(["batch1", "batch2"])
        assert deleted_count == 2

        await self.service.shutdown()

    @pytest.mark.asyncio
    async def test_state_lock_context_manager(self):
        """Test state lock context manager."""
        await self.service.initialize()

        # Test successful lock acquisition
        async with self.service.state_lock("lock_key"):
            await self.service.set("lock_key", "locked_value")

        # Test lock timeout
        with pytest.raises(asyncio.TimeoutError):
            async with self.service.state_lock("timeout_key", timeout=0.1):
                # Simulate long operation
                await asyncio.sleep(0.2)

        await self.service.shutdown()

    @pytest.mark.asyncio
    async def test_cleanup_task(self):
        """Test automatic cleanup task."""
        # Use settings with very fast cleanup
        fast_settings = StateManagerSettings(cleanup_interval_seconds=0.05)
        service = StateManagerService(fast_settings)

        await service.initialize()

        # Set state with short TTL
        await service.set("cleanup_key", "cleanup_value", ttl_seconds=0.1)
        assert await service.exists("cleanup_key")

        # Wait for expiration and cleanup
        await asyncio.sleep(0.2)

        # Should be cleaned up
        assert not await service.exists("cleanup_key")

        await service.shutdown()

    @pytest.mark.asyncio
    async def test_metrics_tracking(self):
        """Test metrics tracking."""
        await self.service.initialize()

        # Perform operations
        await self.service.set("metrics_key", "metrics_value")
        await self.service.get("metrics_key")
        await self.service.delete("metrics_key")

        # Check metrics
        health = await self.service.health_check()
        metrics = health["service_specific"]["metrics"]

        assert metrics["sets_total"] >= 1
        assert metrics["gets_total"] >= 1
        assert metrics["deletes_total"] >= 1

        await self.service.shutdown()

    @pytest.mark.asyncio
    async def test_sync_state_operations(self):
        """Test state synchronization."""
        # Enable persistent storage for sync test
        sync_settings = StateManagerSettings(enable_persistent_storage=True)
        service = StateManagerService(sync_settings)

        await service.initialize()

        # Set state and sync
        await service.set("sync_key", "sync_value", state_type=StateType.PERSISTENT)
        await service.sync_state(["sync_key"])

        # Check metrics
        health = await service.health_check()
        metrics = health["service_specific"]["metrics"]
        assert metrics["sync_operations_total"] >= 1

        await service.shutdown()


class TestConvenienceFunctions:
    """Test convenience functions for state management."""

    @pytest.mark.asyncio
    async def test_convenience_functions(self):
        """Test get_state, set_state, delete_state functions."""
        with patch("acb.depends.depends.get_sync") as mock_depends_get_sync:
            # Mock the state service
            mock_service = AsyncMock()
            mock_service.get.return_value = "convenience_value"
            mock_service.set.return_value = None
            mock_service.delete.return_value = True
            mock_depends_get_sync.return_value = mock_service

            # Test convenience functions
            await set_state("conv_key", "convenience_value")
            value = await get_state("conv_key")
            assert value == "convenience_value"

            deleted = await delete_state("conv_key")
            assert deleted is True

            # Verify service calls
            mock_service.set.assert_called_once()
            mock_service.get.assert_called_once()
            mock_service.delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_state_service_fallback(self):
        """Test get_state_service fallback behavior."""
        with (
            patch("acb.depends.depends.get_sync", side_effect=Exception("No service")),
            patch("acb.depends.depends.set") as mock_depends_set,
        ):
            # Should create new service instance
            service = await get_state_service()
            assert service is not None
            assert isinstance(service, StateManagerService)

            # Should register the service
            mock_depends_set.assert_called_once()

    @pytest.mark.asyncio
    async def test_managed_state_context_manager(self):
        """Test managed_state context manager."""
        with patch("acb.services.state.get_state_service") as mock_get_service:
            mock_service = AsyncMock()
            mock_service.set_multi = AsyncMock()
            mock_service.delete_multi = AsyncMock()
            mock_get_service.return_value = mock_service

            initial_state = {"init_key1": "init_value1", "init_key2": "init_value2"}
            cleanup_keys = ["cleanup_key1", "cleanup_key2"]

            async with managed_state(
                initial_state=initial_state, cleanup_keys=cleanup_keys
            ) as service:
                assert service is mock_service

            # Verify initial state was set
            mock_service.set_multi.assert_called_once_with(
                initial_state, state_type=StateType.TRANSIENT
            )

            # Verify cleanup was performed
            mock_service.delete_multi.assert_called_once_with(cleanup_keys)


class TestStateEntry:
    """Test StateEntry model functionality."""

    def test_state_entry_creation(self):
        """Test StateEntry creation and basic properties."""
        from datetime import datetime

        now = datetime.now()
        entry = StateEntry(
            key="test_key",
            value="test_value",
            state_type=StateType.TRANSIENT,
            created_at=now,
            updated_at=now,
        )

        assert entry.key == "test_key"
        assert entry.value == "test_value"
        assert entry.state_type == StateType.TRANSIENT
        assert entry.status == StateStatus.ACTIVE
        assert entry.version == 1
        assert not entry.is_expired()

    def test_state_entry_expiration(self):
        """Test StateEntry expiration logic."""
        from datetime import datetime, timedelta

        now = datetime.now()
        past_time = now - timedelta(seconds=60)

        expired_entry = StateEntry(
            key="expired_key",
            value="expired_value",
            state_type=StateType.TRANSIENT,
            created_at=past_time,
            updated_at=past_time,
            expires_at=past_time,  # Already expired
        )

        assert expired_entry.is_expired()

        # Test non-expiring entry
        no_expiry_entry = StateEntry(
            key="no_expiry_key",
            value="no_expiry_value",
            state_type=StateType.PERSISTENT,
            created_at=now,
            updated_at=now,
            expires_at=None,
        )

        assert not no_expiry_entry.is_expired()

    def test_state_entry_update_value(self):
        """Test StateEntry value update with version increment."""
        from datetime import datetime

        now = datetime.now()
        entry = StateEntry(
            key="update_key",
            value="original_value",
            state_type=StateType.TRANSIENT,
            created_at=now,
            updated_at=now,
        )

        original_version = entry.version
        original_updated_at = entry.updated_at

        # Update value
        entry.update_value("new_value")

        assert entry.value == "new_value"
        assert entry.version == original_version + 1
        assert entry.updated_at > original_updated_at


class TestStateManagerSettings:
    """Test StateManagerSettings configuration."""

    def test_default_settings(self):
        """Test default settings values."""
        settings = StateManagerSettings()

        assert settings.default_ttl_seconds == 3600
        assert settings.max_memory_entries == 10000
        assert settings.cleanup_interval_seconds == 300
        assert settings.enable_persistent_storage is True
        assert settings.persistent_storage_adapter == "repository"
        assert settings.enable_state_sync is False
        assert settings.sync_interval_seconds == 60
        assert settings.lock_timeout_seconds == 10.0
        assert settings.batch_size == 100

    def test_custom_settings(self):
        """Test custom settings values."""
        settings = StateManagerSettings(
            default_ttl_seconds=1800,
            max_memory_entries=5000,
            enable_persistent_storage=False,
            enable_state_sync=True,
        )

        assert settings.default_ttl_seconds == 1800
        assert settings.max_memory_entries == 5000
        assert settings.enable_persistent_storage is False
        assert settings.enable_state_sync is True
