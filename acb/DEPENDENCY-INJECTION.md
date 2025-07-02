# Dependency Injection Documentation

> **ACB Documentation**: [Main](../README.md) | [Core Systems](./README.md) | [Actions](./actions/README.md) | [Adapters](./adapters/README.md)

## Overview

ACB's dependency injection system is built on the [bevy](https://github.com/bevy-org/bevy) package and provides a clean, FastAPI-like approach to component wiring and dependency management.

## Core Components

### The `depends` Object

The central dependency injection interface provides three main functions:

```python
from acb.depends import depends

# Register a dependency
depends.set(MyClass, instance)

# Retrieve a dependency
instance = depends.get(MyClass)

# Inject dependencies into functions
@depends.inject
async def my_function(config: Config = depends()):
    # Dependencies automatically provided
    pass
```

## Registration Patterns

### Automatic Registration

ACB automatically registers core components:

```python
# These are automatically available
from acb.config import Config
from acb.logger import Logger

@depends.inject
async def my_function(
    config: Config = depends(),
    logger: Logger = depends()
):
    logger.info(f"App: {config.app.name}")
```

### Manual Registration

Register your own components:

```python
from acb.depends import depends

class MyService:
    def __init__(self, api_key: str):
        self.api_key = api_key

    async def do_work(self) -> str:
        return "Work completed"

# Register the service
service = MyService("secret-key")
depends.set(MyService, service)

# Now it's available for injection
@depends.inject
async def use_service(service: MyService = depends()):
    result = await service.do_work()
    return result
```

### Adapter Registration

Adapters are registered automatically when imported:

```python
from acb.adapters import import_adapter

# Import and register adapters
Cache = import_adapter("cache")
Storage = import_adapter("storage")

# Or use automatic detection
# Cache, Storage = import_adapter()  # Detects from variable names

@depends.inject
async def process_data(
    cache: Cache = depends(),
    storage: Storage = depends()
):
    # Adapters are injected based on configuration
    pass
```

## Injection Patterns

### Function Injection

The most common pattern using the `@depends.inject` decorator:

```python
from acb.depends import depends
from acb.config import Config
import typing as t

@depends.inject
async def process_user_data(
    user_id: str,
    config: Config = depends(),
    cache: Cache = depends()
) -> dict[str, t.Any]:
    """Process user data with injected dependencies."""
    app_name = config.app.name

    # Check cache first
    cached_data = await cache.get(f"user:{user_id}")
    if cached_data:
        return cached_data

    # Process and cache result
    result = {"user_id": user_id, "app": app_name, "processed": True}
    await cache.set(f"user:{user_id}", result, ttl=3600)
    return result
```

### Direct Retrieval

For cases where decorator injection isn't suitable:

```python
from acb.depends import depends
from acb.config import Config

async def manual_retrieval():
    # Get dependencies directly
    config = depends.get(Config)
    cache = depends.get("cache")  # Can use string names

    # Use the dependencies
    app_name = config.app.name
    await cache.set("key", "value")
```

### Class-based Injection

For service classes:

```python
from acb.depends import depends
from acb.config import Config

class UserService:
    def __init__(self):
        self.config = depends.get(Config)
        self.cache = depends.get("cache")

    async def get_user(self, user_id: str) -> dict:
        # Use injected dependencies
        cached = await self.cache.get(f"user:{user_id}")
        if cached:
            return cached
        # Fetch and cache user...
```

## Advanced Patterns

### Conditional Dependencies

```python
from acb.depends import depends
from acb.config import Config

@depends.inject
async def conditional_processing(
    data: dict,
    config: Config = depends()
):
    if config.debug.enabled:
        logger = depends.get("logger")
        logger.debug(f"Processing data: {data}")

    # Process data...
```

### Factory Pattern

```python
from acb.depends import depends

class ServiceFactory:
    @staticmethod
    @depends.inject
    def create_service(config: Config = depends()) -> "MyService":
        if config.app.environment == "production":
            return ProductionService(config)
        return DevelopmentService(config)

# Register the factory result
service = ServiceFactory.create_service()
depends.set(MyService, service)
```

### Dependency Chains

