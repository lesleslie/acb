> **ACB Documentation**: [Main](../../../README.md) | [Core Systems](../../README.md) | [Actions](../../actions/README.md) | [Adapters](../README.md) | [Cache](./README.md)

# Cache Adapter

The Cache adapter provides a standardized interface for data caching in ACB applications, with support for in-memory and Redis implementations.

## Table of Contents

- [Overview](#overview)
- [Available Implementations](#available-implementations)
- [Installation](#installation)
- [Configuration](#configuration)
  - [Settings](#settings)
  - [Detailed Settings](#detailed-settings)
- [Basic Usage](#basic-usage)
- [Advanced Usage](#advanced-usage)
  - [Working with Complex Data Types](#working-with-complex-data-types)
  - [Cache Patterns](#cache-patterns)
  - [Cache Invalidation](#cache-invalidation)
- [Troubleshooting](#troubleshooting)
- [Implementation Details](#implementation-details)
- [Related Adapters](#related-adapters)
- [Additional Resources](#additional-resources)

## Overview

The ACB Cache adapter offers:

- Fast data retrieval with configurable time-to-live (TTL)
- Support for multiple cache backends
- Automatic serialization and deserialization of complex data types
- Asynchronous operations for non-blocking performance
- Cache namespacing to avoid key collisions
- Atomic operations for distributed caching

## Available Implementations

| Implementation | Description | Best For |
|----------------|-------------|----------|
| **Memory** | In-memory cache using Python dictionaries | Development, testing, single-instance applications |
| **Redis** | Distributed cache using Redis | Production, multi-instance applications, shared caching |

## Installation

```bash
# Install with Redis cache support
pdm add "acb[redis]"

# Or include it with other dependencies
pdm add "acb[redis,sql,storage]"
```

## Configuration

### Settings

Configure the Cache adapter in your `settings/adapters.yml` file:

```yaml
# Use Memory implementation
cache: memory

# Or use Redis implementation
cache: redis

# Or disable caching
cache: null
```

### Detailed Settings

The Cache adapter settings can be customized in your `settings/app.yml` file:

```yaml
cache:
  # Default time-to-live in seconds (0 = no expiration)
  default_ttl: 3600

  # Namespace prefix for all cache keys
  namespace: "myapp"

  # Redis-specific settings
  redis:
    host: "localhost"
    port: 6379
    db: 0
    password: null
    socket_timeout: 5
    socket_connect_timeout: 5

  # Memory-specific settings
  memory:
    max_size: 1000  # Maximum number of items to store
    eviction_policy: "lru"  # Least recently used
```

## Basic Usage

```python
from acb.depends import depends
from acb.adapters import import_adapter

# Import the cache adapter (automatically selects the one enabled in config)
Cache = import_adapter("cache")

# Get the cache instance via dependency injection
cache = depends.get(Cache)

# Store a value in the cache with a TTL of 60 seconds
await cache.set("my_key", "my_value", ttl=60)

# Retrieve a value from the cache
value = await cache.get("my_key")
print(value)  # "my_value"

# Check if a key exists
exists = await cache.exists("my_key")
print(exists)  # True

# Delete a key
await cache.delete("my_key")
```

## Advanced Usage

### Working with Complex Data Types

```python
from acb.depends import depends
from acb.adapters import import_adapter
from datetime import datetime

Cache = import_adapter("cache")
cache = depends.get(Cache)

# Store complex data types (automatically serialized)
user_data = {
    "id": 1001,
    "name": "John Doe",
    "email": "john@example.com",
    "active": True,
    "last_login": datetime.now(),
    "permissions": ["read", "write", "admin"]
}

# Store in cache
await cache.set("user:1001", user_data)

# Retrieve and use
retrieved_user = await cache.get("user:1001")
print(f"User: {retrieved_user['name']}, Email: {retrieved_user['email']}")
```

### Cache Patterns

```python
# Cache-aside pattern
async def get_user(user_id):
    # Try to get from cache first
    cache_key = f"user:{user_id}"
    user = await cache.get(cache_key)

    if user is None:
        # Cache miss - get from database
        user = await database.get_user(user_id)

        # Store in cache for next time
        if user:
            await cache.set(cache_key, user, ttl=3600)  # Cache for 1 hour

    return user

# Bulk operations
keys = [f"product:{i}" for i in range(1, 6)]
products = await cache.multi_get(keys)

# Set multiple values at once
items = {
    "cart:1001:item:1": {"product_id": 501, "quantity": 2},
    "cart:1001:item:2": {"product_id": 502, "quantity": 1},
    "cart:1001:count": 2
}
await cache.multi_set(items, ttl=1800)  # 30 minutes
```

### Cache Invalidation

```python
# Increment a counter
views = await cache.incr("page:views")
print(f"Page views: {views}")

# Decrement a counter
remaining = await cache.decr("rate:limit:user:1001", 1)
print(f"Remaining requests: {remaining}")

# Set expiration on existing key
await cache.expire("session:token", 1800)  # 30 minutes

# Delete keys by pattern (Redis implementation only)
await cache.delete_pattern("user:1001:*")

# Clear entire cache (use with caution!)
await cache.clear()
```

## Troubleshooting

### Common Issues

1. **Connection Errors with Redis**
   - **Problem**: `ConnectionError: Error connecting to Redis on localhost:6379`
   - **Solution**: Verify Redis is running and check connection settings in your configuration

2. **Serialization Errors**
   - **Problem**: `SerializationError: Cannot serialize object of type <class 'MyCustomClass'>`
   - **Solution**: Ensure objects being cached are serializable (use dataclasses, Pydantic models, or implement `__dict__` method)

3. **Cache Misses**
   - **Problem**: Values not found in cache when expected
   - **Solution**: Check TTL settings, verify keys are consistent, and ensure cache isn't being cleared unexpectedly

4. **Memory Issues**
   - **Problem**: `MemoryError` or high memory usage with Memory implementation
   - **Solution**: Configure `max_size` setting or switch to Redis implementation for large datasets

## Implementation Details

The Cache adapter implements these core methods:

```python
class CacheBase:
    async def get(self, key: str) -> Any: ...
    async def set(self, key: str, value: Any, ttl: int = None) -> bool: ...
    async def delete(self, key: str) -> bool: ...
    async def exists(self, key: str) -> bool: ...
    async def incr(self, key: str, amount: int = 1) -> int: ...
    async def decr(self, key: str, amount: int = 1) -> int: ...
    async def expire(self, key: str, ttl: int) -> bool: ...
    async def multi_get(self, keys: list[str]) -> dict[str, Any]: ...
    async def multi_set(self, mapping: dict[str, Any], ttl: int = None) -> bool: ...
    async def clear(self) -> bool: ...
    # Redis-specific methods
    async def delete_pattern(self, pattern: str) -> int: ...  # Redis only
```

## Related Adapters

- [**Storage Adapter**](../storage/README.md): Use with Cache for storing file metadata
- [**SQL Adapter**](../sql/README.md): Cache database query results for improved performance
- [**NoSQL Adapter**](../nosql/README.md): Cache document queries from NoSQL databases

## Additional Resources

- [Redis Documentation](https://redis.io/documentation)
- [Caching Patterns](https://codeahoy.com/2017/08/11/caching-strategies-and-how-to-choose-the-right-one/)
- [Cache Invalidation Strategies](https://www.sobyte.net/post/2022-01/cache-invalidation-strategies/)
- [ACB Adapters Overview](../README.md)
- [ACB Configuration Guide](../../README.md)
