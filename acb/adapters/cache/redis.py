import logging
import socket
import typing as t
from contextlib import suppress

from cashews.backends.redis.client import Redis, SafePipeline, SafeRedis
from cashews.exceptions import CacheBackendInteractionError
from cashews.serialize import Serializer, register_type
from pydantic import RedisDsn
from redis.asyncio.client import Pipeline
from redis.asyncio.cluster import ClusterPipeline
from redis.asyncio.cluster import RedisCluster as _RedisCluster
from redis.exceptions import RedisError as RedisConnectionError
from acb.actions.encode import dump, load
from acb.adapters import import_adapter
from acb.config import Config
from acb.depends import depends
from ._base import CacheBase, CacheBaseSettings

Logger = import_adapter()


class RedisCluster(_RedisCluster):
    async def execute_command(
        self,
        command: bytes | memoryview | str | int | float,
        *args: t.Any,
        **kwargs: t.Any,
    ):
        try:
            return await super().execute_command(command, *args, **kwargs)
        except (TimeoutError, RedisConnectionError, socket.gaierror, OSError) as exp:
            raise CacheBackendInteractionError() from exp


class SafeRedisCluster(_RedisCluster):
    logger: Logger = depends()  # type: ignore

    async def execute_command(
        self,
        command: str,
        *args: t.Any,
        **kwargs: t.Any,
    ) -> t.Any:
        try:
            return await super().execute_command(command, *args, **kwargs)
        except (TimeoutError, RedisConnectionError, socket.gaierror, OSError) as exp:
            if command.lower() == "ping":
                raise CacheBackendInteractionError() from exp
            self.logger.error(
                "redis: can not execute command: %s", command, exc_info=True
            )
            if command.lower() in ("unlink", "del", "memory", "ttl"):
                return 0
            if command.lower() == "scan":
                return [0, []]

    async def initialize(self):
        try:
            return await super().initialize()
        except (TimeoutError, RedisConnectionError, socket.gaierror, OSError):
            self.logger.error("redis: can not initialize cache", exc_info=True)
            return self

    __aenter__ = initialize


class SafeClusterPipeline(ClusterPipeline):
    logger: Logger = depends()  # type: ignore

    async def execute(  # type: ignore
        self, raise_on_error: bool = False, allow_redirections: bool = True
    ) -> None:  # type: ignore
        try:
            await super().execute(raise_on_error)
        except RedisConnectionError:
            self.logger.error("redis: can not execute pipeline", exc_info=True)


class CacheSettings(CacheBaseSettings):
    socket_timeout: t.Optional[float] = 1
    wait_for_connection_timeout: t.Optional[float] = 10
    retry_on_timeout: t.Optional[bool] = False
    disable: t.Optional[bool] = False
    max_connections: t.Optional[int] = 10
    cluster: t.Optional[bool] = False

    @depends.inject
    def __init__(self, config: Config = depends(), **values: t.Any) -> None:
        super().__init__(config, **values)
        self._url = RedisDsn(  # type: ignore
            f"redis://{self.host.get_secret_value()}:{self.port}?protocol=3"
        )


class Cache(CacheBase):
    async def encoder(self, value: t.Any, *args: t.Any, **kwargs: t.Any) -> bytes:
        return await dump.msgpack(
            value,
            secret_key=self.config.app.secret_key,
            secure_salt=self.config.app.secure_salt,
        )

    async def decoder(self, value: bytes, *args: t.Any, **kwargs: t.Any) -> t.Any:
        return await load.msgpack(
            value,
            secret_key=self.config.app.secret_key,
            secure_salt=self.config.app.secure_salt,
        )

    async def init(self, *args: t.Any, **kwargs: t.Any) -> t.NoReturn:
        self.logger.info(f"Cache url: {self.config.cache._url}")
        _logger = logging.getLogger("push_response")
        _logger.handlers.clear()
        cluster = False if not self.config.deployed else self.config.cache.cluster
        if cluster:
            self.logger.info("RedisCluster mode enabled")
        if not suppress:
            self._client_class = Redis if not cluster else RedisCluster
            self._pipeline_class = Pipeline if not cluster else ClusterPipeline
        else:
            self._pipeline_class = SafePipeline if not cluster else SafeClusterPipeline
            self._client_class = SafeRedis if not cluster else SafeRedisCluster
        super().__init__()
        await super().init(
            str(self.config.cache._url),
            client_side=True,
            client_side_prefix=self.config.cache.prefix,
            socket_timeout=self.config.cache.socket_timeout,
            disable=self.config.cache.disable,
            client_name=self.config.app.name,
        )
        register_type(Serializer, self.encoder, self.decoder)
        if not self.config.cache.disable:
            self.logger.debug(f"Ping:  {(await self.ping()).decode()}")


depends.set(Cache)
