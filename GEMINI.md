# GEMINI.md

This file provides guidance to Gemini when working with code in this repository.

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

### Directory Structure (v0.19.3+ Simplified)

```
acb/
├── actions/          # Pure utility functions (verb-based)
│   ├── compress/     # Compression utilities (gzip, brotli)
│   ├── encode/       # Encoding/decoding (JSON, YAML, TOML, MsgPack)
│   ├── hash/         # Hashing utilities (blake3, crc32c, md5)
│   └── validate/     # Input validation utilities
│   └── secure/       # Cryptographic utilities
├── core/             # Essential adapter infrastructure
│   ├── ssl_config.py # SSL/TLS configuration
│   └── cleanup.py    # Simple resource cleanup patterns
├── adapters/         # External system integrations
│   ├── cache/        # Memory, Redis caching (simplified)
│   │   ├── memory.py
│   │   ├── redis.py
│   │   └── _base.py  # Basic cache functionality
│   ├── sql/          # MySQL, PostgreSQL, SQLite databases
│   │   ├── mysql.py
│   │   ├── pgsql.py
│   │   ├── sqlite.py
│   │   └── _base.py  # Basic SQL functionality
│   ├── nosql/        # MongoDB, Firestore, Redis
│   ├── storage/      # S3, GCS, Azure, file storage
│   ├── secret/       # Secret management (Infisical, GCP Secret Manager)
│   ├── monitoring/   # Sentry, Logfire
│   └── ...
├── config.py         # Configuration system with simple hot-reloading
├── depends.py        # Dependency injection framework
├── logger.py         # Logging system
└── debug.py          # Debugging utilities
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

ACB uses a comprehensive metadata system for adapter identification, capability discovery, and version management. Each adapter should include a `MODULE_METADATA` constant with standardized information.

#### Core Metadata Schema

```python
from acb.adapters import (
    AdapterMetadata,
    AdapterStatus,
    AdapterCapability,
    generate_adapter_id,
)

# Required metadata for all adapters
MODULE_METADATA = AdapterMetadata(
    module_id=generate_adapter_id(),  # UUID7 identifier (persistent)
    name="Redis Cache",  # Human-readable name
    category="cache",  # Adapter category
    provider="redis",  # Technology provider
    version="1.0.0",  # Semantic version (independent of ACB)
    acb_min_version="0.18.0",  # Minimum ACB version required
    acb_max_version="2.0.0",  # Maximum ACB version supported
    author="Developer <dev@example.com>",  # Primary maintainer
    created_date="2025-01-12",  # ISO date of creation
    last_modified="2025-01-12",  # ISO date of last modification
    status=AdapterStatus.STABLE,  # Development status
    capabilities=[  # Feature capabilities
        AdapterCapability.ASYNC_OPERATIONS,
        AdapterCapability.CONNECTION_POOLING,
        AdapterCapability.CACHING,
    ],
    required_packages=["redis>=4.0.0"],  # Required dependencies
    optional_packages=["hiredis>=2.0.0"],  # Optional dependencies
    description="High-performance Redis caching adapter",
    documentation_url="https://docs.example.com/redis-cache",
    repository_url="https://github.com/example/redis-adapter",
    settings_class="CacheSettings",  # Configuration class name
    config_example={  # Example configuration
        "host": "localhost",
        "port": 6379,
        "db": 0,
    },
    custom={"custom_field": "value"},  # Custom metadata fields
)
```

#### Adapter Status Levels

```python
class AdapterStatus(Enum):
    ALPHA = "alpha"  # Early development, breaking changes expected
    BETA = "beta"  # Feature complete, may have bugs
    STABLE = "stable"  # Production ready
    DEPRECATED = "deprecated"  # Scheduled for removal
    EXPERIMENTAL = "experimental"  # Proof of concept
```

#### Adapter Capabilities

The capability system enables runtime feature detection:

```python
# Connection Management
AdapterCapability.CONNECTION_POOLING  # Supports connection pooling
AdapterCapability.RECONNECTION  # Auto-reconnection support

