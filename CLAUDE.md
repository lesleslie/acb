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

### Memory Cache Adapter (v0.16.17+ Enhancement)

The memory cache adapter now implements the full aiocache BaseCache interface:

```python
# New methods available in memory cache adapter
await cache.set("key", "value", ttl=300)    # Set with TTL
await cache.add("key", "value")             # Set only if not exists
await cache.increment("counter", delta=1)    # Atomic increment
await cache.expire("key", ttl=60)           # Update TTL
await cache.multi_set({"k1": "v1", "k2": "v2"})  # Batch operations
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
```

### Configuration Library Mode Detection (v0.16.17+)

ACB now automatically detects when it's being used as a library vs application:

```python
# ACB detects library usage in these contexts:
# - During pip install
# - In setup.py execution
# - During build processes
# - In test contexts

# Manual override if needed:
import os
os.environ["ACB_LIBRARY_MODE"] = "true"
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
5. **Verification**: **MANDATORY** - Run `python -m crackerjack -t --ai-agent` before task completion
6. **Automation**: Use crackerjack for comprehensive workflows

## Code Quality Compliance

When generating code, AI assistants MUST follow these standards to ensure compliance with Refurb and Bandit pre-commit hooks:

### Refurb Standards (Modern Python Patterns)

**Use modern syntax and built-ins:**
- Use `pathlib.Path` instead of `os.path` operations
- Use `str.removeprefix()` and `str.removesuffix()` instead of string slicing
- Use `itertools.batched()` for chunking sequences (Python 3.12+)
- Prefer `match` statements over complex `if/elif` chains
- Use `|` for union types instead of `Union` from typing
- Use `dict1 | dict2` for merging instead of `{**dict1, **dict2}`

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

### Integration with Pre-commit Hooks

These standards align with the project's pre-commit hooks:
- **Refurb**: Automatically suggests modern Python patterns
- **Bandit**: Scans for security vulnerabilities
- **Pyright**: Enforces type safety
- **Ruff**: Handles formatting and additional linting

By following these guidelines during code generation, AI assistants will produce code that passes all quality checks without requiring manual fixes.

## Important Rules from .windsurfrules

- Always implement adapter pattern with public/private method delegation
- Use `_ensure_client()` pattern for lazy connection initialization
- Mock classes must mirror real implementation signatures
- Follow consistent async interfaces across all adapters
- Group dependencies by adapter type in pyproject.toml
- Use ACB settings pattern for component configuration
- Implement proper error handling with appropriate exception types

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
