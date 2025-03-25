import typing as t
from functools import cached_property

from pydantic import SecretStr
from acb.depends import depends

from ._base import RequestsBase, RequestsBaseSettings


class RequestsSettings(RequestsBaseSettings):
    base_url: str = ""
    timeout: int = 10
    auth: t.Optional[tuple[str, SecretStr]] = None


class Requests(RequestsBase):
    @cached_property
    def client(self) -> "niquests.AsyncSession":  # type: ignore
        session = niquests.AsyncSession()  # type: ignore
        if self.config.requests.base_url:
            session.base_url = self.config.requests.base_url
        return session

    async def get(
        self,
        url: str,
        timeout: int = 10,
        params: t.Optional[dict[str, t.Any]] = None,
        headers: t.Optional[dict[str, str]] = None,
        cookies: t.Optional[dict[str, str]] = None,
    ) -> t.Any:
        response = await self.client.get(
            url, timeout=timeout, params=params, headers=headers, cookies=cookies
        )
        response.raise_for_status()
        return response

    async def post(
        self,
        url: str,
        data: t.Optional[dict[str, t.Any]] = None,
        timeout: int = 10,
        json: t.Optional[dict[str, t.Any]] = None,
    ) -> t.Any:
        response = await self.client.post(url, data=data, json=json, timeout=timeout)
        response.raise_for_status()
        return response

    async def put(
        self,
        url: str,
        data: t.Optional[dict[str, t.Any]] = None,
        timeout: int = 10,
        json: t.Optional[dict[str, t.Any]] = None,
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
        data: t.Optional[dict[str, t.Any]] = None,
        json: t.Optional[dict[str, t.Any]] = None,
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
        data: t.Optional[dict[str, t.Any]] = None,
        json: t.Optional[dict[str, t.Any]] = None,
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
