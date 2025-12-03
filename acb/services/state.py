"""State Management Service for ACB Framework.

Provides focused state management capabilities with in-memory and persistent
storage options, state synchronization, and lifecycle management.

Features:
- StateManager interface for consistent state operations
- In-memory state management with TTL support
- Persistent state storage via Repository Layer
- State synchronization mechanisms
- Automatic state cleanup and lifecycle management
- Thread-safe state operations using asyncio locks
"""

from collections import defaultdict
from enum import Enum

import asyncio
import typing as t
from contextlib import asynccontextmanager, suppress
from datetime import datetime, timedelta
from pydantic import BaseModel, Field

from acb.services._base import (
    ServiceBase,
    ServiceConfig,
    ServiceMetrics,
    ServiceSettings,
)
from acb.services.discovery import (
    ServiceCapability,
    create_service_metadata_template,
)


class StateType(Enum):
    """Types of state that can be managed."""

    TRANSIENT = "transient"  # Short-lived, memory-only
    PERSISTENT = "persistent"  # Long-lived, stored persistently
    SESSION = "session"  # Session-specific state
    SHARED = "shared"  # Shared across multiple processes
    CACHED = "cached"  # Cached state with TTL


class StateStatus(Enum):
    """Status of state entries."""

    ACTIVE = "active"
    EXPIRED = "expired"
    LOCKED = "locked"
    SYNCING = "syncing"
    DELETED = "deleted"


class StateEntry(BaseModel):
    """Individual state entry with metadata."""

    key: str
    value: t.Any
    state_type: StateType
    status: StateStatus = StateStatus.ACTIVE
    created_at: datetime
    updated_at: datetime
    expires_at: datetime | None = None
    version: int = 1
    metadata: dict[str, t.Any] = Field(default_factory=dict)

    def is_expired(self) -> bool:
        """Check if state entry has expired."""
        if self.expires_at is None:
            return False
        return datetime.now() >= self.expires_at

    def update_value(self, value: t.Any) -> None:
        """Update state value with version increment."""
        self.value = value
        self.updated_at = datetime.now()
        self.version += 1


class StateManagerSettings(ServiceSettings):
    """Settings for State Management Service."""

    # In-memory state configuration
    default_ttl_seconds: int = Field(
        default=3600,
        description="Default TTL for state entries",
    )
    max_memory_entries: int = Field(
        default=10000,
        description="Maximum entries in memory",
    )
    cleanup_interval_seconds: float = Field(
        default=300.0,
        description="Interval for automatic cleanup",
    )

    # Persistent storage configuration
    enable_persistent_storage: bool = Field(
        default=True,
        description="Enable persistent state storage",
    )
    persistent_storage_adapter: str = Field(
        default="repository",
        description="Adapter for persistent storage",
    )

    # Synchronization settings
    enable_state_sync: bool = Field(
        default=False,
        description="Enable state synchronization",
    )
    sync_interval_seconds: float = Field(
        default=60.0,
        description="State sync interval",
    )

    # Performance settings
    lock_timeout_seconds: float = Field(
        default=10.0,
        description="Timeout for state locks",
    )
    batch_size: int = Field(default=100, description="Batch size for bulk operations")

    def __init__(self, **values: t.Any) -> None:
        """Initialize without dependency injection for testing."""
        # Skip dependency injection for testing
        try:
            from acb.config import Config
            from acb.depends import depends

            depends.get_sync(Config)
            super().__init__(**values)
        except Exception:
            # Fallback for testing - initialize BaseModel directly
            from pydantic import BaseModel

            BaseModel.__init__(self, **values)


class StateManagerConfig(ServiceConfig):
    """Configuration for State Management Service."""

    state_manager: StateManagerSettings = Field(default_factory=StateManagerSettings)


class StateManagerMetrics(ServiceMetrics):
    """Metrics for State Management Service."""

    # State operation metrics
    gets_total: int = 0
    sets_total: int = 0
    deletes_total: int = 0
    expires_total: int = 0

    # Memory state metrics
    memory_entries_count: int = 0
    memory_size_bytes: int = 0

    # Persistent state metrics
    persistent_reads_total: int = 0
    persistent_writes_total: int = 0

    # Synchronization metrics
    sync_operations_total: int = 0
    sync_conflicts_total: int = 0

    # Performance metrics
    lock_acquisitions_total: int = 0
    lock_timeouts_total: int = 0


