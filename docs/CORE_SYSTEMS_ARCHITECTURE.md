---
id: 01K6GSRD6X5ERPDASQ67Q771JG
---
______________________________________________________________________

## id: 01K6GSM7Z7YYB366VGREMX0T89

______________________________________________________________________

## id: 01K6GPA5FFKY3Z8FAQRRX0MJ6N

______________________________________________________________________

## id: 01K6GMDS0SQSG7823WH3A8DAXC

______________________________________________________________________

## id: 01K6GKSWXRZ8W2TJ88NFYR3PQK

______________________________________________________________________

## id: 01K6GKJMQSQVEGFK8PW4TMY1FF

______________________________________________________________________

## id: 01K6GJYGVQY0Y3JPZ9N561YV3Y

______________________________________________________________________

## id: 01K6GGMBKYKKC57XMVGK0MPGQ9

______________________________________________________________________

## id: 01K6G688V8D3JV8MBDRBR716E4

______________________________________________________________________

## id: 01K6G5HSEWS71XJ7Z81WH28FXY

______________________________________________________________________

## id: 01K6G58HBZ8MZY82CP4J9PFPVS

______________________________________________________________________

## id: 01K6G4MGXK2GM2HPCW628VYKDZ

______________________________________________________________________

## id: 01K6G3RBD9975GGHDTKW9QHG67

______________________________________________________________________

## id: 01K6G3986J89HVHX5BKNQ2MFZV

______________________________________________________________________

## id: 01K6FZP6Y7C0Z1PDRK3EK3K4CG

______________________________________________________________________

## id: 01K6FXPDZKN9F0YRM51EFQETD6

# ACB Core Systems Architecture

This document provides a comprehensive overview of ACB's core systems and how they work together to provide a powerful, modular framework for building Python applications.

## Table of Contents

