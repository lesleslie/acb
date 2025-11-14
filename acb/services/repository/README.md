> **ACB Documentation**: [Main](../../../README.md) | [Services](../README.md) | [Repository Services](./README.md)

# ACB Services: Repository

The repository package delivers a full repository/unit-of-work stack for data
access patterns across SQL, NoSQL, and in-memory stores.

## Table of Contents

- [Overview](#overview)
- [Patterns & Building Blocks](#patterns--building-blocks)
- [Coordination & Caching](#coordination--caching)
- [Usage Patterns](#usage-patterns)
- [Best Practices](#best-practices)
- [Related Resources](#related-resources)

## Overview

Repository services decouple data access from domain logic by standardizing CRUD
interfaces, discovery, and lifecycle management. They integrate with adapters
for persistence and expose metrics, health checks, and DI-friendly registries.

## Patterns & Building Blocks

- `RepositoryBase`: Abstract base with CRUD signatures, cache hooks, and metrics tracking
- `RepositorySettings`: Centralizes pagination, timeouts, and cache defaults per repository
- `QueryBuilder` / `QueryResult`: Compose structured queries without leaking adapter-specific syntax
- `Specification`, `AndSpecification`, `OrSpecification`, `NotSpecification`: Build reusable filter logic
- `RepositoryRegistry`: Register repositories by entity type with singleton, scoped, or transient lifetimes
- `UnitOfWork` / `UnitOfWorkManager`: Manage transactional boundaries across multiple repositories
- `RepositoryService`: ServiceBase implementation that orchestrates registration, health, metrics, and background tasks

## Coordination & Caching

- `MultiDatabaseCoordinator` coordinates cross-database commits with pluggable strategies
- `RepositoryCacheSettings` and `CachedRepository` layer cache policies over repositories
- Health metrics capture cache hit rates, transaction success, and coordination status for observability
- Configuration overrides enable automatic repository registration and metrics polling

## Usage Patterns

```python
from dataclasses import dataclass
from typing import Any

from acb.services.repository import (
    RepositoryBase,
    RepositoryScope,
    RepositoryService,
    RepositoryServiceSettings,
    get_registry,
)


@dataclass
class Order:
    id: int
    status: str


class OrderRepository(RepositoryBase[Order, int]):
    def __init__(self) -> None:
        super().__init__(Order)
        self._store: dict[int, Order] = {}

    async def create(self, entity: Order) -> Order:
        self._store[entity.id] = entity
        return entity

    async def get_by_id(self, entity_id: int) -> Order | None:
        return self._store.get(entity_id)

    async def update(self, entity: Order) -> Order:
        self._store[entity.id] = entity
        return entity

    async def delete(self, entity_id: int) -> bool:
        return self._store.pop(entity_id, None) is not None

    async def list(
        self,
        filters: dict[str, Any] | None = None,
        sort: list[Any] | None = None,
        pagination: Any | None = None,
    ) -> list[Order]:
        return list(self._store.values())

    async def count(self, filters: dict[str, Any] | None = None) -> int:
        return len(self._store)


registry = get_registry()
registry.register(Order, OrderRepository, scope=RepositoryScope.SINGLETON)

service = RepositoryService(
    settings=RepositoryServiceSettings(auto_register_repositories=False),
)


async def main() -> None:
    async with service:
        async with service.uow_manager.transaction() as uow:
            orders = registry.get(Order)
            uow.add_repository("orders", orders)
            await orders.create(Order(id=1, status="pending"))
```

## Best Practices

- Register repositories during startup (or `initialize_services`) so discovery can resolve them by entity type
- Use `RepositoryScope.SCOPED` for request-bound repositories and `RepositoryScope.TRANSIENT` for cheap factories
- Combine `Specification` objects with `QueryBuilder` to express complex filters cleanly
- Capture transaction metrics from `UnitOfWorkManager.get_transaction_stats()` to watch for regressions

## Related Resources

- [Services Layer](../README.md)
- [Performance Services](../performance/README.md)
- [Validation Services](../validation/README.md)
- [Main Documentation](../../../README.md)
