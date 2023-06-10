from functools import cached_property
from functools import lru_cache

from acb import AppSettings
from httpx_cache import AsyncClient
from httpx_cache.cache.redis import RedisCache


class HttpxSettings(AppSettings):
    cache_db: int

    @cached_property
    def redis_connection(self):
        return AsyncClient(cache=RedisCache(redis_url="redis://localhost:6379/0"))


class Httpx:
    @staticmethod
    @lru_cache
    def get_redis_connection():
        connection = HttpxSettings.redis_connection
        return connection

    async def get(self, url):
        async with self.get_redis_connection() as client:  # type: ignore[override]
            return await client.get(url)
