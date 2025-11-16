"""Integration tests for common ACB adapter usage patterns.

These tests demonstrate realistic usage patterns for adapters in applications
rather than testing internal adapter behavior.
"""

from __future__ import annotations

import asyncio
import pytest
import typing as t


class TestCacheUsagePatterns:
    """Demonstrate common cache usage patterns in applications."""

    @pytest.mark.asyncio
    async def test_cache_as_performance_layer(self) -> None:
        """Pattern: Using cache to avoid expensive operations.

        In real applications, this would avoid database queries.
        """
        # Simulated cache pattern
        cache_store: dict[str, t.Any] = {}

        async def get_user_from_cache(user_id: int) -> dict[str, t.Any] | None:
            """Get user from cache or return None."""
            return cache_store.get(f"user:{user_id}")

        async def set_user_in_cache(user_id: int, user_data: dict[str, t.Any]) -> None:
            """Store user in cache."""
            cache_store[f"user:{user_id}"] = user_data

        async def get_user(user_id: int) -> dict[str, t.Any]:
            """Get user with caching."""
            # Check cache first (fast)
            cached = await get_user_from_cache(user_id)
            if cached:
                return cached

            # Fallback to "database" (slow)
            user = {"id": user_id, "name": "John Doe", "email": "john@example.com"}

            # Cache the result
            await set_user_in_cache(user_id, user)
            return user

        # First call - miss (simulated database query)
        user1 = await get_user(123)
        assert user1["name"] == "John Doe"

        # Second call - hit (from cache)
        user2 = await get_user(123)
        assert user2 == user1

    @pytest.mark.asyncio
    async def test_cache_expiration_pattern(self) -> None:
        """Pattern: Cache with TTL-based expiration.

        Shows how to implement cache expiration patterns.
        """
        cache_with_ttl: dict[str, tuple[t.Any, float]] = {}
        current_time = 0.0

        async def set_with_ttl(key: str, value: t.Any, ttl: float) -> None:
            """Set value with TTL."""
            cache_with_ttl[key] = (value, current_time + ttl)

        async def get_with_expiry(key: str) -> t.Any | None:
            """Get value, checking expiration."""
            if key not in cache_with_ttl:
                return None

            value, expiry_time = cache_with_ttl[key]
            if current_time >= expiry_time:
                del cache_with_ttl[key]
                return None

            return value

        # Cache with short TTL
        await set_with_ttl("token", "abc123xyz", ttl=5.0)

        # Initially available
        token = await get_with_expiry("token")
        assert token == "abc123xyz"

        # Pattern demonstrated: Time-based expiration

    @pytest.mark.asyncio
    async def test_cache_invalidation_on_update(self) -> None:
        """Pattern: Invalidate cache when data changes.

        Shows cache invalidation when underlying data is modified.
        """
        cache: dict[str, t.Any] = {}

        async def cache_get(key: str) -> t.Any | None:
            return cache.get(key)

        async def cache_set(key: str, value: t.Any) -> None:
            cache[key] = value

        async def cache_delete(key: str) -> None:
            if key in cache:
                del cache[key]

        async def update_user(user_id: int, **changes: t.Any) -> dict[str, t.Any]:
            """Update user and invalidate cache."""
            user_key = f"user:{user_id}"

            # Invalidate stale cache
            await cache_delete(user_key)

            # Update user (in real app, this would be a database update)
            updated_user = {"id": user_id, **changes}

            # Cache the updated version
            await cache_set(user_key, updated_user)
            return updated_user

        # Update user
        user = await update_user(1, name="Jane Doe", email="jane@example.com")
        assert user["name"] == "Jane Doe"

        # Verify it's in cache
        cached = await cache_get("user:1")
        assert cached == user


