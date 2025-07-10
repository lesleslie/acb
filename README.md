
<p align="center">
<img src="./images/acb-logo.png" alt="ACB Logo">
</p>

> **ACB Documentation**: [Main](./README.md) | [Core Systems](./acb/README.md) | [Actions](./acb/actions/README.md) | [Adapters](./acb/adapters/README.md)

# <u>A</u>synchronous <u>C</u>omponent <u>B</u>ase (ACB)

[![Code style: crackerjack](https://img.shields.io/badge/code%20style-crackerjack-000042)](https://github.com/lesleslie/crackerjack)
[![Python: 3.13+](https://img.shields.io/badge/python-3.13%2B-green)](https://www.python.org/downloads/)

## What is ACB?

ACB is a modular Python framework for building asynchronous applications with pluggable components. It provides a collection of self-contained **actions** and flexible **adapters** that integrate with various systems, along with a dynamic configuration and dependency injection system.

In simpler terms, ACB helps you build Python applications by providing ready-made components that you can easily plug together, configure, and extend.

ACB can be used as a standalone framework or as a foundation for higher-level frameworks. For example, [FastBlocks](https://github.com/lesleslie/fastblocks) builds on ACB to create a web application framework specifically designed for server-side rendered HTMX applications.

## Key Concepts

If you're new to ACB, here are the key concepts to understand:

1. **Actions**: Self-contained utility functions that perform specific tasks like compression, encoding, or hashing. Think of these as your toolbox of helper functions.

2. **Adapters**: Standardized interfaces to external systems like databases, caching, or storage. Adapters let you switch between different implementations (e.g., Redis vs. in-memory cache) without changing your code.

3. **Dependency Injection**: A pattern that automatically provides components to your functions when needed. This eliminates the need to manually create and pass objects around.

4. **Configuration System**: A way to configure your application using YAML files instead of hardcoding values in your code.

5. **Package Registration**: ACB automatically discovers and registers components in your application, reducing boilerplate code.

## Key Features

- **Modular Architecture**: Mix and match components to build your application
- **Asynchronous First**: Built for high-performance async operations
- **Pluggable Adapters**: Swap implementations without changing your code
- **Static Registration**: Fast, reliable adapter loading through static mappings (0.16.17+)
- **Configuration-Driven**: Change behavior through configuration rather than code
- **Type Safety**: Built on Pydantic for validation and type safety
- **Performance Optimized**: Streamlined initialization and reduced overhead (0.16.17+)

## Table of Contents

- [Key Concepts](#key-concepts)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [Architecture Overview](#architecture-overview)
- [Core Components](#core-components)
  - [Actions](#actions)
  - [Adapters](#adapters)
  - [Configuration System](#configuration-system)
  - [Dependency Injection](#dependency-injection)
- [Common Patterns](#common-patterns)
- [Use Cases](#use-cases)
- [Built-in Components](#built-in-components)
- [Debugging](#debugging)
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

> **Note**: ACB requires Python 3.13 or later.

### Optional Dependencies

ACB supports various optional dependencies for different adapters and functionality:

| Feature Group | Components | Installation Command |
|---------|------------|----------------------|
| Cache | Memory, Redis | `pdm add "acb[cache]"` |
| DNS | Domain name management (Cloud DNS, Cloudflare) | `pdm add "acb[dns]"` |
| FTPD | File transfer protocols (FTP, SFTP) | `pdm add "acb[ftpd]"` |
| Monitoring | Error tracking (Sentry), Logging (Logfire) | `pdm add "acb[monitoring]"` |
| NoSQL | Database (MongoDB, Firestore, Redis) | `pdm add "acb[nosql]"` |
| Requests | HTTP clients (HTTPX, Niquests) | `pdm add "acb[requests]"` |
| Secret | Secret management (Infisical, Secret Manager) | `pdm add "acb[secret]"` |
| SMTP | Email sending (Gmail, Mailgun) | `pdm add "acb[smtp]"` |
| SQL | Database (MySQL, PostgreSQL) | `pdm add "acb[sql]"` |
| Storage | File storage (S3, GCS, Azure, local) | `pdm add "acb[storage]"` |
| Demo | Demo/example utilities | `pdm add "acb[demo]"` |
| Development | Development tools | `pdm add "acb[dev]"` |
| Multiple Features | Combined dependencies | `pdm add "acb[cache,sql,nosql]"` |
| Web Application | Typical web app stack | `pdm add "acb[cache,sql,storage]"` |
| All Features | All optional dependencies | `pdm add "acb[all]"` |

## Architecture Overview

ACB follows a component-based architecture with automatic discovery and registration of modules:

```text
acb/
├── actions/         # Reusable utility functions (compress, encode, hash)
├── adapters/        # Integration modules for external systems
│   ├── cache/       # Memory and Redis caching
│   ├── dns/         # DNS management
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

#### What Are Actions?

Think of actions as a toolbox of utility functions that you can use anywhere in your application. Unlike adapters (which provide interfaces to external systems), actions are simple functions that perform specific tasks like compression, encoding, or hashing.

Key characteristics of actions:

- **Self-contained**: Each action is independent and doesn't rely on external services
- **Automatically available**: No need to register or initialize them
- **Categorized**: Organized by function (compress, encode, hash, etc.)
- **Consistent API**: Similar operations have similar interfaces

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
# The level parameter controls the compression level (higher = more compression but slower)
compressed = compress.brotli("Hello, ACB!", level=3)
print(f"Compressed size: {len(compressed)} bytes")

# Decompress back to the original text
original = decompress.brotli(compressed)
print(f"Original text: {original}")
```

**Example: Using the encode/decode actions**

```python
from acb.actions.encode import encode, decode

# Create a Python dictionary
data = {
    "name": "ACB Framework",
    "version": "1.0.0",
    "features": ["actions", "adapters", "dependency injection"]
}

# Encode as JSON
json_data = encode.json(data)
print(f"JSON: {json_data}")

# Encode as YAML
yaml_data = encode.yaml(data)
print(f"YAML:\n{yaml_data}")

# Decode back from JSON
original = decode.json(json_data)
print(f"Decoded: {original}")
```

**Example: Using the hash action**

```python
from acb.actions.hash import hash

# Generate a secure hash using blake3 (very fast and secure)
file_content = b"This is the content of my file"
file_hash = hash.blake3(file_content)
print(f"File hash: {file_hash}")

# Generate a CRC32C checksum (good for data integrity checks)
checksum = hash.crc32c(file_content)
print(f"Checksum: {checksum}")
```

For more detailed documentation on actions, see the [Actions README](./acb/actions/README.md).

### Adapters

Adapters provide standardized interfaces to external systems and services. Each adapter category includes a base class that defines the interface and multiple implementations.

Projects built on ACB, like FastBlocks, can extend this adapter system with domain-specific adapters while maintaining compatibility with ACB's core infrastructure.

#### Understanding the Adapter Pattern in ACB

The adapter pattern in ACB works like this:

1. **Define a standard interface** for a specific type of service (e.g., caching)
2. **Create multiple implementations** of that interface (e.g., memory cache, Redis cache)
3. **Configure which implementation to use** in your settings
4. **Use the interface in your code** without worrying about the specific implementation

This means you can switch from a memory cache to Redis by changing a single line in your configuration file, without modifying any of your application code.

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

# Method 1: Explicit adapter import
Cache = import_adapter("cache")

# Method 2: Automatic detection (convenience feature)
# ACB can automatically detect the adapter name from the variable name
Cache = import_adapter()  # Automatically detects "cache" from variable name

# Method 3: Multiple adapters - use separate calls
Cache = import_adapter("cache")
Storage = import_adapter("storage")
SQL = import_adapter("sql")

# Method 4: Multiple adapters with automatic detection
Cache, Storage, SQL = import_adapter()  # Detects all three from variable names

# Get an instance of the adapter via dependency injection
cache = depends.get(Cache)

# Use the adapter with a consistent API
# These methods work the same way regardless of whether you're using
# the memory cache or Redis implementation
async def cache_example():
    # Store a value in the cache with a 60-second TTL
    await cache.set("user:123", {"name": "John", "role": "admin"}, ttl=60)

    # Retrieve the value from cache
    user = await cache.get("user:123")
    if user:
        print(f"Found user: {user['name']}")
    else:
        print("User not found in cache")

    # Delete a value from cache
    await cache.delete("user:123")
```

**Switching Implementations**

To switch from memory cache to Redis, just update your `settings/adapters.yml` file:

```yaml
# Use in-memory cache (good for development)
cache: memory

# OR

# Use Redis cache (good for production)
cache: redis
```

Your application code remains exactly the same!

For more detailed documentation on adapters, see the [Adapters README](./acb/adapters/README.md).

### Configuration System

ACB's configuration system is built on Pydantic and supports multiple configuration sources:

- **YAML Files**: Environment-specific settings in YAML format
- **Secret Files**: Secure storage of sensitive information
- **Secret Managers**: Integration with external secret management services

#### Example: Defining custom settings

```python
from acb.config import Settings
import typing as t
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

#### How Dependency Injection Works in ACB

```
┌─────────────────────┐      ┌─────────────────────┐
│                     │      │                     │
│  Your Application   │      │   ACB Components    │
│                     │      │                     │
└──────────┬──────────┘      └──────────┬──────────┘
           │                            │
           │                            │
           ▼                            ▼
┌─────────────────────────────────────────────────┐
│                                                 │
│             Dependency Registry                 │
│                                                 │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────┐  │
│  │   Config    │  │   Cache     │  │ Logger  │  │
│  └─────────────┘  └─────────────┘  └─────────┘  │
│                                                 │
└─────────────────────────────────────────────────┘
                        │
                        │
                        ▼
┌─────────────────────────────────────────────────┐
│                                                 │
│             @depends.inject                     │
│                                                 │
│  Automatically injects dependencies into your   │
│  functions based on type annotations or         │
│  explicit depends() calls                       │
│                                                 │
└─────────────────────────────────────────────────┘
```

**Example: Using dependency injection**

```python
import typing as t

from acb.depends import depends
from acb.config import Config
from acb.logger import Logger
from ._base import MyServiceBase



class MyService(MyServiceBase):
    async def process_data(self, data: dict[str, t.Any]) -> dict[str, t.Any]:
        # Process data...
        return result

    async def init(self):
        await super().init()

# Register your custom component
depends.set(MyService)  # Now MyService is available in the dependency registry

# Inject dependencies into functions
@depends.inject  # This decorator automatically injects the dependencies
async def process_data(data: dict[str, t.Any],
                      config: Config = depends(),  # Injected based on type
                      logger: Logger = depends() # Injected by name
                      ):
    # Now you can use config and logger without manually creating them
    logger.info(f"Processing data with app: {config.app.name}")
    # Process data...
    return result
```

#### Benefits of Dependency Injection

1. **Reduced Boilerplate**: No need to manually create and pass objects
2. **Testability**: Easy to mock dependencies for testing
3. **Flexibility**: Change implementations without changing your code
4. **Decoupling**: Components don't need to know how to create their dependencies

## Getting Started

### Basic Application Setup

Let's walk through creating a simple ACB application step by step:

1. **Create a new project with PDM:**

```bash
# Create a directory for your project
mkdir myapp
cd myapp

# Initialize a new Python project with PDM
pdm init

# Add ACB as a dependency
pdm add acb
```

2. **Create a basic application structure:**

ACB works best with a specific directory structure. Here's what you should create:

```
myapp/                  # Root project directory
├── myapp/              # Your application package
│   ├── __init__.py     # Makes myapp a Python package
│   ├── actions/        # Directory for your custom actions
│   │   └── __init__.py # Makes actions a subpackage
│   ├── adapters/       # Directory for your custom adapters
│   │   └── __init__.py # Makes adapters a subpackage
│   └── main.py         # Your application entry point
└── settings/           # Configuration directory
    ├── app.yml         # Application settings
    ├── debug.yml       # Debug settings
    └── adapters.yml    # Adapter configuration
```

3. **Create basic configuration files:**

Let's create a simple `settings/app.yml` file:

```yaml
# settings/app.yml
app:
  name: "MyApp"        # Your application name
  title: "My ACB App"  # Display title
  version: "0.1.0"     # Version number
```

And a simple `settings/adapters.yml` file:

```yaml
# settings/adapters.yml
# Choose which adapter implementations to use
cache: memory          # Use in-memory cache
logger: loguru         # Use Loguru for logging
storage: file          # Use file system storage
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
storage: file
```

## Common Patterns

Here are some common patterns and examples that will help you get started with ACB:

### 1. Using Dependency Injection

Dependency injection is a core concept in ACB. Here's how to use it effectively:

```python
from acb.depends import depends
from acb.config import Config
from acb.adapters import import_adapter

# Import adapter classes
Cache, Storage = import_adapter()  # This gets the configured cache and storage adapters

# Method 1: Using depends.get() directly
def direct_injection_example():
    # Get instances when you need them
    config = depends.get()
    cache = depends.get()

    # Use the components
    print(f"App name: {config.app.name}")

# Method 2: Using the @depends.inject decorator (recommended)
@depends.inject
async def process_file(filename: str,
                     cache: Cache =depends(),       # Injected automatically
                     storage: Storage = depends(),  # Injected automatically
                     config: Config = depends()     # Injected automatically
                       ):
    # All dependencies are automatically provided
    print(f"Processing {filename} for app {config.app.name}")

    # Check if file is cached
    content = await cache.get(f"file:{filename}")
    if not content:
        # If not in cache, get from storage
        content = await storage.get_file(filename)
        if content:
            # Store in cache for next time
            await cache.set(f"file:{filename}", content, ttl=3600)
    return content
```

### 2. Working with Configuration

ACB's configuration system makes it easy to manage settings:

```python
from acb.depends import depends
from acb.config import Config

# Get the configuration
config = depends.get(Config)

# Access standard app settings
app_name = config.app.name
app_version = config.app.version

# Access adapter-specific settings
cache_ttl = config.cache.default_ttl
storage_bucket = config.storage.buckets.media

# Access debug settings
debug_mode = config.debug.enabled
```

### 3. Using Actions

Actions are utility functions that perform specific tasks:

```python
# Using compression actions
from acb.actions.compress import compress, decompress

# Compress data with brotli
compressed_data = compress.brotli("Hello, ACB!", level=4)

# Decompress it back
original_data = decompress.brotli(compressed_data)

# Using encoding actions
from acb.actions.encode import encode, decode

# Encode data as JSON
json_data = encode.json({"message": "Hello, ACB!"})

# Decode it back
original_dict = decode.json(json_data)

# Using hash actions
from acb.actions.hash import hash

# Generate a secure hash
file_hash = hash.blake3(b"file content")
```

## Built-in Components

### Debug Module

ACB provides comprehensive debugging tools to help troubleshoot your application:

- **Granular debug levels**: Control debug output for specific components
- **Pretty-printed output**: Human-readable debug information
- **Performance timers**: Measure and optimize execution time

```python
# Using the timeit decorator to measure performance
from acb.debug import timeit

@timeit
async def slow_operation():
    # This function's execution time will be logged
    await asyncio.sleep(1)
    return "Done"
```

### Logging

The framework includes a robust logging system with structured logging and multiple output formats:

- **Asynchronous logging**: Non-blocking log operations
- **Structured data**: JSON-formatted logs for better analysis
- **Multiple adapters**: Choose between different logging implementations

```python
# Get a logger instance
logger = depends.get("logger")

# Different log levels
logger.debug("Detailed information for debugging")
logger.info("General information about program execution")
logger.warning("Warning about potential issues")
logger.error("Error that doesn't stop the program")
logger.critical("Critical error that might stop the program")

# Structured logging with context
logger.info("User logged in", user_id=123, ip_address="192.168.1.1")
```

## Use Cases

Here are some common use cases for ACB and how to implement them:

### 1. Building a Data Processing Pipeline

ACB is great for building data processing pipelines that need to handle different data sources and storage options:

```python
from acb.depends import depends
from acb.adapters import import_adapter
from acb.actions.encode import encode, decode
from acb.actions.compress import compress, decompress
import typing as t

# Import adapters
Storage = import_adapter("storage")
Cache = import_adapter("cache")
SQL = import_adapter("sql")

@depends.inject
async def process_data_pipeline(data_id: str,
                              storage=depends(Storage),
                              cache=depends(Cache),
                              sql=depends(SQL)):
    # Step 1: Check if processed data is in cache
    processed_data = await cache.get(f"processed:{data_id}")
    if processed_data:
        return decode.json(decompress.brotli(processed_data))

    # Step 2: If not in cache, check if raw data is in storage
    raw_data = await storage.get_file(f"data/{data_id}.json")
    if not raw_data:
        # Step 3: If not in storage, fetch from database
        raw_data = await sql.fetch_one(
            "SELECT data FROM raw_data WHERE id = ?", data_id
        )
        if raw_data:
            # Save to storage for future use
            await storage.put_file(f"data/{data_id}.json", raw_data["data"])

    if not raw_data:
        return None

    # Step 4: Process the data
    data_dict = decode.json(raw_data)
    processed_result = transform_data(data_dict)  # Your processing function

    # Step 5: Cache the processed result
    compressed_result = compress.brotli(encode.json(processed_result))
    await cache.set(f"processed:{data_id}", compressed_result, ttl=3600)

    return processed_result
```

### 2. Building a Configuration Management System

ACB's configuration system makes it easy to build a configuration management system:

```python
from acb.depends import depends
from acb.config import Config, Settings
from pydantic import SecretStr

# Define custom settings models
class DatabaseSettings(Settings):
    host: str = "localhost"
    port: int = 5432
    username: str = "postgres"
    password: SecretStr = SecretStr("")
    database: str = "myapp"

class ApiSettings(Settings):
    base_url: str = "https://api.example.com"
    version: str = "v1"
    timeout: int = 30
    api_key: SecretStr = SecretStr("")

# Access configuration
@depends.inject
async def initialize_services(config=depends(Config)):
    # Access standard app settings
    app_name = config.app.name
    app_version = config.app.version

    # Access custom settings
    db_config = config.database
    api_config = config.api

    print(f"Initializing {app_name} v{app_version}")
    print(f"Connecting to database {db_config.database} at {db_config.host}:{db_config.port}")
    print(f"Using API at {api_config.base_url}/{api_config.version}")
```

### 3. Building a Caching Layer

ACB's cache adapter makes it easy to implement caching:

```python
from acb.depends import depends
from acb.adapters import import_adapter
from acb.actions.encode import encode, decode
import typing as t
import time
import asyncio

Cache = import_adapter("cache")

@depends.inject
async def get_user_data(user_id: int, cache=depends(Cache)):
    # Try to get from cache first
    cache_key = f"user:{user_id}"
    cached_data = await cache.get(cache_key)

    if cached_data:
        print("Cache hit!")
        return decode.json(cached_data)

    print("Cache miss, fetching from database...")
    # Simulate database query
    await asyncio.sleep(1)  # Slow database query

    # In a real app, you would fetch from a database
    user_data = {
        "id": user_id,
        "name": f"User {user_id}",
        "email": f"user{user_id}@example.com",
        "created_at": time.time()
    }

    # Cache the result for future requests
    await cache.set(cache_key, encode.json(user_data), ttl=300)  # Cache for 5 minutes

    return user_data
```

## Performance (ACB 0.16.17+)

ACB 0.16.17 introduces significant performance improvements:

### Adapter System Performance

- **Static Mappings**: Replaced dynamic discovery with hardcoded mappings for 50-70% faster adapter loading
- **Reduced Import Overhead**: Eliminated runtime module scanning and discovery
- **Lock-based Initialization**: Prevents duplicate adapter initialization in concurrent scenarios
- **Cached Registration**: Adapter registry caching reduces repeated lookups

### Configuration System Performance

- **Library Mode Detection**: Automatic detection reduces configuration overhead when ACB is used as a dependency
- **Lazy Loading**: Configuration components are loaded only when needed
- **Optimized File Operations**: Reduced filesystem operations during startup
- **Smart Caching**: Configuration values are cached to avoid repeated parsing

### Memory and Cache Performance

- **aiocache Integration**: Memory cache now uses optimized aiocache backend
- **PickleSerializer**: Faster serialization for complex Python objects
- **Connection Pooling**: Improved Redis connection management
- **Zero-timeout Operations**: Memory cache optimized for local access

### Dependency System Performance

- **Removed Mock System**: Eliminated `tests/mocks/` overhead, reducing startup time by 30-40%
- **Streamlined Dependencies**: Major cleanup of PDM lock file with optimized dependencies
- **Faster Injection**: Improved dependency injection performance through better caching

### Performance Comparison

| Component | Pre-0.16.17 | 0.16.17+ | Improvement |
|-----------|-------------|----------|-------------|
| Adapter Loading | ~50-100ms | ~15-30ms | 50-70% faster |
| Memory Cache Ops | ~0.2-0.5ms | ~0.1-0.2ms | 50% faster |
| Configuration Load | ~20-40ms | ~10-20ms | 50% faster |
| Test Startup | ~200-400ms | ~100-200ms | 50% faster |

### Benchmarking Your Application

To measure performance improvements in your application:

```python
from acb.debug import timeit
import asyncio

@timeit
async def benchmark_adapter_loading():
    from acb.adapters import import_adapter
    Cache, Storage, SQL = import_adapter()
    return "Adapters loaded"

@timeit
async def benchmark_cache_operations():
    from acb.adapters import import_adapter
    from acb.depends import depends

    Cache = import_adapter("cache")
    cache = depends.get(Cache)

    # Benchmark cache operations
    await cache.set("test_key", {"data": "test"}, ttl=60)
    result = await cache.get("test_key")
    await cache.delete("test_key")
    return result

# Run benchmarks
asyncio.run(benchmark_adapter_loading())
asyncio.run(benchmark_cache_operations())
```

## Debugging

ACB provides a comprehensive debugging system that helps you troubleshoot your applications effectively. While a brief overview is provided in the [Built-in Components](#built-in-components) section, this section offers a more detailed look at ACB's debugging capabilities.

### Debug Module Features

The debug module in ACB (`acb/debug.py`) offers several powerful features:

- **Enhanced Debug Output**: Using the `debug` function (powered by icecream) for better visibility
- **Pretty Printing**: Format complex objects for better readability
- **Performance Timing**: Measure execution time of functions with the `timeit` decorator
- **Environment-Aware Behavior**: Different debugging behavior in development vs. production
- **Colorized Output**: Improved readability with color-coded debug information

### Using the Debug Module

Here are some examples of how to use ACB's debugging features:

```python
from acb.debug import debug, timeit, pprint
import asyncio

# Basic debugging - prints the expression and its value
user_id = 123
debug(user_id)  # Output: debug: user_id = 123

# Debug complex objects with pretty formatting
user_data = {"id": 123, "name": "John", "roles": ["admin", "editor"], "settings": {"theme": "dark", "notifications": True}}
debug(user_data)  # Outputs a nicely formatted representation of the dictionary

# Measure function execution time
@timeit
async def fetch_data():
    await asyncio.sleep(0.5)  # Simulate network request
    return {"status": "success"}

# The execution time will be automatically logged when the function is called
result = await fetch_data()  # Output: fetch_data took 0.501s

# Asynchronous pretty printing for complex objects
await pprint(result)  # Prints the result with nice formatting to stderr
```

### Debug Configuration

ACB's debug behavior can be configured through your application settings:

```yaml
# settings/debug.yml
debug:
  enabled: true           # Enable/disable debugging globally
  production: false       # Production mode changes debug behavior
  log_level: "DEBUG"      # Set the debug log level
  # Module-specific debug settings
  cache: true             # Enable debugging for cache module
  storage: false          # Disable debugging for storage module
```

### Environment-Aware Debugging

ACB's debugging system automatically adjusts its behavior based on the environment:

- **Development Mode**: Verbose output with context information and colorization
- **Production Mode**: Minimal output focused on essential information
- **Deployed Environment**: Debug output is routed to the logging system instead of stderr

This ensures that you get detailed information during development while avoiding performance impacts in production.

### Advanced Debugging Techniques

For more complex debugging scenarios, ACB provides additional utilities:

```python
from acb.debug import get_calling_module, patch_record
from acb.depends import depends
from acb.logger import Logger

# Get the module that called the current function
module = get_calling_module()

# Patch log records with module information
logger = depends.get(Logger)
patch_record(module, "Debug message with module context")
```

For more detailed information about debugging in ACB, see the [Core Systems documentation](./acb/README.md#3-debugging-tools).

## Advanced Usage

### Creating Custom Actions

Create your own reusable actions by adding Python modules to the actions directory:

```python
# myapp/actions/validate.py
from pydantic import BaseModel
import re
import typing as t

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
from typing import Protocol

class PaymentBaseSettings(Settings):
    currency: str = "USD"
    default_timeout: int = 30

class PaymentBase(AdapterBase, Protocol):
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
import typing as t

class StripeSettings(PaymentBaseSettings):
    api_key: SecretStr = SecretStr("sk_test_default")

class Stripe(PaymentBase):
    settings: StripeSettings | None = None

    async def init(self) -> None:
        if self.settings:
            stripe.api_key = self.settings.api_key.get_secret_value()

    async def charge(self, amount: float, description: str) -> str:
        response: t.Any = await stripe.PaymentIntent.create(
            amount=int(amount * 100),  # Convert to cents
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
- [AnyIO](https://anyio.readthedocs.io/)
- [msgspec](https://jcristharif.com/msgspec/)
- [Logfire](https://docs.logfire.dev/)
- [Sentry](https://docs.sentry.io/)

## License

This project is licensed under the terms of the BSD 3-Clause license.

## Projects Using ACB

Here are some notable projects built with ACB:

- [**FastBlocks**](https://github.com/lesleslie/fastblocks): A web application framework that directly extends Starlette while leveraging ACB's component architecture to create a powerful platform for server-side rendered HTMX applications. FastBlocks combines Starlette's ASGI capabilities with ACB's infrastructure, adding web-specific adapters for templates, routing, authentication, and admin interfaces.

## Contributing

Contributions to ACB are welcome! We follow a workflow inspired by the Crackerjack development guidelines. To ensure consistency and high quality, please adhere to the following steps when contributing:

1. **Fork and Clone**
   Fork the repository and clone it locally.

2. **Set Up Your Development Environment**
   Use [PDM](https://pdm.fming.dev/) for dependency and virtual environment management. ACB requires Python 3.13 or later. Add ACB as a development dependency:
   ```
   pdm add -G dev acb
   ```

3. **Code Style and Type Checking**
   ACB uses modern Python typing features and follows strict type checking. We use:
   - Type annotations with the latest Python 3.13 syntax
   - Protocols instead of ABC for interface definitions
   - Union types with the `|` operator instead of `Union[]`
   - Type checking with pyright in strict mode
   - Ruff for linting and formatting

4. **Run Pre-commit Hooks & Tests**
   Before submitting a pull request, ensure your changes pass all quality checks and tests. We recommend running the following command (which is inspired by Crackerjack's automated workflow):
   ```
   python -m crackerjack -x -t -p <version> -c
   ```
   *Alternatively, you can use:*
   ```
   python -m crackerjack -a <version>
   ```
   This command cleans your code, runs linting, tests, bumps the version (micro, minor, or major), and commits changes.

5. **Testing**
   All tests are written using pytest and should include coverage reporting:
   ```
   pytest --cov=acb
   ```
   Test configuration is in pyproject.toml, not in separate .coveragerc or pytest.ini files.

6. **Submit a Pull Request**
   If everything passes, submit a pull request describing your changes. Include details about your contribution and reference any related issues.

7. **Feedback and Review**
   Our maintainers will review your changes. Please be responsive to feedback and be prepared to update your pull request as needed.

For more detailed development guidelines and the Crackerjack philosophy that influences our workflow, please refer to our internal development documentation.

Happy contributing!
