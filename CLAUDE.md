# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Context System

ACB has a new `acb/context.py` module that provides centralized context management for the framework. This is part of the simplified architecture in v0.19.1+.

## Development Commands

### Testing

```bash
# Run all tests
python -m pytest

# Run tests with coverage
python -m pytest --cov=acb --cov-report=term

# Run specific test categories
python -m pytest -m unit        # Unit tests only
python -m pytest -m integration # Integration tests only
python -m pytest -m benchmark   # Benchmark tests only

# Run tests for specific adapter
python -m pytest tests/adapters/cache/
python -m pytest tests/adapters/sql/test_mysql.py

# Run tests with verbose output
python -m pytest -v

# Run with show output (print statements)
python -m pytest -s
```

### Code Quality

```bash
# Lint and format code
ruff check --fix
ruff format

# Type checking (using pyright)
pyright

# Full quality workflow with crackerjack
python -m crackerjack -x -t -p <version> -c    # Clean, test, bump version, commit
python -m crackerjack -a <version>             # Alternative automated workflow
python -m crackerjack -t --ai-agent            # Test and quality verification (AI-optimized output)
python -m crackerjack -t                       # Test and quality verification (human-friendly output)
```

### Package Management

```bash
# Install development dependencies
uv sync --group dev

# Install with specific adapter groups
uv add "acb[cache,sql,storage]"  # Common web app stack
uv add "acb[all]"                # All optional dependencies

# Add development dependency
uv add --group dev <package>
```

## Architecture Overview

ACB (Asynchronous Component Base) is a modular Python framework with a component-based architecture built around **actions**, **adapters**, and **dependency injection**.

### Featured Implementation

