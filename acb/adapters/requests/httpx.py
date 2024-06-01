import typing as t

from hishel import (
    AsyncCacheClient,  # type: ignore
    RedisStorage,  # type: ignore
)
from httpx import Response as HttpxResponse
from redis.asyncio import Redis as AsyncRedis
from acb.depends import depends
from ._base import RequestsBase, RequestsBaseSettings


class RequestsSettings(RequestsBaseSettings): ...


class Requests(RequestsBase):
    storage: RedisStorage  # type: ignore

    async def get(self, url: str, timeout: int = 5) -> HttpxResponse:
        async with AsyncCacheClient() as client:
            return await client.get(url, timeout=timeout)

    async def post(
        self, url: str, data: dict[str, t.Any], timeout: int = 5
    ) -> HttpxResponse:
        async with AsyncCacheClient() as client:
            return await client.post(url, data=data, timeout=timeout)

    async def put(
        self, url: str, data: dict[str, t.Any], timeout: int = 5
    ) -> HttpxResponse:
        async with AsyncCacheClient() as client:
            return await client.put(url, data=data, timeout=timeout)

    async def delete(self, url: str, timeout: int = 5) -> HttpxResponse:
        async with AsyncCacheClient(storage=self.storage) as client:
            return await client.delete(url, timeout=timeout)

    @depends.inject
    async def init(self) -> None:  # type: ignore
        self.storage = RedisStorage(
            client=AsyncRedis(
                host=self.config.cache.host.get_secret_value(),
                port=self.config.cache.port,
                db=self.config.requests.cache_db,
            ),
            ttl=self.config.requests.cache_ttl,
        )


depends.set(Requests)
