"""Protocol interfaces for ACB Services layer.

This module defines Protocol-based interfaces for the reintroduced Services layer
in ACB v0.20.0+. Unlike adapters (which use base classes for shared implementation),
services use Protocols for clean, testable business logic interfaces.

## Architectural Decision: Why Protocols for Services?

ACB uses **two different dependency injection patterns** for different component types:

### Services → Protocol-Based DI (THIS MODULE)
**When to use**: Business logic, workflows, orchestration, application-specific code

**Benefits**:
- ✅ Pure interface contracts without implementation coupling
- ✅ Easy mocking for tests (no inheritance required)
- ✅ Better IDE autocomplete and type checking
- ✅ Multiple implementations without coupling
- ✅ Clear separation of concerns

**Example**:
```python
from acb.depends import Inject, depends
from acb.services.protocols import RepositoryServiceProtocol


@depends.inject
async def business_logic(repo: Inject[RepositoryServiceProtocol]):
    # Protocol-based DI for clean, testable code
    async with repo.unit_of_work() as uow:
        entity = await repo.get("id")
        await repo.save(entity, uow)
```

### Adapters → Concrete Class DI
**When to use**: External system integrations (databases, caches, storage, messaging)

**Benefits**:
- ✅ Share infrastructure code (cleanup, SSL config, connection pooling)
- ✅ Configuration-driven selection (settings/adapters.yml)
- ✅ Consistent resource lifecycle management

**Example**:
```python
from acb.depends import Inject, depends
from acb.adapters import import_adapter

Cache = import_adapter("cache")  # Concrete class


@depends.inject
async def infrastructure_code(cache: Inject[Cache]):
    # Concrete class DI for shared infrastructure
    await cache.set("key", "value")
```

## Services vs. Adapters Summary

| Aspect | Services (Protocols) | Adapters (Concrete Classes) |
|--------|---------------------|----------------------------|
| **Purpose** | Business logic | External integrations |
| **DI Pattern** | `Inject[ServiceProtocol]` | `Inject[ConcreteClass]` |
| **Implementation** | No base class required | Inherit from base class |
| **Testing** | Easy mocking (duck typing) | Use real impl or mock |
| **Example** | RepositoryServiceProtocol | Cache, Storage, Sql |

## Available Service Protocols

This module provides the following Protocol interfaces:

### 1. RepositoryServiceProtocol
Unit of Work pattern for transactional data access.
Use for: Database operations, entity persistence, transactional workflows

### 2. ValidationServiceProtocol
Input validation with security features.
Use for: User input validation, business rule checking, XSS prevention

### 3. PerformanceServiceProtocol
Performance optimization and monitoring.
Use for: Performance budgets, metrics collection, optimization

### 4. EventServiceProtocol
Event-driven architecture support.
Use for: Event publishing, subscription, handler management

### 5. WorkflowServiceProtocol
Workflow orchestration capabilities.
Use for: Multi-step processes, state machines, workflow management

## Usage Examples

### Example 1: Repository Service with Unit of Work

```python
from acb.depends import Inject, depends
from acb.services.protocols import RepositoryServiceProtocol

@depends.inject
async def update_user_profile(
    user_id: str,
    profile_data: dict,
    repo: Inject[RepositoryServiceProtocol]
):
    \"\"\"Update user profile within a transaction.\"\"\"
    async with repo.unit_of_work() as uow:
        # Get entity
        user = await repo.get(user_id)
        if not user:
            raise ValueError(f"User {user_id} not found")

        # Update entity
        user.update_profile(profile_data)

        # Save within transaction
        await repo.save(user, uow)

        # Commit happens automatically on context exit
```

### Example 2: Validation Service

```python
from acb.depends import Inject, depends
from acb.services.protocols import ValidationServiceProtocol

@depends.inject
async def register_user(
    user_data: dict,
    validator: Inject[ValidationServiceProtocol]
):
    \"\"\"Register new user with validation.\"\"\"
    # Validate input
    result = await validator.validate_input(
        user_data,
        rules=["email", "password", "username"]
    )

    if not result["is_valid"]:
        raise ValueError(f"Validation failed: {result['errors']}")

    # Sanitize for security
    clean_data = await validator.sanitize_input(
        user_data,
        allowed_fields=["email", "password", "username"]
    )

    # Proceed with registration
    return clean_data
```

### Example 3: Combining Multiple Service Protocols

```python
from acb.depends import Inject, depends
from acb.services.protocols import (
    RepositoryServiceProtocol,
    ValidationServiceProtocol,
    EventServiceProtocol
)

@depends.inject
async def create_order(
    order_data: dict,
    repo: Inject[RepositoryServiceProtocol],
    validator: Inject[ValidationServiceProtocol],
    events: Inject[EventServiceProtocol]
):
    \"\"\"Create order with validation, persistence, and events.\"\"\"

    # 1. Validate
    result = await validator.validate_input(order_data)
    if not result["is_valid"]:
        raise ValueError("Invalid order data")

    # 2. Persist
    async with repo.unit_of_work() as uow:
        order = Order(**order_data)
        await repo.save(order, uow)

    # 3. Publish event
    await events.publish({
        "event_id": uuid4(),
        "event_type": "order.created",
        "payload": {"order_id": str(order.id)},
        "timestamp": datetime.utcnow(),
        "source": "order-service",
        "correlation_id": None
    })

    return order
```

### Example 4: Mixing Services (Protocols) with Adapters (Concrete Classes)

```python
from acb.depends import Inject, depends
from acb.adapters import import_adapter
from acb.services.protocols import RepositoryServiceProtocol, ValidationServiceProtocol

# Adapters use concrete classes
Cache = import_adapter("cache")
Storage = import_adapter("storage")

@depends.inject
async def process_document(
    doc_id: str,
    # Services use Protocols
    repo: Inject[RepositoryServiceProtocol],
    validator: Inject[ValidationServiceProtocol],
    # Adapters use concrete classes
    cache: Inject[Cache],
    storage: Inject[Storage]
):
    \"\"\"Process document using both services and adapters.\"\"\"

    # Check cache (adapter)
    cached = await cache.get(f"doc:{doc_id}")
    if cached:
        return cached

    # Get from repository (service)
    doc = await repo.get(doc_id)

    # Validate (service)
    result = await validator.validate_business_rules(doc)
    if not result["is_valid"]:
        raise ValueError("Document validation failed")

    # Store in cloud storage (adapter)
    await storage.upload(f"documents/{doc_id}.json", doc.to_json())

    # Cache result (adapter)
    await cache.set(f"doc:{doc_id}", doc, ttl=3600)

    return doc
```

## Testing with Protocols

Protocols make testing incredibly easy—no inheritance required!

```python
import pytest
from acb.depends import depends
from acb.services.protocols import RepositoryServiceProtocol, ValidationServiceProtocol


# Mock repository - just implement the protocol interface
class MockRepository:
    def __init__(self):
        self.entities = {}

    async def get(self, entity_id):
        return self.entities.get(entity_id)

    async def save(self, entity, uow=None):
        self.entities[entity.id] = entity

    async def delete(self, entity_id, uow=None):
        return self.entities.pop(entity_id, None) is not None

    async def find(self, filters, limit=100, offset=0):
        return list(self.entities.values())

    async def count(self, filters=None):
        return len(self.entities)

    def unit_of_work(self):
        return MockUnitOfWork()


# Mock works because it matches the Protocol structure!
@pytest.fixture
def mock_repo():
    repo = MockRepository()
    depends.set(RepositoryServiceProtocol, repo)
    return repo


async def test_my_function(mock_repo):
    # Function receives MockRepository via DI
    result = await my_function()
    assert result is not None
```

## Implementation Guidelines

When implementing these protocols:

1. **Create a concrete class** that implements the protocol:
   ```python
   from acb.services.protocols import RepositoryServiceProtocol


   class SqlRepository:  # No inheritance needed!
       async def get(self, entity_id):
           # Implementation
           pass

       # ... implement other protocol methods
   ```

2. **Register with dependency injection**:
   ```python
   from acb.depends import depends

   repo = SqlRepository()
   depends.set(RepositoryServiceProtocol, repo)
   ```

3. **Consumers use the Protocol, not the concrete class**:
   ```python
   @depends.inject
   async def consumer(repo: Inject[RepositoryServiceProtocol]):
       # Works with any implementation
       pass
   ```

## Version Compatibility

- **v0.20.0+**: Protocol-based DI for services
- **v0.19.x**: Concrete classes work but Protocols recommended
- **Migration**: Existing code continues to work; gradually migrate to Protocols

## See Also

- `CLAUDE.md` - Complete architectural guidance
- `docs/ARCHITECTURE-DECISION-PROTOCOL-DI.md` - Detailed rationale
- `acb/services/` - Concrete implementations
- `acb/adapters/` - Adapter pattern examples

Author: ACB Team
Created: 2025-10-16
Version: 1.0.0
"""

