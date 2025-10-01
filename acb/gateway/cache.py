"""Response caching and optimization for ACB Gateway.

This module provides response caching capabilities including:
- HTTP response caching with TTL
- Cache key generation strategies
- Cache invalidation and warming
- Multi-tenant cache isolation
- Cache statistics and monitoring
- Integration with ACB cache adapters

Features:
- Intelligent cache key generation
- TTL-based cache expiration
- Cache size and memory management
- Multi-tenant cache isolation
- Cache statistics tracking
- Integration with external cache stores
"""

from __future__ import annotations

import hashlib
import time
import typing as t
from dataclasses import dataclass, field
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field
from acb.gateway._base import GatewayRequest, GatewayResponse


class CacheStrategy(Enum):
    """Cache strategy types."""

    NONE = "none"
    MEMORY = "memory"
    REDIS = "redis"
    HYBRID = "hybrid"


class CacheKeyStrategy(Enum):
    """Cache key generation strategies."""

    SIMPLE = "simple"  # method + path
    QUERY_AWARE = "query_aware"  # method + path + query params
    HEADER_AWARE = "header_aware"  # method + path + specific headers
    USER_AWARE = "user_aware"  # method + path + user context
    TENANT_AWARE = "tenant_aware"  # method + path + tenant
    CUSTOM = "custom"  # custom key generation


@dataclass
class CachedResponse:
    """Cached response data."""

    # Response data
    status_code: int
    headers: dict[str, str]
    body: bytes | str | None = None

    # Cache metadata
    cache_key: str = ""
    cached_at: float = field(default_factory=time.time)
    ttl: int = 300  # seconds
    hits: int = 0

    # Request context
    tenant_id: str | None = None
    user_id: str | None = None

    # Compression info
    compressed: bool = False
    original_size: int = 0
    compressed_size: int = 0

    def is_expired(self) -> bool:
        """Check if cached response is expired."""
        return time.time() > (self.cached_at + self.ttl)

    def time_to_expire(self) -> float:
        """Get time until expiration in seconds."""
        return max(0.0, (self.cached_at + self.ttl) - time.time())

    def increment_hits(self) -> None:
        """Increment hit counter."""
        self.hits += 1

    def to_gateway_response(self) -> GatewayResponse:
        """Convert to GatewayResponse."""
        return GatewayResponse(
            status_code=self.status_code,
            headers=self.headers.copy(),
            body=self.body,
            cache_hit=True,
            cache_ttl=int(self.time_to_expire()),
        )


@dataclass
class CacheStats:
    """Cache statistics."""

    # Hit/miss statistics
    hits: int = 0
    misses: int = 0
    total_requests: int = 0

    # Size statistics
    total_entries: int = 0
    memory_usage_bytes: int = 0
    max_memory_bytes: int = 0

    # Performance statistics
    avg_lookup_time_ms: float = 0.0
    avg_store_time_ms: float = 0.0

    # Eviction statistics
    evictions: int = 0
    expirations: int = 0

    # Per-tenant statistics
    tenant_stats: dict[str, dict[str, int]] = field(default_factory=dict)

    @property
    def hit_rate(self) -> float:
        """Calculate cache hit rate."""
        if self.total_requests == 0:
            return 0.0
        return self.hits / self.total_requests

    @property
    def miss_rate(self) -> float:
        """Calculate cache miss rate."""
        if self.total_requests == 0:
            return 0.0
        return self.misses / self.total_requests

    def to_dict(self) -> dict[str, t.Any]:
        """Convert to dictionary format."""
        return {
            "hits": self.hits,
            "misses": self.misses,
            "total_requests": self.total_requests,
            "hit_rate": self.hit_rate,
            "miss_rate": self.miss_rate,
            "total_entries": self.total_entries,
            "memory_usage_bytes": self.memory_usage_bytes,
            "max_memory_bytes": self.max_memory_bytes,
            "avg_lookup_time_ms": self.avg_lookup_time_ms,
            "avg_store_time_ms": self.avg_store_time_ms,
            "evictions": self.evictions,
            "expirations": self.expirations,
            "tenant_stats": self.tenant_stats,
        }


