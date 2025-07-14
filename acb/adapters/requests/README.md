> **ACB Documentation**: [Main](../../../README.md) | [Core Systems](../../README.md) | [Actions](../../actions/README.md) | [Adapters](../README.md) | [Requests](./README.md)

# Requests Adapter

The Requests adapter provides a standardized interface for making HTTP requests in ACB applications, with support for caching, retries, and multiple client implementations.

## Table of Contents

- [Overview](#overview)
- [Available Implementations](#available-implementations)
- [Installation](#installation)
- [Configuration](#configuration)
- [Basic Usage](#basic-usage)
- [Advanced Usage](#advanced-usage)
  - [Working with Response Objects](#working-with-response-objects)
  - [Request Caching](#request-caching)
  - [Custom Headers](#custom-headers)
  - [Authentication](#authentication)
- [Troubleshooting](#troubleshooting)
- [Performance Considerations](#performance-considerations)
- [Implementation Details](#implementation-details)
- [Related Adapters](#related-adapters)
- [Additional Resources](#additional-resources)

## Overview

The ACB Requests adapter offers a consistent way to make HTTP requests:

- Asynchronous HTTP client operations
- Multiple backend implementations
- Integrated request caching with Redis
- Standardized error handling
- Configurable timeouts and retries
- Automatic JSON serialization/deserialization
- Session management

## Available Implementations

| Implementation | Description | Best For |
|----------------|-------------|----------|
| **HTTPX** | Modern, async-native HTTP client | Most applications, default choice |
| **Niquests** | Extended HTTP client | Advanced use cases (placeholder implementation) |

## Installation

```bash
# Install with Requests support
uv add "acb[requests]"

# Or include it with other dependencies
uv add "acb[requests,redis,cache]"
```

## Configuration

### Settings

Configure the Requests adapter in your `settings/adapters.yml` file:

```yaml
# Use HTTPX implementation
requests: httpx

# Or use Niquests implementation (when available)
requests: niquests

# Or disable request adapter
requests: null
```

### Requests Settings

The Requests adapter settings can be customized in your `settings/app.yml` file:

```yaml
requests:
  # Default cache TTL for HTTP responses (in seconds)
  cache_ttl: 3600  # 1 hour

  # Default timeout for requests (in seconds)
  default_timeout: 10

  # Default retry configuration
  retries:
    max_attempts: 3
    backoff_factor: 0.5
    status_forcelist: [500, 502, 503, 504]
```

## Basic Usage

```python
from acb.depends import depends
from acb.adapters import import_adapter

# Import the Requests adapter
Requests = import_adapter("requests")

# Get the Requests instance via dependency injection
requests = depends.get(Requests)

# Make a GET request
response = await requests.get("https://api.example.com/users", timeout=5)
print(f"Status code: {response.status_code}")
print(f"Response body: {response.json()}")

# Make a POST request
data = {
    "name": "John Doe",
    "email": "john@example.com"
}
response = await requests.post("https://api.example.com/users", data=data, timeout=10)
print(f"Created user with ID: {response.json()['id']}")

# Make a PUT request
data = {
    "name": "John Smith",
    "email": "john.smith@example.com"
}
response = await requests.put("https://api.example.com/users/123", data=data)

# Make a DELETE request
response = await requests.delete("https://api.example.com/users/123")
```

## Advanced Usage

### Working with Response Objects

```python
# Get detailed information from response objects
response = await requests.get("https://api.example.com/users/123")

# Status code and headers
print(f"Status: {response.status_code}")
print(f"Content type: {response.headers['content-type']}")

# JSON data (automatically parsed)
user = response.json()
print(f"User: {user['name']}, Email: {user['email']}")

# Raw content
raw_content = response.content
print(f"Raw response size: {len(raw_content)} bytes")

# Text content
text_content = response.text
print(f"Text content: {text_content}")
```

### Request Caching

The Requests adapter automatically caches responses using Redis:

```python
# This request will be cached based on URL and request parameters
first_response = await requests.get("https://api.example.com/data")

# This identical request will return the cached response without making a new HTTP request
second_response = await requests.get("https://api.example.com/data")

# A request with different parameters will not use the cache
different_response = await requests.get("https://api.example.com/data?filter=new")

# The cache behavior is controlled by the cache_ttl setting in your configuration
# You can also bypass the cache for specific requests if needed
```

### Custom Headers

```python
# Set custom headers for a request
headers = {
    "Authorization": "Bearer token123",
    "X-Custom-Header": "CustomValue",
    "Accept-Language": "en-US"
}

response = await requests.get(
    "https://api.example.com/protected-resource",
    headers=headers
)
```

### Authentication

```python
# Basic authentication
response = await requests.get(
    "https://api.example.com/secure",
    auth=("username", "password")
)

# Bearer token authentication
token = "your_access_token"
response = await requests.get(
    "https://api.example.com/secure",
    headers={"Authorization": f"Bearer {token}"}
)

# API key authentication
api_key = "your_api_key"
response = await requests.get(
    "https://api.example.com/secure",
    headers={"X-API-Key": api_key}
)
```

## Troubleshooting

### Common Issues

1. **Connection Error**
   - **Problem**: `ConnectionError: Connection refused`
   - **Solution**:
     - Verify the URL is correct
     - Check network connectivity
     - Ensure the service is running and accessible

2. **Timeout Error**
   - **Problem**: `TimeoutError: Request timed out`
   - **Solution**:
     - Increase the timeout value
     - Check if the service is responding slowly
     - Consider optimizing the request payload size

3. **Authentication Failure**
   - **Problem**: `HTTP 401 Unauthorized` or `HTTP 403 Forbidden`
   - **Solution**:
     - Verify authentication credentials
     - Check if the token has expired
     - Ensure you have the correct permissions

4. **Cache-Related Issues**
   - **Problem**: Unexpected cached responses
   - **Solution**:
     - Check Redis connection settings
     - Verify the cache TTL configuration
     - Ensure unique request parameters for different requests

5. **Rate Limiting**
   - **Problem**: `HTTP 429 Too Many Requests`
   - **Solution**:
     - Implement request throttling
     - Add exponential backoff between requests
     - Contact API provider for rate limit increase

## Performance Considerations

### Caching Strategy

The Requests adapter uses Redis for caching HTTP responses, which can significantly improve performance:

```python
# Without caching, each of these calls would make a separate HTTP request
# With caching enabled, subsequent identical requests use the cached response
await requests.get("https://api.example.com/slow-endpoint")  # ~500ms (actual request)
await requests.get("https://api.example.com/slow-endpoint")  # ~5ms (from cache)
await requests.get("https://api.example.com/slow-endpoint")  # ~5ms (from cache)
```

### Timeout Management

Properly configured timeouts prevent your application from hanging:

```python
# Set appropriate timeouts for different types of requests
# Fast API calls
await requests.get("https://api.example.com/status", timeout=2)

# Calls that might take longer
await requests.get("https://api.example.com/large-dataset", timeout=30)

# Balance between user experience and operation completion
# Too short: Operations might fail unnecessarily
# Too long: Users might experience UI delays
```

### Connection Pooling

The HTTPX implementation uses connection pooling for better performance:

- Reuses connections for requests to the same host
- Reduces connection establishment overhead
- Improves request throughput

## Implementation Details

The Requests adapter implements these core methods:

```python
class RequestsBase:
    async def get(self, url: str, timeout: int = 5) -> Response: ...
    async def post(self, url: str, data: dict[str, Any], timeout: int = 5) -> Response: ...
    async def put(self, url: str, data: dict[str, Any], timeout: int = 5) -> Response: ...
    async def delete(self, url: str, timeout: int = 5) -> Response: ...
```

The HTTPX implementation uses `hishel` for request caching with Redis:

```python
class Requests(RequestsBase):
    storage: AsyncRedisStorage
    controller: Controller

    def cache_key(self, request: Request, body: bytes) -> str:
        key = generate_key(request, body)
        return f"{self.config.app.name}:httpx:{key}"

    async def get(self, url: str, timeout: int = 5) -> HttpxResponse:
        async with AsyncCacheClient(
            storage=self.storage, controller=self.controller
        ) as client:
            return await client.get(url, timeout=timeout)

    # Additional methods for post, put, delete...
```

## Related Adapters

The Requests adapter works well with these other ACB adapters:

- [**Cache Adapter**](../cache/README.md): Used indirectly for response caching
- [**Secret Adapter**](../secret/README.md): Store API keys and credentials securely
- [**NoSQL Adapter**](../nosql/README.md): Store API responses for longer-term persistence

Integration example:

```python
from acb.depends import depends
from acb.adapters import import_adapter

# Get necessary adapters
Requests = import_adapter("requests")
Secret = import_adapter("secret")
NoSQL = import_adapter("nosql")

requests = depends.get(Requests)
secret = depends.get(Secret)
nosql = depends.get(NoSQL)

async def fetch_and_store_weather():
    # Get API key from secrets manager
    api_key = await secret.get("weather_api_key")

    # Make API request
    response = await requests.get(
        f"https://api.weatherservice.com/forecast?api_key={api_key}"
    )

    if response.status_code == 200:
        weather_data = response.json()

        # Store in database for historical analysis
        await nosql.weather_data.insert_one({
            "date": datetime.now().isoformat(),
            "forecast": weather_data,
            "location": "New York"
        })

        return weather_data
    else:
        raise Exception(f"API request failed with status {response.status_code}")
```

## Additional Resources

- [HTTPX Documentation](https://www.python-httpx.org/)
- [Hishel Documentation](https://github.com/karpetrosyan/hishel)
- [HTTP Status Codes](https://httpstatuses.com/)
- [ACB Cache Adapter](../cache/README.md)
- [ACB Secret Adapter](../secret/README.md)
- [ACB Adapters Overview](../README.md)
