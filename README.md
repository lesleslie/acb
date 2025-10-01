---
id: 01K6GSRDW7QQ66H8362D1NC6KY
---
______________________________________________________________________

## id: 01K6GSM8PZP64CR5519M4JQ6QQ

______________________________________________________________________

## id: 01K6GPA63E9SY7R3TM6ZWMB09Q

______________________________________________________________________

## id: 01K6GMDSVKDX9VRSEP2H0HH22X

______________________________________________________________________

## id: 01K6GKSYP9KTZ6Y05QH0ZAV8DB

______________________________________________________________________

## id: 01K6GKJQJYQCKHNTTPXY30M8HT

______________________________________________________________________

## id: 01K6GJYJ7M3NK8RAV1GN44J2DA

______________________________________________________________________

## id: 01K6GGMCACAEJ5MMJMWKF98K8E

______________________________________________________________________

## id: 01K6G68CNCRTWXMZXJEHCS7Q4P

______________________________________________________________________

## id: 01K6G5HWQR7HRQB12K1A46503K

______________________________________________________________________

## id: 01K6G58NP7VVD8GQ0ZGYTMJQST

______________________________________________________________________

## id: 01K6G4MMMKS3Z00WPGZF5QGNY7

______________________________________________________________________

## id: 01K6G3RCK29QEVJX9PM5AYG0B4

______________________________________________________________________

## id: 01K6G399PH280SJJEW0QRRM96Q

______________________________________________________________________

## id: 01K6FZP8DW67E13PT0ATMTF8NS

______________________________________________________________________

## id: 01K6FY3WB0EGJYESBDVYCHYCN5

______________________________________________________________________

## id: 01K6FVEBAD0X204NYV1TR4DN80

______________________________________________________________________

## id: 01K6FV1E371JSRE4SJZAAEQYAC

<p align="center">
<img src="./images/acb-logo.png" alt="ACB Logo">
</p>

> **ACB Documentation**: \[[README|Main]\] | \[[acb/README|Core Systems]\] | \[[acb/actions/README|Actions]\] | \[[acb/adapters/README|Adapters]\]

# <u>A</u>synchronous <u>C</u>omponent <u>B</u>ase (ACB)