class CacheConfig(BaseModel):
    """Cache configuration."""

    # Cache strategy
    strategy: CacheStrategy = CacheStrategy.MEMORY
    enabled: bool = True

    # Cache key generation
    key_strategy: CacheKeyStrategy = CacheKeyStrategy.QUERY_AWARE
    key_prefix: str = "gateway:"
    include_headers: list[str] = Field(default_factory=list)
    exclude_headers: list[str] = Field(
        default_factory=lambda: ["authorization", "cookie"],
    )

    # TTL settings
    default_ttl: int = 300  # 5 minutes
    max_ttl: int = 3600  # 1 hour
    min_ttl: int = 60  # 1 minute

    # Size limits
    max_entries: int = 10000
    max_memory_mb: int = 100
    max_response_size_kb: int = 1024  # 1MB

    # Response caching rules
    cache_successful_responses: bool = True
    cache_error_responses: bool = False
    cacheable_status_codes: list[int] = Field(
        default_factory=lambda: [200, 301, 302, 404],
    )
    cacheable_methods: list[str] = Field(default_factory=lambda: ["GET", "HEAD"])

    # Multi-tenancy
    tenant_isolation: bool = True
    per_tenant_limits: bool = True

    # Compression
    enable_compression: bool = True
    compression_threshold: int = 1024  # bytes
    compression_level: int = 6

    # Cache warming
    enable_warming: bool = False
    warming_paths: list[str] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid")


class CacheKeyGenerator:
    """Cache key generation strategies."""

    def __init__(self, config: CacheConfig) -> None:
        self._config = config

    def generate_key(
        self,
        request: GatewayRequest,
        tenant_id: str | None = None,
        user_id: str | None = None,
    ) -> str:
        """Generate cache key based on strategy."""
        if self._config.key_strategy == CacheKeyStrategy.SIMPLE:
            return self._simple_key(request)
        if self._config.key_strategy == CacheKeyStrategy.QUERY_AWARE:
            return self._query_aware_key(request)
        if self._config.key_strategy == CacheKeyStrategy.HEADER_AWARE:
            return self._header_aware_key(request)
        if self._config.key_strategy == CacheKeyStrategy.USER_AWARE:
            return self._user_aware_key(request, user_id)
        if self._config.key_strategy == CacheKeyStrategy.TENANT_AWARE:
            return self._tenant_aware_key(request, tenant_id)
        return self._simple_key(request)

    def _simple_key(self, request: GatewayRequest) -> str:
        """Generate simple cache key from method and path."""
        key_parts = [
            self._config.key_prefix,
            request.method.value.lower(),
            request.path,
        ]
        return self._hash_key(":".join(key_parts))

    def _query_aware_key(self, request: GatewayRequest) -> str:
        """Generate cache key including query parameters."""
        key_parts = [
            self._config.key_prefix,
            request.method.value.lower(),
            request.path,
        ]

        # Add sorted query parameters
        if request.query_params:
            query_parts = [
                f"{key}={value}" for key, value in sorted(request.query_params.items())
            ]
            key_parts.append("?" + "&".join(query_parts))

        return self._hash_key(":".join(key_parts))

    def _header_aware_key(self, request: GatewayRequest) -> str:
        """Generate cache key including specific headers."""
        key_parts = [
            self._config.key_prefix,
            request.method.value.lower(),
            request.path,
        ]

        # Add query parameters
        if request.query_params:
            query_parts = [
                f"{key}={value}" for key, value in sorted(request.query_params.items())
            ]
            key_parts.append("?" + "&".join(query_parts))

        # Add specific headers
        header_parts = []
        for header_name in self._config.include_headers:
            header_value = request.headers.get(header_name)
            if header_value:
                header_parts.append(f"{header_name}:{header_value}")

        if header_parts:
            key_parts.append("headers:" + "|".join(sorted(header_parts)))

        return self._hash_key(":".join(key_parts))

    def _user_aware_key(self, request: GatewayRequest, user_id: str | None) -> str:
        """Generate cache key including user context."""
        key_parts = [
            self._config.key_prefix,
            request.method.value.lower(),
            request.path,
            f"user:{user_id or 'anonymous'}",
        ]

        # Add query parameters
        if request.query_params:
            query_parts = [
                f"{key}={value}" for key, value in sorted(request.query_params.items())
            ]
            key_parts.append("?" + "&".join(query_parts))

        return self._hash_key(":".join(key_parts))

    def _tenant_aware_key(self, request: GatewayRequest, tenant_id: str | None) -> str:
        """Generate cache key including tenant context."""
        key_parts = [
            self._config.key_prefix,
            request.method.value.lower(),
            request.path,
            f"tenant:{tenant_id or 'default'}",
        ]

        # Add query parameters
        if request.query_params:
            query_parts = [
                f"{key}={value}" for key, value in sorted(request.query_params.items())
            ]
            key_parts.append("?" + "&".join(query_parts))

        return self._hash_key(":".join(key_parts))

    def _hash_key(self, key: str) -> str:
        """Hash the key to ensure consistent length."""
        return hashlib.sha256(key.encode()).hexdigest()