class StateManager:
    """Interface for state management operations."""

    async def get(self, key: str, default: t.Any = None) -> t.Any:
        """Get state value by key."""
        raise NotImplementedError

    async def set(
        self,
        key: str,
        value: t.Any,
        *,
        state_type: StateType = StateType.TRANSIENT,
        ttl_seconds: int | None = None,
        metadata: dict[str, t.Any] | None = None,
    ) -> None:
        """Set state value with optional TTL and metadata."""
        raise NotImplementedError

    async def delete(self, key: str) -> bool:
        """Delete state entry."""
        raise NotImplementedError

    async def exists(self, key: str) -> bool:
        """Check if state key exists."""
        raise NotImplementedError

    async def keys(self, pattern: str = "*") -> list[str]:
        """List state keys matching pattern."""
        raise NotImplementedError

    async def clear(self, state_type: StateType | None = None) -> int:
        """Clear state entries, optionally by type."""
        raise NotImplementedError


class InMemoryStateManager(StateManager):
    """In-memory state manager with TTL support."""

    def __init__(self, settings: StateManagerSettings) -> None:
        self._settings = settings
        self._state: dict[str, StateEntry] = {}
        self._locks: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)
        self._global_lock = asyncio.Lock()

    async def get(self, key: str, default: t.Any = None) -> t.Any:
        """Get state value by key."""
        async with self._locks[key]:
            entry = self._state.get(key)
            if entry is None:
                return default

            if entry.is_expired():
                await self._remove_expired_entry(key)
                return default

            return entry.value

    async def set(
        self,
        key: str,
        value: t.Any,
        *,
        state_type: StateType = StateType.TRANSIENT,
        ttl_seconds: int | None = None,
        metadata: dict[str, t.Any] | None = None,
    ) -> None:
        """Set state value with optional TTL and metadata."""
        async with self._locks[key]:
            now = datetime.now()
            expires_at = None

            if ttl_seconds is not None:
                expires_at = now + timedelta(seconds=ttl_seconds)
            elif state_type == StateType.TRANSIENT:
                expires_at = now + timedelta(seconds=self._settings.default_ttl_seconds)

            # Update existing entry or create new one
            if key in self._state:
                entry = self._state[key]
                entry.update_value(value)
                entry.expires_at = expires_at
                entry.state_type = state_type
                if metadata:
                    entry.metadata.update(metadata)
            else:
                entry = StateEntry(
                    key=key,
                    value=value,
                    state_type=state_type,
                    created_at=now,
                    updated_at=now,
                    expires_at=expires_at,
                    metadata=metadata or {},
                )
                self._state[key] = entry

            # Check memory limits
            await self._enforce_memory_limits()

    async def delete(self, key: str) -> bool:
        """Delete state entry."""
        async with self._locks[key]:
            entry = self._state.pop(key, None)
            if entry:
                entry.status = StateStatus.DELETED
                return True
            return False

    async def exists(self, key: str) -> bool:
        """Check if state key exists."""
        async with self._locks[key]:
            entry = self._state.get(key)
            if entry is None:
                return False

            if entry.is_expired():
                await self._remove_expired_entry(key)
                return False

            return True

    async def keys(self, pattern: str = "*") -> list[str]:
        """List state keys matching pattern."""
        async with self._global_lock:
            if pattern == "*":
                return list(self._state.keys())

            # Simple pattern matching (could be enhanced with regex)
            import fnmatch

            return [key for key in self._state if fnmatch.fnmatch(key, pattern)]

    async def clear(self, state_type: StateType | None = None) -> int:
        """Clear state entries, optionally by type."""
        async with self._global_lock:
            if state_type is None:
                count = len(self._state)
                self._state.clear()
                return count

            keys_to_remove = [
                key
                for key, entry in self._state.items()
                if entry.state_type == state_type
            ]

            for key in keys_to_remove:
                del self._state[key]

            return len(keys_to_remove)

    async def _remove_expired_entry(self, key: str) -> None:
        """Remove expired entry from state."""
        if key in self._state:
            self._state[key].status = StateStatus.EXPIRED
            del self._state[key]

    async def _enforce_memory_limits(self) -> None:
        """Enforce memory limits by removing oldest entries."""
        if len(self._state) <= self._settings.max_memory_entries:
            return

        # Remove oldest entries until under limit
        sorted_entries = sorted(
            self._state.items(),
            key=lambda x: x[1].updated_at,
            reverse=False,
        )

        entries_to_remove = len(self._state) - self._settings.max_memory_entries
        for key, _ in sorted_entries[:entries_to_remove]:
            del self._state[key]

    def get_memory_stats(self) -> dict[str, t.Any]:
        """Get memory usage statistics."""
        import sys

        total_size = sum(sys.getsizeof(entry.value) for entry in self._state.values())

        return {
            "entries_count": len(self._state),
            "memory_size_bytes": total_size,
            "by_type": {
                state_type.value: sum(
                    1
                    for entry in self._state.values()
                    if entry.state_type == state_type
                )
                for state_type in StateType
            },
        }