```python
class DatabaseService:
    @depends.inject
    def __init__(self, config: Config = depends()):
        self.config = config
        self.connection = None

class UserRepository:
    @depends.inject
    def __init__(self, db: DatabaseService = depends()):
        self.db = db

class UserService:
    @depends.inject
    def __init__(self, repo: UserRepository = depends()):
        self.repo = repo

# Register in dependency order
depends.set(DatabaseService)
depends.set(UserRepository)
depends.set(UserService)
```

## Type Hints and IDE Support

### Proper Type Annotations

```python
import typing as t
from acb.depends import depends
from acb.adapters import import_adapter

# Import adapter types
Cache = import_adapter("cache")
Storage = import_adapter("storage")

@depends.inject
async def typed_function(
    user_id: str,
    cache: Cache = depends(),  # Type-safe injection
    storage: Storage = depends()
) -> dict[str, t.Any]:
    # IDE will provide proper autocomplete
    await cache.set("key", "value")
    await storage.put_file("file.txt", b"content")
    return {"status": "processed"}
```

### Generic Dependencies

```python
import typing as t
from acb.depends import depends

T = t.TypeVar('T')

@depends.inject
async def generic_processor(
    data: T,
    config: Config = depends()
) -> T:
    # Process data while maintaining type
    return data
```

## Testing with Dependency Injection

### Mock Dependencies

```python
import pytest
from unittest.mock import AsyncMock
from acb.depends import depends

@pytest.fixture
def mock_cache():
    mock = AsyncMock()
    mock.get.return_value = None
    mock.set.return_value = None
    depends.set("cache", mock)
    yield mock

@pytest.mark.asyncio
async def test_function_with_mocks(mock_cache):
    @depends.inject
    async def test_function(cache=depends("cache")):
        await cache.set("key", "value")
        return await cache.get("key")

    result = await test_function()
    mock_cache.set.assert_called_once_with("key", "value")
```

### Dependency Isolation

```python
import pytest
from acb.depends import depends

@pytest.fixture(autouse=True)
def isolate_dependencies():
    # Store original state
    original_repo = depends._repository

    # Create clean repository for test
    depends._repository = {}

    yield

    # Restore original state
    depends._repository = original_repo
```

## Best Practices

1. **Use Type Hints**: Always provide type annotations for better IDE support
2. **Prefer Injection**: Use `@depends.inject` over manual `depends.get()` calls
3. **Register Early**: Register dependencies during application startup
4. **Test Isolation**: Use dependency mocking in tests
5. **Avoid Circular Dependencies**: Design components to avoid circular references
6. **Use Interfaces**: Depend on abstract base classes or protocols when possible
7. **Document Dependencies**: Clearly document what dependencies a function requires

## Common Patterns

### Service Layer Pattern

```python
# Define service interfaces
class UserServiceInterface(Protocol):
    async def get_user(self, user_id: str) -> User: ...
    async def create_user(self, user_data: dict) -> User: ...

# Implement services
class UserService:
    @depends.inject
    def __init__(self, db: Database = depends(), cache: Cache = depends()):
        self.db = db
        self.cache = cache

    async def get_user(self, user_id: str) -> User:
        # Implementation...
        pass

# Register and use
depends.set(UserServiceInterface, UserService())

@depends.inject
async def api_handler(
    user_id: str,
    user_service: UserServiceInterface = depends()
):
    return await user_service.get_user(user_id)
```

### Configuration-Based Factory

```python
@depends.inject
def create_storage_adapter(config: Config = depends()):
    """Create storage adapter based on configuration."""
    if config.storage.provider == "s3":
        return S3Storage(config.storage)
    elif config.storage.provider == "gcs":
        return GCSStorage(config.storage)
    else:
        return FileStorage(config.storage)

# Register the factory result
storage = create_storage_adapter()
depends.set(StorageInterface, storage)
```

## Troubleshooting

### Common Issues

**Dependency Not Found**: Ensure the dependency is registered before use.

**Type Annotation Errors**: Verify that type hints match registered types.

**Circular Dependencies**: Redesign components to eliminate circular references.

**Testing Issues**: Use proper mocking and dependency isolation in tests.
