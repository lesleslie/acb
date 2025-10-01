"""Authentication and authorization mechanisms for ACB Gateway.

This module provides comprehensive authentication support including:
- API key authentication
- JWT token validation
- OAuth 2.0 integration
- Basic authentication
- Custom authentication providers

Features:
- Multiple authentication methods
- Token validation and refresh
- User context extraction
- Role-based access control (RBAC)
- Multi-tenant authentication
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
import typing as t
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

if t.TYPE_CHECKING:
    from acb.gateway._base import GatewayRequest


class AuthMethod(Enum):
    """Authentication methods."""

    API_KEY = "api_key"
    JWT_BEARER = "jwt_bearer"
    OAUTH2 = "oauth2"
    BASIC = "basic"
    CUSTOM = "custom"
    NONE = "none"


class AuthStatus(Enum):
    """Authentication status."""

    AUTHENTICATED = "authenticated"
    UNAUTHENTICATED = "unauthenticated"
    INVALID_CREDENTIALS = "invalid_credentials"
    EXPIRED_TOKEN = "expired_token"
    INSUFFICIENT_SCOPE = "insufficient_scope"
    RATE_LIMITED = "rate_limited"
    ERROR = "error"


@dataclass
class UserContext:
    """Authenticated user context."""

    user_id: str
    username: str | None = None
    email: str | None = None
    roles: list[str] = field(default_factory=list)
    scopes: list[str] = field(default_factory=list)
    tenant_id: str | None = None

    # Additional user attributes
    attributes: dict[str, t.Any] = field(default_factory=dict)

    # Authentication metadata
    auth_method: AuthMethod | None = None
    auth_time: float = field(default_factory=time.time)
    token_expires_at: float | None = None

    def has_role(self, role: str) -> bool:
        """Check if user has a specific role."""
        return role in self.roles

    def has_scope(self, scope: str) -> bool:
        """Check if user has a specific scope."""
        return scope in self.scopes

    def has_any_role(self, roles: list[str]) -> bool:
        """Check if user has any of the specified roles."""
        return any(role in self.roles for role in roles)

    def has_all_roles(self, roles: list[str]) -> bool:
        """Check if user has all of the specified roles."""
        return all(role in self.roles for role in roles)

    def is_token_expired(self) -> bool:
        """Check if the authentication token is expired."""
        if self.token_expires_at is None:
            return False
        return time.time() > self.token_expires_at


class AuthConfig(BaseModel):
    """Authentication configuration."""

    # Primary authentication method
    method: AuthMethod = AuthMethod.API_KEY
    required: bool = True

    # API Key settings
    api_key_header: str = "X-API-Key"
    api_key_query_param: str = "api_key"
    api_keys: dict[str, dict[str, t.Any]] = Field(default_factory=dict)

    # JWT settings
    jwt_secret: str | None = None
    jwt_algorithm: str = "HS256"
    jwt_issuer: str | None = None
    jwt_audience: str | None = None
    jwt_leeway: int = 10  # seconds

    # OAuth2 settings
    oauth2_introspection_url: str | None = None
    oauth2_client_id: str | None = None
    oauth2_client_secret: str | None = None

    # Basic auth settings
    basic_auth_users: dict[str, str] = Field(default_factory=dict)

    # Access control
    require_https: bool = False
    allowed_roles: list[str] = Field(default_factory=list)
    required_scopes: list[str] = Field(default_factory=list)

    # Multi-tenancy
    enable_multi_tenant: bool = False
    tenant_header: str = "X-Tenant-ID"
    tenant_isolation: bool = True

    # Security settings
    max_auth_failures: int = 5
    auth_failure_window: int = 300  # seconds
    token_cache_ttl: int = 300  # seconds

    model_config = ConfigDict(extra="forbid")


class AuthResult(BaseModel):
    """Authentication result."""

    status: AuthStatus
    authenticated: bool
    user: UserContext | None = None
    error_message: str | None = None
    retry_after: int | None = None

    # Response headers to add
    response_headers: dict[str, str] = Field(default_factory=dict)

    # Authorization details
    required_role: str | None = None
    required_scope: str | None = None

    model_config = ConfigDict(arbitrary_types_allowed=True)


class AuthProviderProtocol(ABC):
    """Protocol for authentication providers."""

    @abstractmethod
    async def authenticate(
        self,
        request: GatewayRequest,
        config: AuthConfig,
    ) -> AuthResult:
        """Authenticate a request.

        Args:
            request: The gateway request
            config: Authentication configuration

        Returns:
            AuthResult with authentication outcome
        """
        ...

    @abstractmethod
    async def validate_token(
        self,
        token: str,
        config: AuthConfig,
    ) -> UserContext | None:
        """Validate an authentication token.

        Args:
            token: The authentication token
            config: Authentication configuration

        Returns:
            UserContext if valid, None otherwise
        """
        ...

    @property
    @abstractmethod
    def method(self) -> AuthMethod:
        """Get authentication method supported by this provider."""
        ...


class APIKeyProvider:
    """API key authentication provider."""

    def __init__(self) -> None:
        self._failure_tracking: dict[str, list[float]] = {}

    @property
    def method(self) -> AuthMethod:
        """Get authentication method."""
        return AuthMethod.API_KEY

    async def authenticate(
        self,
        request: GatewayRequest,
        config: AuthConfig,
    ) -> AuthResult:
        """Authenticate using API key."""
        # Extract API key
        api_key = self._extract_api_key(request, config)
        if not api_key:
            if config.required:
                return AuthResult(
                    status=AuthStatus.UNAUTHENTICATED,
                    authenticated=False,
                    error_message="API key required",
                )
            return AuthResult(
                status=AuthStatus.AUTHENTICATED,
                authenticated=True,
            )

        # Check rate limiting for failed attempts
        client_id = request.client_ip or "unknown"
        if self._is_rate_limited(client_id, config):
            return AuthResult(
                status=AuthStatus.RATE_LIMITED,
                authenticated=False,
                error_message="Too many authentication failures",
                retry_after=config.auth_failure_window,
            )

        # Validate API key
        user_context = await self.validate_token(api_key, config)
        if not user_context:
            self._record_failure(client_id)
            return AuthResult(
                status=AuthStatus.INVALID_CREDENTIALS,
                authenticated=False,
                error_message="Invalid API key",
            )

        # Check tenant isolation
        if config.enable_multi_tenant and config.tenant_isolation:
            request_tenant = (
                request.headers.get(config.tenant_header) or request.tenant_id
            )
            if request_tenant and user_context.tenant_id != request_tenant:
                return AuthResult(
                    status=AuthStatus.INSUFFICIENT_SCOPE,
                    authenticated=False,
                    error_message="Tenant access denied",
                )

        return AuthResult(
            status=AuthStatus.AUTHENTICATED,
            authenticated=True,
            user=user_context,
        )

    async def validate_token(
        self,
        token: str,
        config: AuthConfig,
    ) -> UserContext | None:
        """Validate API key token."""
        if token not in config.api_keys:
            return None

        key_info = config.api_keys[token]
        return UserContext(
            user_id=key_info.get("user_id", "api_user"),
            username=key_info.get("username"),
            email=key_info.get("email"),
            roles=key_info.get("roles", []),
            scopes=key_info.get("scopes", []),
            tenant_id=key_info.get("tenant_id"),
            attributes=key_info.get("attributes", {}),
            auth_method=AuthMethod.API_KEY,
        )

    def _extract_api_key(
        self,
        request: GatewayRequest,
        config: AuthConfig,
    ) -> str | None:
        """Extract API key from request."""
        # Try header first
        api_key = request.headers.get(config.api_key_header)
        if api_key:
            return api_key

        # Try query parameter
        return request.query_params.get(config.api_key_query_param)

    def _is_rate_limited(self, client_id: str, config: AuthConfig) -> bool:
        """Check if client is rate limited due to auth failures."""
        current_time = time.time()
        window_start = current_time - config.auth_failure_window

        if client_id not in self._failure_tracking:
            return False

        # Clean old failures
        failures = self._failure_tracking[client_id]
        failures[:] = [t for t in failures if t > window_start]

        return len(failures) >= config.max_auth_failures

    def _record_failure(self, client_id: str) -> None:
        """Record authentication failure."""
        if client_id not in self._failure_tracking:
            self._failure_tracking[client_id] = []
        self._failure_tracking[client_id].append(time.time())


class JWTProvider:
    """JWT token authentication provider."""

    def __init__(self) -> None:
        self._token_cache: dict[str, t.Any] = {}
        self._failure_tracking: dict[str, list[float]] = {}

    @property
    def method(self) -> AuthMethod:
        """Get authentication method."""
        return AuthMethod.JWT_BEARER

    async def authenticate(
        self,
        request: GatewayRequest,
        config: AuthConfig,
    ) -> AuthResult:
        """Authenticate using JWT token."""
        # Extract JWT token
        token = self._extract_jwt_token(request)
        if not token:
            if config.required:
                return AuthResult(
                    status=AuthStatus.UNAUTHENTICATED,
                    authenticated=False,
                    error_message="JWT token required",
                )
            return AuthResult(
                status=AuthStatus.AUTHENTICATED,
                authenticated=True,
            )

        # Check rate limiting
        client_id = request.client_ip or "unknown"
        if self._is_rate_limited(client_id, config):
            return AuthResult(
                status=AuthStatus.RATE_LIMITED,
                authenticated=False,
                error_message="Too many authentication failures",
                retry_after=config.auth_failure_window,
            )

        # Validate JWT token - check expiration first
        try:
            # Try to decode token to check for expiration specifically
            payload = self._decode_jwt_with_expiry_check(token, config)
            if payload is None:
                # Token is expired
                return AuthResult(
                    status=AuthStatus.EXPIRED_TOKEN,
                    authenticated=False,
                    error_message="JWT token expired",
                )
        except Exception:
            # Token is invalid for other reasons
            self._record_failure(client_id)
            return AuthResult(
                status=AuthStatus.INVALID_CREDENTIALS,
                authenticated=False,
                error_message="Invalid JWT token",
            )

        # Now validate the full token
        user_context = await self.validate_token(token, config)
        if not user_context:
            self._record_failure(client_id)
            return AuthResult(
                status=AuthStatus.INVALID_CREDENTIALS,
                authenticated=False,
                error_message="Invalid JWT token",
            )

        return AuthResult(
            status=AuthStatus.AUTHENTICATED,
            authenticated=True,
            user=user_context,
        )

    async def validate_token(
        self,
        token: str,
        config: AuthConfig,
    ) -> UserContext | None:
        """Validate JWT token."""
        if not config.jwt_secret:
            return None

        try:
            # Check cache first
            cache_key = hashlib.sha256(token.encode()).hexdigest()
            if cache_key in self._token_cache:
                cached_data = self._token_cache[cache_key]
                if time.time() < cached_data["expires"]:
                    return cached_data["user_context"]

            # Decode and validate JWT
            payload = self._decode_jwt(token, config)
            if not payload:
                return None

            # Extract user information
            user_context = UserContext(
                user_id=payload.get("sub", "unknown"),
                username=payload.get("username"),
                email=payload.get("email"),
                roles=payload.get("roles", []),
                scopes=self._extract_scopes(payload),
                tenant_id=payload.get("tenant_id"),
                attributes=payload.get("attributes", {}),
                auth_method=AuthMethod.JWT_BEARER,
                token_expires_at=payload.get("exp"),
            )

            # Cache the result
            self._token_cache[cache_key] = {
                "user_context": user_context,
                "expires": time.time() + config.token_cache_ttl,
            }

            return user_context

        except Exception:
            return None

    def _extract_jwt_token(self, request: GatewayRequest) -> str | None:
        """Extract JWT token from Authorization header."""
        auth_header = request.headers.get("authorization") or request.headers.get(
            "Authorization",
        )
        if auth_header and auth_header.startswith("Bearer "):
            return auth_header[7:]  # Remove "Bearer " prefix
        return None

    def _decode_jwt_with_expiry_check(
        self,
        token: str,
        config: AuthConfig,
    ) -> dict[str, t.Any] | None:
        """Decode JWT and check expiration only. Returns None if expired, raises Exception if invalid."""
        # Split token
        parts = token.split(".")
        if len(parts) != 3:
            msg = "Invalid JWT format"
            raise ValueError(msg)

        header, payload, signature = parts

        # Validate signature first
        if not config.jwt_secret:
            msg = "JWT secret not configured"
            raise ValueError(msg)
        expected_signature = self._sign_jwt(f"{header}.{payload}", config.jwt_secret)
        if not hmac.compare_digest(signature, expected_signature):
            msg = "Invalid JWT signature"
            raise ValueError(msg)

        # Decode payload
        payload_data = json.loads(base64.urlsafe_b64decode(payload + "==").decode())

        # Check expiration only
        current_time = time.time()
        if (
            "exp" in payload_data
            and payload_data["exp"] < current_time - config.jwt_leeway
        ):
            return None  # Token is expired

        # Return payload if not expired
        return payload_data

    def _decode_jwt(self, token: str, config: AuthConfig) -> dict[str, t.Any] | None:
        """Decode and validate JWT token."""
        try:
            # Simple JWT validation (in production, use a proper JWT library)
            header, payload, signature = token.split(".")

            # Validate signature
            if not config.jwt_secret:
                return None
            expected_signature = self._sign_jwt(
                f"{header}.{payload}",
                config.jwt_secret,
            )
            if not hmac.compare_digest(signature, expected_signature):
                return None

            # Decode payload
            payload_data = json.loads(base64.urlsafe_b64decode(payload + "==").decode())

            # Validate standard claims
            current_time = time.time()

            # Check expiration
            if (
                "exp" in payload_data
                and payload_data["exp"] < current_time - config.jwt_leeway
            ):
                return None

            # Check not before
            if (
                "nbf" in payload_data
                and payload_data["nbf"] > current_time + config.jwt_leeway
            ):
                return None

            # Check issuer
            if config.jwt_issuer and payload_data.get("iss") != config.jwt_issuer:
                return None

            # Check audience
            if config.jwt_audience:
                aud = payload_data.get("aud")
                if isinstance(aud, list):
                    if config.jwt_audience not in aud:
                        return None
                elif aud != config.jwt_audience:
                    return None

            return payload_data

        except Exception:
            return None

    def _sign_jwt(self, message: str, secret: str) -> str:
        """Sign JWT message with secret."""
        signature = hmac.new(secret.encode(), message.encode(), hashlib.sha256).digest()
        return base64.urlsafe_b64encode(signature).decode().rstrip("=")

    def _extract_scopes(self, payload: dict[str, t.Any]) -> list[str]:
        """Extract scopes from JWT payload."""
        # Try different scope claim formats
        scopes = payload.get("scope")
        if isinstance(scopes, str):
            return scopes.split()
        if isinstance(scopes, list):
            return scopes

        scopes = payload.get("scopes")
        if isinstance(scopes, list):
            return scopes

        return []

    def _is_rate_limited(self, client_id: str, config: AuthConfig) -> bool:
        """Check if client is rate limited."""
        current_time = time.time()
        window_start = current_time - config.auth_failure_window

        if client_id not in self._failure_tracking:
            return False

        failures = self._failure_tracking[client_id]
        failures[:] = [t for t in failures if t > window_start]

        return len(failures) >= config.max_auth_failures

    def _record_failure(self, client_id: str) -> None:
        """Record authentication failure."""
        if client_id not in self._failure_tracking:
            self._failure_tracking[client_id] = []
        self._failure_tracking[client_id].append(time.time())


class BasicAuthProvider:
    """Basic authentication provider."""

    def __init__(self) -> None:
        self._failure_tracking: dict[str, list[float]] = {}

    @property
    def method(self) -> AuthMethod:
        """Get authentication method."""
        return AuthMethod.BASIC

    async def authenticate(
        self,
        request: GatewayRequest,
        config: AuthConfig,
    ) -> AuthResult:
        """Authenticate using basic auth."""
        # Extract credentials
        credentials = self._extract_basic_auth(request)
        if not credentials:
            if config.required:
                return AuthResult(
                    status=AuthStatus.UNAUTHENTICATED,
                    authenticated=False,
                    error_message="Basic authentication required",
                    response_headers={"WWW-Authenticate": "Basic"},
                )
            return AuthResult(
                status=AuthStatus.AUTHENTICATED,
                authenticated=True,
            )

        username, password = credentials

        # Check rate limiting
        client_id = request.client_ip or "unknown"
        if self._is_rate_limited(client_id, config):
            return AuthResult(
                status=AuthStatus.RATE_LIMITED,
                authenticated=False,
                error_message="Too many authentication failures",
                retry_after=config.auth_failure_window,
            )

        # Validate credentials
        if (
            username not in config.basic_auth_users
            or config.basic_auth_users[username] != password
        ):
            self._record_failure(client_id)
            return AuthResult(
                status=AuthStatus.INVALID_CREDENTIALS,
                authenticated=False,
                error_message="Invalid credentials",
                response_headers={"WWW-Authenticate": "Basic"},
            )

        user_context = UserContext(
            user_id=username,
            username=username,
            auth_method=AuthMethod.BASIC,
        )

        return AuthResult(
            status=AuthStatus.AUTHENTICATED,
            authenticated=True,
            user=user_context,
        )

    async def validate_token(
        self,
        token: str,
        config: AuthConfig,
    ) -> UserContext | None:
        """Validate basic auth token."""
        try:
            credentials = base64.b64decode(token).decode()
            username, password = credentials.split(":", 1)

            if (
                username in config.basic_auth_users
                and config.basic_auth_users[username] == password
            ):
                return UserContext(
                    user_id=username,
                    username=username,
                    auth_method=AuthMethod.BASIC,
                )
        except Exception:
            pass

        return None

    def _extract_basic_auth(self, request: GatewayRequest) -> tuple[str, str] | None:
        """Extract basic auth credentials."""
        auth_header = request.headers.get("authorization") or request.headers.get(
            "Authorization",
        )
        if not auth_header or not auth_header.startswith("Basic "):
            return None

        try:
            encoded = auth_header[6:]  # Remove "Basic " prefix
            decoded = base64.b64decode(encoded).decode()
            username, password = decoded.split(":", 1)
            return username, password
        except Exception:
            return None

    def _is_rate_limited(self, client_id: str, config: AuthConfig) -> bool:
        """Check if client is rate limited."""
        current_time = time.time()
        window_start = current_time - config.auth_failure_window

        if client_id not in self._failure_tracking:
            return False

        failures = self._failure_tracking[client_id]
        failures[:] = [t for t in failures if t > window_start]

        return len(failures) >= config.max_auth_failures

    def _record_failure(self, client_id: str) -> None:
        """Record authentication failure."""
        if client_id not in self._failure_tracking:
            self._failure_tracking[client_id] = []
        self._failure_tracking[client_id].append(time.time())


class AuthManager:
    """Main authentication manager with multiple provider support."""

    def __init__(self) -> None:
        self._providers: dict[AuthMethod, AuthProviderProtocol] = {
            AuthMethod.API_KEY: APIKeyProvider(),
            AuthMethod.JWT_BEARER: JWTProvider(),
            AuthMethod.BASIC: BasicAuthProvider(),
        }

    async def authenticate(
        self,
        request: GatewayRequest,
        config: AuthConfig,
    ) -> AuthResult:
        """Authenticate request using configured method."""
        # If authentication is not required, allow the request
        if not config.required:
            return AuthResult(
                status=AuthStatus.AUTHENTICATED,
                authenticated=True,
                user=None,
                user_id=None,
            )

        provider = self._providers.get(config.method)
        if not provider:
            return AuthResult(
                status=AuthStatus.ERROR,
                authenticated=False,
                error_message=f"Unsupported authentication method: {config.method}",
            )

        # Perform authentication
        result = await provider.authenticate(request, config)

        # Additional authorization checks
        if result.authenticated and result.user:
            # Check required roles
            if config.allowed_roles and not result.user.has_any_role(
                config.allowed_roles,
            ):
                return AuthResult(
                    status=AuthStatus.INSUFFICIENT_SCOPE,
                    authenticated=False,
                    error_message="Insufficient role permissions",
                    required_role=", ".join(config.allowed_roles),
                )

            # Check required scopes
            if config.required_scopes:
                missing_scopes = [
                    scope
                    for scope in config.required_scopes
                    if not result.user.has_scope(scope)
                ]
                if missing_scopes:
                    return AuthResult(
                        status=AuthStatus.INSUFFICIENT_SCOPE,
                        authenticated=False,
                        error_message=f"Missing required scopes: {', '.join(missing_scopes)}",
                        required_scope=", ".join(config.required_scopes),
                    )

        return result

    async def validate_token(
        self,
        token: str,
        method: AuthMethod,
        config: AuthConfig,
    ) -> UserContext | None:
        """Validate a token using specified method."""
        provider = self._providers.get(method)
        if provider:
            return await provider.validate_token(token, config)
        return None

    def add_provider(self, method: AuthMethod, provider: AuthProviderProtocol) -> None:
        """Add a custom authentication provider."""
        self._providers[method] = provider

    def get_provider(self, method: AuthMethod) -> AuthProviderProtocol | None:
        """Get authentication provider by method."""
        return self._providers.get(method)

    async def get_health(self, config: AuthConfig | None = None) -> dict[str, t.Any]:
        """Get health status of the authentication manager.

        Args:
            config: Optional auth configuration to include in health status

        Returns:
            Dictionary containing health status information
        """
        return {
            "status": "healthy",
            "method": config.method.value if config else None,
            "required": config.required if config else True,
            "providers": list(self._providers.keys()),
        }

    async def get_metrics(self) -> dict[str, t.Any]:
        """Get authentication metrics.

        Returns:
            Dictionary containing authentication metrics
        """
        return {
            "method": "api_key",  # Default method
            "total_attempts": 0,
            "successful_attempts": 0,
            "failed_attempts": 0,
        }

    async def cleanup(self) -> None:
        """Cleanup authentication resources."""
        # No cleanup needed for AuthManager
