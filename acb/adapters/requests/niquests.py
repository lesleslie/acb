from uuid import UUID

import typing as t

try:
    import niquests
    from niquests import Response as NiquestsResponse
except Exception:  # pragma: no cover - allow tests without niquests installed
    import os as _os
    import sys as _sys

    if "pytest" in _sys.modules or _os.getenv("TESTING", "False").lower() == "true":
        from unittest.mock import MagicMock

        niquests = MagicMock()  # type: ignore[assignment]
        NiquestsResponse = MagicMock  # type: ignore[assignment]
    else:
        raise

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

MODULE_ID = UUID("0197ff55-9026-7672-b2aa-b843381c6604")
MODULE_STATUS = AdapterStatus.STABLE

MODULE_METADATA = AdapterMetadata(
    module_id=MODULE_ID,
    name="Niquests HTTP Client",
    category="requests",
    provider="niquests",
    version="1.0.0",
    acb_min_version="0.18.0",
    author="lesleslie <les@wedgwoodwebworks.com>",
    created_date="2025-01-12",
    last_modified="2025-01-20",
    status=MODULE_STATUS,
    capabilities=[
        AdapterCapability.ASYNC_OPERATIONS,
        AdapterCapability.TLS_SUPPORT,
        AdapterCapability.CONNECTION_POOLING,
        AdapterCapability.CACHING,
        AdapterCapability.RECONNECTION,
    ],
    required_packages=["niquests"],
    description=(
        "Niquests-based HTTP client with universal ACB cache integration "
        "and connection pooling"
    ),
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


class Requests(RequestsBase, CleanupMixin):
    """Niquests-based HTTP client with universal caching and connection pooling.

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
        self._http_client: niquests.AsyncSession | None = None
        self._http_cache = UniversalHTTPCache(
            cache=cache,
            default_ttl=self.config.requests.cache_ttl,
        )

    async def _create_client(self) -> niquests.AsyncSession:
        """Create Niquests session with connection pooling settings."""
        session = niquests.AsyncSession(
            pool_connections=self.config.requests.max_connections,
            pool_maxsize=self.config.requests.max_keepalive_connections,
        )

        if self.config.requests.base_url:
            session.base_url = self.config.requests.base_url

        if self.config.requests.auth:
            username, password = self.config.requests.auth
            session.auth = (username, password.get_secret_value())

        return session

    async def _ensure_client(self) -> niquests.AsyncSession:
        """Get or create the Niquests session."""
        if self._http_client is None:
            self._http_client = await self._create_client()
        return self._http_client

    @property
    def client(self) -> niquests.AsyncSession:
        """Synchronous client access (raises if not initialized)."""
        if self._http_client is None:
            msg = (
                "Niquests client not initialized. "
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
        """Enhanced cleanup for Niquests adapter."""
        if self._http_client is not None:
            try:
                await self._http_client.close()
            except Exception as e:
                self.logger.exception(f"Niquests client cleanup failed: {e}")
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
    ) -> NiquestsResponse:
        """GET request with universal caching."""
        # Build full URL with params
        if params:
            # Niquests handles params, so we need to build URL for cache key
            from urllib.parse import urlencode

            query_string = urlencode(params)
            full_url = f"{url}?{query_string}"
        else:
            full_url = url

        # Check cache first
        cached = await self._http_cache.get_cached_response(
            method="GET",
            url=full_url,
            headers=headers or {},
        )

        if cached:
            # Return cached response as Niquests Response object
            response = NiquestsResponse()
            response.status_code = cached["status"]
            response.headers.update(cached["headers"])
            response._content = cached["content"]
            return response

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
    ) -> NiquestsResponse:
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
    ) -> NiquestsResponse:
        """PUT request (not cached - PUT is not a safe method)."""
        client = await self._ensure_client()
        return await client.put(
            url,
            data=data,
            json=json,
            timeout=timeout,
        )

    async def delete(self, url: str, timeout: int = 5) -> NiquestsResponse:
        """DELETE request (not cached - DELETE is not a safe method)."""
        client = await self._ensure_client()
        return await client.delete(url, timeout=timeout)

    async def patch(
        self,
        url: str,
        timeout: int = 5,
        data: dict[str, t.Any] | None = None,
        json: dict[str, t.Any] | None = None,
    ) -> NiquestsResponse:
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
    ) -> NiquestsResponse:
        """HEAD request with universal caching."""
        full_url = url

        # Check cache
        cached = await self._http_cache.get_cached_response(
            method="HEAD",
            url=full_url,
            headers=headers or {},
        )

        if cached:
            response = NiquestsResponse()
            response.status_code = cached["status"]
            response.headers.update(cached["headers"])
            response._content = b""  # HEAD responses have no body
            return response

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

    async def options(self, url: str, timeout: int = 5) -> NiquestsResponse:
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
    ) -> NiquestsResponse:
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
            "Niquests adapter initialized with universal HTTP caching "
            "(RFC 9111 compliant - 80%)",
        )


depends.set(Requests, "niquests")
