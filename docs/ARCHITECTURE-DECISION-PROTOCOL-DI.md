# Architecture Decision Record: Protocol-Based Dependency Injection for Services

**Status**: Accepted
**Date**: 2025-10-16
**Decision Makers**: ACB Core Team
**Version**: ACB v0.20.0+

______________________________________________________________________

## Context and Problem Statement

ACB (Asynchronous Component Base) has historically used concrete class-based dependency injection for both adapters (external system integrations) and services (business logic components). With the reintroduction of the Services layer in v0.20.0, we need to decide:

**Should ACB adopt Protocol-based dependency injection for the Services layer, or continue using concrete classes for all components?**

This decision affects:

- **Developer Experience**: How easy is it to write and understand service code?
- **Testability**: How difficult is it to write unit tests and mock dependencies?
- **Type Safety**: How well do type checkers catch errors at development time?
- **Flexibility**: How easy is it to swap implementations or extend functionality?
- **Performance**: What is the runtime overhead of different DI patterns?
- **Consistency**: Should all ACB components use the same DI pattern?

## Decision Drivers

### Technical Factors

1. **Architectural Layer Differences**

   - **Adapters**: External system integration requiring shared infrastructure code
   - **Services**: Business logic orchestration requiring clean interfaces

1. **Testing Requirements**

   - Services contain complex business logic requiring extensive mocking
   - Adapters provide infrastructure utilities with simpler testing needs

1. **Implementation Patterns**

   - Adapters need base classes for connection pooling, retry logic, cleanup patterns
   - Services benefit from interface-only definitions without implementation inheritance

1. **Type System Evolution**

   - Python 3.13+ has excellent Protocol support with structural typing
   - Modern type checkers (pyright, mypy) handle Protocols well

1. **Framework Philosophy**

   - ACB prioritizes **explicit over implicit**
   - ACB values **simple over complex** for adapters
   - ACB embraces **modern Python patterns** where beneficial

### Practical Considerations

6. **Migration Impact**: Existing adapter code is stable and well-tested
1. **Learning Curve**: Developers need to understand when to use which pattern
1. **Documentation**: Clear guidance needed for both patterns
1. **Ecosystem Compatibility**: Integration with FastBlocks and other ACB-based projects

## Considered Options

### Option 1: Universal Protocol-Based DI

**Description**: Convert ALL components (adapters + services) to Protocol-based DI

**Pros**:

- ✅ Consistent DI pattern across entire codebase
- ✅ Maximum testability for all components
- ✅ Clean separation of interface and implementation everywhere

**Cons**:

- ❌ Loses shared adapter infrastructure (connection pooling, retry logic, cleanup)
- ❌ Duplicates utility code across adapter implementations
- ❌ Breaks stable, well-tested adapter base classes
- ❌ Large migration effort with unclear benefits for adapters
- ❌ Complexity where simplicity was working well

**Verdict**: ❌ **Rejected** - Sacrifices proven adapter patterns for consistency that doesn't add value

______________________________________________________________________

### Option 2: Keep Concrete Classes for Everything

**Description**: Continue using concrete class DI for both adapters and services

**Pros**:

- ✅ No migration needed - zero breaking changes
- ✅ Consistent DI pattern across entire codebase
- ✅ Keeps proven adapter infrastructure patterns
- ✅ Simple mental model - one DI approach

**Cons**:

- ❌ Services tightly coupled to concrete implementations
- ❌ Difficult to mock complex service dependencies in tests
- ❌ Forces inheritance where composition would be cleaner
- ❌ Business logic tests require full implementation stack
- ❌ Misses benefits of Python's Protocol type system for business logic

**Verdict**: ❌ **Rejected** - Works for adapters, but limits service testability and flexibility

______________________________________________________________________

### Option 3: Hybrid Approach (SELECTED)

**Description**: Protocol-based DI for Services, Concrete class DI for Adapters

**Pros**:

