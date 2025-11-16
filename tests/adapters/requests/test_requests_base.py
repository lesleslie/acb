"""Tests for the base Requests adapter."""

from unittest.mock import AsyncMock

import pytest
import typing as t

from acb.adapters.requests._base import RequestsBase, RequestsBaseSettings


class TestRequestsBaseSettings:
    def test_default_values(self) -> None:
        settings = RequestsBaseSettings()
        assert settings.cache_ttl == 7200


class MockRequestsBase(RequestsBase):
    def __init__(self) -> None:
        self._initialized = False
        self._get = AsyncMock()
        self._post = AsyncMock()
        self._put = AsyncMock()
        self._delete = AsyncMock()

    async def init(self) -> None:
        self._initialized = True

    async def get(self, url: str, timeout: int = 30) -> t.Any:
        return await self._get(url, timeout)

    async def post(self, url: str, data: dict[str, t.Any], timeout: int = 30) -> t.Any:
        return await self._post(url, data, timeout)

    async def put(self, url: str, data: dict[str, t.Any], timeout: int = 30) -> t.Any:
        return await self._put(url, data, timeout)

    async def delete(self, url: str, timeout: int = 30) -> t.Any:
        return await self._delete(url, timeout)


@pytest.fixture
async def requests_base() -> MockRequestsBase:
    base = MockRequestsBase()
    await base.init()
    return base


@pytest.mark.asyncio
async def test_requests_base_init(requests_base: MockRequestsBase) -> None:
    assert requests_base._initialized


@pytest.mark.asyncio
async def test_get_method(requests_base: MockRequestsBase) -> None:
    requests_base._get.return_value = {"status": "ok"}
    result = await requests_base.get("https://example.com", 10)

    requests_base._get.assert_called_once_with("https://example.com", 10)
    assert result == {"status": "ok"}


@pytest.mark.asyncio
async def test_post_method(requests_base: MockRequestsBase) -> None:
    requests_base._post.return_value = {"status": "created"}
    data = {"key": "value"}
    result = await requests_base.post("https://example.com", data, 10)

    requests_base._post.assert_called_once_with("https://example.com", data, 10)
    assert result == {"status": "created"}


@pytest.mark.asyncio
async def test_put_method(requests_base: MockRequestsBase) -> None:
    requests_base._put.return_value = {"status": "updated"}
    data = {"key": "value"}
    result = await requests_base.put("https://example.com", data, 10)

    requests_base._put.assert_called_once_with("https://example.com", data, 10)
    assert result == {"status": "updated"}


@pytest.mark.asyncio
async def test_delete_method(requests_base: MockRequestsBase) -> None:
    requests_base._delete.return_value = {"status": "deleted"}
    result = await requests_base.delete("https://example.com", 10)

    requests_base._delete.assert_called_once_with("https://example.com", 10)
    assert result == {"status": "deleted"}
