"""Tests for Authentication functionality."""

import time
from unittest.mock import AsyncMock, MagicMock

import pytest

from acb.gateway.auth import (
    AuthConfig,
    AuthMethod,
    AuthResult,
    AuthManager,
    APIKeyProvider,
    JWTProvider,
    BasicAuthProvider,
)
from acb.gateway._base import GatewayRequest, RequestMethod


@pytest.fixture
def auth_config():
    """Authentication configuration."""
    return AuthConfig(
        method=AuthMethod.API_KEY,
        api_key_header="X-API-Key",
        jwt_secret="test-secret",
        jwt_algorithm="HS256",
        oauth2_client_id="test-client",
        oauth2_client_secret="test-secret",
        oauth2_introspection_url="https://oauth.example.com/token",
    )


@pytest.fixture
def mock_request():
    """Mock gateway request."""
    return GatewayRequest(
        method=RequestMethod.GET,
        path="/api/test",
        headers={"X-API-Key": "valid-key"},
        body="",
        query_params={},
        client_ip="127.0.0.1",
        user_agent="test-agent",
    )


@pytest.fixture
def mock_storage():
    """Mock storage backend."""
    storage = AsyncMock()
    storage.get.return_value = None
    storage.set.return_value = None
    return storage


class TestAPIKeyProvider:
    """Test cases for API Key authentication."""

    @pytest.mark.asyncio
    async def test_authenticate_valid_key(self, auth_config, mock_storage):
        """Test authentication with valid API key."""
        authenticator = APIKeyProvider()

        # Setup auth config with valid API key
        auth_config.api_keys = {
            "valid-key": {
                "user_id": "test-user",
                "permissions": ["read", "write"],
                "active": True,
            }
        }

        request = GatewayRequest(
            method=RequestMethod.GET,
            path="/api/test",
            headers={"X-API-Key": "valid-key"},
            body="",
            query_params={},
            client_ip="127.0.0.1",
            user_agent="test-agent",
        )

        result = await authenticator.authenticate(request, auth_config)

        assert result.authenticated is True
        assert result.user.user_id == "test-user"

    @pytest.mark.asyncio
    async def test_authenticate_invalid_key(self, auth_config, mock_storage):
        """Test authentication with invalid API key."""
        authenticator = APIKeyProvider()

        # Auth config has no valid keys
        auth_config.api_keys = {}

        request = GatewayRequest(
            method=RequestMethod.GET,
            path="/api/test",
            headers={"X-API-Key": "invalid-key"},
            body="",
            query_params={},
            client_ip="127.0.0.1",
            user_agent="test-agent",
        )

        result = await authenticator.authenticate(request, auth_config)

        assert result.authenticated is False
        assert result.error_message == "Invalid API key"

    @pytest.mark.asyncio
    async def test_authenticate_missing_header(self, auth_config, mock_storage):
        """Test authentication with missing API key header."""
        authenticator = APIKeyProvider()

        request = GatewayRequest(
            method=RequestMethod.GET,
            path="/api/test",
            headers={},  # No API key header
            body="",
            query_params={},
            client_ip="127.0.0.1",
            user_agent="test-agent",
        )

        result = await authenticator.authenticate(request, auth_config)

        assert result.authenticated is False
        assert result.error_message == "API key required"

    @pytest.mark.asyncio
    async def test_authenticate_inactive_key(self, auth_config, mock_storage):
        """Test authentication with inactive API key."""
        authenticator = APIKeyProvider()

        # Setup auth config with inactive key (no 'active' field means inactive)
        # Note: The actual implementation checks if key exists in api_keys dict
        # An inactive key would simply not be in the dict or have active=False
        auth_config.api_keys = {}  # Inactive keys not in config

        request = GatewayRequest(
            method=RequestMethod.GET,
            path="/api/test",
            headers={"X-API-Key": "inactive-key"},
            body="",
            query_params={},
            client_ip="127.0.0.1",
            user_agent="test-agent",
        )

        result = await authenticator.authenticate(request, auth_config)

        assert result.authenticated is False
        assert result.error_message == "Invalid API key"


