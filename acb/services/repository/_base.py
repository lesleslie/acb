"""Repository Base Classes and Interface.

Provides foundational repository pattern implementation with:
- Generic repository interface for CRUD operations
- Base settings and configuration
- Error handling for repository operations
- Integration with ACB dependency injection
"""

import builtins
from abc import ABC, abstractmethod
from enum import Enum

import typing as t
from dataclasses import dataclass
from pydantic import Field, field_validator
from typing import Any, TypeVar

from acb.cleanup import CleanupMixin
from acb.config import Settings
from acb.depends import depends

# Type variables for generic repository
EntityType = TypeVar("EntityType")
IDType = TypeVar("IDType")


class RepositoryError(Exception):
    """Base exception for repository operations."""

    def __init__(
        self,
        message: str,
        entity_type: str | None = None,
        operation: str | None = None,
    ) -> None:
        self.entity_type = entity_type
        self.operation = operation
        super().__init__(message)


class EntityNotFoundError(RepositoryError):
    """Raised when an entity is not found."""

    def __init__(self, entity_type: str, entity_id: Any) -> None:
        super().__init__(
            f"{entity_type} with ID {entity_id} not found",
            entity_type=entity_type,
            operation="find",
        )
        self.entity_id = entity_id


class DuplicateEntityError(RepositoryError):
    """Raised when trying to create a duplicate entity."""

    def __init__(self, entity_type: str, conflict_field: str, value: Any) -> None:
        super().__init__(
            f"{entity_type} with {conflict_field}={value} already exists",
            entity_type=entity_type,
            operation="create",
        )
        self.conflict_field = conflict_field
        self.value = value


class SortDirection(Enum):
    """Sort direction enumeration."""

    ASC = "asc"
    DESC = "desc"


@dataclass
class SortCriteria:
    """Sort criteria specification."""

    field: str
    direction: SortDirection = SortDirection.ASC


@dataclass
class PaginationInfo:
    """Pagination information."""

    page: int = 1
    page_size: int = 50
    total_items: int | None = None
    total_pages: int | None = None

    def __post_init__(self) -> None:
        if self.total_items is not None and self.total_pages is None:
            self.total_pages = (self.total_items + self.page_size - 1) // self.page_size

    @property
    def offset(self) -> int:
        """Calculate offset for database queries."""
        return (self.page - 1) * self.page_size

    @property
    def has_next(self) -> bool:
        """Check if there's a next page."""
        return self.total_pages is not None and self.page < self.total_pages

    @property
    def has_previous(self) -> bool:
        """Check if there's a previous page."""
        return self.page > 1


class RepositorySettings(Settings):
    """Repository configuration settings."""

    # Caching settings
    cache_enabled: bool = True
    cache_ttl: int = Field(default=300, description="Cache TTL in seconds")
    cache_prefix: str = Field(default="repo", description="Cache key prefix")

    # Query settings
    default_page_size: int = Field(default=50, ge=1, le=1000)
    max_page_size: int = Field(default=1000, ge=1)
    query_timeout: float = Field(default=30.0, description="Query timeout in seconds")

    # Transaction settings
    transaction_timeout: float = Field(
        default=60.0,
        description="Transaction timeout in seconds",
    )
    isolation_level: str = Field(
        default="READ_COMMITTED",
        description="Default isolation level",
    )

    # Performance settings
    batch_size: int = Field(default=100, ge=1, le=10000)
    connection_pool_size: int = Field(default=10, ge=1, le=100)

    @field_validator("default_page_size")
    @classmethod
    def validate_page_size(cls, v: int, info: t.Any) -> int:
        values: Any = info.data if hasattr(info, "data") else {}
        if "max_page_size" in values and v > values["max_page_size"]:
            msg = "default_page_size cannot exceed max_page_size"
            raise ValueError(msg)
        return v


