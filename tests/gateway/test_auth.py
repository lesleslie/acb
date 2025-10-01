"""Tests for Authentication functionality."""

import time
from unittest.mock import AsyncMock, MagicMock

import pytest

from acb.gateway.auth import (
    AuthConfig,
    AuthMethod,
    AuthResult,
    AuthManager,
    APIKeyAuthenticator,
    JWTAuthenticator,
    OAuthAuthenticator,
)
from acb.gateway._base import GatewayRequest, HttpMethod


@pytest.fixture
def auth_config():
    """Authentication configuration."""
    return AuthConfig(
        enabled=True,
        method=AuthMethod.API_KEY,
        api_key_header="X-API-Key",
        jwt_secret="test-secret",
        jwt_algorithm="HS256",
        oauth_client_id="test-client",
        oauth_client_secret="test-secret",
        oauth_token_url="https://oauth.example.com/token",
    )


@pytest.fixture
def mock_request():
    """Mock gateway request."""
    return GatewayRequest(
        method=HttpMethod.GET,
        path="/api/test",
        headers={"X-API-Key": "valid-key"},
        body="",
        query_params={},
        tenant_id="test-tenant",
        client_ip="127.0.0.1",
        user_agent="test-agent",
        request_id="test-request",
        content_length=0,
    )


@pytest.fixture
def mock_storage():
    """Mock storage backend."""
    storage = AsyncMock()
    storage.get.return_value = None
    storage.set.return_value = None
    return storage


class TestAPIKeyAuthenticator:
    """Test cases for API Key authentication."""

    @pytest.mark.asyncio
    async def test_authenticate_valid_key(self, auth_config, mock_storage):
        """Test authentication with valid API key."""
        authenticator = APIKeyAuthenticator(auth_config, mock_storage)

        # Mock valid API key
        mock_storage.get.return_value = {
            "user_id": "test-user",
            "permissions": ["read", "write"],
            "active": True,
        }

        request = GatewayRequest(
            method=HttpMethod.GET,
            path="/api/test",
            headers={"X-API-Key": "valid-key"},
            body="",
            query_params={},
            tenant_id="test-tenant",
            client_ip="127.0.0.1",
            user_agent="test-agent",
            request_id="test-request",
            content_length=0,
        )

        result = await authenticator.authenticate(request)

        assert result.authenticated is True
        assert result.user_id == "test-user"
        assert result.permissions == ["read", "write"]
        assert result.error is None

    @pytest.mark.asyncio
    async def test_authenticate_invalid_key(self, auth_config, mock_storage):
        """Test authentication with invalid API key."""
        authenticator = APIKeyAuthenticator(auth_config, mock_storage)

        # Mock invalid API key
        mock_storage.get.return_value = None

        request = GatewayRequest(
            method=HttpMethod.GET,
            path="/api/test",
            headers={"X-API-Key": "invalid-key"},
            body="",
            query_params={},
            tenant_id="test-tenant",
            client_ip="127.0.0.1",
            user_agent="test-agent",
            request_id="test-request",
            content_length=0,
        )

        result = await authenticator.authenticate(request)

        assert result.authenticated is False
        assert result.user_id is None
        assert result.error == "Invalid API key"

    @pytest.mark.asyncio
    async def test_authenticate_missing_header(self, auth_config, mock_storage):
        """Test authentication with missing API key header."""
        authenticator = APIKeyAuthenticator(auth_config, mock_storage)

        request = GatewayRequest(
            method=HttpMethod.GET,
            path="/api/test",
            headers={},  # No API key header
            body="",
            query_params={},
            tenant_id="test-tenant",
            client_ip="127.0.0.1",
            user_agent="test-agent",
            request_id="test-request",
            content_length=0,
        )

        result = await authenticator.authenticate(request)

        assert result.authenticated is False
        assert result.error == "Missing API key"

    @pytest.mark.asyncio
    async def test_authenticate_inactive_key(self, auth_config, mock_storage):
        """Test authentication with inactive API key."""
        authenticator = APIKeyAuthenticator(auth_config, mock_storage)

        # Mock inactive API key
        mock_storage.get.return_value = {
            "user_id": "test-user",
            "permissions": ["read"],
            "active": False,
        }

        request = GatewayRequest(
            method=HttpMethod.GET,
            path="/api/test",
            headers={"X-API-Key": "inactive-key"},
            body="",
            query_params={},
            tenant_id="test-tenant",
            client_ip="127.0.0.1",
            user_agent="test-agent",
            request_id="test-request",
            content_length=0,
        )

        result = await authenticator.authenticate(request)

        assert result.authenticated is False
        assert result.error == "API key is inactive"


