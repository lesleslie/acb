from uuid import UUID

import typing as t

try:
    import niquests
except Exception:  # pragma: no cover - allow tests without niquests installed
    import os as _os
    import sys as _sys

    if "pytest" in _sys.modules or _os.getenv("TESTING", "False").lower() == "true":
        from unittest.mock import MagicMock

        niquests = MagicMock()  # type: ignore[assignment]
    else:
        raise
from pydantic import SecretStr

from acb.adapters import AdapterCapability, AdapterMetadata, AdapterStatus
from acb.depends import depends

from ._base import RequestsBase, RequestsBaseSettings

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
    ],
    required_packages=["niquests"],
    description="Niquests-based HTTP client with async session support",
    settings_class="RequestsSettings",
    config_example={
        "base_url": "https://api.example.com",
        "timeout": 10,
        "auth": ("username", "password"),  # pragma: allowlist secret
    },
)


class RequestsSettings(RequestsBaseSettings):
    base_url: str = ""
    timeout: int = 10
    auth: tuple[str, SecretStr] | None = None


class Requests(RequestsBase):
    def __init__(self, **kwargs: t.Any) -> None:
        super().__init__()

    async def _create_client(self) -> "niquests.AsyncSession":
        session = niquests.AsyncSession()
        if self.config.requests.base_url:
            session.base_url = self.config.requests.base_url
        return session

    async def get_client(self) -> "niquests.AsyncSession":
        return await self._ensure_client()  # type: ignore  # type: ignore[no-any-return]

    @property
    def client(self) -> "niquests.AsyncSession":
        if self._client is None:
            msg = "Client not initialized. Call get_client() first."
            raise RuntimeError(msg)
        return self._client

    async def get(
        self,
        url: str,
        timeout: int = 10,
        params: dict[str, t.Any] | None = None,
        headers: dict[str, str] | None = None,
        cookies: dict[str, str] | None = None,
    ) -> t.Any:
        client = await self.get_client()
        response = await client.get(
            url,
            timeout=timeout,
            params=params,
            headers=headers,
            cookies=cookies,
        )
        response.raise_for_status()
        return response

    async def post(
        self,
        url: str,
        data: dict[str, t.Any] | None = None,
        timeout: int = 10,
        json: dict[str, t.Any] | None = None,
    ) -> t.Any:
        client = await self.get_client()
        response = await client.post(url, data=data, json=json, timeout=timeout)
        response.raise_for_status()
        return response

    async def put(
        self,
        url: str,
        data: dict[str, t.Any] | None = None,
        timeout: int = 10,
        json: dict[str, t.Any] | None = None,
    ) -> t.Any:
        client = await self.get_client()
        response = await client.put(url, data=data, json=json, timeout=timeout)
        response.raise_for_status()
        return response

    async def delete(self, url: str, timeout: int = 10) -> t.Any:
        client = await self.get_client()
        response = await client.delete(url, timeout=timeout)
        response.raise_for_status()
        return response

    async def patch(
        self,
        url: str,
        timeout: int = 10,
        data: dict[str, t.Any] | None = None,
        json: dict[str, t.Any] | None = None,
    ) -> t.Any:
        client = await self.get_client()
        response = await client.patch(url, timeout=timeout, data=data, json=json)
        response.raise_for_status()
        return response

    async def head(self, url: str, timeout: int = 10) -> t.Any:
        client = await self.get_client()
        response = await client.head(url, timeout=timeout)
        response.raise_for_status()
        return response

    async def options(self, url: str, timeout: int = 10) -> t.Any:
        client = await self.get_client()
        response = await client.options(url, timeout=timeout)
        response.raise_for_status()
        return response

    async def request(
        self,
        method: str,
        url: str,
        data: dict[str, t.Any] | None = None,
        json: dict[str, t.Any] | None = None,
        timeout: int = 10,
    ) -> t.Any:
        client = await self.get_client()
        response = await client.request(
            method,
            url,
            data=data,
            json=json,
            timeout=timeout,
        )
        response.raise_for_status()
        return response

    async def close(self) -> None:
        if self._client is not None:
            await self._client.close()

    async def init(self) -> None:
        self.logger.debug("Niquests adapter initialized")


depends.set(Requests, "niquests")
