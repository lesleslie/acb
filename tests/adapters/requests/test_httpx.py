"""Tests for the HTTPX requests adapter."""

from unittest.mock import AsyncMock, MagicMock, patch

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
    def mock_config(self) -> MagicMock:
        """Create a mock config."""
        mock_config = MagicMock()
        mock_config.app.name = "test_app"
        mock_config.cache = MagicMock()
        mock_config.cache.host = MagicMock()
        mock_config.cache.host.get_secret_value.return_value = "localhost"
        mock_config.cache.port = 6379
        mock_config.requests = MagicMock()
        mock_config.requests.cache_ttl = 7200
        mock_config.requests.timeout = 10
        mock_config.requests.max_connections = 100
        mock_config.requests.max_keepalive_connections = 20
        mock_config.requests.keepalive_expiry = 5.0
        return mock_config

    @pytest.fixture
    def requests_adapter(self, mock_config: MagicMock) -> Requests:
        """Create a requests adapter instance."""
        adapter = Requests()
        adapter.config = mock_config
        adapter.logger = MagicMock()
        return adapter

    @pytest.mark.asyncio
    async def test_init(self, requests_adapter: Requests) -> None:
        """Test adapter initialization."""
        await requests_adapter.init()
        requests_adapter.logger.debug.assert_called_once_with(
            "HTTPX adapter initialized with lazy loading"
        )

    @pytest.mark.asyncio
    async def test_create_storage(self, requests_adapter: Requests) -> None:
        """Test storage creation."""
        with (
            patch("acb.adapters.requests.httpx.AsyncRedis") as mock_redis,
            patch("acb.adapters.requests.httpx.AsyncRedisStorage") as mock_storage,
        ):
            mock_redis_client = AsyncMock()
            mock_redis.return_value = mock_redis_client
            mock_storage_instance = AsyncMock()
            mock_storage.return_value = mock_storage_instance

            storage = await requests_adapter._create_storage()

            mock_redis.assert_called_once_with(host="localhost", port=6379)
            mock_storage.assert_called_once_with(client=mock_redis_client, ttl=7200)
            assert storage == mock_storage_instance

    @pytest.mark.asyncio
    async def test_create_controller(self, requests_adapter: Requests) -> None:
        """Test controller creation."""
        with patch("acb.adapters.requests.httpx.Controller") as mock_controller:
            mock_controller_instance = AsyncMock()
            mock_controller.return_value = mock_controller_instance

            controller = await requests_adapter._create_controller()

            mock_controller.assert_called_once()
            assert controller == mock_controller_instance

    def test_cache_key(self, requests_adapter: Requests) -> None:
        """Test cache key generation."""
        from httpcore import Request

        request = Request("GET", "https://example.com")
        body = b""

        key = requests_adapter.cache_key(request, body)

        assert key.startswith("test_app:httpx:")

    @pytest.mark.asyncio
    async def test_get_cached_client(self, requests_adapter: Requests) -> None:
        """Test cached client retrieval."""
        with (
            patch.object(
                requests_adapter, "get_storage", AsyncMock()
            ) as mock_get_storage,
            patch.object(
                requests_adapter, "get_controller", AsyncMock()
            ) as mock_get_controller,
            patch("acb.adapters.requests.httpx.AsyncCacheClient") as mock_client_class,
        ):
            mock_storage = AsyncMock()
            mock_controller = AsyncMock()
            mock_client = AsyncMock()

            mock_get_storage.return_value = mock_storage
            mock_get_controller.return_value = mock_controller
            mock_client_class.return_value = mock_client

            client = await requests_adapter._get_cached_client()

            mock_get_storage.assert_called_once()
            mock_get_controller.assert_called_once()
            mock_client_class.assert_called_once()
            assert client == mock_client
            assert "default" in requests_adapter._client_cache

    @pytest.mark.asyncio
    async def test_get_method(self, requests_adapter: Requests) -> None:
        """Test GET method."""
        mock_client = AsyncMock()
        mock_response = AsyncMock()
        mock_client.get.return_value = mock_response

        with patch.object(
            requests_adapter, "_get_cached_client", AsyncMock(return_value=mock_client)
        ):
            response = await requests_adapter.get("https://example.com", timeout=5)

            mock_client.get.assert_called_once_with(
                "https://example.com",
                timeout=5,
                params=None,
                headers=None,
                cookies=None,
            )
            assert response == mock_response

    @pytest.mark.asyncio
    async def test_post_method(self, requests_adapter: Requests) -> None:
        """Test POST method."""
        mock_client = AsyncMock()
        mock_response = AsyncMock()
        mock_client.post.return_value = mock_response

        with patch.object(
            requests_adapter, "_get_cached_client", AsyncMock(return_value=mock_client)
        ):
            response = await requests_adapter.post(
                "https://example.com", data={"key": "value"}
            )

            mock_client.post.assert_called_once_with(
                "https://example.com", data={"key": "value"}, json=None, timeout=5
            )
            assert response == mock_response

    @pytest.mark.asyncio
    async def test_put_method(self, requests_adapter: Requests) -> None:
        """Test PUT method."""
        mock_client = AsyncMock()
        mock_response = AsyncMock()
        mock_client.put.return_value = mock_response

        with patch.object(
            requests_adapter, "_get_cached_client", AsyncMock(return_value=mock_client)
        ):
            response = await requests_adapter.put(
                "https://example.com", data={"key": "value"}
            )

            mock_client.put.assert_called_once_with(
                "https://example.com", data={"key": "value"}, json=None, timeout=5
            )
            assert response == mock_response

    @pytest.mark.asyncio
    async def test_delete_method(self, requests_adapter: Requests) -> None:
        """Test DELETE method."""
        mock_client = AsyncMock()
        mock_response = AsyncMock()
        mock_client.delete.return_value = mock_response

        with patch.object(
            requests_adapter, "_get_cached_client", AsyncMock(return_value=mock_client)
        ):
            response = await requests_adapter.delete("https://example.com", timeout=5)

            mock_client.delete.assert_called_once_with("https://example.com", timeout=5)
            assert response == mock_response

    @pytest.mark.asyncio
    async def test_patch_method(self, requests_adapter: Requests) -> None:
        """Test PATCH method."""
        mock_client = AsyncMock()
        mock_response = AsyncMock()
        mock_client.patch.return_value = mock_response

        with patch.object(
            requests_adapter, "_get_cached_client", AsyncMock(return_value=mock_client)
        ):
            response = await requests_adapter.patch(
                "https://example.com", data={"key": "value"}
            )

            mock_client.patch.assert_called_once_with(
                "https://example.com", timeout=5, data={"key": "value"}, json=None
            )
            assert response == mock_response

    @pytest.mark.asyncio
    async def test_head_method(self, requests_adapter: Requests) -> None:
        """Test HEAD method."""
        mock_client = AsyncMock()
        mock_response = AsyncMock()
        mock_client.head.return_value = mock_response

        with patch.object(
            requests_adapter, "_get_cached_client", AsyncMock(return_value=mock_client)
        ):
            response = await requests_adapter.head("https://example.com", timeout=5)

            mock_client.head.assert_called_once_with("https://example.com", timeout=5)
            assert response == mock_response

    @pytest.mark.asyncio
    async def test_options_method(self, requests_adapter: Requests) -> None:
        """Test OPTIONS method."""
        mock_client = AsyncMock()
        mock_response = AsyncMock()
        mock_client.options.return_value = mock_response

        with patch.object(
            requests_adapter, "_get_cached_client", AsyncMock(return_value=mock_client)
        ):
            response = await requests_adapter.options("https://example.com", timeout=5)

            mock_client.options.assert_called_once_with(
                "https://example.com", timeout=5
            )
            assert response == mock_response

    @pytest.mark.asyncio
    async def test_request_method(self, requests_adapter: Requests) -> None:
        """Test generic request method."""
        mock_client = AsyncMock()
        mock_response = AsyncMock()
        mock_client.request.return_value = mock_response

        with patch.object(
            requests_adapter, "_get_cached_client", AsyncMock(return_value=mock_client)
        ):
            response = await requests_adapter.request(
                "PUT", "https://example.com", data={"key": "value"}
            )

            mock_client.request.assert_called_once_with(
                "PUT",
                "https://example.com",
                timeout=5,
                data={"key": "value"},
                json=None,
            )
            assert response == mock_response

    @pytest.mark.asyncio
    async def test_storage_property(self, requests_adapter: Requests) -> None:
        """Test storage property."""
        mock_storage = AsyncMock()
        requests_adapter._storage = mock_storage

        storage = requests_adapter.storage

        assert storage == mock_storage

    @pytest.mark.asyncio
    async def test_storage_property_setter(self, requests_adapter: Requests) -> None:
        """Test storage property setter."""
        mock_storage = AsyncMock()

        requests_adapter.storage = mock_storage

        assert requests_adapter._storage == mock_storage

    @pytest.mark.asyncio
    async def test_controller_property(self, requests_adapter: Requests) -> None:
        """Test controller property."""
        mock_controller = AsyncMock()
        requests_adapter._controller = mock_controller

        controller = requests_adapter.controller

        assert controller == mock_controller

    @pytest.mark.asyncio
    async def test_controller_property_setter(self, requests_adapter: Requests) -> None:
        """Test controller property setter."""
        mock_controller = AsyncMock()

        requests_adapter.controller = mock_controller

        assert requests_adapter._controller == mock_controller

    @pytest.mark.asyncio
    async def test_close(self, requests_adapter: Requests) -> None:
        """Test adapter close method."""
        mock_client1 = AsyncMock()
        mock_client2 = AsyncMock()
        requests_adapter._client_cache = {
            "client1": mock_client1,
            "client2": mock_client2,
        }

        await requests_adapter.close()

        mock_client1.aclose.assert_called_once()
        mock_client2.aclose.assert_called_once()
        assert len(requests_adapter._client_cache) == 0