- ✅ **Services**: Clean interfaces, easy mocking, flexible testing
- ✅ **Adapters**: Keep proven infrastructure patterns intact
- ✅ **Best of Both Worlds**: Right tool for each layer
- ✅ **Zero Breaking Changes**: Existing adapter code unchanged
- ✅ **Clear Mental Model**: Pattern choice matches architectural layer

**Cons**:

- ⚠️ Two DI patterns to learn (mitigated by clear documentation)
- ⚠️ Need decision matrix for edge cases (mitigated by architectural guidelines)

**Verdict**: ✅ **SELECTED** - Pragmatic solution maximizing benefits while minimizing disruption

______________________________________________________________________

## Decision Outcome

**We adopt a hybrid dependency injection architecture:**

| Component Type | DI Pattern | Interface Type | Injection Syntax | Rationale |
|---------------|-----------|----------------|------------------|-----------|
| **Services** | Protocol-based | `ServiceProtocol` | `Inject[RepositoryServiceProtocol]` | Clean interfaces, easy testing, business logic flexibility |
| **Adapters** | Concrete class | Base class | `Inject[Cache]` | Shared infrastructure, proven patterns, configuration-driven |
| **Core** | Concrete class | Direct class | `Inject[Config]` | Foundational, stable, simple |

### Key Principles

1. **Services Use Protocols** - Business logic components define Protocol interfaces for clean, testable contracts
1. **Adapters Use Concrete Classes** - Infrastructure components use base classes for shared implementation
1. **Core Uses Concrete Classes** - Foundational components (Config, Logger) use direct classes for simplicity

### Implementation Guidelines

#### For Services (Protocol-Based DI)

**Define Protocol Interface:**

```python
# acb/services/protocols.py
from typing import Protocol, AsyncContextManager
import typing as t


class RepositoryServiceProtocol(Protocol):
    """Protocol for repository services with Unit of Work pattern."""

    def unit_of_work(self) -> AsyncContextManager[UnitOfWork]:
        """Begin a unit of work transaction."""
        ...

    async def get(self, entity_id: str | UUID) -> EntityProtocol | None:
        """Get entity by ID."""
        ...

    async def save(
        self,
        entity: EntityProtocol,
        uow: UnitOfWork | None = None,
    ) -> None:
        """Save entity within optional unit of work."""
        ...
```

**Implement Concrete Service:**

```python
# acb/services/repository/sql_repository.py
from acb.services.protocols import RepositoryServiceProtocol, UnitOfWork
from acb.depends import depends, Inject
from acb.adapters import import_adapter

Sql = import_adapter("sql")


class SqlRepositoryService:
    """SQL-based repository implementation.

    Implements RepositoryServiceProtocol using SQL adapter.
    """

    @depends.inject
    def __init__(self, sql: Inject[Sql]) -> None:
        self._sql = sql

    @asynccontextmanager
    async def unit_of_work(self) -> AsyncGenerator[UnitOfWork]:
        """Begin SQL transaction."""
        async with self._sql.transaction() as txn:
            yield UnitOfWork(transaction=txn)

    async def get(self, entity_id: str | UUID) -> EntityProtocol | None:
        """Fetch entity from SQL database."""
        # Implementation...
        pass
```

**Use in Business Logic:**

```python
from acb.depends import depends, Inject
from acb.services.protocols import RepositoryServiceProtocol, ValidationServiceProtocol


@depends.inject
async def process_order(
    order_id: str,
    repo: Inject[RepositoryServiceProtocol],  # Protocol, not concrete!
    validator: Inject[ValidationServiceProtocol],
):
    """Process an order with validation and persistence."""
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

**Test with Mock:**

```python
import pytest
from unittest.mock import AsyncMock, MagicMock
from acb.depends import depends


# Mock implements the Protocol interface
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


@pytest.fixture
def mock_repo():
    return MockRepository()


@pytest.mark.asyncio
async def test_process_order(mock_repo):
    # Register mock for Protocol
    depends.set(RepositoryServiceProtocol, mock_repo)

    # Test uses Protocol interface, not concrete class
    await process_order("order-123")

    assert "order-123" in mock_repo.entities