class RepositoryProtocol(t.Protocol[EntityType, IDType]):  # type: ignore[misc]
    """Protocol defining repository interface."""

    async def create(self, entity: EntityType) -> EntityType:
        """Create a new entity."""
        ...

    async def get_by_id(self, entity_id: IDType) -> EntityType | None:
        """Get entity by ID."""
        ...

    async def update(self, entity: EntityType) -> EntityType:
        """Update an existing entity."""
        ...

    async def delete(self, entity_id: IDType) -> bool:
        """Delete entity by ID."""
        ...

    async def list(
        self,
        filters: dict[str, Any] | None = None,
        sort: list[SortCriteria] | None = None,
        pagination: PaginationInfo | None = None,
    ) -> list[EntityType]:
        """List entities with filtering, sorting, and pagination."""
        ...

    async def count(self, filters: dict[str, Any] | None = None) -> int:
        """Count entities matching filters."""
        ...

    async def exists(self, entity_id: IDType) -> bool:
        """Check if entity exists."""
        ...


class RepositoryBase[EntityType, IDType](CleanupMixin, ABC):
    """Abstract base class for repositories.

    Provides common functionality for all repository implementations:
    - CRUD operations interface
    - Error handling and logging
    - Caching integration
    - Performance monitoring
    - Resource cleanup
    """

    def __init__(
        self,
        entity_type: type[EntityType],
        settings: RepositorySettings | None = None,
    ) -> None:
        super().__init__()
        self.entity_type = entity_type
        self.entity_name = getattr(entity_type, "__name__", str(entity_type))
        self.settings = settings or depends.get_sync(RepositorySettings)
        self._cache = None
        self._metrics: dict[str, t.Any] = {}

    async def _async_init(self) -> None:
        """Async initialization of repository dependencies."""
        if self._cache is None:
            from acb.adapters import import_adapter

            Cache = import_adapter("cache")
            self._cache = await depends.get(Cache)

    @property
    def cache_key_prefix(self) -> str:
        """Get cache key prefix for this repository."""
        return f"{self.settings.cache_prefix}:{self.entity_name.lower()}"

    def _build_cache_key(self, key: str) -> str:
        """Build cache key with proper prefix."""
        return f"{self.cache_key_prefix}:{key}"

    async def _get_cache(self) -> None:
        """Get cache adapter if enabled."""
        if self.settings.cache_enabled and self._cache is None:
            try:
                from acb.adapters import import_adapter

                Cache = import_adapter("cache")
                self._cache = await depends.get(Cache)
            except ImportError:
                self.settings.cache_enabled = False
        return self._cache

    async def _increment_metric(self, operation: str, success: bool = True) -> None:
        """Track operation metrics."""
        metric_key = f"{operation}_{'success' if success else 'error'}"
        self._metrics[metric_key] = self._metrics.get(metric_key, 0) + 1

    async def _handle_error(self, error: Exception, operation: str) -> None:
        """Handle repository errors with proper logging and metrics."""
        await self._increment_metric(operation, success=False)

        if isinstance(error, RepositoryError):
            raise

        # Wrap other exceptions in RepositoryError
        msg = f"Repository operation failed: {error}"
        raise RepositoryError(
            msg,
            entity_type=self.entity_name,
            operation=operation,
        ) from error

    @abstractmethod
    async def create(self, entity: EntityType) -> EntityType:
        """Create a new entity.

        Args:
            entity: Entity to create

        Returns:
            Created entity with any generated fields

        Raises:
            DuplicateEntityError: If entity already exists
            RepositoryError: For other creation failures
        """

    @abstractmethod
    async def get_by_id(self, entity_id: IDType) -> EntityType | None:
        """Get entity by ID.

        Args:
            entity_id: Unique identifier for the entity

        Returns:
            Entity if found, None otherwise
        """

    async def get_by_id_or_raise(self, entity_id: IDType) -> EntityType:
        """Get entity by ID, raise if not found.

        Args:
            entity_id: Unique identifier for the entity

        Returns:
            Entity if found

        Raises:
            EntityNotFoundError: If entity not found
        """
        entity = await self.get_by_id(entity_id)
        if entity is None:
            raise EntityNotFoundError(self.entity_name, entity_id)
        return entity

    @abstractmethod
    async def update(self, entity: EntityType) -> EntityType:
        """Update an existing entity.

        Args:
            entity: Entity to update

        Returns:
            Updated entity

        Raises:
            EntityNotFoundError: If entity doesn't exist
            RepositoryError: For other update failures
        """

    @abstractmethod
    async def delete(self, entity_id: IDType) -> bool:
        """Delete entity by ID.

        Args:
            entity_id: Unique identifier for the entity

        Returns:
            True if entity was deleted, False if not found
        """

    async def delete_or_raise(self, entity_id: IDType) -> None:
        """Delete entity by ID, raise if not found.

        Args:
            entity_id: Unique identifier for the entity

        Raises:
            EntityNotFoundError: If entity not found
        """
        deleted = await self.delete(entity_id)
        if not deleted:
            raise EntityNotFoundError(self.entity_name, entity_id)

    @abstractmethod
    async def list(
        self,
        filters: dict[str, Any] | None = None,
        sort: list[SortCriteria] | None = None,
        pagination: PaginationInfo | None = None,
    ) -> list[EntityType]:
        """List entities with filtering, sorting, and pagination.

        Args:
            filters: Dictionary of field filters
            sort: List of sort criteria
            pagination: Pagination information

        Returns:
            List of entities matching criteria
        """

    @abstractmethod
    async def count(self, filters: dict[str, Any] | None = None) -> int:
        """Count entities matching filters.

        Args:
            filters: Dictionary of field filters

        Returns:
            Number of matching entities
        """

    async def exists(self, entity_id: IDType) -> bool:
        """Check if entity exists.

        Args:
            entity_id: Unique identifier for the entity

        Returns:
            True if entity exists, False otherwise
        """
        entity = await self.get_by_id(entity_id)
        return entity is not None

    async def list_paginated(
        self,
        filters: dict[str, Any] | None = None,
        sort: builtins.list[SortCriteria] | None = None,
        page: int = 1,
        page_size: int | None = None,
    ) -> tuple[builtins.list[EntityType], PaginationInfo]:
        """List entities with pagination information.

        Args:
            filters: Dictionary of field filters
            sort: List of sort criteria
            page: Page number (1-based)
            page_size: Items per page

        Returns:
            Tuple of (entities, pagination_info)
        """
        if page_size is None:
            page_size = self.settings.default_page_size

        page_size = min(page_size, self.settings.max_page_size)

        # Get total count
        total_items = await self.count(filters)

        # Create pagination info
        pagination = PaginationInfo(
            page=page,
            page_size=page_size,
            total_items=total_items,
        )

        # Get entities for current page
        entities = await self.list(filters, sort, pagination)

        return entities, pagination

    async def batch_create(
        self,
        entities: builtins.list[EntityType],
    ) -> builtins.list[EntityType]:
        """Create multiple entities in batch.

        Args:
            entities: List of entities to create

        Returns:
            List of created entities
        """
        return [await self.create(entity) for entity in entities]

    async def batch_update(
        self,
        entities: builtins.list[EntityType],
    ) -> builtins.list[EntityType]:
        """Update multiple entities in batch.

        Args:
            entities: List of entities to update

        Returns:
            List of updated entities
        """
        return [await self.update(entity) for entity in entities]

    async def batch_delete(self, entity_ids: builtins.list[IDType]) -> int:
        """Delete multiple entities by ID.

        Args:
            entity_ids: List of entity IDs to delete

        Returns:
            Number of entities deleted
        """
        deleted_count = 0
        for entity_id in entity_ids:
            if await self.delete(entity_id):
                deleted_count += 1
        return deleted_count

    async def get_metrics(self) -> dict[str, Any]:
        """Get repository performance metrics.

        Returns:
            Dictionary of metrics
        """
        return {
            "entity_type": self.entity_name,
            "cache_enabled": self.settings.cache_enabled,
            "operations": self._metrics.copy(),
            "settings": {
                "default_page_size": self.settings.default_page_size,
                "max_page_size": self.settings.max_page_size,
                "cache_ttl": self.settings.cache_ttl,
            },
        }

    async def _cleanup_resources(self) -> None:
        """Clean up repository resources."""
        self._metrics.clear()
        self._cache = None
