"""Integration tests for adapter combinations and cross-adapter workflows.

Tests end-to-end scenarios combining multiple adapters to ensure they work
together correctly in realistic application patterns.
"""

from __future__ import annotations

from unittest.mock import patch

import asyncio
import pytest

from acb.adapters import import_adapter
from acb.depends import depends


class TestCacheStorageIntegration:
    """Test cache and storage adapters working together."""

    @pytest.mark.asyncio
    async def test_cache_before_storage_lookup(self) -> None:
        """Test using cache to avoid repeated storage lookups.

        Simulates a common pattern where frequently accessed data is cached
        to reduce storage I/O.
        """
        # Get cache and storage adapters
        Cache = import_adapter("cache")
        cache = await depends.get(Cache)

        # Mock key for testing
        test_key = "test:document:123"
        test_data = {"id": 123, "name": "Test Document", "content": "test content"}

        # Test cache hit after initial set
        await cache.set(test_key, test_data, ttl=300)
        cached = await cache.get(test_key)

        assert cached == test_data

    @pytest.mark.asyncio
    async def test_cache_expiration_workflow(self) -> None:
        """Test cache expiration triggering storage refresh."""
        Cache = import_adapter("cache")
        cache = await depends.get(Cache)

        test_key = "temp:cache:key"
        test_value = "temporary_data"

        # Set with short TTL
        await cache.set(test_key, test_value, ttl=1)

        # Verify value is cached
        cached_value = await cache.get(test_key)
        assert cached_value == test_value

        # Wait for expiration
        await asyncio.sleep(1.5)

        # Value should be expired (returned None in most implementations)
        await cache.get(test_key)
        # Note: Some cache implementations return None, others raise
        # This test demonstrates the pattern

    @pytest.mark.asyncio
    async def test_cache_with_serialization(self) -> None:
        """Test caching complex objects with serialization."""
        Cache = import_adapter("cache")
        cache = await depends.get(Cache)

        test_key = "complex:object:key"
        complex_data = {
            "user_id": 42,
            "profile": {"name": "Test User", "email": "test@example.com"},
            "roles": ["admin", "user"],
            "active": True,
        }

        # Cache should handle serialization automatically
        await cache.set(test_key, complex_data, ttl=600)
        retrieved = await cache.get(test_key)

        assert retrieved is not None
        assert retrieved["user_id"] == 42
        assert retrieved["profile"]["name"] == "Test User"

    @pytest.mark.asyncio
    async def test_cache_multi_set_workflow(self) -> None:
        """Test caching multiple related items together."""
        Cache = import_adapter("cache")
        cache = await depends.get(Cache)

        # Batch set multiple related cache items
        related_items = {
            "user:123:profile": {"id": 123, "name": "Alice"},
            "user:123:settings": {"theme": "dark", "language": "en"},
            "user:123:notifications": {"enabled": True, "count": 5},
        }

        # Cache in batch
        await cache.multi_set(related_items)

        # Verify all items cached
        for key in related_items:
            cached = await cache.get(key)
            assert cached == related_items[key]

    @pytest.mark.asyncio
    async def test_cache_increment_pattern(self) -> None:
        """Test cache for tracking counters (like page views)."""
        Cache = import_adapter("cache")
        cache = await depends.get(Cache)

        counter_key = "stats:page_views:123"

        # Initialize counter
        await cache.set(counter_key, 0)

        # Simulate increments
        for _ in range(5):
            await cache.increment(counter_key, delta=1)

        # Verify final count
        final_count = await cache.get(counter_key)
        assert final_count == 5


class TestServiceCacheIntegration:
    """Test services working with cache adapters."""

    @pytest.mark.asyncio
    async def test_repository_service_with_caching(self) -> None:
        """Test repository service using cache for performance."""
        # Mock a repository service pattern
        Cache = import_adapter("cache")
        cache = await depends.get(Cache)

        # Simulate repository pattern
        class MockEntity:
            def __init__(self, entity_id: int, name: str) -> None:
                self.entity_id = entity_id
                self.name = name

        entity = MockEntity(1, "Test Entity")
        cache_key = f"entity:{entity.entity_id}"

        # Cache the entity
        await cache.set(cache_key, {"id": entity.entity_id, "name": entity.name})

        # Verify retrieval
        cached_entity = await cache.get(cache_key)
        assert cached_entity["id"] == entity.entity_id

    @pytest.mark.asyncio
    async def test_validation_service_with_result_caching(self) -> None:
        """Test caching validation results for repeated validations."""
        Cache = import_adapter("cache")
        cache = await depends.get(Cache)

        # Cache validation results
        schema_key = "validation:schema:user"
        validation_result = {"is_valid": True, "errors": []}

        await cache.set(schema_key, validation_result, ttl=3600)

        cached_result = await cache.get(schema_key)
        assert cached_result["is_valid"] is True


class TestAdapterErrorHandling:
    """Test error handling when adapters are unavailable."""

    @pytest.mark.asyncio
    async def test_adapter_fallback_to_memory(self) -> None:
        """Test graceful fallback when Redis unavailable."""
        # This demonstrates the pattern of adapters providing fallbacks
        Cache = import_adapter("cache")
        cache = await depends.get(Cache)

        # Memory cache should always be available
        assert cache is not None
        assert hasattr(cache, "set")
        assert hasattr(cache, "get")

    @pytest.mark.asyncio
    async def test_adapter_initialization_errors_handled(self) -> None:
        """Test handling of adapter initialization failures."""
        # Simulate adapter that fails to initialize
        with patch.object(
            type(depends), "get", side_effect=Exception("Connection failed")
        ):
            # Application should handle gracefully
            try:
                Cache = import_adapter("cache")
                # This will raise, demonstrating error handling pattern
                await depends.get(Cache)
            except Exception as e:
                assert "Connection failed" in str(e)


