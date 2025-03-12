# ACB Adapters

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
4. **Automatic Registration**: Adapters are discovered and registered when your application starts
5. **Dependency Injection**: Adapters are accessed through the dependency injection system

## Available Adapters

ACB includes the following adapter categories:

### Application Adapters
- [**App**](./app/README.md): Application bootstrapping and lifecycle management
  - **Main**: Default application adapter

### Caching Adapters
- [**Cache**](./cache/README.md): Fast data caching
  - **Memory**: In-memory cache for development and small applications
  - **Redis**: Distributed cache using Redis

### DNS Adapters
- [**DNS**](./dns/README.md): Domain name management
  - **Cloud DNS**: Interface to cloud provider DNS services

### File Transfer Adapters
- [**FTPD**](./ftpd/README.md): File transfer protocol implementations
  - **FTP**: Standard File Transfer Protocol client
  - **SFTP**: Secure File Transfer Protocol client

### Logging Adapters
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
  - **Firestore**: Google Cloud Firestore database
  - **MongoDB**: MongoDB document database
  - **Redis**: Redis database for structured data

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
  - **Gmail**: Send emails through Gmail
  - **Mailgun**: Send emails through Mailgun API

### SQL Database Adapters
- [**SQL**](./sql/README.md): Relational databases
  - **MySQL**: MySQL/MariaDB database adapter
  - **PostgreSQL**: PostgreSQL database adapter

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
pdm add "acb[redis,sql,storage]"

# Install with all adapter dependencies
pdm add "acb[all]"
```

The following adapter-specific dependency groups are available:

| Feature Group | Components | Installation Command |
|---------------|------------|----------------------|
| redis | Cache, NoSQL | `pdm add "acb[redis]"` |
| sql | MySQL, PostgreSQL | `pdm add "acb[sql]"` |
| nosql | MongoDB, Firestore | `pdm add "acb[nosql]"` |
| storage | S3, GCS, Azure, Local | `pdm add "acb[storage]"` |
| logging | Loguru, structlog | `pdm add "acb[logging]"` |
| aws | S3, other AWS services | `pdm add "acb[aws]"` |
| gcp | Cloud Storage, other GCP services | `pdm add "acb[gcp]"` |
| azure | Azure Blob Storage, other Azure services | `pdm add "acb[azure]"` |
| secret | Secret management | `pdm add "acb[secret]"` |
| monitoring | Error tracking and monitoring | `pdm add "acb[monitoring]"` |

## Configuration

Adapters are configured in the `settings/adapters.yml` file. This file defines which implementation of each adapter type will be used:

```yaml
# Example adapters.yml
cache: redis       # Use Redis for caching
logger: loguru     # Use Loguru for logging
sql: pgsql         # Use PostgreSQL for SQL database
storage: s3        # Use S3 for storage
# Other adapters use their default implementation or are disabled when set to null
secret: null       # Secret adapter is disabled
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
from acb.adapters import import_adapter

# Import an adapter class (automatically selects the one enabled in config)
Cache = import_adapter("cache")  # Returns Redis or Memory adapter based on config

# Get an instance via dependency injection
cache = depends.get(Cache)

# Use the adapter with a consistent API
await cache.set("key", "value", ttl=300)
value = await cache.get("key")
```

### Injecting Adapters Into Functions

```python
from acb.depends import depends
from acb.adapters import import_adapter

# Define adapter types
Storage = import_adapter("storage")
Logger = import_adapter("logger")

@depends.inject
async def process_file(
    filename: str,
    storage=depends(Storage),  # Injected storage adapter
    logger=depends(Logger)     # Injected logger adapter
):
    logger.info(f"Processing file: {filename}")
    content = await storage.get_file(filename)
    # Process the file...
    return result
```

### Using Multiple Adapters

```python
from acb.depends import depends

# Import multiple adapters simultaneously
Cache, Storage, SQL = depends.get("cache", "storage", "sql")

# Use them together
async def backup_data(key):
    # Get data from cache
    data = await Cache.get(key)
    if not data:
        # If not in cache, get from database
        data = await SQL.fetch_one("SELECT data FROM items WHERE key = ?", key)
        if data:
            # Store in cache for next time
            await Cache.set(key, data, ttl=3600)

    # Backup to storage
    if data:
        await Storage.put_file(f"backups/{key}.json", data)
```

## Implementing Custom Adapters

You can create your own adapters to extend ACB:

1. Create the adapter directory structure:
```
myapp/adapters/payment/
├── __init__.py
├── _base.py
├── stripe.py
└── paypal.py
```

2. Define the base interface in `_base.py`:
```python
from acb.config import AdapterBase, Settings
from pydantic import SecretStr

class PaymentBaseSettings(Settings):
    currency: str = "USD"
    default_timeout: int = 30

class PaymentBase(AdapterBase):
    async def charge(self, amount: float, description: str) -> str:
        """Charge a payment and return a transaction ID"""
        raise NotImplementedError()

    async def refund(self, transaction_id: str) -> bool:
        """Refund a previous transaction"""
        raise NotImplementedError()
```

3. Implement specific providers like `stripe.py`:
```python
from ._base import PaymentBase, PaymentBaseSettings
from pydantic import SecretStr
import stripe

class StripeSettings(PaymentBaseSettings):
    api_key: SecretStr = SecretStr("sk_test_default")

class Stripe(PaymentBase):
    settings: StripeSettings = None

    async def init(self) -> None:
        stripe.api_key = self.settings.api_key.get_secret_value()

    async def charge(self, amount: float, description: str) -> str:
        response = await stripe.PaymentIntent.create(
            amount=int(amount * 100),  # Convert to cents
            currency=self.settings.currency,
            description=description
        )
        return response.id
```

4. Update your `settings/adapters.yml` file:
```yaml
# Enable your custom adapter
payment: stripe
```

5. Use your adapter:
```python
from acb.depends import depends
from acb.adapters import import_adapter

# Import your adapter
Payment = import_adapter("payment")

# Get an instance
payment = depends.get(Payment)

# Use it
transaction_id = await payment.charge(19.99, "Premium subscription")
```

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
- [Configuration Guide](../config.md)
- [Dependency Injection Guide](../depends.md)