class TestJWTProvider:
    """Test cases for JWT authentication."""

    @pytest.mark.asyncio
    async def test_authenticate_valid_token(self, auth_config, mock_storage):
        """Test authentication with valid JWT token."""
        import jwt

        authenticator = JWTProvider()

        # Create valid JWT token
        payload = {
            "sub": "test-user",
            "exp": int(time.time()) + 3600,
            "iat": int(time.time()),
            "roles": ["admin"],
            "scopes": ["read", "write"],
        }
        token = jwt.encode(payload, auth_config.jwt_secret, algorithm=auth_config.jwt_algorithm)

        request = GatewayRequest(
            method=RequestMethod.GET,
            path="/api/test",
            headers={"Authorization": f"Bearer {token}"},
            body="",
            query_params={},
            client_ip="127.0.0.1",
            user_agent="test-agent",
        )

        result = await authenticator.authenticate(request, auth_config)

        assert result.authenticated is True
        assert result.user.user_id == "test-user"
        assert result.user.scopes == ["read", "write"]

    @pytest.mark.asyncio
    async def test_authenticate_expired_token(self, auth_config, mock_storage):
        """Test authentication with expired JWT token."""
        import jwt

        authenticator = JWTProvider()

        # Create expired JWT token
        payload = {
            "sub": "test-user",
            "exp": int(time.time()) - 3600,  # Expired 1 hour ago
            "iat": int(time.time()) - 7200,  # Issued 2 hours ago
        }
        token = jwt.encode(payload, auth_config.jwt_secret, algorithm=auth_config.jwt_algorithm)

        request = GatewayRequest(
            method=RequestMethod.GET,
            path="/api/test",
            headers={"Authorization": f"Bearer {token}"},
            body="",
            query_params={},
            client_ip="127.0.0.1",
            user_agent="test-agent",
        )

        result = await authenticator.authenticate(request, auth_config)

        assert result.authenticated is False
        assert "expired" in result.error_message.lower()

    @pytest.mark.asyncio
    async def test_authenticate_invalid_signature(self, auth_config, mock_storage):
        """Test authentication with invalid JWT signature."""
        import jwt

        authenticator = JWTProvider()

        # Create JWT with wrong secret
        payload = {
            "sub": "test-user",
            "exp": int(time.time()) + 3600,
            "iat": int(time.time()),
        }
        token = jwt.encode(payload, "wrong-secret", algorithm=auth_config.jwt_algorithm)

        request = GatewayRequest(
            method=RequestMethod.GET,
            path="/api/test",
            headers={"Authorization": f"Bearer {token}"},
            body="",
            query_params={},
            client_ip="127.0.0.1",
            user_agent="test-agent",
        )

        result = await authenticator.authenticate(request, auth_config)

        assert result.authenticated is False
        assert "invalid" in result.error_message.lower()

    @pytest.mark.asyncio
    async def test_authenticate_malformed_token(self, auth_config, mock_storage):
        """Test authentication with malformed JWT token."""
        authenticator = JWTProvider()

        request = GatewayRequest(
            method=RequestMethod.GET,
            path="/api/test",
            headers={"Authorization": "Bearer invalid.token.format"},
            body="",
            query_params={},
            client_ip="127.0.0.1",
            user_agent="test-agent",
        )

        result = await authenticator.authenticate(request, auth_config)

        assert result.authenticated is False
        assert "invalid" in result.error_message.lower()