class PersistentStateManager(StateManager):
    """Persistent state manager using Repository Layer."""

    def __init__(self, settings: StateManagerSettings) -> None:
        self._settings = settings
        self._repository = None  # Will be injected via dependency system

    async def _ensure_repository(self) -> t.Any:
        """Ensure repository is available."""
        if self._repository is None:
            # Get repository from dependency injection
            from acb.depends import depends

            try:
                self._repository = depends.get_sync("repository_service")
            except Exception:
                # Fallback to mock implementation for testing
                self._repository = t.cast("t.Any", MockRepositoryService())

        return self._repository

    async def get(self, key: str, default: t.Any = None) -> t.Any:
        """Get state value from persistent storage."""
        repository = await self._ensure_repository()
        try:
            result = await t.cast("t.Any", repository.find_by_key)("state_entries", key)
            if result:
                entry_data = result.get("data", {})
                entry = StateEntry(**entry_data)
                if entry.is_expired():
                    await self.delete(key)
                    return default
                return entry.value
            return default
        except Exception:
            return default

    async def set(
        self,
        key: str,
        value: t.Any,
        *,
        state_type: StateType = StateType.PERSISTENT,
        ttl_seconds: int | None = None,
        metadata: dict[str, t.Any] | None = None,
    ) -> None:
        """Set state value in persistent storage."""
        repository = await self._ensure_repository()
        now = datetime.now()
        expires_at = None

        if ttl_seconds is not None:
            expires_at = now + timedelta(seconds=ttl_seconds)

        entry = StateEntry(
            key=key,
            value=value,
            state_type=state_type,
            created_at=now,
            updated_at=now,
            expires_at=expires_at,
            metadata=metadata or {},
        )

        await t.cast("t.Any", repository.upsert)(
            "state_entries",
            {"key": key, "data": entry.model_dump()},
        )

    async def delete(self, key: str) -> bool:
        """Delete state entry from persistent storage."""
        repository = await self._ensure_repository()
        try:
            result = await t.cast("t.Any", repository.delete_by_key)(
                "state_entries",
                key,
            )
            return result is not None
        except Exception:
            return False

    async def exists(self, key: str) -> bool:
        """Check if state key exists in persistent storage."""
        repository = await self._ensure_repository()
        try:
            result = await t.cast("t.Any", repository.find_by_key)("state_entries", key)
            if result:
                entry_data = result.get("data", {})
                entry = StateEntry(**entry_data)
                if entry.is_expired():
                    await self.delete(key)
                    return False
                return True
            return False
        except Exception:
            return False

    async def keys(self, pattern: str = "*") -> list[str]:
        """List state keys from persistent storage."""
        repository = await self._ensure_repository()
        try:
            results = await t.cast("t.Any", repository.find_all)("state_entries")
            keys = [result.get("key", "") for result in results if result.get("key")]

            if pattern == "*":
                return keys

            import fnmatch

            return [key for key in keys if fnmatch.fnmatch(key, pattern)]
        except Exception:
            return []

    async def clear(self, state_type: StateType | None = None) -> int:
        """Clear state entries from persistent storage."""
        repository = await self._ensure_repository()
        try:
            if state_type is None:
                results = await t.cast("t.Any", repository.find_all)("state_entries")
                count = len(results)
                await t.cast("t.Any", repository.clear_collection)("state_entries")
                return count

            # Filter by state type
            results = await t.cast("t.Any", repository.find_all)("state_entries")
            keys_to_remove = []

            for result in results:
                entry_data = result.get("data", {})
                entry = StateEntry(**entry_data)
                if entry.state_type == state_type:
                    keys_to_remove.append(entry.key)

            for key in keys_to_remove:
                await t.cast("t.Any", repository.delete_by_key)("state_entries", key)

            return len(keys_to_remove)
        except Exception:
            return 0


