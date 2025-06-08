import typing as t
from functools import cached_property

import niquests
from pydantic import SecretStr
from acb.depends import depends

from ._base import RequestsBase, RequestsBaseSettings


class RequestsSettings(RequestsBaseSettings):
    base_url: str = ""
    timeout: int = 10
    auth: tuple[str, SecretStr] | None = None


class Requests(RequestsBase):
    @cached_property
    def client(self) -> "niquests.AsyncSession":
        session = niquests.AsyncSession()
        if self.config.requests.base_url:
            session.base_url = self.config.requests.base_url
        return session

    async def get(
        self,
        url: str,
        timeout: int = 10,
        params: dict[str, t.Any] | None = None,
        headers: dict[str, str] | None = None,
        cookies: dict[str, str] | None = None,
    ) -> t.Any:
        response = await self.client.get(
            url, timeout=timeout, params=params, headers=headers, cookies=cookies
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
        response = await self.client.post(url, data=data, json=json, timeout=timeout)
        response.raise_for_status()
        return response

    async def put(
        self,
        url: str,
        data: dict[str, t.Any] | None = None,
        timeout: int = 10,
        json: dict[str, t.Any] | None = None,
    ) -> t.Any:
        response = await self.client.put(url, data=data, json=json, timeout=timeout)
        response.raise_for_status()
        return response

    async def delete(self, url: str, timeout: int = 10) -> t.Any:
        response = await self.client.delete(url, timeout=timeout)
        response.raise_for_status()
        return response

    async def patch(
        self,
        url: str,
        timeout: int = 10,
        data: dict[str, t.Any] | None = None,
        json: dict[str, t.Any] | None = None,
    ) -> t.Any:
        response = await self.client.patch(url, timeout=timeout, data=data, json=json)
        response.raise_for_status()
        return response

    async def head(self, url: str, timeout: int = 10) -> t.Any:
        response = await self.client.head(url, timeout=timeout)
        response.raise_for_status()
        return response

    async def options(self, url: str, timeout: int = 10) -> t.Any:
        response = await self.client.options(url, timeout=timeout)
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
        response = await self.client.request(
            method, url, data=data, json=json, timeout=timeout
        )
        response.raise_for_status()
        return response

    async def close(self) -> None:
        await self.client.close()

    async def init(self) -> None:
        self.logger.debug("Niquests adapter initialized")


depends.set(Requests)
