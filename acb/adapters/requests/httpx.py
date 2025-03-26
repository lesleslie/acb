import typing as t

from hishel import AsyncCacheClient, AsyncRedisStorage, Controller
from hishel._utils import generate_key
from httpcore import Request
from httpx import Response as HttpxResponse
from pydantic import SecretStr
from redis.asyncio import Redis as AsyncRedis
from acb.adapters import import_adapter
from acb.depends import depends

from ._base import RequestsBase, RequestsBaseSettings


class RequestsSettings(RequestsBaseSettings):
    base_url: str = ""
    timeout: int = 10
    auth: t.Optional[tuple[str, SecretStr]] = None


class Requests(RequestsBase):
    storage: AsyncRedisStorage
    controller: Controller

    def cache_key(self, request: Request, body: bytes) -> str:
        key = generate_key(request, body)
        return f"{self.config.app.name}:httpx:{key}"

    async def get(
        self,
        url: str,
        timeout: int = 5,
        params: t.Optional[dict[str, t.Any]] = None,
        headers: t.Optional[dict[str, str]] = None,
        cookies: t.Optional[dict[str, str]] = None,
    ) -> HttpxResponse:
        async with AsyncCacheClient(
            storage=self.storage, controller=self.controller
        ) as client:
            return await client.get(
                url, timeout=timeout, params=params, headers=headers, cookies=cookies
            )

    async def post(
        self,
        url: str,
        data: t.Optional[dict[str, t.Any]] = None,
        timeout: int = 5,
        json: t.Optional[dict[str, t.Any]] = None,
    ) -> HttpxResponse:
        async with AsyncCacheClient(
            storage=self.storage, controller=self.controller
        ) as client:
            return await client.post(url, data=data, json=json, timeout=timeout)

    async def put(
        self,
        url: str,
        data: t.Optional[dict[str, t.Any]] = None,
        timeout: int = 5,
        json: t.Optional[dict[str, t.Any]] = None,
    ) -> HttpxResponse:
        async with AsyncCacheClient(
            storage=self.storage, controller=self.controller
        ) as client:
            return await client.put(url, data=data, json=json, timeout=timeout)

    async def delete(self, url: str, timeout: int = 5) -> HttpxResponse:
        async with AsyncCacheClient(
            storage=self.storage, controller=self.controller
        ) as client:
            return await client.delete(url, timeout=timeout)

    async def patch(
        self,
        url: str,
        timeout: int = 5,
        data: t.Optional[dict[str, t.Any]] = None,
        json: t.Optional[dict[str, t.Any]] = None,
    ) -> HttpxResponse:
        async with AsyncCacheClient(
            storage=self.storage, controller=self.controller
        ) as client:
            return await client.patch(url, timeout=timeout, data=data, json=json)

    async def head(self, url: str, timeout: int = 5) -> HttpxResponse:
        async with AsyncCacheClient(
            storage=self.storage, controller=self.controller
        ) as client:
            return await client.head(url, timeout=timeout)

    async def options(self, url: str, timeout: int = 5) -> HttpxResponse:
        async with AsyncCacheClient(
            storage=self.storage, controller=self.controller
        ) as client:
            return await client.options(url, timeout=timeout)

    async def request(
        self,
        method: str,
        url: str,
        timeout: int = 5,
        data: t.Optional[dict[str, t.Any]] = None,
        json: t.Optional[dict[str, t.Any]] = None,
    ) -> HttpxResponse:
        async with AsyncCacheClient(
            storage=self.storage, controller=self.controller
        ) as client:
            return await client.request(
                method, url, timeout=timeout, data=data, json=json
            )

    async def close(self) -> None:
        pass

    @depends.inject
    async def init(self) -> None:  # type: ignore
        import_adapter("cache")
        self.storage = AsyncRedisStorage(
            client=AsyncRedis(
                host=self.config.cache.host.get_secret_value(),
                port=self.config.cache.port,
            ),
            ttl=self.config.requests.cache_ttl,
        )
        self.controller = Controller(key_generator=self.cache_key)  # type: ignore


depends.set(Requests)
