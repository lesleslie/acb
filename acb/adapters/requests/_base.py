"""Base classes for ACB requests adapters.

This module provides the foundational classes for HTTP client adapters,
including settings configuration and protocol definitions.
"""

import typing as t

from acb.config import AdapterBase, Settings


class RequestsBaseSettings(Settings):
    """Base settings for all requests adapters."""

    cache_ttl: int = 7200
    max_connections: int = 100
    max_keepalive_connections: int = 20
    keepalive_expiry: float = 5.0
    base_url: str = ""
    timeout: int = 10
    auth: tuple[str, str] | None = None


class RequestsProtocol(t.Protocol):
    """Protocol defining the interface for HTTP requests adapters."""

    async def get(self, url: str, timeout: int) -> t.Any: ...

    async def post(self, url: str, data: dict[str, t.Any], timeout: int) -> t.Any: ...

    async def put(self, url: str, data: dict[str, t.Any], timeout: int) -> t.Any: ...

    async def delete(self, url: str, timeout: int) -> t.Any: ...


class RequestsBase(AdapterBase):
    """Base class for all requests adapters."""
