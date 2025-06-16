"""Tests for the HTTPX Requests adapter."""

from collections.abc import AsyncGenerator
from types import TracebackType
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import Response
from pytest_benchmark.fixture import BenchmarkFixture
from acb.adapters.requests.httpx import Requests, RequestsSettings


class MockResponse(Response):
    def __init__(
        self, status_code: int = 200, content: bytes = b"", **kwargs: Any
    ) -> None:
        super().__init__(status_code, content=content, **kwargs)


class MockAsyncRedis:
    def __init__(self, **kwargs: Any) -> None:
        self.kwargs = kwargs
        self.get = AsyncMock()
        self.set = AsyncMock()
        self.delete = AsyncMock()


class MockAsyncCacheClient:
    def __init__(self, **kwargs: Any) -> None:
        self.kwargs = kwargs
        self._get = AsyncMock(return_value=Response(status_code=200))
        self._post = AsyncMock(return_value=Response(status_code=200))
        self._put = AsyncMock(return_value=Response(status_code=200))
        self._delete = AsyncMock(return_value=Response(status_code=200))
        self._patch = AsyncMock(return_value=Response(status_code=200))
        self._head = AsyncMock(return_value=Response(status_code=200))
        self._options = AsyncMock(return_value=Response(status_code=200))
        self._request = AsyncMock(return_value=Response(status_code=200))

    async def __aenter__(self) -> "MockAsyncCacheClient":
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        pass

    async def get(self, *args: Any, **kwargs: Any) -> Response:
        return await self._get(*args, **kwargs)

    async def post(self, *args: Any, **kwargs: Any) -> Response:
        return await self._post(*args, **kwargs)

    async def put(self, *args: Any, **kwargs: Any) -> Response:
        return await self._put(*args, **kwargs)

    async def delete(self, *args: Any, **kwargs: Any) -> Response:
        return await self._delete(*args, **kwargs)

    async def patch(self, *args: Any, **kwargs: Any) -> Response:
        return await self._patch(*args, **kwargs)

    async def head(self, *args: Any, **kwargs: Any) -> Response:
        return await self._head(*args, **kwargs)

    async def options(self, *args: Any, **kwargs: Any) -> Response:
        return await self._options(*args, **kwargs)

    async def request(self, *args: Any, **kwargs: Any) -> Response:
        return await self._request(*args, **kwargs)


@pytest.fixture
def mock_cache_client() -> MockAsyncCacheClient:
    return MockAsyncCacheClient()


@pytest.fixture
def mock_redis() -> MockAsyncRedis:
    return MockAsyncRedis(host="localhost", port=6379)


@pytest.fixture
async def requests_adapter() -> AsyncGenerator[Requests]:
    with (
        patch("acb.adapters.requests.httpx.AsyncRedis") as mock_redis_cls,
        patch("acb.adapters.requests.httpx.AsyncRedisStorage") as mock_storage_cls,
        patch("acb.adapters.requests.httpx.Controller") as mock_controller_cls,
        patch("acb.adapters.requests.httpx.AsyncCacheClient") as mock_client_cls,
    ):
        mock_redis_instance = MockAsyncRedis()
        mock_redis_cls.return_value = mock_redis_instance

        mock_storage = MagicMock()
        mock_storage_cls.return_value = mock_storage

        mock_controller = MagicMock()
        mock_controller_cls.return_value = mock_controller

        mock_client = MockAsyncCacheClient()
        mock_client_cls.return_value = mock_client

        test_response = MockResponse()

        mock_client._get.return_value = test_response
        mock_client._post.return_value = test_response
        mock_client._put.return_value = test_response
        mock_client._delete.return_value = test_response
        mock_client._patch.return_value = test_response
        mock_client._head.return_value = test_response
        mock_client._options.return_value = test_response
        mock_client._request.return_value = test_response

        adapter = Requests()

        adapter.storage = mock_storage
        adapter.controller = mock_controller

        adapter.logger = MagicMock()

        mock_config = MagicMock()
        mock_config.app.name = "test_app"
        mock_config.cache.host.get_secret_value.return_value = "localhost"
        mock_config.cache.port = 6379
        mock_config.requests.cache_ttl = 7200
        adapter.config = mock_config

        await adapter.init()

        adapter.client = mock_client

        yield adapter