class MemoryCache:
    """In-memory cache implementation."""

    def __init__(self, config: CacheConfig) -> None:
        self._config = config
        self._cache: dict[str, CachedResponse] = {}
        self._stats = CacheStats()
        self._stats.max_memory_bytes = config.max_memory_mb * 1024 * 1024

    async def get(self, key: str) -> CachedResponse | None:
        """Get cached response by key."""
        start_time = time.perf_counter()

        try:
            if key not in self._cache:
                self._stats.misses += 1
                self._stats.total_requests += 1
                return None

            cached_response = self._cache[key]

            # Check expiration
            if cached_response.is_expired():
                del self._cache[key]
                self._stats.misses += 1
                self._stats.expirations += 1
                self._stats.total_requests += 1
                self._stats.total_entries -= 1
                return None

            # Update statistics
            cached_response.increment_hits()
            self._stats.hits += 1
            self._stats.total_requests += 1

            return cached_response

        finally:
            lookup_time = (time.perf_counter() - start_time) * 1000
            self._update_avg_lookup_time(lookup_time)

    async def set(
        self,
        key: str,
        response: GatewayResponse,
        ttl: int | None = None,
        tenant_id: str | None = None,
        user_id: str | None = None,
    ) -> bool:
        """Set cached response."""
        start_time = time.perf_counter()

        try:
            # Check if caching is appropriate
            if not self._should_cache_response(response):
                return False

            # Calculate TTL
            effective_ttl = min(ttl or self._config.default_ttl, self._config.max_ttl)
            effective_ttl = max(effective_ttl, self._config.min_ttl)

            # Check size limits
            response_size = self._estimate_response_size(response)
            if response_size > self._config.max_response_size_kb * 1024:
                return False

            # Evict if necessary
            await self._evict_if_necessary(response_size)

            # Create cached response
            cached_response = CachedResponse(
                status_code=response.status_code,
                headers=self._filter_headers(response.headers),
                body=response.body,
                cache_key=key,
                ttl=effective_ttl,
                tenant_id=tenant_id,
                user_id=user_id,
            )

            # Compress if enabled
            if self._config.enable_compression:
                await self._compress_response(cached_response, response_size)

            # Store in cache
            self._cache[key] = cached_response
            self._stats.total_entries += 1
            self._stats.memory_usage_bytes += response_size

            # Update tenant statistics
            if tenant_id and self._config.tenant_isolation:
                if tenant_id not in self._stats.tenant_stats:
                    self._stats.tenant_stats[tenant_id] = {
                        "entries": 0,
                        "memory_bytes": 0,
                    }
                self._stats.tenant_stats[tenant_id]["entries"] += 1
                self._stats.tenant_stats[tenant_id]["memory_bytes"] += response_size

            return True

        finally:
            store_time = (time.perf_counter() - start_time) * 1000
            self._update_avg_store_time(store_time)

    async def delete(self, key: str) -> bool:
        """Delete cached response by key."""
        if key in self._cache:
            cached_response = self._cache[key]
            del self._cache[key]
            self._stats.total_entries -= 1

            # Update tenant statistics
            if cached_response.tenant_id and self._config.tenant_isolation:
                tenant_stats = self._stats.tenant_stats.get(cached_response.tenant_id)
                if tenant_stats:
                    tenant_stats["entries"] = max(0, tenant_stats["entries"] - 1)

            return True
        return False

    async def clear(self, tenant_id: str | None = None) -> int:
        """Clear cache entries."""
        if tenant_id and self._config.tenant_isolation:
            # Clear only tenant-specific entries
            keys_to_remove = [
                key
                for key, cached_response in self._cache.items()
                if cached_response.tenant_id == tenant_id
            ]
            for key in keys_to_remove:
                await self.delete(key)
            return len(keys_to_remove)
        # Clear all entries
        count = len(self._cache)
        self._cache.clear()
        self._stats.total_entries = 0
        self._stats.memory_usage_bytes = 0
        self._stats.tenant_stats.clear()
        return count

    async def get_stats(self) -> CacheStats:
        """Get cache statistics."""
        return self._stats

    def _should_cache_response(self, response: GatewayResponse) -> bool:
        """Check if response should be cached."""
        # Check if error responses should be cached
        if response.is_server_error() or response.is_client_error():
            if not self._config.cache_error_responses:
                return False

        # Check status code
        if response.status_code not in self._config.cacheable_status_codes:
            return False

        # Check for cache control headers
        cache_control = response.headers.get("cache-control", "").lower()
        return not ("no-cache" in cache_control or "no-store" in cache_control)

    def _filter_headers(self, headers: dict[str, str]) -> dict[str, str]:
        """Filter headers for caching."""
        filtered = {}
        for name, value in headers.items():
            if name.lower() not in [h.lower() for h in self._config.exclude_headers]:
                filtered[name] = value
        return filtered

    def _estimate_response_size(self, response: GatewayResponse) -> int:
        """Estimate response size in bytes."""
        size = 0

        # Headers
        for name, value in response.headers.items():
            size += len(name.encode()) + len(value.encode()) + 4  # ": \r\n"

        # Body
        if response.body:
            if isinstance(response.body, bytes):
                size += len(response.body)
            elif isinstance(response.body, str):
                size += len(response.body.encode())
            else:
                # Estimate for dict/object
                import json

                size += len(json.dumps(response.body).encode())

        return size

    async def _evict_if_necessary(self, new_response_size: int) -> None:
        """Evict entries if necessary to make room."""
        max_entries = self._config.max_entries
        max_memory = self._config.max_memory_mb * 1024 * 1024

        # Check entry count limit
        while len(self._cache) >= max_entries:
            await self._evict_lru()

        # Check memory limit
        while (self._stats.memory_usage_bytes + new_response_size) > max_memory:
            if not await self._evict_lru():
                break  # No more entries to evict

    async def _evict_lru(self) -> bool:
        """Evict least recently used entry."""
        if not self._cache:
            return False

        # Find LRU entry (lowest hits, oldest cache time)
        lru_key = min(
            self._cache.keys(),
            key=lambda k: (self._cache[k].hits, self._cache[k].cached_at),
        )

        await self.delete(lru_key)
        self._stats.evictions += 1
        return True

    async def _compress_response(
        self,
        cached_response: CachedResponse,
        original_size: int,
    ) -> None:
        """Compress response body if beneficial."""
        if original_size < self._config.compression_threshold:
            return

        if isinstance(cached_response.body, str | bytes):
            import gzip

            body_bytes = (
                cached_response.body.encode()
                if isinstance(cached_response.body, str)
                else cached_response.body
            )
            compressed = gzip.compress(
                body_bytes,
                compresslevel=self._config.compression_level,
            )

            # Only use compression if it reduces size significantly
            if len(compressed) < original_size * 0.9:
                cached_response.body = compressed
                cached_response.compressed = True
                cached_response.original_size = original_size
                cached_response.compressed_size = len(compressed)

    def _update_avg_lookup_time(self, lookup_time_ms: float) -> None:
        """Update average lookup time."""
        if self._stats.total_requests == 1:
            self._stats.avg_lookup_time_ms = lookup_time_ms
        else:
            self._stats.avg_lookup_time_ms = (
                self._stats.avg_lookup_time_ms * (self._stats.total_requests - 1)
                + lookup_time_ms
            ) / self._stats.total_requests

    def _update_avg_store_time(self, store_time_ms: float) -> None:
        """Update average store time."""
        count = self._stats.total_entries
        if count == 1:
            self._stats.avg_store_time_ms = store_time_ms
        else:
            self._stats.avg_store_time_ms = (
                self._stats.avg_store_time_ms * (count - 1) + store_time_ms
            ) / count


