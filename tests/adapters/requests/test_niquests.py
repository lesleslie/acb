"""Tests for the niquests adapter."""

import typing as t
from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic import SecretStr
from acb.adapters.requests.niquests import Requests, RequestsSettings


class MockNiquestsResponse:
    def __init__(
        self, status_code: int = 200, data: t.Any = None, json_data: t.Any = None
    ) -> None:
        self.status_code = status_code
        self._data = data
        self._json = json_data

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise Exception(f"HTTP Error: {self.status_code}")

    async def data(self) -> t.Any:
        return self._data

    async def json(self) -> t.Any:
        return self._json


class MockNiquestsAsyncSession:
    def __init__(self) -> None:
        self.base_url = ""
        self.get = AsyncMock()
        self.post = AsyncMock()
        self.put = AsyncMock()
        self.delete = AsyncMock()
        self.patch = AsyncMock()
        self.head = AsyncMock()
        self.options = AsyncMock()
        self.request = AsyncMock()
        self.close = AsyncMock()

        self.get.return_value = MockNiquestsResponse()
        self.post.return_value = MockNiquestsResponse()
        self.put.return_value = MockNiquestsResponse()
        self.delete.return_value = MockNiquestsResponse()
        self.patch.return_value = MockNiquestsResponse()
        self.head.return_value = MockNiquestsResponse()
        self.options.return_value = MockNiquestsResponse()
        self.request.return_value = MockNiquestsResponse()


@pytest.fixture
def mock_session() -> MockNiquestsAsyncSession:
    return MockNiquestsAsyncSession()


@pytest.fixture
def requests_adapter(mock_session: MockNiquestsAsyncSession) -> Requests:
    mock_config = MagicMock()
    mock_config.requests = RequestsSettings(
        base_url="https://api.example.com",
        timeout=30,
        auth=("username", SecretStr("password")),
    )

    mock_logger = MagicMock()

    adapter = Requests()
    adapter.config = mock_config
    adapter.logger = mock_logger

    object.__setattr__(adapter, "_client", mock_session)

    adapter.__class__.client = property(
        lambda self: object.__getattribute__(self, "_client")
    )

    mock_session.base_url = "https://api.example.com"

    return adapter


class TestRequestsSettings:
    def test_default_values(self) -> None:
        settings = RequestsSettings()
        assert settings.base_url == ""
        assert settings.timeout == 10
        assert settings.auth is None
        assert settings.cache_ttl == 7200

    def test_custom_values(self) -> None:
        from pydantic import SecretStr

        settings = RequestsSettings(
            base_url="https://api.example.com",
            timeout=30,
            auth=("username", SecretStr("password")),
            cache_ttl=3600,
        )

        assert settings.base_url == "https://api.example.com"
        assert settings.timeout == 30
        assert settings.auth is not None
        assert settings.auth[0] == "username"
        assert settings.auth[1].get_secret_value() == "password"
        assert settings.cache_ttl == 3600

        settings_no_auth = RequestsSettings(
            base_url="https://api.example.com",
            timeout=30,
            auth=None,
            cache_ttl=3600,
        )

        assert settings_no_auth.auth is None


@pytest.mark.asyncio
async def test_init(requests_adapter: Requests) -> None:
    # Create mock logger
    mock_logger = MagicMock()
    requests_adapter.logger = mock_logger

    await requests_adapter.init()
    mock_logger.debug.assert_called_once_with("Niquests adapter initialized")


@pytest.mark.asyncio
async def test_client_property(mock_session: MockNiquestsAsyncSession) -> None:
    adapter = Requests()
    adapter.config = MagicMock()
    adapter.config.requests.base_url = "https://api.example.com"
    object.__setattr__(adapter, "_client", mock_session)
    adapter.__class__.client = property(
        lambda self: object.__getattribute__(self, "_client")
    )

    mock_session.base_url = adapter.config.requests.base_url

    assert adapter.client.base_url == "https://api.example.com"

    mock_response = MockNiquestsResponse()
    adapter.client.get.return_value = mock_response

    result = await adapter.get("/test")
    adapter.client.get.assert_called_once()
    assert result == mock_response


