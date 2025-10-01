---
id: 01K6EGN78BGCBJFSKW0K9S5VXJ
---
# API Gateway Adapter

Comprehensive API Gateway implementation for ACB framework providing authentication, rate limiting, usage tracking, and request/response validation.

## Features

- **Authentication**: JWT, API key, and OAuth2 support
- **Rate Limiting**: Token bucket and sliding window algorithms
- **Usage Tracking**: Request metrics, quota management, and analytics
- **Middleware Chain**: CORS, security headers, validation, and logging
- **Request/Response Validation**: Pydantic schema validation
- **Analytics**: Endpoint and user usage analytics

## Quick Start

```python
from acb.adapters.gateway import APIGateway, GatewaySettings, GatewayConfig

# Configure gateway
config = GatewayConfig(
    auth_enabled=True,
    rate_limiting_enabled=True,
    usage_tracking_enabled=True,
    cors_enabled=True,
)

settings = GatewaySettings(gateway_config=config)

# Create and initialize gateway
gateway = APIGateway(settings)
await gateway.initialize()

# Add API key for authentication
await gateway.add_api_key("my-secret-key", "user123", ["read", "write"])

# Create user quota
await gateway.create_user_quota("user123", requests_per_hour=500)

# Handle requests
response = await gateway.handle_request(
    method="POST",
    path="/api/users",
    headers={"Authorization": "Bearer my-secret-key"},
    body={"name": "John Doe"},
    required_scopes=["write"]
)

print(f"Status: {response.status}")
print(f"Body: {response.body}")
```

## Configuration

### Basic Configuration

```yaml
# settings/gateway.yml
enabled: true
host: "0.0.0.0"
port: 8080
debug: false

# CORS settings
cors_enabled: true
cors_origins: ["*"]
cors_methods: ["GET", "POST", "PUT", "DELETE", "OPTIONS"]

# Rate limiting
rate_limiting_enabled: true
default_rate_limit: 100  # requests per minute
rate_limit_window_seconds: 60

# Authentication
auth_enabled: true
auth_providers: ["jwt", "api_key"]
jwt_secret: "your-secret-key"
jwt_algorithm: "HS256"

# Usage tracking
usage_tracking_enabled: true
usage_analytics_enabled: true

# Validation
validation_enabled: true
strict_validation: false
```

## Authentication

### JWT Authentication

```python
from acb.adapters.gateway.auth import JWTAuthProvider

# Configure JWT in settings
config = GatewayConfig(
    jwt_secret="your-secret-key",
    jwt_algorithm="HS256"
)

# Use JWT token in requests
headers = {"Authorization": "Bearer your-jwt-token"}
```

### API Key Authentication

```python
# Add API keys
await gateway.add_api_key("api-key-123", "user456", ["read"])

# Use API key in requests
headers = {"Authorization": "ApiKey api-key-123"}
```

## Rate Limiting

### Token Bucket Algorithm

```python
from acb.adapters.gateway.rate_limit import RateLimitConfig, TokenBucketLimiter

config = RateLimitConfig(
    requests_per_window=100,
    window_seconds=60,
    burst_size=10,
    replenish_rate=1.0
)

limiter = TokenBucketLimiter(config)
result = await limiter.check_rate_limit("user123")
```

### Sliding Window Algorithm

```python
from acb.adapters.gateway.rate_limit import SlidingWindowLimiter

limiter = SlidingWindowLimiter(config)
result = await limiter.check_rate_limit("user123")
```

## Usage Tracking and Analytics

### Track Usage

```python
from acb.adapters.gateway.usage import UsageTracker

tracker = UsageTracker()
await tracker.initialize()

# Usage is tracked automatically for authenticated requests
await tracker.record_request(
    user_id="user123",
    endpoint="/api/users",
    method="GET",
    response_status=200,
    response_time_ms=150.5
)
```

### Get Analytics