1. \[[#overview|Overview]\]
1. \[[#core-systems|Core Systems]\]
1. \[[#services-layer|Services Layer]\]
1. \[[#event-system|Event System]\]
1. \[[#task-queue-system|Task Queue System]\]
1. \[[#workflow-engine|Workflow Engine]\]
1. \[[#testing-infrastructure|Testing Infrastructure]\]
1. \[[#migration-system|Migration System]\]
1. \[[#integration-patterns|Integration Patterns]\]
1. \[[#usage-in-real-projects|Usage in Real Projects]\]

______________________________________________________________________

## Overview

ACB (Asynchronous Component Base) is built on a layered architecture where each system serves a specific purpose while integrating seamlessly with other components. The framework prioritizes:

- **Modularity**: Each system is independent but can be combined for complex workflows
- **Async-First**: All operations are designed for high-performance asynchronous execution
- **Dependency Injection**: Components are automatically wired together using the `depends` framework
- **Configuration-Driven**: Behavior is controlled through YAML configuration files

### Architecture Layers

```
┌─────────────────────────────────────────────────────────┐
│                    Application Layer                     │
│              (FastBlocks, Crackerjack, etc.)            │
└─────────────────────────────────────────────────────────┘
                            │
┌─────────────────────────────────────────────────────────┐
│                    Services Layer                        │
│         (Business Logic, Validation, Repository)        │
└─────────────────────────────────────────────────────────┘
                            │
┌─────────────────────────────────────────────────────────┐
│              Event & Workflow Orchestration             │
│           (Events, Queues, Workflows, MCP)              │
└─────────────────────────────────────────────────────────┘
                            │
┌─────────────────────────────────────────────────────────┐
│                    Adapter Layer                         │
│      (Cache, SQL, NoSQL, Storage, Monitoring, etc.)     │
└─────────────────────────────────────────────────────────┘
                            │
┌─────────────────────────────────────────────────────────┐
│                   Core Infrastructure                    │
│           (Config, DI, Logger, SSL, Cleanup)            │
└─────────────────────────────────────────────────────────┘
```

______________________________________________________________________

## Core Systems

### Configuration System (`acb.config`)

The configuration system provides centralized settings management with hot-reloading support.

**Key Features:**

- YAML-based configuration files
- Secret management integration
- Environment variable support
- Simple hot-reload monitoring
- Pydantic-based validation

**Configuration Structure:**

```
settings/
├── app.yml          # Application settings
├── debug.yml        # Debug configuration
├── adapters.yml     # Adapter selection
├── models.yml       # Model framework settings
└── secrets/         # Secret files (not committed)
```

**Usage Example:**

```python
from acb.config import Config
from acb.depends import depends


@depends.inject
async def my_function(config: Config = depends()):
    app_name = config.app.name
    debug_mode = config.debug.enabled
```

**Hot-Reload Support:**

```python
from acb.config import Config, enable_config_hot_reload

config = Config()
hot_reload = await enable_config_hot_reload(config, check_interval=5.0)

# Configuration changes are automatically detected
# Stop monitoring when done
await hot_reload.stop()
```

### Dependency Injection (`acb.depends`)

ACB uses the `bevy` framework for dependency injection, enabling automatic component wiring.

**Key Features:**

- Automatic dependency resolution
- Singleton and factory patterns
- Lazy initialization
- Type-based injection

**Usage Example:**

```python
from acb.depends import depends
from acb.adapters import import_adapter

# Import adapter classes
Cache = import_adapter("cache")
Storage = import_adapter("storage")


@depends.inject
async def process_data(
    cache: Cache = depends(), storage: Storage = depends(), config: Config = depends()
):
    # Dependencies automatically injected
    data = await cache.get("key")
    if not data:
        data = await storage.read("file.txt")
        await cache.set("key", data)
    return data
```

### Logging System (`acb.logger`)

Loguru-based async logging with structured output and performance tracking.

**Key Features:**

- Async logging operations
- Structured JSON output
- Performance timing
- Context-aware logging
- Integration with monitoring adapters

**Usage Example:**

```python
from acb.logger import logger

logger.info("Processing request", user_id=123, action="create")
logger.error("Database error", error=str(e), query=sql)
logger.debug("Cache hit", key=cache_key, ttl=300)
```

______________________________________________________________________

## Services Layer

The Services Layer provides business logic orchestration with dependency injection and standardized patterns.

### Service Base (`acb.services.ServiceBase`)

All services inherit from `ServiceBase` which provides:

- Automatic dependency injection
- Lifecycle management
- Error handling patterns
- Integration with events and queues

**Key Components:**

#### 1. Service Discovery (`acb.services.discovery`)

Dynamically discover and register services at runtime.

**Features:**

- Convention-based service discovery
- Service metadata and versioning
- Health check integration
- Capability-based filtering

**Usage:**

```python
from acb.services import ServiceBase, register_service


class UserService(ServiceBase):
    async def create_user(self, data: dict) -> User:
        # Validate input
        await self.validation.validate(data, UserSchema)

        # Business logic
        user = await self.repository.create(User(**data))

        # Emit event
        await self.events.emit("user.created", user_id=user.id)

        return user


# Register service
register_service(UserService)
```

#### 2. Repository Pattern (`acb.services.repository`)

Provides data access abstraction with multiple backend support.

**Features:**

- Unified query interface
- Transaction management via Unit of Work
- Caching integration
- Specification pattern support

**Usage:**

```python
from acb.services.repository import Repository, UnitOfWork


class UserRepository(Repository[User]):
    async def find_by_email(self, email: str) -> User | None:
        return await self.find_one({"email": email})


# Use with Unit of Work for transactions
async with UnitOfWork() as uow:
    user_repo = uow.get_repository(UserRepository)
    user = await user_repo.create(user_data)
    await uow.commit()
```

#### 3. Validation Service (`acb.services.validation`)

Input validation and sanitization with multiple schema support.

**Features:**

- Pydantic schema validation
- Custom validation rules
- Sanitization utilities
- Error result formatting

**Usage:**

```python
from acb.services.validation import ValidationService

validation = ValidationService()

# Validate input
result = await validation.validate(user_data, UserCreateSchema)
if not result.is_valid:
    raise ValidationError(result.errors)

# Sanitize input
clean_html = await validation.sanitize_html(user_input)
```

#### 4. Error Handling (`acb.services.error_handling`)

Standardized error handling with retry mechanisms and circuit breakers.

**Features:**

- Typed exception hierarchy
- Automatic retry with exponential backoff
- Error context preservation
- Integration with monitoring

**Usage:**

```python
from acb.services.error_handling import retry_async, ServiceError


@retry_async(max_attempts=3, backoff=2.0)
async def fetch_external_data(url: str) -> dict:
    try:
        return await http_client.get(url)
    except Exception as e:
        raise ServiceError(f"Failed to fetch data: {e}")
```

______________________________________________________________________

## Event System

The Event System provides pub/sub messaging for decoupled communication between components.

### Key Features

- **Asynchronous event publishing and subscription**
- **Type-safe event definitions**
- **Retry mechanisms with exponential backoff**
- **Event filtering and routing**
- **Integration with task queues for background processing**
- **Event discovery and registration**

### Components

#### 1. Event Publisher (`acb.events.publisher`)

Emits events to all registered subscribers.

**Usage:**

```python
from acb.events import EventPublisher

publisher = EventPublisher()

# Emit event
await publisher.emit(
    "user.created", user_id=user.id, email=user.email, timestamp=datetime.now()
)

# Emit with metadata
await publisher.emit(
    "order.completed",
    order_id=order.id,
    metadata={"priority": "high", "region": "us-west"},
)
```

#### 2. Event Subscriber (`acb.events.subscriber`)

Listens for and handles specific events.

**Usage:**

```python
from acb.events import EventSubscriber

subscriber = EventSubscriber()


@subscriber.on("user.created")
async def handle_user_created(event_data: dict):
    user_id = event_data["user_id"]
    email = event_data["email"]

    # Send welcome email
    await email_service.send_welcome(email)

    # Create user profile
    await profile_service.create(user_id)


# Subscribe to multiple events
@subscriber.on(["user.updated", "user.deleted"])
async def handle_user_changes(event_data: dict):
    await cache.invalidate(f"user:{event_data['user_id']}")
```

#### 3. Event Discovery (`acb.events.discovery`)

Automatically discover and register event handlers.

**Usage:**

```python
from acb.events.discovery import discover_event_handlers

# Discover handlers in specific module
handlers = await discover_event_handlers("myapp.events")

# Register discovered handlers
for handler in handlers:
    subscriber.register(handler)
```

### Integration with Task Queues

Events can trigger background tasks via queue integration:

```python
from acb.events import EventPublisher
from acb.queues import Queue

publisher = EventPublisher()
queue = Queue()


@subscriber.on("order.placed")
async def handle_order_placed(event_data: dict):
    # Queue background task for processing
    await queue.enqueue(
        "process_order", order_id=event_data["order_id"], priority="high"
    )
```

______________________________________________________________________

## Task Queue System

The Task Queue System enables background job processing with multiple backend support.

### Key Features

- **Multiple backends**: Memory, Redis, RabbitMQ
- **Priority queues**
- **Task scheduling and delayed execution**
- **Worker pool management**
- **Retry mechanisms**
- **Task discovery and registration**

### Components

#### 1. Queue Backends

**Memory Queue** (`acb.queues.memory`):

- Simple in-memory queue for development
- No external dependencies
- Lost on restart

**Redis Queue** (`acb.queues.redis`):

- Persistent queue storage
- Distributed worker support
- High performance

**RabbitMQ Queue** (`acb.queues.rabbitmq`):

- Enterprise-grade message broker
- Advanced routing capabilities
- Transaction support

#### 2. Task Definition

```python
from acb.queues import Queue, task

queue = Queue()


@task(queue=queue, max_retries=3)
async def send_email(recipient: str, subject: str, body: str):
    """Send email task"""
    await email_service.send(recipient, subject, body)


@task(queue=queue, priority="high")
async def process_payment(order_id: str, amount: float):
    """Process payment task"""
    await payment_service.charge(order_id, amount)
```

#### 3. Task Enqueueing

```python
from acb.queues import Queue

queue = Queue()

# Enqueue immediate task
await queue.enqueue(
    "send_email",
    recipient="user@example.com",
    subject="Welcome",
    body="Welcome to our service!",
)

# Enqueue with delay
await queue.enqueue_in(
    3600,  # 1 hour delay
    "send_reminder",
    user_id=user.id,
)

# Enqueue at specific time
await queue.enqueue_at(
    datetime(2025, 1, 1, 0, 0, 0), "new_year_greeting", user_id=user.id
)
```

#### 4. Task Scheduler (`acb.queues.scheduler`)

Schedule recurring tasks with cron-like syntax:

```python
from acb.queues import Scheduler

scheduler = Scheduler()


# Run daily at midnight
@scheduler.cron("0 0 * * *")
async def daily_backup():
    await backup_service.run()


# Run every hour
@scheduler.every_hour()
async def cleanup_cache():
    await cache.cleanup()


# Run every 5 minutes
@scheduler.interval(minutes=5)
async def health_check():
    await monitoring.check_health()
```

#### 5. Worker Management

```python
from acb.queues import Worker

# Start worker pool
worker = Worker(queue=queue, concurrency=10)
await worker.start()

# Process tasks
await worker.process()

# Graceful shutdown
await worker.stop()
```

### Queue Configuration

Configure queue backend in `settings/adapters.yml`:

```yaml
queue:
  backend: redis  # memory, redis, rabbitmq
  redis:
    host: localhost
    port: 6379
    db: 0
  workers:
    concurrency: 10
    max_retries: 3
```

______________________________________________________________________

## Workflow Engine

The Workflow Engine orchestrates complex multi-step processes with dependency resolution.

### Key Features

- **Step-based workflow composition**
- **Automatic dependency resolution**
- **Parallel step execution**
- **State management and persistence**
- **Retry logic and error handling**
- **Integration with Events and Task Queues**
- **Dynamic workflow discovery**

### Components

#### 1. Workflow Definition

```python
from acb.workflows import WorkflowDefinition, WorkflowStep

workflow = WorkflowDefinition(
    workflow_id="order-fulfillment",
    name="Order Fulfillment Workflow",
    steps=[
        WorkflowStep(
            step_id="validate",
            name="Validate Order",
            action="validate_order",
            params={"order_id": "${order_id}"},
        ),
        WorkflowStep(
            step_id="charge",
            name="Charge Payment",
            action="charge_payment",
            params={"order_id": "${order_id}"},
            depends_on=["validate"],
        ),
        WorkflowStep(
            step_id="ship",
            name="Ship Order",
            action="ship_order",
            params={"order_id": "${order_id}"},
            depends_on=["charge"],
        ),
        WorkflowStep(
            step_id="notify",
            name="Send Notification",
            action="send_notification",
            params={"order_id": "${order_id}"},
            depends_on=["ship"],
        ),
    ],
)
```

#### 2. Workflow Execution

```python
from acb.workflows import import_workflow_engine

WorkflowEngine = import_workflow_engine("basic")
engine = WorkflowEngine(max_concurrent_steps=5)

# Execute workflow
result = await engine.execute(workflow, context={"order_id": "ORDER-123"})

# Check result
if result.state == WorkflowState.COMPLETED:
    print("Workflow completed successfully")
    for step_result in result.step_results.values():
        print(f"{step_result.step_id}: {step_result.state}")
elif result.state == WorkflowState.FAILED:
    print(f"Workflow failed: {result.error}")
```

#### 3. Parallel Execution

The workflow engine automatically executes independent steps in parallel:

```python
workflow = WorkflowDefinition(
    workflow_id="parallel-processing",
    name="Parallel Data Processing",
    steps=[
        WorkflowStep(
            step_id="fetch_data",
            name="Fetch Data",
            action="fetch_data",
        ),
        # These three steps run in parallel after fetch_data
        WorkflowStep(
            step_id="process_images",
            name="Process Images",
            action="process_images",
            depends_on=["fetch_data"],
        ),
        WorkflowStep(
            step_id="extract_text",
            name="Extract Text",
            action="extract_text",
            depends_on=["fetch_data"],
        ),
        WorkflowStep(
            step_id="generate_thumbnails",
            name="Generate Thumbnails",
            action="generate_thumbnails",
            depends_on=["fetch_data"],
        ),
        # Final step waits for all parallel steps
        WorkflowStep(
            step_id="save_results",
            name="Save Results",
            action="save_results",
            depends_on=["process_images", "extract_text", "generate_thumbnails"],
        ),
    ],
)
```

#### 4. Workflow Service Integration

```python
from acb.workflows import WorkflowService


class OrderService(ServiceBase):
    def __init__(self):
        self.workflow_service = WorkflowService()

    async def fulfill_order(self, order_id: str):
        # Start workflow
        result = await self.workflow_service.execute_workflow(
            "order-fulfillment", {"order_id": order_id}
        )

        # Monitor progress via events
        @self.events.on("workflow.step.completed")
        async def handle_step_completed(event_data: dict):
            step_id = event_data["step_id"]
            logger.info(f"Step completed: {step_id}")

        return result
```

#### 5. Workflow Discovery

```python
from acb.workflows.discovery import (
    list_workflow_engines,
    import_workflow_engine,
    register_workflow_engine,
)

# List available engines
engines = list_workflow_engines()

# Import specific engine
CustomEngine = import_workflow_engine("custom")

# Register custom engine
register_workflow_engine("my-engine", "myapp.workflows.CustomWorkflowEngine")
```

### Workflow Configuration

```yaml
# settings/workflows.yml
workflows:
  max_concurrent_steps: 5
  default_timeout: 300
  retry_attempts: 3

  engines:
    basic:
      enabled: true
    custom:
      enabled: false
```

### Real-World Usage

**In Crackerjack** (`../crackerjack`):

Crackerjack extensively uses workflows for its multi-phase quality assurance pipeline:

```python
# Workflow for code quality checks
quality_workflow = WorkflowDefinition(
    workflow_id="quality-check",
    steps=[
        WorkflowStep("format", "ruff format", depends_on=[]),
        WorkflowStep("lint", "ruff check", depends_on=["format"]),
        WorkflowStep("typecheck", "pyright", depends_on=["format"]),
        WorkflowStep("test", "pytest", depends_on=["lint", "typecheck"]),
        WorkflowStep("coverage", "pytest --cov", depends_on=["test"]),
    ],
)
```

______________________________________________________________________

## Testing Infrastructure

Comprehensive testing support with fixtures, providers, and validation utilities.

### Key Features

- **Adapter mocking and fixtures**
- **Async test support**
- **Coverage tracking**
- **Integration test helpers**
- **Test data providers**

### Components

#### 1. Test Fixtures (`acb.testing.fixtures`)

Reusable test fixtures for common testing scenarios:

```python
import pytest
from acb.testing import mock_config, mock_cache, mock_sql


@pytest.mark.asyncio
async def test_user_service(mock_config, mock_cache, mock_sql):
    """Test with mocked dependencies"""
    service = UserService()

    # Mock cache returns None (cache miss)
    mock_cache.get.return_value = None

    # Mock SQL returns user data
    mock_sql.execute.return_value = {"id": 1, "name": "John"}

    user = await service.get_user(1)
    assert user.name == "John"

    # Verify cache was checked
    mock_cache.get.assert_called_once_with("user:1")
```

#### 2. Adapter Providers (`acb.testing.providers`)

Test data providers for adapters:

```python
from acb.testing.providers import AdapterProvider


class UserTestProvider(AdapterProvider):
    """Provides test data for user testing"""

    @staticmethod
    def user_data() -> dict:
        return {
            "id": 1,
            "name": "Test User",
            "email": "test@example.com",
            "created_at": datetime.now(),
        }

    @staticmethod
    def multiple_users(count: int = 5) -> list[dict]:
        return [UserTestProvider.user_data() for _ in range(count)]


# Use in tests
def test_user_creation():
    user_data = UserTestProvider.user_data()
    user = User(**user_data)
    assert user.name == "Test User"
```

#### 3. Integration Test Helpers

```python
from acb.testing import IntegrationTest


class TestUserServiceIntegration(IntegrationTest):
    """Integration tests with real adapters"""

    @classmethod
    async def setup_class(cls):
        """Setup real adapters for testing"""
        cls.cache = await cls.create_adapter("cache")
        cls.sql = await cls.create_adapter("sql")
        await cls.sql.execute("CREATE TABLE users (...)")

    async def test_user_creation_flow(self):
        """Test complete user creation flow"""
        service = UserService(cache=self.cache, sql=self.sql)

        # Create user
        user = await service.create_user({"name": "John"})

        # Verify in database
        db_user = await self.sql.fetch_one("SELECT * FROM users WHERE id = ?", user.id)
        assert db_user["name"] == "John"

        # Verify cache
        cached = await self.cache.get(f"user:{user.id}")
        assert cached == user
```

#### 4. Pytest Markers

```python
import pytest


# Mark as unit test
@pytest.mark.unit
async def test_validation():
    """Fast unit test"""
    pass


# Mark as integration test
@pytest.mark.integration
async def test_database_integration():
    """Slower integration test"""
    pass


# Mark as benchmark
@pytest.mark.benchmark
async def test_cache_performance():
    """Performance benchmark test"""
    pass


# Skip if condition
@pytest.mark.skipif(not HAS_REDIS, reason="Redis not available")
async def test_redis_cache():
    pass
```

### Test Configuration

```python
# tests/conftest.py
import pytest
from acb.testing import setup_test_environment


@pytest.fixture(scope="session")
async def test_env():
    """Setup test environment"""
    return await setup_test_environment(
        {
            "adapters": {"cache": "memory", "sql": "sqlite", "storage": "memory"},
            "debug": {"enabled": True},
        }
    )
```

### Running Tests

```bash
# Run all tests
python -m pytest

# Run only unit tests
python -m pytest -m unit

# Run with coverage
python -m pytest --cov=acb --cov-report=term

# Run specific test file
python -m pytest tests/services/test_user_service.py

# Run with verbose output
python -m pytest -v
```

______________________________________________________________________

## Migration System

The Migration System handles schema and data migrations for databases.

### Key Features

- **Version-based migrations**
- **Automatic migration discovery**
- **Rollback support**
- **SQL and NoSQL support**
- **Migration validation**
- **Dependency tracking**

### Components

#### 1. Migration Definition

```python
from acb.migrations import Migration


class CreateUsersTable(Migration):
    """Migration: Create users table"""

    version = "001"
    description = "Create users table with basic fields"

    async def up(self):
        """Apply migration"""
        await self.sql.execute("""
            CREATE TABLE users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

    async def down(self):
        """Rollback migration"""
        await self.sql.execute("DROP TABLE users")
```

#### 2. Migration Runner

```python
from acb.migrations import MigrationRunner

runner = MigrationRunner()

# Run pending migrations
await runner.migrate()

# Rollback last migration
await runner.rollback()

# Rollback to specific version
await runner.rollback_to("003")

# Show migration status
status = await runner.status()
for migration in status:
    print(f"{migration.version}: {migration.description}")
    print(f"  Applied: {migration.applied_at}")
```

#### 3. Migration Discovery

```python
from acb.migrations import discover_migrations

# Discover migrations in directory
migrations = await discover_migrations("migrations/")

# Discover with pattern
migrations = await discover_migrations("migrations/", pattern="*.py")
```

#### 4. Data Migrations

```python
class MigrateUserPasswords(Migration):
    """Migration: Migrate passwords to new hash algorithm"""

    version = "005"
    description = "Migrate user passwords to argon2"

    async def up(self):
        """Apply data migration"""
        users = await self.sql.fetch_all("SELECT id, password FROM users")

        for user in users:
            # Re-hash password
            new_hash = argon2.hash(user["password"])
            await self.sql.execute(
                "UPDATE users SET password = ? WHERE id = ?", new_hash, user["id"]
            )

    async def down(self):
        """Rollback not supported for this migration"""
        raise NotImplementedError("Cannot rollback password migration")
```

#### 5. Migration Events

```python
from acb.events import EventSubscriber

subscriber = EventSubscriber()


@subscriber.on("migration.started")
async def handle_migration_started(event_data: dict):
    version = event_data["version"]
    logger.info(f"Starting migration {version}")


@subscriber.on("migration.completed")
async def handle_migration_completed(event_data: dict):
    version = event_data["version"]
    logger.info(f"Completed migration {version}")

    # Invalidate caches that depend on schema
    await cache.flush()


@subscriber.on("migration.failed")
async def handle_migration_failed(event_data: dict):
    version = event_data["version"]
    error = event_data["error"]
    logger.error(f"Migration {version} failed: {error}")
```

### Migration Configuration

```yaml
# settings/migrations.yml
migrations:
  directory: "migrations/"
  table: "_migrations"
  auto_discover: true
  validate_before_apply: true
```

______________________________________________________________________

## Integration Patterns

### Pattern 1: Service + Events + Queues

Combine services with events for real-time updates and queues for background processing:

```python
class OrderService(ServiceBase):
    """Order service with event and queue integration"""

    async def place_order(self, order_data: dict) -> Order:
        # Validate and create order
        order = await self.repository.create(Order(**order_data))

        # Emit real-time event
        await self.events.emit("order.placed", order_id=order.id)

        # Queue background tasks
        await self.queue.enqueue("process_payment", order_id=order.id)
        await self.queue.enqueue("send_confirmation", order_id=order.id)
        await self.queue.enqueue_in(
            3600,  # 1 hour delay
            "send_shipping_update",
            order_id=order.id,
        )

        return order


# Event handlers
@subscriber.on("order.placed")
async def handle_order_placed(event_data: dict):
    # Real-time notification
    await notification_service.notify_user(event_data["order_id"])


# Background tasks
@task(queue=queue)
async def process_payment(order_id: str):
    order = await order_service.get_order(order_id)
    await payment_service.charge(order)
    await events.emit("payment.completed", order_id=order_id)
```

### Pattern 2: Workflow + Services

Use workflows to orchestrate complex service operations:

```python
# Define workflow
user_onboarding_workflow = WorkflowDefinition(
    workflow_id="user-onboarding",
    steps=[
        WorkflowStep(
            step_id="create_account",
            action="user_service.create_user",
        ),
        WorkflowStep(
            step_id="setup_profile",
            action="profile_service.create_profile",
            depends_on=["create_account"],
        ),
        WorkflowStep(
            step_id="send_welcome",
            action="email_service.send_welcome",
            depends_on=["create_account"],
        ),
        WorkflowStep(
            step_id="create_preferences",
            action="preference_service.create_defaults",
            depends_on=["create_account"],
        ),
    ],
)


# Execute via service
class OnboardingService(ServiceBase):
    async def onboard_user(self, user_data: dict):
        result = await self.workflow_engine.execute(
            user_onboarding_workflow, context=user_data
        )

        if result.state == WorkflowState.COMPLETED:
            await self.events.emit(
                "onboarding.completed", user_id=result.outputs["user_id"]
            )

        return result
```

### Pattern 3: Testing with All Systems

Comprehensive integration testing:

```python
class TestOrderFlowIntegration(IntegrationTest):
    """Test complete order flow with all systems"""

    async def test_complete_order_flow(self):
        # Setup
        order_service = OrderService()

        # Track events
        events_received = []

        @subscriber.on("order.placed")
        async def track_event(event_data):
            events_received.append(event_data)

        # Place order
        order = await order_service.place_order(
            {"items": [{"id": 1, "qty": 2}], "customer_id": 123}
        )

        # Verify event emitted
        assert len(events_received) == 1
        assert events_received[0]["order_id"] == order.id

        # Verify queue tasks enqueued
        tasks = await queue.get_pending_tasks()
        assert any(t["task"] == "process_payment" for t in tasks)

        # Process queued tasks
        worker = Worker(queue=queue)
        await worker.process_all()

        # Verify workflow completed
        workflow_result = await workflow_service.get_result(order.id)
        assert workflow_result.state == WorkflowState.COMPLETED
```

______________________________________________________________________

## Usage in Real Projects

### FastBlocks Integration

[FastBlocks](https://github.com/lesleslie/fastblocks) is a high-performance web framework built on ACB that showcases enterprise-grade patterns:

**Services Layer:**

```python
from fastblocks import Service
from acb.services import ServiceBase


class UserService(ServiceBase):
    """FastBlocks user service with ACB integration"""

    async def authenticate(self, email: str, password: str) -> User:
        # Use ACB cache for session management
        cached_user = await self.cache.get(f"user:{email}")
        if cached_user:
            return cached_user

        # Query database
        user = await self.repository.find_by_email(email)
        if user and verify_password(password, user.password):
            await self.cache.set(f"user:{email}", user, ttl=3600)

            # Emit event
            await self.events.emit("user.authenticated", user_id=user.id)

            return user

        raise AuthenticationError("Invalid credentials")
```

**Event Integration:**

```python
# Real-time notifications
@subscriber.on("user.authenticated")
async def track_login(event_data: dict):
    await analytics.track_event("login", event_data)


@subscriber.on("page.viewed")
async def update_analytics(event_data: dict):
    await queue.enqueue("process_analytics", event_data)
```

### Crackerjack Integration

[Crackerjack](https://github.com/lesleslie/crackerjack) uses ACB's workflow system for its quality assurance pipeline:

**Workflow Orchestration:**

```python
# Quality check workflow
qa_workflow = WorkflowDefinition(
    workflow_id="qa-pipeline",
    steps=[
        WorkflowStep("format", "ruff format"),
        WorkflowStep("lint", "ruff check", depends_on=["format"]),
        WorkflowStep("typecheck", "pyright", depends_on=["format"]),
        WorkflowStep("security", "bandit", depends_on=["format"]),
        WorkflowStep("test", "pytest", depends_on=["lint", "typecheck"]),
        WorkflowStep("coverage", "pytest --cov", depends_on=["test"]),
    ],
)

# Execute with event tracking
result = await workflow_engine.execute(qa_workflow)


@subscriber.on("workflow.step.completed")
async def track_qa_progress(event_data: dict):
    logger.info(f"QA step completed: {event_data['step_id']}")
```

**Queue Integration:**

```python
# Background quality checks
@task(queue=queue, priority="high")
async def run_security_scan(repo_path: str):
    await crackerjack.scan_security(repo_path)


@task(queue=queue, priority="low")
async def generate_coverage_report(test_results: dict):
    await crackerjack.generate_report(test_results)
```

### Custom Application Example

Building a complete application with all ACB systems:

```python
from acb import depends
from acb.services import ServiceBase
from acb.workflows import WorkflowDefinition, import_workflow_engine
from acb.events import EventPublisher, EventSubscriber
from acb.queues import Queue, task


# Configure application
class BlogService(ServiceBase):
    """Blog service with full ACB integration"""

    async def publish_post(self, post_data: dict) -> Post:
        # Validate
        await self.validation.validate(post_data, PostSchema)

        # Create post
        post = await self.repository.create(Post(**post_data))

        # Emit event for real-time updates
        await self.events.emit(
            "post.published", post_id=post.id, author_id=post.author_id
        )

        # Queue background tasks
        await self.queue.enqueue("generate_sitemap")
        await self.queue.enqueue("send_notifications", post_id=post.id)
        await self.queue.enqueue("update_search_index", post_id=post.id)

        return post

    async def import_posts(self, import_data: dict):
        # Use workflow for complex import process
        workflow = WorkflowDefinition(
            workflow_id="import-posts",
            steps=[
                WorkflowStep("validate", "validate_import_data"),
                WorkflowStep("backup", "backup_database", depends_on=["validate"]),
                WorkflowStep("import", "import_posts_batch", depends_on=["backup"]),
                WorkflowStep("reindex", "update_search_index", depends_on=["import"]),
                WorkflowStep("notify", "send_completion_email", depends_on=["reindex"]),
            ],
        )

        return await self.workflow_engine.execute(workflow, context=import_data)


# Event handlers
subscriber = EventSubscriber()


@subscriber.on("post.published")
async def handle_post_published(event_data: dict):
    # Real-time notification to subscribers
    await notification_service.notify_subscribers(event_data["post_id"])

    # Update cache
    await cache.invalidate("recent_posts")


# Background tasks
queue = Queue()


@task(queue=queue)
async def generate_sitemap():
    posts = await blog_service.get_all_posts()
    await sitemap_generator.generate(posts)


@task(queue=queue, max_retries=3)
async def send_notifications(post_id: str):
    post = await blog_service.get_post(post_id)
    subscribers = await subscription_service.get_subscribers()

    for subscriber in subscribers:
        await email_service.send(subscriber.email, post)


@task(queue=queue, priority="low")
async def update_search_index(post_id: str):
    post = await blog_service.get_post(post_id)
    await search_engine.index(post)
```

______________________________________________________________________

## Summary

ACB's core systems work together to provide a complete framework for building modern Python applications:

- **Services Layer**: Business logic orchestration with dependency injection
- **Event System**: Decoupled communication via pub/sub messaging
- **Task Queues**: Background job processing with multiple backends
- **Workflow Engine**: Complex multi-step process orchestration
- **Testing Infrastructure**: Comprehensive testing support
- **Migration System**: Schema and data migration management

These systems are designed to be used independently or combined for maximum flexibility. Whether building a simple web service or a complex enterprise application, ACB provides the tools needed for clean, maintainable, and scalable code.

For more information, see:

- \[[README|Main README]\]
- \[[MIGRATION-GUIDE|Migration Guide]\]
- [Individual adapter documentation](../acb/adapters/)