from collections.abc import AsyncGenerator
from enum import Enum
from uuid import UUID

import typing as t
from contextlib import AbstractAsyncContextManager as AsyncContextManager
from datetime import datetime
from typing import Protocol

# Re-export for convenience
__all__ = [
    "EntityProtocol",
    "Event",
    "EventHandler",
    # Events
    "EventServiceProtocol",
    "PerformanceBudget",
    "PerformanceMetrics",
    # Performance
    "PerformanceServiceProtocol",
    # Repository
    "RepositoryServiceProtocol",
    "UnitOfWork",
    "ValidationResult",
    "ValidationRule",
    # Validation
    "ValidationServiceProtocol",
    "ValidationSeverity",
    # Workflow
    "WorkflowServiceProtocol",
    "WorkflowState",
    "WorkflowTransition",
]


# ============================================================================
# Enums and Common Types
# ============================================================================


class ValidationSeverity(Enum):
    """Severity levels for validation results."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class WorkflowState(Enum):
    """Standard workflow states."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


# ============================================================================
# Data Models (Structural Types, not tied to implementation)
# ============================================================================


class ValidationResult(t.TypedDict):
    """Validation result structure."""

    is_valid: bool
    errors: list[dict[str, t.Any]]
    warnings: list[dict[str, t.Any]]
    severity: ValidationSeverity
    timestamp: datetime


