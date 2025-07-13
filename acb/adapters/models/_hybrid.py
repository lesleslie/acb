"""Hybrid Query Interface for Multiple Query Styles.

This module provides a unified interface that supports different query styles:
- Simple Active Record style for basic CRUD operations
- Repository pattern for domain-specific queries
- Advanced Query Builder for complex queries
- Specification pattern for composable business rules
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from enum import Enum
from typing import Any, TypeVar

from acb.adapters.models._query import Query, QueryBuilder, registry
from acb.adapters.models._repository import (
    Repository,
    RepositoryFactory,
    RepositoryOptions,
)
from acb.adapters.models._specification import Specification, SpecificationBuilder
from acb.adapters.models._specification import field as spec_field

T = TypeVar("T")


class QueryStyle(Enum):
    SIMPLE = "simple"
    REPOSITORY = "repository"
    ADVANCED = "advanced"
    SPECIFICATION = "specification"


@dataclass
class HybridQueryOptions:
    default_style: QueryStyle = QueryStyle.SIMPLE
    cache_enabled: bool = True
    cache_ttl: int = 300
    batch_size: int = 100
    enable_soft_delete: bool = False
    audit_enabled: bool = False
    transaction_timeout: int = 30
    query_timeout: int = 60


class SimpleQuery[T]:
    def __init__(self, model_class: type[T], query_builder: QueryBuilder) -> None:
        self.model_class = model_class
        self.query_builder = query_builder
        self._query = query_builder.query(model_class)

    async def all(self) -> list[T]:
        return await self._query.all()

    async def first(self) -> T | None:
        return await self._query.first()

    async def find(self, id_value: Any) -> T | None:
        return await self._query.where("id", id_value).first()

    async def create(self, **kwargs: Any) -> T:
        return await self._query.create(kwargs)

    async def where(self, **conditions: Any) -> SimpleQuery[T]:
        for field, value in conditions.items():
            self._query = self._query.where(field, value)
        return self

    async def order_by(self, *fields: str) -> SimpleQuery[T]:
        for field in fields:
            if field.startswith("-"):
                self._query = self._query.order_by_desc(field[1:])
            else:
                self._query = self._query.order_by(field)
        return self

    async def limit(self, count: int) -> SimpleQuery[T]:
        self._query = self._query.limit(count)
        return self

    async def offset(self, count: int) -> SimpleQuery[T]:
        self._query = self._query.offset(count)
        return self

    async def count(self) -> int:
        return await self._query.count()

    async def exists(self) -> bool:
        return await self._query.exists()

    async def update(self, **kwargs: Any) -> Any:
        return await self._query.update(kwargs)

    async def delete(self) -> Any:
        return await self._query.delete()


class SpecificationQuery[T]:
    def __init__(self, model_class: type[T], query_builder: QueryBuilder) -> None:
        self.model_class = model_class
        self.query_builder = query_builder
        self._specifications: list[Specification[T]] = []

    def with_spec(self, spec: Specification[T]) -> SpecificationQuery[T]:
        self._specifications.append(spec)
        return self

    def where_spec(self, spec: Specification[T]) -> SpecificationQuery[T]:
        return self.with_spec(spec)

    async def all(self) -> list[T]:
        if not self._specifications:
            return await self.query_builder.query(self.model_class).all()
        combined_spec = self._specifications[0]
        for spec in self._specifications[1:]:
            combined_spec = combined_spec.and_(spec)
        query = self.query_builder.query(self.model_class)
        query.query_spec = combined_spec.to_query_spec()

        return await query.all()

    async def first(self) -> T | None:
        results = await self.all()
        return results[0] if results else None

    async def count(self) -> int:
        if not self._specifications:
            return await self.query_builder.query(self.model_class).count()
        combined_spec = self._specifications[0]
        for spec in self._specifications[1:]:
            combined_spec = combined_spec.and_(spec)
        query = self.query_builder.query(self.model_class)
        query.query_spec = combined_spec.to_query_spec()

        return await query.count()

    async def exists(self) -> bool:
        count = await self.count()
        return count > 0

    def evaluate_in_memory(self, candidates: list[T]) -> list[T]:
        if not self._specifications:
            return candidates
        combined_spec = self._specifications[0]
        for spec in self._specifications[1:]:
            combined_spec = combined_spec.and_(spec)

        return [
            candidate
            for candidate in candidates
            if combined_spec.is_satisfied_by(candidate)
        ]


class HybridQueryInterface:
    def __init__(
        self,
        query_builder: QueryBuilder | None = None,
        options: HybridQueryOptions | None = None,
    ) -> None:
        self.query_builder = query_builder or QueryBuilder(
            registry.get_database_adapter(),
            registry.get_model_adapter(),
        )
        self.options = options or HybridQueryOptions()

        repo_options = RepositoryOptions(
            cache_enabled=self.options.cache_enabled,
            cache_ttl=self.options.cache_ttl,
            batch_size=self.options.batch_size,
            enable_soft_delete=self.options.enable_soft_delete,
            audit_enabled=self.options.audit_enabled,
        )
        self.repository_factory = RepositoryFactory(self.query_builder, repo_options)

    def simple(self, model_class: type[T]) -> SimpleQuery[T]:
        return SimpleQuery(model_class, self.query_builder)

    def repository(self, model_class: type[T]) -> Repository[T]:
        return self.repository_factory.get_repository(model_class)

    def advanced(self, model_class: type[T]) -> Query[T]:
        return self.query_builder.query(model_class)

    def specification(self, model_class: type[T]) -> SpecificationQuery[T]:
        return SpecificationQuery(model_class, self.query_builder)

    def query(
        self,
        model_class: type[T],
        style: QueryStyle | None = None,
    ) -> SimpleQuery[T] | Repository[T] | Query[T] | SpecificationQuery[T]:
        query_style = style or self.options.default_style

        if query_style == QueryStyle.SIMPLE:
            return self.simple(model_class)
        if query_style == QueryStyle.REPOSITORY:
            return self.repository(model_class)
        if query_style == QueryStyle.ADVANCED:
            return self.advanced(model_class)
        if query_style == QueryStyle.SPECIFICATION:
            return self.specification(model_class)
        msg = f"Unknown query style: {query_style}"
        raise ValueError(msg)

    async def find_by_id(self, model_class: type[T], id_value: Any) -> T | None:
        return await self.simple(model_class).find(id_value)

    async def create(self, model_class: type[T], **kwargs: Any) -> T:
        return await self.simple(model_class).create(**kwargs)

    async def find_all(self, model_class: type[T], limit: int | None = None) -> list[T]:
        query = self.simple(model_class)
        if limit:
            query = await query.limit(limit)
        return await query.all()

    async def batch_create(
        self,
        model_class: type[T],
        records: list[dict[str, Any]],
    ) -> list[T]:
        repo = self.repository(model_class)
        return await repo.batch_create(records)

    async def batch_update(
        self,
        model_class: type[T],
        updates: list[dict[str, Any]],
    ) -> list[T]:
        repo = self.repository(model_class)
        return await repo.batch_update(updates)

    async def batch_delete(self, model_class: type[T], ids: list[Any]) -> int:
        repo = self.repository(model_class)
        return await repo.batch_delete(ids)

    @asynccontextmanager
    async def transaction(self) -> AsyncGenerator[Any]:
        async with self.query_builder.transaction() as txn:
            yield txn

    def register_custom_repository(
        self,
        model_class: type[T],
        repository: Repository[T],
    ) -> None:
        self.repository_factory.register_repository(model_class, repository)

    def clear_cache(self, model_class: type[T] | None = None) -> None:
        if model_class:
            repo = self.repository_factory.get_repository(model_class)
            repo.clear_cache()
        else:
            pass

    def warm_cache(self, model_class: type[T], entities: list[T]) -> None:
        repo = self.repository_factory.get_repository(model_class)
        repo.warm_cache(entities)

    def spec(self) -> SpecificationBuilder:
        return SpecificationBuilder()

    def field(self, field_name: str) -> Any:
        return spec_field(field_name)


class ModelManager[T]:
    def __init__(
        self,
        model_class: type[T],
        hybrid_interface: HybridQueryInterface,
    ) -> None:
        self.model_class = model_class
        self.hybrid = hybrid_interface

    @property
    def simple(self) -> SimpleQuery[T]:
        return self.hybrid.simple(self.model_class)

    @property
    def repository(self) -> Repository[T]:
        return self.hybrid.repository(self.model_class)

    @property
    def advanced(self) -> Query[T]:
        return self.hybrid.advanced(self.model_class)

    @property
    def specification(self) -> SpecificationQuery[T]:
        return self.hybrid.specification(self.model_class)

    def query(self, style: QueryStyle | None = None) -> Any:
        return self.hybrid.query(self.model_class, style)

    async def find_by_id(self, id_value: Any) -> T | None:
        return await self.hybrid.find_by_id(self.model_class, id_value)

    async def create(self, **kwargs: Any) -> T:
        return await self.hybrid.create(self.model_class, **kwargs)

    async def find_all(self, limit: int | None = None) -> list[T]:
        return await self.hybrid.find_all(self.model_class, limit)

    @asynccontextmanager
    async def transaction(self) -> AsyncGenerator[Any]:
        async with self.hybrid.transaction() as txn:
            yield txn


class ACBQuery:
    def __init__(
        self,
        database_adapter_name: str | None = None,
        model_adapter_name: str | None = None,
        options: HybridQueryOptions | None = None,
    ) -> None:
        query_builder = registry.create_query_builder(
            database_adapter_name,
            model_adapter_name,
        )

        self.hybrid = HybridQueryInterface(query_builder, options)

        self._model_managers: dict[type, ModelManager[Any]] = {}

    def simple(self, model_class: type[T]) -> SimpleQuery[T]:
        return self.hybrid.simple(model_class)

    def repository(self, model_class: type[T]) -> Repository[T]:
        return self.hybrid.repository(model_class)

    def advanced(self, model_class: type[T]) -> Query[T]:
        return self.hybrid.advanced(model_class)

    def specification(self, model_class: type[T]) -> SpecificationQuery[T]:
        return self.hybrid.specification(model_class)

    def query(self, model_class: type[T], style: QueryStyle | None = None) -> Any:
        return self.hybrid.query(model_class, style)

    def model(self, model_class: type[T]) -> ModelManager[T]:
        if model_class not in self._model_managers:
            self._model_managers[model_class] = ModelManager(model_class, self.hybrid)
        return self._model_managers[model_class]

    async def find_by_id(self, model_class: type[T], id_value: Any) -> T | None:
        return await self.hybrid.find_by_id(model_class, id_value)

    async def create(self, model_class: type[T], **kwargs: Any) -> T:
        return await self.hybrid.create(model_class, **kwargs)

    async def batch_create(
        self,
        model_class: type[T],
        records: list[dict[str, Any]],
    ) -> list[T]:
        return await self.hybrid.batch_create(model_class, records)

    async def batch_update(
        self,
        model_class: type[T],
        updates: list[dict[str, Any]],
    ) -> list[T]:
        return await self.hybrid.batch_update(model_class, updates)

    async def batch_delete(self, model_class: type[T], ids: list[Any]) -> int:
        return await self.hybrid.batch_delete(model_class, ids)

    @asynccontextmanager
    async def transaction(self) -> AsyncGenerator[Any]:
        async with self.hybrid.transaction() as txn:
            yield txn

    def spec(self) -> SpecificationBuilder:
        return self.hybrid.spec()

    def field(self, field_name: str) -> Any:
        return self.hybrid.field(field_name)

    def register_custom_repository(
        self,
        model_class: type[T],
        repository: Repository[T],
    ) -> None:
        self.hybrid.register_custom_repository(model_class, repository)

    def clear_cache(self, model_class: type[T] | None = None) -> None:
        self.hybrid.clear_cache(model_class)

    def warm_cache(self, model_class: type[T], entities: list[T]) -> None:
        self.hybrid.warm_cache(model_class, entities)


acb_query = ACBQuery()
