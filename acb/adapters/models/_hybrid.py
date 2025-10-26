"""Hybrid query interface for ACB.

This module provides the unified ACBQuery interface that combines
database adapters with model adapters to provide a clean, type-safe
API for database operations.
"""

from __future__ import annotations

from typing import Any, TypeVar

from acb.adapters.models._query import registry

T = TypeVar("T")


class SimpleOperations:
    """Simple CRUD operations for a model."""

    def __init__(
        self,
        model: type[T],
        db_adapter_name: str,
        model_adapter_name: str,
    ) -> None:
        self._model = model
        self._db = registry.get_database_adapter(db_adapter_name)
        self._model_adapter = registry.get_model_adapter(model_adapter_name)

    async def create(self, data: dict[str, Any]) -> T:
        """Create a new record.

        Args:
            data: Dictionary of field values

        Returns:
            Created model instance
        """
        return await self._db.create(self._model, data)

    async def create_or_update(
        self,
        data: dict[str, Any],
        key_field: str,
    ) -> T:
        """Create or update a record (upsert).

        Args:
            data: Dictionary of field values
            key_field: Field name to use as unique key

        Returns:
            Created or updated model instance
        """
        return await self._db.create_or_update(self._model, data, key_field)

    async def update(
        self,
        filters: dict[str, Any],
        data: dict[str, Any],
    ) -> T | None:
        """Update records matching filters.

        Args:
            filters: Field filters to match records
            data: Dictionary of values to update

        Returns:
            Updated model instance or None
        """
        return await self._db.update(self._model, filters, data)

    async def find(self, **filters: Any) -> T | None:
        """Find a single record by filters.

        Args:
            **filters: Field filters (e.g., id=1, name="John")

        Returns:
            Model instance or None if not found
        """
        return await self._db.find(self._model, **filters)

    async def all(self) -> list[T]:
        """Get all records.

        Returns:
            List of all model instances
        """
        return await self._db.all(self._model)

    async def delete(self, **filters: Any) -> bool:
        """Delete records matching filters.

        Args:
            **filters: Field filters to match records

        Returns:
            True if any records were deleted
        """
        return await self._db.delete(self._model, **filters)


class AdvancedOperations:
    """Advanced query operations with ordering and limiting."""

    def __init__(
        self,
        model: type[T],
        db_adapter_name: str,
    ) -> None:
        self._model = model
        self._db = registry.get_database_adapter(db_adapter_name)
        self._order_field: str | None = None
        self._order_desc: bool = False
        self._limit_value: int | None = None

    def order_by_desc(self, field: str) -> AdvancedOperations:
        """Order results by field in descending order.

        Args:
            field: Field name to order by

        Returns:
            Self for chaining
        """
        self._order_field = field
        self._order_desc = True
        return self

    def order_by(self, field: str) -> AdvancedOperations:
        """Order results by field in ascending order.

        Args:
            field: Field name to order by

        Returns:
            Self for chaining
        """
        self._order_field = field
        self._order_desc = False
        return self

    def limit(self, count: int) -> AdvancedOperations:
        """Limit number of results.

        Args:
            count: Maximum number of results

        Returns:
            Self for chaining
        """
        self._limit_value = count
        return self

    async def all(self) -> list[T]:
        """Execute query and return results.

        Returns:
            List of model instances matching criteria
        """
        return await self._db.all(
            self._model,
            order_by=self._order_field,
            limit=self._limit_value,
            desc=self._order_desc,
        )


class ModelInterface:
    """Interface for a specific model combining simple and advanced operations."""

    def __init__(
        self,
        model: type[T],
        db_adapter_name: str,
        model_adapter_name: str,
    ) -> None:
        self.simple = SimpleOperations(model, db_adapter_name, model_adapter_name)
        self.advanced = AdvancedOperations(model, db_adapter_name)


class ACBQuery:
    """Unified query interface for ACB models.

    This class provides a fluent API for database operations that works
    with any registered database adapter (SQL, NoSQL) and model adapter
    (Pydantic, SQLModel, etc.).

    Example:
        ```python
        from acb.adapters.models._hybrid import ACBQuery
        from acb.adapters.models._query import registry

        # Register adapters
        registry.register_database_adapter("sql", sql_adapter)
        registry.register_model_adapter("sqlmodel", sqlmodel_adapter)

        # Create query interface
        query = ACBQuery(database_adapter_name="sql", model_adapter_name="sqlmodel")

        # Use it
        user = await query.for_model(User).simple.find(id=1)
        recent = (
            await query.for_model(User)
            .advanced.order_by_desc("created_at")
            .limit(10)
            .all()
        )
        ```
    """

    def __init__(
        self,
        database_adapter_name: str = "sql",
        model_adapter_name: str = "pydantic",
    ) -> None:
        """Initialize ACBQuery with adapter names.

        Args:
            database_adapter_name: Name of registered database adapter
            model_adapter_name: Name of registered model adapter
        """
        self._db_adapter_name = database_adapter_name
        self._model_adapter_name = model_adapter_name

    def for_model(self, model: type[T]) -> ModelInterface:
        """Get query interface for a specific model.

        Args:
            model: The model class to query

        Returns:
            ModelInterface with simple and advanced operations
        """
        return ModelInterface(
            model,
            self._db_adapter_name,
            self._model_adapter_name,
        )
