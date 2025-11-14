# ACB Architecture Guide

> **Version:** 0.31.1 | **Architecture:** Simplified Adapter Pattern

This guide explains ACB's simplified architecture and core design patterns.

## Table of Contents

- [Overview](<#overview>)
- [Core Design Principles](<#core-design-principles>)
- [Architecture Layers](<#architecture-layers>)
- [Core Systems](<#core-systems>)
- [Adapter Pattern](<#adapter-pattern>)
- [Actions System](<#actions-system>)
- [Testing Infrastructure](<#testing-infrastructure>)
- [Integration Patterns](<#integration-patterns>)

## Overview

ACB (Asynchronous Component Base) is a **minimalist Python framework** built on a layered architecture focusing on clean adapter interfaces for external systems. Version 0.19.1+ represents a major simplification, removing complex enterprise features to focus on ACB's core mission.

### What ACB Does

- **Unified Adapter Interfaces**: Clean, consistent APIs for external systems (databases, caches, storage, etc.)
- **Dependency Injection**: Automatic component wiring using the `bevy` framework
- **Configuration Management**: YAML-based settings with hot-reload support
- **Async-First Design**: Built for high-performance asynchronous operations
- **Action Utilities**: Self-contained utility functions for common tasks

### What ACB Does (Since v0.19.1+)

ACB focuses on clean adapter interfaces while maintaining essential enterprise features:

- ✅ Unified Adapter Interfaces: Clean, consistent APIs for external systems
- ✅ Services layer: Standardized service patterns with lifecycle management
- ✅ Events system: Event-driven architecture for communication between components
- ✅ Dependency Injection: Automatic component wiring using the `bevy` framework
- ✅ Configuration Management: YAML-based settings with hot-reload support
- ✅ Actions System: Self-contained utility functions for common tasks
- ✅ Async-First Design: Built for high-performance asynchronous operations

## Core Design Principles

### 1. Adapter Pattern Over Inheritance

All external integrations use standardized adapter interfaces:

```python
from acb.adapters import import_adapter

# Get adapter classes (not instances)
Cache = import_adapter("cache")  # Redis or Memory
Storage = import_adapter("storage")  # S3, GCS, Azure, or File
SQL = import_adapter("sql")  # PostgreSQL, MySQL, or SQLite
```

### 2. Convention Over Configuration

ACB uses sensible defaults and convention-based discovery:

```
settings/
├── app.yml          # Application configuration
├── adapters.yml     # Adapter implementation selection
├── debug.yml        # Debug settings
├── models.yml       # Model framework settings
└── secrets/         # Secret files (not committed)
```

### 3. Dependency Injection

Components are automatically wired using type-based injection:

```python
from acb.depends import depends, Inject


@depends.inject
async def my_function(
    cache: Inject[Cache], storage: Inject[Storage], config: Inject[Config]
):
    # Dependencies automatically injected
    await cache.set("key", "value")
    await storage.write_file("data.txt", "content")
```

### 4. Async-First

All operations are designed for asynchronous execution:

```python
# All adapter methods are async
await cache.get("key")
await storage.read_file("data.txt")
async with sql.get_session() as session:
    result = await session.execute(query)
```

## Architecture Layers

ACB follows a layered architecture with clear separation of concerns:

```
┌─────────────────────────────────────────┐
│        Application Layer                │
│    (FastBlocks, Crackerjack, etc.)      │
└─────────────────────────────────────────┘
                    │
┌─────────────────────────────────────────┐
│         Services Layer                  │
│ (Business logic and lifecycle mgmt)     │
│ - Repository: Data access patterns      │
│ - Validation: Data validation & security│
│ - Performance: Optimization services    │
└─────────────────────────────────────────┘
                    │
┌─────────────────────────────────────────┐
│         Orchestration Layer             │
│ (Communication & process management)    │
│ - Events: Event-driven communication    │
│ - Tasks: Background job processing      │
│ - Workflows: Process orchestration      │
│ - MCP: AI/ML model context protocol     │
└─────────────────────────────────────────┘
                    │
┌─────────────────────────────────────────┐
│         Adapter Layer                   │
│  (External system integration)          │
│  (Cache, SQL, NoSQL, Storage, etc.)     │
└─────────────────────────────────────────┘
                    │
┌─────────────────────────────────────────┐
│      Core Infrastructure                │
│  (Config, DI, Logger, Context, SSL)     │
└─────────────────────────────────────────┘
```

### Layer Responsibilities

**Application Layer:**

- Contains application-specific business logic
- Uses ACB components to implement domain functionality
- Frameworks like FastBlocks operate at this layer

**Services Layer:**

- Provides stateful components with lifecycle management
- Implements business services with health checks and metrics
- Handles domain-specific operations (repository, validation, performance)

**Orchestration Layer:**

- Manages communication between components
- Handles background processing and task execution
- Orchestrates multi-step processes and workflows
- Provides AI/ML integration interfaces (MCP)

**Adapter Layer:**

- Provides standardized interfaces to external systems
- Abstracts implementation details of external services
- Enables configuration-driven implementation selection

**Core Infrastructure:**

- Provides foundational services for the framework
- Handles configuration, dependency injection, and logging
- Ensures consistent cross-cutting concerns

### Development & Deployment Tools

ACB also includes specialized tools for development and deployment that operate outside the runtime architecture:

**Migration Tools:**

- Provides version migration capabilities for ACB applications
- Handles compatibility between different ACB versions
- Supports rollback and validation of migrations

**Testing Infrastructure:**

- Comprehensive testing utilities and fixtures
- Mocking capabilities for all ACB components
- Performance testing tools

## Core Systems

### Configuration System (`acb.config`)

Centralized settings management with hot-reloading:

```python
from acb.config import Config, enable_config_hot_reload

config = Config()

# Enable hot-reload monitoring
hot_reload = await enable_config_hot_reload(config, check_interval=5.0)

# Configuration changes are automatically detected
# Stop monitoring when done
await hot_reload.stop()
```

**Key Features:**

- YAML-based configuration files
- Secret management integration
- Environment variable support
- Simple hot-reload monitoring
- Pydantic-based validation

### Dependency Injection (`acb.depends`)

Built on the `bevy` framework for automatic component wiring:

```python
from acb.depends import depends, Inject
from acb.adapters import import_adapter

Cache = import_adapter("cache")

# Register singleton
cache_instance = Cache()
depends.set(Cache, cache_instance)


# Automatic injection
@depends.inject
async def process_data(cache: Inject[Cache]):
    return await cache.get("data")
```

**Key Features:**

- Type-based dependency resolution
- Singleton and factory patterns
- Lazy initialization
- No boilerplate required

### Logging System (`acb.logger`)

Loguru-based async logging with structured output:

```python
from acb.logger import logger

logger.info("Processing request", user_id=123, action="create")
logger.error("Database error", error=str(e), query=sql)
logger.debug("Cache hit", key=cache_key, ttl=300)
```

**Key Features:**

- Async logging operations
- Structured JSON output
- Performance timing
- Context-aware logging
- Integration with monitoring adapters

### Context Management (`acb.context`)

Centralized context for the framework (v0.19.1+):

```python
from acb.context import context

# Access configuration
app_name = context.config.app.name

# Access adapters
cache = context.cache
storage = context.storage
```

**Key Features:**

- Centralized access to core components
- Simplified architecture
- Clean API surface

## Adapter Pattern

### Adapter Categories

ACB provides adapters for major external system categories:

- **cache**: Memory, Redis (aiocache, coredis)
- **models**: SQLModel, Pydantic, Redis-OM, msgspec, attrs
- **sql**: MySQL, PostgreSQL, SQLite (SQLAlchemy, SQLModel)
- **nosql**: MongoDB, Firestore, Redis
- **storage**: File, S3, GCS, Azure
- **secret**: Infisical, GCP Secret Manager, Azure Key Vault, Cloudflare KV
- **monitoring**: Sentry, Logfire
- **requests**: HTTPX, Niquests
- **smtp**: Gmail, Mailgun
- **dns**: Cloud DNS, Cloudflare, Route53
- **ftpd**: FTP, SFTP clients

### Adapter Implementation Pattern

All adapters follow a consistent pattern:

```python
class ExampleAdapter:
    def __init__(self):
        self._client = None
        self._settings = None

    async def public_method(self, *args, **kwargs):
        # Public methods delegate to private implementation
        return await self._public_method(*args, **kwargs)

    async def _public_method(self, *args, **kwargs):
        # Private method contains actual implementation
        client = await self._ensure_client()
        # Implementation logic here
        return result

    async def _ensure_client(self):
        # Lazy client initialization with connection pooling
        if self._client is None:
            self._client = await self._create_client()
        return self._client
```

### Adapter Metadata

Each adapter includes `MODULE_METADATA` for identification:

```python
from acb.adapters import AdapterMetadata, AdapterStatus, AdapterCapability

MODULE_METADATA = AdapterMetadata(
    module_id=generate_adapter_id(),
    name="Redis Cache",
    category="cache",
    provider="redis",
    version="1.0.0",
    acb_min_version="0.18.0",
    status=AdapterStatus.STABLE,
    capabilities=[
        AdapterCapability.ASYNC_OPERATIONS,
        AdapterCapability.CACHING,
        AdapterCapability.CONNECTION_POOLING,
    ],
    required_packages=["redis>=4.0.0"],
    description="High-performance Redis caching adapter",
)
```

### Simple Resource Cleanup

All adapters use a simplified cleanup pattern (v0.19.1+):

```python
from acb.cleanup import CleanupMixin


class SimpleAdapter(CleanupMixin):
    def __init__(self):
        super().__init__()
        self._client = None

    async def _create_client(self):
        client = SomeClient()
        self.register_resource(client)  # Register for automatic cleanup
        return client

    # Cleanup is automatic via CleanupMixin
```

## Actions System

Stateless utility functions organized by verb-based actions (not a runtime architectural layer). Actions provide simple, stateless operations that can be used across all architectural layers:

```python
# Compression actions
from acb.actions.compress import compress, decompress

compressed = compress.gzip("Hello, ACB!", compresslevel=9)

# Encoding actions
from acb.actions.encode import encode, decode

json_data = await encode.json(data)

# Hashing actions
from acb.actions.hash import hash

blake3_hash = await hash.blake3("some data")
```

**Action Structure:**

- `acb.actions.compress`: gzip, brotli compression
- `acb.actions.encode`: JSON, YAML, TOML, MsgPack serialization
- `acb.actions.hash`: blake3, crc32c, md5 hashing

See [ACTION_TEMPLATE.md](<./ACTION_TEMPLATE.md>) for creating custom actions.

## Testing Infrastructure

### Test Fixtures

ACB provides comprehensive testing support:

```python
import pytest
from acb.testing import mock_config, mock_cache, mock_sql


@pytest.mark.asyncio
async def test_user_service(mock_config, mock_cache, mock_sql):
    """Test with mocked dependencies"""
    service = UserService()

    # Mock cache returns None (cache miss)
    mock_cache.get.return_value = None

    # Mock SQL returns user data
    mock_sql.execute.return_value = {"id": 1, "name": "John"}

    user = await service.get_user(1)
    assert user.name == "John"
```

### File System Mocking

Tests automatically patch file operations:

```python
def test_file_operation(mock_async_file_system, patch_async_file_operations):
    # Files are automatically mocked - no actual I/O
    pass
```

### Key Fixtures

- `mock_config`: Mocked Config for unit testing
- `real_config`: Real Config instance for integration tests
- `mock_adapter_settings`: Generic adapter settings mock
- `patch_file_operations`: File system mocking for unit tests
- `patch_async_file_operations`: Async file system mocking

## Integration Patterns

### Pattern 1: Multi-Adapter Usage

Combine multiple adapters with dependency injection:

```python
from acb.depends import depends, Inject
from acb.adapters import import_adapter

Cache = import_adapter("cache")
Storage = import_adapter("storage")
SQL = import_adapter("sql")


@depends.inject
async def process_user_data(
    cache: Inject[Cache], storage: Inject[Storage], sql: Inject[SQL]
):
    # Check cache first
    user_data = await cache.get("user:123")
    if not user_data:
        # Fetch from database
        async with sql.get_session() as session:
            user_data = await session.execute(query)

        # Cache the result
        await cache.set("user:123", user_data, ttl=3600)

    # Store to backup
    await storage.write_file("backups/user_123.json", user_data)

    return user_data
```

### Pattern 2: Configuration-Driven Adapters

Select adapter implementations via configuration:

```yaml
# settings/adapters.yml
cache: redis        # or: memory
storage: s3         # or: file, gcs, azure
sql: postgresql     # or: mysql, sqlite
models: true        # Enable models adapter
```

### Pattern 3: FastBlocks Integration

ACB powers FastBlocks web framework:

```python
from fastblocks import HTTPEndpoint
from acb.depends import depends, Inject
from acb.config import Config


class FastBlocksEndpoint(HTTPEndpoint):
    config: Inject[Config]

    def __init__(self, scope, receive, send):
        super().__init__(scope, receive, send)
        self.templates = depends.get("templates")
```

## Summary

ACB's comprehensive architecture (v0.20.0+) focuses on:

- **Clean Adapter Interfaces**: Unified APIs for external systems
- **Services Layer**: Lifecycle management for stateful components
- **Orchestration Layer**: Events, Tasks, and Workflow management
- **Essential Core**: Config, DI, Logger, Context, SSL
- **Async Performance**: Built for high-throughput applications
- **Developer Experience**: Convention over configuration

For implementation guidance:

- [ARCHITECTURE_IMPLEMENTATION_GUIDE.md](<./ARCHITECTURE_IMPLEMENTATION_GUIDE.md>) - Complete guide to architectural layers and implementation patterns
- [ACTION_TEMPLATE.md](<./ACTION_TEMPLATE.md>) - Creating custom actions
- [ADAPTER_TEMPLATE.md](<./ADAPTER_TEMPLATE.md>) - Creating custom adapters
- [PERFORMANCE-GUIDE.md](<./PERFORMANCE-GUIDE.md>) - Performance optimization
- [TROUBLESHOOTING.md](<./TROUBLESHOOTING.md>) - Common issues and solutions
- [Individual adapter READMEs](../acb/adapters/) - Adapter-specific documentation