[![Code style: crackerjack](https://img.shields.io/badge/code%20style-crackerjack-000042)](https://github.com/lesleslie/crackerjack)
[![Python: 3.13+](https://img.shields.io/badge/python-3.13%2B-green)](https://www.python.org/downloads/)
![Coverage](https://img.shields.io/badge/coverage-42.3%25-red)

## What is ACB?

ACB is a modular Python framework for building asynchronous applications with pluggable components. It provides a collection of self-contained **actions** and flexible **adapters** that integrate with various systems, along with a dynamic configuration and dependency injection system.

In simpler terms, ACB helps you build Python applications by providing ready-made components that you can easily plug together, configure, and extend.

ACB can be used as a standalone framework or as a foundation for higher-level frameworks. For example, [FastBlocks](https://github.com/lesleslie/fastblocks) builds on ACB to create a web application framework specifically designed for server-side rendered HTMX applications.

## Key Concepts

If you're new to ACB, here are the key concepts to understand:

1. **Actions**: Self-contained utility functions that perform specific tasks like compression, encoding, or hashing. Think of these as your toolbox of helper functions.

1. **Adapters**: Standardized interfaces to external systems like databases, caching, or storage. Adapters let you switch between different implementations (e.g., Redis vs. in-memory cache) without changing your code.

1. **Dependency Injection**: A pattern that automatically provides components to your functions when needed. This eliminates the need to manually create and pass objects around.

1. **Configuration System**: A way to configure your application using YAML files instead of hardcoding values in your code.

1. **Package Registration**: ACB automatically discovers and registers components in your application, reducing boilerplate code.

## Key Features

- **Modular Architecture**: Mix and match components to build your application
- **Asynchronous First**: Built for high-performance async operations
- **Pluggable Adapters**: Swap implementations without changing your code
- **Dynamic Discovery**: Convention-based adapter detection and configuration-driven selection
- **Configuration-Driven**: Change behavior through configuration rather than code
- **Type Safety**: Built on Pydantic for validation and type safety
- **Performance Optimized**: Streamlined initialization and reduced overhead (0.18.0+)
- **Simple & Reliable**: Focused on core adapter functionality without over-engineering (0.19.3+)
- **Basic Security**: Essential SSL/TLS configuration and secure defaults
- **Resource Cleanup**: Simple resource management patterns with automatic cleanup

## Table of Contents

- \[[#key-concepts|Key Concepts]\]
- \[[#installation|Installation]\]
- \[[#quick-start|Quick Start]\]
- \[[#architecture-overview|Architecture Overview]\]
- \[[#core-components|Core Components]\]
  - \[[#actions|Actions]\]
  - \[[#adapters|Adapters]\]
  - \[[#universal-query-interface|Universal Query Interface]\]
  - \[[#configuration-system|Configuration System]\]
  - \[[#dependency-injection|Dependency Injection]\]
- \[[#common-patterns|Common Patterns]\]
- \[[#use-cases|Use Cases]\]
- \[[#built-in-components|Built-in Components]\]
- \[[#security-features|Security Features]\]
- \[[#basic-monitoring|Basic Monitoring]\]
- \[[#debugging|Debugging]\]
- \[[#advanced-usage|Advanced Usage]\]
- \[[#documentation|Documentation]\]
- \[[#acknowledgements|Acknowledgements]\]
- \[[#license|License]\]
- \[[#projects-using-acb|Projects Using ACB]\]
- \[[#contributing|Contributing]\]

## Installation

Install ACB using [uv](https://docs.astral.sh/uv/):

```bash
uv add acb
```

> **Note**: ACB requires Python 3.13 or later.

### Optional Dependencies

ACB supports various optional dependencies for different adapters and functionality:

| Feature Group | Components | Installation Command |
| ----------------- | ---------------------------------------------------------------------------------- | ---------------------------------------- |
| Secret | Secret management (Infisical, Secret Manager) | `uv add "acb[secret]` |
| SMTP | Email sending (Gmail, Mailgun) | `uv add "acb[smtp]` |
| SQL | Database (MySQL, PostgreSQL) | `uv add "acb[sql]` |
| Storage | File storage (S3, GCS, Azure, local) | `uv add "acb[storage]` |
| Vector | Vector database (DuckDB with VSS, with Weaviate, OpenSearch, Qdrant planned) | `uv add "acb[vector]` |
| Demo | Demo/example utilities | `uv add "acb[demo]` |
| Development | Development tools | `uv add "acb[dev]` |
| Multiple Features | Combined dependencies | `uv add "acb[models,cache,sql,nosql]` |
| Web Application | Typical web app stack | `uv add "acb[models,cache,sql,storage]` |
| Web Application Plus | Web app stack with vector support | `uv add "acb[webapp-plus]` |
| All Features | All optional dependencies | `uv add "acb[all]` |

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
│   ├── vector/      # Vector database adapters (DuckDB with VSS)
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
| ----------------------- | -------------------------- | ------------------------- |
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
    "features": ["actions", "adapters", "dependency injection"],
}

# Encode as JSON (async method)
json_data = await encode.json(data)
print(f"JSON: {json_data}")

# Encode as YAML (async method)
yaml_data = await encode.yaml(data)
print(f"YAML:\n{yaml_data}")

# Decode back from JSON (async method)
original = await decode.json(json_data)
print(f"Decoded: {original}")
```

**Example: Using the hash action**

```python
from acb.actions.hash import hash

# Generate a secure hash using blake3 (very fast and secure) - async method
file_content = b"This is the content of my file"
file_hash = await hash.blake3(file_content)
print(f"File hash: {file_hash}")

# Generate a CRC32C checksum (good for data integrity checks) - async method
checksum = await hash.crc32c(file_content)
print(f"Checksum: {checksum}")
```

For more detailed documentation on actions, see the \[[acb/actions/README|Actions README]\].

### Adapters

Adapters provide standardized interfaces to external systems and services. Each adapter category includes a base class that defines the interface and multiple implementations.

Projects built on ACB, like FastBlocks, can extend this adapter system with domain-specific adapters while maintaining compatibility with ACB's core infrastructure.

#### Understanding the Adapter Pattern in ACB

ACB uses **dynamic discovery** with convention-based adapter loading:

1. **Convention-Based Discovery**: Adapters are automatically detected based on directory structure (`acb/adapters/{category}/{implementation}.py`)
1. **Configuration-Driven Selection**: Choose which implementation to use via `settings/adapters.yml`
1. **Lazy Loading**: Adapters are loaded and initialized only when needed
1. **Dependency Injection**: Seamlessly integrated with ACB's dependency system

This means you can switch from memory cache to Redis by changing a single line in your configuration file, without modifying any of your application code - ACB automatically discovers and loads the correct implementation.

#### Key Adapter Categories

| Adapter Category | Description | Implementations |
| ---------------- | ----------------------- | ---------------------------------------------------------- |
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

For more detailed documentation on adapters, see the \[[acb/adapters/README|Adapters README]\].

### Universal Query Interface

ACB provides a powerful Universal Query Interface that allows you to write database queries that work consistently across both SQL and NoSQL databases, while maintaining full type safety and supporting multiple query patterns.

#### Key Benefits

- **Database Agnostic**: Write queries that work with MySQL, PostgreSQL, MongoDB, Firestore, and Redis
- **Universal Model Support**: Automatically works with SQLModel, SQLAlchemy, Pydantic, msgspec, attrs, and Redis-OM
- **Intelligent Auto-Detection**: Automatically detects model types - no configuration needed
- **Multiple Query Styles**: Choose between Simple, Repository, Specification, and Advanced patterns
- **Type Safety**: Full generic type support with automatic serialization/deserialization
- **Composable Business Logic**: Build complex rules with the Specification pattern
- **Multi-Framework Applications**: Use different model frameworks in the same application

#### Universal Model Framework Support

ACB's Models adapter automatically detects and works with multiple model frameworks seamlessly:

```python
from sqlmodel import SQLModel, Field
from pydantic import BaseModel
import msgspec
import attrs
from acb.adapters import import_adapter

# Get the models adapter - auto-detects all framework types
Models = import_adapter("models")
models = depends.get(Models)


# SQLModel for SQL databases - automatically detected
class User(SQLModel, table=True):
    id: int = Field(default=None, primary_key=True)
    name: str
    email: str


# SQLAlchemy for traditional ORM - automatically detected
from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


class Product(Base):
    __tablename__ = "products"
    id = Column(Integer, primary_key=True)
    name = Column(String(100))
    price = Column(Integer)


# Pydantic for API DTOs - automatically detected
class UserCreateRequest(BaseModel):
    name: str
    email: str


# msgspec for high-performance serialization - automatically detected
class UserSession(msgspec.Struct):
    user_id: str
    token: str
    expires_at: int


# attrs for mature applications - automatically detected
@attrs.define
class UserProfile:
    bio: str
    avatar_url: str


# All work with the same universal query interface!
print(models.auto_detect_model_type(User))  # "sqlmodel"
print(models.auto_detect_model_type(Product))  # "sqlalchemy"
print(models.auto_detect_model_type(UserCreateRequest))  # "pydantic"
print(models.auto_detect_model_type(UserSession))  # "msgspec"
print(models.auto_detect_model_type(UserProfile))  # "attrs"

# Get the right adapter automatically
user_adapter = models.get_adapter_for_model(User)  # SQLModelAdapter
product_adapter = models.get_adapter_for_model(Product)  # SQLAlchemyModelAdapter
dto_adapter = models.get_adapter_for_model(UserCreateRequest)  # PydanticModelAdapter
session_adapter = models.get_adapter_for_model(UserSession)  # MsgspecModelAdapter
profile_adapter = models.get_adapter_for_model(UserProfile)  # AttrsModelAdapter
```

**Why This Matters**: You can migrate between frameworks, use different frameworks for different purposes, or gradually adopt new frameworks without rewriting your query logic.

#### Query Patterns

**Simple Query Style** - Active Record-like interface for basic CRUD operations:

```python
from acb.adapters.models._hybrid import ACBQuery
from sqlmodel import SQLModel, Field


class User(SQLModel, table=True):
    id: int = Field(default=None, primary_key=True)
    name: str
    email: str
    active: bool = True


# Setup query interface
query = ACBQuery()

# Simple CRUD operations that work with any database
users = await query.for_model(User).simple.all()
user = await query.for_model(User).simple.find(1)
new_user = await query.for_model(User).simple.create(
    {"name": "John Doe", "email": "john@example.com"}
)
```

**Repository Pattern** - Domain-driven design with built-in caching:

```python
from acb.adapters.models._repository import RepositoryOptions

# Configure repository with caching and audit trails
repo = query.for_model(User).repository(
    RepositoryOptions(
        cache_enabled=True, cache_ttl=300, enable_soft_delete=True, audit_enabled=True
    )
)

# Domain-specific methods
active_users = await repo.find_active()
recent_users = await repo.find_recent(days=7)
```

**Specification Pattern** - Composable business rules:

```python
from acb.adapters.models._specification import field, range_spec

# Create reusable specifications
active_spec = field("active").equals(True)
adult_spec = field("age").greater_than_or_equal(18)
email_spec = field("email").like("%@company.com")

# Combine specifications
company_employees = active_spec & adult_spec & email_spec

# Use across different query styles
users = await query.for_model(User).specification.with_spec(company_employees).all()
```

**Advanced Query Builder** - Full control over query construction:

```python
# Complex queries with method chaining
users = await (
    query.for_model(User)
    .advanced.where("active", True)
    .where_gt("age", 21)
    .where_in("department", ["engineering", "product"])
    .order_by_desc("created_at")
    .limit(10)
    .all()
)
```

#### Database Switching

The same query code works across different databases. Switch implementations by changing your configuration:

```yaml
# Use SQL database (PostgreSQL, MySQL, SQLite)
adapters.yml:
  sql: postgresql

# OR use NoSQL database (MongoDB, Firestore, Redis)
adapters.yml:
  nosql: mongodb
```

Your query code remains identical regardless of the database backend!

#### Hybrid Database Architecture

Use different databases for different models in the same application:

```python
# Users in SQL database
sql_query = ACBQuery(database_adapter_name="sql", model_adapter_name="sqlmodel")
users = await sql_query.for_model(User).simple.all()

# User activity in NoSQL database
nosql_query = ACBQuery(database_adapter_name="nosql", model_adapter_name="pydantic")
activity = await nosql_query.for_model(UserActivity).simple.all()
```

For comprehensive documentation and examples, see the \[[acb/adapters/models/README|Models Adapter Documentation]\].

### MCP Server

ACB includes a comprehensive Model Context Protocol (MCP) server that provides a standardized interface for AI applications to interact with the entire ACB ecosystem. The MCP server acts as a central orchestration layer that exposes all of ACB's capabilities through the Model Context Protocol, enabling AI assistants like Claude to discover, interact with, and orchestrate ACB components.

#### Key Features

- **Universal Component Discovery**: List all available actions, adapters, services, and other components in a single interface
- **Action Execution**: Execute any registered action with parameter validation across all action categories
- **Adapter Management**: Enable, disable, or configure adapters dynamically with real-time status monitoring
- **Workflow Orchestration**: Define and execute complex multi-step workflows that span across different component types
- **Health Monitoring**: Check the health status of all system components with detailed diagnostic information
- **Resource Access**: Access component registry information, system metrics, and real-time event streams
- **AI/ML Integration**: Seamlessly integrate with AI/ML adapters for LLM interactions, embedding generation, and model serving

#### Architecture

The MCP server is built on top of ACB's existing architecture and provides a unified interface for:

- **Actions**: Business logic components that perform specific tasks (compression, encoding, hashing, etc.)
- **Adapters**: Interface components that connect to external systems (databases, caches, storage, etc.)
- **Services**: Background services that provide ongoing functionality (when implemented)
- **Events**: Event-driven communication between components
- **AI/ML Components**: Integration with LLMs, embedding models, and ML serving platforms
- **Configuration**: Centralized configuration management
- **Logging**: Structured logging and monitoring

#### Example Usage with AI Assistants

The MCP server can be easily integrated with AI assistants like Claude Desktop:

```json
{
  "mcpServers": {
    "acb": {
      "command": "uv",
      "args": [
        "run",
        "python",
        "-m",
        "acb.mcp.server"
      ],
      "env": {
        "ACB_MCP_HOST": "127.0.0.1",
        "ACB_MCP_PORT": "8000"
      }
    }
  }
}
```

Once configured, AI assistants can:

1. Discover all available ACB components through a single endpoint
1. Execute actions like compressing data or generating hashes
1. Interact with adapters to access databases, storage, or caching systems
1. Orchestrate complex workflows that combine multiple operations
1. Monitor system health and access real-time metrics

For more details on the MCP server implementation, see the \[[acb/mcp/README|MCP Server Documentation]\] and \[[claude_desktop_config.json|example configurations]\].

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
async def process_data(
    data: dict[str, t.Any],
    config: Config = depends(),  # Injected based on type
    logger: Logger = depends(),  # Injected by name
):
    # Now you can use config and logger without manually creating them
    logger.info(f"Processing data with app: {config.app.name}")
    # Process data...
    return result
```

#### Benefits of Dependency Injection

1. **Reduced Boilerplate**: No need to manually create and pass objects
1. **Testability**: Easy to mock dependencies for testing
1. **Flexibility**: Change implementations without changing your code
1. **Decoupling**: Components don't need to know how to create their dependencies

````

## Getting Started

### Basic Application Setup

Let's walk through creating a simple ACB application step by step:

1. **Create a new project with UV:**

```bash
# Create a directory for your project
mkdir myapp
cd myapp

# Initialize a new Python project with UV
uv init

# Add ACB as a dependency
uv add acb
````

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
async def process_file(
    filename: str,
    cache: Cache = depends(),  # Injected automatically
    storage: Storage = depends(),  # Injected automatically
    config: Config = depends(),  # Injected automatically
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
async def process_data_pipeline(
    data_id: str, storage=depends(Storage), cache=depends(Cache), sql=depends(SQL)
):
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
    print(
        f"Connecting to database {db_config.database} at {db_config.host}:{db_config.port}"
    )
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
        "created_at": time.time(),
    }

    # Cache the result for future requests
    await cache.set(cache_key, encode.json(user_data), ttl=300)  # Cache for 5 minutes

    return user_data
```

## Performance (ACB 0.19.0+)

ACB 0.19.0+ introduces significant performance improvements and architectural simplification:

### Adapter System Performance

- **Dynamic Discovery**: Convention-based adapter detection with caching for 50-70% faster adapter loading
- **Lazy Loading**: Adapters are loaded and initialized only when needed
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

| Component | Pre-0.18.0 | 0.19.0+ | Improvement |
| ------------------ | ---------- | ---------- | ------------- |
| Adapter Loading | ~50-100ms | ~10-25ms | 60-80% faster |
| Memory Cache Ops | ~0.2-0.5ms | ~0.05-0.1ms | 70% faster |
| Configuration Load | ~20-40ms | ~8-15ms | 60% faster |
| Test Startup | ~200-400ms | ~80-150ms | 60% faster |
| Basic Resource Cleanup | N/A | ~0.1-0.2ms | New feature |

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

ACB provides a comprehensive debugging system that helps you troubleshoot your applications effectively. While a brief overview is provided in the \[[#built-in-components|Built-in Components]\] section, this section offers a more detailed look at ACB's debugging capabilities.

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
user_data = {
    "id": 123,
    "name": "John",
    "roles": ["admin", "editor"],
    "settings": {"theme": "dark", "notifications": True},
}
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

## Security Features

ACB provides essential security features focused on secure defaults and SSL/TLS configuration.

### Secret Management

Securely manage sensitive configuration using the secret adapters:

```python
from acb.adapters import import_adapter
from acb.depends import depends

# Use Infisical for secret management
Secret = import_adapter("secret")
secret = depends.get(Secret)

# Store and retrieve secrets securely
await secret.create("database_password", "super_secure_password123!")
password = await secret.get("database_password")

# List available secrets
secret_names = await secret.list()
```

### Input Validation

Use Pydantic models for basic input validation and data sanitization:

```python
from pydantic import BaseModel, EmailStr, Field, validator
from typing import Optional


class UserInput(BaseModel):
    username: str = Field(..., min_length=3, max_length=20, pattern=r"^[a-zA-Z0-9_]+$")
    email: EmailStr
    age: Optional[int] = Field(None, ge=0, le=150)

    @validator("username")
    def validate_username(cls, v):
        if not v.replace("_", "").isalnum():
            raise ValueError(
                "Username must contain only letters, numbers, and underscores"
            )
        return v.lower()


# Validate user input
try:
    user_data = UserInput(username=user_input, email=email_input, age=age_input)
    # Data is automatically validated and sanitized
    safe_username = user_data.username
    safe_email = user_data.email
except ValidationError as e:
    logger.warning(f"Validation failed: {e}")
```

### Basic Security Practices

ACB follows secure defaults and best practices:

```python
# Use environment variables for sensitive data
import os
from pydantic import SecretStr


class DatabaseConfig(BaseModel):
    host: str = "localhost"
    port: int = 5432
    username: str
    password: SecretStr  # Automatically masked in logs

    @classmethod
    def from_env(cls):
        return cls(
            host=os.getenv("DB_HOST", "localhost"),
            port=int(os.getenv("DB_PORT", "5432")),
            username=os.getenv("DB_USERNAME"),
            password=os.getenv("DB_PASSWORD"),
        )


# Use secure random generation
import secrets

api_token = secrets.token_urlsafe(32)
session_id = secrets.token_hex(16)

# Use SSL/TLS connections (see next section)
```

### SSL/TLS Configuration

ACB provides basic SSL/TLS configuration for adapters that support secure connections:

```python
from acb.core.ssl_config import SSLConfigMixin


class SecureAdapter(SSLConfigMixin):
    def __init__(self):
        super().__init__()
        # SSL settings are configured via environment or settings files

    async def connect(self):
        # Use SSL settings for secure connections
        ssl_context = self._create_ssl_context()
        connection = await create_secure_connection(ssl_context=ssl_context)
        return connection


# SSL settings are configured in settings/adapters.yml or environment variables
```

## Basic Monitoring

ACB provides simple monitoring capabilities through logging and error tracking adapters.

### Error Tracking with Sentry

Set up basic error tracking for production monitoring:

```python
from acb.adapters import import_adapter
from acb.depends import depends

# Configure Sentry monitoring
Monitoring = import_adapter("monitoring")
monitoring = depends.get(Monitoring)

# Automatic error tracking is enabled once configured
try:
    # Your application code
    result = await some_operation()
except Exception as e:
    # Errors are automatically captured by Sentry
    logger.error(f"Operation failed: {e}")
    raise
```

### Structured Logging with Logfire

Use Logfire for structured logging and performance insights:

```python
from acb.depends import depends
from acb.logger import Logger

logger = depends.get(Logger)

# Structured logging with context
logger.info(
    "Cache operation started",
    extra={"operation": "cache_get", "key": "user:123", "cache_type": "redis"},
)

# Performance timing
import time

start_time = time.time()
result = await cache.get("user:123")
duration = time.time() - start_time

logger.info(
    "Cache operation completed",
    extra={
        "operation": "cache_get",
        "duration_ms": duration * 1000,
        "hit": result is not None,
    },
)
```

### Simple Resource Cleanup

ACB provides basic resource cleanup patterns:

```python
from acb.core.cleanup import CleanupMixin


class MyAdapter(CleanupMixin):
    def __init__(self):
        super().__init__()
        self._connection = None

    async def _create_connection(self):
        connection = await connect_to_service()
        self.register_resource(connection)  # Automatic cleanup
        return connection

    async def get_data(self):
        if self._connection is None:
            self._connection = await self._create_connection()
        return await self._connection.fetch_data()

    # Cleanup happens automatically when the adapter is destroyed
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

For more detailed information about debugging in ACB, see the \[[acb/README#3-debugging-tools|Core Systems documentation]\].

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
            description=description,
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

- \[\[acb/README|**Core Systems**\]\]: Configuration, dependency injection, debugging, and logging
- \[\[acb/actions/README|**Actions**\]\]: Detailed guide to built-in actions and creating custom ones
- \[\[acb/adapters/README|**Adapters**\]\]: Comprehensive documentation on adapter system and implementations
  - \[\[acb/adapters/cache/README|**Cache Adapter**\]\]: Memory and Redis caching
  - \[\[acb/adapters/sql/README|**SQL Adapter**\]\]: SQL database connections
  - \[\[acb/adapters/storage/README|**Storage Adapter**\]\]: File and object storage

## Acknowledgements

ACB "blocks" logo used by permission from [Andy Coe Band](https://andycoeband.com).

Special thanks to the following open-source projects that power ACB:

### Core Framework & Configuration

- [Pydantic](https://pydantic-docs.helpmanual.io/) - Data validation and settings management
- [pydantic-settings](https://pydantic-settings.helpmanual.io/) - Settings management with multiple sources
- [bevy](https://github.com/bevy-org/bevy) - Dependency injection framework
- [AnyIO](https://anyio.readthedocs.io/) - Async compatibility layer and utilities
- [Typer](https://typer.tiangolo.com/) - Modern CLI framework

### Serialization & Data Processing

- [msgspec](https://jcristharif.com/msgspec/) - High-performance JSON/MessagePack serialization
- [attrs](https://github.com/python-attrs/attrs) - Classes without boilerplate
- [PyYAML](https://pyyaml.org/) - YAML parser and emitter
- [tomlkit](https://github.com/sdispater/tomlkit) - TOML parser and writer

### Async & Networking

- [httpx](https://www.python-httpx.org/) - Modern async HTTP client
- [aiofiles](https://github.com/Tinche/aiofiles) - Async file operations
- [aiocache](https://github.com/aio-libs/aiocache) - Async cache interface

### Database & Storage

- [SQLAlchemy](https://www.sqlalchemy.org/) - SQL toolkit and ORM
- [SQLModel](https://sqlmodel.tiangolo.com/) - Modern SQL databases with Python
- [Redis](https://redis.io/) - In-memory data store
- [pymongo](https://pymongo.readthedocs.io/) - MongoDB driver

### Monitoring & Debugging

- [Loguru](https://loguru.readthedocs.io/) - Enhanced logging with async support
- [Logfire](https://docs.logfire.dev/) - Structured logging and monitoring
- [Sentry](https://docs.sentry.io/) - Error tracking and performance monitoring
- [icecream](https://github.com/gruns/icecream) - Enhanced debugging utilities

### Cloud & Infrastructure

- [boto3](https://boto3.amazonaws.com/v1/documentation/api/latest/index.html) - AWS SDK
- [google-cloud-storage](https://cloud.google.com/storage/docs/reference/libraries) - Google Cloud Storage
- [azure-storage-blob](https://docs.microsoft.com/en-us/python/api/azure-storage-blob/) - Azure Blob Storage

### Compression & Hashing

- [brotli](https://github.com/google/brotli) - Brotli compression
- [blake3](https://github.com/BLAKE3-team/BLAKE3) - Cryptographic hash function
- [crc32c](https://github.com/ICRAR/crc32c) - CRC32C checksum

### Development Environment

- [PyCharm](https://www.jetbrains.com/pycharm/) - The premier Python IDE that powered the development of ACB
- [Claude Code](https://claude.ai/code) - AI-powered development assistant that accelerated development and ensured code quality

We extend our gratitude to all the maintainers and contributors of these outstanding projects that make ACB's powerful component architecture possible.

## License

This project is licensed under the terms of the BSD 3-Clause license.

## Projects Using ACB

Here are some notable projects built with ACB:

- [**FastBlocks**](https://github.com/lesleslie/fastblocks): A web application framework that directly extends Starlette while leveraging ACB's component architecture to create a powerful platform for server-side rendered HTMX applications. FastBlocks combines Starlette's ASGI capabilities with ACB's infrastructure, adding web-specific adapters for templates, routing, authentication, and admin interfaces.

## Contributing

Contributions to ACB are welcome! We follow a workflow inspired by the Crackerjack development guidelines. To ensure consistency and high quality, please adhere to the following steps when contributing:

1. **Fork and Clone**
   Fork the repository and clone it locally.

1. **Set Up Your Development Environment**
   Use [UV](https://docs.astral.sh/uv/) for dependency and virtual environment management. ACB requires Python 3.13 or later. Add ACB as a development dependency:

   ```
   uv add --dev acb
   ```

1. **Code Style and Type Checking**
   ACB uses modern Python typing features and follows strict type checking. We use:

   - Type annotations with the latest Python 3.13 syntax
   - Protocols instead of ABC for interface definitions
   - Union types with the `|` operator instead of `Union[]`
   - Type checking with pyright in strict mode
   - Ruff for linting and formatting

1. **Run Pre-commit Hooks & Tests**
   Before submitting a pull request, ensure your changes pass all quality checks and tests. We recommend running the following command (which is inspired by Crackerjack's automated workflow):

   ```
   python -m crackerjack -x -t -p <version> -c
   ```

   *Alternatively, you can use:*

   ```
   python -m crackerjack -a <version>
   ```

   This command cleans your code, runs linting, tests, bumps the version (patch, minor, or major), and commits changes.

1. **Testing**
   All tests are written using pytest and should include coverage reporting:

   ```
   pytest --cov=acb
   ```

   Test configuration is in pyproject.toml, not in separate .coveragerc or pytest.ini files.

1. **Submit a Pull Request**
   If everything passes, submit a pull request describing your changes. Include details about your contribution and reference any related issues.

1. **Feedback and Review**
   Our maintainers will review your changes. Please be responsive to feedback and be prepared to update your pull request as needed.

For more detailed development guidelines and the Crackerjack philosophy that influences our workflow, please refer to our internal development documentation.

Happy contributing!

# Test change
