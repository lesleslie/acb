import typing as t

from hishel import (
    AsyncCacheClient,
    AsyncRedisStorage,
    Controller,
)
from hishel._utils import generate_key
from httpcore import Request
from httpx import Response as HttpxResponse
from redis.asyncio import Redis as AsyncRedis
from acb.depends import depends
from ._base import RequestsBase, RequestsBaseSettings


class RequestsSettings(RequestsBaseSettings): ...


class Requests(RequestsBase):
    storage: AsyncRedisStorage
    controller: Controller

    def cache_key(self, request: Request, body: bytes) -> str:
        key = generate_key(request, body)
        return f"{self.config.app.name}:httpx:{key}"

    async def get(self, url: str, timeout: int = 5) -> HttpxResponse:
        async with AsyncCacheClient(
            storage=self.storage, controller=self.controller
        ) as client:
            return await client.get(url, timeout=timeout)

    async def post(
        self, url: str, data: dict[str, t.Any], timeout: int = 5
    ) -> HttpxResponse:
        async with AsyncCacheClient(
            storage=self.storage, controller=self.controller
        ) as client:
            return await client.post(url, data=data, timeout=timeout)

    async def put(
        self, url: str, data: dict[str, t.Any], timeout: int = 5
    ) -> HttpxResponse:
        async with AsyncCacheClient(
            storage=self.storage, controller=self.controller
        ) as client:
            return await client.put(url, data=data, timeout=timeout)

    async def delete(self, url: str, timeout: int = 5) -> HttpxResponse:
        async with AsyncCacheClient(
            storage=self.storage, controller=self.controller
        ) as client:
            return await client.delete(url, timeout=timeout)

    @depends.inject
    async def init(self) -> None:  # type: ignore
        self.storage = AsyncRedisStorage(
            client=AsyncRedis(
                host=self.config.cache.host.get_secret_value(),
                port=self.config.cache.port,
                # db=self.config.requests.cache_db,
            ),
            ttl=self.config.requests.cache_ttl,
        )
        self.controller = Controller(key_generator=self.cache_key)  # type: ignore


depends.set(Requests)
