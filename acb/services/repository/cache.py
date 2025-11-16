"""Repository Caching Implementation.

Provides caching capabilities for repositories:
- Cached repository wrapper
- Cache invalidation strategies
- Cache-aside and write-through patterns
- Integration with ACB cache adapters
"""

import builtins
import hashlib
import json
from enum import Enum

from dataclasses import dataclass
from pydantic import Field
from typing import TYPE_CHECKING, Any, TypeVar

from acb.config import Settings
from acb.depends import depends

from ._base import PaginationInfo, RepositoryBase, SortCriteria

if TYPE_CHECKING:
    from datetime import datetime

EntityType = TypeVar("EntityType")
IDType = TypeVar("IDType")


class CacheStrategy(Enum):
    """Cache strategy enumeration."""

    CACHE_ASIDE = "cache_aside"  # Read from cache, write to DB first
    WRITE_THROUGH = "write_through"  # Write to cache and DB simultaneously
    WRITE_BEHIND = "write_behind"  # Write to cache immediately, DB later
    REFRESH_AHEAD = "refresh_ahead"  # Proactively refresh before expiration


class InvalidationStrategy(Enum):
    """Cache invalidation strategy."""

    TTL_ONLY = "ttl_only"  # Only TTL-based expiration
    WRITE_INVALIDATE = "write_invalidate"  # Invalidate on write operations
    TAG_BASED = "tag_based"  # Tag-based invalidation
    EVENT_DRIVEN = "event_driven"  # Event-driven invalidation


@dataclass
class CacheMetrics:
    """Cache performance metrics."""

    hits: int = 0
    misses: int = 0
    writes: int = 0
    invalidations: int = 0
    errors: int = 0

    @property
    def hit_rate(self) -> float:
        """Calculate cache hit rate."""
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0

    @property
    def total_operations(self) -> int:
        """Get total cache operations."""
        return self.hits + self.misses + self.writes


class RepositoryCacheSettings(Settings):
    """Repository cache configuration settings."""

    # Cache strategy
    strategy: CacheStrategy = CacheStrategy.CACHE_ASIDE
    invalidation: InvalidationStrategy = InvalidationStrategy.WRITE_INVALIDATE

    # Cache TTL settings
    entity_ttl: int = Field(default=300, description="Entity cache TTL in seconds")
    query_ttl: int = Field(default=60, description="Query result cache TTL in seconds")
    count_ttl: int = Field(default=30, description="Count cache TTL in seconds")

    # Cache key settings
    key_prefix: str = Field(default="repo_cache", description="Cache key prefix")
    include_entity_version: bool = Field(
        default=True,
        description="Include entity version in keys",
    )

    # Performance settings
    max_query_cache_size: int = Field(
        default=1000,
        description="Max cached query results",
    )
    batch_invalidation: bool = Field(
        default=True,
        description="Enable batch invalidation",
    )
    async_invalidation: bool = Field(
        default=False,
        description="Enable async invalidation",
    )

    # Serialization settings
    compress_large_objects: bool = Field(
        default=True,
        description="Compress objects > 1KB",
    )
    compression_threshold: int = Field(
        default=1024,
        description="Compression threshold in bytes",
    )