# Data Operations
AdapterCapability.TRANSACTIONS  # Transaction support
AdapterCapability.BULK_OPERATIONS  # Batch operations
AdapterCapability.STREAMING  # Streaming data support
AdapterCapability.COMPRESSION  # Data compression
AdapterCapability.ENCRYPTION  # Encryption support

# Performance
AdapterCapability.CACHING  # Built-in caching
AdapterCapability.ASYNC_OPERATIONS  # Async/await support
AdapterCapability.BATCHING  # Request batching

AdapterCapability.LOGGING  # Structured logging

# Schema Management
AdapterCapability.SCHEMA_VALIDATION  # Schema validation
AdapterCapability.MIGRATIONS  # Database migrations
AdapterCapability.BACKUP_RESTORE  # Backup/restore operations
```

#### Metadata Utility Functions

```python
from acb.adapters import (
    generate_adapter_id,
    create_metadata_template,
    extract_metadata_from_module,
    validate_version_compatibility,
    check_adapter_capability,
    generate_adapter_report,
)

# Generate unique adapter ID
adapter_id = generate_adapter_id()

# Create template for new adapter
template = create_metadata_template(
    name="My Adapter", category="storage", provider="custom"
)

# Extract metadata from adapter module
metadata = extract_metadata_from_module(adapter_module)

# Check version compatibility
is_compatible = validate_version_compatibility(metadata, "0.19.0")

# Check for specific capability
has_pooling = check_adapter_capability(adapter, AdapterCapability.CONNECTION_POOLING)

# Generate comprehensive adapter report
report = generate_adapter_report(adapter_class)
```

#### Usage in Adapter Development

When implementing new adapters, always include metadata:

```python
# my_adapter.py
from acb.adapters import AdapterMetadata, AdapterStatus, AdapterCapability

MODULE_METADATA = AdapterMetadata(
    module_id="01234567-89ab-cdef-0123-456789abcdef",
    name="Custom Storage",
    category="storage",
    provider="custom",
    version="0.1.0",
    acb_min_version="0.19.0",
    author="Your Name <your.email@example.com>",
    created_date="2025-01-14",
    last_modified="2025-01-14",
    status=AdapterStatus.BETA,
    capabilities=[
        AdapterCapability.ASYNC_OPERATIONS,
        AdapterCapability.ENCRYPTION,
    ],
    required_packages=["custom-storage>=1.0.0"],
    description="Custom storage adapter with encryption",
    settings_class="CustomStorageSettings",
)


class Storage:
    # Adapter implementation
    pass
```

#### Benefits of Metadata System

1. **Unique Identification**: Each adapter has a persistent UUID7 identifier
1. **Version Tracking**: Independent versioning from ACB core
1. **Capability Discovery**: Runtime feature detection and validation
1. **Compatibility Checking**: Automatic version requirement validation
1. **Debugging Support**: Comprehensive adapter information for troubleshooting
1. **Template System**: Standardized adapter development workflow
1. **Documentation**: Built-in documentation and examples

### Simplified Architecture (v0.19.3+)

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


# FastBlocks HTTPEndpoint Pattern (from FastBlocks GEMINI.md)
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

When generating code, AI assistants MUST follow these standards to ensure compliance with Refurb and Bandit pre-commit hooks:

**IMPORTANT: Target Python 3.13+** - All code should be compatible with Python 3.13 or newer when possible. Use modern Python features and syntax.

### Refurb Standards (Modern Python Patterns)

**Use modern syntax and built-ins:**

- Use `pathlib.Path` instead of `os.path` operations
- Use `str.removeprefix()` and `str.removesuffix()` instead of string slicing
- Use `itertools.batched()` for chunking sequences (Python 3.12+)
- Prefer `match` statements over complex `if/elif` chains
- Use `|` for union types instead of `Union` from typing
- Use `dict1 | dict2` for merging instead of `{**dict1, **dict2}`

**Example of good patterns:**

```python
# Good: Modern pathlib usage
from pathlib import Path