class ValidationRule(t.TypedDict):
    """Validation rule structure."""

    name: str
    description: str
    severity: ValidationSeverity
    enabled: bool


class PerformanceMetrics(t.TypedDict):
    """Performance metrics structure."""

    response_time_ms: float
    memory_usage_mb: float
    cpu_percent: float
    active_connections: int
    timestamp: datetime


class PerformanceBudget(t.TypedDict):
    """Performance budget constraints."""

    max_response_time_ms: float
    max_memory_mb: float
    max_cpu_percent: float
    max_connections: int


class Event(t.TypedDict):
    """Event structure for event-driven services."""

    event_id: UUID
    event_type: str
    payload: dict[str, t.Any]
    timestamp: datetime
    source: str
    correlation_id: str | None


class WorkflowTransition(t.TypedDict):
    """Workflow state transition."""

    from_state: WorkflowState
    to_state: WorkflowState
    timestamp: datetime
    reason: str | None


# ============================================================================
# Protocol: Repository Service (Unit of Work Pattern)
# ============================================================================


class UnitOfWork(Protocol):
    """Unit of Work protocol for transactional operations."""

    async def commit(self) -> None:
        """Commit the transaction."""
        ...

    async def rollback(self) -> None:
        """Rollback the transaction."""
        ...

    async def __aenter__(self) -> "UnitOfWork":
        """Enter async context."""
        ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: t.Any,
    ) -> None:
        """Exit async context."""
        ...


class EntityProtocol(Protocol):
    """Protocol for domain entities."""

    id: str | UUID
    created_at: datetime
    updated_at: datetime


class RepositoryServiceProtocol(Protocol):
    """Protocol for repository services with Unit of Work pattern.

    Provides transactional data access with clean abstractions over
    persistence mechanisms. Implementations can use SQL, NoSQL, or
    any other storage backend.

    Example:
        ```python
        @depends.inject
        async def update_user(
            user_id: str, data: dict, repo: Inject[RepositoryServiceProtocol]
        ):
            async with repo.unit_of_work() as uow:
                user = await repo.get(user_id)
                user.update(data)
                await repo.save(user, uow)
        ```
    """

    def unit_of_work(self) -> AsyncContextManager[UnitOfWork]:
        """Create a new unit of work (transaction).

        Returns:
            Async context manager for transaction
        """
        ...

    async def get(self, entity_id: str | UUID) -> EntityProtocol | None:
        """Get entity by ID.

        Args:
            entity_id: Entity identifier

        Returns:
            Entity if found, None otherwise
        """
        ...

    async def save(
        self,
        entity: EntityProtocol,
        uow: UnitOfWork | None = None,
    ) -> None:
        """Save entity (create or update).

        Args:
            entity: Entity to save
            uow: Optional unit of work for transaction
        """
        ...

    async def delete(
        self,
        entity_id: str | UUID,
        uow: UnitOfWork | None = None,
    ) -> bool:
        """Delete entity by ID.

        Args:
            entity_id: Entity identifier
            uow: Optional unit of work for transaction

        Returns:
            True if deleted, False if not found
        """
        ...

    async def find(
        self,
        filters: dict[str, t.Any],
        limit: int = 100,
        offset: int = 0,
    ) -> list[EntityProtocol]:
        """Find entities matching filters.

        Args:
            filters: Filter criteria
            limit: Maximum results
            offset: Results offset

        Returns:
            List of matching entities
        """
        ...

    async def count(self, filters: dict[str, t.Any] | None = None) -> int:
        """Count entities matching filters.

        Args:
            filters: Optional filter criteria

        Returns:
            Count of matching entities
        """
        ...