class CachedRepository(RepositoryBase[EntityType, IDType]):
    """Repository wrapper that adds caching capabilities.

    Wraps an existing repository to provide transparent caching with
    configurable strategies and invalidation policies.
    """

    def __init__(
        self,
        wrapped_repository: RepositoryBase[EntityType, IDType],
        cache_settings: RepositoryCacheSettings | None = None,
    ) -> None:
        super().__init__(wrapped_repository.entity_type, wrapped_repository.settings)
        self.wrapped = wrapped_repository
        self.cache_settings = cache_settings or depends.get_sync(
            RepositoryCacheSettings
        )
        self._cache = None
        self._metrics: CacheMetrics = CacheMetrics()  # type: ignore[assignment]
        self._query_cache: dict[str, tuple[Any, datetime]] = {}

    async def _ensure_cache(self) -> Any | None:
        """Ensure cache adapter is available."""
        if self._cache is None:
            try:
                from acb.adapters import import_adapter

                Cache = import_adapter("cache")
                self._cache = await depends.get(Cache)
            except ImportError:
                # Cache not available, disable caching
                return None
        return self._cache

    def _build_entity_key(self, entity_id: IDType) -> str:
        """Build cache key for entity."""
        return f"{self.cache_settings.key_prefix}:entity:{self.entity_name.lower()}:{entity_id}"

    def _build_query_key(self, operation: str, **kwargs: Any) -> str:
        """Build cache key for query operation."""
        # Create deterministic key from operation parameters
        key_data = {"operation": operation, "entity": self.entity_name.lower()} | kwargs

        # Sort for consistency
        sorted_data = json.dumps(key_data, sort_keys=True)
        hash_suffix = hashlib.md5(
            sorted_data.encode(),
            usedforsecurity=False,
        ).hexdigest()[:8]

        return f"{self.cache_settings.key_prefix}:query:{self.entity_name.lower()}:{operation}:{hash_suffix}"

    def _build_count_key(self, filters: dict[str, Any] | None = None) -> str:
        """Build cache key for count operation."""
        if filters:
            filter_hash = hashlib.md5(
                json.dumps(filters, sort_keys=True).encode(),
                usedforsecurity=False,
            ).hexdigest()[:8]
            return f"{self.cache_settings.key_prefix}:count:{self.entity_name.lower()}:{filter_hash}"
        return f"{self.cache_settings.key_prefix}:count:{self.entity_name.lower()}:all"

    async def _get_from_cache(self, key: str) -> tuple[Any, bool]:
        """Get value from cache.

        Returns:
            Tuple of (value, found)
        """
        cache = await self._ensure_cache()
        if not cache:
            return None, False

        try:
            value = await cache.get(key)
            if value is not None:
                self._metrics.hits += 1
                return value, True
            self._metrics.misses += 1
            return None, False
        except Exception:
            self._metrics.errors += 1
            return None, False

    async def _set_in_cache(self, key: str, value: Any, ttl: int) -> bool:
        """Set value in cache.

        Returns:
            True if successful, False otherwise
        """
        cache = await self._ensure_cache()
        if not cache:
            return False

        try:
            await cache.set(key, value, ttl=ttl)
            self._metrics.writes += 1
            return True
        except Exception:
            self._metrics.errors += 1
            return False

    async def _invalidate_cache_key(self, key: str) -> bool:
        """Invalidate cache key.

        Returns:
            True if successful, False otherwise
        """
        cache = await self._ensure_cache()
        if not cache:
            return False

        try:
            await cache.delete(key)
            self._metrics.invalidations += 1
            return True
        except Exception:
            self._metrics.errors += 1
            return False

    async def _invalidate_entity_cache(self, entity_id: IDType) -> None:
        """Invalidate cache entries for an entity."""
        if self.cache_settings.invalidation == InvalidationStrategy.TTL_ONLY:
            return

        entity_key = self._build_entity_key(entity_id)
        await self._invalidate_cache_key(entity_key)

        # Invalidate related query caches if using write invalidation
        if self.cache_settings.invalidation == InvalidationStrategy.WRITE_INVALIDATE:
            await self._invalidate_query_caches()

    async def _invalidate_query_caches(self) -> None:
        """Invalidate all query caches for this entity type."""
        cache = await self._ensure_cache()
        if not cache:
            return

        # Pattern-based invalidation for query keys
        f"{self.cache_settings.key_prefix}:query:{self.entity_name.lower()}:*"

        # Note: Not all cache backends support pattern deletion
        # For now, we'll clear the in-memory query cache
        self._query_cache.clear()

    async def create(self, entity: EntityType) -> EntityType:
        """Create entity with cache handling."""
        try:
            # Create in wrapped repository first
            created_entity = await self.wrapped.create(entity)
            await self._increment_metric("create", True)

            # Handle caching based on strategy
            if self.cache_settings.strategy in (
                CacheStrategy.WRITE_THROUGH,
                CacheStrategy.WRITE_BEHIND,
            ):
                # Cache the created entity
                entity_id = getattr(created_entity, "id", None)
                if entity_id:
                    entity_key = self._build_entity_key(entity_id)
                    await self._set_in_cache(
                        entity_key,
                        created_entity,
                        self.cache_settings.entity_ttl,
                    )

            # Invalidate related caches
            if hasattr(created_entity, "id"):
                await self._invalidate_entity_cache(created_entity.id)

            return created_entity

        except Exception:
            await self._increment_metric("create", False)
            raise

    async def get_by_id(self, entity_id: IDType) -> EntityType | None:
        """Get entity by ID with caching."""
        try:
            entity_key = self._build_entity_key(entity_id)

            # Try cache first for cache-aside strategy
            if self.cache_settings.strategy == CacheStrategy.CACHE_ASIDE:
                cached_entity, found = await self._get_from_cache(entity_key)
                if found:
                    return cached_entity

            # Get from wrapped repository
            entity = await self.wrapped.get_by_id(entity_id)
            await self._increment_metric("get_by_id", True)

            # Cache the result if found
            if entity and self.cache_settings.strategy != CacheStrategy.WRITE_BEHIND:
                await self._set_in_cache(
                    entity_key,
                    entity,
                    self.cache_settings.entity_ttl,
                )

            return entity

        except Exception:
            await self._increment_metric("get_by_id", False)
            raise

    async def update(self, entity: EntityType) -> EntityType:
        """Update entity with cache handling."""
        try:
            # Update in wrapped repository first
            updated_entity = await self.wrapped.update(entity)
            await self._increment_metric("update", True)

            # Handle caching based on strategy
            entity_id = getattr(updated_entity, "id", None)
            if entity_id:
                if self.cache_settings.strategy == CacheStrategy.WRITE_THROUGH:
                    # Update cache immediately
                    entity_key = self._build_entity_key(entity_id)
                    await self._set_in_cache(
                        entity_key,
                        updated_entity,
                        self.cache_settings.entity_ttl,
                    )
                else:
                    # Invalidate cache
                    await self._invalidate_entity_cache(entity_id)

            return updated_entity

        except Exception:
            await self._increment_metric("update", False)
            raise

    async def delete(self, entity_id: IDType) -> bool:
        """Delete entity with cache handling."""
        try:
            # Delete from wrapped repository
            deleted = await self.wrapped.delete(entity_id)
            await self._increment_metric("delete", True)

            # Invalidate cache
            if deleted:
                await self._invalidate_entity_cache(entity_id)

            return deleted

        except Exception:
            await self._increment_metric("delete", False)
            raise

    async def list(
        self,
        filters: dict[str, Any] | None = None,
        sort: list[SortCriteria] | None = None,
        pagination: PaginationInfo | None = None,
    ) -> list[EntityType]:
        """List entities with query caching."""
        try:
            query_key = self._build_query_key(
                "list",
                filters=filters,
                sort=[{"field": s.field, "direction": s.direction.value} for s in sort]
                if sort
                else None,
                pagination={"page": pagination.page, "page_size": pagination.page_size}
                if pagination
                else None,
            )

            # Try cache first
            cached_result, found = await self._get_from_cache(query_key)
            if found:
                return cached_result

            # Get from wrapped repository
            entities = await self.wrapped.list(filters, sort, pagination)
            await self._increment_metric("list", True)

            # Cache the result
            await self._set_in_cache(query_key, entities, self.cache_settings.query_ttl)

            return entities

        except Exception:
            await self._increment_metric("list", False)
            raise

    async def count(self, filters: dict[str, Any] | None = None) -> int:
        """Count entities with caching."""
        try:
            count_key = self._build_count_key(filters)

            # Try cache first
            cached_count, found = await self._get_from_cache(count_key)
            if found:
                return cached_count

            # Get from wrapped repository
            count = await self.wrapped.count(filters)
            await self._increment_metric("count", True)

            # Cache the result
            await self._set_in_cache(count_key, count, self.cache_settings.count_ttl)

            return count

        except Exception:
            await self._increment_metric("count", False)
            raise

    async def exists(self, entity_id: IDType) -> bool:
        """Check entity existence with caching."""
        # For exists, we can use get_by_id which is already cached
        entity = await self.get_by_id(entity_id)
        return entity is not None

    async def warm_cache(self, entity_ids: builtins.list[IDType]) -> int:
        """Warm cache with entities.

        Args:
            entity_ids: List of entity IDs to pre-load

        Returns:
            Number of entities successfully cached
        """
        warmed = 0
        for entity_id in entity_ids:
            try:
                entity = await self.get_by_id(entity_id)
                if entity:
                    warmed += 1
            except Exception:
                continue
        return warmed

    async def invalidate_all(self) -> None:
        """Invalidate all cache entries for this repository."""
        cache = await self._ensure_cache()
        if not cache:
            return

        # Clear in-memory query cache
        self._query_cache.clear()

        # Try to clear cache entries by pattern
        patterns = [
            f"{self.cache_settings.key_prefix}:entity:{self.entity_name.lower()}:*",
            f"{self.cache_settings.key_prefix}:query:{self.entity_name.lower()}:*",
            f"{self.cache_settings.key_prefix}:count:{self.entity_name.lower()}:*",
        ]

        for _pattern in patterns:
            # Note: Not all cache backends support pattern deletion
            # This would need to be implemented per cache type
            pass

    async def get_cache_metrics(self) -> dict[str, Any]:
        """Get cache performance metrics.

        Returns:
            Dictionary of cache metrics
        """
        return {
            "entity_type": self.entity_name,
            "strategy": self.cache_settings.strategy.value
            if self.cache_settings.strategy
            else None,
            "invalidation": self.cache_settings.invalidation.value,
            "metrics": {
                "hits": self._metrics.hits,
                "misses": self._metrics.misses,
                "writes": self._metrics.writes,
                "invalidations": self._metrics.invalidations,
                "errors": self._metrics.errors,
                "hit_rate": self._metrics.hit_rate,
                "total_operations": self._metrics.total_operations,
            },
            "settings": {
                "entity_ttl": self.cache_settings.entity_ttl,
                "query_ttl": self.cache_settings.query_ttl,
                "count_ttl": self.cache_settings.count_ttl,
            },
        }

    async def _cleanup_resources(self) -> None:
        """Clean up cache resources."""
        self._query_cache.clear()
        if self.wrapped:
            await self.wrapped._cleanup_resources()