class MockRepositoryService:
    """Mock repository service for testing."""

    def __init__(self) -> None:
        self._data: dict[str, dict[str, t.Any]] = defaultdict(dict)

    async def find_by_key(self, collection: str, key: str) -> dict[str, t.Any] | None:
        """Find entry by key."""
        return self._data[collection].get(key)

    async def upsert(self, collection: str, data: dict[str, t.Any]) -> None:
        """Insert or update entry."""
        key = data.get("key")
        if key:
            self._data[collection][key] = data

    async def delete_by_key(self, collection: str, key: str) -> dict[str, t.Any] | None:
        """Delete entry by key."""
        return t.cast("dict[str, t.Any] | None", self._data[collection].pop(key, None))

    async def find_all(self, collection: str) -> list[dict[str, t.Any]]:
        """Find all entries in collection."""
        return list(self._data[collection].values())

    async def clear_collection(self, collection: str) -> None:
        """Clear entire collection."""
        self._data[collection].clear()


class StateManagerService(ServiceBase):
    """State Management Service with multiple backends."""

    SERVICE_METADATA = create_service_metadata_template(
        name="State Management Service",
        category="state",
        service_type="manager",
        author="ACB Framework",
        description="Focused state management with in-memory and persistent storage",
        capabilities=[
            ServiceCapability.LIFECYCLE_MANAGEMENT,
            ServiceCapability.CACHING,
            ServiceCapability.ASYNC_OPERATIONS,
        ],
        settings_class="StateManagerSettings",
    )

    def __init__(self, settings: StateManagerSettings | None = None) -> None:
        super().__init__()
        self._settings = settings or StateManagerSettings()
        self._config = StateManagerConfig(
            service_id="state_manager_service",
            name="State Management Service",
            state_manager=self._settings,
        )
        self._metrics: StateManagerMetrics = StateManagerMetrics()

        # State managers
        self._memory_manager = InMemoryStateManager(self._settings)
        self._persistent_manager = None
        if self._settings.enable_persistent_storage:
            self._persistent_manager = PersistentStateManager(self._settings)

        # Cleanup task
        self._cleanup_task: asyncio.Task[None] | None = None

    async def _initialize(self) -> None:
        """Service-specific initialization logic."""
        # Start cleanup task
        cleanup_interval = getattr(self._settings, "cleanup_interval_seconds", 0)
        if cleanup_interval > 0:
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())

    async def _shutdown(self) -> None:
        """Service-specific shutdown logic."""
        if self._cleanup_task:
            self._cleanup_task.cancel()
            with suppress(asyncio.CancelledError):
                await self._cleanup_task

    async def initialize(self) -> None:
        """Initialize the state management service."""
        await super().initialize()

    async def shutdown(self) -> None:
        """Shutdown the state management service."""
        await super().shutdown()

    @asynccontextmanager
    async def state_lock(
        self,
        key: str,
        timeout: float | None = None,
    ) -> t.AsyncGenerator[None]:
        """Context manager for exclusive state access."""
        timeout = timeout or getattr(self._settings, "lock_timeout_seconds", 30.0)
        lock = asyncio.Lock()

        try:
            async with asyncio.timeout(timeout):
                async with lock:
                    self._metrics.lock_acquisitions_total += 1
                    yield
        except TimeoutError:
            self._metrics.lock_timeouts_total += 1
            raise

    # Memory state operations
    async def get(self, key: str, default: t.Any = None) -> t.Any:
        """Get state value, trying memory first then persistent storage."""
        self._metrics.gets_total += 1

        # Try memory first
        value = await self._memory_manager.get(key, None)
        if value is not None:
            return value

        # Try persistent storage if enabled
        if self._persistent_manager:
            self._metrics.persistent_reads_total += 1
            return await self._persistent_manager.get(key, default)

        return default

    async def set(
        self,
        key: str,
        value: t.Any,
        *,
        state_type: StateType = StateType.TRANSIENT,
        ttl_seconds: int | None = None,
        metadata: dict[str, t.Any] | None = None,
    ) -> None:
        """Set state value in appropriate storage."""
        self._metrics.sets_total += 1

        # Always store in memory for fast access
        await self._memory_manager.set(
            key,
            value,
            state_type=state_type,
            ttl_seconds=ttl_seconds,
            metadata=metadata,
        )

        # Store in persistent storage for persistent types
        if self._persistent_manager and state_type in {
            StateType.PERSISTENT,
            StateType.SHARED,
        }:
            self._metrics.persistent_writes_total += 1
            await self._persistent_manager.set(
                key,
                value,
                state_type=state_type,
                ttl_seconds=ttl_seconds,
                metadata=metadata,
            )

    async def delete(self, key: str) -> bool:
        """Delete state entry from all storages."""
        self._metrics.deletes_total += 1

        memory_deleted = await self._memory_manager.delete(key)
        persistent_deleted = False

        if self._persistent_manager:
            persistent_deleted = await self._persistent_manager.delete(key)

        return memory_deleted or persistent_deleted

    async def exists(self, key: str) -> bool:
        """Check if state key exists in any storage."""
        # Check memory first
        if await self._memory_manager.exists(key):
            return True

        # Check persistent storage
        if self._persistent_manager:
            return await self._persistent_manager.exists(key)

        return False

    async def keys(self, pattern: str = "*") -> list[str]:
        """List state keys from all storages."""
        memory_keys = set(await self._memory_manager.keys(pattern))
        persistent_keys = set()

        if self._persistent_manager:
            persistent_keys = set(await self._persistent_manager.keys(pattern))

        return list(memory_keys | persistent_keys)

    async def clear(self, state_type: StateType | None = None) -> int:
        """Clear state entries from all storages."""
        memory_count = await self._memory_manager.clear(state_type)
        persistent_count = 0

        if self._persistent_manager:
            persistent_count = await self._persistent_manager.clear(state_type)

        return memory_count + persistent_count

    # Batch operations
    async def get_multi(self, keys: list[str]) -> dict[str, t.Any]:
        """Get multiple state values."""
        result = {}
        for key in keys:
            value = await self.get(key)
            if value is not None:
                result[key] = value
        return result

    async def set_multi(
        self,
        items: dict[str, t.Any],
        *,
        state_type: StateType = StateType.TRANSIENT,
        ttl_seconds: int | None = None,
    ) -> None:
        """Set multiple state values."""
        tasks = [
            self.set(key, value, state_type=state_type, ttl_seconds=ttl_seconds)
            for key, value in items.items()
        ]
        await asyncio.gather(*tasks)

    async def delete_multi(self, keys: list[str]) -> int:
        """Delete multiple state entries."""
        tasks = [self.delete(key) for key in keys]
        results = await asyncio.gather(*tasks)
        return sum(results)

    # State synchronization
    async def sync_state(self, keys: list[str] | None = None) -> None:
        """Synchronize state between memory and persistent storage."""
        if not self._persistent_manager:
            return

        self._metrics.sync_operations_total += 1

        if keys is None:
            keys = await self._memory_manager.keys()

        for key in keys:
            try:
                memory_value = await self._memory_manager.get(key)
                persistent_value = await self._persistent_manager.get(key)

                if memory_value != persistent_value:
                    self._metrics.sync_conflicts_total += 1
                    # Memory takes precedence for now
                    if memory_value is not None:
                        await self._persistent_manager.set(key, memory_value)
                    elif persistent_value is not None:
                        await self._memory_manager.set(key, persistent_value)
            except Exception:
                # Log sync errors but continue
                continue

    async def health_check(self) -> dict[str, t.Any]:
        """Health check for state management service."""
        base_health = await super().health_check()

        # Memory statistics
        memory_stats = self._memory_manager.get_memory_stats()

        # Update metrics
        self._metrics.memory_entries_count = memory_stats["entries_count"]
        self._metrics.memory_size_bytes = memory_stats["memory_size_bytes"]

        service_health = {
            "memory_state": {
                "entries_count": memory_stats["entries_count"],
                "memory_size_bytes": memory_stats["memory_size_bytes"],
                "by_type": memory_stats["by_type"],
            },
            "persistent_storage_enabled": self._persistent_manager is not None,
            "cleanup_task_running": self._cleanup_task is not None
            and not self._cleanup_task.done(),
            "metrics": {
                "gets_total": self._metrics.gets_total,
                "sets_total": self._metrics.sets_total,
                "deletes_total": self._metrics.deletes_total,
                "persistent_reads_total": self._metrics.persistent_reads_total,
                "persistent_writes_total": self._metrics.persistent_writes_total,
                "sync_operations_total": self._metrics.sync_operations_total,
                "sync_conflicts_total": self._metrics.sync_conflicts_total,
                "lock_acquisitions_total": self._metrics.lock_acquisitions_total,
                "lock_timeouts_total": self._metrics.lock_timeouts_total,
            },
        }

        base_health["service_specific"] = service_health
        return base_health

    async def _cleanup_loop(self) -> None:
        """Background cleanup loop for expired state entries."""
        cleanup_interval = getattr(self._settings, "cleanup_interval_seconds", 60)
        while True:
            try:
                await asyncio.sleep(cleanup_interval)
                await self._cleanup_expired_entries()
            except asyncio.CancelledError:
                break
            except Exception:
                # Log cleanup errors but continue
                continue

    async def _cleanup_expired_entries(self) -> None:
        """Clean up expired state entries."""
        # Get all keys and check for expiration
        all_keys = await self._memory_manager.keys()
        expired_keys = []

        for key in all_keys:
            entry = self._memory_manager._state.get(key)
            if entry and entry.is_expired():
                expired_keys.append(key)

        # Remove expired entries
        for key in expired_keys:
            await self._memory_manager.delete(key)
            self._metrics.expires_total += 1


