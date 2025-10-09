# ACB Migration Guide

This guide helps you upgrade between ACB versions, detailing breaking changes and upgrade paths.

## Table of Contents

- [Version 0.19.1+ (Simplified Architecture)](<#version-0191-simplified-architecture>)
- [Version 0.16.17+ (Performance Optimizations)](<#version-01617-performance-optimizations>)
- [General Migration Best Practices](<#general-migration-best-practices>)
- [Troubleshooting](<#troubleshooting>)

## Version 0.19.1+ (Simplified Architecture)

### Overview

Version 0.19.1 represents a **major architectural simplification**, removing complex enterprise features to focus on ACB's core mission: providing clean, reliable adapter interfaces for external systems.

### Removed Features

The following enterprise features were **completely removed**:

#### ❌ Services Layer

```python
# REMOVED - No longer available
from acb.services import ServiceBase, register_service


class UserService(ServiceBase):  # ❌ ServiceBase removed
    pass
```

**Migration Path:**

- Implement business logic directly in your application
- Use dependency injection for adapter access
- Consider framework-specific patterns (e.g., FastBlocks services)

#### ❌ Event System

```python
# REMOVED - No longer available
from acb.events import EventPublisher, EventSubscriber

publisher = EventPublisher()  # ❌ Events removed
await publisher.emit("user.created", user_id=123)
```

**Migration Path:**

- Use framework-specific event systems (e.g., Starlette events)
- Implement custom pub/sub if needed
- Consider external message brokers for distributed events

#### ❌ Task Queue System

```python
# REMOVED - No longer available
from acb.queues import Queue, task

queue = Queue()  # ❌ Queues removed


@task(queue=queue)
async def process_order(order_id: str):
    pass
```

**Migration Path:**

- Use dedicated task queue libraries (Celery, RQ, Dramatiq, Huey)
- Implement simple async task processing if needed
- Consider cloud-based queue services (AWS SQS, Google Pub/Sub)

#### ❌ Workflow Engine

```python
# REMOVED - No longer available
from acb.workflows import WorkflowDefinition, WorkflowEngine

workflow = WorkflowDefinition(...)  # ❌ Workflows removed
```

**Migration Path:**

- Use workflow libraries (Temporal, Prefect, Airflow)
- Implement custom workflow logic if simple
- Use application-level orchestration

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

### Migration Checklist for v0.19.1+

- [ ] **Remove service layer dependencies** - Use direct adapter access
- [ ] **Replace event system** - Use framework-specific events or custom implementation
- [ ] **Replace queue system** - Use dedicated task queue library
- [ ] **Replace workflow engine** - Use workflow library or custom orchestration
- [ ] **Update health checks** - Implement simple application-level checks
- [ ] **Update retry logic** - Use `tenacity` or simple retry patterns
- [ ] **Update cleanup patterns** - Use `CleanupMixin` for resource cleanup
- [ ] **Test thoroughly** - Validate all functionality after migration

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

#### After (v0.19.1+)

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

1. Check the [TROUBLESHOOTING.md](<./TROUBLESHOOTING.md>) guide
1. Review [adapter-specific documentation](../acb/adapters/)
1. Search [GitHub Issues](https://github.com/lesleslie/acb/issues)
1. Create a minimal reproduction case
1. Report issues with version details and error messages

### Version Compatibility Table

| ACB Version | Python Version | Key Changes |
|-------------|---------------|-------------|
| 0.23.0 | 3.13+ | Current stable release |
| 0.19.1 | 3.13+ | **Major simplification** - removed enterprise features |
| 0.16.17 | 3.12+ | Static adapter mappings, performance improvements |
| 0.16.0 | 3.12+ | Initial stable release |

## Summary

ACB's evolution focuses on **simplicity and performance**:

- **v0.19.1+**: Simplified architecture, removed complex features
- **v0.16.17+**: Performance optimizations, static mappings
- **Current (v0.23.0)**: Stable, production-ready, minimal core

For detailed changes, always refer to:

- [CHANGELOG.md](<../CHANGELOG.md>) - Complete version history
- [ARCHITECTURE.md](<./ARCHITECTURE.md>) - Current architecture
- [Adapter READMEs](../acb/adapters/) - Adapter-specific changes