@pytest.mark.asyncio
async def test_get(requests_adapter: Requests) -> None:
    mock_response = MockNiquestsResponse(json_data={"key": "value"})
    requests_adapter.client.get.return_value = mock_response  # type: ignore[attr-defined]

    response = await requests_adapter.get(
        url="/test",
        timeout=5,
        params={"param": "value"},
        headers={"header": "value"},
        cookies={"cookie": "value"},
    )

    requests_adapter.client.get.assert_called_once_with(  # type: ignore[attr-defined]
        "/test",
        timeout=5,
        params={"param": "value"},
        headers={"header": "value"},
        cookies={"cookie": "value"},
    )

    assert response == mock_response


@pytest.mark.asyncio
async def test_post(requests_adapter: Requests) -> None:
    mock_response = MockNiquestsResponse(status_code=201)
    requests_adapter.client.post.return_value = mock_response  # type: ignore[attr-defined]

    response = await requests_adapter.post(
        url="/test", data={"key": "value"}, timeout=5
    )

    requests_adapter.client.post.assert_called_once_with(  # type: ignore[attr-defined]
        "/test", data={"key": "value"}, json=None, timeout=5
    )

    assert response == mock_response


@pytest.mark.asyncio
async def test_put(requests_adapter: Requests) -> None:
    mock_response = MockNiquestsResponse()
    requests_adapter.client.put.return_value = mock_response  # type: ignore[attr-defined]

    response = await requests_adapter.put(url="/test", json={"key": "value"}, timeout=5)

    requests_adapter.client.put.assert_called_once_with(  # type: ignore[attr-defined]
        "/test", data=None, json={"key": "value"}, timeout=5
    )

    assert response == mock_response


@pytest.mark.asyncio
async def test_delete(requests_adapter: Requests) -> None:
    mock_response = MockNiquestsResponse(status_code=204)
    requests_adapter.client.delete.return_value = mock_response  # type: ignore[attr-defined]

    response = await requests_adapter.delete(url="/test", timeout=5)

    requests_adapter.client.delete.assert_called_once_with("/test", timeout=5)  # type: ignore[attr-defined]

    assert response == mock_response


@pytest.mark.asyncio
async def test_patch(requests_adapter: Requests) -> None:
    mock_response = MockNiquestsResponse()
    requests_adapter.client.patch.return_value = mock_response  # type: ignore[attr-defined]

    response = await requests_adapter.patch(
        url="/test", json={"key": "value"}, timeout=5
    )

    requests_adapter.client.patch.assert_called_once_with(  # type: ignore[attr-defined]
        "/test", timeout=5, data=None, json={"key": "value"}
    )

    assert response == mock_response


@pytest.mark.asyncio
async def test_head(requests_adapter: Requests) -> None:
    mock_response = MockNiquestsResponse()
    requests_adapter.client.head.return_value = mock_response  # type: ignore[attr-defined]

    response = await requests_adapter.head(url="/test", timeout=5)

    requests_adapter.client.head.assert_called_once_with("/test", timeout=5)  # type: ignore[attr-defined]

    assert response == mock_response


@pytest.mark.asyncio
async def test_options(requests_adapter: Requests) -> None:
    mock_response = MockNiquestsResponse()
    requests_adapter.client.options.return_value = mock_response  # type: ignore[attr-defined]

    response = await requests_adapter.options(url="/test", timeout=5)

    requests_adapter.client.options.assert_called_once_with("/test", timeout=5)  # type: ignore[attr-defined]

    assert response == mock_response


@pytest.mark.asyncio
async def test_request(requests_adapter: Requests) -> None:
    mock_response = MockNiquestsResponse()
    requests_adapter.client.request.return_value = mock_response  # type: ignore[attr-defined]

    response = await requests_adapter.request(
        method="GET", url="/test", json={"key": "value"}, timeout=5
    )

    requests_adapter.client.request.assert_called_once_with(  # type: ignore[attr-defined]
        "GET", "/test", data=None, json={"key": "value"}, timeout=5
    )

    assert response == mock_response


@pytest.mark.asyncio
async def test_close(requests_adapter: Requests) -> None:
    await requests_adapter.close()
    requests_adapter.client.close.assert_called_once()  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_raise_for_status(requests_adapter: Requests) -> None:
    mock_response = MockNiquestsResponse(status_code=404)
    requests_adapter.client.get.return_value = mock_response  # type: ignore[attr-defined]

    with pytest.raises(Exception):
        await requests_adapter.get(url="/test")
