# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Quick Reference

**Version**: 0.31.6 | **Python**: 3.13+ | **Featured**: [FastBlocks](https://github.com/lesleslie/fastblocks)

### Essential Commands

```bash
# Testing
python -m pytest                    # All tests
python -m pytest -m unit           # Unit tests only
python -m pytest --cov=acb         # With coverage

# Quality (MANDATORY before task completion)
python -m crackerjack -t --ai-fix  # Full verification
ruff check --fix && ruff format    # Lint & format
pyright                            # Type checking

# Package Management (UPDATED for v0.24.0)
uv sync --group dev                     # Install dev dependencies
uv add --group cache                    # Add single adapter
uv add --group cache --group sql        # Add multiple adapters
uv add --group webapp                   # Add composite group
```

## Architecture Overview

ACB (Asynchronous Component Base) is a modular Python framework built around **actions**, **adapters**, **services**, and **dependency injection**.

### Recent Breaking Changes (v0.24.0)

**CRITICAL**: Dependency installation syntax has changed:

- ❌ **Old (no longer works)**: `uv add "acb[cache]"`
- ✅ **New (required)**: `uv add --group cache`

All adapter installations now use the `--group` flag instead of extras syntax. See CHANGELOG.md for full migration details.

### Core Design Patterns

1. **Adapter Pattern**: Standardized interfaces for external systems (cache, SQL, storage, etc.)
1. **Dependency Injection**: Automatic component wiring via `bevy` framework
1. **Configuration-Driven**: YAML-based behavior control (`settings/`)
1. **Async-First**: High-performance asynchronous operations
1. **Dynamic Loading**: Convention-based adapter discovery

### Directory Structure (v0.19.1+)

```
acb/
├── actions/          # Utility functions (compress, encode, hash)
├── adapters/         # External system integrations
│   ├── cache/        # Memory, Redis (aiocache interface)
│   ├── sql/          # MySQL, PostgreSQL, SQLite
│   ├── storage/      # S3, GCS, Azure, file
│   ├── nosql/        # MongoDB, Firestore, Redis
│   ├── messaging/    # Memory, Redis, RabbitMQ (pub/sub + queue)
│   ├── models/       # SQLModel, Pydantic, msgspec, attrs
│   ├── secret/       # Infisical, GCP, Azure, Cloudflare
│   ├── monitoring/   # Sentry, Logfire
│   ├── requests/     # HTTPX, Niquests
│   ├── smtp/         # Gmail, Mailgun
│   ├── dns/          # Cloud DNS, Cloudflare, Route53
│   └── ftpd/         # FTP, SFTP
├── events/           # Event-driven messaging (uses pubsub)
├── tasks/            # Task queue system (uses queue)
├── cleanup.py        # Resource cleanup patterns
├── config.py         # Configuration with hot-reloading
├── context.py        # Centralized context management
├── depends.py        # Dependency injection
├── logger.py         # Loguru-based logging
└── ssl_config.py     # SSL/TLS configuration
```

### Comprehensive Architecture (v0.20.0+)

**Adapter Layer**: Clean interfaces for external systems with config-driven selection
**Services Layer**: Enterprise features (lifecycle, health monitoring, validation, workflows)
**Core Infrastructure**: Config, DI, logging, debugging, SSL/TLS
**MCP Integration**: Model Context Protocol server for AI application integration

### Available Services (v0.20.0+)

| Service | Location | Key Features |
|---------|----------|--------------|
| **Repository** | `acb.services.repository` | Unit of Work, query builder, specifications, caching |
| **Validation** | `acb.services.validation` | Schema validation, sanitization, coercion, decorators |
| **Performance** | `acb.services.performance` | Metrics, query optimization, cache optimization, serverless |
| **Health** | `acb.services.health` | Service health monitoring and status checks |
| **Registry** | `acb.services.registry` | Service discovery and registration |
| **State** | `acb.services.state` | State management and persistence |

### Adapter Implementation Pattern

```python
class ExampleAdapter:
    def __init__(self):
        self._client = None
        self._settings = None

    async def public_method(self, *args, **kwargs):
        return await self._public_method(*args, **kwargs)

    async def _public_method(self, *args, **kwargs):
        client = await self._ensure_client()
        # Implementation logic
        return result

    async def _ensure_client(self):
        if self._client is None:
            self._client = await self._create_client()
        return self._client

    async def _create_client(self):
        # Initialize client using self._settings
        return client_instance
```

**Key Points**: Public/private delegation, lazy initialization, `_ensure_client()` pattern

### Adapter Metadata Standard

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

## Configuration System

### Settings Structure

```
settings/
├── app.yml          # Application settings
├── debug.yml        # Debug configuration
├── adapters.yml     # Adapter selection (cache: redis, sql: postgresql, etc.)
├── models.yml       # Model frameworks (sqlmodel, pydantic, msgspec, attrs)
└── secrets/         # Secret files (not committed)
```

### Adapter Selection Example

```yaml
# settings/adapters.yml
cache: redis        # or: memory
storage: s3         # or: file, gcs, azure
sql: postgresql     # or: mysql, sqlite
models: true        # Enable models adapter
```

### Dependency Injection

```python
from acb.depends import depends, Inject
from acb.adapters import import_adapter
from acb.config import Config

Cache = import_adapter("cache")  # Concrete class
Storage = import_adapter("storage")


@depends.inject
async def my_function(
    cache: Inject[Cache], storage: Inject[Storage], config: Inject[Config]
):
    await cache.set("key", "value", ttl=300)
    await storage.upload("file.txt", data)
```

### Protocol-Based vs Concrete Class DI

**CRITICAL**: ACB uses different DI patterns for different layers.

#### Services Layer (Protocol-Based)

```python
from acb.services.protocols import RepositoryServiceProtocol, ValidationServiceProtocol


@depends.inject
async def business_logic(
    repo: Inject[RepositoryServiceProtocol],  # Protocol
    validator: Inject[ValidationServiceProtocol],
):
    async with repo.unit_of_work() as uow:
        entity = await repo.get("id")
        result = await validator.validate_business_rules(entity)
        if result["is_valid"]:
            await repo.save(entity, uow)
```

**Why Protocols**: Pure business logic, easy mocking, clear interfaces, better type checking

**Available Protocols**: `RepositoryServiceProtocol`, `ValidationServiceProtocol`, `PerformanceServiceProtocol`, `EventServiceProtocol`, `WorkflowServiceProtocol`

#### Adapters Layer (Concrete Classes)

```python
from acb.adapters import import_adapter

Cache = import_adapter("cache")  # Concrete class


@depends.inject
async def infrastructure_code(cache: Inject[Cache]):
    await cache.set("key", "value")
```

**Why Concrete**: Shared infrastructure (cleanup, SSL, pooling), config-driven, resource lifecycle

#### Decision Matrix

| Component | DI Pattern | Reason | Example |
|-----------|-----------|---------|---------|
| **Services** | `Inject[ServiceProtocol]` | Business logic, testing | `RepositoryServiceProtocol` |
| **Adapters** | `Inject[ConcreteClass]` | Infrastructure, config | `Cache`, `Storage`, `Sql` |
| **Core** | `Inject[ConcreteClass]` | Foundational | `Config`, `Logger` |

**For detailed examples**, see adapter-specific READMEs in `acb/adapters/*/README.md`

## Testing Guidelines

### Mock Requirements

- Match real adapter signatures
- Implement public/private delegation
- Mock async context managers need `__aenter__` and `__aexit__`
- Clear cached properties: `del adapter.property_name`

### Test Organization

- Use markers: `@pytest.mark.unit`, `@pytest.mark.integration`, `@pytest.mark.benchmark`
- Never create actual files - use provided mock fixtures
- Separate test classes for complex adapters

### Key Fixtures

- `mock_config`: Mocked Config for unit testing
- `real_config`: Real Config for integration tests
- `patch_file_operations`: File system mocking
- `patch_async_file_operations`: Async file system mocking

## Development Workflow

1. **Setup**: `uv sync --group dev`
1. **Code**: Follow adapter patterns and async interfaces
1. **Test**: Write tests with proper mocking
1. **Quality**: Use ruff for formatting, pyright for type checking
1. **Verification**: **MANDATORY** - Run `python -m crackerjack -t --ai-fix` before completion
1. **Automation**: Use crackerjack for comprehensive workflows

## Code Quality Compliance

**Python 3.13+** with modern syntax and security practices:

**Modern patterns**: `pathlib.Path`, `str.removeprefix()`, `|` unions, `dict1 | dict2`, comprehensions, `match` statements, type annotations

**Security**: Never use `eval()`, `exec()`, `subprocess.shell=True`, `pickle` with untrusted data. Use `secrets` module, parameterized queries, input validation

**Type safety**: Explicit hints, `str | None`, `list[str]`, `dict[str, Any]`, type narrowing with assertions

**Pre-commit hooks**: Refurb, Bandit, Pyright, Ruff, pyproject-fmt, Vulture, Creosote, Complexipy, Codespell, detect-secrets

## Version Information

### Current: 0.31.6

**Key improvements**:

- Comprehensive test coverage improvements and bug fixes (v0.29.x)
- Enhanced logger adapter with DI integration (v0.29.x)
- Model Context Protocol (MCP) server for AI integration
- Logly logger adapter with Rust-powered performance (v0.23.1)
- APScheduler queue adapter for enterprise task scheduling (v0.23.1)
- Modern dependency groups using `--group` syntax (v0.24.0)
- Comprehensive architecture with Services layer
- Basic resource cleanup via CleanupMixin
- Streamlined cache operations (aiocache interface)
- Performance improvements (50% faster operations)
- Universal query interface for models adapter

### Recent Changes (v0.16.17+)

- **Static Adapter Mappings**: Hardcoded mappings for better performance
- **Memory Cache Rewrite**: Full aiocache interface with MsgPack
- **Library Mode Detection**: Automatic library vs app detection
- **Performance**: 50-70% faster adapter loading, 30-40% faster tests

### Breaking Changes

1. **v0.24.0**: Dependency installation changed to `--group` syntax (CRITICAL)
1. **v0.16.17**: Memory cache now uses aiocache interface
1. **v0.16.17**: Some test mocks removed - use real adapters
1. **v0.16.17**: Library mode auto-detection may affect initialization

**Migration**: See `MIGRATION-0.24.0.md`, `MIGRATION-0.16.17.md`, and `CHANGELOG.md`

## Adapter Documentation

Each adapter has detailed README with examples:

- **[Cache](./acb/adapters/cache/README.md)**: Memory, Redis caching
- **[SQL](./acb/adapters/sql/README.md)**: MySQL, PostgreSQL, SQLite
- **[Storage](./acb/adapters/storage/README.md)**: S3, GCS, Azure, file
- **[Messaging](./acb/adapters/messaging/README.md)**: Memory, Redis, RabbitMQ
- **[Models](./acb/adapters/models/README.md)**: Universal query interface
- **[Secret](./acb/adapters/secret/README.md)**: Infisical, GCP, Azure, Cloudflare
- **[Monitoring](./acb/adapters/monitoring/README.md)**: Sentry, Logfire
- **[DNS](./acb/adapters/dns/README.md)**: Cloud DNS, Cloudflare, Route53
- **[SMTP](./acb/adapters/smtp/README.md)**: Gmail, Mailgun
- **[NoSQL](./acb/adapters/nosql/README.md)**: MongoDB, Firestore, Redis
- **[Requests](./acb/adapters/requests/README.md)**: HTTPX, Niquests
- **[FTPD](./acb/adapters/ftpd/README.md)**: FTP, SFTP

### Recent Adapter Additions

**Logly Logger** (v0.23.1): Rust-powered high-performance logging

- Install: `uv add --group logger`
- Config: `logger: logly` in settings/adapters.yml
- Features: Advanced compression (gzip, zstd), async callbacks, extended log levels
- Performance: Rust backend optimization for high-throughput scenarios

**APScheduler Queue** (v0.23.1): Enterprise-grade task scheduling

- Install: `uv add --group queue-apscheduler` (base) or variants with SQL/MongoDB/Redis
- Config: `queue: apscheduler` in settings/adapters.yml
- Features: Cron expressions, job persistence, clustering, dead letter queue
- Supports: Multiple job stores (memory, SQL, MongoDB, Redis) and executors

## Logging Output Strategy

**Version**: 0.29.2+ | **Default Behavior**: Human logs on stdout, structured logs only when `--debug` or an explicit env toggle is provided.

### Stream Configuration

ACB logger adapters (Loguru, Logly, Structlog) support dual-sink output:

- **stdout**: Human-readable formatted logs with colors (Rich/pretty printing)
- **stderr**: Structured JSON logs for AI/machine consumption (enabled by default)

### Default Behavior (v0.25.3+)

Structured logging is now opt-in to avoid JSON noise during normal or `-v/--verbose` runs. Enable it via `--debug` or the `ACB_FORCE_STRUCTURED_STDERR=1` (or `ACB_STRUCTURED_ONLY=1`) environment variable when machine-readable output is required:

```bash
# Humans see pretty logs on stdout; pass --debug for structured stderr
python -m acb.workflow --debug 2>structured.jsonl

# Later, AI can analyze the structured logs
jq -r 'select(.level=="ERROR") | .message' structured.jsonl
```

### Environment Variable Configuration

**Opt-out of stderr structured logging**:

```bash
ACB_DISABLE_STRUCTURED_STDERR=1 python -m acb.workflow
# Only stdout (human-readable) logs will be generated
```

**Stderr-only mode** (disable stdout):

```bash
ACB_STRUCTURED_ONLY=1 python -m acb.workflow 2>logs.jsonl
# Only JSON logs to stderr, no stdout output
```

**Enable OpenTelemetry trace context** (Phase 2):

```bash
ACB_ENABLE_OTEL=1 python -m acb.workflow 2>logs.jsonl
# JSON logs include trace_id and span_id fields
```

### JSON Log Format

Structured logs follow OpenTelemetry-compatible schema:

```json
{
  "timestamp": "2025-11-07T10:30:00.123456Z",
  "level": "INFO",
  "event": "acb.workflow.execute",
  "message": "Processing workflow step",
  "attributes": {
    "line": 42,
    "module": "acb.workflow",
    "correlation_id": "abc123",
    "custom_field": "value"
  },
  "version": "1.0.0",
  "trace_id": "a1b2c3d4e5f6...",  // Optional (if ACB_ENABLE_OTEL=1)
  "span_id": "1234567890abcdef"   // Optional (if ACB_ENABLE_OTEL=1)
}
```

### Configuration in settings/logger.yml

```yaml
logger:
  # Stdout configuration (human-readable)
  log_level: INFO
  colorize: true

  # Stderr structured logging (enabled by default)
  enable_stderr_sink: true  # Set to false to disable
  stderr_level: INFO
  stderr_format: json  # or "msgpack"

  # Advanced: Disable stdout, stderr-only
  disable_stdout_sink: false  # Set to true for stderr-only

  # OpenTelemetry integration (opt-in)
  enable_otel: false  # Set to true for trace context
  otel_trace_propagation: true
  otel_service_name: my-service  # Optional

  # Additional sinks (optional)
  additional_sinks:
    - type: file
      path: /var/log/app.log
      level: WARNING
      rotation: "1 day"
```

### Usage Scenarios

**Human Development**:

```bash
# Default - see pretty logs in terminal
python -m acb.workflow
```

**AI Analysis**:

```bash
# Capture JSON for post-processing
python -m acb.workflow 2>analysis.jsonl

# Filter errors
jq 'select(.level=="ERROR")' analysis.jsonl

# Extract metrics
jq '.attributes | select(.duration_ms)' analysis.jsonl
```

**Hybrid (Human + AI)**:

```bash
# Human watches stdout, AI gets stderr data
python -m acb.workflow 2>monitoring.jsonl &
tail -f monitoring.jsonl | jq -r '.message'  # AI monitoring
```

**CI/CD Pipelines**:

```bash
# Separate human logs from machine logs
python -m acb.workflow \
  > human_readable.log \
  2> structured.jsonl
```

### Why Stderr for Structured Logs?

1. **Stream Separation**: stdout = presentation, stderr = data
1. **Standard Practice**: nginx, systemd, many observability tools
1. **Easy Redirection**: `2>logs.jsonl` captures only structured data
1. **AI Parsing**: No Rich markup filtering needed
1. **Backward Compatible**: Opt-out available via environment variable

## Common Issues

**Quick fixes**:

- Adapter not loading → Check `settings/adapters.yml`, install with `uv add --group adapter_name`
- Import errors → Install ACB with `uv add acb`, verify Python 3.13+
- Config errors → Verify YAML syntax, create `settings/` structure
- Test failures → Use async fixtures, `@pytest.mark.asyncio` decorator
- Secret detection → Add `# pragma: allowlist secret` to examples
- **Dependency install fails** → Use `--group` syntax, not old extras syntax `[adapter]`

## Critical Development Rules

**MANDATORY**:

- Do what has been asked; nothing more, nothing less
- NEVER create files unless absolutely necessary
- ALWAYS prefer editing existing files
- NEVER proactively create documentation files unless explicitly requested
- Run `python -m crackerjack -t --ai-fix` before marking tasks complete
- When working with secrets in config examples, add `# pragma: allowlist secret`
- Always return `Any` (not `type(Any)`) from adapter field type methods

## Task Completion Requirements

**MANDATORY before marking any task complete**:

1. Run `python -m crackerjack -t --ai-fix` for all quality checks
1. Fix all formatting, linting, type checking, and test failures
1. Re-run verification to ensure all checks pass
1. Document that crackerjack verification completed successfully

**Never skip crackerjack verification** - it's the project's quality gate.

## Performance Best Practices

1. **Lazy Loading**: Initialize expensive resources only when needed
1. **Connection Pooling**: Configure pool sizes in `settings/adapters.yml`
1. **Singleton Services**: Register expensive services once at startup
1. **Cache Strategy**: Use appropriate TTL values
1. **Async Best Practices**: Use `asyncio.gather()` for concurrent operations

**For detailed performance optimization**, see `docs/PERFORMANCE-GUIDE.md`

## Important Patterns

- Adapter pattern with public/private method delegation
- `_ensure_client()` for lazy connection initialization
- Mock classes must mirror real implementation signatures
- Consistent async interfaces across all adapters
- MODULE_METADATA in all adapters with proper AdapterMetadata schema
- Resource cleanup via CleanupMixin
- Security: validate inputs, use secure defaults
  **Force structured stderr without `--debug`**:

```bash
ACB_FORCE_STRUCTURED_STDERR=1 python -m acb.workflow 2>logs.jsonl
# Emits JSON logs even without CLI debug flag
```
