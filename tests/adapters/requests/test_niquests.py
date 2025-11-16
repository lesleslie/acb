"""Tests for the Niquests requests adapter."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from acb.adapters.requests.niquests import Requests, RequestsSettings


class TestRequestsSettings:
    """Test Niquests requests settings."""

    def test_default_settings(self) -> None:
        """Test settings initialization with default values."""
        settings = RequestsSettings()

        assert settings.cache_ttl == 7200
        assert settings.base_url == ""
        assert settings.timeout == 10
        assert settings.auth is None


class TestRequests:
    """Test Niquests requests adapter."""

    @pytest.fixture
    def mock_config(self) -> MagicMock:
        """Create a mock config."""
        mock_config = MagicMock()
        mock_config.requests = MagicMock()
        mock_config.requests.base_url = ""
        mock_config.requests.timeout = 10
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
            "Niquests adapter initialized"
        )

    @pytest.mark.asyncio
    async def test_create_client(self, requests_adapter: Requests) -> None:
        """Test client creation."""
        with patch(
            "acb.adapters.requests.niquests.niquests.AsyncSession"
        ) as mock_session:
            mock_client = AsyncMock()
            mock_session.return_value = mock_client

            client = await requests_adapter._create_client()

            mock_session.assert_called_once()
            assert client == mock_client

    @pytest.mark.asyncio
    async def test_get_client(self, requests_adapter: Requests) -> None:
        """Test client retrieval."""
        with patch.object(
            requests_adapter, "_ensure_client", AsyncMock()
        ) as mock_ensure:
            mock_client = AsyncMock()
            mock_ensure.return_value = mock_client

            client = await requests_adapter.get_client()

            mock_ensure.assert_called_once()
            assert client == mock_client

    def test_client_property_initialized(self, requests_adapter: Requests) -> None:
        """Test client property when initialized."""
        mock_client = AsyncMock()
        requests_adapter._client = mock_client

        client = requests_adapter.client

        assert client == mock_client

    def test_client_property_not_initialized(self, requests_adapter: Requests) -> None:
        """Test client property when not initialized."""
        requests_adapter._client = None

        with pytest.raises(RuntimeError, match="Client not initialized"):
            _ = requests_adapter.client

    @pytest.mark.asyncio
    async def test_get_method(self, requests_adapter: Requests) -> None:
        """Test GET method."""
        mock_client = AsyncMock()
        mock_response = AsyncMock()
        mock_client.get.return_value = mock_response
        mock_response.raise_for_status = MagicMock()

        with patch.object(
            requests_adapter, "get_client", AsyncMock(return_value=mock_client)
        ):
            response = await requests_adapter.get("https://example.com", timeout=5)

            mock_client.get.assert_called_once_with(
                "https://example.com",
                timeout=5,
                params=None,
                headers=None,
                cookies=None,
            )
            mock_response.raise_for_status.assert_called_once()
            assert response == mock_response

    @pytest.mark.asyncio
    async def test_post_method(self, requests_adapter: Requests) -> None:
        """Test POST method."""
        mock_client = AsyncMock()
        mock_response = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_response.raise_for_status = MagicMock()

        with patch.object(
            requests_adapter, "get_client", AsyncMock(return_value=mock_client)
        ):
            response = await requests_adapter.post(
                "https://example.com", data={"key": "value"}
            )

            mock_client.post.assert_called_once_with(
                "https://example.com", data={"key": "value"}, json=None, timeout=10
            )
            mock_response.raise_for_status.assert_called_once()
            assert response == mock_response

    @pytest.mark.asyncio
    async def test_put_method(self, requests_adapter: Requests) -> None:
        """Test PUT method."""
        mock_client = AsyncMock()
        mock_response = AsyncMock()
        mock_client.put.return_value = mock_response
        mock_response.raise_for_status = MagicMock()

        with patch.object(
            requests_adapter, "get_client", AsyncMock(return_value=mock_client)
        ):
            response = await requests_adapter.put(
                "https://example.com", data={"key": "value"}
            )

            mock_client.put.assert_called_once_with(
                "https://example.com", data={"key": "value"}, json=None, timeout=10
            )
            mock_response.raise_for_status.assert_called_once()
            assert response == mock_response

    @pytest.mark.asyncio
    async def test_delete_method(self, requests_adapter: Requests) -> None:
        """Test DELETE method."""
        mock_client = AsyncMock()
        mock_response = AsyncMock()
        mock_client.delete.return_value = mock_response
        mock_response.raise_for_status = MagicMock()

        with patch.object(
            requests_adapter, "get_client", AsyncMock(return_value=mock_client)
        ):
            response = await requests_adapter.delete("https://example.com", timeout=5)

            mock_client.delete.assert_called_once_with("https://example.com", timeout=5)
            mock_response.raise_for_status.assert_called_once()
            assert response == mock_response

    @pytest.mark.asyncio
    async def test_patch_method(self, requests_adapter: Requests) -> None:
        """Test PATCH method."""
        mock_client = AsyncMock()
        mock_response = AsyncMock()
        mock_client.patch.return_value = mock_response
        mock_response.raise_for_status = MagicMock()

        with patch.object(
            requests_adapter, "get_client", AsyncMock(return_value=mock_client)
        ):
            response = await requests_adapter.patch(
                "https://example.com", data={"key": "value"}
            )

            mock_client.patch.assert_called_once_with(
                "https://example.com", timeout=10, data={"key": "value"}, json=None
            )
            mock_response.raise_for_status.assert_called_once()
            assert response == mock_response

    @pytest.mark.asyncio
    async def test_head_method(self, requests_adapter: Requests) -> None:
        """Test HEAD method."""
        mock_client = AsyncMock()
        mock_response = AsyncMock()
        mock_client.head.return_value = mock_response
        mock_response.raise_for_status = MagicMock()

        with patch.object(
            requests_adapter, "get_client", AsyncMock(return_value=mock_client)
        ):
            response = await requests_adapter.head("https://example.com", timeout=5)

            mock_client.head.assert_called_once_with("https://example.com", timeout=5)
            mock_response.raise_for_status.assert_called_once()
            assert response == mock_response

    @pytest.mark.asyncio
    async def test_options_method(self, requests_adapter: Requests) -> None:
        """Test OPTIONS method."""
        mock_client = AsyncMock()
        mock_response = AsyncMock()
        mock_client.options.return_value = mock_response
        mock_response.raise_for_status = MagicMock()

        with patch.object(
            requests_adapter, "get_client", AsyncMock(return_value=mock_client)
        ):
            response = await requests_adapter.options("https://example.com", timeout=5)

            mock_client.options.assert_called_once_with(
                "https://example.com", timeout=5
            )
            mock_response.raise_for_status.assert_called_once()
            assert response == mock_response

    @pytest.mark.asyncio
    async def test_request_method(self, requests_adapter: Requests) -> None:
        """Test generic request method."""
        mock_client = AsyncMock()
        mock_response = AsyncMock()
        mock_client.request.return_value = mock_response
        mock_response.raise_for_status = MagicMock()

        with patch.object(
            requests_adapter, "get_client", AsyncMock(return_value=mock_client)
        ):
            response = await requests_adapter.request(
                "PUT", "https://example.com", data={"key": "value"}
            )

            mock_client.request.assert_called_once_with(
                "PUT",
                "https://example.com",
                data={"key": "value"},
                json=None,
                timeout=10,
            )
            mock_response.raise_for_status.assert_called_once()
            assert response == mock_response

    @pytest.mark.asyncio
    async def test_close(self, requests_adapter: Requests) -> None:
        """Test adapter close method."""
        mock_client = AsyncMock()
        requests_adapter._client = mock_client

        await requests_adapter.close()

        mock_client.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_no_client(self, requests_adapter: Requests) -> None:
        """Test adapter close method when no client exists."""
        requests_adapter._client = None

        await requests_adapter.close()

        # Should not raise any exception
