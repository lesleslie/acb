"""Mock Adapter Provider for ACB Testing.

Provides mock implementations of ACB adapters with realistic behavior
patterns for comprehensive testing scenarios.

Features:
- Realistic mock behavior for all adapter types
- Configurable response patterns
- Error simulation capabilities
- Performance testing support
- Resource cleanup tracking
"""

from unittest.mock import AsyncMock, MagicMock

import typing as t
from contextlib import asynccontextmanager

from acb.testing.discovery import (
    TestProviderCapability,
    create_test_provider_metadata_template,
)

# Provider metadata
PROVIDER_METADATA = create_test_provider_metadata_template(
    name="Mock Adapter Provider",
    category="mocking",
    provider_type="adapter_mock",
    author="ACB Testing Team",
    description="Mock implementations of ACB adapters with realistic behavior",
    version="1.0.0",
    capabilities=[
        TestProviderCapability.ADAPTER_MOCKING,
        TestProviderCapability.ASYNC_MOCKING,
        TestProviderCapability.TEMP_RESOURCE_MANAGEMENT,
    ],
    settings_class="MockAdapterProviderSettings",
)


class MockAdapterProvider:
    """Provider for mock ACB adapters."""

    PROVIDER_METADATA = PROVIDER_METADATA

    def __init__(self) -> None:
        self._mock_instances: dict[str, t.Any] = {}
        self._call_history: dict[str, list[t.Any]] = {}

    def create_cache_mock(self, behavior: dict[str, t.Any] | None = None) -> AsyncMock:
        """Create a realistic cache adapter mock."""
        cache_mock = AsyncMock()
        cache_mock._storage = {}

        # Configure default behavior
        default_behavior = {
            "get_delay": 0.001,  # 1ms delay
            "set_delay": 0.002,  # 2ms delay
            "miss_rate": 0.1,  # 10% cache miss rate
            "error_rate": 0.0,  # No errors by default
        }

        if behavior:
            default_behavior.update(behavior)

        async def mock_get(key: str) -> t.Any:
            if default_behavior["error_rate"] > 0:
                import random

                if random.random() < default_behavior["error_rate"]:
                    msg = "Mock cache connection error"
                    raise ConnectionError(msg)

            # Simulate delay
            import asyncio

            await asyncio.sleep(default_behavior["get_delay"])

            # Simulate cache misses
            import random

            if random.random() < default_behavior["miss_rate"]:
                return None

            return cache_mock._storage.get(key)

        async def mock_set(key: str, value: t.Any, ttl: int | None = None) -> bool:
            import asyncio

            await asyncio.sleep(default_behavior["set_delay"])
            cache_mock._storage[key] = value
            return True

        async def mock_delete(key: str) -> bool:
            cache_mock._storage.pop(key, None)
            return True

        async def mock_clear() -> bool:
            cache_mock._storage.clear()
            return True

        # Assign behaviors
        cache_mock.get.side_effect = mock_get
        cache_mock.set.side_effect = mock_set
        cache_mock.delete.side_effect = mock_delete
        cache_mock.clear.side_effect = mock_clear

        # Track instance
        self._mock_instances["cache"] = cache_mock
        return cache_mock

    def create_storage_mock(
        self,
        behavior: dict[str, t.Any] | None = None,
    ) -> AsyncMock:
        """Create a realistic storage adapter mock."""
        storage_mock = AsyncMock()
        storage_mock._files = {}

        default_behavior = {
            "read_delay": 0.005,  # 5ms delay
            "write_delay": 0.010,  # 10ms delay
            "error_rate": 0.0,  # No errors by default
            "max_file_size": 1024 * 1024 * 10,  # 10MB limit
        }

        if behavior:
            default_behavior.update(behavior)

        async def mock_read(path: str) -> bytes:
            import asyncio

            await asyncio.sleep(default_behavior["read_delay"])

            if path not in storage_mock._files:
                msg = f"File not found: {path}"
                raise FileNotFoundError(msg)

            return t.cast("bytes", storage_mock._files[path])

        async def mock_write(path: str, data: bytes) -> bool:
            if len(data) > default_behavior["max_file_size"]:
                msg = "File too large"
                raise ValueError(msg)

            import asyncio

            await asyncio.sleep(default_behavior["write_delay"])
            storage_mock._files[path] = data
            return True

        async def mock_exists(path: str) -> bool:
            return path in storage_mock._files

        async def mock_delete(path: str) -> bool:
            storage_mock._files.pop(path, None)
            return True

        # Assign behaviors
        storage_mock.read.side_effect = mock_read
        storage_mock.write.side_effect = mock_write
        storage_mock.exists.side_effect = mock_exists
        storage_mock.delete.side_effect = mock_delete

        self._mock_instances["storage"] = storage_mock
        return storage_mock

    def create_sql_mock(self, behavior: dict[str, t.Any] | None = None) -> AsyncMock:
        """Create a realistic SQL adapter mock."""
        sql_mock = AsyncMock()
        sql_mock._tables = {}
        sql_mock._next_id = 1

        default_behavior = {
            "query_delay": 0.002,  # 2ms delay
            "error_rate": 0.0,  # No errors by default
            "max_rows": 1000,  # Query result limit
        }

        if behavior:
            default_behavior.update(behavior)

        async def mock_execute(
            query: str,
            params: tuple[t.Any, ...] | None = None,
        ) -> t.Any:
            import asyncio

            await asyncio.sleep(default_behavior["query_delay"])

            # Simple query simulation
            result_mock = MagicMock()

            if query.strip().upper().startswith("INSERT"):
                result_mock.rowcount = 1
                result_mock.lastrowid = sql_mock._next_id
                sql_mock._next_id += 1
            elif query.strip().upper().startswith(("UPDATE", "DELETE")):
                result_mock.rowcount = 1
            else:
                result_mock.rowcount = 0

            return result_mock

        async def mock_fetch_one(
            query: str,
            params: tuple[t.Any, ...] | None = None,
        ) -> dict[str, t.Any] | None:
            import asyncio

            await asyncio.sleep(default_behavior["query_delay"])

            # Return mock row
            return {"id": 1, "name": "test_record", "active": True}

        async def mock_fetch_all(
            query: str,
            params: tuple[t.Any, ...] | None = None,
        ) -> list[dict[str, t.Any]]:
            import asyncio

            await asyncio.sleep(default_behavior["query_delay"])

            # Return mock rows (limited by max_rows)
            return [
                {"id": i + 1, "name": f"test_record_{i}", "active": True}
                for i in range(min(5, int(default_behavior["max_rows"])))
            ]

        # Assign behaviors
        sql_mock.execute.side_effect = mock_execute
        sql_mock.fetch_one.side_effect = mock_fetch_one
        sql_mock.fetch_all.side_effect = mock_fetch_all

        self._mock_instances["sql"] = sql_mock
        return sql_mock

    def create_nosql_mock(self, behavior: dict[str, t.Any] | None = None) -> AsyncMock:
        """Create a realistic NoSQL adapter mock."""
        nosql_mock = AsyncMock()
        nosql_mock._collections = {}

        default_behavior = {
            "query_delay": 0.003,  # 3ms delay
            "error_rate": 0.0,  # No errors by default
            "max_docs": 100,  # Document limit
        }

        if behavior:
            default_behavior.update(behavior)

        async def mock_find_one(
            collection: str,
            query: dict[str, t.Any],
        ) -> dict[str, t.Any] | None:
            import asyncio

            await asyncio.sleep(default_behavior["query_delay"])

            if collection not in nosql_mock._collections:
                return None

            # Simple mock document
            return {"_id": "507f1f77bcf86cd799439011", "name": "test", "active": True}

        async def mock_find_many(
            collection: str,
            query: dict[str, t.Any],
        ) -> list[dict[str, t.Any]]:
            import asyncio

            await asyncio.sleep(default_behavior["query_delay"])

            # Return mock documents
            return [
                {
                    "_id": f"507f1f77bcf86cd79943901{i}",
                    "name": f"test_{i}",
                    "active": True,
                }
                for i in range(min(3, int(default_behavior["max_docs"])))
            ]

        async def mock_insert_one(
            collection: str,
            document: dict[str, t.Any],
        ) -> dict[str, t.Any]:
            import asyncio

            await asyncio.sleep(default_behavior["query_delay"])

            if collection not in nosql_mock._collections:
                nosql_mock._collections[collection] = []

            doc_id = (
                f"507f1f77bcf86cd799439{len(nosql_mock._collections[collection]):03d}"
            )
            document["_id"] = doc_id
            nosql_mock._collections[collection].append(document)

            return {"inserted_id": doc_id}

        # Assign behaviors
        nosql_mock.find_one.side_effect = mock_find_one
        nosql_mock.find_many.side_effect = mock_find_many
        nosql_mock.insert_one.side_effect = mock_insert_one

        self._mock_instances["nosql"] = nosql_mock
        return nosql_mock

    def create_secret_mock(self, behavior: dict[str, t.Any] | None = None) -> AsyncMock:
        """Create a realistic secret management adapter mock."""
        secret_mock = AsyncMock()
        secret_mock._secrets = {
            "test_secret": "secret_value_123",
            "api_key": "test_api_key_456",
            "database_password": "secure_password_789",
        }

        default_behavior = {
            "fetch_delay": 0.010,  # 10ms delay (secrets are slower)
            "error_rate": 0.0,  # No errors by default
        }

        if behavior:
            default_behavior.update(behavior)

        async def mock_get_secret(name: str) -> str | None:
            import asyncio

            await asyncio.sleep(default_behavior["fetch_delay"])

            if name not in secret_mock._secrets:
                msg = f"Secret not found: {name}"
                raise ValueError(msg)

            return t.cast("str", secret_mock._secrets[name])

        async def mock_set_secret(name: str, value: str) -> bool:
            import asyncio

            await asyncio.sleep(default_behavior["fetch_delay"])
            secret_mock._secrets[name] = value
            return True

        # Assign behaviors
        secret_mock.get_secret.side_effect = mock_get_secret
        secret_mock.set_secret.side_effect = mock_set_secret

        self._mock_instances["secret"] = secret_mock
        return secret_mock

    def get_mock_instance(self, adapter_type: str) -> AsyncMock | None:
        """Get a previously created mock instance."""
        return self._mock_instances.get(adapter_type)

    def reset_mocks(self) -> None:
        """Reset all mock instances and call history."""
        for mock in self._mock_instances.values():
            mock.reset_mock()
        self._call_history.clear()

    def get_call_history(self, adapter_type: str) -> list[t.Any]:
        """Get call history for a specific adapter type."""
        return self._call_history.get(adapter_type, [])

    @asynccontextmanager
    async def mock_adapter_context(
        self,
        adapter_type: str,
        behavior: dict[str, t.Any] | None = None,
    ) -> t.AsyncGenerator[AsyncMock]:
        """Context manager for temporary mock adapter."""
        # Create mock based on type
        if adapter_type == "cache":
            mock = self.create_cache_mock(behavior)
        elif adapter_type == "storage":
            mock = self.create_storage_mock(behavior)
        elif adapter_type == "sql":
            mock = self.create_sql_mock(behavior)
        elif adapter_type == "nosql":
            mock = self.create_nosql_mock(behavior)
        elif adapter_type == "secret":
            mock = self.create_secret_mock(behavior)
        else:
            msg = f"Unknown adapter type: {adapter_type}"
            raise ValueError(msg)

        try:
            yield mock
        finally:
            # Cleanup if needed
            if hasattr(mock, "_cleanup"):
                await mock._cleanup()
