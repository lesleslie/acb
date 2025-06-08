import typing as t

from aiocache.backends.redis import RedisBackend
from aiocache.serializers import PickleSerializer
from coredis.cache import TrackingCache
from coredis.client import Redis, RedisCluster
from pydantic import SecretStr
from acb.config import Config
from acb.debug import debug
from acb.depends import depends

from ._base import CacheBase, CacheBaseSettings


class CacheSettings(CacheBaseSettings):
    host: SecretStr = SecretStr("127.0.0.1")
    local_host: str = "127.0.0.1"
    port: int | None = 6379
    cluster: bool | None = False
    connect_timeout: float | None = 3
    max_connections: int | None = None
    health_check_interval: int | None = 0

    @depends.inject
    def __init__(self, config: Config = depends(), **values: t.Any) -> None:
        super().__init__(**values)
        self.host = SecretStr(self.local_host) if not config.deployed else self.host


class Cache(CacheBase, RedisBackend):
    def __init__(self, redis_url: str | None = None, **kwargs: t.Any) -> None:
        self.redis_url = redis_url
        filtered_kwargs = {k: v for k, v in kwargs.items() if k != "redis_url"}
        super().__init__(**filtered_kwargs)

    async def _close(self, *args: t.Any, _conn: t.Any = None, **kwargs: t.Any) -> None:
        pass

    async def _clear(
        self, namespace: str | None = None, _conn: t.Any = None
    ) -> t.Literal[True]:
        if not namespace:
            pattern = f"{self.config.app.name}:*"
        else:
            pattern = f"{self.config.app.name}:{namespace}:*"
        keys = await self.client.keys(pattern)
        if keys:
            debug(keys)
            for key in keys:
                await self.client.unlink((key,))
        return True

    async def _exists(self, key: str, _conn: t.Any = None) -> bool:
        number = await self.client.exists([key])
        return bool(number)

    async def init(self, *args: t.Any, **kwargs: t.Any) -> None:
        if not hasattr(self, "_namespace"):
            self._namespace = f"{self.config.app.name}:"
        if not hasattr(self, "_serializer"):
            self._serializer = PickleSerializer()
        redis_kwargs = dict(
            host=self.config.cache.host.get_secret_value(),
            port=self.config.cache.port,
            client_name=self.config.app.name,
            cache=TrackingCache(),
            decode_responses=False,
            connect_timeout=self.config.cache.connect_timeout,
            max_connections=self.config.cache.max_connections,
            health_check_interval=self.config.cache.health_check_interval,
        )
        if self.config.cache.cluster:
            self.logger.info("RedisCluster mode enabled")
            del redis_kwargs["health_check_interval"]
            self.client = RedisCluster(**redis_kwargs)
        else:
            self.client = Redis(**redis_kwargs)


depends.set(Cache)
