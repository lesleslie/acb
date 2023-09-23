from acb.config import ac
from httpx import Response as HttpxResponse
from httpx_cache import AsyncClient
from httpx_cache.cache.redis import RedisCache
from pydantic import AnyHttpUrl
from . import RequestBaseSettings
import typing as t
from . import RequestBase


class RequestSettings(RequestBaseSettings):
    ...


class Request(RequestBase):
    client: t.Optional[AsyncClient] = None

    async def connection(self):
        async with self.client as client:
            yield client

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
        self.client = AsyncClient(
            cache=RedisCache(
                redis_url=f"redis://{ac.cache.host.get_secret_value()}:{ac.cache.port}/"
                f"{ac.request.cache_db}"
            )
        )


request = Request()