@pytest.mark.asyncio
async def test_requests_settings() -> None:
    settings = RequestsSettings()
    assert settings.base_url == ""
    assert settings.timeout == 10
    assert settings.auth is None
    assert settings.cache_ttl == 7200


@pytest.mark.asyncio
async def test_cache_key() -> None:
    with (
        patch("acb.adapters.requests.httpx.Request") as mock_request,
        patch("acb.adapters.requests.httpx.generate_key") as mock_generate,
    ):
        mock_generate.return_value = "test_key"
        adapter = Requests()
        adapter.config = MagicMock()
        adapter.config.app.name = "test_app"

        result = adapter.cache_key(mock_request, b"test_body")

        assert result == "test_app:httpx:test_key"
        mock_generate.assert_called_once_with(mock_request, b"test_body")


@pytest.mark.asyncio
async def test_get_method(requests_adapter: Requests) -> None:
    with patch("acb.adapters.requests.httpx.AsyncCacheClient") as mock_client_cls:
        mock_client = MockAsyncCacheClient()
        mock_client_cls.return_value = mock_client
        test_response = MockResponse()
        mock_client._get.return_value = test_response

        # Clear the client cache to ensure fresh client creation
        requests_adapter._client_cache.clear()

        response = await requests_adapter.get("https://example.com", timeout=10)

        mock_client_cls.assert_called_once()
        assert mock_client_cls.call_args[1]["storage"] == requests_adapter.storage
        assert mock_client_cls.call_args[1]["controller"] == requests_adapter.controller

        assert isinstance(response, Response)
        assert response.status_code == 200


@pytest.mark.asyncio
async def test_post_method(requests_adapter: Requests) -> None:
    with patch("acb.adapters.requests.httpx.AsyncCacheClient") as mock_client_cls:
        mock_client = MockAsyncCacheClient()
        mock_client_cls.return_value = mock_client
        test_response = MockResponse()
        mock_client._post.return_value = test_response

        # Clear the client cache to ensure fresh client creation
        requests_adapter._client_cache.clear()

        response = await requests_adapter.post(
            "https://example.com", data={"key": "value"}, timeout=10
        )

        mock_client_cls.assert_called_once()
        mock_client._post.assert_called_once()
        assert response.status_code == 200


@pytest.mark.asyncio
async def test_put_method(requests_adapter: Requests) -> None:
    with patch("acb.adapters.requests.httpx.AsyncCacheClient") as mock_client_cls:
        mock_client = MockAsyncCacheClient()
        mock_client_cls.return_value = mock_client
        test_response = MockResponse()
        mock_client._put.return_value = test_response

        # Clear the client cache to ensure fresh client creation
        requests_adapter._client_cache.clear()

        response = await requests_adapter.put(
            "https://example.com", data={"key": "value"}, timeout=10
        )

        mock_client_cls.assert_called_once()
        mock_client._put.assert_called_once()
        assert response.status_code == 200


@pytest.mark.asyncio
async def test_delete_method(requests_adapter: Requests) -> None:
    with patch("acb.adapters.requests.httpx.AsyncCacheClient") as mock_client_cls:
        mock_client = MockAsyncCacheClient()
        mock_client_cls.return_value = mock_client
        test_response = MockResponse()
        mock_client._delete.return_value = test_response

        # Clear the client cache to ensure fresh client creation
        requests_adapter._client_cache.clear()

        response = await requests_adapter.delete("https://example.com", timeout=10)

        mock_client_cls.assert_called_once()
        mock_client._delete.assert_called_once()
        assert response.status_code == 200


