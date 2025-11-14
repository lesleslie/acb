> **ACB Documentation**: [Main](<../../../README.md>) | [Core Systems](<../../README.md>) | [Actions](<../../actions/README.md>) | [Adapters](<../README.md>) | [Cache](<./README.md>)

# Cache Adapter

The Cache adapter provides a standardized interface for data caching in ACB applications, with support for both in-memory and Redis-based implementations.

## Table of Contents

- [Overview](<#overview>)
- [Available Implementations](<#available-implementations>)
- [Installation](<#installation>)
- [Configuration](<#configuration>)
- [Basic Usage](<#basic-usage>)
- [Advanced Usage](<#advanced-usage>)
  - [Caching Complex Data Types](<#caching-complex-data-types>)
  - [Multi-Key Operations](<#multi-key-operations>)
  - [Cache Decorators](<#cache-decorators>)
  - [Working with Namespaces](<#working-with-namespaces>)
- [Troubleshooting](<#troubleshooting>)
- [Implementation Details](<#implementation-details>)
- [Performance Considerations](<#performance-considerations>)
- [Related Adapters](<#related-adapters>)
- [Additional Resources](<#additional-resources>)

## Overview

Caching is a crucial component of high-performance applications. The ACB Cache adapter offers:

- Fast, asynchronous caching operations
- Multiple backend implementations
- Serialization options for complex data types
- Configurable time-to-live (TTL) settings
- Support for secure caching of sensitive data

## Available Implementations

| Implementation | Description | Best For | Interface |
| -------------- | -------------------------------------------------- | ----------------------------------------------- | --------------------------------- |
| **Memory** | In-memory caching using aiocache SimpleMemoryCache | Development, small applications, testing | Full aiocache BaseCache interface |
| **Redis** | Distributed caching using Redis with aiocache | Production, distributed systems, shared caching | Full aiocache BaseCache interface |

## Installation

```bash
# Install cache support (memory + Redis)
uv add --group cache

# Or include it with other dependencies
uv add --group cache --group sql --group storage
```

## Configuration

### Settings

Configure the cache adapter in your `settings/adapters.yaml` file:

```yaml
# Use Redis implementation
cache: redis

# Or use Memory implementation
cache: memory

# Or disable caching
cache: null
```

### Cache Settings

The cache adapter settings can be customized in your `settings/app.yaml` file:

```yaml
cache:
  # Default time-to-live for cached items (seconds)
  default_ttl: 86400  # 24 hours

  # TTL for query results
  query_ttl: 600  # 10 minutes

  # TTL for responses (shorter in development)
  response_ttl: 3600  # 1 hour

  # TTL for templates
  template_ttl: 86400  # 24 hours
```

## Basic Usage

```python
from acb.depends import depends, Inject
from acb.adapters import import_adapter

# Import the cache adapter (automatically selects the one enabled in config)
Cache = import_adapter("cache")

# Get the cache instance via dependency injection
cache = depends.get(Cache)

# Set a value in the cache
await cache.set("my_key", "my_value", ttl=300)  # Cache for 5 minutes

# Get a value from the cache
value = await cache.get("my_key")

# Delete a value from the cache
await cache.delete("my_key")

# Check if a key exists
exists = await cache.exists("my_key")
```

## Advanced Usage

### Caching Complex Data Types

The cache adapter automatically handles serialization of complex data types:

```python
import datetime

# Cache a dictionary
user_data = {
    "id": 1234,
    "name": "John Doe",
    "roles": ["admin", "editor"],
    "active": True,
    "last_login": datetime.datetime.now(),
}

# The cache adapter will handle serialization automatically
await cache.set("user:1234", user_data)

# Retrieve it later - it will be deserialized automatically
cached_user = await cache.get("user:1234")
```

### Multi-Key Operations

Both memory and Redis cache implementations support efficient multi-key operations through the aiocache interface:

```python
# Set multiple keys at once using multi_set
pairs = [
    ("product:1", {"name": "Widget", "price": 19.99}),
    ("product:2", {"name": "Gadget", "price": 24.99}),
    ("product:3", {"name": "Doohickey", "price": 14.99}),
]
await cache.multi_set(pairs, ttl=300)

# Get multiple keys at once - returns results in the same order as keys
products = await cache.multi_get(["product:1", "product:2", "product:3"])

# Additional aiocache operations
# Add a value only if the key doesn't exist
added = await cache.add("unique:key", "value", ttl=60)

# Increment a numeric value atomically
new_value = await cache.increment("counter:visits", delta=1)

# Set expiration on an existing key
await cache.expire("existing:key", ttl=120)
```

### Cache Decorators

Use cache decorators to automatically cache function results:

```python
from acb.depends import depends, Inject
from acb.adapters import import_adapter

Cache = import_adapter("cache")
cache = depends.get(Cache)


# Cache the result of an expensive operation
@cache.cached(ttl=300)  # Cache results for 5 minutes
async def get_user_data(user_id: int):
    # This function will only be called when the cache doesn't have the result
    # The key will be based on the function name and arguments
    return await database.fetch_user(user_id)


# Using the cached function is the same as using the original function
user = await get_user_data(123)  # First call executes the function
same_user = await get_user_data(123)  # Second call returns cached result
```

### Working with Namespaces

Organize your cache keys with namespaces:

```python
# Create a namespaced cache instance
user_cache = cache.namespace("users")

# Keys will be prefixed with the namespace
await user_cache.set("1234", user_data)  # Actual key is "users:1234"

# Get data from the namespaced cache
user = await user_cache.get("1234")  # Looks for key "users:1234"

# Clear all keys in a namespace
await user_cache.clear()  # Removes all keys with prefix "users:"
```

## Troubleshooting

### Common Issues

1. **Redis Connection Error**

   - **Problem**: `ConnectionError: Error connecting to Redis server`
   - **Solution**:
     - Ensure Redis is running: `redis-cli ping` should return `PONG`
     - Check connection settings in your configuration
     - Verify network access if Redis is on a different server

1. **Serialization Error**

   - **Problem**: `SerializationError: Object not serializable`
   - **Solution**:
     - Ensure all cached objects are serializable
     - Custom classes should implement `__dict__` or appropriate serialization methods
     - Consider converting complex objects to dictionaries before caching

1. **Cache Miss When Expected Hit**

   - **Problem**: Cache returns `None` when you expect a value
   - **Solution**:
     - Check TTL settings - the item may have expired
     - Verify the key being used is correct, including namespaces
     - Check for clear operations that might have removed the item

1. **Memory Implementation Performance**

   - **Problem**: Memory cache performance degrades with large datasets
   - **Solution**:
     - Switch to Redis implementation for production workloads
     - Implement cache size limits in configuration
     - Use more granular TTL values to expire less-used items

## Implementation Details

### Modern Architecture

The cache adapter uses the aiocache library interface for both memory and Redis implementations. This provides:

- **Unified Interface**: Both implementations use the same aiocache BaseCache abstract methods
- **Consistent Behavior**: Memory and Redis caches behave identically from an API perspective
- **Better Performance**: Optimized serialization with PickleSerializer
- **Full Feature Support**: All aiocache operations are supported

### Core Interface Methods

The Cache adapter now implements the full aiocache BaseCache interface:

```python
# Core aiocache methods implemented by both memory and Redis adapters
class Cache(BaseCache):
    # Basic operations
    async def get(self, key: str, encoding: str = "utf-8") -> t.Any: ...
    async def set(self, key: str, value: t.Any, ttl: int | None = None) -> None: ...
    async def delete(self, key: str) -> bool: ...
    async def exists(self, key: str) -> bool: ...
    async def clear(self, namespace: str | None = None) -> bool: ...

    # Advanced operations
    async def multi_get(
        self, keys: list[str], encoding: str = "utf-8"
    ) -> list[t.Any]: ...
    async def multi_set(
        self, pairs: list[tuple[str, t.Any]], ttl: int | None = None
    ) -> None: ...
    async def add(self, key: str, value: t.Any, ttl: int | None = None) -> bool: ...
    async def increment(self, key: str, delta: int = 1) -> int: ...
    async def expire(self, key: str, ttl: int) -> bool: ...
```

### Memory Cache Implementation

The memory cache adapter uses aiocache's `SimpleMemoryCache` with these features:

- **PickleSerializer**: Handles complex Python objects automatically
- **Namespace Support**: Automatic key prefixing with application name
- **Zero Timeout**: Optimized for local access without network delays
- **Thread-Safe**: Safe for concurrent access within the same process

### Redis Cache Implementation

The Redis cache adapter leverages aiocache's Redis backend with:

- **Connection Pooling**: Efficient Redis connection management
- **Distributed Access**: Shared cache across multiple application instances
- **Persistence Options**: Configurable Redis persistence settings
- **Network Optimized**: Batch operations for better network efficiency

## Performance Considerations

When working with the Cache adapter, keep these performance considerations in mind:

1. **Key Length**: Shorter keys perform better, especially in Redis
1. **Data Size**: Large objects (>1MB) may impact performance; consider chunking
1. **TTL Strategy**: Use appropriate TTL values based on data volatility
1. **Implementation Choice**:
   - **Memory**: Fastest for small applications but doesn't scale across services
   - **Redis**: Better for distributed systems but has network overhead

For high-traffic applications, consider these performance patterns:

```python
# Pattern: Cache aside
async def get_item(item_id):
    # Try cache first
    cached = await cache.get(f"item:{item_id}")
    if cached:
        return cached

    # Cache miss - get from database
    item = await database.get_item(item_id)

    # Store in cache for next time
    await cache.set(f"item:{item_id}", item, ttl=3600)

    return item
```

### Performance Comparison

| Implementation | Read Performance | Write Performance | Multi-Instance Support | Memory Usage |
| -------------- | ----------------- | ----------------- | ---------------------- | ------------------------- |
| **Memory** | Very Fast (0.1ms) | Very Fast (0.1ms) | No | High (all cached objects) |
| **Redis** | Fast (1-2ms) | Fast (1-2ms) | Yes | Low (on app server) |

## Related Adapters

The Cache adapter works well with other ACB adapters:

- [**SQL Adapter**](<../sql/README.md>): Cache database query results to reduce database load
- [**NoSQL Adapter**](<../nosql/README.md>): Cache document results for faster access
- [**Requests Adapter**](<../requests/README.md>): Cache API responses to reduce external calls
- [**Storage Adapter**](<../storage/README.md>): Cache file metadata to avoid storage operations

Common integration patterns:

```python
from acb.depends import depends, Inject
from acb.config import Config


# Caching database query results
@depends.inject
async def get_users_by_role(role: str, config: Inject[Config]):
    @cache.cached(ttl=config.cache.query_ttl)
    async def _get_users_by_role():
        async with sql.get_session() as session:
            statement = select(User).where(User.role == role)
            result = await session.execute(statement)
            return result.scalars().all()

    return await _get_users_by_role()


# Caching API responses
@depends.inject
async def get_weather(city: str, config: Inject[Config]):
    @cache.cached(ttl=config.cache.response_ttl)
    async def _get_weather():
        response = await requests.get(f"https://api.weather.com/{city}")
        return response.json()

    return await _get_weather()
```

## Additional Resources

- [Redis Documentation](https://redis.io/documentation)
- [Redis Caching Patterns](https://redis.com/solutions/use-cases/caching/)
- [Caching Best Practices](https://aws.amazon.com/caching/best-practices/)
- [ACB SQL Adapter](<../sql/README.md>)
- [ACB NoSQL Adapter](<../nosql/README.md>)
- [ACB Adapters Overview](<../README.md>)