class TestServiceCachingPatterns:
    """Demonstrate caching patterns in service layers."""

    @pytest.mark.asyncio
    async def test_repository_caching_layer(self) -> None:
        """Pattern: Cache layer for repository pattern.

        Shows caching as a layer above the repository.
        """
        cache: dict[str, t.Any] = {}

        class UserRepository:
            """Mock repository with caching support."""

            async def get_by_id(self, user_id: int) -> dict[str, t.Any] | None:
                """Get user by ID with caching."""
                cache_key = f"user:{user_id}"

                # Check cache
                if cache_key in cache:
                    return cache[cache_key]

                # Simulated database query
                user = {"id": user_id, "name": f"User {user_id}"}

                # Cache result
                cache[cache_key] = user
                return user

        repo = UserRepository()
        user1 = await repo.get_by_id(1)
        user2 = await repo.get_by_id(1)

        assert user1 == user2  # Same object from cache

    @pytest.mark.asyncio
    async def test_validation_result_caching(self) -> None:
        """Pattern: Cache validation results.

        Shows caching expensive validation operations.
        """
        validation_cache: dict[str, bool] = {}

        async def validate_with_caching(email: str) -> bool:
            """Validate email with caching.

            In real apps, this might be an expensive DNS/database lookup.
            """
            if email in validation_cache:
                return validation_cache[email]

            # Simulated expensive validation
            is_valid = "@" in email and "." in email.split("@")[1]

            # Cache the result
            validation_cache[email] = is_valid
            return is_valid

        # First validation
        result1 = await validate_with_caching("test@example.com")
        assert result1 is True

        # Second validation uses cache
        result2 = await validate_with_caching("test@example.com")
        assert result2 == result1


class TestConcurrentCacheAccess:
    """Demonstrate concurrent cache usage patterns."""

    @pytest.mark.asyncio
    async def test_concurrent_cache_reads(self) -> None:
        """Pattern: Concurrent reads from cache.

        Shows efficient concurrent access patterns.
        """
        cache: dict[str, t.Any] = {
            "user:1": {"id": 1, "name": "Alice"},
            "user:2": {"id": 2, "name": "Bob"},
            "user:3": {"id": 3, "name": "Charlie"},
        }

        async def get_user(user_id: int) -> dict[str, t.Any] | None:
            """Get user from cache (simulated async operation)."""
            await asyncio.sleep(0.01)  # Simulate I/O
            return cache.get(f"user:{user_id}")

        # Concurrent reads
        users = await asyncio.gather(
            get_user(1),
            get_user(2),
            get_user(3),
        )

        assert len(users) == 3
        assert users[0]["name"] == "Alice"
        assert users[1]["name"] == "Bob"

    @pytest.mark.asyncio
    async def test_cache_stampede_prevention(self) -> None:
        """Pattern: Prevent cache stampede under concurrent load.

        Shows how to avoid multiple concurrent cache misses loading same data.
        """
        cache: dict[str, t.Any] = {}
        loading: dict[str, asyncio.Future[t.Any]] = {}

        async def get_with_lock(
            key: str, loader: t.Callable[[], t.Awaitable[t.Any]]
        ) -> t.Any:
            """Get from cache, with stampede prevention.

            If multiple tasks request the same missing key,
            only one loads it while others wait.
            """
            # Check cache
            if key in cache:
                return cache[key]

            # Check if another task is already loading
            if key in loading:
                return await loading[key]

            # Create future for this load operation
            future: asyncio.Future[t.Any] = asyncio.Future()
            loading[key] = future

            try:
                # Load the value
                value = await loader()

                # Cache it
                cache[key] = value

                # Mark future as done
                future.set_result(value)
                return value
            finally:
                # Clean up loading state
                del loading[key]

        # Simulated slow loader
        load_count = 0

        async def slow_loader() -> dict[str, t.Any]:
            """Loader that takes time."""
            nonlocal load_count
            load_count += 1
            await asyncio.sleep(0.01)
            return {"id": 1, "data": "expensive"}

        # Concurrent access to same missing key
        results = await asyncio.gather(
            get_with_lock("user:1", slow_loader),
            get_with_lock("user:1", slow_loader),
            get_with_lock("user:1", slow_loader),
        )

        # All requests get same result
        assert results[0] == results[1] == results[2]

        # But loader was only called once (stampede prevention worked)
        assert load_count == 1


