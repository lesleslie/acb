"""Tests for the HTTPX requests adapter."""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from acb.adapters.requests.httpx import Requests, RequestsSettings


class TestRequestsSettings:
    """Test HTTPX requests settings."""

    def test_default_settings(self) -> None:
        """Test settings initialization with default values."""
        settings = RequestsSettings()

        assert settings.cache_ttl == 7200
        assert settings.base_url == ""
        assert settings.timeout == 10
        assert settings.max_connections == 100
        assert settings.max_keepalive_connections == 20
        assert settings.keepalive_expiry == 5.0


class TestRequests:
    """Test HTTPX requests adapter."""

    @pytest.fixture
    def mock_cache(self) -> AsyncMock:
        """Create a mock cache adapter."""
        cache = AsyncMock()
        cache.get = AsyncMock(return_value=None)
        cache.set = AsyncMock()
        cache.delete = AsyncMock()
        return cache

    @pytest.fixture
    def mock_config(self) -> MagicMock:
        """Create a mock config."""
        mock_config = MagicMock()
        mock_config.requests = MagicMock()
        mock_config.requests.cache_ttl = 7200
        mock_config.requests.timeout = 10
        mock_config.requests.max_connections = 100
        mock_config.requests.max_keepalive_connections = 20
        mock_config.requests.keepalive_expiry = 5.0
        mock_config.requests.base_url = None
        mock_config.requests.auth = None
        return mock_config

    @pytest.fixture
    def requests_adapter(
        self, mock_cache: AsyncMock, mock_config: MagicMock
    ) -> Requests:
        """Create a requests adapter instance."""
        import asyncio

        with patch("acb.adapters.requests.httpx.depends"):
            adapter = Requests.__new__(Requests)
            adapter.cache = mock_cache
            adapter.config = mock_config
            adapter._http_client = None
            adapter._http_cache = MagicMock()
            # CleanupMixin attributes
            adapter._resources = []
            adapter._cleaned_up = False
            adapter._cleanup_lock = asyncio.Lock()
            # Config base class attributes
            adapter._client = None
            adapter._resource_cache = {}
            adapter._initialization_args = {}
            return adapter

    @pytest.mark.asyncio
    async def test_ensure_client_creates_client(
        self, requests_adapter: Requests
    ) -> None:
        """Test that _ensure_client creates HTTPX client."""
        mock_client = AsyncMock()

        with patch.object(
            requests_adapter, "_create_client", return_value=mock_client
        ) as mock_create:
            client = await requests_adapter._ensure_client()

            assert client == mock_client
            assert requests_adapter._http_client == mock_client
            mock_create.assert_called_once()

    @pytest.mark.asyncio
    async def test_ensure_client_returns_cached(
        self, requests_adapter: Requests
    ) -> None:
        """Test that _ensure_client returns cached client."""
        mock_client = AsyncMock()
        requests_adapter._http_client = mock_client

        client = await requests_adapter._ensure_client()

        assert client == mock_client

    @pytest.mark.asyncio
    async def test_get_with_cache_hit(self, requests_adapter: Requests) -> None:
        """Test GET method with cache hit."""
        cached_response = {
            "status": 200,
            "headers": {"content-type": "application/json"},
            "content": b'{"result": "cached"}',
        }
        requests_adapter._http_cache.get_cached_response = AsyncMock(
            return_value=cached_response
        )

        response = await requests_adapter.get("https://example.com")

        assert response.status_code == 200
        assert response.content == b'{"result": "cached"}'
        requests_adapter._http_cache.get_cached_response.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_with_cache_miss(self, requests_adapter: Requests) -> None:
        """Test GET method with cache miss."""
        requests_adapter._http_cache.get_cached_response = AsyncMock(return_value=None)
        requests_adapter._http_cache.store_response = AsyncMock()

        mock_client = AsyncMock()
        mock_response = httpx.Response(
            200,
            headers={"cache-control": "max-age=300"},
            content=b'{"result": "fresh"}',
        )
        mock_client.get = AsyncMock(return_value=mock_response)

        with patch.object(requests_adapter, "_ensure_client", return_value=mock_client):
            response = await requests_adapter.get("https://example.com")

            assert response.status_code == 200
            assert response.content == b'{"result": "fresh"}'
            requests_adapter._http_cache.get_cached_response.assert_called_once()
            requests_adapter._http_cache.store_response.assert_called_once()

    @pytest.mark.asyncio
    async def test_post_method(self, requests_adapter: Requests) -> None:
        """Test POST method."""
        mock_client = AsyncMock()
        mock_response = httpx.Response(201, content=b'{"created": true}')
        mock_client.post = AsyncMock(return_value=mock_response)

        requests_adapter._http_cache.store_response = AsyncMock()

        with patch.object(requests_adapter, "_ensure_client", return_value=mock_client):
            response = await requests_adapter.post(
                "https://example.com", json={"key": "value"}
            )

            assert response.status_code == 201
            mock_client.post.assert_called_once()

    @pytest.mark.asyncio
    async def test_put_method(self, requests_adapter: Requests) -> None:
        """Test PUT method."""
        mock_client = AsyncMock()
        mock_response = httpx.Response(200, content=b'{"updated": true}')
        mock_client.put = AsyncMock(return_value=mock_response)

        with patch.object(requests_adapter, "_ensure_client", return_value=mock_client):
            response = await requests_adapter.put(
                "https://example.com", json={"key": "value"}
            )

            assert response.status_code == 200
            mock_client.put.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_method(self, requests_adapter: Requests) -> None:
        """Test DELETE method."""
        mock_client = AsyncMock()
        mock_response = httpx.Response(204)
        mock_client.delete = AsyncMock(return_value=mock_response)

        with patch.object(requests_adapter, "_ensure_client", return_value=mock_client):
            response = await requests_adapter.delete("https://example.com")

            assert response.status_code == 204
            mock_client.delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_patch_method(self, requests_adapter: Requests) -> None:
        """Test PATCH method."""
        mock_client = AsyncMock()
        mock_response = httpx.Response(200, content=b'{"patched": true}')
        mock_client.patch = AsyncMock(return_value=mock_response)

        with patch.object(requests_adapter, "_ensure_client", return_value=mock_client):
            response = await requests_adapter.patch(
                "https://example.com", json={"key": "value"}
            )

            assert response.status_code == 200
            mock_client.patch.assert_called_once()

    @pytest.mark.asyncio
    async def test_head_method(self, requests_adapter: Requests) -> None:
        """Test HEAD method."""
        mock_client = AsyncMock()
        mock_response = httpx.Response(200)
        mock_client.head = AsyncMock(return_value=mock_response)

        requests_adapter._http_cache.get_cached_response = AsyncMock(return_value=None)
        requests_adapter._http_cache.store_response = AsyncMock()

        with patch.object(requests_adapter, "_ensure_client", return_value=mock_client):
            response = await requests_adapter.head("https://example.com")

            assert response.status_code == 200
            mock_client.head.assert_called_once()

    @pytest.mark.asyncio
    async def test_options_method(self, requests_adapter: Requests) -> None:
        """Test OPTIONS method."""
        mock_client = AsyncMock()
        mock_response = httpx.Response(200)
        mock_client.options = AsyncMock(return_value=mock_response)

        with patch.object(requests_adapter, "_ensure_client", return_value=mock_client):
            response = await requests_adapter.options("https://example.com")

            assert response.status_code == 200
            mock_client.options.assert_called_once()

    @pytest.mark.asyncio
    async def test_async_context_manager(self, requests_adapter: Requests) -> None:
        """Test async context manager support."""
        mock_client = AsyncMock()

        with patch.object(
            requests_adapter, "_ensure_client", new=AsyncMock(return_value=mock_client)
        ):
            async with requests_adapter as adapter:
                assert adapter == requests_adapter
                # The mock client will be set after _ensure_client is called
                assert (
                    requests_adapter._http_client is not None
                    or requests_adapter._ensure_client.called
                )

    @pytest.mark.asyncio
    async def test_cleanup(self, requests_adapter: Requests) -> None:
        """Test cleanup method closes HTTP client."""
        mock_client = AsyncMock()
        requests_adapter._http_client = mock_client

        await requests_adapter.cleanup()

        mock_client.aclose.assert_called_once()
        assert requests_adapter._http_client is None