class CacheManager:
    """Main cache manager for response caching."""

    def __init__(self, config: CacheConfig | None = None) -> None:
        self._config = config or CacheConfig()
        self._key_generator = CacheKeyGenerator(self._config)

        # Initialize cache backend
        if self._config.strategy == CacheStrategy.MEMORY:
            self._cache = MemoryCache(self._config)
        else:
            # Default to memory cache
            self._cache = MemoryCache(self._config)

    async def get_cached_response(
        self,
        request: GatewayRequest,
        tenant_id: str | None = None,
        user_id: str | None = None,
    ) -> CachedResponse | None:
        """Get cached response for request."""
        if not self._config.enabled:
            return None

        if not self._is_cacheable_request(request):
            return None

        cache_key = self._key_generator.generate_key(request, tenant_id, user_id)
        return await self._cache.get(cache_key)

    async def cache_response(
        self,
        request: GatewayRequest,
        response: GatewayResponse,
        ttl: int | None = None,
        tenant_id: str | None = None,
        user_id: str | None = None,
    ) -> bool:
        """Cache response for future requests."""
        if not self._config.enabled:
            return False

        if not self._is_cacheable_request(request):
            return False

        cache_key = self._key_generator.generate_key(request, tenant_id, user_id)
        return await self._cache.set(cache_key, response, ttl, tenant_id, user_id)

    async def invalidate_cache(
        self,
        request: GatewayRequest | None = None,
        pattern: str | None = None,
        tenant_id: str | None = None,
    ) -> int:
        """Invalidate cached responses."""
        if pattern:
            # Pattern-based invalidation (simplified)
            return await self._cache.clear(tenant_id)
        if request:
            # Specific request invalidation
            cache_key = self._key_generator.generate_key(request, tenant_id)
            deleted = await self._cache.delete(cache_key)
            return 1 if deleted else 0
        # Clear all for tenant or everything
        return await self._cache.clear(tenant_id)

    async def get_cache_stats(self) -> CacheStats:
        """Get cache statistics."""
        return await self._cache.get_stats()

    def _is_cacheable_request(self, request: GatewayRequest) -> bool:
        """Check if request is cacheable."""
        # Check method
        if request.method.value not in self._config.cacheable_methods:
            return False

        # Check for cache control headers
        cache_control = request.headers.get("cache-control", "").lower()
        return "no-cache" not in cache_control


class CacheResult(BaseModel):
    """Cache operation result."""

    hit: bool
    cached_response: CachedResponse | None = None
    cache_key: str | None = None
    ttl_remaining: int | None = None

    model_config = ConfigDict(arbitrary_types_allowed=True)