```python
# Get endpoint analytics
analytics = await gateway.get_usage_analytics(time_range_hours=24)
print(analytics["endpoints"])
print(analytics["users"])

# Get user-specific stats
user_stats = await gateway.get_user_usage_stats("user123")
print(f"Daily requests: {user_stats['daily_requests']}")
print(f"Remaining quota: {user_stats['remaining']['daily']}")
```

### Quota Management

```python
# Set custom quota for a user
await gateway.create_user_quota(
    user_id="premium_user",
    requests_per_hour=2000,
    requests_per_day=50000,
    requests_per_month=1000000,
    bytes_per_day=100 * 1024 * 1024  # 100MB
)
```

## Middleware

### Custom Middleware

```python
from acb.adapters.gateway.middleware import MiddlewareBase

class CustomMiddleware(MiddlewareBase):
    async def process_request(self, request):
        # Add custom request processing
        request["custom_header"] = "processed"
        return request

    async def process_response(self, response):
        # Add custom response processing
        response["headers"]["X-Custom"] = "processed"
        return response

# Add to gateway
gateway.processor.middleware_chain.add_middleware(CustomMiddleware())
```

### Request Validation

```python
from pydantic import BaseModel
from acb.adapters.gateway.middleware import ValidationMiddleware

class UserCreateSchema(BaseModel):
    name: str
    email: str
    age: int

# Register schema for validation
validation_middleware = gateway.processor.middleware_chain.get_middleware_by_type(ValidationMiddleware)
validation_middleware.register_schema("/api/users", "POST", UserCreateSchema)
```

## Health Monitoring

```python
# Check gateway health
health = await gateway.health_check()
print(f"Status: {health['status']}")
print(f"Components: {health['components']}")
print(f"Uptime: {health['uptime_seconds']} seconds")

# Check individual component health
auth_health = await gateway.processor.auth_middleware.health_check()
rate_limit_health = await gateway.processor.rate_limit_middleware.health_check()
```

## Integration with ACB

```python
from acb.depends import depends
from acb.adapters import import_adapter

# Register gateway with dependency injection
Gateway = import_adapter("gateway")
gateway = Gateway()
await gateway.initialize()

depends.set(Gateway, gateway)

# Use in other components
@depends.inject
async def my_service(gateway: Gateway = depends()):
    response = await gateway.handle_request("GET", "/api/health")
    return response
```

## Security Features

- **CORS Support**: Configurable cross-origin resource sharing
- **Security Headers**: Automatic security headers (HSTS, XSS protection, etc.)
- **Request Validation**: Schema-based request validation
- **Rate Limiting**: Multiple algorithms to prevent abuse
- **Authentication**: Multiple auth providers with scope validation
- **Usage Quotas**: Prevent resource abuse with quota enforcement

## Performance

- **Async Operations**: Full async/await support
- **Connection Pooling**: Efficient resource management
- **Memory Efficient**: Sliding windows and LRU caches
- **Metrics Collection**: Built-in performance monitoring
- **Background Processing**: Non-blocking analytics and cleanup

## Error Handling

The gateway provides comprehensive error handling with appropriate HTTP status codes:

- `400`: Bad Request (validation errors)
- `401`: Unauthorized (authentication failed)
- `402`: Payment Required (quota exceeded)
- `429`: Too Many Requests (rate limited)
- `500`: Internal Server Error (gateway errors)

## Module Metadata

The gateway adapter includes proper ACB metadata for discovery:

```python
MODULE_METADATA = AdapterMetadata(
    name="API Gateway",
    category="gateway",
    provider="acb",
    version="1.0.0",
    capabilities=[
        AdapterCapability.ASYNC_OPERATIONS,
        AdapterCapability.AUTHENTICATION,
        AdapterCapability.RATE_LIMITING,
        AdapterCapability.MONITORING,
        AdapterCapability.VALIDATION,
    ],
    required_packages=["pyjwt>=2.0.0", "pydantic>=2.0.0"],
)
```