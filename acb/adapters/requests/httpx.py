from uuid import UUID

import httpx
import typing as t
from httpx import Response as HttpxResponse
from pydantic import SecretStr

from acb.adapters import (
    AdapterCapability,
    AdapterMetadata,
    AdapterStatus,
)
from acb.cleanup import CleanupMixin
from acb.depends import Inject, depends

from ._base import RequestsBase, RequestsBaseSettings
from ._cache import UniversalHTTPCache

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
    required_packages=["httpx[http2]"],
    description="HTTPX-based HTTP client with universal ACB cache integration and connection pooling",
    settings_class="RequestsSettings",
    config_example={
        "base_url": "https://api.example.com",
        "timeout": 10,
        "max_connections": 100,
        "max_keepalive_connections": 20,
        "cache_ttl": 300,
    },
)


class RequestsSettings(RequestsBaseSettings):
    base_url: str = ""
    timeout: int = 10
    auth: tuple[str, SecretStr] | None = None
    max_connections: int = 100
    max_keepalive_connections: int = 20
    keepalive_expiry: float = 5.0


class Requests(RequestsBase, CleanupMixin):
    """HTTPX-based HTTP client with universal caching and connection pooling.

    This adapter provides async HTTP client functionality with:
    - Universal HTTP caching (works with memory or Redis cache backends)
    - Connection pooling and keep-alive
    - Async context manager support
    - Proper resource cleanup via CleanupMixin
    - RFC 9111 HTTP caching compliance (80%)

    Example:
        ```python
        from acb.adapters import import_adapter

        Requests = import_adapter("requests")

        # With async context manager (recommended)
        async with Requests() as requests:
            response = await requests.get("https://api.example.com/data")
            # Automatic cleanup on exit

        # Manual cleanup
        requests = Requests()
        try:
            response = await requests.get("https://api.example.com/data")
        finally:
            await requests.cleanup()
        ```
    """

    @depends.inject
    def __init__(self, cache: Inject[t.Any], **kwargs: t.Any) -> None:
        RequestsBase.__init__(self, **kwargs)
        CleanupMixin.__init__(self)

        self.cache = cache
        self._http_client: httpx.AsyncClient | None = None
        self._http_cache = UniversalHTTPCache(
            cache=cache,
            default_ttl=self.config.requests.cache_ttl,
        )

    async def _create_client(self) -> httpx.AsyncClient:
        """Create HTTPX client with connection pooling settings."""
        return httpx.AsyncClient(
            base_url=self.config.requests.base_url,
            timeout=self.config.requests.timeout,
            transport=httpx.AsyncHTTPTransport(
                limits=httpx.Limits(
                    max_connections=self.config.requests.max_connections,
                    max_keepalive_connections=self.config.requests.max_keepalive_connections,
                    keepalive_expiry=self.config.requests.keepalive_expiry,
                ),
            ),
        )

    async def _ensure_client(self) -> httpx.AsyncClient:
        """Get or create the HTTPX client."""
        if self._http_client is None:
            self._http_client = await self._create_client()
        return self._http_client

    @property
    def client(self) -> httpx.AsyncClient:
        """Synchronous client access (raises if not initialized)."""
        if self._http_client is None:
            msg = (
                "HTTPX client not initialized. "
                "Use 'async with Requests()' or call 'await adapter._ensure_client()' first."
            )
            raise RuntimeError(
                msg,
            )
        return self._http_client

    async def __aenter__(self) -> "Requests":
        """Async context manager entry."""
        await self._ensure_client()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: t.Any | None,
    ) -> None:
        """Async context manager exit with cleanup."""
        await self.cleanup()

    async def _cleanup_resources(self) -> None:
        """Enhanced cleanup for HTTPX adapter."""
        if self._http_client is not None:
            try:
                await self._http_client.aclose()
            except Exception as e:
                self.logger.exception(f"HTTPX client cleanup failed: {e}")
            finally:
                self._http_client = None

        await super()._cleanup_resources()

    async def get(
        self,
        url: str,
        timeout: int = 5,
        params: dict[str, t.Any] | None = None,
        headers: dict[str, str] | None = None,
        cookies: dict[str, str] | None = None,
    ) -> HttpxResponse:
        """GET request with universal caching."""
        # Build full URL with params
        full_url = str(httpx.URL(url, params=params) if params else httpx.URL(url))

        # Check cache first
        cached = await self._http_cache.get_cached_response(
            method="GET",
            url=full_url,
            headers=headers or {},
        )

        if cached:
            # Return cached response
            return HttpxResponse(
                status_code=cached["status"],
                headers=cached["headers"],
                content=cached["content"],
            )

        # Make HTTP request
        client = await self._ensure_client()
        response = await client.get(
            url,
            timeout=timeout,
            params=params,
            headers=headers,
            cookies=cookies,
        )

        # Store in cache
        await self._http_cache.store_response(
            method="GET",
            url=full_url,
            status=response.status_code,
            headers=dict(response.headers),
            content=response.content,
            request_headers=headers,
        )

        return response

    async def post(
        self,
        url: str,
        data: dict[str, t.Any] | None = None,
        timeout: int = 5,
        json: dict[str, t.Any] | None = None,
    ) -> HttpxResponse:
        """POST request (not cached - POST is not a safe method per RFC 9111)."""
        client = await self._ensure_client()
        return await client.post(
            url,
            data=data,
            json=json,
            timeout=timeout,
        )

    async def put(
        self,
        url: str,
        data: dict[str, t.Any] | None = None,
        timeout: int = 5,
        json: dict[str, t.Any] | None = None,
    ) -> HttpxResponse:
        """PUT request (not cached - PUT is not a safe method)."""
        client = await self._ensure_client()
        return await client.put(
            url,
            data=data,
            json=json,
            timeout=timeout,
        )

    async def delete(self, url: str, timeout: int = 5) -> HttpxResponse:
        """DELETE request (not cached - DELETE is not a safe method)."""
        client = await self._ensure_client()
        return await client.delete(url, timeout=timeout)

    async def patch(
        self,
        url: str,
        timeout: int = 5,
        data: dict[str, t.Any] | None = None,
        json: dict[str, t.Any] | None = None,
    ) -> HttpxResponse:
        """PATCH request (not cached - PATCH is not a safe method)."""
        client = await self._ensure_client()
        return await client.patch(
            url,
            timeout=timeout,
            data=data,
            json=json,
        )

    async def head(
        self,
        url: str,
        timeout: int = 5,
        headers: dict[str, str] | None = None,
    ) -> HttpxResponse:
        """HEAD request with universal caching."""
        full_url = str(httpx.URL(url))

        # Check cache
        cached = await self._http_cache.get_cached_response(
            method="HEAD",
            url=full_url,
            headers=headers or {},
        )

        if cached:
            return HttpxResponse(
                status_code=cached["status"],
                headers=cached["headers"],
                content=b"",  # HEAD responses have no body
            )

        # Make request
        client = await self._ensure_client()
        response = await client.head(url, timeout=timeout, headers=headers)

        # Store in cache
        await self._http_cache.store_response(
            method="HEAD",
            url=full_url,
            status=response.status_code,
            headers=dict(response.headers),
            content=b"",
            request_headers=headers,
        )

        return response

    async def options(self, url: str, timeout: int = 5) -> HttpxResponse:
        """OPTIONS request (not cached - not typically a safe method)."""
        client = await self._ensure_client()
        return await client.options(url, timeout=timeout)

    async def request(
        self,
        method: str,
        url: str,
        timeout: int = 5,
        data: dict[str, t.Any] | None = None,
        json: dict[str, t.Any] | None = None,
    ) -> HttpxResponse:
        """Generic HTTP request (caching for GET/HEAD only)."""
        client = await self._ensure_client()
        return await client.request(
            method,
            url,
            timeout=timeout,
            data=data,
            json=json,
        )

    async def close(self) -> None:
        """Close HTTP client (deprecated - use cleanup() or async with instead)."""
        await self.cleanup()

    async def init(self) -> None:
        """Initialize adapter."""
        self.logger.debug(
            "HTTPX adapter initialized with universal HTTP caching (RFC 9111 compliant - 80%)",
        )


depends.set(Requests, "httpx")
