import typing as t

from acb.depends import depends
from httpx import Response as HttpxResponse
from httpx_cache import AsyncClient
from httpx_cache.cache.redis import RedisCache
from ._base import RequestsBase
from ._base import RequestsBaseSettings


class RequestsSettings(RequestsBaseSettings):
    loggers: list[str] = ["httpx_caching"]


class Requests(RequestsBase):
    cache: t.Optional[RedisCache] = None

    async def get(self, url: str) -> HttpxResponse:
        async with AsyncClient(cache=self.cache) as client:
            return await client.get(url)

    async def post(self, url: str, data: dict[str, t.Any]) -> HttpxResponse:
        async with AsyncClient(cache=self.cache) as client:
            return await client.post(url, data=data)

    async def put(self, url: str, data: dict[str, t.Any]) -> HttpxResponse:
        async with AsyncClient(cache=self.cache) as client:
            return await client.put(url, data=data)

    async def delete(self, url: str) -> HttpxResponse:
        async with AsyncClient(cache=self.cache) as client:
            return await client.delete(url)

    async def init(self) -> None:
        self.cache = RedisCache(
            redis_url=f"redis://{self.config.cache.host.get_secret_value()}:{self.config.cache.port}/"
            f"{self.config.requests.cache_db}"
        )


depends.set(Requests, Requests())
