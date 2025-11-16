"""NoSQL database adapter for ACB query interface.

This module provides a NoSQL-based implementation of the DatabaseAdapter
for use with the ACB query interface, supporting MongoDB, Firestore, and Redis.
"""

from __future__ import annotations

from pydantic import BaseModel
from typing import Any, TypeVar

from acb.adapters.models._query import DatabaseAdapter

T = TypeVar("T", bound=BaseModel)


class NoSQLDatabaseAdapter(DatabaseAdapter[T]):
    """NoSQL database adapter for document databases.

    This adapter provides database operations for NoSQL databases
    (MongoDB, Firestore, Redis) using their async drivers.
    """

    def __init__(self, nosql_adapter: Any) -> None:
        """Initialize with a NoSQL adapter instance.

        Args:
            nosql_adapter: ACB NoSQL adapter (e.g., Mongodb, Firestore, Redis)
        """
        self._nosql = nosql_adapter

    def _get_collection_name(self, model: type[T]) -> str:
        """Get collection name from model.

        Args:
            model: Model class

        Returns:
            Collection name (e.g., "users" for User model)
        """
        # Use model name in lowercase as collection name
        return model.__name__.lower() + "s"

    def _model_to_dict(self, instance: T) -> dict[str, Any]:
        """Convert model instance to dictionary for storage.

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

    def _dict_to_model(self, model: type[T], data: dict[str, Any]) -> T:
        """Convert dictionary to model instance.

        Args:
            model: Model class
            data: Dictionary data

        Returns:
            Model instance
        """
        # Handle MongoDB _id field
        if "_id" in data and "id" not in data:
            data["id"] = str(data.pop("_id"))
        return model(**data)

    async def create(self, model: type[T], data: dict[str, Any]) -> T:
        """Create a new record.

        Args:
            model: Model class
            data: Dictionary of field values

        Returns:
            Created model instance
        """
        collection = self._get_collection_name(model)
        instance = model(**data)
        doc = self._model_to_dict(instance)

        result = await self._nosql.insert_one(collection, doc)

        # Add the generated ID if available
        if hasattr(result, "inserted_id"):
            doc["id"] = str(result.inserted_id)

        return self._dict_to_model(model, doc)

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
        collection = self._get_collection_name(model)

        # Find existing document
        existing = await self._nosql.find_one(collection, filters)
        if not existing:
            return None

        # Update the document
        update_dict = {"$set": data}
        await self._nosql.update_one(collection, filters, update_dict)

        # Fetch updated document
        updated = await self._nosql.find_one(collection, filters)
        if not updated:
            return None

        return self._dict_to_model(model, updated)

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
        collection = self._get_collection_name(model)
        doc = await self._nosql.find_one(collection, filters)

        if not doc:
            return None

        return self._dict_to_model(model, doc)

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
        collection = self._get_collection_name(model)

        # Build query options
        kwargs: dict[str, Any] = {}
        if order_by:
            # MongoDB sort format: [(field, direction)]
            direction = -1 if desc else 1
            kwargs["sort"] = [(order_by, direction)]
        if limit is not None:
            kwargs["limit"] = limit

        docs = await self._nosql.find(collection, {}, **kwargs)
        return [self._dict_to_model(model, doc) for doc in docs]

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
        collection = self._get_collection_name(model)
        result = await self._nosql.delete_one(collection, filters)

        # Check if any documents were deleted
        if hasattr(result, "deleted_count"):
            return result.deleted_count > 0

        return bool(result)
