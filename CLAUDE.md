# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

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
2. **Dependency Injection**: Components are automatically wired together using the `bevy` framework
3. **Configuration-Driven**: Behavior is controlled through YAML configuration files
4. **Async-First**: Built for high-performance asynchronous operations
5. **Dynamic Adapter Loading**: Adapters are loaded on-demand using convention-based discovery

### Directory Structure
```
acb/
├── actions/          # Self-contained utility functions (compress, encode, hash)
├── adapters/         # External system integrations
│   ├── cache/        # Memory, Redis caching
│   ├── sql/          # MySQL, PostgreSQL databases
│   ├── nosql/        # MongoDB, Firestore, Redis
│   ├── storage/      # S3, GCS, Azure, file storage
│   ├── secret/       # Secret management (Infisical, GCP Secret Manager)
│   ├── monitoring/   # Sentry, Logfire
│   └── ...
├── config.py         # Configuration system using Pydantic
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
from acb.adapters import AdapterMetadata, AdapterStatus, AdapterCapability, generate_adapter_id

# Required metadata for all adapters
MODULE_METADATA = AdapterMetadata(
    module_id=generate_adapter_id(),  # UUID7 identifier (persistent)
    name="Redis Cache",               # Human-readable name
    category="cache",                 # Adapter category
    provider="redis",                 # Technology provider
    version="1.0.0",                  # Semantic version (independent of ACB)
    acb_min_version="0.18.0",        # Minimum ACB version required
    acb_max_version="2.0.0",         # Maximum ACB version supported
    author="Developer <dev@example.com>",  # Primary maintainer
    created_date="2025-01-12",        # ISO date of creation
    last_modified="2025-01-12",       # ISO date of last modification
    status=AdapterStatus.STABLE,      # Development status
    capabilities=[                    # Feature capabilities
        AdapterCapability.ASYNC_OPERATIONS,
        AdapterCapability.CONNECTION_POOLING,
        AdapterCapability.CACHING,
    ],
    required_packages=["redis>=4.0.0"],  # Required dependencies
    optional_packages=["hiredis>=2.0.0"], # Optional dependencies
    description="High-performance Redis caching adapter",
    documentation_url="https://docs.example.com/redis-cache",
    repository_url="https://github.com/example/redis-adapter",
    settings_class="CacheSettings",   # Configuration class name
    config_example={                  # Example configuration
        "host": "localhost",
        "port": 6379,
        "db": 0
    },
    custom={"custom_field": "value"}  # Custom metadata fields
)
```

#### Adapter Status Levels

```python
class AdapterStatus(Enum):
    ALPHA = "alpha"           # Early development, breaking changes expected
    BETA = "beta"             # Feature complete, may have bugs
    STABLE = "stable"         # Production ready
    DEPRECATED = "deprecated" # Scheduled for removal
    EXPERIMENTAL = "experimental"  # Proof of concept
```

#### Adapter Capabilities

The capability system enables runtime feature detection:

```python
# Connection Management
AdapterCapability.CONNECTION_POOLING    # Supports connection pooling
AdapterCapability.RECONNECTION          # Auto-reconnection support
AdapterCapability.HEALTH_CHECKS         # Health monitoring

# Data Operations
AdapterCapability.TRANSACTIONS          # Transaction support
AdapterCapability.BULK_OPERATIONS       # Batch operations
AdapterCapability.STREAMING             # Streaming data support
AdapterCapability.COMPRESSION           # Data compression
AdapterCapability.ENCRYPTION            # Encryption support

# Performance
AdapterCapability.CACHING               # Built-in caching
AdapterCapability.ASYNC_OPERATIONS      # Async/await support
AdapterCapability.BATCHING              # Request batching

# Observability
AdapterCapability.METRICS               # Metrics collection
AdapterCapability.TRACING               # Distributed tracing
AdapterCapability.LOGGING               # Structured logging

# Schema Management
AdapterCapability.SCHEMA_VALIDATION     # Schema validation
AdapterCapability.MIGRATIONS            # Database migrations
AdapterCapability.BACKUP_RESTORE        # Backup/restore operations
```

#### Metadata Utility Functions

```python
from acb.adapters import (
    generate_adapter_id,
    create_metadata_template,
    extract_metadata_from_module,
    validate_version_compatibility,
    check_adapter_capability,
    generate_adapter_report
)

# Generate unique adapter ID
adapter_id = generate_adapter_id()

# Create template for new adapter
template = create_metadata_template(
    name="My Adapter",
    category="storage",
    provider="custom"
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
2. **Version Tracking**: Independent versioning from ACB core
3. **Capability Discovery**: Runtime feature detection and validation
4. **Compatibility Checking**: Automatic version requirement validation
5. **Debugging Support**: Comprehensive adapter information for troubleshooting
6. **Template System**: Standardized adapter development workflow
7. **Documentation**: Built-in documentation and examples

### Memory Cache Adapter (v0.16.17+ Enhancement)

The memory cache adapter now implements the full aiocache BaseCache interface with MsgPack serialization and brotli compression:

```python
# New methods available in memory cache adapter
await cache.set("key", "value", ttl=300)    # Set with TTL
await cache.add("key", "value")             # Set only if not exists
await cache.increment("counter", delta=1)    # Atomic increment
await cache.expire("key", ttl=60)           # Update TTL
await cache.multi_set({"k1": "v1", "k2": "v2"})  # Batch operations