class TestJWTAuthenticator:
    """Test cases for JWT authentication."""

    @pytest.mark.asyncio
    async def test_authenticate_valid_token(self, auth_config, mock_storage):
        """Test authentication with valid JWT token."""
        import jwt

        authenticator = JWTAuthenticator(auth_config, mock_storage)

        # Create valid JWT token
        payload = {
            "sub": "test-user",
            "exp": int(time.time()) + 3600,
            "iat": int(time.time()),
            "permissions": ["read", "write"],
        }
        token = jwt.encode(payload, auth_config.jwt_secret, algorithm=auth_config.jwt_algorithm)

        request = GatewayRequest(
            method=HttpMethod.GET,
            path="/api/test",
            headers={"Authorization": f"Bearer {token}"},
            body="",
            query_params={},
            tenant_id="test-tenant",
            client_ip="127.0.0.1",
            user_agent="test-agent",
            request_id="test-request",
            content_length=0,
        )

        result = await authenticator.authenticate(request)

        assert result.authenticated is True
        assert result.user_id == "test-user"
        assert result.permissions == ["read", "write"]

    @pytest.mark.asyncio
    async def test_authenticate_expired_token(self, auth_config, mock_storage):
        """Test authentication with expired JWT token."""
        import jwt

        authenticator = JWTAuthenticator(auth_config, mock_storage)

        # Create expired JWT token
        payload = {
            "sub": "test-user",
            "exp": int(time.time()) - 3600,  # Expired 1 hour ago
            "iat": int(time.time()) - 7200,  # Issued 2 hours ago
        }
        token = jwt.encode(payload, auth_config.jwt_secret, algorithm=auth_config.jwt_algorithm)

        request = GatewayRequest(
            method=HttpMethod.GET,
            path="/api/test",
            headers={"Authorization": f"Bearer {token}"},
            body="",
            query_params={},
            tenant_id="test-tenant",
            client_ip="127.0.0.1",
            user_agent="test-agent",
            request_id="test-request",
            content_length=0,
        )

        result = await authenticator.authenticate(request)

        assert result.authenticated is False
        assert "expired" in result.error.lower()

    @pytest.mark.asyncio
    async def test_authenticate_invalid_signature(self, auth_config, mock_storage):
        """Test authentication with invalid JWT signature."""
        import jwt

        authenticator = JWTAuthenticator(auth_config, mock_storage)

        # Create JWT with wrong secret
        payload = {
            "sub": "test-user",
            "exp": int(time.time()) + 3600,
            "iat": int(time.time()),
        }
        token = jwt.encode(payload, "wrong-secret", algorithm=auth_config.jwt_algorithm)

        request = GatewayRequest(
            method=HttpMethod.GET,
            path="/api/test",
            headers={"Authorization": f"Bearer {token}"},
            body="",
            query_params={},
            tenant_id="test-tenant",
            client_ip="127.0.0.1",
            user_agent="test-agent",
            request_id="test-request",
            content_length=0,
        )

        result = await authenticator.authenticate(request)

        assert result.authenticated is False
        assert "invalid" in result.error.lower()

    @pytest.mark.asyncio
    async def test_authenticate_malformed_token(self, auth_config, mock_storage):
        """Test authentication with malformed JWT token."""
        authenticator = JWTAuthenticator(auth_config, mock_storage)

        request = GatewayRequest(
            method=HttpMethod.GET,
            path="/api/test",
            headers={"Authorization": "Bearer invalid.token.format"},
            body="",
            query_params={},
            tenant_id="test-tenant",
            client_ip="127.0.0.1",
            user_agent="test-agent",
            request_id="test-request",
            content_length=0,
        )

        result = await authenticator.authenticate(request)

        assert result.authenticated is False
        assert "invalid" in result.error.lower()


