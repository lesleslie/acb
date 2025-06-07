# ACB Performance Guide

> **ACB Documentation**: [Main](../README.md) | [Core Systems](../acb/README.md) | [Actions](../acb/actions/README.md) | [Adapters](../acb/adapters/README.md)

This guide provides best practices and techniques for optimizing ACB application performance.

## Table of Contents

- [General Performance Principles](#general-performance-principles)
- [Dependency Injection Performance](#dependency-injection-performance)
- [Adapter Performance](#adapter-performance)
- [Configuration Optimization](#configuration-optimization)
- [Async Best Practices](#async-best-practices)
- [Monitoring and Profiling](#monitoring-and-profiling)
- [Production Deployment](#production-deployment)

## General Performance Principles

### 1. Minimize Import Time

Avoid expensive operations during module import:

```python
# Slow - executed at import time
expensive_data = compute_expensive_data()

# Fast - computed when needed
@cached_property
def expensive_data(self):
    return compute_expensive_data()
```

### 2. Use Lazy Loading

Initialize expensive resources only when needed:

```python
from acb.depends import depends

class ExpensiveService:
    def __init__(self):
        self._client = None

    async def _ensure_client(self):
        if self._client is None:
            self._client = await create_expensive_client()
        return self._client

    async def operation(self):
        client = await self._ensure_client()
        return await client.do_work()
```

### 3. Connection Pooling

Use connection pools for database and external service connections:

```python
# SQL adapter automatically uses connection pooling
# Configure pool size in settings
sql:
  pool_size: 20
  max_overflow: 30
  pool_timeout: 30
```

## Dependency Injection Performance

### Singleton Pattern

Register expensive services as singletons:

```python
from acb.depends import depends

# Register once during startup
expensive_service = ExpensiveService()
depends.set(ExpensiveService, expensive_service)

# All injections use the same instance
@depends.inject
async def fast_function(service: ExpensiveService = depends()):
    # No initialization cost per call
    return await service.operation()
```

### Type-Based Injection

Use type annotations for faster dependency resolution:

```python
# Fast - type-based lookup
@depends.inject
async def typed_function(cache: Cache = depends()):
    pass

# Slower - string-based lookup
@depends.inject
async def string_function(cache=depends("cache")):
    pass
```

## Adapter Performance

### Cache Adapter

Optimize caching strategy:

```python
from acb.adapters import import_adapter
from acb.depends import depends

Cache = import_adapter("cache")

@depends.inject
async def optimized_caching(cache: Cache = depends()):
    # Use appropriate TTL values
    short_ttl = 60      # Frequently changing data
    medium_ttl = 3600   # Hourly updates
    long_ttl = 86400    # Daily updates

    # Batch operations when possible
    data = await cache.multi_get(["key1", "key2", "key3"])

    # Use namespaces for organization and bulk operations
    user_cache = cache.namespace("users")
    await user_cache.set("123", user_data, ttl=medium_ttl)
```

### SQL Adapter

Optimize database operations:

```python
from acb.adapters import import_adapter

SQL = import_adapter("sql")

@depends.inject
async def optimized_database(sql: SQL = depends()):
    # Use connection pooling
    async with sql.get_session() as session:
        # Batch queries when possible
        users = await session.execute(
            select(User).where(User.id.in_([1, 2, 3]))
        )

        # Use eager loading to avoid N+1 queries
        users_with_orders = await session.execute(
            select(User).options(selectinload(User.orders))
        )

        # Use bulk operations
        await session.execute(
            update(User).where(User.active == False).values(archived=True)
        )
```

### Storage Adapter

Optimize file operations:

```python
from acb.adapters import import_adapter

Storage = import_adapter("storage")

@depends.inject
async def optimized_storage(storage: Storage = depends()):
    # Stream large files instead of loading into memory
    async for chunk in storage.stream_file("large_file.bin"):
        await process_chunk(chunk)

    # Use batch operations for multiple files
    files = await storage.list_files("uploads/")
    metadata = await storage.get_metadata_batch(files)

    # Implement client-side caching for metadata
    metadata_cache = {}
    for file_path in files:
        if file_path not in metadata_cache:
            metadata_cache[file_path] = await storage.get_metadata(file_path)
```

## Configuration Optimization

### Production Settings

Optimize configuration for production:

```yaml
# settings/app.yml (production)
cache:
  default_ttl: 3600
  query_ttl: 600
  response_ttl: 1800

debug:
  enabled: false
  production: true
  log_level: "INFO"

sql:
  pool_size: 20
  max_overflow: 30
  pool_recycle: 3600
  echo: false  # Disable SQL logging in production
```

### Disable Debug Features

Remove debug overhead in production:

```python
from acb.depends import depends
from acb.config import Config

@depends.inject
async def conditional_debug(config: Config = depends()):
    if config.debug.enabled:
        # Expensive debug operations only in debug mode
        debug_info = await collect_debug_info()
        logger.debug("Debug info", extra=debug_info)
```

## Async Best Practices

### Concurrency Optimization

Use async patterns effectively:

```python
import asyncio
from acb.depends import depends

@depends.inject
async def concurrent_operations(
    cache: Cache = depends(),
    storage: Storage = depends()
):
    # Run independent operations concurrently
    cache_task = cache.get("user:123")
    storage_task = storage.get_file("profile.jpg")

    # Await all operations together
    user_data, profile_image = await asyncio.gather(
        cache_task,
        storage_task
    )

    return {"user": user_data, "profile": profile_image}
```

### Semaphore for Rate Limiting

Control concurrency to prevent resource exhaustion:

```python
import asyncio

# Limit concurrent database connections
db_semaphore = asyncio.Semaphore(10)

@depends.inject
async def rate_limited_operation(sql: SQL = depends()):
    async with db_semaphore:
        # Only 10 concurrent database operations
        async with sql.get_session() as session:
            return await session.execute(expensive_query)
```

### Background Tasks

Use background tasks for non-critical operations:

```python
import asyncio
from typing import Any

background_tasks: set[asyncio.Task[Any]] = set()

async def schedule_background_task(coro):
    """Schedule a coroutine to run in the background."""
    task = asyncio.create_task(coro)
    background_tasks.add(task)
    task.add_done_callback(background_tasks.discard)

# Usage
await schedule_background_task(update_cache_in_background())
```

## Monitoring and Profiling

### Performance Timing

Use ACB's built-in timing decorator:

```python
from acb.debug import timeit

@timeit
async def performance_critical_function():
    # Function execution time will be logged
    await expensive_operation()
```

### Custom Metrics

Implement custom performance metrics:

```python
import time
from acb.depends import depends
from acb.logger import Logger

@depends.inject
async def tracked_operation(logger: Logger = depends()):
    start_time = time.time()

    try:
        result = await some_operation()

        duration = time.time() - start_time
        logger.info(
            "Operation completed",
            duration_ms=duration * 1000,
            success=True
        )
        return result

    except Exception as e:
        duration = time.time() - start_time
        logger.error(
            "Operation failed",
            duration_ms=duration * 1000,
            success=False,
            error=str(e)
        )
        raise
```

### Memory Monitoring

Monitor memory usage:

```python
import psutil
import asyncio

async def memory_monitor():
    """Background task to monitor memory usage."""
    while True:
        memory = psutil.Process().memory_info()
        logger.info(
            "Memory usage",
            rss_mb=memory.rss / 1024 / 1024,
            vms_mb=memory.vms / 1024 / 1024
        )
        await asyncio.sleep(60)  # Check every minute
```

## Production Deployment

### Environment Configuration

Optimize for production environment:

```bash
# Environment variables
export PYTHONOPTIMIZE=1
export PYTHONDONTWRITEBYTECODE=1
export ACB_ENV=production
```

### Process Management

Use proper process management:

```python
# main.py
import asyncio
import signal
from acb.depends import depends

class Application:
    def __init__(self):
        self.running = True

    async def shutdown(self):
        """Graceful shutdown handler."""
        self.running = False
        # Cleanup resources
        await self.cleanup_connections()

    async def cleanup_connections(self):
        """Clean up database connections and other resources."""
        # Close database pools
        sql = depends.get("sql")
        await sql.close_all_connections()

        # Close cache connections
        cache = depends.get("cache")
        await cache.close()

async def main():
    app = Application()

    # Set up signal handlers
    loop = asyncio.get_event_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, lambda: asyncio.create_task(app.shutdown()))

    try:
        while app.running:
            await asyncio.sleep(0.1)
    finally:
        await app.cleanup_connections()

if __name__ == "__main__":
    asyncio.run(main())
```

### Resource Limits

Configure appropriate resource limits:

```yaml
# docker-compose.yml
services:
  app:
    deploy:
      resources:
        limits:
          memory: 512M
          cpus: '0.5'
        reservations:
          memory: 256M
          cpus: '0.25'
```

### Health Checks

Implement health check endpoints:

```python
from acb.depends import depends

@depends.inject
async def health_check(
    cache: Cache = depends(),
    sql: SQL = depends()
):
    """Check health of all critical services."""
    checks = {}

    # Check cache
    try:
        await cache.set("health", "ok", ttl=10)
        await cache.get("health")
        checks["cache"] = "healthy"
    except Exception as e:
        checks["cache"] = f"unhealthy: {e}"

    # Check database
    try:
        async with sql.get_session() as session:
            await session.execute("SELECT 1")
        checks["database"] = "healthy"
    except Exception as e:
        checks["database"] = f"unhealthy: {e}"

    return {
        "status": "healthy" if all(
            status == "healthy" for status in checks.values()
        ) else "unhealthy",
        "checks": checks
    }
```

## Performance Checklist

- [ ] Use connection pooling for databases
- [ ] Implement appropriate caching strategies
- [ ] Use lazy loading for expensive resources
- [ ] Enable async operations where possible
- [ ] Monitor memory usage and optimize TTL values
- [ ] Use batch operations for multiple items
- [ ] Disable debug features in production
- [ ] Implement proper error handling and logging
- [ ] Use background tasks for non-critical operations
- [ ] Set up health checks and monitoring