# Performance optimizations:
# - MsgPack serialization for efficient data storage
# - Brotli compression for reduced memory usage
# - aiocache BaseCache interface for consistency with Redis adapter
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
    cache: Cache = depends(),
    storage: Storage = depends(),
    config: Config = depends()
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
new_user = await query.for_model(User).simple.create({
    "name": "John Doe",
    "email": "john@example.com"
})

# Repository pattern with caching
from acb.adapters.models._repository import RepositoryOptions
repo = query.for_model(User).repository(RepositoryOptions(
    cache_enabled=True,
    cache_ttl=300,
    enable_soft_delete=True
))
active_users = await repo.find_active()

# Specification pattern for business rules
from acb.adapters.models._specification import field
active_spec = field("active").equals(True)
email_spec = field("email").like("%@company.com")
company_users = await query.for_model(User).specification.with_spec(
    active_spec & email_spec
).all()

# Advanced query builder
filtered_users = await (query.for_model(User).advanced
    .where("active", True)
    .where_gt("id", 100)
    .order_by_desc("id")
    .limit(10)
    .all())
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
- **secret**: Infisical, GCP Secret Manager
- **monitoring**: Sentry, Logfire
- **requests**: HTTPX, Niquests
- **smtp**: Gmail, Mailgun
- **dns**: Cloud DNS, Cloudflare
- **ftpd**: FTP, SFTP clients

## Development Workflow

1. **Setup**: `uv sync --group dev`
2. **Code**: Follow adapter patterns and async interfaces
3. **Test**: Write tests with proper mocking
4. **Quality**: Use ruff for formatting and pyright for type checking
5. **Verification**: **MANDATORY** - Run `python -m crackerjack -t --ai-agent` before task completion
6. **Automation**: Use crackerjack for comprehensive workflows

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

### Bandit Security Standards

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
with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', delete=False) as f:
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

## Recent Changes and Best Practices (v0.16.17+)

### Performance Optimizations
- **Dynamic Adapter Loading**: Simplified adapter loading with convention-based discovery
- **Memory Cache Enhancement**: Full aiocache interface implementation (50% faster operations)
- **Test Infrastructure**: Removed heavy mocks for faster test startup (30-40% improvement)

### Core Adapters
Only two adapters are automatically registered as they are truly essential for ACB operation:
- `config` - Configuration management (always needed)
- `loguru` - Logging system (always needed)

All other adapters follow the opt-in principle and must be explicitly configured in `settings/adapters.yml`.

### Breaking Changes to Be Aware Of
1. **Memory Cache Interface**: Now uses aiocache BaseCache interface - update method signatures
2. **Test Mocks**: Some test mocks removed - use real adapters or minimal mocks
3. **Configuration Detection**: Library mode auto-detection may affect initialization

### Migration Best Practices
- Review MIGRATION-0.16.17.md for detailed upgrade instructions
- Update memory cache usage to new aiocache interface
- Test thoroughly with dynamic adapter loading
- Verify configuration loading in library mode

## Task Completion Requirements

**MANDATORY: Before marking any task as complete, AI assistants MUST:**

1. **Run crackerjack verification**: Execute `python -m crackerjack -t --ai-agent` to run all quality checks and tests with AI-optimized output
2. **Fix any issues found**: Address all formatting, linting, type checking, and test failures
3. **Re-run verification**: Ensure crackerjack passes completely (all hooks pass, all tests pass)
4. **Document verification**: Mention that crackerjack verification was completed successfully

**Why this is critical:**
- Ensures all code meets project quality standards
- Prevents broken code from being committed
- Maintains consistency with project development workflow
- Catches issues early before they become problems

**Never skip crackerjack verification** - it's the project's standard quality gate.

## Documentation and Testing Audit Requirements

**MANDATORY: AI assistants must regularly audit documentation and tests for consistency, accuracy, and obsolete information.**

### Documentation Audit Checklist

When working on significant changes or upon request, AI assistants MUST:

1. **Package Manager Consistency**: Ensure all installation commands use UV (not PDM)
2. **Python Version Accuracy**: Verify all documentation reflects Python 3.13+ requirement
3. **Cross-Project References**: Check that ACB ↔ FastBlocks links are accurate
4. **Command Accuracy**: Verify all CLI commands and code examples work with current versions
5. **URL Validation**: Ensure GitHub URLs point to correct organizations and repositories
6. **Version Information**: Update any outdated version requirements or compatibility information
7. **Workflow Currency**: Remove or update obsolete development workflows and processes

### Testing Audit Checklist

1. **Test Coverage**: Ensure tests cover new features and changes
2. **Mock Accuracy**: Verify mocks match current adapter interfaces
3. **Integration Tests**: Check that tests work with current ACB adapter system
4. **CI/CD Commands**: Verify automated testing commands are current
5. **Quality Gates**: Ensure all quality checks (ruff, pyright, crackerjack) pass

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