@pytest.mark.asyncio
async def test_patch_method(requests_adapter: Requests) -> None:
    with patch("acb.adapters.requests.httpx.AsyncCacheClient") as mock_client_cls:
        mock_client = MockAsyncCacheClient()
        mock_client_cls.return_value = mock_client
        test_response = MockResponse()
        mock_client._patch.return_value = test_response

        # Clear the client cache to ensure fresh client creation
        requests_adapter._client_cache.clear()

        response = await requests_adapter.patch(
            "https://example.com", data={"key": "value"}, timeout=10
        )

        mock_client_cls.assert_called_once()
        mock_client._patch.assert_called_once()
        assert response.status_code == 200


@pytest.mark.asyncio
async def test_head_method(requests_adapter: Requests) -> None:
    with patch("acb.adapters.requests.httpx.AsyncCacheClient") as mock_client_cls:
        mock_client = MockAsyncCacheClient()
        mock_client_cls.return_value = mock_client
        test_response = MockResponse()
        mock_client._head.return_value = test_response

        # Clear the client cache to ensure fresh client creation
        requests_adapter._client_cache.clear()

        response = await requests_adapter.head("https://example.com", timeout=10)

        mock_client_cls.assert_called_once()
        mock_client._head.assert_called_once()
        assert response.status_code == 200


@pytest.mark.asyncio
async def test_options_method(requests_adapter: Requests) -> None:
    with patch("acb.adapters.requests.httpx.AsyncCacheClient") as mock_client_cls:
        mock_client = MockAsyncCacheClient()
        mock_client_cls.return_value = mock_client
        test_response = MockResponse()
        mock_client._options.return_value = test_response

        # Clear the client cache to ensure fresh client creation
        requests_adapter._client_cache.clear()

        response = await requests_adapter.options("https://example.com", timeout=10)

        mock_client_cls.assert_called_once()
        mock_client._options.assert_called_once()
        assert response.status_code == 200


@pytest.mark.asyncio
async def test_request_method(requests_adapter: Requests) -> None:
    with patch("acb.adapters.requests.httpx.AsyncCacheClient") as mock_client_cls:
        mock_client = MockAsyncCacheClient()
        mock_client_cls.return_value = mock_client
        test_response = MockResponse()
        mock_client._request.return_value = test_response

        # Clear the client cache to ensure fresh client creation
        requests_adapter._client_cache.clear()

        response = await requests_adapter.request(
            "GET", "https://example.com", timeout=10
        )

        mock_client_cls.assert_called_once()
        assert mock_client_cls.call_args[1]["storage"] == requests_adapter.storage
        assert mock_client_cls.call_args[1]["controller"] == requests_adapter.controller

        assert isinstance(response, Response)
        assert response.status_code == 200