config_file = Path("config") / "settings.yaml"
if config_file.exists():
    content = config_file.read_text(encoding="utf-8")

# Good: String methods
if name.startswith("test_"):
    name = name.removeprefix("test_")


# Good: Union types
def process_data(data: str | bytes) -> dict[str, Any]:
    pass


# Good: Context managers
with open(file_path, encoding="utf-8") as f:
    data = f.read()
```

**Use efficient built-in functions:**

- Use `any()` and `all()` instead of manual boolean loops
- Use list/dict comprehensions over manual loops when appropriate
- Use `enumerate()` instead of manual indexing with `range(len())`
- Use `zip()` for parallel iteration instead of manual indexing

**Resource management:**

- Always use context managers (`with` statements) for file operations
- Use `tempfile` module for temporary files instead of manual paths
- Prefer `subprocess.run()` over `subprocess.Popen()` when possible

### Bandit Code Security Standards

**Never use dangerous functions:**

- Avoid `eval()`, `exec()`, or `compile()` with any user input
- Never use `subprocess.shell=True` or `os.system()`
- Don't use `pickle` with untrusted data
- Avoid `yaml.load()` - use `yaml.safe_load()` instead

**Cryptography and secrets:**

- Use `secrets` module for cryptographic operations, never `random`
- Never hardcode passwords, API keys, or secrets in source code
- Use environment variables or secure configuration for sensitive data
- Use `hashlib` with explicit algorithms, avoid MD5/SHA1 for security

**File and path security:**

- Always validate file paths to prevent directory traversal
- Use `tempfile.mkstemp()` instead of predictable temporary file names
- Always specify encoding when opening files
- Validate all external inputs before processing

**Database and injection prevention:**

- Use parameterized queries, never string concatenation for SQL
- Validate and sanitize all user inputs
- Use prepared statements for database operations

**Example of secure patterns:**

```python
# Good: Secure random generation
import secrets

token = secrets.token_urlsafe(32)

# Good: Safe subprocess usage
import subprocess

result = subprocess.run(["ls", "-la"], capture_output=True, text=True)

# Good: Secure file operations
import tempfile

with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", delete=False) as f:
    f.write(data)
    temp_path = f.name

# Good: Environment variables for secrets
import os

api_key = os.environ.get("API_KEY")
if not api_key:
    raise ValueError("API_KEY environment variable required")

# Good: Parameterized database queries
cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
```

### Pyright Type Safety Standards

**Always use explicit type annotations:**

- Function parameters must have type hints
- Function return types must be annotated
- Class attributes should have type annotations
- Use `from __future__ import annotations` for forward references

**Handle Optional types properly:**

- Use `str | None` instead of `Optional[str]` when possible
- Always check for None before using optional values
- Use explicit `assert` statements or type guards when narrowing types

**Generic types and collections:**

- Use `list[str]` instead of `List[str]` when possible
- Use `dict[str, Any]` instead of `Dict[str, Any]` when possible
- Properly type generic classes with `TypeVar` when needed
- Use `Sequence` or `Iterable` for function parameters when appropriate

**Protocol and ABC usage:**

- Prefer `typing.Protocol` over abstract base classes for duck typing
- Use `@runtime_checkable` when protocols need runtime checks
- Define clear interfaces with protocols

**Example of proper typing:**

```python
from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable
from pathlib import Path

if TYPE_CHECKING:
    from collections.abc import Sequence


@runtime_checkable
class Writable(Protocol):
    def write(self, data: str) -> None: ...


def process_files(
    paths: Sequence[Path],
    output: Writable,
    encoding: str = "utf-8",
) -> dict[str, int]:
    """Process files and return statistics."""
    stats: dict[str, int] = {}

    for path in paths:
        if path.exists():
            content = path.read_text(encoding=encoding)
            stats[str(path)] = len(content)
            output.write(f"Processed {path}\n")

    return stats