# ============================================================================
# Protocol: Validation Service (Security + Validation)
# ============================================================================


class ValidationServiceProtocol(Protocol):
    """Protocol for validation services with security features.

    Provides input validation, business rule checking, and security
    validation (XSS, SQL injection, etc.). Supports custom validation
    rules and severity levels.

    Example:
        ```python
        @depends.inject
        async def create_user(data: dict, validator: Inject[ValidationServiceProtocol]):
            result = await validator.validate_input(data, rules=["email", "password"])
            if not result["is_valid"]:
                raise ValidationError(result["errors"])
        ```
    """

    async def validate_input(
        self,
        data: dict[str, t.Any],
        rules: list[str] | None = None,
        strict: bool = True,
    ) -> ValidationResult:
        """Validate input data against rules.

        Args:
            data: Input data to validate
            rules: Specific rules to apply (None = all rules)
            strict: Whether to fail on warnings

        Returns:
            Validation result with errors/warnings
        """
        ...

    async def validate_business_rules(
        self,
        entity: EntityProtocol,
        context: dict[str, t.Any] | None = None,
    ) -> ValidationResult:
        """Validate business rules for entity.

        Args:
            entity: Entity to validate
            context: Optional validation context

        Returns:
            Validation result
        """
        ...

    async def sanitize_input(
        self,
        data: dict[str, t.Any],
        allowed_fields: list[str] | None = None,
    ) -> dict[str, t.Any]:
        """Sanitize user input (XSS, injection prevention).

        Args:
            data: Input data to sanitize
            allowed_fields: Whitelist of allowed fields

        Returns:
            Sanitized data
        """
        ...

    async def add_rule(
        self,
        rule: ValidationRule,
    ) -> None:
        """Add custom validation rule.

        Args:
            rule: Validation rule to add
        """
        ...

    async def remove_rule(self, rule_name: str) -> bool:
        """Remove validation rule.

        Args:
            rule_name: Name of rule to remove

        Returns:
            True if removed, False if not found
        """
        ...


# ============================================================================
# Protocol: Performance Service (Optimization + Monitoring)
# ============================================================================


class PerformanceServiceProtocol(Protocol):
    """Protocol for performance optimization services.

    Provides performance monitoring, optimization suggestions, and
    performance budget enforcement.

    Example:
        ```python
        @depends.inject
        async def monitor_request(perf: Inject[PerformanceServiceProtocol]):
            async with perf.measure("api_request"):
                # Perform operation
                pass

            metrics = await perf.get_metrics()
            if not await perf.check_budget(metrics):
                # Performance budget exceeded
                await perf.optimize()
        ```
    """

    async def measure(
        self,
        operation_name: str,
    ) -> AsyncContextManager[None]:
        """Measure operation performance.

        Args:
            operation_name: Name of operation to measure

        Returns:
            Async context manager for measurement
        """
        ...

    async def get_metrics(
        self,
        operation_name: str | None = None,
    ) -> PerformanceMetrics:
        """Get performance metrics.

        Args:
            operation_name: Optional specific operation

        Returns:
            Performance metrics
        """
        ...

    async def check_budget(
        self,
        metrics: PerformanceMetrics,
        budget: PerformanceBudget | None = None,
    ) -> bool:
        """Check if metrics meet performance budget.

        Args:
            metrics: Current metrics
            budget: Performance budget (None = use default)

        Returns:
            True if within budget, False otherwise
        """
        ...

    async def optimize(
        self,
        target: str | None = None,
    ) -> dict[str, t.Any]:
        """Optimize performance for target.

        Args:
            target: Specific optimization target

        Returns:
            Optimization results
        """
        ...