class TestHttpxRequestsBenchmarks:
    @pytest.fixture
    async def benchmark_adapter(self) -> AsyncGenerator[Requests]:
        with (
            patch("acb.adapters.requests.httpx.AsyncRedis") as mock_redis_cls,
            patch("acb.adapters.requests.httpx.AsyncRedisStorage") as mock_storage_cls,
            patch("acb.adapters.requests.httpx.Controller") as mock_controller_cls,
            patch("acb.adapters.requests.httpx.AsyncCacheClient") as mock_client_cls,
        ):
            mock_redis_instance = MockAsyncRedis()
            mock_redis_cls.return_value = mock_redis_instance

            mock_storage = MagicMock()
            mock_storage_cls.return_value = mock_storage

            mock_controller = MagicMock()
            mock_controller_cls.return_value = mock_controller

            mock_client = MockAsyncCacheClient()
            mock_client_cls.return_value = mock_client

            test_response = MockResponse()
            mock_client._get.return_value = test_response
            mock_client._post.return_value = test_response

            adapter = Requests()
            adapter.storage = mock_storage
            adapter.controller = mock_controller
            adapter.logger = MagicMock()

            mock_config = MagicMock()
            mock_config.app.name = "test_app"
            mock_config.cache.host.get_secret_value.return_value = "localhost"
            mock_config.cache.port = 6379
            mock_config.requests.cache_ttl = 7200
            adapter.config = mock_config

            await adapter.init()
            adapter.client = mock_client

            yield adapter

    @pytest.fixture
    def small_payload(self) -> dict[str, Any]:
        return {"data": "small_test_data"}

    @pytest.fixture
    def medium_payload(self) -> dict[str, Any]:
        return {"data": "medium_test_data" * 100}

    @pytest.fixture
    def large_payload(self) -> dict[str, Any]:
        return {"data": "large_test_data" * 10000}

    @pytest.mark.benchmark
    @pytest.mark.asyncio
    async def test_get_request_performance(
        self, benchmark: BenchmarkFixture, benchmark_adapter: Requests
    ) -> None:
        async def get_request():
            return await benchmark_adapter.get("https://example.com", timeout=10)

        response = await benchmark(get_request)
        assert response.status_code == 200

    @pytest.mark.benchmark
    @pytest.mark.asyncio
    async def test_post_small_payload_performance(
        self,
        benchmark: BenchmarkFixture,
        benchmark_adapter: Requests,
        small_payload: dict[str, Any],
    ) -> None:
        async def post_request():
            return await benchmark_adapter.post(
                "https://example.com", json=small_payload, timeout=10
            )

        response = await benchmark(post_request)
        assert response.status_code == 200

    @pytest.mark.benchmark
    @pytest.mark.asyncio
    async def test_post_medium_payload_performance(
        self,
        benchmark: BenchmarkFixture,
        benchmark_adapter: Requests,
        medium_payload: dict[str, Any],
    ) -> None:
        async def post_request():
            return await benchmark_adapter.post(
                "https://example.com", json=medium_payload, timeout=10
            )

        response = await benchmark(post_request)
        assert response.status_code == 200

    @pytest.mark.benchmark
    @pytest.mark.asyncio
    async def test_post_large_payload_performance(
        self,
        benchmark: BenchmarkFixture,
        benchmark_adapter: Requests,
        large_payload: dict[str, Any],
    ) -> None:
        async def post_request():
            return await benchmark_adapter.post(
                "https://example.com", json=large_payload, timeout=10
            )

        response = await benchmark(post_request)
        assert response.status_code == 200

    @pytest.mark.benchmark
    @pytest.mark.asyncio
    async def test_multiple_requests_performance(
        self, benchmark: BenchmarkFixture, benchmark_adapter: Requests
    ) -> None:
        async def multiple_requests() -> list[Response]:
            responses: list[Response] = []
            for i in range(10):
                response = await benchmark_adapter.get(
                    f"https://example.com/endpoint_{i}", timeout=10
                )
                responses.append(response)
            return responses

        responses = await benchmark(multiple_requests)
        assert len(responses) == 10
        assert all(r.status_code == 200 for r in responses)

    @pytest.mark.benchmark
    @pytest.mark.asyncio
    async def test_mixed_requests_performance(
        self,
        benchmark: BenchmarkFixture,
        benchmark_adapter: Requests,
        small_payload: dict[str, Any],
    ) -> None:
        async def mixed_requests():
            get_response = await benchmark_adapter.get(
                "https://example.com", timeout=10
            )
            post_response = await benchmark_adapter.post(
                "https://example.com", json=small_payload, timeout=10
            )
            put_response = await benchmark_adapter.put(
                "https://example.com", json=small_payload, timeout=10
            )
            delete_response = await benchmark_adapter.delete(
                "https://example.com", timeout=10
            )
            return [get_response, post_response, put_response, delete_response]

        responses = await benchmark(mixed_requests)
        assert len(responses) == 4
        assert all(r.status_code == 200 for r in responses)