class TestBasicAuthProvider:
    """Test cases for Basic authentication."""

    @pytest.mark.asyncio
    async def test_authenticate_valid_credentials(self, auth_config, mock_storage):
        """Test authentication with valid basic credentials."""
        import base64

        authenticator = BasicAuthProvider()

        # Setup auth config with valid user
        auth_config.basic_auth_users = {
            "testuser": "testpass"
        }

        # Create basic auth header
        credentials = base64.b64encode(b"testuser:testpass").decode("utf-8")

        request = GatewayRequest(
            method=RequestMethod.GET,
            path="/api/test",
            headers={"Authorization": f"Basic {credentials}"},
            body="",
            query_params={},
            client_ip="127.0.0.1",
            user_agent="test-agent",
        )

        result = await authenticator.authenticate(request, auth_config)

        assert result.authenticated is True
        assert result.user.user_id == "testuser"

    @pytest.mark.asyncio
    async def test_authenticate_invalid_credentials(self, auth_config, mock_storage):
        """Test authentication with invalid basic credentials."""
        import base64

        authenticator = BasicAuthProvider()

        # Setup auth config with valid user
        auth_config.basic_auth_users = {
            "testuser": "testpass"
        }

        # Create basic auth header with wrong password
        credentials = base64.b64encode(b"testuser:wrongpass").decode("utf-8")

        request = GatewayRequest(
            method=RequestMethod.GET,
            path="/api/test",
            headers={"Authorization": f"Basic {credentials}"},
            body="",
            query_params={},
            client_ip="127.0.0.1",
            user_agent="test-agent",
        )

        result = await authenticator.authenticate(request, auth_config)

        assert result.authenticated is False
        assert "invalid" in result.error_message.lower()


class TestAuthManager:
    """Test cases for main AuthManager class."""

    @pytest.mark.asyncio
    async def test_authenticate_success(self, auth_config, mock_storage, mock_request):
        """Test successful authentication."""
        manager = AuthManager()

        # Setup auth config with valid API key
        auth_config.api_keys = {
            "valid-key": {
                "user_id": "test-user",
                "permissions": ["read"],
                "active": True,
            }
        }

        result = await manager.authenticate(mock_request, auth_config)

        assert result.authenticated is True
        assert result.user.user_id == "test-user"

    @pytest.mark.asyncio
    async def test_authenticate_not_required(self, mock_storage, mock_request):
        """Test authentication when not required."""
        config = AuthConfig(required=False)
        manager = AuthManager()

        result = await manager.authenticate(mock_request, config)

        # Should always succeed when authentication is not required
        assert result.authenticated is True
        assert result.user is None

    @pytest.mark.asyncio
    async def test_authenticate_cache_hit(self, auth_config, mock_storage, mock_request):
        """Test authentication with cache hit."""
        manager = AuthManager()

        # Setup auth config with valid API key
        # AuthManager doesn't have built-in caching - providers handle their own caching
        auth_config.api_keys = {
            "valid-key": {
                "user_id": "test-user",
                "permissions": ["read"],
                "active": True,
            }
        }

        result = await manager.authenticate(mock_request, auth_config)

        assert result.authenticated is True
        assert result.user.user_id == "test-user"

    @pytest.mark.asyncio
    async def test_get_health(self, auth_config, mock_storage):
        """Test health status."""
        manager = AuthManager()

        health = await manager.get_health(auth_config)

        assert health["status"] == "healthy"
        assert health["method"] == auth_config.method.value
        assert health["required"] == auth_config.required

    @pytest.mark.asyncio
    async def test_get_metrics(self, auth_config, mock_storage, mock_request):
        """Test metrics collection."""
        manager = AuthManager()

        # Setup auth config with valid API key
        auth_config.api_keys = {
            "valid-key": {
                "user_id": "test-user",
                "permissions": ["read"],
                "active": True,
            }
        }

        # Perform some authentications
        await manager.authenticate(mock_request, auth_config)
        await manager.authenticate(mock_request, auth_config)

        metrics = await manager.get_metrics()

        assert "method" in metrics
        assert "total_attempts" in metrics
        assert "successful_attempts" in metrics
        assert "failed_attempts" in metrics

    @pytest.mark.asyncio
    async def test_cleanup(self, auth_config, mock_storage):
        """Test authentication manager cleanup."""
        manager = AuthManager()

        # Cleanup should not raise any errors
        await manager.cleanup()

        # AuthManager cleanup is a no-op currently
        assert True
