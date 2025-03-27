
<p align="center">
  <img src="https://drive.google.com/uc?id=1pMUqyvgMkhGYoLz3jBibZDl3J63HEcCC">
</p>

> **ACB Documentation**: [Main](./README.md) | [Core Systems](./acb/README.md) | [Actions](./acb/actions/README.md) | [Adapters](./acb/adapters/README.md)

# <u>A</u>synchronous <u>C</u>omponent <u>B</u>ase (ACB)

[![Code style: crackerjack](https://img.shields.io/badge/code%20style-crackerjack-000042)](https://github.com/lesleslie/crackerjack)

## What is ACB?

ACB is a modular Python framework for building asynchronous applications with pluggable components. It provides a collection of self-contained **actions** and flexible **adapters** that integrate with various systems, along with a dynamic configuration and dependency injection system.

## Key Features

- **Modular Architecture**: Mix and match components to build your application
- **Asynchronous First**: Built for high-performance async operations
- **Pluggable Adapters**: Swap implementations without changing your code
- **Automatic Discovery**: Components are automatically discovered and registered
- **Configuration-Driven**: Change behavior through configuration rather than code
- **Type Safety**: Built on Pydantic for validation and type safety

## Table of Contents

- [Installation](#installation)
- [Quick Start](#quick-start)
- [Architecture Overview](#architecture-overview)
- [Core Components](#core-components)
  - [Actions](#actions)
  - [Adapters](#adapters)
  - [Configuration System](#configuration-system)
  - [Dependency Injection](#dependency-injection)
- [Use Cases](#use-cases)
- [Built-in Components](#built-in-components)
- [Advanced Usage](#advanced-usage)
- [Documentation](#documentation)
- [Acknowledgements](#acknowledgements)
- [License](#license)
- [Projects Using ACB](#projects-using-acb)
- [Contributing](#contributing)

## Installation

Install ACB using [pdm](https://pdm.fming.dev):

```
pdm add acb
```

### Optional Dependencies

ACB supports various optional dependencies for different adapters and functionality:

| Feature Group | Components | Installation Command |
|---------------|------------|----------------------|
| Cache | Memory, Redis | `pdm add "acb[cache]"` |
| SQL | Database (MySQL, PostgreSQL) | `pdm add "acb[sql]"` |
| NoSQL | Database (MongoDB, Firestore, Redis) | `pdm add "acb[nosql]"` |
| Storage | File storage (S3, GCS, Azure, local) | `pdm add "acb[storage]"` |
| DNS | Domain name management | `pdm add "acb[dns]"` |
| Requests | HTTP clients (HTTPX, Niquests) | `pdm add "acb[requests]"` |
| SMTP | Email sending (Gmail, Mailgun) | `pdm add "acb[smtp]"` |
| FTPD | File transfer protocols (FTP, SFTP) | `pdm add "acb[ftpd]"` |
| Secret | Secret management | `pdm add "acb[secret]"` |
| Monitoring | Error tracking and monitoring | `pdm add "acb[monitoring]"` |
| Multiple Features | Combined dependencies | `pdm add "acb[cache,sql,nosql]"` |
| Web Application | Typical web app stack | `pdm add "acb[cache,sql,storage]"` |
| Development | Development tools | `pdm add "acb[dev]"` |

## Architecture Overview

ACB follows a component-based architecture with automatic discovery and registration of modules:

```
acb/
├── actions/         # Reusable utility functions (compress, encode, hash)
├── adapters/        # Integration modules for external systems
│   ├── cache/       # Memory and Redis caching
│   ├── dns/         # DNS management
│   ├── logger/      # Logging adapters (Loguru, structlog)
│   ├── sql/         # Database adapters (MySQL, PostgreSQL)
│   ├── nosql/       # NoSQL adapters (MongoDB, Firestore, Redis)
│   ├── storage/     # Storage adapters (S3, GCS, Azure, local)
│   └── ...          # Additional adapter categories
├── config.py        # Configuration system using Pydantic
├── depends.py       # Dependency injection framework
└── ...
```

## Core Components

ACB is structured around these fundamental building blocks:

### Actions

Actions are modular, self-contained utility functions that perform specific tasks. They are automatically discovered and registered, making them immediately available throughout your application.

#### Available Actions

| Action Category | Description | Implementations |
|-----------------|-------------|----------------|
| **Compress/Decompress** | Efficient data compression | gzip, brotli |
| **Encode/Decode** | Data serialization | JSON, YAML, TOML, MsgPack |
| **Hash** | Secure hashing functions | blake3, crc32c, md5 |

**Example: Using the compress action**

```python
from acb.actions.compress import compress, decompress

# Compress some text data using brotli
compressed = compress.brotli("Hello, ACB!", level=3)

# Decompress back to the original text
original = decompress.brotli(compressed)
```

For more detailed documentation on actions, see the [Actions README](./acb/actions/README.md).

### Adapters

Adapters provide standardized interfaces to external systems and services. Each adapter category includes a base class that defines the interface and multiple implementations.

#### Key Adapter Categories

| Adapter Category | Description | Implementations |
|------------------|-------------|----------------|
| **Cache** | Data caching | Memory, Redis |
| **DNS** | Domain name management | Cloud DNS |
| **FTP/SFTP** | File transfer protocols | FTP, SFTP |
| **Logger** | Structured logging | Loguru, structlog |
| **Database** | Data persistence | SQL (MySQL, PostgreSQL), NoSQL (MongoDB, Firestore, Redis) |
| **Storage** | File storage | File, Memory, S3, Cloud Storage, Azure |
| **Secret** | Secret management | Infisical, Secret Manager |

**Example: Using the cache adapter**

```python
from acb.depends import depends
from acb.adapters import import_adapter

# Import the cache adapter (automatically uses the one enabled in config)
Cache = import_adapter("cache")

# Get the cache instance via dependency injection
cache = depends.get(Cache)

# Use the cache with a consistent API regardless of implementation
await cache.set("my_key", "my_value", ttl=60)
value = await cache.get("my_key")
```

For more detailed documentation on adapters, see the [Adapters README](./acb/adapters/README.md).

### Configuration System

ACB's configuration system is built on Pydantic and supports multiple configuration sources:

- **YAML Files**: Environment-specific settings in YAML format
- **Secret Files**: Secure storage of sensitive information
- **Secret Managers**: Integration with external secret management services

#### Example: Defining custom settings

```python
from acb.config import Settings
from pydantic import SecretStr

class MyServiceSettings(Settings):
    api_url: str = "https://api.example.com"
    api_version: str = "v1"
    timeout: int = 30
    max_retries: int = 3
    api_key: SecretStr = SecretStr("default-key")  # Automatically handled securely
```

### Dependency Injection

ACB features a simple yet powerful dependency injection system that makes component wiring automatic and testable.

**Example: Using dependency injection**

```python
from acb.depends import depends
from acb.config import Config

# Register your custom component
depends.set(MyService)

# Inject dependencies into functions
@depends.inject
async def process_data(data, config: Config = depends(), logger = depends("logger")):
    logger.info(f"Processing data with app: {config.app.name}")
    # Process data...
    return result
```

## Getting Started

### Basic Application Setup

1. **Create a new project with PDM:**

```bash
mkdir myapp
cd myapp
pdm init
pdm add acb
```

2. **Create a basic application structure:**

```
myapp/
├── myapp/
│   ├── __init__.py
│   ├── actions/
│   │   └── __init__.py
│   ├── adapters/
│   │   └── __init__.py
│   └── main.py
└── settings/
    ├── app.yml
    ├── debug.yml
    └── adapters.yml
```

3. **Initialize ACB in your main.py:**

```python
from acb import register_pkg
from acb.depends import depends
from acb.config import Config

# Register your package with ACB
register_pkg()

# Access configuration
config = depends.get(Config)

# Import adapters
Logger = depends.get("logger")

async def main():
    Logger.info(f"Starting {config.app.name} application")
    # Your application logic here

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
```

### Configuration Files

Create your initial configuration files:

#### settings/app.yml
```yaml
app:
  name: "MyApp"
  title: "My ACB Application"
  domain: "myapp.example.com"
  version: "0.1.0"
```

#### settings/adapters.yml
```yaml
# Choose your adapter implementations
cache: memory
logger: loguru
storage: file
```

## Built-in Components

### Debug Module

ACB provides comprehensive debugging tools to help troubleshoot your application:

- **Granular debug levels**: Control debug output for specific components
- **Pretty-printed output**: Human-readable debug information
- **Performance timers**: Measure and optimize execution time

### Logging

The framework includes a robust logging system with structured logging and multiple output formats:

- **Asynchronous logging**: Non-blocking log operations
- **Structured data**: JSON-formatted logs for better analysis
- **Multiple adapters**: Choose between different logging implementations

## Advanced Usage

### Creating Custom Actions

Create your own reusable actions by adding Python modules to the actions directory:

```python
# myapp/actions/validate.py
from pydantic import BaseModel
import re

class Validate(BaseModel):
    @staticmethod
    def email(email: str) -> bool:
        """Validate an email address"""
        pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
        return bool(re.match(pattern, email))

validate = Validate()
```

### Implementing Custom Adapters

Extend ACB with your own adapters to integrate with additional services:

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

    async def refund(self, transaction_id: str) -> bool:
        try:
            await stripe.Refund.create(payment_intent=transaction_id)
            return True
        except stripe.error.StripeError:
            return False
```

## Documentation

For more detailed documentation about ACB components:

- [**Core Systems**](./acb/README.md): Configuration, dependency injection, debugging, and logging
- [**Actions**](./acb/actions/README.md): Detailed guide to built-in actions and creating custom ones
- [**Adapters**](./acb/adapters/README.md): Comprehensive documentation on adapter system and implementations
  - [**Cache Adapter**](./acb/adapters/cache/README.md): Memory and Redis caching
  - [**SQL Adapter**](./acb/adapters/sql/README.md): SQL database connections
  - [**Storage Adapter**](./acb/adapters/storage/README.md): File and object storage

## Acknowledgements

ACB "blocks" logo used by permission from [Andy Coe Band](https://andycoeband.com).

Special thanks to the following open-source projects for powering ACB:
- [Pydantic](https://pydantic-docs.helpmanual.io/)
- [pydantic-settings](https://pydantic-settings.helpmanual.io/)
- [bevy](https://github.com/bevy-org/bevy)
- [Loguru](https://loguru.readthedocs.io/)
- [Typer](https://typer.tiangolo.com/)

## License

This project is licensed under the terms of the BSD 3-Clause license.

## Projects Using ACB

Here are some notable projects built with ACB:

- [**FastBlocks**](https://github.com/example/fastblocks): A rapid development framework that leverages ACB's asynchronous components to build scalable web applications.

## Contributing

Contributions to ACB are welcome! We follow a workflow inspired by the Crackerjack development guidelines. To ensure consistency and high quality, please adhere to the following steps when contributing:

1. **Fork and Clone**
   Fork the repository and clone it locally.

2. **Set Up Your Development Environment**
   Use [PDM](https://pdm.fming.dev/) for dependency and virtual environment management. Add ACB as a development dependency:
   ```
   pdm add -G dev acb
   ```

3. **Run Pre-commit Hooks & Tests**
   Before submitting a pull request, ensure your changes pass all quality checks and tests. We recommend running the following command (which is inspired by Crackerjack's automated workflow):
   ```
   python -m crackerjack -x -t -p <version> -c
   ```
   *Alternatively, you can use:*
   ```
   python -m crackerjack -a <version>
   ```
   This command cleans your code, runs linting, tests, bumps the version (micro, minor, or major), and commits changes.

4. **Submit a Pull Request**
   If everything passes, submit a pull request describing your changes. Include details about your contribution and reference any related issues.

5. **Feedback and Review**
   Our maintainers will review your changes. Please be responsive to feedback and be prepared to update your pull request as needed.

For more detailed development guidelines and the Crackerjack philosophy that influences our workflow, please refer to our internal development documentation.

Happy contributing!
