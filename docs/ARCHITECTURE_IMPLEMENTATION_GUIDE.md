# ACB Architecture Implementation Guide

## Overview

This document provides implementation guidance for the ACB (Asynchronous Component Base) framework, detailing the architectural layers, patterns, and best practices for implementing components according to the current architecture.

## Architectural Layers

### 1. Application Layer

- Contains application-specific business logic
- Uses ACB components to implement domain functionality
- Frameworks like FastBlocks operate at this layer

### 2. Services Layer

- **Purpose**: Stateful components with lifecycle management
- **Examples**: Repository, Validation, Performance services
- **Pattern**: Inherit from `ServiceBase` for standardized lifecycle
- **Responsibilities**: Business services with health checks, metrics, and resource management

### 3. Orchestration Layer

- **Purpose**: Communication and process management between components
- **Examples**: Events, Tasks, Workflows, MCP (Model Context Protocol)
- **Pattern**: Event-driven and background processing systems
- **Responsibilities**: Communication, background job execution, workflow orchestration

### 4. Adapter Layer

- **Purpose**: Standardized interfaces to external systems
- **Examples**: Cache, SQL, NoSQL, Storage, Secret, etc.
- **Pattern**: Configuration-driven implementation selection
- **Responsibilities**: Abstracting external system details

### 5. Core Infrastructure

- **Purpose**: Foundational services for the framework
- **Examples**: Config, Dependency Injection, Logger, Context, SSL
- **Pattern**: Singleton services with consistent interfaces
- **Responsibilities**: Cross-cutting concerns and base functionality

### 6. Actions Layer (Special Case)

- **Purpose**: Self-contained utility functions for common tasks
- **Examples**: Compression, encoding, hashing, etc.
- **Pattern**: Module-level functions organized by verb category
- **Note**: Actions are not a runtime architectural layer like services or adapters, but rather a utility collection that can be used throughout other layers

## Implementation Patterns

### Service Implementation

#### For Complex Services (with Multiple Implementations)

```python
# Use _base.py pattern for complex domains

# myapp/services/data/_base.py
from abc import ABC, abstractmethod
from typing import Protocol, TypeVar


class DataProcessorProtocol(Protocol):
    async def process(self, data: dict) -> dict: ...


T = TypeVar("T")


class DataProcessorBase(ABC):
    @abstractmethod
    async def process(self, data: dict) -> dict: ...
```

```python
# myapp/services/data/service.py
from acb.services._base import ServiceBase
from ._base import DataProcessorBase


class DataProcessingService(ServiceBase, DataProcessorBase):
    def __init__(self):
        from acb.services._base import ServiceConfig

        service_config = ServiceConfig(
            service_id="data_processing", name="Data Processing Service", priority=50
        )
        super().__init__(service_config=service_config)

    async def _initialize(self) -> None:
        # Service-specific initialization
        pass

    async def _shutdown(self) -> None:
        # Service-specific cleanup
        pass

    async def _health_check(self) -> dict:
        return {"status": "healthy"}

    async def process(self, data: dict) -> dict:
        # Implementation
        return data
```

#### For Simple Services (Focused Functionality)

```python
# For focused services, use direct ServiceBase inheritance
from acb.services._base import ServiceBase, ServiceConfig


class SimpleCacheService(ServiceBase):
    def __init__(self):
        service_config = ServiceConfig(
            service_id="simple_cache", name="Simple Cache Service"
        )
        super().__init__(service_config=service_config)

    async def _initialize(self) -> None:
        # Simple initialization
        pass

    async def _shutdown(self) -> None:
        # Simple cleanup
        pass

    async def _health_check(self) -> dict:
        return {"status": "healthy"}
```

### Event Implementation

```python
from acb.events import event_handler, EventHandlerResult, create_event
from acb.depends import depends


@event_handler("user.created")
async def handle_user_created(event):
    """Handle user creation events."""
    # Process the event
    user_id = event.payload.get("user_id")

    # Perform actions
    result = await process_user_creation(user_id)

    return EventHandlerResult(success=True, metadata={"processed_user_id": user_id})


# Publishing events
event = create_event(
    "user.created", "user_service", {"user_id": 123, "email": "user@example.com"}
)
publisher = depends.get(EventPublisher)
await publisher.publish(event)
```

### Task Implementation

```python
from acb.tasks import task_handler, TaskData


@task_handler("process_upload")
async def process_upload_task(task_data: TaskData):
    """Task to process file uploads."""
    file_path = task_data.payload.get("file_path")

    # Process the upload
    result = await upload_and_process_file(file_path)

    return {"status": "completed", "file_path": file_path, "result": result}
```

