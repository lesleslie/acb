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
from .unit_of_work import UnitOfWork, UnitOfWorkManager
from .specifications import Specification, AndSpecification, OrSpecification, NotSpecification
from .registry import RepositoryRegistry
from .cache import CachedRepository, RepositoryCacheSettings
from .query_builder import QueryBuilder, QueryResult
from .coordinator import MultiDatabaseCoordinator
from .service import RepositoryService

__all__ = [
    "RepositoryBase",
    "RepositoryError",
    "RepositorySettings",
    "UnitOfWork",
    "UnitOfWorkManager",
    "Specification",
    "AndSpecification",
    "OrSpecification",
    "NotSpecification",
    "RepositoryRegistry",
    "CachedRepository",
    "RepositoryCacheSettings",
    "QueryBuilder",
    "QueryResult",
    "MultiDatabaseCoordinator",
    "RepositoryService",
]