# Good: Type narrowing with assertion
def validate_config(config: dict[str, str | None]) -> dict[str, str]:
    """Validate that all config values are non-None."""
    validated: dict[str, str] = {}
    for key, value in config.items():
        assert value is not None, f"Config key {key} cannot be None"
        validated[key] = value
    return validated
```

### Integration with Pre-commit Hooks

These standards align with the project's pre-commit hooks:

- **Refurb**: Automatically suggests modern Python patterns
- **Bandit**: Scans for security vulnerabilities
- **Pyright**: Enforces type safety
- **Ruff**: Handles formatting and additional linting
- **pyproject-fmt**: Validates and formats pyproject.toml files
- **Vulture**: Detects unused code (dead code detection)
- **Creosote**: Identifies unused dependencies
- **Complexipy**: Analyzes code complexity
- **Autotyping**: Automatically adds type annotations
- **Codespell**: Fixes common spelling mistakes
- **Detect-secrets**: Prevents credential leaks
- **Standard hooks**: File formatting (trailing whitespace, end-of-file fixes, YAML/TOML validation)

By following these guidelines during code generation, AI assistants will produce code that passes all quality checks without requiring manual fixes.

### Tool Configuration in pyproject.toml

Key tool configurations:

- **Ruff**: Target Python 3.13, line length 88, auto-fix enabled
- **Pytest**: Auto-discover tests, 300s timeout, coverage fail under 42%
- **Pyright**: Strict mode with some relaxed settings for practicality
- **Coverage**: Branch coverage disabled, exclude test files
- **Bandit**: Security scanning with some practical skips
- **Vulture**: Dead code detection with 86% confidence threshold

## Project Structure Details

### Directory Layout

```
acb/
├── __init__.py            # Package initialization and registration
├── actions/               # Self-contained utility functions
│   ├── compress/          # Compression utilities (gzip, brotli)
│   ├── encode/            # Encoding/decoding (JSON, YAML, TOML, MsgPack)
│   └── hash/              # Hashing utilities (blake3, crc32c, md5)
├── adapters/              # External system integrations
│   ├── cache/             # Caching adapters (memory, redis)
│   ├── dns/               # DNS management (Cloud DNS, Cloudflare, Route53)
│   ├── ftpd/              # File transfer (FTP, SFTP)
│   ├── models/            # Model framework support (SQLModel, Pydantic, etc.)
│   ├── monitoring/        # Monitoring (Sentry, Logfire)
│   ├── nosql/             # NoSQL databases (MongoDB, Firestore, Redis)
│   ├── requests/          # HTTP clients (HTTPX, Niquests)
│   ├── secret/            # Secret management (Infisical, GCP, Azure, Cloudflare)
│   ├── smtp/              # Email sending (Gmail, Mailgun)
│   ├── sql/               # SQL databases (MySQL, PostgreSQL, SQLite)
│   └── storage/           # File storage (S3, GCS, Azure, file, memory)
├── config.py              # Configuration system using Pydantic
├── depends.py             # Dependency injection framework
├── logger.py              # Logging system
└── debug.py               # Debugging utilities
```

### Settings Directory Structure

```
settings/
├── app.yml                # Application settings (name, version, domain)
├── debug.yml              # Debug configuration
├── adapters.yml           # Adapter implementation selection
├── models.yml             # Models framework configuration
└── secrets/               # Secret files (not committed to version control)
```

**Note**: The `/settings/` directory is gitignored in ACB itself and should only be created by consuming applications. When developing ACB itself, test configurations should use mocked settings.

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

### Current Version: 0.19.3

Key improvements in v0.19.3:

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

- **Latest Version**: 0.19.3
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

## Documentation and Testing Audit Requirements

**MANDATORY: AI assistants must regularly audit documentation and tests for consistency, accuracy, and obsolete information.**

### Documentation Audit Checklist

When working on significant changes or upon request, AI assistants MUST:

1. **Package Manager Consistency**: Ensure all installation commands use UV (not PDM)
1. **Python Version Accuracy**: Verify all documentation reflects Python 3.13+ requirement
1. **Cross-Project References**: Check that ACB ↔ FastBlocks links are accurate
1. **Command Accuracy**: Verify all CLI commands and code examples work with current versions
1. **URL Validation**: Ensure GitHub URLs point to correct organizations and repositories
1. **Version Information**: Update any outdated version requirements or compatibility information
1. **Workflow Currency**: Remove or update obsolete development workflows and processes

### Testing Audit Checklist

1. **Test Coverage**: Ensure tests cover new features and changes
1. **Mock Accuracy**: Verify mocks match current adapter interfaces
1. **Integration Tests**: Check that tests work with current ACB adapter system
1. **CI/CD Commands**: Verify automated testing commands are current
1. **Quality Gates**: Ensure all quality checks (ruff, pyright, crackerjack) pass

### Regular Audit Triggers

Perform comprehensive audits when:

- Making significant architectural changes
- Updating major dependencies
- Changing development tooling (package managers, linters, etc.)
- Releasing new versions
- Upon explicit request for documentation review

### Audit Documentation

When completing an audit, document:

- **Files audited**: List all documentation files reviewed
- **Issues found**: Specific inconsistencies, inaccuracies, or obsolete information
- **Changes made**: Summary of updates and fixes
- **Verification**: Confirmation that examples and commands were tested

This ensures ACB documentation remains current, accurate, and helpful for developers.

## Common Issues and Solutions

### Secret Detection False Positives

When working with config examples containing placeholder passwords, add the pragma comment to prevent detect-secrets hook failures:

```python
config_example = {
    "host": "localhost",
    "password": "your-db-password",  # pragma: allowlist secret
}
```

### Adapter Field Type Methods

Always return `Any` (not `type(Any)`) from adapter field type methods for missing fields:

```python
def get_field_type(self, model_class: type[T], field_name: str) -> type:
    # Wrong: return type(Any)
    # Correct: return Any
    return Any
