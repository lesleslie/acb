> **ACB Documentation**: [Main](../../../README.md) | [Core Systems](../../README.md) | [Actions](../../actions/README.md) | [Adapters](../README.md) | [Requests](./README.md)

# Requests Adapter

> **Configuration**
> Choose the `requests` implementation in `settings/adapters.yaml` and tune it via `settings/requests.yaml`. Store secrets in `settings/secrets/` or via a secret manager so they never reach git.

The Requests adapter provides a standardized interface for making HTTP requests in ACB applications, with RFC 9111 compliant caching, connection pooling, and multiple client implementations.

## Table of Contents

- [Overview](#overview)
- [Available Implementations](#available-implementations)
- [Installation](#installation)
- [Configuration](#configuration)
- [Basic Usage](#basic-usage)
- [Advanced Usage](#advanced-usage)
  - [Async Context Managers](#async-context-managers)
  - [Working with Response Objects](#working-with-response-objects)
  - [HTTP Caching (RFC 9111)](#http-caching-rfc-9111)
  - [Custom Headers](#custom-headers)
  - [Authentication](#authentication)
  - [GraphQL Query Caching](#graphql-query-caching)
- [Troubleshooting](#troubleshooting)
- [Performance Considerations](#performance-considerations)
- [Architecture](#architecture)
- [Migration from Hishel](#migration-from-hishel)
- [Related Adapters](#related-adapters)
- [Additional Resources](#additional-resources)

## Overview

The ACB Requests adapter offers a consistent way to make HTTP requests with intelligent caching:

- **RFC 9111 HTTP Caching**: 80% compliant implementation with automatic cache control
- **Universal Cache Integration**: Works with memory or Redis cache backends
- **Async-First Design**: Fully asynchronous operations with proper resource cleanup
- **Multiple Backends**: HTTPX and Niquests implementations
- **Connection Pooling**: Efficient connection reuse and keep-alive
- **GraphQL Support**: POST body-based cache keys for GraphQL queries
- **ACB Pattern Compliance**: CleanupMixin, async context managers, dependency injection

## Available Implementations

| Implementation | Description | Best For |
| -------------- | -------------------------------- | ----------------------------------------------- |
| **HTTPX** | Modern, async-native HTTP client with HTTP/2 support | Most applications, default choice |
| **Niquests** | Python-requests-compatible async client | Migration from `requests` library |

Both implementations share the same universal caching layer and ACB patterns.

## Installation

```bash
# Install with Requests support
uv add --group requests

# With cache support (recommended for HTTP caching)
uv add --group requests --group cache
```

## Configuration

### Settings

Configure the Requests adapter in your `settings/adapters.yml` file:

```yaml
# Use HTTPX implementation (default)
requests: httpx

# Or use Niquests implementation
requests: niquests

# Cache backend for HTTP responses
cache: redis  # or: memory
```

### Requests Settings

Configure caching and connection pooling in `settings/app.yml`:

```yaml
requests:
  # HTTP response cache TTL (seconds)
  cache_ttl: 7200  # 2 hours

  # Connection pool settings
  max_connections: 100
  max_keepalive_connections: 20
  keepalive_expiry: 5.0

  # Default timeout (seconds)
  timeout: 10

  # Optional base URL for all requests
  base_url: "https://api.example.com"

  # Optional authentication (basic auth)
  auth:
    - username
    - password  # pragma: allowlist secret
```

## Basic Usage

```python
from acb.adapters import import_adapter

Requests = import_adapter("requests")

# Recommended: Use async context manager for automatic cleanup
async with Requests() as requests:
    response = await requests.get("https://api.example.com/users")
    print(f"Status: {response.status_code}")
    print(f"Data: {response.json()}")

# Alternative: Manual lifecycle management
requests = Requests()
try:
    response = await requests.get("https://api.example.com/users")
finally:
    await requests.cleanup()  # Important: cleanup resources
```

### HTTP Methods

```python
async with Requests() as requests:
    # GET request
    response = await requests.get(
        "https://api.example.com/users",
        params={"page": 1, "limit": 10},
        headers={"Accept": "application/json"},
    )

    # POST request
    response = await requests.post(
        "https://api.example.com/users",
        json={"name": "John Doe", "email": "john@example.com"},
    )

    # PUT request
    response = await requests.put(
        "https://api.example.com/users/123", json={"name": "John Smith"}
    )

    # DELETE request
    response = await requests.delete("https://api.example.com/users/123")

    # PATCH request
    response = await requests.patch(
        "https://api.example.com/users/123", json={"email": "john.smith@example.com"}
    )

    # HEAD request (cached like GET)
    response = await requests.head("https://api.example.com/users/123")

    # OPTIONS request
    response = await requests.options("https://api.example.com/users")
```

## Advanced Usage

### Async Context Managers

The Requests adapter supports async context managers for automatic resource cleanup:

```python
from acb.adapters import import_adapter

Requests = import_adapter("requests")

# Automatic client initialization and cleanup
async with Requests() as requests:
    response1 = await requests.get("https://api.example.com/data")
    response2 = await requests.post("https://api.example.com/submit", json={...})
    # Client automatically closed on exit
```

**Benefits**:

- Automatic HTTP client initialization
- Guaranteed resource cleanup (connection pools, file handles)
- Exception-safe cleanup (cleanup happens even if errors occur)
- Follows ACB adapter patterns (CleanupMixin)

### Working with Response Objects

```python
async with Requests() as requests:
    response = await requests.get("https://api.example.com/users/123")

    # Status code and headers
    print(f"Status: {response.status_code}")
    print(f"Content-Type: {response.headers['content-type']}")

    # JSON data (automatically parsed)
    user = response.json()
    print(f"User: {user['name']}, Email: {user['email']}")

    # Raw bytes content
    raw_content = response.content
    print(f"Response size: {len(raw_content)} bytes")

    # Text content (decoded)
    text_content = response.text
    print(f"Text: {text_content}")

    # Check response success
    response.raise_for_status()  # Raises exception if 4xx/5xx
```

### HTTP Caching (RFC 9111)

The Requests adapter implements RFC 9111 HTTP caching with 80% specification compliance:

**Supported Features**:

- ✅ `cache-control: no-store` (never cached)
- ✅ `cache-control: private` (not cached in shared cache)
- ✅ `cache-control: max-age` (TTL from server)
- ✅ `Pragma: no-cache` (HTTP/1.0 compatibility)
- ✅ Cacheable methods (GET, HEAD only)
- ✅ Cacheable status codes (200, 203, 206, 300, 301, 304, 410)
- ✅ Age calculation and freshness validation
- ✅ Vary header support (case-insensitive)

**Automatic Caching**:

```python
async with Requests() as requests:
    # First request: HTTP call made, response cached
    response1 = await requests.get("https://api.example.com/data")
    # Time: ~500ms (actual HTTP request)

    # Second request: Served from cache (no HTTP call)
    response2 = await requests.get("https://api.example.com/data")
    # Time: <1ms (cache hit)

    # Different URL: New HTTP call and cache entry
    response3 = await requests.get("https://api.example.com/other-data")
```

**Cache Behavior**:

```python
# GET and HEAD requests are cached
await requests.get("https://api.example.com/data")  # Cached
await requests.head("https://api.example.com/data")  # Cached

# POST, PUT, DELETE, PATCH are NOT cached (unsafe methods per RFC 9111)
await requests.post("https://api.example.com/data", json={...})  # Not cached
await requests.put("https://api.example.com/data", json={...})  # Not cached
await requests.delete("https://api.example.com/data")  # Not cached
```

**Server Cache-Control Headers**:

```python
# Server response with cache-control headers:
# Cache-Control: max-age=3600
# → Cached for 1 hour (server TTL)

# Cache-Control: no-store
# → Never cached

# Cache-Control: private
# → Not cached (ACB treats all caches as shared)

# No cache headers
# → Uses default TTL from settings (cache_ttl: 7200)
```

**Cache Key Generation**:

The cache key includes:

- HTTP method (GET, HEAD)
- Full URL (including query parameters)
- POST body hash (for GraphQL support)
- Vary header values (for content negotiation)

```python
# Different cache keys
await requests.get("https://api.example.com/data?page=1")  # Key 1
await requests.get("https://api.example.com/data?page=2")  # Key 2 (different params)
await requests.get("https://api.example.com/other")  # Key 3 (different URL)
```

### Custom Headers

```python
async with Requests() as requests:
    headers = {
        "Authorization": "Bearer token123",
        "X-Custom-Header": "CustomValue",
        "Accept-Language": "en-US",
    }

    response = await requests.get("https://api.example.com/protected", headers=headers)
```

### Authentication

```python
# Basic authentication (configured in settings)
# settings/app.yml:
# requests:
#   auth: [username, password]

async with Requests() as requests:
    # Auth automatically included
    response = await requests.get("https://api.example.com/secure")

# Bearer token authentication
async with Requests() as requests:
    token = "your_access_token"
    response = await requests.get(
        "https://api.example.com/secure", headers={"Authorization": f"Bearer {token}"}
    )

# API key authentication
async with Requests() as requests:
    api_key = "your_api_key"
    response = await requests.get(
        "https://api.example.com/secure", headers={"X-API-Key": api_key}
    )
```

### GraphQL Query Caching

GraphQL queries use POST requests, which are normally not cached. The universal cache supports POST body-based cache keys for GraphQL:

```python
async with Requests() as requests:
    # Each unique GraphQL query is cached separately by body hash
    query1 = {
        "query": """
            query GetUser($id: ID!) {
                user(id: $id) {
                    name
                    email
                }
            }
        """,
        "variables": {"id": "123"},
    }

    # First request: HTTP call made, cached by body hash
    response1 = await requests.post("https://api.example.com/graphql", json=query1)

    # Identical query: Served from cache (same body hash)
    response2 = await requests.post("https://api.example.com/graphql", json=query1)

    # Different query: New HTTP call (different body hash)
    query2 = {"query": "{ user(id: 2) { name } }"}
    response3 = await requests.post("https://api.example.com/graphql", json=query2)
```

**Note**: For production GraphQL applications with advanced features (normalized entity caching, query batching, schema introspection), consider dedicated libraries:

- [`gql`](https://github.com/graphql-python/gql) - Full-featured async GraphQL client
- [`strawberry-graphql`](https://strawberry.rocks/) - Modern Python GraphQL framework
- [`sgqlc`](https://github.com/profusion/sgqlc) - Simple GraphQL client with code generation

These can be used alongside ACB for complete GraphQL support.

## Troubleshooting

### Common Issues

**Connection Error**

- **Problem**: `ConnectionError: Connection refused`
- **Solution**:
  - Verify the URL is correct
  - Check network connectivity
  - Ensure the service is running and accessible

**Timeout Error**

- **Problem**: `TimeoutError: Request timed out`
- **Solution**:
  - Increase the timeout value in settings
  - Check if the service is responding slowly
  - Consider using async operations to avoid blocking

**Client Not Initialized**

- **Problem**: `RuntimeError: Client not initialized`
- **Solution**:
  - Use async context manager: `async with Requests() as requests:`
  - Or call `await adapter._ensure_client()` before requests
  - Always cleanup: `await requests.cleanup()`

**Cache Issues**

- **Problem**: Stale cached responses
- **Solution**:
  - Check cache TTL settings (`cache_ttl` in `app.yml`)
  - Verify Redis connection if using Redis cache
  - Check server `Cache-Control` headers

**Resource Leaks**

- **Problem**: Too many open connections
- **Solution**:
  - Always use async context managers or call `cleanup()`
  - Check connection pool settings (`max_connections`)
  - Verify `cleanup()` is called in exception handlers

## Performance Considerations

### Caching Performance

The universal cache provides significant performance improvements:

```python
# Benchmark example:
# First request (cache miss): ~500ms (HTTP + serialization)
await requests.get("https://api.example.com/slow-endpoint")

# Subsequent requests (cache hit): <1ms (from Redis/memory)
await requests.get("https://api.example.com/slow-endpoint")
await requests.get("https://api.example.com/slow-endpoint")
```

**Cache Performance**:

- **Cache hit**: \<1ms (msgspec deserialization + dict reconstruction)
- **Cache miss**: HTTP time + \<5ms (msgspec serialization overhead)
- **Memory cache**: Fastest (\<0.1ms hit time)
- **Redis cache**: \<1ms hit time (local Redis), \<10ms (remote Redis)

### Connection Pooling

Both HTTPX and Niquests use connection pooling for efficiency:

```yaml
# settings/app.yml
requests:
  max_connections: 100           # Total connection pool size
  max_keepalive_connections: 20  # Keep-alive connections
  keepalive_expiry: 5.0          # Keep-alive timeout (seconds)
```

**Benefits**:

- Reuses TCP connections to the same host
- Reduces connection establishment overhead (~50-100ms per connection)
- Improves throughput for multiple requests

### Timeout Management

```python
# Fast API calls (status checks)
await requests.get("https://api.example.com/status", timeout=2)

# Normal API calls
await requests.get("https://api.example.com/data", timeout=10)

# Large data transfers
await requests.get("https://api.example.com/large-dataset", timeout=30)
```

**Guidelines**:

- Set timeouts based on expected response time
- Too short: Operations fail unnecessarily
- Too long: Poor user experience
- Default: 10 seconds (configurable in settings)

## Architecture

### Universal HTTP Cache

The Requests adapter uses a universal caching layer (`UniversalHTTPCache`) that works with any HTTP client:

```
┌─────────────────────────────────────────────────────┐
│          Requests Adapter (HTTPX/Niquests)         │
├─────────────────────────────────────────────────────┤
│                                                     │
│  ┌─────────────────────────────────────────────┐  │
│  │      UniversalHTTPCache                     │  │
│  │  - RFC 9111 compliance (80%)                │  │
│  │  - Cache key generation                     │  │
│  │  - Freshness validation                     │  │
│  │  - msgspec serialization                    │  │
│  └───────────────┬─────────────────────────────┘  │
│                  │                                  │
│                  ▼                                  │
│  ┌─────────────────────────────────────────────┐  │
│  │       ACB Cache Adapter                     │  │
│  │  (memory, Redis, or custom)                 │  │
│  └─────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────┘
```

**Key Components**:

1. **Cache Key Generation**: `SHA-256(method:url:body_hash:vary_headers)`
1. **Serialization**: msgspec MessagePack (binary, Redis-compatible)
1. **RFC 9111 Rules**: Cacheability checks, freshness validation
1. **Storage**: ACB cache adapter (memory or Redis)

### Implementation Pattern

Both HTTPX and Niquests follow the same ACB adapter pattern:

```python
from acb.cleanup import CleanupMixin
from ._cache import UniversalHTTPCache


class Requests(RequestsBase, CleanupMixin):
    def __init__(self, cache: Inject[t.Any], **kwargs):
        RequestsBase.__init__(self, **kwargs)
        CleanupMixin.__init__(self)

        self._http_client = None
        self._http_cache = UniversalHTTPCache(
            cache=cache, default_ttl=self.config.requests.cache_ttl
        )

    async def _ensure_client(self):
        """Lazy initialization of HTTP client."""
        if self._http_client is None:
            self._http_client = await self._create_client()
        return self._http_client

    async def __aenter__(self):
        """Async context manager entry."""
        await self._ensure_client()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.cleanup()

    async def _cleanup_resources(self):
        """Resource cleanup."""
        if self._http_client:
            await self._http_client.close()
```

## Migration from Hishel

If you're upgrading from a previous ACB version that used Hishel:

**Breaking Changes**:

- ✅ **Automatic**: Cache behavior is now automatic (no manual `CacheClient` needed)
- ✅ **Headers**: Remove `X-Hishel-*` headers (not needed)
- ✅ **Import**: Remove `from hishel import *` imports
- ✅ **Storage**: Remove `ACBCacheStorage` usage (deleted class)

**Migration Steps**:

```python
# Before (v0.30.x and earlier with Hishel)
from hishel.httpx import AsyncCacheClient
from acb.adapters.requests._base import ACBCacheStorage

storage = ACBCacheStorage(default_ttl=3600.0)
async with AsyncCacheClient(storage=storage) as client:
    response = await client.get(
        "https://api.example.com/data", headers={"X-Hishel-Body-Key": "true"}
    )

# After (v0.31.x with universal cache)
from acb.adapters import import_adapter

Requests = import_adapter("requests")
async with Requests() as requests:
    response = await requests.get("https://api.example.com/data")
    # GraphQL POST caching automatic (no header needed)
```

**What Changed**:

- Caching is now automatic for GET/HEAD requests
- GraphQL POST body caching is automatic (SHA-256 body hash)
- No Hishel-specific headers or configuration needed
- Simpler API, same performance

## Related Adapters

The Requests adapter integrates with:

- [**Cache Adapter**](../cache/README.md): Required for HTTP response caching
- [**Secret Adapter**](../secret/README.md): Store API keys and credentials securely
- [**NoSQL Adapter**](../nosql/README.md): Store API responses for longer-term persistence

Integration example:

```python
from acb.adapters import import_adapter

Requests = import_adapter("requests")
Secret = import_adapter("secret")
NoSQL = import_adapter("nosql")


async def fetch_and_store_weather():
    # Get API key from secrets
    api_key = await Secret().get("weather_api_key")

    # Make HTTP request with caching
    async with Requests() as requests:
        response = await requests.get(
            f"https://api.weatherservice.com/forecast?api_key={api_key}"
        )

        if response.status_code == 200:
            weather_data = response.json()

            # Store in database for historical analysis
            async with NoSQL() as nosql:
                await nosql.weather_data.insert_one(
                    {
                        "date": datetime.now().isoformat(),
                        "forecast": weather_data,
                        "location": "New York",
                    }
                )

            return weather_data
```

## Additional Resources

- [HTTPX Documentation](https://www.python-httpx.org/)
- [Niquests Documentation](https://niquests.readthedocs.io/)
- [RFC 9111: HTTP Caching](https://www.rfc-editor.org/rfc/rfc9111.html)
- [HTTP Status Codes](https://httpstatuses.com/)
- [ACB Cache Adapter](../cache/README.md)
- [ACB Secret Adapter](../secret/README.md)
- [ACB Adapters Overview](../README.md)
