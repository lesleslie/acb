# ACB Migration Guide

This guide helps you upgrade between ACB versions, detailing breaking changes and upgrade paths.

## Table of Contents

- [Version 0.19.1+ (Simplified Architecture)](#version-0191-simplified-architecture)
- [Version 0.16.17+ (Performance Optimizations)](#version-01617-performance-optimizations)
- [General Migration Best Practices](#general-migration-best-practices)
- [Troubleshooting](#troubleshooting)

## Version 0.19.1+ (Simplified Architecture)

### Overview

Version 0.19.1 represents a **major architectural simplification**, removing complex enterprise features to focus on ACB's core mission: providing clean, reliable adapter interfaces for external systems.

### Removed Features (v0.19.1)

The following enterprise features were temporarily removed in v0.19.1 and were
reintroduced in subsequent releases:

#### ❌ Services Layer (temporarily removed in 0.19.1)

```python
# REMOVED in v0.19.1 - No longer available
from acb.services import ServiceBase, register_service


class UserService(ServiceBase):  # ❌ ServiceBase removed
    pass
```

**Migration Note:** If you are targeting exactly 0.19.1, implement service logic
directly in your application and access adapters via DI. For versions >= 0.20,
use the reintroduced Services layer shown below.

### Reintroduced Features (after 0.19.1)

The following features are available again in current versions:

#### ✅ Services Layer

```python
# AVAILABLE - Reintroduced after v0.19.1
from acb.services import ServiceBase, ServiceConfig, ServiceSettings


class UserService(ServiceBase):  # ✅ ServiceBase available again
    async def _initialize(self) -> None:
        # Service initialization logic
        pass

    async def _shutdown(self) -> None:
        # Service shutdown logic
        pass

    async def _health_check(self) -> dict:
        # Custom health check logic
        return {"status": "healthy"}
```

The Services layer now provides standardized patterns for building long-running, stateful components with lifecycle management, health checking, metrics collection, and resource cleanup capabilities.

#### ✅ Events System

```python
# AVAILABLE - Reintroduced after v0.19.1
from acb.events import EventPublisher, EventSubscriber, create_event

# Create and publish events
event = create_event("user.created", "user_service", {"user_id": 123})
publisher = EventPublisher()  # ✅ Events available again
await publisher.publish(event)
```

#### ✅ Tasks System

```python
# AVAILABLE - Reintroduced after v0.19.1
from acb.tasks import create_task_queue, TaskData

# Create and process background tasks
async with create_task_queue("memory") as queue:
    task = TaskData(task_type="email_task", payload={"email": "user@example.com"})
    task_id = await queue.enqueue(task)  # ✅ Tasks available again
```

#### ✅ Workflows

```python
# AVAILABLE - Reintroduced after v0.19.1
from acb.workflows import WorkflowService

workflow_service = WorkflowService()
# Define and execute workflows using ACB's workflow patterns
```

The Services, Events, Tasks, and Workflows systems have been redesigned with better integration with the core infrastructure, providing lifecycle management, health monitoring, and dependency injection capabilities.

#### ❌ Complex Health Checking

```python
# REMOVED - Simplified in v0.19.1
from acb.health import HealthChecker  # ❌ No longer available
```

**Migration Path:**

- Implement simple health checks in your application
- Use adapter-specific health checks if needed

#### ❌ Advanced Retry Mechanisms

```python
# REMOVED - Simplified in v0.19.1
from acb.retry import retry_with_circuit_breaker  # ❌ No longer available
```

**Migration Path:**

- Use `tenacity` library for retries
- Implement simple retry logic if needed

### Simplified Features

#### ✅ Basic Resource Cleanup

```python
# BEFORE (v0.19.0 and earlier)
from acb.health import HealthChecker
from acb.retry import CircuitBreaker

# Complex enterprise patterns

# AFTER (v0.19.1+)
from acb.cleanup import CleanupMixin


class SimpleAdapter(CleanupMixin):
    def __init__(self):
        super().__init__()
        self._client = None

    async def _create_client(self):
        client = SomeClient()
        self.register_resource(client)  # Simple cleanup registration
        return client
```

#### ✅ Essential SSL/TLS Configuration

```python
# SSL configuration simplified but still available
from acb.ssl_config import SSLConfig

ssl_config = SSLConfig()
# Basic SSL support where needed
```

#### ✅ Simple Configuration Hot-Reloading

```python
# BEFORE (v0.19.0 and earlier)
from acb.config import ConfigWatcher  # Complex system

# AFTER (v0.19.1+)
from acb.config import Config, enable_config_hot_reload

config = Config()
hot_reload = await enable_config_hot_reload(config, check_interval=5.0)

# Simple, reliable configuration monitoring
await hot_reload.stop()
```

### Migration Checklist

If migrating to exactly v0.19.1:

- [ ] Remove service/event/task/workflow dependencies
- [ ] Replace events/queues with project‑level implementations
- [ ] Simplify health and retry logic

If migrating to v0.20+ (current):

- [ ] Adopt reintroduced Services/Events/Tasks/Workflows
- [ ] Use `CleanupMixin` for resource cleanup
- [ ] Validate health checks with `acb.monitoring.*`
- [ ] Run full quality workflow: `python -m crackerjack`

### Code Examples

#### Before (v0.19.0)

```python
from acb.services import ServiceBase
from acb.events import EventPublisher
from acb.queues import Queue


class UserService(ServiceBase):
    async def create_user(self, data: dict):
        user = await self.repository.create(User(**data))
        await self.events.emit("user.created", user_id=user.id)
        await self.queue.enqueue("send_welcome_email", user_id=user.id)
        return user
```

#### After (v0.19.1 - Temporarily Removed)

```python
from acb.depends import depends, Inject
from acb.adapters import import_adapter

Cache = import_adapter("cache")
SQL = import_adapter("sql")


@depends.inject
async def create_user(data: dict, cache: Inject[Cache], sql: Inject[SQL]):
    # Direct adapter usage
    async with sql.get_session() as session:
        user = User(**data)
        session.add(user)
        await session.commit()

    # Cache the user
    await cache.set(f"user:{user.id}", user, ttl=3600)

    # Use external task queue or framework events if needed
    # await send_welcome_email(user.id)  # Direct call or external queue

    return user
```

#### After (v0.20.0+ - Services Reintroduced)

```python
from acb.services import ServiceBase, ServiceConfig, ServiceSettings
from acb.depends import depends, Inject
from acb.adapters import import_adapter

Cache = import_adapter("cache")
SQL = import_adapter("sql")


class UserService(ServiceBase):
    def __init__(self):
        service_config = ServiceConfig(
            service_id="user_service",
            name="User Service",
            description="Manages user creation and operations",
        )
        super().__init__(service_config=service_config)

    async def create_user(
        self, data: dict, cache: Inject[Cache] = depends(), sql: Inject[SQL] = depends()
    ):
        async with sql.get_session() as session:
            user = User(**data)
            session.add(user)
            await session.commit()

        # Cache the user
        await cache.set(f"user:{user.id}", user, ttl=3600)

        # Emit event using events system
        from acb.events import create_event

        event = create_event("user.created", "user_service", {"user_id": user.id})
        # Use event publisher to emit the event
        from acb.events import EventPublisher

        publisher = depends.get(EventPublisher)
        await publisher.publish(event)

        return user
```

## Version 0.16.17+ (Performance Optimizations)

### Static Adapter Mappings

ACB 0.16.17 introduced **static adapter mappings** for better performance and reliability:

```python
# Static mappings replaced dynamic discovery
static_mappings = {
    "cache.memory": ("acb.adapters.cache.memory", "Cache"),
    "cache.redis": ("acb.adapters.cache.redis", "Cache"),
    "storage.s3": ("acb.adapters.storage.s3", "Storage"),
    "sql.pgsql": ("acb.adapters.sql.pgsql", "Sql"),
    # ... and many more
}
```

**Benefits:**

- 50-70% faster adapter loading
- Eliminates runtime discovery issues
- Prevents import errors

**Migration:** No code changes required - this is transparent

### Memory Cache Interface Update

Memory cache now uses **aiocache BaseCache interface**:

```python
# BEFORE (v0.16.16 and earlier)
await cache.set("key", "value")
await cache.get("key")

# AFTER (v0.16.17+)
# Same basic interface, but now supports full aiocache API
await cache.set("key", "value", ttl=300)
await cache.add("key", "value")  # Set only if not exists
await cache.increment("counter", delta=1)  # Atomic increment
await cache.multi_set({"k1": "v1", "k2": "v2"})  # Batch operations
```

**Migration:**

- Review method signatures if using advanced cache features
- Update TTL parameter usage if needed
- Test cache operations thoroughly

### Library Mode Detection

ACB now **automatically detects** when used as a library vs application:

```python
# Auto-detection contexts:
# - During pip install or setup.py execution
# - When current directory is not "acb"
# - Build processes and package installation
# - Test contexts (pytest detection)

# Manual override if needed:
import os

os.environ["ACB_LIBRARY_MODE"] = "true"
```

**Migration:** No changes required unless you have custom initialization logic

### Test Infrastructure Changes

Some **heavy mocks were removed** for faster test startup:

```python
# Use minimal mocks or real adapters in tests
def test_adapter(mock_config):
    # Use provided mock fixtures
    pass
```

**Migration:**

- Update tests to use provided mock fixtures
- Consider using real adapters for integration tests
- 30-40% faster test startup expected

## General Migration Best Practices

### Before Upgrading

1. **Read the CHANGELOG** - Review all changes for your target version
1. **Check compatibility** - Ensure your Python version is 3.13+
1. **Review dependencies** - Check for breaking changes in dependencies
1. **Create backup** - Backup your codebase before major upgrades

### During Migration

1. **Update incrementally** - Upgrade one major version at a time
1. **Run tests frequently** - Test after each change
1. **Use type checking** - Run `pyright` to catch type errors
1. **Check deprecation warnings** - Address warnings before they become errors

### After Upgrading

1. **Run full test suite** - Ensure all tests pass
1. **Review performance** - Check for performance regressions
1. **Update documentation** - Update your docs to reflect changes
1. **Monitor production** - Watch for issues after deployment

### Incremental Upgrade Path

For **safe migrations across multiple versions**:

```bash
# Example: Upgrading from 0.16.0 to 0.19.1
uv add "acb==0.16.17"  # First to 0.16.17
# Run tests, fix issues

uv add "acb==0.18.0"   # Then to 0.18.0
# Run tests, fix issues

uv add "acb==0.19.0"   # Then to 0.19.0
# Run tests, fix issues

uv add "acb==0.19.1"   # Finally to 0.19.1
# Run tests, fix issues
```

## Troubleshooting

### Common Migration Issues

#### Import Errors After Upgrade

**Problem:** `ImportError: cannot import name 'ServiceBase'`

**Solution:**

- Check if feature was removed in new version
- See "Removed Features" section above
- Update code to use new patterns

#### Type Errors

**Problem:** `Type error: Incompatible types in assignment`

**Solution:**

- Run `pyright` to identify all type errors
- Update type annotations to match new signatures
- Check adapter method signatures in documentation

#### Test Failures

**Problem:** Tests fail after migration

**Solution:**

- Update mock objects to match new interfaces
- Use provided test fixtures
- Check test configuration for deprecations

#### Configuration Errors

**Problem:** `ConfigError: Invalid configuration`

**Solution:**

- Review configuration file structure
- Check for removed configuration options
- Validate YAML syntax

### Getting Help

If you encounter issues during migration:

1. Check the [TROUBLESHOOTING.md](./TROUBLESHOOTING.md) guide
1. Review [adapter-specific documentation](../acb/adapters/)
1. Search [GitHub Issues](https://github.com/lesleslie/acb/issues)
1. Create a minimal reproduction case
1. Report issues with version details and error messages

### Version Compatibility Table

| ACB Version | Python Version | Key Changes |
|-------------|---------------|-------------|
| 0.29.2 | 3.13+ | Current stable release - enhanced test coverage, logger DI integration |
| 0.25.2 | 3.13+ | MCP server, services, events, tasks, workflows |
| 0.20.0+ | 3.13+ | **Services reintroduced** - Services, Events, Tasks, and Workflows restored |
| 0.19.1 | 3.13+ | **Major simplification** - temporarily removed enterprise features |
| 0.16.17 | 3.12+ | Static adapter mappings, performance improvements |
| 0.16.0 | 3.12+ | Initial stable release |

## Summary

ACB's evolution focuses on **simplicity, performance, and comprehensive service architecture**:

- **v0.20.0+**: Services, Events, Tasks, and Workflows reintroduced with improved architecture
- **v0.19.1**: Simplified architecture, temporarily removed complex features
- **v0.16.17+**: Performance optimizations, static mappings
- **Current (v0.29.2)**: Stable, production-ready with enhanced test coverage and DI improvements

For detailed changes, always refer to:

- [CHANGELOG.md](../CHANGELOG.md) - Complete version history
- [ARCHITECTURE.md](./ARCHITECTURE.md) - Current architecture
- [Adapter READMEs](../acb/adapters/) - Adapter-specific changes