class TestAdapterErrorRecovery:
    """Demonstrate error handling patterns with adapters."""

    @pytest.mark.asyncio
    async def test_graceful_cache_miss_handling(self) -> None:
        """Pattern: Handle cache misses gracefully.

        Shows how applications should handle cache misses.
        """
        cache: dict[str, t.Any] = {}

        async def get_with_fallback(
            key: str, fallback: t.Callable[[], t.Awaitable[t.Any]]
        ) -> t.Any:
            """Get from cache, or load from fallback."""
            try:
                if key in cache:
                    return cache[key]
            except Exception:
                pass  # Treat errors as cache miss

            # Use fallback (database, file, etc.)
            return await fallback()

        async def load_user() -> dict[str, t.Any]:
            """Fallback loader."""
            return {"id": 1, "name": "Default User"}

        result = await get_with_fallback("user:1", load_user)
        assert result["name"] == "Default User"

    @pytest.mark.asyncio
    async def test_cache_operation_failure_recovery(self) -> None:
        """Pattern: Recover from cache operation failures.

        Shows how to handle cache errors gracefully.
        """

        class CacheWithFallback:
            """Cache that falls back on errors."""

            def __init__(self) -> None:
                self.cache: dict[str, t.Any] = {}
                self.fail_next = False

            async def get(self, key: str) -> t.Any | None:
                """Get with automatic fallback on error."""
                try:
                    if self.fail_next:
                        raise Exception("Simulated cache failure")
                    return self.cache.get(key)
                except Exception:
                    # Fallback: miss is treated as cache miss, not error
                    return None

            async def set(self, key: str, value: t.Any) -> bool:
                """Set with failure recovery."""
                try:
                    if self.fail_next:
                        raise Exception("Simulated cache failure")
                    self.cache[key] = value
                    return True
                except Exception:
                    # Log error, but don't fail the application
                    return False

        cache = CacheWithFallback()

        # Simulate cache failure
        cache.fail_next = True
        result = await cache.get("key")
        assert result is None  # Handled gracefully

        success = await cache.set("key", "value")
        assert success is False  # Failure handled gracefully

        # Recovery
        cache.fail_next = False
        await cache.set("key", "value")
        result = await cache.get("key")
        assert result == "value"


@pytest.mark.asyncio
async def test_multi_adapter_workflow() -> None:
    """Pattern: Workflow using multiple adapters.

    Demonstrates how multiple adapters work together in a realistic workflow.
    """
    # Simulated cache and storage
    cache: dict[str, t.Any] = {}
    storage: dict[str, t.Any] = {"user:1": {"id": 1, "name": "Stored User"}}

    async def get_user(user_id: int) -> dict[str, t.Any]:
        """Get user from cache or storage."""
        key = f"user:{user_id}"

        # Try cache first (fast)
        if key in cache:
            return cache[key]

        # Fallback to storage (slow)
        if key in storage:
            user = storage[key]
            # Cache the result for future use
            cache[key] = user
            return user

        raise KeyError(f"User {user_id} not found")

    # First access: cache miss, storage hit
    user1 = await get_user(1)
    assert user1["name"] == "Stored User"

    # Second access: cache hit
    user2 = await get_user(1)
    assert user1 == user2
    assert "user:1" in cache  # Now in cache


@pytest.mark.asyncio
async def test_cache_warming_pattern() -> None:
    """Pattern: Pre-load cache with commonly accessed data.

    Shows how to initialize cache with frequently accessed data.
    """
    cache: dict[str, t.Any] = {}

    async def warm_cache() -> None:
        """Pre-load frequently accessed data."""
        frequently_accessed = {
            "user:1": {"id": 1, "name": "Alice"},
            "user:2": {"id": 2, "name": "Bob"},
            "config:app": {"debug": False, "version": "1.0.0"},
        }

        # Load all into cache
        for key, value in frequently_accessed.items():
            cache[key] = value

    # Warm the cache
    await warm_cache()

    # Verify cache is populated
    assert cache["user:1"]["name"] == "Alice"
    assert cache["config:app"]["version"] == "1.0.0"
