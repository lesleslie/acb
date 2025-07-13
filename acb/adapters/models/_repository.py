"""Repository Pattern for Domain-Specific Queries.

This module implements the Repository Pattern, providing a collection-like interface
for each entity with domain-specific query methods that encapsulate business logic.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import UTC
from typing import (
    Any,
    Protocol,
    TypeVar,
    runtime_checkable,
)

from acb.adapters.models._query import QueryBuilder, QueryCondition, QueryOperator
from acb.adapters.models._specification import Specification

T = TypeVar("T")


@dataclass
class RepositoryOptions:
    cache_enabled: bool = True
    cache_ttl: int = 300
    batch_size: int = 100
    enable_soft_delete: bool = False
    soft_delete_field: str = "deleted_at"
    audit_enabled: bool = False
    audit_fields: list[str] = field(
        default_factory=lambda: [
            "created_at",
            "updated_at",
            "created_by",
            "updated_by",
        ],
    )


@runtime_checkable
class RepositoryProtocol(Protocol[T]):
    async def find_by_id(self, id_value: Any) -> T | None: ...

    async def find_all(
        self,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[T]: ...

    async def find_by_specification(self, spec: Specification[T]) -> list[T]: ...

    async def count(self, spec: Specification[T] | None = None) -> int: ...

    async def exists(self, spec: Specification[T]) -> bool: ...

    async def create(self, entity_data: dict[str, Any]) -> T: ...

    async def update(self, id_value: Any, entity_data: dict[str, Any]) -> T | None: ...

    async def delete(self, id_value: Any) -> bool: ...


class Repository[T](ABC):
    def __init__(
        self,
        model_class: type[T],
        query_builder: QueryBuilder,
        options: RepositoryOptions | None = None,
    ) -> None:
        self.model_class = model_class
        self.query_builder = query_builder
        self.options = options or RepositoryOptions()
        self._cache: dict[Any, T] = {}
        self._cache_timestamps: dict[Any, float] = {}

    @property
    def _primary_key_field(self) -> str:
        model_adapter = self.query_builder.model_adapter
        if hasattr(model_adapter, "get_primary_key_field"):
            return model_adapter.get_primary_key_field(self.model_class)  # type: ignore[attr-defined]
        return "id"

    async def find_by_id(self, id_value: Any) -> T | None:
        if self.options.cache_enabled and id_value in self._cache:
            if self._is_cache_valid(id_value):
                return self._cache[id_value]
            self._remove_from_cache(id_value)
        result = (
            await self.query_builder.query(self.model_class)
            .where(self._primary_key_field, id_value)
            .first()
        )
        if result and self.options.cache_enabled:
            self._add_to_cache(id_value, result)

        return result

    async def find_all(
        self,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[T]:
        query = self.query_builder.query(self.model_class)

        if limit is not None:
            query = query.limit(limit)

        if offset is not None:
            query = query.offset(offset)

        if self.options.enable_soft_delete:
            query = query.where_null(self.options.soft_delete_field)

        return await query.all()

    async def find_by_specification(self, spec: Specification[T]) -> list[T]:
        query_spec = spec.to_query_spec()
        if self.options.enable_soft_delete:
            query_spec.filter.conditions.append(
                QueryCondition(
                    self.options.soft_delete_field,
                    QueryOperator.IS_NULL,
                    None,
                ),
            )
        query = self.query_builder.query(self.model_class)
        query.query_spec = query_spec

        return await query.all()

    async def count(self, spec: Specification[T] | None = None) -> int:
        query = self.query_builder.query(self.model_class)
        if spec:
            query_spec = spec.to_query_spec()
            query.query_spec = query_spec
        if self.options.enable_soft_delete:
            query = query.where_null(self.options.soft_delete_field)

        return await query.count()

    async def exists(self, spec: Specification[T]) -> bool:
        count = await self.count(spec)
        return count > 0

    async def create(self, entity_data: dict[str, Any]) -> T:
        if self.options.audit_enabled:
            entity_data = self._add_audit_fields(entity_data, is_create=True)
        result = await self.query_builder.create(self.model_class, entity_data)
        if isinstance(result, dict):
            model_adapter = self.query_builder.model_adapter
            entity = model_adapter.deserialize_to_class(self.model_class, result)  # type: ignore[attr-defined]
            if self.options.cache_enabled and self._primary_key_field in result:
                id_value = result[self._primary_key_field]
                self._add_to_cache(id_value, entity)
            return entity
        return result  # type: ignore[return-value]

    async def update(self, id_value: Any, entity_data: dict[str, Any]) -> T | None:
        if self.options.audit_enabled:
            entity_data = self._add_audit_fields(entity_data, is_create=False)
        if self.options.cache_enabled:
            self._remove_from_cache(id_value)
        query = self.query_builder.query(self.model_class)
        await query.where(self._primary_key_field, id_value).update(entity_data)

        return await self.find_by_id(id_value)

    async def delete(self, id_value: Any) -> bool:
        if self.options.cache_enabled:
            self._remove_from_cache(id_value)
        query = self.query_builder.query(self.model_class)
        if self.options.enable_soft_delete:
            from datetime import datetime

            update_data = {self.options.soft_delete_field: datetime.now(tz=UTC)}
            result = await query.where(self._primary_key_field, id_value).update(
                update_data,
            )
            return result is not None
        result = await query.where(self._primary_key_field, id_value).delete()
        return result is not None

    async def batch_create(self, entities_data: list[dict[str, Any]]) -> list[T]:
        if not entities_data:
            return []
        if self.options.audit_enabled:
            entities_data = [
                self._add_audit_fields(data, is_create=True) for data in entities_data
            ]
        batch_size = self.options.batch_size
        results = []
        for i in range(0, len(entities_data), batch_size):
            batch = entities_data[i : i + batch_size]
            batch_results = await self.query_builder.create(self.model_class, batch)
            if isinstance(batch_results, list):
                results.extend(batch_results)
            else:
                results.append(batch_results)

        return results

    async def batch_update(self, updates: list[dict[str, Any]]) -> list[T]:
        if not updates:
            return []
        results = []
        for update in updates:
            if self._primary_key_field not in update:
                continue
            id_value = update[self._primary_key_field]
            update_data = {
                k: v for k, v in update.items() if k != self._primary_key_field
            }
            result = await self.update(id_value, update_data)
            if result:
                results.append(result)

        return results

    async def batch_delete(self, ids: list[Any]) -> int:
        if not ids:
            return 0
        if self.options.cache_enabled:
            for id_value in ids:
                self._remove_from_cache(id_value)
        query = self.query_builder.query(self.model_class)
        if self.options.enable_soft_delete:
            from datetime import datetime

            update_data = {self.options.soft_delete_field: datetime.now(tz=UTC)}
            result = await query.where_in(self._primary_key_field, ids).update(
                update_data,
            )
        else:
            result = await query.where_in(self._primary_key_field, ids).delete()

        return len(ids) if result else 0

    @asynccontextmanager
    async def transaction(self) -> AsyncGenerator[Any]:
        async with self.query_builder.transaction() as txn:
            yield txn

    def _is_cache_valid(self, id_value: Any) -> bool:
        if id_value not in self._cache_timestamps:
            return False
        import time

        return (time.time() - self._cache_timestamps[id_value]) < self.options.cache_ttl

    def _add_to_cache(self, id_value: Any, entity: T) -> None:
        import time

        self._cache[id_value] = entity
        self._cache_timestamps[id_value] = time.time()

    def _remove_from_cache(self, id_value: Any) -> None:
        self._cache.pop(id_value, None)
        self._cache_timestamps.pop(id_value, None)

    def _add_audit_fields(
        self,
        data: dict[str, Any],
        is_create: bool,
    ) -> dict[str, Any]:
        from datetime import datetime

        data = data.copy()

        if is_create:
            if "created_at" in self.options.audit_fields:
                data["created_at"] = datetime.now(tz=UTC)
            if "created_by" in self.options.audit_fields:
                data["created_by"] = self._get_current_user_id()

        if "updated_at" in self.options.audit_fields:
            data["updated_at"] = datetime.now(tz=UTC)
        if "updated_by" in self.options.audit_fields:
            data["updated_by"] = self._get_current_user_id()

        return data

    def _get_current_user_id(self) -> Any:
        return None

    def clear_cache(self) -> None:
        self._cache.clear()
        self._cache_timestamps.clear()

    def warm_cache(self, entities: list[T]) -> None:
        if not self.options.cache_enabled:
            return
        model_adapter = self.query_builder.model_adapter
        for entity in entities:
            entity_dict = model_adapter.serialize(entity)
            if self._primary_key_field in entity_dict:
                id_value = entity_dict[self._primary_key_field]
                self._add_to_cache(id_value, entity)

    @abstractmethod
    async def find_active(self) -> list[T]:
        pass

    @abstractmethod
    async def find_recent(self, days: int = 7) -> list[T]:
        pass


class GenericRepository(Repository[T]):
    def __init__(
        self,
        model_class: type[T],
        query_builder: QueryBuilder,
        options: RepositoryOptions | None = None,
    ) -> None:
        super().__init__(model_class, query_builder, options)

    async def find_active(self) -> list[T]:
        query = self.query_builder.query(self.model_class)
        try:
            return await query.where("status", "active").all()
        except Exception:
            try:
                return await query.where("active", True).all()
            except Exception:
                return await self.find_all()

    async def find_recent(self, days: int = 7) -> list[T]:
        from datetime import datetime, timedelta

        cutoff_date = datetime.now(tz=UTC) - timedelta(days=days)
        query = self.query_builder.query(self.model_class)
        try:
            return (
                await query.where_gte("created_at", cutoff_date)
                .order_by_desc("created_at")
                .all()
            )
        except Exception:
            return []


class RepositoryFactory:
    def __init__(
        self,
        query_builder: QueryBuilder,
        default_options: RepositoryOptions | None = None,
    ) -> None:
        self.query_builder = query_builder
        self.default_options = default_options or RepositoryOptions()
        self._repositories: dict[type, Repository[Any]] = {}

    def get_repository(
        self,
        model_class: type[T],
        options: RepositoryOptions | None = None,
    ) -> Repository[T]:
        if model_class not in self._repositories:
            repository_options = options or self.default_options
            self._repositories[model_class] = GenericRepository(
                model_class,
                self.query_builder,
                repository_options,
            )

        return self._repositories[model_class]

    def register_repository(
        self,
        model_class: type[T],
        repository: Repository[T],
    ) -> None:
        self._repositories[model_class] = repository

    def create_repository(
        self,
        model_class: type[T],
        options: RepositoryOptions | None = None,
    ) -> Repository[T]:
        repository_options = options or self.default_options
        return GenericRepository(model_class, self.query_builder, repository_options)


class ReadOnlyRepository(Repository[T]):
    async def create(self, entity_data: dict[str, Any]) -> T:
        msg = "Create operation is not allowed in read-only repository"
        raise NotImplementedError(
            msg,
        )

    async def update(self, id_value: Any, entity_data: dict[str, Any]) -> T | None:
        msg = "Update operation is not allowed in read-only repository"
        raise NotImplementedError(
            msg,
        )

    async def delete(self, id_value: Any) -> bool:
        msg = "Delete operation is not allowed in read-only repository"
        raise NotImplementedError(
            msg,
        )

    async def batch_create(self, entities_data: list[dict[str, Any]]) -> list[T]:
        msg = "Batch create operation is not allowed in read-only repository"
        raise NotImplementedError(
            msg,
        )

    async def batch_update(self, updates: list[dict[str, Any]]) -> list[T]:
        msg = "Batch update operation is not allowed in read-only repository"
        raise NotImplementedError(
            msg,
        )

    async def batch_delete(self, ids: list[Any]) -> int:
        msg = "Batch delete operation is not allowed in read-only repository"
        raise NotImplementedError(
            msg,
        )


class AuditableRepository(Repository[T]):
    def __init__(
        self,
        model_class: type[T],
        query_builder: QueryBuilder,
        options: RepositoryOptions | None = None,
    ) -> None:
        if options is None:
            options = RepositoryOptions()
        options.audit_enabled = True
        super().__init__(model_class, query_builder, options)

    async def get_audit_trail(self, id_value: Any) -> list[dict[str, Any]]:
        return []

    async def get_entity_versions(self, id_value: Any) -> list[T]:
        return []
