import typing as t

from acb.config import ac
from httpx import Response as HttpxResponse
from httpx_cache import AsyncClient
from httpx_cache.cache.redis import RedisCache
from . import RequestBase
from . import RequestBaseSettings


class RequestSettings(RequestBaseSettings):
    ...


class Request(RequestBase):
    cache: t.Optional[RedisCache] = None

    async def get(self, url: str) -> HttpxResponse:
        async with AsyncClient(cache=self.cache) as client:
            return await client.get(url)

    async def post(self, url: str, data: dict) -> HttpxResponse:
        async with AsyncClient(cache=self.cache) as client:
            return await client.post(url, data=data)

    async def put(self, url: str, data: dict) -> HttpxResponse:
        async with AsyncClient(cache=self.cache) as client:
            return await client.put(url, data=data)

    async def delete(self, url: str) -> HttpxResponse:
        async with AsyncClient(cache=self.cache) as client:
            return await client.delete(url)

    async def init(self) -> None:
        self.cache = RedisCache(
            redis_url=f"redis://{ac.cache.host.get_secret_value()}:{ac.cache.port}/"
            f"{ac.request.cache_db}"
        )


#


request = Request()
