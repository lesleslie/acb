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
python -m crackerjack --ai-agent               # Run with AI assistance
```

### Package Management
```bash
# Install development dependencies
pdm install -G dev

# Install with specific adapter groups
pdm add "acb[cache,sql,storage]"  # Common web app stack
pdm add "acb[all]"                # All optional dependencies

# Add development dependency
pdm add -G dev <package>
```

## Architecture Overview

ACB (Asynchronous Component Base) is a modular Python framework with a component-based architecture built around **actions**, **adapters**, and **dependency injection**.

### Core Design Patterns

1. **Adapter Pattern**: All external integrations use standardized interfaces with pluggable implementations
2. **Dependency Injection**: Components are automatically wired together using the `bevy` framework
3. **Configuration-Driven**: Behavior is controlled through YAML configuration files
4. **Async-First**: Built for high-performance asynchronous operations

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
    async def public_method(self, *args, **kwargs):
        # Public methods delegate to private implementation
        return await self._public_method(*args, **kwargs)

    async def _public_method(self, *args, **kwargs):
        # Private method contains actual implementation
        client = await self._ensure_client()
        # Implementation logic here

    async def _ensure_client(self):
        # Lazy client initialization pattern
        if self._client is None:
            self._client = await self._create_client()
        return self._client
```

## Configuration System

### Settings Structure
```
settings/
├── app.yml          # Application settings (name, version, domain)
├── debug.yml        # Debug configuration
├── adapters.yml     # Adapter implementation selection
└── secrets/         # Secret files (not committed)
```

### Adapter Selection
Configure which implementations to use in `settings/adapters.yml`:
```yaml
cache: redis        # or: memory
storage: s3         # or: file, gcs, azure
sql: postgresql     # or: mysql
```

### Dependency Injection Usage
```python
from acb.depends import depends
from acb.adapters import import_adapter

# Import adapter classes (not instances)
Cache, Storage = import_adapter("cache", "storage")

@depends.inject
async def my_function(
    cache: Cache = depends(),
    storage: Storage = depends(),
    config: Config = depends()
):
    # Dependencies automatically injected
    pass
```

## Testing Guidelines

### Mock Implementation Requirements
- Mock classes must match real adapter signatures
- Implement proper public/private method delegation
- Mock async context managers need both `__aenter__` and `__aexit__`
- Clear cached properties before tests: `del adapter.property_name`

### Test Organization
- Base test files: `test_<category>_base.py` (shared fixtures, base tests)
- Implementation tests: `test_<implementation>.py` (specific behavior)
- Use pytest markers: `@pytest.mark.unit`, `@pytest.mark.integration`

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
- **sql**: MySQL, PostgreSQL (SQLAlchemy, SQLModel)
- **nosql**: MongoDB, Firestore, Redis
- **storage**: File, S3, GCS, Azure
- **secret**: Infisical, GCP Secret Manager
- **monitoring**: Sentry, Logfire
- **requests**: HTTPX, Niquests
- **smtp**: Gmail, Mailgun
- **dns**: Cloud DNS, Cloudflare

## Development Workflow

1. **Setup**: `pdm install -G dev`
2. **Code**: Follow adapter patterns and async interfaces
3. **Test**: Write tests with proper mocking
4. **Quality**: Use ruff for formatting and pyright for type checking
5. **Automation**: Use crackerjack for comprehensive workflows

## Important Rules from .windsurfrules

- Always implement adapter pattern with public/private method delegation
- Use `_ensure_client()` pattern for lazy connection initialization
- Mock classes must mirror real implementation signatures
- Follow consistent async interfaces across all adapters
- Group dependencies by adapter type in pyproject.toml
- Use ACB settings pattern for component configuration
- Implement proper error handling with appropriate exception types
