"""Query interface registry and base adapters for ACB.

This module provides the foundation for database-agnostic query operations,
allowing different database backends (SQL, NoSQL) to be used with different
model frameworks (Pydantic, SQLModel, etc.) through a unified interface.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from typing import Any, TypeVar

T = TypeVar("T")


class DatabaseAdapter[T](ABC):
    """Abstract base class for database adapters.

    Database adapters provide the low-level database operations
    for a specific database backend (SQL, NoSQL, etc.).
    """

    @abstractmethod
    async def create(self, model: type[T], data: dict[str, Any]) -> T:
        """Create a new record in the database.

        Args:
            model: The model class to create
            data: Dictionary of field values

        Returns:
            The created model instance
        """
        ...

    @abstractmethod
    async def update(
        self,
        model: type[T],
        filters: dict[str, Any],
        data: dict[str, Any],
    ) -> T | None:
        """Update records matching filters.

        Args:
            model: The model class to update
            filters: Field filters to match records
            data: Dictionary of values to update

        Returns:
            Updated model instance or None if not found
        """
        ...

    @abstractmethod
    async def find(
        self,
        model: type[T],
        **filters: Any,
    ) -> T | None:
        """Find a single record by filters.

        Args:
            model: The model class to query
            **filters: Field filters (e.g., id=1, name="John")

        Returns:
            Model instance or None if not found
        """
        ...

    @abstractmethod
    async def all(
        self,
        model: type[T],
        order_by: str | None = None,
        limit: int | None = None,
        desc: bool = False,
    ) -> list[T]:
        """Get all records, optionally ordered and limited.

        Args:
            model: The model class to query
            order_by: Field name to order by
            limit: Maximum number of records
            desc: Sort in descending order

        Returns:
            List of model instances
        """
        ...

    @abstractmethod
    async def delete(
        self,
        model: type[T],
        **filters: Any,
    ) -> bool:
        """Delete records matching filters.

        Args:
            model: The model class
            **filters: Field filters to match records

        Returns:
            True if any records were deleted
        """
        ...

    async def create_or_update(
        self,
        model: type[T],
        data: dict[str, Any],
        key_field: str,
    ) -> T:
        """Create a new record or update if it exists (upsert).

        Args:
            model: The model class
            data: Dictionary of field values
            key_field: Field name to use as unique key

        Returns:
            Created or updated model instance
        """
        key_value = data.get(key_field)
        if key_value is None:
            # No key value, just create
            return await self.create(model, data)

        # Try to find existing
        existing = await self.find(model, **{key_field: key_value})
        if existing:
            # Update existing
            return await self.update(model, {key_field: key_value}, data) or existing
        # Create new
        return await self.create(model, data)


class ModelAdapter[T](ABC):
    """Abstract base class for model adapters.

    Model adapters handle model-specific serialization/deserialization
    for different model frameworks (Pydantic, SQLModel, etc.).
    """

    @abstractmethod
    def from_dict(self, model: type[T], data: dict[str, Any]) -> T:
        """Create a model instance from a dictionary.

        Args:
            model: The model class
            data: Dictionary of field values

        Returns:
            Model instance
        """
        ...

    @abstractmethod
    def to_dict(self, instance: T) -> dict[str, Any]:
        """Convert a model instance to a dictionary.

        Args:
            instance: The model instance

        Returns:
            Dictionary of field values
        """
        ...

    @abstractmethod
    def update_from_dict(self, instance: T, data: dict[str, Any]) -> None:
        """Update a model instance from a dictionary in-place.

        Args:
            instance: The model instance to update
            data: Dictionary of field values to update
        """
        ...


class QueryRegistry:
    """Registry for database and model adapters.

    This singleton registry allows different parts of the application
    to register and retrieve database and model adapters by name.
    """

    def __init__(self) -> None:
        self._database_adapters: dict[str, DatabaseAdapter[Any]] = {}
        self._model_adapters: dict[str, ModelAdapter[Any]] = {}

    def register_database_adapter(
        self,
        name: str,
        adapter: DatabaseAdapter[Any],
    ) -> None:
        """Register a database adapter.

        Args:
            name: Adapter name (e.g., "sql", "nosql")
            adapter: The database adapter instance
        """
        self._database_adapters[name] = adapter

    def register_model_adapter(
        self,
        name: str,
        adapter: ModelAdapter[Any],
    ) -> None:
        """Register a model adapter.

        Args:
            name: Adapter name (e.g., "pydantic", "sqlmodel")
            adapter: The model adapter instance
        """
        self._model_adapters[name] = adapter

    def get_database_adapter(self, name: str) -> DatabaseAdapter[Any]:
        """Get a registered database adapter.

        Args:
            name: Adapter name

        Returns:
            The database adapter

        Raises:
            KeyError: If adapter not found
        """
        if name not in self._database_adapters:
            raise KeyError(
                f"Database adapter '{name}' not registered. "
                f"Available: {list(self._database_adapters.keys())}"
            )
        return self._database_adapters[name]

    def get_model_adapter(self, name: str) -> ModelAdapter[Any]:
        """Get a registered model adapter.

        Args:
            name: Adapter name

        Returns:
            The model adapter

        Raises:
            KeyError: If adapter not found
        """
        if name not in self._model_adapters:
            raise KeyError(
                f"Model adapter '{name}' not registered. "
                f"Available: {list(self._model_adapters.keys())}"
            )
        return self._model_adapters[name]


# Global registry instance
registry = QueryRegistry()
