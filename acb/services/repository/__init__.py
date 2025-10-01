"""Repository Layer for ACB Framework.

This module provides a comprehensive repository pattern implementation with:
- Repository base interface with CRUD operations
- Unit of Work pattern for transaction management
- Query Specification pattern for complex queries
- Entity caching strategies
- Multi-database coordination
- Integration with existing ACB database adapters

Phase 1 Component: Essential data access patterns for the ACB framework.
"""

from ._base import RepositoryBase, RepositoryError, RepositorySettings
from .cache import CachedRepository, RepositoryCacheSettings
from .coordinator import MultiDatabaseCoordinator
from .query_builder import QueryBuilder, QueryResult
from .registry import RepositoryRegistry
from .service import RepositoryService
from .specifications import (
    AndSpecification,
    NotSpecification,
    OrSpecification,
    Specification,
)
from .unit_of_work import UnitOfWork, UnitOfWorkManager

__all__ = [
    "AndSpecification",
    "CachedRepository",
    "MultiDatabaseCoordinator",
    "NotSpecification",
    "OrSpecification",
    "QueryBuilder",
    "QueryResult",
    "RepositoryBase",
    "RepositoryCacheSettings",
    "RepositoryError",
    "RepositoryRegistry",
    "RepositoryService",
    "RepositorySettings",
    "Specification",
    "UnitOfWork",
    "UnitOfWorkManager",
]