**FastBlocks**: A high-performance web framework built on ACB showcasing enterprise-grade adapter patterns and HTMX integration. [See FastBlocks on GitHub](https://github.com/lesleslie/fastblocks) for a complete example of ACB best practices in production.

### Version Compatibility

- **Python**: 3.13+ (required)
- **FastBlocks Integration**: ACB v0.19.0+ required for FastBlocks v0.14.0+
- **Breaking Changes**: See MIGRATION guides for version-specific upgrade instructions

### Core Design Patterns

1. **Adapter Pattern**: All external integrations use standardized interfaces with pluggable implementations
1. **Dependency Injection**: Components are automatically wired together using the `bevy` framework
1. **Configuration-Driven**: Behavior is controlled through YAML configuration files
1. **Async-First**: Built for high-performance asynchronous operations
1. **Dynamic Adapter Loading**: Adapters are loaded on-demand using convention-based discovery

### Directory Structure (v0.19.1+ Simplified)

```
acb/
├── actions/          # Pure utility functions (verb-based)
│   ├── compress/     # Compression utilities (gzip, brotli)
│   ├── encode/       # Encoding/decoding (JSON, YAML, TOML, MsgPack)
│   └── hash/         # Hashing utilities (blake3, crc32c, md5)
├── core/             # Essential adapter infrastructure
│   ├── ssl_config.py # SSL/TLS configuration
│   └── cleanup.py    # Simple resource cleanup patterns
├── adapters/         # External system integrations
│   ├── cache/        # Memory, Redis caching (simplified)
│   │   ├── memory.py
│   │   ├── redis.py
│   │   └── _base.py  # Basic cache functionality
│   ├── models/       # Model framework support (SQLModel, Pydantic, etc.)
│   ├── sql/          # MySQL, PostgreSQL, SQLite databases
│   │   ├── mysql.py
│   │   ├── pgsql.py
│   │   ├── sqlite.py
│   │   └── _base.py  # Basic SQL functionality
│   ├── nosql/        # MongoDB, Firestore, Redis
│   ├── storage/      # S3, GCS, Azure, file storage
│   ├── secret/       # Secret management (Infisical, GCP Secret Manager, Azure, Cloudflare)
│   ├── monitoring/   # Sentry, Logfire
│   ├── requests/     # HTTP clients (HTTPX, Niquests)
│   ├── smtp/         # Email sending (Gmail, Mailgun)
│   ├── dns/          # DNS management (Cloud DNS, Cloudflare, Route53)
│   ├── ftpd/         # File transfer (FTP, SFTP)
│   └── ...
├── config.py         # Configuration system with simple hot-reloading
├── context.py        # Centralized context management (v0.19.1+)
├── depends.py        # Dependency injection framework
├── logger.py         # Logging system
├── debug.py          # Debugging utilities
└── console.py        # Console utilities
```

### Adapter Implementation Pattern

All adapters follow a consistent pattern with public/private method delegation:

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
        # Lazy client initialization pattern with connection pooling
        if self._client is None:
            self._client = await self._create_client()
        return self._client

    async def _create_client(self):
        # Initialize the actual client connection
        # Use self._settings for configuration
        return client_instance
```

### Adapter Metadata Standard

Each adapter includes `MODULE_METADATA` for identification and capability discovery:

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
    capabilities=[AdapterCapability.ASYNC_OPERATIONS, AdapterCapability.CACHING],
    required_packages=["redis>=4.0.0"],
    description="High-performance Redis caching adapter",
)
```

**Key capabilities**: CONNECTION_POOLING, TRANSACTIONS, ASYNC_OPERATIONS, CACHING, ENCRYPTION
**Status levels**: ALPHA, BETA, STABLE, DEPRECATED, EXPERIMENTAL

### Simplified Architecture (v0.19.1+)

ACB has been significantly simplified to focus on its core mission: providing clean, reliable adapter interfaces for external systems. Complex enterprise features have been removed or simplified to avoid over-engineering.

#### Core Simplifications

**Removed Complex Features:**

- Complex enterprise monitoring and health checking
- Advanced retry mechanisms and circuit breakers
- Multi-tier caching strategies and complex query builders
- Distributed tracing and observability frameworks
- Rate limiting and advanced security systems
- Backup and restore functionality

**Preserved Essential Features:**

- Basic resource cleanup patterns
- SSL/TLS configuration support
- Simple configuration hot-reloading
- Core adapter functionality
- Basic model framework support

#### Simple Resource Cleanup

All adapters now use a simplified cleanup pattern:

```python
from acb.core.cleanup import CleanupMixin


class SimpleAdapter(CleanupMixin):
    """Adapter with basic cleanup capability"""

    def __init__(self):
        super().__init__()
        self._client = None

    async def _create_client(self):
        client = SomeClient()
        self.register_resource(client)  # Register for automatic cleanup
        return client

    async def get_data(self):
        client = await self._ensure_client()
        return await client.fetch_data()

    # Cleanup is automatic via CleanupMixin
```

#### Basic Cache Operations

Cache adapters provide simple, reliable caching:

```python
# Basic cache operations
await cache.set("key", "value", ttl=300)
await cache.get("key")
await cache.delete("key")

# Standard aiocache interface
await cache.add("key", "value")  # Set only if not exists
await cache.increment("counter", delta=1)  # Atomic increment
await cache.expire("key", ttl=60)  # Update TTL
await cache.multi_set({"k1": "v1", "k2": "v2"})  # Batch operations

# Automatic resource cleanup with context manager
async with cache:
    await cache.set("temp", "data")
    # Cleanup happens automatically
```

#### Simple Configuration Hot-Reloading

Basic configuration monitoring is now built into the config system:

```python
from acb.config import Config, enable_config_hot_reload

# Enable simple hot-reloading
config = Config()
hot_reload = await enable_config_hot_reload(config, check_interval=5.0)

# Configuration files are monitored automatically:
# - settings/app.yml
# - settings/adapters.yml
# - settings/debug.yml
# - settings/models.yml

# Stop monitoring when done
await hot_reload.stop()
```

## Configuration System

### Settings Structure

```
settings/
├── app.yml          # Application settings (name, version, domain)
├── debug.yml        # Debug configuration
├── adapters.yml     # Adapter implementation selection
├── models.yml       # Models framework configuration (SQLModel, Pydantic, Redis-OM)
└── secrets/         # Secret files (not committed)
```

### Adapter Selection

Configure which implementations to use in `settings/adapters.yml`:

```yaml
cache: redis        # or: memory
storage: s3         # or: file, gcs, azure
sql: postgresql     # or: mysql, sqlite
models: true        # Enable models adapter (auto-detects model types)
nosql: mongodb      # or: firestore, redis
ftpd: sftp          # or: ftp
```

### Static Adapter Mappings (v0.16.17+)

ACB uses hardcoded static mappings for adapter registration, improving performance and reliability:

```python
# Example of static adapter mappings
static_mappings = {
    "cache.memory": ("acb.adapters.cache.memory", "Cache"),
    "cache.redis": ("acb.adapters.cache.redis", "Cache"),
    "storage.s3": ("acb.adapters.storage.s3", "Storage"),
    "sql.pgsql": ("acb.adapters.sql.pgsql", "Sql"),
    # ... and many more
}
```

This approach eliminates runtime discovery issues and import errors.

### Models Framework Configuration

Configure which model frameworks are enabled in `settings/models.yml`:

```yaml
# Enable SQLModel support (default: true)
sqlmodel: true

# Enable Pydantic support (default: true)
pydantic: true

# Enable Redis-OM support (default: false)
redis_om: false

# Enable msgspec support (default: false)
msgspec: false

# Enable attrs support (default: false)
attrs: false
```

### Dependency Injection Usage

```python
from acb.depends import depends
from acb.adapters import import_adapter

# Import adapter classes (not instances)
Cache = import_adapter("cache")
Storage = import_adapter("storage")

# Or use the no-argument form that infers from context
# Cache, Storage = import_adapter()  # Infers from variable names


@depends.inject
async def my_function(
    cache: Cache = depends(), storage: Storage = depends(), config: Config = depends()
):
    # Dependencies automatically injected
    pass


# FastBlocks HTTPEndpoint Pattern (from FastBlocks CLAUDE.md)
class FastBlocksEndpoint(HTTPEndpoint):
    config: Config = depends()

    def __init__(self, scope: Scope, receive: Receive, send: Send) -> None:
        super().__init__(scope, receive, send)
        self.templates = depends.get("templates")
```

### Universal Query Interface Examples (v0.19.0+)

The models adapter provides comprehensive support for multiple model frameworks with automatic detection:

```python
from acb.depends import depends
from acb.adapters import import_adapter
from acb.adapters.models._hybrid import ACBQuery

# Import the models adapter
Models = import_adapter("models")
models = depends.get(Models)

# Example models using different frameworks
from sqlmodel import SQLModel, Field
from pydantic import BaseModel
import msgspec
import attrs


# SQLModel for SQL databases
class User(SQLModel, table=True):
    id: int = Field(default=None, primary_key=True)
    name: str
    email: str
    active: bool = True


# Pydantic for API DTOs
class UserCreateRequest(BaseModel):
    name: str
    email: str


# msgspec for high-performance serialization
class UserSession(msgspec.Struct):
    user_id: str
    token: str
    expires_at: int


# attrs for mature applications
@attrs.define
class UserProfile:
    bio: str
    avatar_url: str


# Universal query interface works with all model types
query = ACBQuery()

# Simple query style - works with any model framework
users = await query.for_model(User).simple.all()
user = await query.for_model(User).simple.find(1)
new_user = await query.for_model(User).simple.create(
    {"name": "John Doe", "email": "john@example.com"}
)

# Basic query operations (simplified)
filtered_users = await query.for_model(User).simple.filter({"active": True}).limit(10)
```

### Configuration Library Mode Detection (v0.16.17+)

ACB now automatically detects when it's being used as a library vs application using sophisticated detection logic:

```python
# ACB detects library usage in these contexts:
# - During pip install or setup.py execution
# - When current directory is not "acb" (working directory check)
# - Build processes and package installation
# - Test contexts (pytest detection)

# Manual override if needed:
import os

os.environ["ACB_LIBRARY_MODE"] = "true"

# Library mode affects:
# - Configuration initialization (eager vs lazy)
# - Adapter registration behavior
# - Debug output configuration
```

## Testing Guidelines

### Mock Implementation Requirements

- Mock classes must match real adapter signatures
- Implement proper public/private method delegation
- Mock async context managers need both `__aenter__` and `__aexit__`
- Clear cached properties before tests: `del adapter.property_name`

### Test Organization

- Implementation tests: `test_<implementation>.py` (specific behavior)
- Shared functionality: `test_<category>_base.py` (when needed for common test patterns)
- Use pytest markers: `@pytest.mark.unit`, `@pytest.mark.integration`, `@pytest.mark.benchmark`
- Base test files contain common fixtures and reusable assertion utilities
- Mock classes must implement proper public/private method delegation
- Separate test classes for complex adapters to avoid fixture conflicts

### File System Mocking

Tests automatically patch file operations to prevent actual file creation:

- `patch_file_operations`: Patches pathlib.Path operations
- `patch_async_file_operations`: Patches anyio.Path operations
- `mock_config`: Provides mocked Config without real files

### Key Test Fixtures

The test suite provides several important fixtures:

- `mock_config`: Mocked Config for unit testing
- `real_config`: Real Config instance for integration tests
- `mock_adapter_settings`: Generic adapter settings mock
- `patch_file_operations`: File system mocking for unit tests
- `patch_async_file_operations`: Async file system mocking

### Testing Best Practices

1. **Never create actual files**: Use provided mock fixtures
1. **Proper delegation**: Mock classes must mirror real implementation signatures
1. **Async context managers**: Implement both `__aenter__` and `__aexit__`
1. **Clear cached properties**: Use `del adapter.property_name` before tests
1. **Exception handling**: Mock objects should handle expected exceptions

## Key Components

### Actions

Self-contained utility functions automatically discovered and registered:

- `acb.actions.compress`: gzip, brotli compression
- `acb.actions.encode`: JSON, YAML, TOML, MsgPack serialization
- `acb.actions.hash`: blake3, crc32c, md5 hashing

### Core Systems

- **Config**: Pydantic-based configuration with secret management
- **Logger**: Loguru-based async logging with structured output
- **Debug**: icecream-powered debugging with performance timing
- **Depends**: bevy-based dependency injection

### Adapter Categories

- **cache**: Memory, Redis (aiocache, coredis)
- **models**: SQLModel, Pydantic, Redis-OM, msgspec, attrs (auto-detection, universal query interface)
- **sql**: MySQL, PostgreSQL, SQLite (SQLAlchemy, SQLModel)
- **nosql**: MongoDB, Firestore, Redis
- **storage**: File, S3, GCS, Azure
- **secret**: Infisical, GCP Secret Manager, Azure Key Vault, Cloudflare KV
- **monitoring**: Sentry, Logfire
- **requests**: HTTPX, Niquests
- **smtp**: Gmail, Mailgun
- **dns**: Cloud DNS, Cloudflare, Route53
- **ftpd**: FTP, SFTP clients

## Development Workflow

1. **Setup**: `uv sync --group dev`
1. **Code**: Follow adapter patterns and async interfaces
1. **Test**: Write tests with proper mocking
1. **Quality**: Use ruff for formatting and pyright for type checking
1. **Verification**: **MANDATORY** - Run `python -m crackerjack -t --ai-agent` before task completion
1. **Automation**: Use crackerjack for comprehensive workflows

## Code Quality Compliance

**Target Python 3.13+** with modern syntax and security practices:

**Modern Python patterns:**

- Use `pathlib.Path`, `str.removeprefix()`, `|` union types, `dict1 | dict2` merging
- Use `any()/all()`, comprehensions, `enumerate()`, context managers
- Prefer `match` statements, type annotations on all functions

**Security requirements:**

- Never use `eval()`, `exec()`, `subprocess.shell=True`, `pickle` with untrusted data
- Use `secrets` module (not `random`), environment variables for secrets
- Parameterized queries only, validate all inputs, specify file encoding

**Type safety:**

- Explicit type hints on parameters/returns, handle `Optional` properly
- Use `str | None`, `list[str]`, `dict[str, Any]` modern syntax
- Type narrowing with assertions, `Protocol` for duck typing

**Pre-commit hooks**: Refurb, Bandit, Pyright, Ruff, pyproject-fmt, Vulture, Creosote, Complexipy, Codespell, detect-secrets

## Project Structure

**Core directories**: `actions/` (utilities), `adapters/` (external systems), `core/` (infrastructure)
**Key files**: `config.py`, `depends.py`, `logger.py`, `debug.py`, `context.py`
**Settings structure**: `app.yml`, `debug.yml`, `adapters.yml`, `models.yml`, `secrets/`

## Important Rules from .windsurfrules

- Always implement adapter pattern with public/private method delegation
- Use `_ensure_client()` pattern for lazy connection initialization
- Mock classes must mirror real implementation signatures
- Follow consistent async interfaces across all adapters
- Group dependencies by adapter type in pyproject.toml
- Use ACB settings pattern for component configuration
- Implement proper error handling with appropriate exception types
- **Include MODULE_METADATA in all adapters** with proper AdapterMetadata schema
- Use AdapterCapability enum for feature detection and runtime validation
- Follow semantic versioning for adapter versions (independent of ACB version)
- **Implement simple resource cleanup** - use basic cleanup patterns via CleanupMixin
- **Follow basic security practices** - validate inputs, use secure defaults

## Version Information and Recent Changes

### Current Version: 0.19.1

Key improvements in v0.19.1:

- **Simplified Architecture**: Removed complex enterprise features to focus on core adapter functionality
- **Basic Resource Cleanup**: Simple, reliable cleanup patterns without over-engineering
- **Essential SSL/TLS**: Basic SSL configuration support where needed
- **Streamlined Cache Operations**: Simple caching with standard aiocache interface
- **Performance Improvements**: Continued optimization with faster adapter loading
- Enhanced models adapter with universal query interface
- Improved SQL adapter reliability and performance
- Better error handling and logging across all adapters
- Updated dependencies and compatibility fixes

### Recent Changes and Best Practices (v0.16.17+)

### Performance Optimizations

- **Dynamic Adapter Loading**: Simplified adapter loading with convention-based discovery
- **Memory Cache Enhancement**: Full aiocache interface implementation (50% faster operations)
- **Test Infrastructure**: Removed heavy mocks for faster test startup (30-40% improvement)

### Core Adapters

Only two adapters are automatically registered as they are truly essential for ACB operation:

- `config` - Configuration management (always needed)
- `loguru` - Logging system (always needed)

All other adapters follow the opt-in principle and must be explicitly configured in `settings/adapters.yml`.

### Performance Best Practices

1. **Use Lazy Loading**: Initialize expensive resources only when needed

   ```python
   async def _ensure_client(self):
       if self._client is None:
           self._client = await self._create_client()
       return self._client
   ```

1. **Connection Pooling**: Configure pool sizes for database adapters

   ```yaml
   sql:
     pool_size: 20
     max_overflow: 30
   ```

1. **Singleton Services**: Register expensive services once during startup

   ```python
   expensive_service = ExpensiveService()
   depends.set(ExpensiveService, expensive_service)
   ```

1. **Cache Strategy**: Use appropriate TTL values to balance memory and performance

1. **Async Best Practices**: Use `asyncio.gather()` for concurrent operations

For detailed performance optimization, see `docs/PERFORMANCE-GUIDE.md`.

### Breaking Changes to Be Aware Of

1. **Memory Cache Interface**: Now uses aiocache BaseCache interface - update method signatures
1. **Test Mocks**: Some test mocks removed - use real adapters or minimal mocks
1. **Configuration Detection**: Library mode auto-detection may affect initialization

### Migration Best Practices

- Review MIGRATION-0.16.17.md for detailed upgrade instructions
- Update memory cache usage to new aiocache interface
- Test thoroughly with dynamic adapter loading
- Verify configuration loading in library mode

## Changelog and Version History

ACB maintains a detailed changelog tracking all significant changes:

- **Latest Version**: 0.19.1
- **Breaking Changes**: See CHANGELOG.md for version-specific breaking changes
- **Migration Guides**: Detailed migration instructions for major version updates
- **Recent Improvements**: Performance optimizations, adapter system refactor (0.16.17+)

### Recent Notable Changes (0.16.17+)

- **Static Adapter Mappings**: Replaced dynamic discovery with hardcoded mappings for better performance
- **Memory Cache Rewrite**: Full aiocache interface implementation with MsgPack serialization
- **Library Mode Detection**: Automatic detection of library vs application usage
- **Architecture Simplification**: Removed complex enterprise features in favor of simplicity
- **Performance**: 50-70% faster adapter loading, 30-40% faster test startup

## Task Completion Requirements

**MANDATORY: Before marking any task as complete, AI assistants MUST:**

1. **Run crackerjack verification**: Execute `python -m crackerjack -t --ai-agent` to run all quality checks and tests with AI-optimized output
1. **Fix any issues found**: Address all formatting, linting, type checking, and test failures
1. **Re-run verification**: Ensure crackerjack passes completely (all hooks pass, all tests pass)
1. **Document verification**: Mention that crackerjack verification was completed successfully

**Why this is critical:**

- Ensures all code meets project quality standards
- Prevents broken code from being committed
- Maintains consistency with project development workflow
- Catches issues early before they become problems

**Never skip crackerjack verification** - it's the project's standard quality gate.

## Adapter-Specific Documentation

Each adapter category has its own detailed README with usage examples and configuration:

- **[Cache](./acb/adapters/cache/README.md)**: Memory and Redis caching with aiocache interface
- **[DNS](./acb/adapters/dns/README.md)**: Domain management (Cloud DNS, Cloudflare, Route53)
- **[FTPD](./acb/adapters/ftpd/README.md)**: File transfer protocols (FTP, SFTP)
- **[Models](./acb/adapters/models/README.md)**: Universal query interface for multiple ORMs
- **[Monitoring](./acb/adapters/monitoring/README.md)**: Error tracking (Sentry, Logfire)
- **[NoSQL](./acb/adapters/nosql/README.md)**: Document databases (MongoDB, Firestore, Redis)
- **[Requests](./acb/adapters/requests/README.md)**: HTTP clients (HTTPX, Niquests)
- **[Secret](./acb/adapters/secret/README.md)**: Secret management (Infisical, GCP, Azure, Cloudflare)
- **[SMTP](./acb/adapters/smtp/README.md)**: Email sending (Gmail, Mailgun)
- **[SQL](./acb/adapters/sql/README.md)**: Relational databases (MySQL, PostgreSQL, SQLite)
- **[Storage](./acb/adapters/storage/README.md)**: File storage (S3, GCS, Azure, local)

## Common Issues and Solutions

**Secret detection**: Add `# pragma: allowlist secret` to config examples
**Adapter field types**: Return `Any` (not `type(Any)`) for missing fields
**Test mocks**: Include all required attributes (e.g., `mock_sql.ssl_enabled = True`)

**Quick fixes:**

- Adapter not loading → Check `settings/adapters.yml`, install with `uv add "acb[adapter_name]"`
- Import errors → Install ACB with `uv add acb`, check Python 3.13+ requirement
- Config errors → Verify YAML syntax, create `settings/` structure
- Test failures → Use proper async fixtures, `@pytest.mark.asyncio` decorator

## Critical Development Rules

**MANDATORY: Follow these rules exactly:**

- Do what has been asked; nothing more, nothing less
- NEVER create files unless they're absolutely necessary for achieving your goal
- ALWAYS prefer editing an existing file to creating a new one
- NEVER proactively create documentation files (\*.md) or README files unless explicitly requested
- When working with secrets in config examples, add `# pragma: allowlist secret` comments
- Always return `Any` (not `type(Any)`) from adapter field type methods for missing fields
