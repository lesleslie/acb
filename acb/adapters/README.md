> **ACB Documentation**: [Main](../../README.md) | [Core Systems](../README.md) | [Actions](../actions/README.md) | [Adapters](./README.md)

# ACB: Adapters

Adapters provide standardized interfaces to external systems and services in the ACB framework. Each adapter category includes a base class that defines the interface and multiple implementations that can be configured and swapped without changing your application code.

## Table of Contents

- [Adapter System Overview](#adapter-system-overview)
- [Available Adapters](#available-adapters)
- [Installation](#installation)
- [Configuration](#configuration)
- [Usage](#usage)
- [Implementing Custom Adapters](#implementing-custom-adapters)
- [Adapter Lifecycle](#adapter-lifecycle)
- [Best Practices](#best-practices)
- [Additional Resources](#additional-resources)

## Adapter System Overview

ACB's adapter system is designed around these principles:

1. **Standardized Interfaces**: Each adapter category defines a consistent interface through a base class
2. **Multiple Implementations**: Different providers can be used interchangeably
3. **Configuration-driven**: Adapters are enabled through configuration rather than code changes
4. **Static Registration**: Adapters use hardcoded mappings for improved performance and reliability (ACB 0.16.17+)
5. **Dependency Injection**: Adapters are accessed through the dependency injection system
6. **Extensibility**: Projects built on ACB can add their own domain-specific adapters

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

## Available Adapters

ACB includes the following adapter categories:

### Caching Adapters
- [**Cache**](./cache/README.md): Fast data caching
  - **Memory**: In-memory cache for development and small applications
  - **Redis**: Distributed cache using Redis

### DNS Adapters
- [**DNS**](./dns/README.md): Domain name management
  - **Cloud DNS**: Google Cloud DNS implementation
  - **Cloudflare**: Cloudflare DNS implementation

### File Transfer Adapters
- [**FTPD**](./ftpd/README.md): File transfer protocol server implementations
  - **FTP**: Standard File Transfer Protocol server using aioftp
  - **SFTP**: Secure File Transfer Protocol server using asyncssh

### Logging
- **Loguru**: ACB uses Loguru as its core logging module for structured logging and error tracking. Refer to the Logging section for configuration details.
- [**Logger**](./logger/README.md): Application logging
  - **Loguru**: Structured logging with Loguru (default)
  - **Structlog**: Alternative structured logging with structlog

### Database Model Adapters
- [**Models**](./models/README.md): Database models and ORM integration
  - **SQLModel**: SQL database ORM with SQLModel

### Monitoring Adapters
- [**Monitoring**](./monitoring/README.md): Application monitoring and error tracking
  - **Logfire**: Logging-based monitoring
  - **Sentry**: Error and performance monitoring with Sentry

### NoSQL Database Adapters
- [**NoSQL**](./nosql/README.md): Non-relational databases
  - **Firestore**: Google Cloud Firestore database using Google Cloud Firestore API
  - **MongoDB**: MongoDB document database using Beanie ODM
  - **Redis**: Redis database for structured data using Redis-OM

### HTTP Client Adapters
- [**Requests**](./requests/README.md): HTTP clients for API consumption
  - **HTTPX**: Modern async HTTP client
  - **Niquests**: Extended HTTP client

### Secret Management Adapters
- [**Secret**](./secret/README.md): Securely storing and retrieving secrets
  - **Infisical**: Infisical secrets manager
  - **Secret Manager**: Cloud-based secret management

### Email Adapters
- [**SMTP**](./smtp/README.md): Email sending
  - **Gmail**: Send emails through Gmail API with OAuth2
  - **Mailgun**: Send emails through Mailgun API

### SQL Database Adapters
- [**SQL**](./sql/README.md): Relational databases
  - **MySQL**: MySQL/MariaDB database adapter
  - **PostgreSQL**: PostgreSQL database adapter
  - **SQLite**: SQLite database adapter (local files and Turso cloud databases)

### Storage Adapters
- [**Storage**](./storage/README.md): File and object storage
  - **Azure**: Azure Blob storage
  - **Cloud Storage**: Google Cloud Storage
  - **File**: Local file system storage
  - **Memory**: In-memory storage for testing
  - **S3**: Amazon S3 or S3-compatible storage

## Installation

Install ACB with specific adapter dependencies:

```bash
# Install with specific adapter dependencies
uv add "acb[cache,sql,storage]"

# Install with all adapter dependencies
uv add "acb[all]"
```

The following adapter-specific dependency groups are available:

| Feature Group | Components                                    | Installation Command        |
|---------------|-----------------------------------------------|-----------------------------|
| cache         | Redis, memory                                 | `uv add "acb[cache]"`      |
| dns           | Cloud DNS, Cloudflare                         | `uv add "acb[dns]"`        |
| ftpd          | FTP, SFTP servers                             | `uv add "acb[ftpd]"`       |
| monitoring    | Sentry, Logfire                              | `uv add "acb[monitoring]"` |
| nosql         | MongoDB (Beanie), Firestore, Redis (Redis-OM) | `uv add "acb[nosql]"`      |
| requests      | HTTPX, Niquests HTTP clients                 | `uv add "acb[requests]"`   |
| secret        | Infisical, Secret Manager                     | `uv add "acb[secret]"`     |
| smtp          | Gmail, Mailgun email sending                  | `uv add "acb[smtp]"`       |
| sql           | MySQL, PostgreSQL, SQLite (including Turso)  | `uv add "acb[sql]"`        |
| storage       | S3, GCS, Azure, Local                         | `uv add "acb[storage]"`    |
| demo          | Demo/example utilities                        | `uv add "acb[demo]"`       |
| dev           | Development tools                             | `uv add "acb[dev]"`        |

## Configuration

Adapters are configured in the `settings/adapters.yml` file. This file defines which implementation of each adapter type will be used:

```yaml
# Example adapters.yml
cache: redis       # Use Redis for caching
logger: loguru     # Use Loguru for logging
sql: pgsql         # Use PostgreSQL for SQL database (or: mysql, sqlite)
storage: s3        # Use S3 for storage
# Other adapters use their default implementation or are disabled when set to null
secret:            # Secret adapter is disabled
```

Each adapter can be further configured in `settings/app.yml`:

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
from acb.depends import depends
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
    storage: Storage =depends(),  # Injected storage adapter
    logger: Logger =depends()     # Injected logger adapter
) -> dict[str, t.Any]:
    logger.info(f"Processing file: {filename}")
    content: bytes | None = await storage.get_file(filename)
    if not content:
        return {"filename": filename, "error": "File not found", "processed": False}
    # Process the file...
    result: dict[str, t.Any] = {"filename": filename, "size": len(content), "processed": True}
    return result
```

### Using Multiple Adapters

```python
import typing as t

from acb.adapters import import_adapter
from acb.depends import depends


# Import multiple adapters simultaneously
Cache, Storage, SQL = import_adapter()

# Use them together
@depends.inject
async def backup_data(key: str, cache: Cache = depends(), sql: SQL = depends(), storage: Storage = depends()) -> bool:
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
            description=description
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
# settings/adapters.yml
payment: stripe
```

### 6. Use Your Custom Adapter

```python
from acb.depends import depends
from acb.adapters import import_adapter

# Import your adapter
Payment = import_adapter("payment")

@depends.inject
async def payment_example(payment: Payment = depends()) -> dict[str, str | bool]:
    transaction_id: str = await payment.charge(19.99, "Premium subscription")
    success: bool = await payment.refund(transaction_id)
    return {"transaction_id": transaction_id, "refunded": success}
```

### Migration from Dynamic Discovery

If you were using the old dynamic discovery system, you'll need to:

1. **Update adapter class names**: Ensure your adapter class name matches the category (e.g., `Payment` for `payment` category)
2. **Add explicit registration**: Use `depends.set()` to register your adapter class
3. **Consider static mappings**: For better performance, consider contributing your adapter to the core static mappings

## Adapter Lifecycle

1. **Registration**: Adapters are discovered and registered during application startup
2. **Configuration**: The enabled adapter for each category is determined from `adapters.yml`
3. **Initialization**: The `init()` method is called when the adapter is first accessed
4. **Usage**: The adapter is used throughout the application lifecycle
5. **Cleanup**: If needed, cleanup is handled when the application shuts down

## Best Practices

1. **Always Use the Interface**: Code against the base adapter interface, not specific implementations
2. **Access via Dependency Injection**: Use `depends.get()` rather than direct imports
3. **Provide Default Settings**: All settings should have sensible defaults
4. **Handle Initialization**: Implement the `init()` method for setup tasks
5. **Consider Async Operations**: Most adapter methods should be asynchronous
6. **Implement Error Handling**: Properly handle and translate provider-specific errors
7. **Add Comprehensive Documentation**: Document all methods, parameters, and return values
8. **Include Troubleshooting Guidelines**: Document common errors and their solutions

## Additional Resources

- [Main ACB Documentation](../README.md)
- [Core Systems Documentation](../README.md)
- [Actions Documentation](../actions/README.md)
