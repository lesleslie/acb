<p align="center">
<img src="./images/acb-logo.png" alt="ACB Logo">
</p>

> **ACB Documentation**: [Main](./README.md) | [Core Systems](./acb/README.md) | [Actions](./acb/actions/README.md) | [Adapters](./acb/adapters/README.md)

# <u>A</u>synchronous <u>C</u>omponent <u>B</u>ase (ACB)

[![Code style: crackerjack](https://img.shields.io/badge/code%20style-crackerjack-000042)](https://github.com/lesleslie/crackerjack)
[![Python: 3.13+](https://img.shields.io/badge/python-3.13%2B-green)](https://www.python.org/downloads/)

## What is ACB?

ACB is a comprehensive asynchronous application platform for building production-ready Python applications with enterprise-grade capabilities. It provides a **complete architectural stack** from low-level utilities to high-level orchestration:

- **Foundation Layer**: Self-contained **actions** (utilities) and flexible **adapters** (integrations)
- **Services Layer**: Long-running components with lifecycle management, health monitoring, and metrics
- **Orchestration Layer**: Event-driven messaging (**Events**), background job processing (**Tasks**), and complex workflow management (**Workflows**)
- **Infrastructure Layer**: Dynamic configuration, dependency injection, and resource management

In simpler terms, ACB evolved from a component framework into a **full application platform** that handles everything from data compression to complex multi-step business processes, all with a consistent, type-safe, async-first API.

ACB can be used as a standalone platform or as a foundation for higher-level frameworks. For example, [FastBlocks](https://github.com/lesleslie/fastblocks) builds on ACB to create a web application framework specifically designed for server-side rendered HTMX applications.

## Key Concepts

If you're new to ACB, here are the key concepts to understand:

1. **Actions**: Self-contained utility functions that perform specific tasks like compression, encoding, or hashing. Think of these as your toolbox of helper functions.

1. **Adapters**: Standardized interfaces to external systems like databases, caching, or storage. Adapters let you switch between different implementations (e.g., Redis vs. in-memory cache) without changing your code.

1. **Dependency Injection**: A pattern that automatically provides components to your functions when needed. This eliminates the need to manually create and pass objects around.

1. **Configuration System**: A way to configure your application using YAML files instead of hardcoding values in your code.

1. **Package Registration**: ACB automatically discovers and registers components in your application, reducing boilerplate code.

## Key Features

### Foundation & Infrastructure

- **Modular Architecture**: Mix and match components across all architectural layers
- **Asynchronous First**: Built for high-performance async operations throughout the stack
- **Pluggable Adapters**: Swap implementations without changing your code (20+ adapter categories)
- **Dynamic Discovery**: Convention-based adapter detection and configuration-driven selection
- **Configuration-Driven**: Change behavior through YAML configuration with hot-reloading support
- **Type Safety**: Built on Pydantic with Protocol-based dependency injection for robust typing
- **Performance Optimized**: Streamlined initialization and reduced overhead (0.18.0+)

### Services Layer (v0.20.0+)

- **Enterprise Services**: Production-ready services with lifecycle management and health monitoring
- **Repository Pattern**: Multi-database coordination with Unit of Work pattern and caching integration
- **Validation Services**: Schema validation, input sanitization, and security-focused data processing
- **Performance Services**: Metrics collection, cache optimization, and query performance analysis

### Orchestration Layer (v0.20.0+)

- **Event-Driven Architecture**: Pub-sub messaging with multiple delivery modes and error handling
- **Background Task Processing**: Reliable job queue with priority support, scheduling, and retry mechanisms
- **Workflow Management**: Complex multi-step process orchestration with state persistence
- **Multiple Backends**: Memory, Redis, RabbitMQ, and APScheduler support for flexible deployment

### Integration & AI (v0.23.0+)

- **AI/ML Adapters**: Seamless integration with LLMs, embedding models, and ML serving platforms
- **Real-time Monitoring**: WebSocket-based dashboards and progress tracking

## Table of Contents

- [Key Concepts](#key-concepts)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [Architecture Overview](#architecture-overview)
- [Core Components](#core-components)
  - [Actions](#actions)
  - [Adapters](#adapters)
  - [Universal Query Interface](#universal-query-interface)
  - [Services](#services)
  - [Events & Orchestration](#events--orchestration)
  - [Configuration System](#configuration-system)
  - [Dependency Injection](#dependency-injection)
- [Common Patterns](#common-patterns)
- [Use Cases](#use-cases)
- [Built-in Components](#built-in-components)
- [Security Features](#security-features)
- [Basic Monitoring](#basic-monitoring)
- [Debugging](#debugging)
- [Advanced Usage](#advanced-usage)
- [Documentation](#documentation)
- [Acknowledgements](#acknowledgements)
- [License](#license)
- [Projects Using ACB](#projects-using-acb)
- [Contributing](#contributing)

## Installation

Install ACB using [uv](https://docs.astral.sh/uv/):

```bash
uv add acb
```

> **Note**: ACB requires Python 3.13 or later.

### Optional Dependencies

ACB supports various optional dependencies for different adapters and functionality:

| Feature Group | Components | Installation Command |
| ----------------- | ---------------------------------------------------------------------------------- | ----------------------------------------------------------------- |
| Cache | Memory and Redis caching | `uv add acb --group cache` |
| DNS | DNS management (Cloud DNS, Cloudflare, Route53) | `uv add acb --group dns` |
| FTPD | File transfer (FTP, SFTP) | `uv add acb --group ftpd` |
| Monitoring | Error tracking (Sentry, Logfire) | `uv add acb --group monitoring` |
| Requests | HTTP clients (HTTPX, Niquests) | `uv add acb --group requests` |
| Secret | Secret management (Infisical, GCP, Azure, Cloudflare) | `uv add acb --group secret` |
| SMTP | Email sending (Mailgun) | `uv add acb --group smtp` |
| SQL | Database (MySQL, PostgreSQL, SQLite) | `uv add acb --group sql` |
| Storage | File storage (S3, GCS, Azure, local) | `uv add acb --group storage` |
| NoSQL | Document databases (MongoDB, Firestore, Redis-OM) | `uv add acb --group nosql` |
| Vector | Vector databases (DuckDB, Pinecone, Qdrant, Weaviate) | `uv add acb --group vector` |
| Graph | Graph databases (Neo4j, ArangoDB) | `uv add acb --group graph` |
| AI | AI/ML integrations (Anthropic, OpenAI, Gemini, Ollama) | `uv add acb --group ai` |
| Embedding | Embedding models (OpenAI, Sentence Transformers) | `uv add acb --group embedding` |
| Reasoning | Reasoning frameworks (LangChain, LlamaIndex) | `uv add acb --group reasoning` |
| Models | Model frameworks (SQLModel, Pydantic, Redis-OM, msgspec, attrs) | `uv add acb --group models` |
| Logger | Advanced logging (Logly, Structlog) | `uv add acb --group logger` |
| Demo | Demo/example utilities (Faker) | `uv add acb --group demo` |
| Development | Development tools (pytest, ruff, pre-commit) | `uv add acb --group dev` |
| **Composite Groups** | | |
| Minimal | Cache + Requests (essential web stack) | `uv add acb --group minimal` |
| API | Cache + NoSQL + Requests + Monitoring | `uv add acb --group api` |
| Microservice | Cache + Requests + Monitoring + Secret | `uv add acb --group microservice` |
| Web Application | Cache + SQL + Storage + Requests + Monitoring | `uv add acb --group webapp` |
| Web App Plus | Web app + Vector databases | `uv add acb --group webapp-plus` |
| Cloud Native | Web app + DNS + Secret + Monitoring | `uv add acb --group cloud-native` |
| Data Platform | SQL + NoSQL + Storage + Monitoring | `uv add acb --group dataplatform` |
| GCP Stack | GCP-specific adapters (DNS, Secret, NoSQL, Storage) | `uv add acb --group gcp` |
| All Features | All optional dependencies | `uv add acb --group all` |
| **Multiple Groups** | Combine any groups | `uv add acb --group cache --group sql --group storage` |

## Architecture Overview

ACB follows a **layered architecture** with automatic discovery and registration of components. The platform is organized into distinct layers, each building on the previous one to provide increasingly sophisticated capabilities:

```text
┌─────────────────────────────────────────────────────────────┐
│                    APPLICATION LAYER                        │
│              (Your Code Using ACB Platform)                 │
└─────────────────────────────────────────────────────────────┘
                            ▼
┌─────────────────────────────────────────────────────────────┐
│              INTEGRATION LAYER (v0.23.0+)                   │
│  ┌──────────────────┐           ┌──────────────────┐       │
│  │    AI/ML         │           │   Monitoring     │       │
│  │   Adapters       │           │   Dashboards     │       │
│  └──────────────────┘           └──────────────────┘       │
└─────────────────────────────────────────────────────────────┘
                            ▼
┌─────────────────────────────────────────────────────────────┐
│            ORCHESTRATION LAYER (v0.20.0+)                   │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐    │
│  │   Events     │  │    Tasks     │  │  Workflows   │    │
│  │  (Pub/Sub)   │  │  (Job Queue) │  │  (Process)   │    │
│  └──────────────┘  └──────────────┘  └──────────────┘    │
└─────────────────────────────────────────────────────────────┘
                            ▼
┌─────────────────────────────────────────────────────────────┐
│              SERVICES LAYER (v0.20.0+)                      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐    │
│  │  Repository  │  │  Validation  │  │ Performance  │    │
│  │   (Data)     │  │   (Schema)   │  │  (Metrics)   │    │
│  └──────────────┘  └──────────────┘  └──────────────┘    │
└─────────────────────────────────────────────────────────────┘
                            ▼
┌─────────────────────────────────────────────────────────────┐
│              FOUNDATION LAYER (Core)                        │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐    │
│  │   Actions    │  │   Adapters   │  │   Models     │    │
│  │  (Utilities) │  │ (20+ Types)  │  │ (Universal)  │    │
│  └──────────────┘  └──────────────┘  └──────────────┘    │
└─────────────────────────────────────────────────────────────┘
                            ▼
┌─────────────────────────────────────────────────────────────┐
│            INFRASTRUCTURE LAYER (Core)                      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐    │
│  │    Config    │  │  Dependency  │  │   Resource   │    │
│  │   (YAML)     │  │  Injection   │  │   Cleanup    │    │
│  └──────────────┘  └──────────────┘  └──────────────┘    │
└─────────────────────────────────────────────────────────────┘
```

### Directory Structure

```text
acb/
├── actions/             # Foundation: Utility functions (compress, encode, hash)
├── adapters/            # Foundation: Integration modules (20+ categories)
│   ├── cache/           # Memory, Redis caching
│   ├── sql/             # MySQL, PostgreSQL, SQLite
│   ├── nosql/           # MongoDB, Firestore, Redis
│   ├── storage/         # S3, GCS, Azure, local file
│   ├── messaging/       # Memory, Redis, RabbitMQ pub-sub
│   ├── queue/           # Memory, Redis, APScheduler task queues
│   ├── ai/              # Anthropic, OpenAI, Gemini, Ollama
│   ├── models/          # Universal query interface
│   └── ...              # 12+ additional categories
├── services/            # Services Layer: Enterprise components
│   ├── repository/      # Data access with Unit of Work pattern
│   ├── validation/      # Schema validation and sanitization
│   ├── performance/     # Metrics and optimization
│   └── _base.py         # ServiceBase for lifecycle management
├── events/              # Orchestration: Event-driven messaging
├── tasks/               # Orchestration: Background job processing
├── workflows/           # Orchestration: Multi-step process management
├── config.py            # Infrastructure: Configuration system
├── depends.py           # Infrastructure: Dependency injection
├── cleanup.py           # Infrastructure: Resource management
└── logger.py            # Infrastructure: Structured logging
```

## Core Components

ACB is structured around these fundamental building blocks:

### Actions

Actions are modular, self-contained utility functions that perform specific tasks. Unlike services, adapters, events, or tasks, actions are not a runtime architectural layer but rather a utility collection of stateless functions available throughout your application.

#### What Are Actions?

Think of actions as a toolbox of utility functions that you can use anywhere in your application. Unlike the architectural layers (Services, Orchestration, Adapters), actions provide simple utility operations without lifecycle management or external system integration.

Key characteristics of actions:

- **Stateless**: Each action is a pure function with no internal state
- **No Lifecycle**: No initialization, configuration, or shutdown required
- **Categorized by Function**: Organized by verb-based categories (compress, encode, hash, etc.)
- **Consistent API**: Similar operations have similar interfaces
- **Cross-Cutting Utility**: Available for use across all architectural layers

#### Available Actions

| Action Category | Description | Implementations |
| ----------------------- | -------------------------- | ------------------------- |
| **Compress/Decompress** | Efficient data compression | gzip, brotli |
| **Encode/Decode** | Data serialization | JSON, YAML, TOML, MsgPack |
| **Hash** | Secure hashing functions | blake3, crc32c, md5 |

**Quick sample**

```python
from acb.actions.compress import compress, decompress
from acb.actions.encode import encode, decode
from acb.actions.hash import hash


async def pipeline(payload: dict[str, str]) -> tuple[str, dict[str, str]]:
    encoded = await encode.json(payload)
    compressed = compress.brotli(encoded, level=3)
    digest = await hash.blake3(compressed)
    restored = await decode.json(decompress.brotli(compressed))
    return digest, restored
```

For the full catalog, see the [Actions README](./acb/actions/README.md).

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
| **SQL** | Relational databases | MySQL, PostgreSQL, SQLite |
| **NoSQL** | Document & key-value stores | MongoDB, Firestore, Redis |
| **Storage** | File storage | File, Memory, S3, Cloud Storage, Azure |
| **Secret** | Secret management | Infisical, Secret Manager |

**Example: Import once, reuse everywhere**

```python
from acb.adapters import import_adapter
from acb.depends import depends, Inject

Cache = import_adapter("cache")
Storage = import_adapter("storage")


@depends.inject
async def cache_example(
    cache: Inject[Cache],
    storage: Inject[Storage],
) -> None:
    await cache.set("user:123", {"name": "Jill"}, ttl=60)
    user = await cache.get("user:123") or await storage.get("user:123")
    if user:
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

For comprehensive documentation and examples, see the [Models Adapter Documentation](./acb/adapters/models/README.md).

### Services

ACB's Services layer provides a standardized framework for building long-running, stateful components with lifecycle management, health checking, metrics collection, and resource cleanup capabilities. Services extend the ServiceBase class to get consistent patterns for initialization, shutdown, and health monitoring.

#### Key Features

- **Lifecycle Management**: Standardized patterns for service initialization, operation, and graceful shutdown
- **Health Monitoring**: Built-in health checking with customizable health check logic
- **Metrics Collection**: Standardized metrics collection for performance and operational visibility
- **Dependency Injection Integration**: Seamless integration with ACB's dependency injection system
- **Configuration Management**: Standardized settings and configuration patterns
- **Resource Cleanup**: Automatic resource management and cleanup patterns

#### Service Architecture Patterns

ACB uses two main patterns for structuring services:

1. **Simple Services**: Services that directly inherit from ServiceBase for focused functionality
1. **Complex Services**: Services with complex domain logic that use a `_base.py` file pattern to define protocols and abstract interfaces

**Services with Complex Domain Logic** (like repository, validation):

- Use the `_base.py` pattern to define protocols, interfaces, and abstract base classes
- This allows for multiple implementations and clear contracts
- Separate abstract contracts from concrete implementations

**Services with Focused Functionality** (like performance optimizers):

- Direct inheritance from ServiceBase is appropriate
- Less need for complex inheritance hierarchies if functionality is straightforward
- Still follow ServiceBase for consistent lifecycle management

#### Example: Creating a Simple Service

```python
from acb.services._base import ServiceBase, ServiceConfig, ServiceSettings
from acb.depends import depends


class MyCustomService(ServiceBase):
    """A custom service example."""

    def __init__(self):
        service_config = ServiceConfig(
            service_id="my_custom_service",
            name="My Custom Service",
            description="An example custom service",
            priority=50,  # Initialization priority
        )
        settings = ServiceSettings()
        super().__init__(service_config, settings)

    async def _initialize(self) -> None:
        """Service-specific initialization logic."""
        self.logger.info("Initializing my custom service")
        # Add initialization code here

    async def _shutdown(self) -> None:
        """Service-specific shutdown logic."""
        self.logger.info("Shutting down my custom service")
        # Add cleanup code here

    async def _health_check(self) -> dict:
        """Service-specific health check logic."""
        return {"status": "ok", "custom_metric": "value"}


# Usage with dependency injection
@depends.inject
async def use_my_service(my_service: MyCustomService = depends()):
    # Use the service instance
    await my_service.initialize()
    # ... do work ...
    await my_service.shutdown()
```

#### Available Services

| Service Category | Description | Key Features |
|------------------|-------------|--------------|
| **Repository** | Data access layer with Unit of Work pattern | Multi-database coordination, caching integration, transaction management |
| **Validation** | Data validation with security features | Schema validation, input sanitization, performance monitoring |
| **Performance** | Optimization services | Metrics collection, cache optimization, query optimization |

### Events & Orchestration

ACB's Events, Tasks, and Workflows systems provide comprehensive orchestration capabilities for building complex, event-driven applications with reliable background processing and process management.

#### Events System

The Events system provides pub-sub messaging capabilities with support for event-driven communication between components.

**Key Features:**

- **Event-Driven Architecture**: Support for pub-sub patterns with multiple subscription options
- **Event Types**: Support for different delivery modes (fire-and-forget, at-least-once, exactly-once)
- **Event Handling**: Support for both functional and class-based event handlers
- **Error Handling**: Built-in retry mechanisms and error management
- **Performance**: Optimized for high-throughput event processing

**Example: Using the Events System**

```python
from acb.events import create_event, EventPublisher, event_handler, EventHandlerResult

# Create and publish events
event = create_event("user.created", "user_service", {"user_id": 123})

async with EventPublisher() as publisher:
    await publisher.publish(event)


# Define event handlers
@event_handler("user.created")
async def handle_user_created(event):
    user_id = event.payload["user_id"]
    print(f"Processing user creation for {user_id}")
    return EventHandlerResult(success=True)
```

#### Tasks System

The Tasks system provides reliable background job processing with multiple backend support and advanced scheduling capabilities.

**Key Features:**

- **Multiple Backends**: Support for memory, Redis, and message queue backends
- **Priority Processing**: Support for prioritized task execution
- **Scheduling**: Support for delayed execution and cron-style scheduling
- **Retry Mechanisms**: Configurable retry with exponential backoff
- **Monitoring**: Built-in metrics and monitoring capabilities

**Example: Using the Tasks System**

```python
from acb.tasks import create_task_queue, TaskData, task_handler

# Create a task queue
async with create_task_queue("memory") as queue:
    # Define a task handler
    @task_handler("email_task")
    async def send_email_task(task_data):
        email = task_data.payload["email"]
        # Send email logic here
        return {"sent": True, "email": email}

    # Register handler
    queue.register_handler("email_task", send_email_task)

    # Create and enqueue a task
    task = TaskData(
        task_type="email_task",
        payload={"email": "user@example.com"},
    )
    task_id = await queue.enqueue(task)
```

#### Workflows System

The Workflows system provides orchestration capabilities for managing complex multi-step processes with state management and error handling.

**Key Features:**

- **State Management**: Persistent state tracking for long-running processes
- **Process Orchestration**: Management of complex multi-step operations
- **Error Handling**: Comprehensive error handling and compensation mechanisms
- **Monitoring**: Built-in workflow monitoring and tracking

**Example: Using the Workflows System**

```python
from acb.workflows import WorkflowService

workflow_service = WorkflowService()


# Define and execute workflows with state management
async def execute_complex_process():
    # Workflow execution with state persistence and error handling
    result = await workflow_service.execute_workflow(
        "complex_business_process",
        {"input_data": "value"},
        timeout=3600,  # 1 hour timeout
    )
    return result
```

### Configuration System

ACB's configuration system is built on Pydantic and supports multiple configuration sources:

- **YAML Files**: Environment-specific settings in YAML format
- **Secret Files**: Secure storage of sensitive information
- **Secret Managers**: Integration with external secret management services

#### Where settings live

| File | Purpose |
| --- | --- |
| `settings/app.yaml` | Application-wide metadata (name, domain, platform, feature toggles) |
| `settings/debug.yaml` | Controls debug/trace switches per adapter category |
| `settings/adapters.yaml` | Chooses which implementation backs each adapter category (cache, queue, sql, …) |
| `settings/<adapter>.yaml` | Per-adapter configuration keyed by adapter category (e.g., `settings/cache.yaml`, `settings/storage.yaml`) |
| `settings/secrets/` | File-based secrets that override any of the above |

ACB always reads `app.yaml`/`debug.yaml` for global settings. Adapter-specific
settings come from two places:

1. **`settings/adapters.yaml`** – select the implementation for each adapter
   category.
1. **`settings/<category>.yaml`** – supply configuration for the selected
   implementation.

Example:

```yaml
# settings/adapters.yaml
cache: redis
storage: s3
queue: apscheduler
```

```yaml
# settings/cache.yaml
cache:
  host: "redis.internal"
  port: 6379
  default_ttl: 900

# settings/queue.yaml
queue:
  job_store_type: postgres
  job_store_url: postgresql+asyncpg://scheduler:pass@db/scheduler
```

If you skip `settings/<category>.yaml`, the adapter falls back to its defaults.
Secrets that power those configs (Redis passwords, API keys, etc.) belong in
`settings/secrets/<name>.yaml` or the configured secret manager so they never
appear in Git.

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

ACB features a simple yet powerful dependency injection system that makes component wiring automatic and testable. Starting in v0.20.0+, ACB uses a **hybrid dependency injection architecture** that matches the pattern to the architectural layer.

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

#### Protocol-Based vs Concrete Class Dependency Injection (v0.20.0+)

ACB uses different dependency injection patterns for different architectural layers:

| Component Type | DI Pattern | Interface Type | Injection Syntax | Best For |
|---------------|-----------|----------------|------------------|----------|
| **Services** | Protocol-based | `ServiceProtocol` | `Inject[RepositoryServiceProtocol]` | Business logic, complex workflows, easy testing |
| **Adapters** | Concrete class | Base class | `Inject[Cache]` | Infrastructure, external systems, shared utilities |
| **Core** | Concrete class | Direct class | `Inject[Config]` | Configuration, logging, foundational components |

**Why Different Patterns?**

- **Services**: Use Protocol-based DI for clean interfaces and easy mocking in tests
- **Adapters**: Use concrete class DI to leverage shared infrastructure (connection pooling, retry logic, cleanup)
- **Core**: Use concrete class DI for stable, foundational components

#### Pattern 1: Protocol-Based DI (Services)

**When to use**: Business logic, complex workflows, testable components

```python
from acb.depends import depends, Inject
from acb.services.protocols import (
    RepositoryServiceProtocol,
    ValidationServiceProtocol,
)


@depends.inject
async def process_order(
    order_id: str,
    repo: Inject[RepositoryServiceProtocol],  # Protocol, not concrete class
    validator: Inject[ValidationServiceProtocol],
):
    """Process an order with validation and persistence.

    Note: Dependencies are Protocol interfaces, making this easy to test
    with mock implementations.
    """
    async with repo.unit_of_work() as uow:
        order = await repo.get(order_id)
        if not order:
            raise ValueError(f"Order {order_id} not found")

        validation = await validator.validate_business_rules(order)
        if not validation.is_valid:
            raise ValueError(f"Invalid order: {validation.errors}")

        order.status = "processed"
        await repo.save(order, uow)
```

**Testing with Protocol-based DI:**

```python
import pytest
from acb.depends import depends
from acb.services.protocols import RepositoryServiceProtocol


# Mock implementation matches Protocol interface
class MockRepository:
    def __init__(self):
        self.entities = {}

    @asynccontextmanager
    async def unit_of_work(self):
        yield UnitOfWork(transaction=None)

    async def get(self, entity_id):
        return self.entities.get(entity_id)

    async def save(self, entity, uow=None):
        self.entities[entity.id] = entity


@pytest.mark.asyncio
async def test_process_order():
    # Register mock for Protocol
    mock_repo = MockRepository()
    depends.set(RepositoryServiceProtocol, mock_repo)

    # Test uses Protocol interface, not concrete implementation
    await process_order("order-123")

    assert "order-123" in mock_repo.entities
```

#### Pattern 2: Concrete Class DI (Adapters)

**When to use**: Infrastructure, external systems, shared utilities

```python
from acb.depends import depends, Inject
from acb.adapters import import_adapter

# Import concrete adapter classes
Cache = import_adapter("cache")
Storage = import_adapter("storage")


@depends.inject
async def cache_uploaded_file(
    file_path: str,
    cache: Inject[Cache],  # Concrete class, not Protocol
    storage: Inject[Storage],
):
    """Cache file metadata from storage.

    Note: Dependencies are concrete classes because we need access to
    shared infrastructure like connection pooling and retry logic.
    """
    metadata = await storage.get_metadata(file_path)
    await cache.set(f"metadata:{file_path}", metadata, ttl=3600)
```

**Why concrete classes for adapters?**

Adapters benefit from shared base class infrastructure:

- Connection pooling via `_ensure_client()`
- Retry logic via `_retry_operation()`
- Resource cleanup via `CleanupMixin`
- Configuration loading from `settings/adapters.yml`
- Standard lifecycle methods (`connect()`, `disconnect()`, `health_check()`)

#### Pattern 3: Mixed DI (Services + Adapters)

**Real-world example**: Services calling adapters

```python
from acb.depends import depends, Inject
from acb.services.protocols import RepositoryServiceProtocol
from acb.adapters import import_adapter

Cache = import_adapter("cache")


@depends.inject
async def get_user_with_cache(
    user_id: str,
    repo: Inject[RepositoryServiceProtocol],  # Service Protocol
    cache: Inject[Cache],  # Adapter concrete class
):
    """Get user from repository with caching.

    This pattern combines Protocol-based DI for business logic (repository)
    with concrete class DI for infrastructure (cache).
    """
    # Try cache first
    cache_key = f"user:{user_id}"
    cached_user = await cache.get(cache_key)
    if cached_user:
        return cached_user

    # Fetch from repository
    user = await repo.get(user_id)
    if user:
        await cache.set(cache_key, user, ttl=300)

    return user
```

#### Registering Custom Components

**Services** (Protocol-based):

```python
from acb.depends import depends
from acb.services.protocols import RepositoryServiceProtocol
from acb.services.repository.sql_repository import SqlRepositoryService

# Register concrete implementation for Protocol
depends.set(RepositoryServiceProtocol, SqlRepositoryService())
```

**Adapters** (Concrete class):

```python
from acb.depends import depends
from acb.adapters import import_adapter

# Adapters auto-register based on settings/adapters.yml
Cache = import_adapter("cache")

# Manual registration (if needed)
cache_instance = Cache()
depends.set(Cache, cache_instance)
```

#### Quick Reference: When to Use Which Pattern

**Use Protocol-based DI when:**

- ✅ Writing business logic in Services layer
- ✅ Need multiple implementations of same interface
- ✅ Want easy mocking in unit tests
- ✅ Prefer composition over inheritance
- ✅ Building new features in v0.20.0+

**Use Concrete class DI when:**

- ✅ Working with Adapters (infrastructure)
- ✅ Need shared base class utilities
- ✅ Using configuration-driven implementation selection
- ✅ Leveraging ACB's connection pooling and retry logic
- ✅ Working with Core components (Config, Logger)

#### Benefits of Dependency Injection

1. **Reduced Boilerplate**: No need to manually create and pass objects
1. **Testability**: Easy to mock dependencies for testing (especially with Protocols)
1. **Flexibility**: Change implementations without changing your code
1. **Decoupling**: Components don't need to know how to create their dependencies
1. **Type Safety**: Full IDE support with type hints and autocomplete
1. **Clear Architecture**: DI pattern signals architectural layer (Service vs Adapter)

For detailed architectural guidance, see [docs/ARCHITECTURE-DECISION-PROTOCOL-DI.md](./docs/ARCHITECTURE-DECISION-PROTOCOL-DI.md).

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

## Common Patterns

Here are some common patterns and examples that will help you get started with ACB:

### 1. Using Dependency Injection

Dependency injection is a core concept in ACB. Here's how to use it effectively:

```python
from acb.depends import depends, Inject
from acb.config import Config
from acb.adapters import import_adapter

# Import adapter classes
Cache, Storage = import_adapter()  # This gets the configured cache and storage adapters


# Method 1: Using depends.get() directly
def direct_injection_example():
    # Get instances when you need them
    config = depends.get(Config)
    cache = depends.get(Cache)

    # Use the components
    print(f"App name: {config.app.name}")


# Method 2: Using the @depends.inject decorator (recommended)
@depends.inject
async def process_file(
    filename: str,
    cache: Inject[Cache],  # Type-safe injection from acb.depends
    storage: Inject[Storage],  # Type-safe injection from acb.depends
    config: Inject[Config],  # Type-safe injection from acb.depends
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
from acb.depends import depends, Inject
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
    data_id: str, storage: Inject[Storage], cache: Inject[Cache], sql: Inject[SQL]
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
from acb.depends import depends, Inject
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
async def initialize_services(config: Inject[Config]):
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
from acb.depends import depends, Inject
from acb.adapters import import_adapter
from acb.actions.encode import encode, decode
import typing as t
import time
import asyncio

Cache = import_adapter("cache")


@depends.inject
async def get_user_data(user_id: int, cache: Inject[Cache]):
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

- [**Architecture Implementation Guide**](./docs/ARCHITECTURE_IMPLEMENTATION_GUIDE.md): Complete guide to ACB's architectural layers and implementation patterns
- [**Core Systems**](./acb/README.md): Configuration, dependency injection, debugging, and logging
- [**Actions**](./acb/actions/README.md): Detailed guide to built-in actions and creating custom ones
- [**Adapters**](./acb/adapters/README.md): Comprehensive documentation on adapter system and implementations
  - [**Cache Adapter**](./acb/adapters/cache/README.md): Memory and Redis caching
  - [**SQL Adapter**](./acb/adapters/sql/README.md): SQL database connections
  - [**Storage Adapter**](./acb/adapters/storage/README.md): File and object storage

## Acknowledgements

ACB "blocks" logo used by permission from [Andy Coe Band](https://www.facebook.com/AndyCoeBand).

Special thanks to the following open-source projects that power ACB:

### Core Framework & Configuration

- [Pydantic](https://pydantic-docs.helpmanual.io/) - Data validation and settings management
- [pydantic-settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/) - Settings management with multiple sources
- [bevy](https://github.com/bevyengine/bevy) - Dependency injection framework
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
- [Claude Code](https://claude.com/product/overview) - AI-powered development assistant that accelerated development and ensured code quality

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

   > ℹ️ **pip-audit networking**: Some vulnerability APIs advertise HTTP/3 and then fail with `MustDowngradeError`. The repo ships `sitecustomize.py` to disable HTTP/3 system-wide so `pip-audit` (and other urllib3 clients) stick to HTTP/1.1/2. Set `ACB_HTTP3_DISABLE=0` if you explicitly need HTTP/3 while running locally.

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