class TestOAuthAuthenticator:
    """Test cases for OAuth authentication."""

    @pytest.mark.asyncio
    async def test_authenticate_valid_token(self, auth_config, mock_storage):
        """Test authentication with valid OAuth token."""
        authenticator = OAuthAuthenticator(auth_config, mock_storage)

        # Mock valid token in cache
        mock_storage.get.return_value = {
            "user_id": "oauth-user",
            "permissions": ["read"],
            "expires_at": time.time() + 3600,
        }

        request = GatewayRequest(
            method=HttpMethod.GET,
            path="/api/test",
            headers={"Authorization": "Bearer oauth-token"},
            body="",
            query_params={},
            tenant_id="test-tenant",
            client_ip="127.0.0.1",
            user_agent="test-agent",
            request_id="test-request",
            content_length=0,
        )

        result = await authenticator.authenticate(request)

        assert result.authenticated is True
        assert result.user_id == "oauth-user"

    @pytest.mark.asyncio
    async def test_authenticate_token_introspection(self, auth_config, mock_storage):
        """Test OAuth token introspection."""
        authenticator = OAuthAuthenticator(auth_config, mock_storage)

        # Mock no cached token, but successful introspection
        mock_storage.get.return_value = None

        # Mock HTTP client for token introspection
        mock_response = AsyncMock()
        mock_response.json.return_value = {
            "active": True,
            "sub": "oauth-user",
            "scope": "read write",
        }
        mock_response.status_code = 200

        mock_client = AsyncMock()
        mock_client.post.return_value.__aenter__.return_value = mock_response
        authenticator._http_client = mock_client

        request = GatewayRequest(
            method=HttpMethod.GET,
            path="/api/test",
            headers={"Authorization": "Bearer new-oauth-token"},
            body="",
            query_params={},
            tenant_id="test-tenant",
            client_ip="127.0.0.1",
            user_agent="test-agent",
            request_id="test-request",
            content_length=0,
        )

        result = await authenticator.authenticate(request)

        assert result.authenticated is True
        assert result.user_id == "oauth-user"
        assert "read" in result.permissions
        assert "write" in result.permissions


class TestAuthManager:
    """Test cases for main AuthManager class."""

    @pytest.mark.asyncio
    async def test_authenticate_success(self, auth_config, mock_storage, mock_request):
        """Test successful authentication."""
        manager = AuthManager(auth_config, mock_storage)

        # Mock valid API key
        mock_storage.get.return_value = {
            "user_id": "test-user",
            "permissions": ["read"],
            "active": True,
        }

        result = await manager.authenticate(mock_request)

        assert result.authenticated is True
        assert result.user_id == "test-user"

    @pytest.mark.asyncio
    async def test_authenticate_disabled(self, auth_config, mock_storage, mock_request):
        """Test authentication when disabled."""
        auth_config.enabled = False
        manager = AuthManager(auth_config, mock_storage)

        result = await manager.authenticate(mock_request)

        # Should always succeed when authentication is disabled
        assert result.authenticated is True
        assert result.user_id is None

    @pytest.mark.asyncio
    async def test_authenticate_cache_hit(self, auth_config, mock_storage, mock_request):
        """Test authentication with cache hit."""
        manager = AuthManager(auth_config, mock_storage)

        # Mock cached authentication result
        cache_key = f"auth:{mock_request.tenant_id}:valid-key"
        cached_result = {
            "authenticated": True,
            "user_id": "cached-user",
            "permissions": ["read"],
            "cached_at": time.time(),
        }

        def mock_get(key):
            if key == cache_key:
                return cached_result
            return {"user_id": "test-user", "permissions": ["read"], "active": True}

        mock_storage.get.side_effect = mock_get

        result = await manager.authenticate(mock_request)

        assert result.authenticated is True
        assert result.user_id == "cached-user"

    @pytest.mark.asyncio
    async def test_get_health(self, auth_config, mock_storage):
        """Test health status."""
        manager = AuthManager(auth_config, mock_storage)

        health = await manager.get_health()

        assert health["status"] == "healthy"
        assert health["method"] == auth_config.method.value
        assert health["enabled"] == auth_config.enabled

    @pytest.mark.asyncio
    async def test_get_metrics(self, auth_config, mock_storage, mock_request):
        """Test metrics collection."""
        manager = AuthManager(auth_config, mock_storage)

        # Mock valid authentication
        mock_storage.get.return_value = {
            "user_id": "test-user",
            "permissions": ["read"],
            "active": True,
        }

        # Perform some authentications
        await manager.authenticate(mock_request)
        await manager.authenticate(mock_request)

        metrics = await manager.get_metrics()

        assert "method" in metrics
        assert "total_attempts" in metrics
        assert "successful_attempts" in metrics
        assert "failed_attempts" in metrics

    @pytest.mark.asyncio
    async def test_cleanup(self, auth_config, mock_storage):
        """Test authentication manager cleanup."""
        manager = AuthManager(auth_config, mock_storage)
        mock_storage.cleanup = AsyncMock()

        await manager.cleanup()

        mock_storage.cleanup.assert_called_once()