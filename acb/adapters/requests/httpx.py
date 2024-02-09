import typing as t

from acb.depends import depends
from httpx import Response as HttpxResponse
from hishel import AsyncCacheClient  # type: ignore
from hishel import RedisStorage  # type: ignore
from ._base import RequestsBase
from ._base import RequestsBaseSettings
from redis.asyncio import Redis as AsyncRedis


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
