"""In-memory database adapter for ACB query interface.

This module provides a simple in-memory implementation of the DatabaseAdapter
for testing and development purposes.
"""

from __future__ import annotations

from pydantic import BaseModel
from typing import Any, TypeVar

from acb.adapters.models._query import DatabaseAdapter

T = TypeVar("T", bound=BaseModel)


class MemoryDatabaseAdapter(DatabaseAdapter[T]):
    """In-memory database adapter for testing and development.

    This adapter stores all data in memory using Python dictionaries.
    Data is not persisted and will be lost when the application restarts.
    """

    def __init__(self) -> None:
        """Initialize with empty storage."""
        self._stores: dict[type[Any], list[dict[str, Any]]] = {}

    def _get_store(self, model: type[T]) -> list[dict[str, Any]]:
        """Get or create storage for a model.

        Args:
            model: Model class

        Returns:
            List of stored documents for this model
        """
        if model not in self._stores:
            self._stores[model] = []
        return self._stores[model]

    def _model_to_dict(self, instance: T) -> dict[str, Any]:
        """Convert model instance to dictionary.

        Args:
            instance: Model instance

        Returns:
            Dictionary representation
        """
        if hasattr(instance, "model_dump"):
            return instance.model_dump()  # type: ignore[no-any-return]
        elif hasattr(instance, "dict"):
            return instance.dict()  # type: ignore[no-any-return]
        return dict(instance)  # type: ignore[call-overload]

    async def create(self, model: type[T], data: dict[str, Any]) -> T:
        """Create a new record.

        Args:
            model: Model class
            data: Dictionary of field values

        Returns:
            Created model instance
        """
        store = self._get_store(model)
        instance = model(**data)
        doc = self._model_to_dict(instance)
        store.append(doc)
        return instance

    async def update(
        self,
        model: type[T],
        filters: dict[str, Any],
        data: dict[str, Any],
    ) -> T | None:
        """Update records matching filters.

        Args:
            model: Model class
            filters: Field filters to match records
            data: Dictionary of values to update

        Returns:
            Updated model instance or None if not found
        """
        store = self._get_store(model)

        # Find matching document
        for doc in store:
            if all(doc.get(key) == value for key, value in filters.items()):
                # Update fields
                doc.update(data)
                return model(**doc)

        return None

    async def find(
        self,
        model: type[T],
        **filters: Any,
    ) -> T | None:
        """Find a single record by filters.

        Args:
            model: Model class
            **filters: Field filters (e.g., id="123", name="John")

        Returns:
            Model instance or None if not found
        """
        store = self._get_store(model)

        for doc in store:
            if all(doc.get(key) == value for key, value in filters.items()):
                return model(**doc)

        return None

    async def all(
        self,
        model: type[T],
        order_by: str | None = None,
        limit: int | None = None,
        desc: bool = False,
    ) -> list[T]:
        """Get all records, optionally ordered and limited.

        Args:
            model: Model class
            order_by: Field name to order by
            limit: Maximum number of records
            desc: Sort in descending order

        Returns:
            List of model instances
        """
        store = self._get_store(model)
        docs = store.copy()  # Copy to avoid mutation

        # Apply ordering
        if order_by:
            docs.sort(
                key=lambda doc: doc.get(order_by, ""),
                reverse=desc,
            )

        # Apply limit
        if limit is not None:
            docs = docs[:limit]

        return [model(**doc) for doc in docs]

    async def delete(
        self,
        model: type[T],
        **filters: Any,
    ) -> bool:
        """Delete records matching filters.

        Args:
            model: Model class
            **filters: Field filters to match records

        Returns:
            True if any records were deleted
        """
        store = self._get_store(model)
        to_remove = [
            doc
            for doc in store
            if all(doc.get(key) == value for key, value in filters.items())
        ]

        for doc in to_remove:
            store.remove(doc)

        return len(to_remove) > 0
