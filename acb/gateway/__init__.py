"""API Gateway Package for ACB Framework.

This package provides comprehensive API Gateway functionality including:
- Rate limiting and throttling mechanisms
- API key management and authentication
- Usage tracking and quota enforcement
- Request/response validation integration
- Multi-tenant routing and isolation
- Analytics and monitoring collection
- Caching and response optimization
- Security headers and CORS management

Key Components:
    - GatewayService: Main gateway service with dependency injection
    - RateLimiter: Multiple rate limiting algorithms (token bucket, sliding window)
    - AuthManager: Authentication mechanisms (API keys, JWT, OAuth)
    - ValidationMiddleware: Request/response validation integration
    - RoutingEngine: Multi-tenant routing and isolation
    - Analytics: Usage tracking and analytics collection
    - CacheManager: Response caching and optimization
    - SecurityHeaders: Security headers and CORS management

Performance:
    - <1ms overhead for simple requests
    - <5ms for authenticated requests with validation
    - <10ms for complex routing with analytics
    - Memory efficient with connection pooling

Security:
    - Rate limiting for DoS protection
    - Authentication and authorization
    - Input validation and sanitization
    - Security headers enforcement
    - CORS policy management

Integration:
    - Services Layer: Full ServiceBase integration
    - Validation Layer: Seamless validation integration
    - Health Check System: Monitoring and metrics
    - Dependency Injection: ACB services integration
"""

from acb.gateway._base import (
    GatewayConfig,
    GatewayLevel,
    GatewayProtocol,
    GatewayResult,
    GatewaySettings,
)
from acb.gateway.analytics import AnalyticsCollector, AnalyticsConfig, AnalyticsEvent
from acb.gateway.auth import AuthConfig, AuthManager, AuthResult
from acb.gateway.cache import CacheConfig, CacheManager, CacheResult
from acb.gateway.discovery import (
    GatewayCapability,
    GatewayMetadata,
    GatewayStatus,
    generate_gateway_id,
    get_gateway_descriptor,
    import_gateway,
    list_available_gateways,
    list_enabled_gateways,
    list_gateways,
)
from acb.gateway.rate_limiting import RateLimitConfig, RateLimiter, RateLimitResult
from acb.gateway.routing import Route, RoutingConfig, RoutingEngine
from acb.gateway.security import SecurityConfig, SecurityHeaders, SecurityManager
from acb.gateway.service import GatewayService
from acb.gateway.validation import (
    RequestResponseValidator,
    ValidationResult,
    ValidationRule,
    ValidationSeverity,
    ValidationType,
)

__all__ = [
    # Core service
    "GatewayService",

    # Discovery system
    "GatewayCapability",
    "GatewayMetadata",
    "GatewayStatus",
    "generate_gateway_id",
    "get_gateway_descriptor",
    "import_gateway",
    "list_available_gateways",
    "list_enabled_gateways",
    "list_gateways",

    # Configuration and settings
    "GatewayConfig",
    "GatewaySettings",
    "GatewayLevel",
    "GatewayProtocol",

    # Results and responses
    "GatewayResult",

    # Authentication
    "AuthManager",
    "AuthResult",
    "AuthConfig",

    # Rate limiting
    "RateLimiter",
    "RateLimitConfig",
    "RateLimitResult",

    # Routing
    "RoutingEngine",
    "Route",
    "RoutingConfig",

    # Analytics
    "AnalyticsCollector",
    "AnalyticsConfig",
    "AnalyticsEvent",

    # Caching
    "CacheManager",
    "CacheConfig",
    "CacheResult",

    # Security
    "SecurityManager",
    "SecurityConfig",
    "SecurityHeaders",

    # Validation
    "RequestResponseValidator",
    "ValidationRule",
    "ValidationResult",
    "ValidationType",
    "ValidationSeverity",
]