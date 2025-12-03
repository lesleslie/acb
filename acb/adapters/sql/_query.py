"""SQL database adapter for ACB query interface.

This module provides a SQLAlchemy-based implementation of the DatabaseAdapter
for use with the ACB query interface.
"""

from __future__ import annotations

from sqlalchemy import asc, desc, select
from sqlalchemy import delete as sql_delete
from sqlmodel import SQLModel
from typing import TYPE_CHECKING, Any, TypeVar

from acb.adapters.models._query import DatabaseAdapter

if TYPE_CHECKING:
    from sqlmodel.ext.asyncio.session import AsyncSession

T = TypeVar("T", bound=SQLModel)


class SQLDatabaseAdapter(DatabaseAdapter[T]):
    """SQL database adapter using SQLAlchemy/SQLModel.

    This adapter provides database operations for SQL databases
    using SQLAlchemy's async engine and SQLModel.
    """

    def __init__(self, sql_adapter: Any) -> None:
        """Initialize with a SQL adapter instance.

        Args:
            sql_adapter: ACB SQL adapter (e.g., Sql, Mysql, Pgsql, Sqlite)
        """
        self._sql = sql_adapter

    async def _get_session(self) -> AsyncSession:
        """Get async database session.

        Returns:
            AsyncSession instance
        """
        # Ensure session is initialized
        return await self._sql._ensure_session()

    async def create(self, model: type[T], data: dict[str, Any]) -> T:
        """Create a new record.

        Args:
            model: SQLModel class
            data: Dictionary of field values

        Returns:
            Created model instance
        """
        session = await self._get_session()
        instance = model(**data)
        session.add(instance)
        await session.commit()
        await session.refresh(instance)
        return instance

    async def update(
        self,
        model: type[T],
        filters: dict[str, Any],
        data: dict[str, Any],
    ) -> T | None:
        """Update records matching filters.

        Args:
            model: SQLModel class
            filters: Field filters to match records
            data: Dictionary of values to update

        Returns:
            Updated model instance or None if not found
        """
        session = await self._get_session()

        # Build WHERE clause from filters
        stmt = select(model)
        for key, value in filters.items():
            stmt = stmt.where(getattr(model, key) == value)

        result = await session.execute(stmt)
        instance = result.scalar_one_or_none()

        if instance is None:
            return None

        # Update fields
        for key, value in data.items():
            if hasattr(instance, key):
                setattr(instance, key, value)

        session.add(instance)
        await session.commit()
        await session.refresh(instance)
        return instance

    async def find(
        self,
        model: type[T],
        **filters: Any,
    ) -> T | None:
        """Find a single record by filters.

        Args:
            model: SQLModel class
            **filters: Field filters (e.g., id=1, name="John")

        Returns:
            Model instance or None if not found
        """
        session = await self._get_session()

        # Build query with filters
        stmt = select(model)
        for key, value in filters.items():
            stmt = stmt.where(getattr(model, key) == value)

        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def all(
        self,
        model: type[T],
        order_by: str | None = None,
        limit: int | None = None,
        descending: bool = False,
    ) -> list[T]:
        """Get all records, optionally ordered and limited.

        Args:
            model: SQLModel class
            order_by: Field name to order by
            limit: Maximum number of records
            descending: Sort in descending order

        Returns:
            List of model instances
        """
        session = await self._get_session()

        stmt = select(model)

        # Add ordering
        if order_by:
            order_column = getattr(model, order_by)
            stmt = stmt.order_by(
                desc(order_column) if descending else asc(order_column),
            )

        # Add limit
        if limit is not None:
            stmt = stmt.limit(limit)

        result = await session.execute(stmt)
        return list(result.scalars().all())

    async def delete(
        self,
        model: type[T],
        **filters: Any,
    ) -> bool:
        """Delete records matching filters.

        Args:
            model: SQLModel class
            **filters: Field filters to match records

        Returns:
            True if any records were deleted
        """
        session = await self._get_session()

        # Build DELETE statement with filters
        stmt = sql_delete(model)
        for key, value in filters.items():
            stmt = stmt.where(getattr(model, key) == value)

        result = await session.execute(stmt)
        await session.commit()

        rowcount = getattr(result, "rowcount", 0)
        return bool(rowcount and rowcount > 0)
