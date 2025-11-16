from uuid import UUID

import httpx
import typing as t
from hishel import (  # type: ignore[import-not-found]
    AsyncCacheClient,
    AsyncRedisStorage,
    Controller,
)
from hishel._utils import generate_key  # type: ignore[import-not-found]
from httpcore import Request
from httpx import Response as HttpxResponse
from pydantic import SecretStr
from redis.asyncio import Redis as AsyncRedis

from acb.adapters import (
    AdapterCapability,
    AdapterMetadata,
    AdapterStatus,
    import_adapter,
)
from acb.depends import depends

from ._base import RequestsBase, RequestsBaseSettings

MODULE_ID = UUID("0197ff55-9026-7672-b2aa-b835cf3f2f3a")
MODULE_STATUS = AdapterStatus.STABLE

MODULE_METADATA = AdapterMetadata(
    module_id=MODULE_ID,
    name="HTTPX Requests",
    category="requests",
    provider="httpx",
    version="1.0.0",
    acb_min_version="0.18.0",
    author="lesleslie <les@wedgwoodwebworks.com>",
    created_date="2025-01-12",
    last_modified="2025-01-20",
    status=MODULE_STATUS,
    capabilities=[
        AdapterCapability.ASYNC_OPERATIONS,
        AdapterCapability.CONNECTION_POOLING,
        AdapterCapability.CACHING,
        AdapterCapability.TLS_SUPPORT,
        AdapterCapability.RECONNECTION,
    ],
    required_packages=["httpx[http2]", "hishel", "redis"],
    description="HTTPX-based HTTP client with Redis caching and connection pooling",
    settings_class="RequestsSettings",
    config_example={
        "base_url": "https://api.example.com",
        "timeout": 10,
        "max_connections": 100,
        "max_keepalive_connections": 20,
        "cache_ttl": 300,
    },
)

Cache = import_adapter()


class RequestsSettings(RequestsBaseSettings):
    base_url: str = ""
    timeout: int = 10
    auth: tuple[str, SecretStr] | None = None
    max_connections: int = 100
    max_keepalive_connections: int = 20
    keepalive_expiry: float = 5.0


class Requests(RequestsBase):
    def __init__(self, **kwargs: t.Any) -> None:
        super().__init__(**kwargs)
        self._storage: AsyncRedisStorage | None = None
        self._controller: Controller | None = None
        self._client_cache: dict[str, AsyncCacheClient] = {}

    async def _create_storage(self) -> AsyncRedisStorage:
        redis_client = AsyncRedis(  # type: ignore[abstract]
            host=self.config.cache.host.get_secret_value(),
            port=self.config.cache.port,
        )
        return AsyncRedisStorage(
            client=redis_client,
            ttl=self.config.requests.cache_ttl,
        )

    async def _create_controller(self) -> Controller:
        return Controller(key_generator=t.cast("t.Any", self.cache_key))

    async def get_storage(self) -> AsyncRedisStorage:
        if self._storage is None:
            self._storage = await self._create_storage()
        return self._storage

    async def get_controller(self) -> Controller:
        if self._controller is None:
            self._controller = await self._create_controller()
        return self._controller

    @property
    def storage(self) -> AsyncRedisStorage | None:
        return self._storage

    @storage.setter
    def storage(self, value: AsyncRedisStorage) -> None:
        self._storage = value

    @property
    def controller(self) -> Controller | None:
        return self._controller

    @controller.setter
    def controller(self, value: Controller) -> None:
        self._controller = value

    def cache_key(self, request: Request, body: bytes) -> str:
        key = generate_key(request, body)
        app_name = self.config.app.name if self.config.app else "default"
        return f"{app_name}:httpx:{key}"

    async def _get_cached_client(self, client_key: str = "default") -> AsyncCacheClient:
        if client_key not in self._client_cache:
            storage = await self.get_storage()
            controller = await self.get_controller()
            self._client_cache[client_key] = AsyncCacheClient(
                storage=storage,
                controller=controller,
                timeout=self.config.requests.timeout,
                limits=httpx.Limits(
                    max_connections=self.config.requests.max_connections,
                    max_keepalive_connections=self.config.requests.max_keepalive_connections,
                    keepalive_expiry=self.config.requests.keepalive_expiry,
                ),
            )
        return self._client_cache[client_key]

    async def get(
        self,
        url: str,
        timeout: int = 5,
        params: dict[str, t.Any] | None = None,
        headers: dict[str, str] | None = None,
        cookies: dict[str, str] | None = None,
    ) -> HttpxResponse:
        client = await self._get_cached_client()
        return await client.get(
            url,
            timeout=timeout,
            params=params,
            headers=headers,
            cookies=cookies,
        )

    async def post(
        self,
        url: str,
        data: dict[str, t.Any] | None = None,
        timeout: int = 5,
        json: dict[str, t.Any] | None = None,
    ) -> HttpxResponse:
        client = await self._get_cached_client()
        return await client.post(url, data=data, json=json, timeout=timeout)

    async def put(
        self,
        url: str,
        data: dict[str, t.Any] | None = None,
        timeout: int = 5,
        json: dict[str, t.Any] | None = None,
    ) -> HttpxResponse:
        client = await self._get_cached_client()
        return await client.put(url, data=data, json=json, timeout=timeout)

    async def delete(self, url: str, timeout: int = 5) -> HttpxResponse:
        client = await self._get_cached_client()
        return await client.delete(url, timeout=timeout)

    async def patch(
        self,
        url: str,
        timeout: int = 5,
        data: dict[str, t.Any] | None = None,
        json: dict[str, t.Any] | None = None,
    ) -> HttpxResponse:
        client = await self._get_cached_client()
        return await client.patch(url, timeout=timeout, data=data, json=json)

    async def head(self, url: str, timeout: int = 5) -> HttpxResponse:
        client = await self._get_cached_client()
        return await client.head(url, timeout=timeout)

    async def options(self, url: str, timeout: int = 5) -> HttpxResponse:
        client = await self._get_cached_client()
        return await client.options(url, timeout=timeout)

    async def request(
        self,
        method: str,
        url: str,
        timeout: int = 5,
        data: dict[str, t.Any] | None = None,
        json: dict[str, t.Any] | None = None,
    ) -> HttpxResponse:
        client = await self._get_cached_client()
        return await client.request(method, url, timeout=timeout, data=data, json=json)

    async def close(self) -> None:
        for client in self._client_cache.values():
            await client.aclose()
        self._client_cache.clear()

    async def init(self) -> None:
        self.logger.debug("HTTPX adapter initialized with lazy loading")


depends.set(Requests, "httpx")
