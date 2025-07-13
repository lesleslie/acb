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
├── models.yml       # Models framework configuration (SQLModel, Pydantic, Redis-OM)
└── secrets/         # Secret files (not committed)
```

### Adapter Selection
Configure which implementations to use in `settings/adapters.yml`:
```yaml
cache: redis        # or: memory
storage: s3         # or: file, gcs, azure
sql: postgresql     # or: mysql
models: true        # Enable models adapter (auto-detects model types)
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
- **models**: SQLModel, Pydantic, Redis-OM (auto-detection, universal query interface)
- **sql**: MySQL, PostgreSQL (SQLAlchemy, SQLModel)
- **nosql**: MongoDB, Firestore, Redis
- **storage**: File, S3, GCS, Azure
- **secret**: Infisical, GCP Secret Manager
- **monitoring**: Sentry, Logfire
- **requests**: HTTPX, Niquests
- **smtp**: Gmail, Mailgun
- **dns**: Cloud DNS, Cloudflare

## Development Workflow

1. **Setup**: `uv sync --group dev`
2. **Code**: Follow adapter patterns and async interfaces
3. **Test**: Write tests with proper mocking
4. **Quality**: Use ruff for formatting and pyright for type checking
5. **Verification**: **MANDATORY** - Run `python -m crackerjack -t --ai-agent` before task completion
6. **Automation**: Use crackerjack for comprehensive workflows

## Code Quality Compliance

When generating code, AI assistants MUST follow these standards to ensure compliance with Refurb and Bandit pre-commit hooks:

**IMPORTANT: Target Python 3.12+** - All code should be compatible with Python 3.12 or newer when possible. Use modern Python features and syntax.

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
