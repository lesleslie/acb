import typing as t

from acb.adapters.logger import Logger
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

    async def get(self, url: str, timeout: int = 5) -> HttpxResponse:
        async with AsyncClient(cache=self.cache) as client:
            return await client.get(url, timeout=timeout)

    async def post(
        self, url: str, data: dict[str, t.Any], timeout: int = 5
    ) -> HttpxResponse:
        async with AsyncClient(cache=self.cache) as client:
            return await client.post(url, data=data, timeout=timeout)

    async def put(
        self, url: str, data: dict[str, t.Any], timeout: int = 5
    ) -> HttpxResponse:
        async with AsyncClient(cache=self.cache) as client:
            return await client.put(url, data=data, timeout=timeout)

    async def delete(self, url: str, timeout: int = 5) -> HttpxResponse:
        async with AsyncClient(cache=self.cache) as client:
            return await client.delete(url, timeout=timeout)

    @depends.inject
    async def init(self, logger: Logger = depends()) -> None:  # type: ignore
        self.cache = RedisCache(
            redis_url=f"redis://{self.config.cache.host.get_secret_value()}:{self.config.cache.port}/"
            f"{self.config.requests.cache_db}"
        )
        logger.info("Requests adapter loaded")


depends.set(Requests, Requests())
