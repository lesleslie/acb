> **ACB Documentation**: [Main](<../../README.md>) | [Core Systems](<../README.md>) | [Actions](<../actions/README.md>) | [Adapters](<./README.md>)

# ACB: Adapters

Adapters provide standardized interfaces to external systems and services in the ACB framework. Each adapter category includes a base class that defines the interface and multiple implementations that can be configured and swapped without changing your application code.

## Table of Contents

- [Adapter System Overview](<#adapter-system-overview>)
- [Security and Monitoring Infrastructure](<#acb-0190-security-and-monitoring-infrastructure>)
- [Available Adapters](<#available-adapters>)
- [Installation](<#installation>)
- [Configuration](<#configuration>)
- [Usage](<#usage>)
- [Implementing Custom Adapters](<#implementing-custom-adapters>)
- [Adapter Lifecycle](<#adapter-lifecycle>)
- [Best Practices](<#best-practices>)
- [Additional Resources](<#additional-resources>)

## Adapter System Overview

ACB's adapter system is designed around these principles:

1. **Standardized Interfaces**: Each adapter category defines a consistent interface through a base class
1. **Multiple Implementations**: Different providers can be used interchangeably
1. **Configuration-driven**: Adapters are enabled through configuration rather than code changes
1. **Static Registration**: Adapters use hardcoded mappings for improved performance and reliability (ACB 0.16.17+)
1. **Dependency Injection**: Adapters are accessed through the dependency injection system
1. **Extensibility**: Projects built on ACB can add their own domain-specific adapters
1. **Enterprise Security**: Built-in security features including validation, rate limiting, and credential management (ACB 0.19.0+)
1. **Production Monitoring**: Comprehensive health checks, performance monitoring, and reliability features (ACB 0.19.0+)

### ACB 0.16.17+ Adapter Registration Changes

Starting with ACB 0.16.17, the adapter system has been significantly refactored:

- **BREAKING CHANGE**: Dynamic adapter discovery has been replaced with static adapter mappings
- **Performance Improvement**: Faster adapter loading through predefined mappings
- **Reliability**: Eliminates runtime discovery issues and import errors
- **Core Adapters**: Only config and loguru adapters are automatically registered as they are required for ACB operation

### Extension by Other Projects

Frameworks built on ACB can extend the adapter system with their own domain-specific adapters. For example, [FastBlocks](https://github.com/lesleslie/fastblocks) extends ACB with web-specific adapters like:

- **Templates**: Asynchronous template rendering for web applications
- **Routes**: Route discovery and registration for web endpoints
- **Auth**: Authentication mechanisms for web applications
- **Admin**: Administrative interfaces for database models

These extensions maintain compatibility with ACB's core infrastructure while adding domain-specific functionality.

### ACB 0.19.0+ Security and Monitoring Infrastructure

ACB 0.19.0 introduces comprehensive enterprise-grade security and monitoring infrastructure that is automatically integrated into all adapters:

#### Security Features

- **Credential Management**: Secure storage and rotation of API keys, passwords, and certificates with encryption
- **Input Validation**: Comprehensive validation and sanitization to prevent injection attacks
- **Rate Limiting**: Configurable rate limiting with multiple strategies (token bucket, sliding window, fixed window)
- **CSRF Protection**: Built-in CSRF token generation and validation for web applications
- **Security Headers**: Automatic security headers including CSP, HSTS, and X-Frame-Options
- **SSL/TLS Configuration**: Unified SSL configuration across all adapters with modern security standards

#### Monitoring and Reliability Features

- **Health Checks**: Proactive health monitoring with configurable intervals and thresholds
- **Performance Monitoring**: Real-time metrics collection for latency, throughput, and error rates
- **Retry Mechanisms**: Intelligent retry logic with exponential backoff and circuit breaker patterns
- **Resource Management**: Enhanced cleanup patterns with error handling and race condition prevention
- **Observability**: Detailed logging and tracing for debugging and performance optimization

#### Usage Examples

```python
from acb.adapters import import_adapter
from acb.depends import depends

# Get an adapter with all security and monitoring features
Cache = import_adapter("cache")
cache = depends.get(Cache)

# Use secure operations (validation + rate limiting + monitoring)
await cache.get_secure("user:123", user_id="current_user")
await cache.set_secure("user:123", user_data, ttl=3600, user_id="current_user")

# Use operations with full monitoring and retry
await cache.get_with_full_monitoring("analytics:daily")
await cache.set_with_retry("session:abc", session_data, ttl=1800)

# Check health and performance
health_status = await cache.check_health()
rate_limit_status = cache.get_rate_limit_status("get", "current_user")
```

All existing adapter operations remain available and unchanged, ensuring backward compatibility.

## Quality Assurance Adapters

ACB includes specialized adapters for quality assurance tools through the crackerjack integration. These adapters follow the same dependency injection and configuration patterns as other adapters but are optimized for code quality, security scanning, and refactoring tools.

### Quality Tool Categories

| Category | Description | Default Timeout | Example Use |
| -------- | ----------- | --------------- | ----------- |
| **Security** | Security vulnerability scanning | 60s (override recommended) | Bandit |
| **Refactoring** | Modern Python idioms and suggestions | 60s (override recommended) | Refurb |
| **Type Checking** | Static type analysis | 60s (override recommended) | Pyright/Zuban |

### Configuring Quality Tool Timeouts

Quality tools often require longer timeouts than standard operations. The default 60-second timeout is often insufficient for large codebases:

```yaml
# settings/adapters.yml
bandit:
  timeout_seconds: 300  # 5 minutes for security scans
  severity_level: "medium"
  confidence_level: "medium"

refurb:
  timeout_seconds: 240  # 4 minutes for refactoring analysis
  enable_all: false
  explain: false
```

### Base QA Adapter Configuration

All QA adapters inherit from `QABaseSettings` which provides common configuration options:

```python
from crackerjack.adapters._qa_adapter_base import QABaseSettings


class QABaseSettings(Settings):
    enabled: bool = True
    timeout_seconds: int = Field(60, ge=1, le=3600)  # Default 60s
    file_patterns: list[str] = Field(default_factory=lambda: ["**/*.py"])
    exclude_patterns: list[str] = Field(default_factory=list)
    fail_on_error: bool = True
    verbose: bool = False
    cache_enabled: bool = True
    cache_ttl: int = 3600
    max_workers: int = Field(4, ge=1, le=16)
```

## Available Adapters

ACB includes the following adapter categories:

### Caching Adapters

- [**Cache**](<./cache/README.md>): Fast data caching
  - **Memory**: In-memory cache for development and small applications
  - **Redis**: Distributed cache using Redis

### DNS Adapters

- [**DNS**](<./dns/README.md>): Domain name management
  - **Cloud DNS**: Google Cloud DNS implementation
  - **Cloudflare**: Cloudflare DNS implementation

### File Transfer Adapters

- [**FTPD**](<./ftpd/README.md>): File transfer protocol server implementations
  - **FTP**: Standard File Transfer Protocol server using aioftp
  - **SFTP**: Secure File Transfer Protocol server using asyncssh

### Logging

- **Loguru**: ACB uses Loguru as its core logging module for structured logging and error tracking. Refer to the Logging section for configuration details.
- [**Logger**](<./logger/README.md>): Application logging
  - **Loguru**: Structured logging with Loguru (default)
  - **Structlog**: Alternative structured logging with structlog

### Database Model Adapters

- [**Models**](<./models/README.md>): Database models and ORM integration
  - **SQLModel**: SQL database ORM with SQLModel

### Monitoring Adapters

- [**Monitoring**](<./monitoring/README.md>): Application monitoring and error tracking
  - **Logfire**: Logging-based monitoring
  - **Sentry**: Error and performance monitoring with Sentry

### NoSQL Database Adapters

- [**NoSQL**](<./nosql/README.md>): Non-relational databases
  - **Firestore**: Google Cloud Firestore database using Google Cloud Firestore API
  - **MongoDB**: MongoDB document database using Beanie ODM
  - **Redis**: Redis database for structured data using Redis-OM

### HTTP Client Adapters

- [**Requests**](<./requests/README.md>): HTTP clients for API consumption
  - **HTTPX**: Modern async HTTP client
  - **Niquests**: Extended HTTP client

### Secret Management Adapters

- [**Secret**](<./secret/README.md>): Securely storing and retrieving secrets
  - **Infisical**: Infisical secrets manager
  - **Secret Manager**: Cloud-based secret management

### Email Adapters

- [**SMTP**](<./smtp/README.md>): Email sending
  - **Gmail**: Send emails through Gmail API with OAuth2
  - **Mailgun**: Send emails through Mailgun API

### SQL Database Adapters

- [**SQL**](<./sql/README.md>): Relational databases
  - **MySQL**: MySQL/MariaDB database adapter
  - **PostgreSQL**: PostgreSQL database adapter
  - **SQLite**: SQLite database adapter (local files and Turso cloud databases)

### Vector Database Adapters

- [**Vector**](<./vector/README.md>): Vector databases for similarity search and AI applications
  - **DuckDB**: Local vector database with VSS extension (Stable)
  - **Weaviate**: Weaviate vector database with hybrid search capabilities (Planned)
  - **OpenSearch**: OpenSearch vector database with k-NN capabilities (Planned)
  - **Qdrant**: Qdrant vector database for production deployments (Planned)

### Storage Adapters

- [**Storage**](<./storage/README.md>): File and object storage
  - **Azure**: Azure Blob storage
  - **Cloud Storage**: Google Cloud Storage
  - **File**: Local file system storage
  - **Memory**: In-memory storage for testing
  - **S3**: Amazon S3 or S3-compatible storage

## Installation

Install ACB with specific adapter groups:

```bash
# Install with specific adapter groups
uv add acb --group cache --group sql --group storage

# Install with all adapter groups
uv add acb --group all
```

The following adapter-specific dependency groups are available:

| Feature Group | Components | Installation Command |
| ------------- | --------------------------------------------- | -------------------------- |
| cache | Redis, memory | `uv add acb --group cache` |
| dns | Cloud DNS, Cloudflare | `uv add acb --group dns` |
| ftpd | FTP, SFTP servers | `uv add acb --group ftpd` |
| monitoring | Sentry, Logfire | `uv add acb --group monitoring` |
| nosql | MongoDB (Beanie), Firestore, Redis (Redis-OM) | `uv add acb --group nosql` |
| requests | HTTPX, Niquests HTTP clients | `uv add acb --group requests` |
| secret | Infisical, Secret Manager | `uv add acb --group secret` |
| smtp | Gmail, Mailgun email sending | `uv add acb --group smtp` |
| sql | MySQL, PostgreSQL, SQLite (including Turso) | `uv add acb --group sql` |
| storage | S3, GCS, Azure, Local | `uv add acb --group storage` |
| vector | DuckDB, Weaviate, OpenSearch, Qdrant | `uv add acb --group vector` |
| demo | Demo/example utilities | `uv add acb --group demo` |
| dev | Development tools | `uv add acb --group dev` |

## Configuration

Adapters are configured in the `settings/adapters.yaml` file. This file defines which implementation of each adapter type will be used:

```yaml
# Example adapters.yaml
cache: redis       # Use Redis for caching
logger: loguru     # Use Loguru for logging
sql: pgsql         # Use PostgreSQL for SQL database (or: mysql, sqlite)
storage: s3        # Use S3 for storage
# Other adapters use their default implementation or are disabled when set to null
secret:            # Secret adapter is disabled
```

Each adapter can be further configured in `settings/app.yaml`:

```yaml
# Example adapter-specific settings
cache:
  default_ttl: 3600

storage:
  buckets:
    media: "media-bucket-name"
    documents: "documents-bucket-name"
```

## Usage

### Basic Adapter Usage

```python
from acb.depends import depends


async def cache_example():
    # Get an instance via dependency injection
    cache = depends.get()

    # Use the adapter with a consistent API
    await cache.set("key", "value", ttl=300)
    value = await cache.get("key")
    return value
```

### Injecting Adapters Into Functions

```python
from acb.depends import depends, Inject
from acb.adapters import import_adapter
import typing as t

# Method 1: Explicit adapter imports
Storage = import_adapter("storage")
Logger = import_adapter("logger")

# Method 2: Automatic detection (convenience feature)
# ACB detects adapter names from variable names on the left side of assignment
Storage, Logger = import_adapter()  # Automatically detects "storage" and "logger"


@depends.inject
async def process_file(
    filename: str,
    storage: Inject[Storage],  # Injected storage adapter
    logger: Inject[Logger],  # Injected logger adapter
) -> dict[str, t.Any]:
    logger.info(f"Processing file: {filename}")
    content: bytes | None = await storage.get_file(filename)
    if not content:
        return {"filename": filename, "error": "File not found", "processed": False}
    # Process the file...
    result: dict[str, t.Any] = {
        "filename": filename,
        "size": len(content),
        "processed": True,
    }
    return result
```

### Using Multiple Adapters

```python
import typing as t

from acb.adapters import import_adapter
from acb.depends import depends, Inject


# Import multiple adapters simultaneously
Cache, Storage, SQL = import_adapter()


# Use them together
@depends.inject
async def backup_data(
    key: str,
    cache: Inject[Cache],
    sql: Inject[SQL],
    storage: Inject[Storage],
) -> bool:
    # Get data from cache
    data: dict[str, t.Any] | None = await cache.get(key)
    if not data:
        # If not in cache, get from database
        data = await sql.fetch_one("SELECT data FROM items WHERE key = ?", key)
        if data:
            # Store in cache for next time
            await cache.set(key, data, ttl=3600)

    # Backup to storage
    if data:
        await storage.put_file(f"backups/{key}.json", data)
        return True
    return False
```

## Static Adapter Mappings (ACB 0.16.17+)

ACB now uses a hardcoded static mapping system for adapter registration. This provides better performance and reliability compared to the previous dynamic discovery system.

### Built-in Adapter Mappings

The following adapters are pre-registered in the static mapping system:

```python
static_mappings = {
    # Cache adapters
    "cache.memory": ("acb.adapters.cache.memory", "Cache"),
    "cache.redis": ("acb.adapters.cache.redis", "Cache"),
    # Storage adapters
    "storage.file": ("acb.adapters.storage.file", "Storage"),
    "storage.memory": ("acb.adapters.storage.memory", "Storage"),
    "storage.s3": ("acb.adapters.storage.s3", "Storage"),
    "storage.azure": ("acb.adapters.storage.azure", "Storage"),
    "storage.cloud_storage": ("acb.adapters.storage.cloud_storage", "Storage"),
    # SQL adapters
    "sql.mysql": ("acb.adapters.sql.mysql", "Sql"),
    "sql.pgsql": ("acb.adapters.sql.pgsql", "Sql"),
    # NoSQL adapters
    "nosql.mongodb": ("acb.adapters.nosql.mongodb", "Nosql"),
    "nosql.redis": ("acb.adapters.nosql.redis", "Nosql"),
    "nosql.firestore": ("acb.adapters.nosql.firestore", "Nosql"),
    # And many more...
}
```

### Core Adapters

These adapters are always available and don't need to be enabled in configuration:

```python
core_adapters = [
    Adapter(
        name="config",
        module="acb.config",
        class_name="Config",
        category="config",
        enabled=True,
        installed=True,
    ),
    Adapter(
        name="loguru",
        module="acb.logger",
        class_name="Logger",
        category="logger",
        enabled=True,
        installed=True,
    ),
]
```

## Implementing Custom Adapters

With the new static mapping system, implementing custom adapters requires additional steps:

### 1. Create the Adapter Structure

```
myapp/adapters/payment/
├── __init__.py
├── _base.py
├── stripe.py
└── paypal.py
```

### 2. Define the Base Interface

```python
# myapp/adapters/payment/_base.py
from acb.config import Settings
from typing import Protocol


class PaymentBaseSettings(Settings):
    currency: str = "USD"
    default_timeout: int = 30


class PaymentBase(Protocol):
    async def charge(self, amount: float, description: str) -> str:
        """Charge a payment and return a transaction ID"""
        ...

    async def refund(self, transaction_id: str) -> bool:
        """Refund a previous transaction"""
        ...
```

### 3. Implement the Adapter

```python
# myapp/adapters/payment/stripe.py
from ._base import PaymentBase, PaymentBaseSettings
from pydantic import SecretStr
from acb.depends import depends
import stripe
import typing as t


class StripeSettings(PaymentBaseSettings):
    api_key: SecretStr = SecretStr("sk_test_default")


class Payment:  # Note: Use category name as class name
    settings: StripeSettings | None = None

    async def init(self) -> None:
        if self.settings:
            stripe.api_key = self.settings.api_key.get_secret_value()

    async def charge(self, amount: float, description: str) -> str:
        response: t.Any = await stripe.PaymentIntent.create(
            amount=int(amount * 100),
            currency=self.settings.currency if self.settings else "USD",
            description=description,
        )
        return response.id

    async def refund(self, transaction_id: str) -> bool:
        try:
            await stripe.Refund.create(payment_intent=transaction_id)
            return True
        except stripe.error.StripeError:
            return False


# Register the adapter with dependency injection
depends.set(Payment)
```

### 4. Register in Package Registry (if needed)

For packages that extend ACB, you may need to register your adapters in the package registry:

```python
# myapp/__init__.py
from acb import register_package
from pathlib import Path

# Register your package with ACB
register_package(Path(__file__).parent)
```

### 5. Configure the Adapter

```yaml
# settings/adapters.yaml
payment: stripe
```

### 6. Use Your Custom Adapter

```python
from acb.depends import depends, Inject
from acb.adapters import import_adapter

# Import your adapter
Payment = import_adapter("payment")


@depends.inject
async def payment_example(payment: Inject[Payment]) -> dict[str, str | bool]:
    transaction_id: str = await payment.charge(19.99, "Premium subscription")
    success: bool = await payment.refund(transaction_id)
    return {"transaction_id": transaction_id, "refunded": success}
```

### Migration from Dynamic Discovery

If you were using the old dynamic discovery system, you'll need to:

1. **Update adapter class names**: Ensure your adapter class name matches the category (e.g., `Payment` for `payment` category)
1. **Add explicit registration**: Use `depends.set()` to register your adapter class
1. **Consider static mappings**: For better performance, consider contributing your adapter to the core static mappings

## Adapter Lifecycle

1. **Registration**: Adapters are discovered and registered during application startup
1. **Configuration**: The enabled adapter for each category is determined from `adapters.yaml`
1. **Initialization**: The `init()` method is called when the adapter is first accessed
1. **Usage**: The adapter is used throughout the application lifecycle
1. **Cleanup**: If needed, cleanup is handled when the application shuts down

## Best Practices

1. **Always Use the Interface**: Code against the base adapter interface, not specific implementations
1. **Access via Dependency Injection**: Use `depends.get()` rather than direct imports
1. **Provide Default Settings**: All settings should have sensible defaults
1. **Handle Initialization**: Implement the `init()` method for setup tasks
1. **Consider Async Operations**: Most adapter methods should be asynchronous
1. **Implement Error Handling**: Properly handle and translate provider-specific errors
1. **Add Comprehensive Documentation**: Document all methods, parameters, and return values
1. **Include Troubleshooting Guidelines**: Document common errors and their solutions

## Additional Resources

- [Main ACB Documentation](<../README.md>)
- [Core Systems Documentation](<../README.md>)
- [Actions Documentation](<../actions/README.md>)
