from functools import cached_property
from functools import lru_cache

from acb.config import ac
from httpx import Response as HttpxResponse
from httpx_cache import AsyncClient
from httpx_cache.cache.redis import RedisCache
from pydantic import AnyHttpUrl
from . import RequestsBaseSettings


class RequestsSettings(RequestsBaseSettings):
    @cached_property
    def redis_connection(self):
        return AsyncClient(
            cache=RedisCache(
                redis_url=f"redis://{ac.cache.host}:{ac.cache.port}/{self.cache_db}"
            )
        )


class Requests:
    @staticmethod
    @lru_cache
    def connection():
        return RequestsSettings.redis_connection

    async def get(self, url: AnyHttpUrl) -> HttpxResponse:
        async with self.connection() as client:
            return await client.get(url)

    async def post(self, url: AnyHttpUrl, data: dict) -> HttpxResponse:
        async with self.connection() as client:
            return await client.post(url, data)

    async def put(self, url: AnyHttpUrl, data: dict) -> HttpxResponse:
        async with self.connection() as client:
            return await client.put(url, data)

    async def delete(self, url: AnyHttpUrl) -> HttpxResponse:
        async with self.connection() as client:
            return await client.delete(url)

    async def init(self) -> None:
        ...


requests = Requests()