### Adapter Implementation

```python
# Adapters should follow the standard ACB adapter pattern
from acb.config import Settings
from acb.cleanup import CleanupMixin


class MyAdapterSettings(Settings):
    host: str = "localhost"
    port: int = 8080


class MyAdapter(CleanupMixin):
    def __init__(self, settings: MyAdapterSettings | None = None):
        super().__init__()
        self.settings = settings or MyAdapterSettings()
        self._client = None

    async def _ensure_client(self):
        if self._client is None:
            self._client = await create_client(self.settings)
            self.register_resource(self._client)
        return self._client

    async def do_operation(self, data: dict):
        client = await self._ensure_client()
        return await client.process(data)
```

### Action Implementation

```python
# Actions are simple utility functions
# acb/actions/crypto/hash.py
async def blake3(data: bytes) -> str:
    """Generate blake3 hash of data."""
    import blake3

    return blake3.blake3(data).hexdigest()


# Usage
from acb.actions.hash import hash

file_hash = await hash.blake3(b"file content")
```

## Actions in the Architecture

Actions are **not** a runtime architectural layer comparable to Services, Orchestration, or Adapters. Instead, they are:

1. **Utility Functions**: Self-contained operations that don't rely on external systems
1. **No Lifecycle Management**: Stateless operations that can be called directly
1. **Organization by Function**: Grouped by verb-based categories (compress, encode, hash)
1. **Immediate Availability**: No initialization needed, available when module is imported

### Correct Placement of Actions:

- **Not a Layer**: Actions are not a runtime architectural layer
- **Cross-cutting Utility**: Available throughout other layers as needed
- **No Dependency Injection**: Direct function calls, not injected services
- **Pure Functions**: Stateless operations with consistent inputs/outputs

### When to Use Actions vs Other Layers:

- **Use Actions** for: Stateless utility operations (compression, hashing, encoding)
- **Use Services** for: Stateful components with lifecycle management
- **Use Adapters** for: External system integrations
- **Use Events/Tasks** for: Inter-component communication and background processing

## Development Best Practices

1. **Choose the Right Layer**: Select the appropriate architectural layer based on functionality:

   - Stateful operations → Services
   - External integrations → Adapters
   - Communication → Events/Tasks
   - Utility functions → Actions

1. **Follow Layer Responsibilities**: Don't mix concerns between layers

   - Services handle business logic and lifecycle
   - Adapters handle external system integration
   - Events handle communication
   - Actions handle utility operations

1. **Consistent Service Patterns**: Use the `_base.py` pattern for complex domains, direct inheritance for simple services

1. **Configuration-Driven**: Use configuration files to control implementations and settings

1. **Dependency Injection**: Use ACB's DI system for component wiring and testing

## Example: Complete Component Implementation

```python
# Complete example showing all layers working together

# 1. Service Layer: Data Processing Service
class DataProcessingService(ServiceBase):
    def __init__(self):
        service_config = ServiceConfig(
            service_id="data_processor", name="Data Processing Service"
        )
        super().__init__(service_config=service_config)

    async def process_data(self, raw_data: bytes):
        # Use actions for utility operations
        from acb.actions.hash import hash
        from acb.actions.compress import compress

        # Hash the data
        data_hash = await hash.blake3(raw_data)

        # Compress the data
        compressed_data = compress.gzip(raw_data)

        # Use adapters for external operations
        Cache = import_adapter("cache")
        cache = depends.get(Cache)

        await cache.set(f"data:{data_hash}", compressed_data)

        # Emit an event for other components
        event = create_event(
            "data.processed",
            "data_processor",
            {"hash": data_hash, "size": len(raw_data)},
        )

        publisher = depends.get(EventPublisher)
        await publisher.publish(event)

        return {"hash": data_hash, "size": len(raw_data)}


# 2. Event Handler: Process the event
@event_handler("data.processed")
async def handle_data_processed(event):
    # Process the completed data operation
    hash_value = event.payload["hash"]
    size = event.payload["size"]
    print(f"Data {hash_value} processed successfully ({size} bytes)")

    return EventHandlerResult(success=True)


# 3. Usage with dependency injection
@depends.inject
async def process_user_upload(data_service: Inject[DataProcessingService] = depends()):
    raw_data = b"example upload data"
    result = await data_service.process_data(raw_data)
    return result
```

This implementation guide reflects the current ACB architecture where services, orchestration components, adapters, and actions each have their proper place and implementation patterns.
