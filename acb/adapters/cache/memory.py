from uuid import UUID

import typing as t
from aiocache.backends.memory import SimpleMemoryCache
from aiocache.serializers import PickleSerializer

from acb.adapters import AdapterCapability, AdapterMetadata, AdapterStatus

# Removed complex mixins - simplified memory cache implementation
from acb.depends import depends

from ._base import CacheBase, CacheBaseSettings

MODULE_ID = UUID("0197ff44-8c12-7f30-af61-2d41c6c89a72")
MODULE_STATUS = AdapterStatus.STABLE

MODULE_METADATA = AdapterMetadata(
    module_id=MODULE_ID,
    name="Memory Cache",
    category="cache",
    provider="memory",
    version="1.0.0",
    acb_min_version="0.18.0",
    author="lesleslie <les@wedgwoodwebworks.com>",
    created_date="2025-01-12",
    last_modified="2025-01-15",
    status=MODULE_STATUS,
    capabilities=[
        AdapterCapability.ASYNC_OPERATIONS,
        AdapterCapability.CACHING,
    ],
    required_packages=["aiocache"],
    description="In-memory caching adapter (no TLS - local storage only)",
    settings_class="CacheSettings",
    config_example={
        "default_ttl": 86400,
        "query_ttl": 600,
    },
)


class CacheSettings(CacheBaseSettings): ...


class Cache(CacheBase):
    def __init__(self, **kwargs: t.Any) -> None:
        super().__init__(**kwargs)
        self._init_kwargs = kwargs

    async def _create_client(self) -> SimpleMemoryCache:
        namespace = f"{self.config.app.name}:" if self.config.app else "acb:"
        cache = SimpleMemoryCache(
            serializer=PickleSerializer(),
            namespace=namespace,
            **self._init_kwargs,
        )
        cache.timeout = 0.0
        return cache

    async def _cleanup_resources(self) -> None:
        """Enhanced memory cache resource cleanup."""
        errors = []

        # Clean up advanced cache if initialized
        if hasattr(self, "_multi_tier_cache") and self._multi_tier_cache is not None:
            try:
                await self._multi_tier_cache.cleanup()
                self.logger.debug("Successfully cleaned up advanced cache")  # type: ignore[no-untyped-call]
            except Exception as e:
                errors.append(f"Failed to cleanup advanced cache: {e}")

        # Simplified cleanup - no tracing

        # Clean up memory cache
        if self._client is not None:
            try:
                # Clear all cached data to prevent memory leaks
                await self._client.clear()
                # Close any background tasks or connections
                if hasattr(self._client, "close"):
                    await self._client.close()
                self.logger.debug("Successfully cleaned up memory cache")  # type: ignore[no-untyped-call]
            except Exception as e:
                errors.append(f"Failed to cleanup memory cache: {e}")
            finally:
                # Always set client to None to prevent memory leaks
                self._client = None

        # Call parent cleanup (skip since we handle everything here)
        # The base class cleanup is handled by the main cleanup() method

        if errors:
            self.logger.warning(f"Memory cache cleanup errors: {'; '.join(errors)}")  # type: ignore[no-untyped-call]

    async def get_client(self) -> SimpleMemoryCache:
        return await self._ensure_client()

    @property
    def _cache(self) -> SimpleMemoryCache:
        client = getattr(self, "_client", None)
        if client is None:
            namespace = f"{self.config.app.name}:" if self.config.app else "acb:"
            cache = SimpleMemoryCache(
                serializer=PickleSerializer(),
                namespace=namespace,
                **self._init_kwargs,
            )
            cache.timeout = 0.0
            self._client = cache
        return self._client

    async def init(self, *args: t.Any, **kwargs: t.Any) -> None:
        self._init_kwargs.update(kwargs)

    async def _set(
        self,
        key: str,
        value: t.Any,
        ttl: int | None = None,
        _cas_token: t.Any = None,
        _conn: t.Any = None,
    ) -> None:
        """Simple set operation without tracing."""
        cache = await self.get_client()
        await cache.set(key, value, ttl=ttl)

    async def _get(
        self,
        key: str,
        encoding: str = "utf-8",
        _conn: t.Any = None,
    ) -> t.Any:
        """Simple get operation without tracing."""
        cache = await self.get_client()
        return await cache.get(key)

    async def _delete(self, key: str, _conn: t.Any = None) -> bool:
        cache = await self.get_client()
        return bool(await cache.delete(key))

    async def _exists(self, key: str, _conn: t.Any = None) -> bool:
        cache = await self.get_client()
        return bool(await cache.exists(key))

    async def _clear(self, namespace: str | None = None, _conn: t.Any = None) -> bool:
        cache = await self.get_client()
        return bool(await cache.clear(namespace=namespace))

    async def _multi_set(
        self,
        pairs: list[tuple[str, t.Any]],
        ttl: int | None = None,
        _conn: t.Any = None,
    ) -> None:
        cache = await self.get_client()
        await cache.multi_set(pairs, ttl=ttl)

    async def _multi_get(
        self,
        keys: list[str],
        encoding: str = "utf-8",
        _conn: t.Any = None,
    ) -> list[t.Any]:
        cache = await self.get_client()
        return list(await cache.multi_get(keys))

    async def _add(
        self,
        key: str,
        value: t.Any,
        ttl: int | None = None,
        _conn: t.Any = None,
    ) -> bool:
        cache = await self.get_client()
        return bool(await cache.add(key, value, ttl=ttl))

    async def _increment(self, key: str, delta: int = 1, _conn: t.Any = None) -> int:
        cache = await self.get_client()
        return int(await cache.increment(key, delta=delta))

    async def _expire(self, key: str, ttl: int, _conn: t.Any = None) -> bool:
        cache = await self.get_client()
        return bool(await cache.expire(key, ttl=ttl))


depends.set(Cache, "memory")