```

#### For Adapters (Concrete Class DI)

**Use Existing Base Class:**

```python
# acb/adapters/cache/redis.py
from acb.adapters.cache._base import CacheBase
from acb.cleanup import CleanupMixin


class Cache(CacheBase, CleanupMixin):
    """Redis cache adapter - concrete implementation."""

    async def set(self, key: str, value: Any, ttl: int = 300) -> None:
        # Shared infrastructure from CacheBase
        client = await self._ensure_client()
        await client.set(key, value, ex=ttl)
```

**Use in Infrastructure Code:**

```python
from acb.depends import depends, Inject
from acb.adapters import import_adapter

Cache = import_adapter("cache")
Storage = import_adapter("storage")


@depends.inject
async def cache_uploaded_file(
    file_path: str,
    cache: Inject[Cache],  # Concrete class, not Protocol
    storage: Inject[Storage],
):
    """Cache file metadata from storage."""
    metadata = await storage.get_metadata(file_path)
    await cache.set(f"metadata:{file_path}", metadata, ttl=3600)
```

**Why No Protocol for Adapters?**

Adapters benefit from shared base class infrastructure:

- Connection pooling via `_ensure_client()`
- Retry logic via `_retry_operation()`
- Resource cleanup via `CleanupMixin`
- Configuration loading from `settings/adapters.yml`
- Standard lifecycle methods (`connect()`, `disconnect()`, `health_check()`)

These utilities would need duplication across implementations if using Protocols.

### Messaging Adapter Exception

**Messaging adapters DO use Protocols** because they provide dual interfaces (pub/sub + queue):

```python
# acb/adapters/messaging/_base.py
from typing import Protocol


class PubSubBackend(Protocol):
    """Protocol for pub/sub messaging (events system)."""

    async def publish(self, topic: str, message: bytes) -> None: ...
    async def subscribe(self, topic: str) -> Subscription: ...


class QueueBackend(Protocol):
    """Protocol for queue messaging (tasks system)."""

    async def enqueue(self, queue: str, message: bytes) -> str: ...
    async def dequeue(self, queue: str) -> QueueMessage | None: ...


class UnifiedMessagingBackend(Protocol):
    """Combines both interfaces for unified backends like Redis."""

    # Includes all methods from both PubSubBackend and QueueBackend
