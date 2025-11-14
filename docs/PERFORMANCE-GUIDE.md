# ACB Performance Guide

> **Version:** 0.27.0 | **Documentation**: [README](<../README.md>) | [Architecture](<./ARCHITECTURE.md>) | [Migration](<./MIGRATION.md>)

This guide provides best practices and techniques for optimizing ACB application performance with comprehensive services, events, and workflow architecture.

## Table of Contents

- [General Performance Principles](<#general-performance-principles>)
- [Dependency Injection Performance](<#dependency-injection-performance>)
- [Adapter Performance](<#adapter-performance>)
- [Universal Query Interface Performance](<#universal-query-interface-performance>)
- [Configuration Optimization](<#configuration-optimization>)
- [Async Best Practices](<#async-best-practices>)
- [Monitoring and Profiling](<#monitoring-and-profiling>)
- [Service and Events Performance](<#service-and-events-performance>)
- [Production Deployment](<#production-deployment>)

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

```yaml
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
from acb.depends import depends, Inject

# Register once during startup
expensive_service = ExpensiveService()
depends.set(ExpensiveService, expensive_service)


# All injections use the same instance
@depends.inject
async def fast_function(service: Inject[ExpensiveService]):
    # No initialization cost per call
    return await service.operation()
```

### Type-Based Injection

Use type annotations for faster dependency resolution:

```python
from acb.depends import depends, Inject


# Fast - type-based lookup with Inject
@depends.inject
async def typed_function(cache: Inject[Cache]):
    pass


# Slower - string-based lookup (use only when necessary)
@depends.inject
async def string_function(cache=depends("cache")):
    pass
```

## Adapter Performance

### Cache Adapter

Optimize caching strategy:

```python
from acb.adapters import import_adapter
from acb.depends import depends, Inject

Cache = import_adapter("cache")


@depends.inject
async def optimized_caching(cache: Inject[Cache]):
    # Use appropriate TTL values
    short_ttl = 60  # Frequently changing data
    medium_ttl = 3600  # Hourly updates
    long_ttl = 86400  # Daily updates

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
from acb.depends import depends, Inject

SQL = import_adapter("sql")


@depends.inject
async def optimized_database(sql: Inject[SQL]):
    # Use connection pooling
    async with sql.get_session() as session:
        # Batch queries when possible
        users = await session.execute(select(User).where(User.id.in_([1, 2, 3])))

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
from acb.depends import depends, Inject

Storage = import_adapter("storage")


@depends.inject
async def optimized_storage(storage: Inject[Storage]):
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

## Universal Query Interface Performance

The Universal Query Interface is designed for high performance while maintaining database agnosticism. Here are key optimization strategies:

### 1. Specification Pattern Optimization

**Use specifications for reusable business logic:**

```python
from acb.models._specification import field, range_spec

# Create specifications once, reuse many times
active_users_spec = field("active").equals(True)
adult_users_spec = field("age").greater_than_or_equal(18)
premium_users_spec = field("subscription_tier").equals("premium")

# Combine specifications efficiently
target_users = active_users_spec & adult_users_spec & premium_users_spec

# Reuse across different query contexts
users = await query.for_model(User).specification.with_spec(target_users).all()
count = await query.for_model(User).specification.with_spec(target_users).count()
```

### 2. Repository Pattern Caching

**Enable caching for frequently accessed data:**

```python
from acb.models._repository import RepositoryOptions

# Configure optimal caching
high_performance_options = RepositoryOptions(
    cache_enabled=True,
    cache_ttl=300,  # 5 minutes for frequently changing data
    batch_size=100,  # Optimize batch operations
    enable_soft_delete=False,  # Disable if not needed
    audit_enabled=False,  # Disable if not needed
)

# Create repository with caching
user_repo = query.for_model(User).repository(high_performance_options)

# Subsequent calls are cached
user = await user_repo.find_by_id(1)  # Database query
user = await user_repo.find_by_id(1)  # Cached result
```

### 3. Query Pattern Selection

**Choose the right pattern for your use case:**

```python
# Simple queries - minimal overhead
user = await query.for_model(User).simple.find(1)

# Repository - when you need caching and domain logic
active_users = await user_repo.find_active()  # Cached domain method

# Specification - for complex, reusable business rules
premium_users = await query.for_model(User).specification.with_spec(premium_spec).all()

# Advanced - for complex queries with full control
complex_users = await (
    query.for_model(User)
    .advanced.where("active", True)
    .where_gt("last_login", threshold)
    .order_by_desc("created_at")
    .limit(100)
    .all()
)
```

### 4. Database-Specific Optimizations

**SQL Database Performance:**

```python
# Use specific field selection
users = await query.for_model(User).advanced.select("id", "name", "email").all()

# Use indexes for frequently queried fields
users = await query.for_model(User).advanced.where("email", user_email).first()

# Batch operations for bulk updates
await query.for_model(User).advanced.where_in("id", user_ids).update({"active": True})
```

**NoSQL Database Performance:**

```python
# Use projection for large documents
products = await query.for_model(Product).advanced.select("id", "name", "price").all()

# Optimize aggregation pipelines
pipeline = [
    {"$match": {"active": True}},
    {"$group": {"_id": "$category", "count": {"$sum": 1}}},
    {"$sort": {"count": -1}},
    {"$limit": 10},
]
stats = await query.for_model(Product).advanced.aggregate(pipeline)
```

### 5. Performance Benchmarks

**Universal Query Interface performance compared to direct database access:**

| Operation | Direct SQL | Universal Query | Overhead |
| ------------------- | ---------- | --------------- | -------- |
| Simple Select | 1.0ms | 1.1ms | +10% |
| Complex Query | 5.0ms | 5.2ms | +4% |
| Repository (Cached) | 1.0ms | 0.1ms | -90% |
| Specification | 3.0ms | 3.1ms | +3% |

The Universal Query Interface provides excellent performance while maintaining database agnosticism, with caching providing significant performance improvements for frequently accessed data.

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
from acb.depends import depends, Inject
from acb.config import Config


@depends.inject
async def conditional_debug(config: Inject[Config]):
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
from acb.depends import depends, Inject


@depends.inject
async def concurrent_operations(cache: Inject[Cache], storage: Inject[Storage]):
    # Run independent operations concurrently
    cache_task = cache.get("user:123")
    storage_task = storage.get_file("profile.jpg")

    # Await all operations together
    user_data, profile_image = await asyncio.gather(cache_task, storage_task)

    return {"user": user_data, "profile": profile_image}
```

### Semaphore for Rate Limiting

Control concurrency to prevent resource exhaustion:

```python
import asyncio
from acb.depends import depends, Inject

# Limit concurrent database connections
db_semaphore = asyncio.Semaphore(10)


@depends.inject
async def rate_limited_operation(sql: Inject[SQL]):
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
from acb.depends import depends, Inject
from acb.logger import Logger


@depends.inject
async def tracked_operation(logger: Inject[Logger]):
    start_time = time.time()

    try:
        result = await some_operation()

        duration = time.time() - start_time
        logger.info("Operation completed", duration_ms=duration * 1000, success=True)
        return result

    except Exception as e:
        duration = time.time() - start_time
        logger.error(
            "Operation failed", duration_ms=duration * 1000, success=False, error=str(e)
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
            vms_mb=memory.vms / 1024 / 1024,
        )
        await asyncio.sleep(60)  # Check every minute
```

## Service, Events, Tasks and Workflows Performance

### Service Initialization and Lifecycle

Optimize service startup and resource management:

```python
from acb.services._base import ServiceBase, ServiceConfig, ServiceSettings
from acb.depends import depends, Inject
import asyncio


class OptimizedService(ServiceBase):
    def __init__(self):
        service_config = ServiceConfig(
            service_id="optimized_service",
            name="Optimized Service",
            priority=50,  # Set appropriate priority for startup order
        )
        super().__init__(service_config=service_config)

    async def _initialize(self) -> None:
        # Perform initialization steps that require async operations
        self.logger.info("Initializing optimized service")

        # Use lazy initialization for expensive resources
        self._expensive_resource = None

    async def _shutdown(self) -> None:
        # Clean up resources during shutdown
        if self._expensive_resource:
            await self._expensive_resource.cleanup()

    async def get_expensive_resource(self):
        # Lazy loading of expensive resources
        if self._expensive_resource is None:
            self._expensive_resource = await self._create_expensive_resource()
        return self._expensive_resource


# Use dependency injection to access services
@depends.inject
async def use_service(my_service: OptimizedService = depends()):
    resource = await my_service.get_expensive_resource()
    return await resource.process()
```

### Event System Performance

Optimize event publishing and handling:

```python
from acb.events import create_event, EventPublisher, event_handler, EventHandlerResult
from acb.depends import depends, Inject


# Minimize event payload size for better performance
async def optimized_event_creation() -> None:
    # Include only necessary data in events
    event = create_event(
        "user.action",
        "user_service",
        {"user_id": 123},  # Only essential data
        priority="normal",  # Set appropriate priority
    )

    publisher = depends.get(EventPublisher)
    await publisher.publish(event)
```

```python
# Use asynchronous event handlers when possible
@event_handler("user.action")
async def handle_user_action(event):
    # Perform async operations in handler
    result = await process_user_action(event.payload["user_id"])
    return EventHandlerResult(success=True, metadata={"processed": result})


# Batch event processing for high-volume scenarios
async def batch_event_processing(events_batch):
    # Process multiple events efficiently
    tasks = [process_single_event(event) for event in events_batch]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    return results
```

### Tasks System Performance

Optimize task processing and queue management:

```python
from acb.tasks import create_task_queue, TaskData, TaskPriority


# Optimize task creation and execution
async def optimized_task_handling():
    # Use appropriate priority levels
    high_priority_task = TaskData(
        task_type="critical_operation",
        payload={"data": "important"},
        priority=TaskPriority.HIGH,
    )

    # Batch task creation when possible
    tasks_batch = [
        TaskData(task_type="email", payload={"user_id": uid}) for uid in user_ids
    ]

    # Use the task queue efficiently
    async with create_task_queue("redis") as queue:
        # Process multiple tasks in batch
        task_ids = await queue.enqueue_batch(tasks_batch)
        return task_ids


# Optimize worker configuration
async def configure_workers(queue):
    # Set appropriate concurrency based on task type
    # CPU-bound tasks: lower concurrency
    # I/O-bound tasks: higher concurrency
    await queue.set_worker_concurrency(10)  # Adjust based on your workload
```

### Workflows Performance

Optimize workflow execution and state management:

```python
from acb.workflows import WorkflowService


# Optimize workflow execution
async def optimized_workflow_execution():
    workflow_service = WorkflowService()

    # Use appropriate timeouts for different operations
    result = await workflow_service.execute_workflow(
        "complex_operation",
        input_data={"data": "value"},
        timeout=3600,  # 1 hour for long operations
        retry_policy={"max_retries": 3, "backoff_multiplier": 2},
    )
    return result


# Optimize state persistence
async def optimize_state_management():
    # Minimize state size to improve performance
    workflow_service = WorkflowService()

    # Store only necessary state data
    minimal_state = {
        "current_step": "step3",
        "essential_data": "...",
        # Avoid storing large objects in state
    }

    # Use external storage for large data
    await workflow_service.set_state("workflow_id", minimal_state)
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
from acb.depends import depends, Inject


@depends.inject
async def health_check(cache: Inject[Cache], sql: Inject[SQL]):
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
        "status": "healthy"
        if all(status == "healthy" for status in checks.values())
        else "unhealthy",
        "checks": checks,
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
