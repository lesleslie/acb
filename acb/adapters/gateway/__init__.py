"""API Gateway adapter for ACB framework.

Provides comprehensive API gateway functionality including rate limiting,
authentication, usage tracking, and request/response validation.
"""

from ._base import (
    GatewayBase,
    GatewayConfig,
    GatewayMetrics,
    GatewaySettings,
    GatewayStatus,
)
from .auth import (
    APIKeyAuthProvider,
    AuthenticationMiddleware,
    AuthProvider,
    AuthResult,
    JWTAuthProvider,
    OAuth2AuthProvider,
)
from .gateway import (
    APIGateway,
    GatewayRequest,
    GatewayResponse,
    RequestProcessor,
)
from .middleware import (
    CORSMiddleware,
    MiddlewareBase,
    MiddlewareChain,
    SecurityHeadersMiddleware,
    ValidationMiddleware,
)
from .rate_limit import (
    RateLimitConfig,
    RateLimiter,
    RateLimitResult,
    SlidingWindowLimiter,
    TokenBucketLimiter,
)
from .usage import (
    QuotaManager,
    UsageAnalytics,
    UsageMetrics,
    UsageTracker,
)

__all__ = [
    # Main gateway
    "APIGateway",
    "APIKeyAuthProvider",
    # Authentication
    "AuthProvider",
    "AuthResult",
    "AuthenticationMiddleware",
    "CORSMiddleware",
    # Base classes
    "GatewayBase",
    "GatewayConfig",
    "GatewayMetrics",
    "GatewayRequest",
    "GatewayResponse",
    "GatewaySettings",
    "GatewayStatus",
    "JWTAuthProvider",
    # Middleware
    "MiddlewareBase",
    "MiddlewareChain",
    "OAuth2AuthProvider",
    "QuotaManager",
    "RateLimitConfig",
    "RateLimitResult",
    # Rate limiting
    "RateLimiter",
    "RequestProcessor",
    "SecurityHeadersMiddleware",
    "SlidingWindowLimiter",
    "TokenBucketLimiter",
    "UsageAnalytics",
    "UsageMetrics",
    # Usage tracking
    "UsageTracker",
    "ValidationMiddleware",
]