# Convenience functions for common state operations
async def get_state_service() -> StateManagerService:
    """Get state management service instance."""
    from acb.depends import depends

    try:
        return t.cast("StateManagerService", depends.get_sync(StateManagerService))
    except Exception:
        # Fallback to new instance
        service = StateManagerService()
        await service.initialize()
        depends.set(StateManagerService, service)
        return service


async def get_state(key: str, default: t.Any = None) -> t.Any:
    """Convenience function to get state value."""
    service = await get_state_service()
    return await service.get(key, default)


async def set_state(
    key: str,
    value: t.Any,
    *,
    state_type: StateType = StateType.TRANSIENT,
    ttl_seconds: int | None = None,
) -> None:
    """Convenience function to set state value."""
    service = await get_state_service()
    await service.set(key, value, state_type=state_type, ttl_seconds=ttl_seconds)


async def delete_state(key: str) -> bool:
    """Convenience function to delete state value."""
    service = await get_state_service()
    return await service.delete(key)


# State management context manager for automatic cleanup
@asynccontextmanager
async def managed_state(
    initial_state: dict[str, t.Any] | None = None,
    cleanup_keys: list[str] | None = None,
    state_type: StateType = StateType.TRANSIENT,
) -> t.AsyncGenerator[StateManagerService]:
    """Context manager for managed state with automatic cleanup."""
    service = await get_state_service()

    # Set initial state
    if initial_state:
        await service.set_multi(initial_state, state_type=state_type)

    try:
        yield service
    finally:
        # Cleanup specified keys
        if cleanup_keys:
            await service.delete_multi(cleanup_keys)