```

This is an exception because:

- Events system needs `PubSubBackend` interface
- Tasks system needs `QueueBackend` interface
- Same backend (Redis) implements both interfaces
- Protocol structural typing enables this dual-interface pattern

______________________________________________________________________

## Consequences

### Positive Consequences

1. **✅ Services Are Highly Testable**

   - Protocol interfaces easy to mock in unit tests
   - No need to instantiate full infrastructure stack
   - Fast test execution with minimal dependencies

1. **✅ Services Are Flexible**

   - Swap implementations without changing business logic
   - Multiple implementations of same Protocol (e.g., SqlRepository, MongoRepository)
   - Composition over inheritance for service design

1. **✅ Adapters Keep Proven Patterns**

   - Zero breaking changes to stable adapter code
   - Shared infrastructure remains intact
   - Connection pooling, retry logic, cleanup patterns preserved

1. **✅ Clear Architectural Boundaries**

   - DI pattern signals architectural layer (Service vs Adapter)
   - Developers know which pattern to use based on component type
   - Consistent with ACB's layered architecture

1. **✅ Type Safety for Business Logic**

   - Protocols provide excellent type checking for service interfaces
   - Structural typing catches interface mismatches at development time
   - Modern type checkers (pyright, mypy) excel with Protocols

### Negative Consequences

1. **⚠️ Two DI Patterns to Learn**

   - **Mitigation**: Comprehensive documentation in CLAUDE.md, this ADR, and services/protocols.py
   - **Severity**: LOW - Clear architectural boundaries make decision obvious

1. **⚠️ Potential Confusion for Edge Cases**

   - **Mitigation**: Decision matrix and examples in documentation
   - **Severity**: LOW - Edge cases are rare, defaults are clear

1. **⚠️ Initial Migration Effort**

   - **Mitigation**: Only new Services layer affected, adapters unchanged
   - **Severity**: LOW - Isolated to new v0.20.0+ features

### Neutral Consequences

1. **📊 Performance Impact**
   - Protocol structural typing has negligible runtime overhead
   - Both patterns use the same `bevy` DI framework
   - No measurable performance difference in practice

______________________________________________________________________

## Implementation Notes

### File Structure

**Services Layer:**

```
acb/services/
├── protocols.py              # Protocol interfaces (NEW)
├── __init__.py               # Exports protocols
├── repository/
│   ├── sql_repository.py     # Implements RepositoryServiceProtocol
│   └── nosql_repository.py   # Implements RepositoryServiceProtocol
├── validation/
│   └── default_validator.py  # Implements ValidationServiceProtocol
└── ...
```

**Adapters Layer (Unchanged):**

```
acb/adapters/
├── cache/
│   ├── _base.py              # CacheBase class with shared infrastructure
│   ├── redis.py              # Cache class extends CacheBase
│   └── memory.py             # Cache class extends CacheBase
├── messaging/
│   ├── _base.py              # PubSubBackend/QueueBackend Protocols (EXCEPTION)
│   ├── redis.py              # Implements both protocols
│   └── rabbitmq.py           # Implements both protocols
└── ...
```

### Registration Pattern

**Services (Protocol-Based):**

```python
# Register concrete implementation for Protocol
from acb.depends import depends
from acb.services.protocols import RepositoryServiceProtocol
from acb.services.repository.sql_repository import SqlRepositoryService

# Explicit registration
depends.set(RepositoryServiceProtocol, SqlRepositoryService())


# Usage injects via Protocol
@depends.inject
async def business_logic(repo: Inject[RepositoryServiceProtocol]):
    # repo is SqlRepositoryService, but injected via Protocol
    pass
```

**Adapters (Concrete Class):**

```python
# Adapters auto-register based on settings/adapters.yml
from acb.adapters import import_adapter

Cache = import_adapter("cache")  # Returns concrete class based on config


# Usage injects concrete class directly
@depends.inject
async def infrastructure_code(cache: Inject[Cache]):
    # cache is actual Redis/Memory implementation
    pass
```

### Testing Strategy

**Services:**

- Mock Protocol interfaces in unit tests
- Use lightweight mock implementations
- Test business logic in isolation

**Adapters:**

- Use real implementations in integration tests
- Mock external systems (Redis, PostgreSQL, S3, etc.)
- Test adapter infrastructure patterns

______________________________________________________________________

## Version Compatibility

- **ACB Version**: v0.20.0+
- **Python Version**: 3.13+ (required for modern Protocol support)
- **FastBlocks Compatibility**: v0.14.0+ (requires ACB v0.19.0+)

______________________________________________________________________

## References

### Related Documentation

- **Developer Guide**: `/Users/les/Projects/acb/CLAUDE.md` - Protocol vs Concrete Class DI section
- **Services Protocols**: `/Users/les/Projects/acb/acb/services/protocols.py` - Usage examples
- **Messaging Protocols**: `/Users/les/Projects/acb/acb/adapters/messaging/_base.py` - Exception case

### External Resources

- [PEP 544 - Protocols: Structural subtyping](https://peps.python.org/pep-0544/)
- [Python typing.Protocol Documentation](https://docs.python.org/3/library/typing.html#typing.Protocol)
- [ACB Adapter Pattern Documentation](https://github.com/lesleslie/acb)

______________________________________________________________________

## Decision Review

This ADR should be reviewed:

- When introducing new architectural layers
- When Python's type system evolves significantly
- After 12 months to assess practical impact
- If developer feedback indicates confusion or issues

**Next Review Date**: 2026-10-16
