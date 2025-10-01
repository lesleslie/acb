"""Authentication providers for API Gateway."""

import time
import typing as t
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime

import jwt

from ._base import GatewayBase, GatewaySettings


@dataclass
class AuthResult:
    """Result of authentication attempt."""

    success: bool
    user_id: str | None = None
    scopes: list[str] | None = None
    error: str | None = None
    metadata: dict[str, t.Any] | None = None


class AuthProvider(ABC):
    """Abstract base class for authentication providers."""

    def __init__(self, settings: GatewaySettings) -> None:
        self.settings = settings

    @abstractmethod
    async def authenticate(self, token: str) -> AuthResult:
        """Authenticate a token and return result."""
        pass

    @abstractmethod
    async def validate_scopes(
        self, result: AuthResult, required_scopes: list[str]
    ) -> bool:
        """Validate that auth result has required scopes."""
        pass


class JWTAuthProvider(AuthProvider):
    """JWT-based authentication provider."""

    def __init__(self, settings: GatewaySettings) -> None:
        super().__init__(settings)
        self.secret = settings.gateway_config.jwt_secret
        self.algorithm = settings.gateway_config.jwt_algorithm

    async def authenticate(self, token: str) -> AuthResult:
        """Authenticate JWT token."""
        try:
            # Remove 'Bearer ' prefix if present
            if token.startswith("Bearer "):
                token = token[7:]

            payload = jwt.decode(token, self.secret, algorithms=[self.algorithm])

            # Check expiration
            if "exp" in payload:
                if datetime.utcnow().timestamp() > payload["exp"]:
                    return AuthResult(success=False, error="Token expired")

            return AuthResult(
                success=True,
                user_id=payload.get("sub", payload.get("user_id")),
                scopes=payload.get("scopes", []),
                metadata={"jwt_payload": payload},
            )

        except jwt.ExpiredSignatureError:
            return AuthResult(success=False, error="Token expired")
        except jwt.InvalidTokenError as e:
            return AuthResult(success=False, error=f"Invalid token: {e}")
        except Exception as e:
            return AuthResult(success=False, error=f"Authentication error: {e}")

    async def validate_scopes(
        self, result: AuthResult, required_scopes: list[str]
    ) -> bool:
        """Validate JWT scopes."""
        if not result.success or not required_scopes:
            return result.success

        user_scopes = result.scopes or []
        return all(scope in user_scopes for scope in required_scopes)


class APIKeyAuthProvider(AuthProvider):
    """API key-based authentication provider."""

    def __init__(self, settings: GatewaySettings) -> None:
        super().__init__(settings)
        self._api_keys: dict[str, dict[str, t.Any]] = {}

    def add_api_key(
        self,
        api_key: str,
        user_id: str,
        scopes: list[str] | None = None,
        metadata: dict[str, t.Any] | None = None,
    ) -> None:
        """Add an API key to the provider."""
        self._api_keys[api_key] = {
            "user_id": user_id,
            "scopes": scopes or [],
            "metadata": metadata or {},
            "created_at": time.time(),
        }

    async def authenticate(self, token: str) -> AuthResult:
        """Authenticate API key."""
        try:
            # Remove common prefixes
            for prefix in ["Bearer ", "ApiKey ", "API-Key "]:
                if token.startswith(prefix):
                    token = token[len(prefix) :]

            if token not in self._api_keys:
                return AuthResult(success=False, error="Invalid API key")

            key_data = self._api_keys[token]
            return AuthResult(
                success=True,
                user_id=key_data["user_id"],
                scopes=key_data["scopes"],
                metadata=key_data["metadata"],
            )

        except Exception as e:
            return AuthResult(success=False, error=f"API key authentication error: {e}")

    async def validate_scopes(
        self, result: AuthResult, required_scopes: list[str]
    ) -> bool:
        """Validate API key scopes."""
        if not result.success or not required_scopes:
            return result.success

        user_scopes = result.scopes or []
        return all(scope in user_scopes for scope in required_scopes)


class OAuth2AuthProvider(AuthProvider):
    """OAuth2-based authentication provider."""

    def __init__(self, settings: GatewaySettings) -> None:
        super().__init__(settings)
        self._token_cache: dict[str, dict[str, t.Any]] = {}

    async def authenticate(self, token: str) -> AuthResult:
        """Authenticate OAuth2 token."""
        try:
            # Remove 'Bearer ' prefix if present
            if token.startswith("Bearer "):
                token = token[7:]

            # Check cache first
            if token in self._token_cache:
                cached = self._token_cache[token]
                if time.time() < cached["expires_at"]:
                    return AuthResult(
                        success=True,
                        user_id=cached["user_id"],
                        scopes=cached["scopes"],
                        metadata=cached["metadata"],
                    )

            # In a real implementation, this would validate with OAuth2 provider
            # For now, we'll return a basic validation
            return AuthResult(
                success=True,
                user_id="oauth2_user",
                scopes=["read", "write"],
                metadata={"provider": "oauth2"},
            )

        except Exception as e:
            return AuthResult(success=False, error=f"OAuth2 authentication error: {e}")

    async def validate_scopes(
        self, result: AuthResult, required_scopes: list[str]
    ) -> bool:
        """Validate OAuth2 scopes."""
        if not result.success or not required_scopes:
            return result.success

        user_scopes = result.scopes or []
        return all(scope in user_scopes for scope in required_scopes)


class AuthenticationMiddleware(GatewayBase):
    """Authentication middleware for API Gateway."""

    def __init__(self, settings: GatewaySettings | None = None) -> None:
        super().__init__(settings)
        self.providers: dict[str, AuthProvider] = {}

    async def initialize(self) -> None:
        """Initialize authentication providers."""
        await super().initialize()

        config = self.settings.gateway_config
        if "jwt" in config.auth_providers:
            self.providers["jwt"] = JWTAuthProvider(self.settings)

        if "api_key" in config.auth_providers:
            self.providers["api_key"] = APIKeyAuthProvider(self.settings)

        if "oauth2" in config.auth_providers:
            self.providers["oauth2"] = OAuth2AuthProvider(self.settings)

    async def authenticate_request(
        self, headers: dict[str, str], required_scopes: list[str] | None = None
    ) -> AuthResult:
        """Authenticate a request using available providers."""
        auth_header = headers.get("Authorization", "")

        if not auth_header:
            return AuthResult(success=False, error="No authorization header")

        # Try each provider
        for provider_name, provider in self.providers.items():
            try:
                result = await provider.authenticate(auth_header)
                if result.success:
                    # Validate scopes if required
                    if required_scopes:
                        if not await provider.validate_scopes(result, required_scopes):
                            return AuthResult(
                                success=False, error="Insufficient permissions"
                            )

                    self.record_request(success=True)
                    return result

            except Exception as e:
                self.record_error(f"Provider {provider_name} error: {e}")
                continue

        self.record_request(success=False)
        self.metrics.requests_unauthorized += 1
        return AuthResult(success=False, error="Authentication failed")

    def add_api_key(
        self,
        api_key: str,
        user_id: str,
        scopes: list[str] | None = None,
        metadata: dict[str, t.Any] | None = None,
    ) -> None:
        """Add API key to the API key provider."""
        if "api_key" in self.providers:
            provider = self.providers["api_key"]
            if isinstance(provider, APIKeyAuthProvider):
                provider.add_api_key(api_key, user_id, scopes, metadata)