# ============================================================================
# Protocol: Event Service (Event-Driven Architecture)
# ============================================================================


class EventHandler(Protocol):
    """Protocol for event handlers."""

    async def handle(self, event: Event) -> None:
        """Handle an event.

        Args:
            event: Event to handle
        """
        ...


class EventServiceProtocol(Protocol):
    """Protocol for event-driven services.

    Provides event publishing, subscription, and handler management
    for event-driven architectures.

    Example:
        ```python
        @depends.inject
        async def publish_user_created(
            user_id: str, events: Inject[EventServiceProtocol]
        ):
            event = {
                "event_id": uuid4(),
                "event_type": "user.created",
                "payload": {"user_id": user_id},
                "timestamp": datetime.utcnow(),
                "source": "user-service",
                "correlation_id": None,
            }
            await events.publish(event)
        ```
    """

    async def publish(
        self,
        event: Event,
    ) -> None:
        """Publish an event.

        Args:
            event: Event to publish
        """
        ...

    async def subscribe(
        self,
        event_type: str,
        handler: EventHandler,
    ) -> UUID:
        """Subscribe to events of a specific type.

        Args:
            event_type: Type of events to subscribe to
            handler: Handler for events

        Returns:
            Subscription ID
        """
        ...

    async def unsubscribe(
        self,
        subscription_id: UUID,
    ) -> bool:
        """Unsubscribe from events.

        Args:
            subscription_id: Subscription to cancel

        Returns:
            True if unsubscribed, False if not found
        """
        ...

    async def get_events(
        self,
        event_type: str | None = None,
        since: datetime | None = None,
        limit: int = 100,
    ) -> AsyncGenerator[Event]:
        """Get historical events.

        Args:
            event_type: Optional event type filter
            since: Optional time filter
            limit: Maximum events to return

        Yields:
            Historical events
        """
        raise NotImplementedError  # pragma: no cover


# ============================================================================
# Protocol: Workflow Service (Orchestration)
# ============================================================================


class WorkflowServiceProtocol(Protocol):
    """Protocol for workflow orchestration services.

    Provides workflow state management, transition handling, and
    orchestration of complex multi-step processes.

    Example:
        ```python
        @depends.inject
        async def process_order(
            order_id: str, workflow: Inject[WorkflowServiceProtocol]
        ):
            # Start workflow
            await workflow.start(order_id, "order_processing")

            # Execute transitions
            await workflow.transition(order_id, WorkflowState.IN_PROGRESS)

            # Check current state
            state = await workflow.get_state(order_id)
        ```
    """

    async def start(
        self,
        workflow_id: str | UUID,
        workflow_type: str,
        initial_data: dict[str, t.Any] | None = None,
    ) -> WorkflowState:
        """Start a new workflow.

        Args:
            workflow_id: Unique workflow identifier
            workflow_type: Type of workflow
            initial_data: Optional initial workflow data

        Returns:
            Initial workflow state
        """
        ...

    async def transition(
        self,
        workflow_id: str | UUID,
        to_state: WorkflowState,
        reason: str | None = None,
    ) -> WorkflowTransition:
        """Transition workflow to new state.

        Args:
            workflow_id: Workflow identifier
            to_state: Target state
            reason: Optional reason for transition

        Returns:
            Transition details
        """
        ...

    async def get_state(
        self,
        workflow_id: str | UUID,
    ) -> WorkflowState:
        """Get current workflow state.

        Args:
            workflow_id: Workflow identifier

        Returns:
            Current state
        """
        ...

    async def get_history(
        self,
        workflow_id: str | UUID,
    ) -> list[WorkflowTransition]:
        """Get workflow transition history.

        Args:
            workflow_id: Workflow identifier

        Returns:
            List of transitions in chronological order
        """
        ...

    async def cancel(
        self,
        workflow_id: str | UUID,
        reason: str | None = None,
    ) -> bool:
        """Cancel a workflow.

        Args:
            workflow_id: Workflow identifier
            reason: Optional cancellation reason

        Returns:
            True if cancelled, False if not found
        """
        ...