```

### Mock Configuration in Tests

Ensure test mocks include all required attributes. For SQLite Turso adapter tests, include:

```python
mock_sql.ssl_enabled = True  # Required for SSL status logging
```

### Quick Troubleshooting

**Adapter not loading**: Check `settings/adapters.yml` configuration
**Import errors**: Ensure optional dependencies installed with `uv add "acb[adapter_name]"`
**Test failures**: Use provided test fixtures and mock patterns
**Configuration issues**: Verify YAML syntax and environment variables
**Performance issues**: Enable connection pooling and lazy loading patterns

1. **ModuleNotFoundError: No module named 'acb'**

   - Solution: Install ACB with `uv add acb`

1. **Adapter not found errors (e.g., KeyError: 'cache')**

   - Ensure adapter is configured in `settings/adapters.yml`
   - Install optional dependencies: `uv add "acb[cache]"`

1. **Python version errors**

   - ACB requires Python 3.13+
   - Check with `python --version`

1. **Configuration file errors**

   - Create required structure: `mkdir -p settings`
   - Check YAML syntax (use spaces not tabs, space after colons)

1. **Async test issues**

   - Use `@pytest.mark.asyncio` decorator
   - Use proper async fixtures from conftest.py

1. **Performance issues**

   - Enable debug mode in `settings/debug.yml`
   - Use connection pooling for database adapters
   - Check cache TTL settings

For detailed troubleshooting, see `docs/TROUBLESHOOTING.md`.

## Critical Development Rules

**MANDATORY: Follow these rules exactly:**

- Do what has been asked; nothing more, nothing less
- NEVER create files unless they're absolutely necessary for achieving your goal
- ALWAYS prefer editing an existing file to creating a new one
- NEVER proactively create documentation files (\*.md) or README files unless explicitly requested
- When working with secrets in config examples, add `# pragma: allowlist secret` comments
- Always return `Any` (not `type(Any)`) from adapter field type methods for missing fields
