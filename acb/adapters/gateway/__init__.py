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
    # Base classes
    "GatewayBase",
    "GatewayConfig",
    "GatewaySettings",
    "GatewayStatus",
    "GatewayMetrics",
    # Authentication
    "AuthProvider",
    "AuthResult",
    "JWTAuthProvider",
    "APIKeyAuthProvider",
    "OAuth2AuthProvider",
    "AuthenticationMiddleware",
    # Middleware
    "MiddlewareBase",
    "MiddlewareChain",
    "CORSMiddleware",
    "SecurityHeadersMiddleware",
    "ValidationMiddleware",
    # Rate limiting
    "RateLimiter",
    "TokenBucketLimiter",
    "SlidingWindowLimiter",
    "RateLimitResult",
    "RateLimitConfig",
    # Usage tracking
    "UsageTracker",
    "UsageMetrics",
    "QuotaManager",
    "UsageAnalytics",
    # Main gateway
    "APIGateway",
    "GatewayRequest",
    "GatewayResponse",
    "RequestProcessor",
]
