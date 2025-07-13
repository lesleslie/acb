"""Redis Cache Adapter for ACB.

Integrates ACB with Redis for high-performance distributed caching using both
aiocache and coredis for maximum compatibility and features.

Features:
    - Connection pooling with configurable limits
    - Cluster support for high availability
    - Health check monitoring
    - Automatic reconnection on failures
    - Tracking cache for debugging
    - Namespace-based key organization

Requirements:
    - Redis server (standalone or cluster)
    - aiocache[redis] for cache interface
    - coredis for advanced Redis features

Example:
    Basic usage with Redis caching:

    ```python
    from acb.depends import depends
    from acb.adapters import import_adapter

    Cache = import_adapter("cache")


    @depends.inject
    async def my_function(cache: Cache = depends()):
        await cache.set("user:123", {"name": "John"}, ttl=300)
        user_data = await cache.get("user:123")
        return user_data
    ```

Author: lesleslie <les@wedgwoodwebworks.com>
Created: 2025-01-12
"""

import typing as t
from uuid import UUID

from aiocache.backends.redis import RedisBackend
from aiocache.serializers import PickleSerializer
from coredis.cache import TrackingCache
from coredis.client import Redis, RedisCluster
from pydantic import SecretStr
from acb.adapters import AdapterStatus
from acb.config import Config
from acb.debug import debug
from acb.depends import depends

from ._base import CacheBase, CacheBaseSettings

MODULE_ID = UUID("0197fe78-4fc8-73f6-be8a-78fd61b63a07")
MODULE_STATUS = AdapterStatus.STABLE


class CacheSettings(CacheBaseSettings):
    host: SecretStr = SecretStr("127.0.0.1")
    local_host: str = "127.0.0.1"
    port: int | None = 6379
    cluster: bool | None = False
    connect_timeout: float | None = 3
    max_connections: int | None = 50
    health_check_interval: int | None = 0
    retry_on_timeout: bool | None = True

    @depends.inject
    def __init__(self, config: Config = depends(), **values: t.Any) -> None:
        super().__init__(**values)
        self.host = SecretStr(self.local_host) if not config.deployed else self.host


class Cache(CacheBase, RedisBackend):
    def __init__(self, redis_url: str | None = None, **kwargs: t.Any) -> None:
        self.redis_url = redis_url
        self._init_kwargs = {k: v for k, v in kwargs.items() if k != "redis_url"}
        super().__init__()

    async def _create_client(self) -> Redis[t.Any] | RedisCluster[t.Any]:
        redis_kwargs = self._init_kwargs | {
            "host": self.config.cache.host.get_secret_value(),
            "port": self.config.cache.port,
            "client_name": self.config.app.name,
            "cache": TrackingCache(),
            "decode_responses": False,
            "connect_timeout": self.config.cache.connect_timeout,
            "max_connections": self.config.cache.max_connections,
            "health_check_interval": self.config.cache.health_check_interval,
            "retry_on_timeout": self.config.cache.retry_on_timeout,
        }
        if self.config.cache.cluster:
            self.logger.info("RedisCluster mode enabled")
            del redis_kwargs["health_check_interval"]
            return RedisCluster(**redis_kwargs)

        return Redis(**redis_kwargs)

    async def get_client(self) -> Redis[t.Any] | RedisCluster[t.Any]:
        return await self._ensure_client()

    async def _close(self, *args: t.Any, _conn: t.Any = None, **kwargs: t.Any) -> None:
        if self._client is not None:
            await self._client.close()

    async def _clear(
        self,
        namespace: str | None = None,
        _conn: t.Any = None,
    ) -> t.Literal[True]:
        if not namespace:
            pattern = f"{self.config.app.name}:*"
        else:
            pattern = f"{self.config.app.name}:{namespace}:*"
        client = await self.get_client()
        keys = await client.keys(pattern)
        if keys:
            debug(keys)
            for key in keys:
                await client.unlink((key,))
        return True

    async def _exists(self, key: str, _conn: t.Any = None) -> bool:
        client = await self.get_client()
        number = await client.exists([key])
        return bool(number)

    async def init(self, *args: t.Any, **kwargs: t.Any) -> None:
        self._init_kwargs.update(kwargs)
        if not hasattr(self, "_namespace"):
            self._namespace = f"{self.config.app.name}:"
        if not hasattr(self, "_serializer"):
            self._serializer = PickleSerializer()


depends.set(Cache)
