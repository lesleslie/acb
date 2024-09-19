import typing as t

from aiocache.backends.redis import RedisBackend
from coredis.cache import TrackingCache
from coredis.client import Redis, RedisCluster
from pydantic import SecretStr
from acb.adapters import import_adapter
from acb.config import Config
from acb.debug import debug
from acb.depends import depends
from ._base import CacheBase, CacheBaseSettings, SecurePickleSerializer

Logger = import_adapter()


class CacheSettings(CacheBaseSettings):
    host: SecretStr = SecretStr("127.0.0.1")
    local_host: str = "127.0.0.1"
    port: t.Optional[int] = 6379
    cluster: t.Optional[bool] = False
    connect_timeout: t.Optional[float] = None
    max_connections: t.Optional[int] = None
    health_check_interval: t.Optional[int] = 0

    @depends.inject
    def __init__(self, config: Config = depends(), **values: t.Any) -> None:
        super().__init__(**values)
        self.host = SecretStr(self.local_host) if not config.deployed else self.host


class Cache(CacheBase, RedisBackend):  # type: ignore
    async def _close(self, *args: t.Any, _conn: t.Any = None, **kwargs: t.Any) -> None:
        pass

    async def _clear(
        self, namespace: t.Optional[str] = None, _conn: t.Any = None
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

    async def init(self, *args: t.Any, **kwargs: t.Any) -> t.NoReturn:
        super().__init__(
            serializer=SecurePickleSerializer(),
            namespace=f"{self.config.app.name}:",
            **kwargs,
        )
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