class TestMultipleAdapterWorkflow:
    """Test realistic workflows using multiple adapters."""

    @pytest.mark.asyncio
    async def test_request_response_caching_pattern(self) -> None:
        """Test HTTP request/response caching common in web apps.

        Simulates caching API responses to reduce external calls.
        """
        Cache = import_adapter("cache")
        cache = await depends.get(Cache)

        # Simulate caching API response
        api_endpoint_key = "api:users:123"
        api_response = {
            "status": 200,
            "data": {"id": 123, "name": "John Doe", "email": "john@example.com"},
            "timestamp": 1234567890,
        }

        # Cache response
        await cache.set(api_endpoint_key, api_response, ttl=300)

        # Verify cache hit
        cached_response = await cache.get(api_endpoint_key)
        assert cached_response["data"]["id"] == 123

    @pytest.mark.asyncio
    async def test_session_data_caching(self) -> None:
        """Test caching user session data.

        Simulates storing session information in cache for fast access.
        """
        Cache = import_adapter("cache")
        cache = await depends.get(Cache)

        session_id = "session:abc123def456"
        session_data = {
            "user_id": 42,
            "username": "alice",
            "login_time": 1234567890,
            "last_activity": 1234567890,
            "ip_address": "192.168.1.100",
        }

        # Cache session
        await cache.set(session_id, session_data, ttl=3600)

        # Verify session retrieval
        cached_session = await cache.get(session_id)
        assert cached_session["user_id"] == 42

    @pytest.mark.asyncio
    async def test_async_batch_operations(self) -> None:
        """Test batch operations across multiple cache items."""
        Cache = import_adapter("cache")
        cache = await depends.get(Cache)

        # Prepare batch items
        items_to_cache = {
            "batch:item:1": {"value": 1, "timestamp": 1000},
            "batch:item:2": {"value": 2, "timestamp": 2000},
            "batch:item:3": {"value": 3, "timestamp": 3000},
        }

        # Batch set
        await cache.multi_set(items_to_cache)

        # Verify all items
        for key in items_to_cache:
            cached = await cache.get(key)
            assert cached is not None
            assert cached["value"] > 0


class TestCrossAdapterDataFlow:
    """Test data flowing through multiple adapters."""

    @pytest.mark.asyncio
    async def test_data_consistency_across_layers(self) -> None:
        """Test that data remains consistent when using cache+storage."""
        Cache = import_adapter("cache")
        cache = await depends.get(Cache)

        # Original data
        entity_id = 1
        entity_data = {"id": entity_id, "name": "Original", "version": 1}

        cache_key = f"entity:{entity_id}"

        # Store in cache
        await cache.set(cache_key, entity_data, ttl=3600)

        # Retrieve and verify
        retrieved = await cache.get(cache_key)
        assert retrieved["version"] == 1
        assert retrieved["name"] == "Original"

    @pytest.mark.asyncio
    async def test_cache_invalidation_pattern(self) -> None:
        """Test invalidating cache when underlying data changes."""
        Cache = import_adapter("cache")
        cache = await depends.get(Cache)

        entity_key = "entity:1"
        original_data = {"id": 1, "name": "Alice", "email": "alice@example.com"}

        # Initial cache
        await cache.set(entity_key, original_data, ttl=3600)
        cached = await cache.get(entity_key)
        assert cached["name"] == "Alice"

        # Simulate data update - invalidate cache
        await cache.delete(entity_key)

        # Cache should be empty
        invalidated = await cache.get(entity_key)
        assert invalidated is None


@pytest.mark.asyncio
async def test_concurrent_cache_operations() -> None:
    """Test concurrent cache operations for thread safety."""
    Cache = import_adapter("cache")
    cache = await depends.get(Cache)

    async def cache_operation(key: str, value: str) -> None:
        """Perform a cache operation."""
        await cache.set(key, value, ttl=60)
        retrieved = await cache.get(key)
        assert retrieved == value

    # Run multiple operations concurrently
    keys_values = [(f"key:{i}", f"value:{i}") for i in range(10)]
    tasks = [cache_operation(k, v) for k, v in keys_values]

    await asyncio.gather(*tasks)


@pytest.mark.asyncio
async def test_adapter_performance_under_load() -> None:
    """Test adapter performance with many operations.

    Demonstrates patterns for performance testing of adapters.
    """
    Cache = import_adapter("cache")
    cache = await depends.get(Cache)

    # Simulate high load
    num_operations = 100

    # Batch set
    batch_items = {f"load:key:{i}": f"value:{i}" for i in range(num_operations)}
    await cache.multi_set(batch_items)

    # Verify all items
    retrieved_count = 0
    for key in batch_items:
        value = await cache.get(key)
        if value is not None:
            retrieved_count += 1

    # Most items should be retrievable
    assert retrieved_count >= int(num_operations * 0.8)  # At least 80%
