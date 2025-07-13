"""Database and Model Agnostic Query Interface.

This module provides a universal query interface that works with any combination of
database adapters and model frameworks through protocol-based design.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from enum import Enum
from typing import (
    TYPE_CHECKING,
    Any,
    Protocol,
    TypeVar,
    runtime_checkable,
)

if TYPE_CHECKING:
    from acb.adapters.models._specification import Specification

T = TypeVar("T")
R = TypeVar("R")


class QueryOperator(Enum):
    EQ = "eq"
    NE = "ne"
    GT = "gt"
    GTE = "gte"
    LT = "lt"
    LTE = "lte"
    IN = "in"
    NOT_IN = "not_in"
    LIKE = "like"
    ILIKE = "ilike"
    IS_NULL = "is_null"
    IS_NOT_NULL = "is_not_null"
    BETWEEN = "between"
    REGEX = "regex"
    EXISTS = "exists"


class SortDirection(Enum):
    ASC = "asc"
    DESC = "desc"


@dataclass
class QueryCondition:
    field: str
    operator: QueryOperator
    value: Any = None

    def __post_init__(self) -> None:
        if self.operator in (
            QueryOperator.IS_NULL,
            QueryOperator.IS_NOT_NULL,
            QueryOperator.EXISTS,
        ):
            self.value = None


@dataclass
class QuerySort:
    field: str
    direction: SortDirection = SortDirection.ASC


@dataclass
class QueryFilter:
    conditions: list[QueryCondition] = field(default_factory=list)
    logical_operator: str = "AND"

    def add_condition(
        self,
        field: str,
        operator: QueryOperator,
        value: Any = None,
    ) -> QueryFilter:
        self.conditions.append(QueryCondition(field, operator, value))
        return self

    def where(self, field: str, value: Any) -> QueryFilter:
        return self.add_condition(field, QueryOperator.EQ, value)

    def where_not(self, field: str, value: Any) -> QueryFilter:
        return self.add_condition(field, QueryOperator.NE, value)

    def where_gt(self, field: str, value: Any) -> QueryFilter:
        return self.add_condition(field, QueryOperator.GT, value)

    def where_gte(self, field: str, value: Any) -> QueryFilter:
        return self.add_condition(field, QueryOperator.GTE, value)

    def where_lt(self, field: str, value: Any) -> QueryFilter:
        return self.add_condition(field, QueryOperator.LT, value)

    def where_lte(self, field: str, value: Any) -> QueryFilter:
        return self.add_condition(field, QueryOperator.LTE, value)

    def where_in(self, field: str, values: list[Any]) -> QueryFilter:
        return self.add_condition(field, QueryOperator.IN, values)

    def where_not_in(self, field: str, values: list[Any]) -> QueryFilter:
        return self.add_condition(field, QueryOperator.NOT_IN, values)

    def where_like(self, field: str, pattern: str) -> QueryFilter:
        return self.add_condition(field, QueryOperator.LIKE, pattern)

    def where_null(self, field: str) -> QueryFilter:
        return self.add_condition(field, QueryOperator.IS_NULL)

    def where_not_null(self, field: str) -> QueryFilter:
        return self.add_condition(field, QueryOperator.IS_NOT_NULL)


@dataclass
class QuerySpec:
    filter: QueryFilter = field(default_factory=QueryFilter)
    sorts: list[QuerySort] = field(default_factory=list)
    limit: int | None = None
    offset: int | None = None
    fields: list[str] | None = None

    def add_sort(
        self,
        field: str,
        direction: SortDirection = SortDirection.ASC,
    ) -> QuerySpec:
        self.sorts.append(QuerySort(field, direction))
        return self

    def order_by(self, field: str) -> QuerySpec:
        return self.add_sort(field)

    def order_by_desc(self, field: str) -> QuerySpec:
        return self.add_sort(field, SortDirection.DESC)

    def take(self, count: int) -> QuerySpec:
        self.limit = count
        return self

    def skip(self, count: int) -> QuerySpec:
        self.offset = count
        return self

    def select(self, *fields: str) -> QuerySpec:
        self.fields = list(fields)
        return self


@runtime_checkable
class DatabaseAdapter(Protocol):
    async def execute_query(
        self,
        entity: str,
        query_spec: QuerySpec,
    ) -> list[dict[str, Any]]: ...

    async def execute_count(self, entity: str, query_spec: QuerySpec) -> int: ...

    async def execute_create(
        self,
        entity: str,
        data: dict[str, Any] | list[dict[str, Any]],
    ) -> Any: ...

    async def execute_update(
        self,
        entity: str,
        query_spec: QuerySpec,
        data: dict[str, Any],
    ) -> Any: ...

    async def execute_delete(self, entity: str, query_spec: QuerySpec) -> Any: ...

    async def execute_aggregate(
        self,
        entity: str,
        pipeline: list[dict[str, Any]],
    ) -> list[dict[str, Any]]: ...

    @asynccontextmanager  # type: ignore[misc]
    async def transaction(self) -> None: ...


@runtime_checkable
class ModelAdapter(Protocol[T]):
    def serialize(self, instance: T) -> dict[str, Any]: ...

    def deserialize(self, data: dict[str, Any]) -> T: ...

    def get_entity_name(self, model_class: type[T]) -> str: ...

    def get_field_mapping(self, model_class: type[T]) -> dict[str, str]: ...

    def validate_data(
        self,
        model_class: type[T],
        data: dict[str, Any],
    ) -> dict[str, Any]: ...


class Query[T]:
    def __init__(
        self,
        model_class: type[T],
        database_adapter: DatabaseAdapter,
        model_adapter: ModelAdapter[T],
    ) -> None:
        self.model_class = model_class
        self.database_adapter = database_adapter
        self.model_adapter = model_adapter
        self.query_spec = QuerySpec()
        self._entity_name = model_adapter.get_entity_name(model_class)
        self._field_mapping = model_adapter.get_field_mapping(model_class)
        self._specifications = []

    def _map_field(self, field: str) -> str:
        return self._field_mapping.get(field, field)

    def _map_query_spec(self, query_spec: QuerySpec) -> QuerySpec:
        mapped_spec = QuerySpec()
        for condition in query_spec.filter.conditions:
            mapped_condition = QueryCondition(
                field=self._map_field(condition.field),
                operator=condition.operator,
                value=condition.value,
            )
            mapped_spec.filter.conditions.append(mapped_condition)
        mapped_spec.filter.logical_operator = query_spec.filter.logical_operator
        for sort in query_spec.sorts:
            mapped_spec.sorts.append(
                QuerySort(field=self._map_field(sort.field), direction=sort.direction),
            )
        mapped_spec.limit = query_spec.limit
        mapped_spec.offset = query_spec.offset
        mapped_spec.fields = (
            [self._map_field(f) for f in query_spec.fields]
            if query_spec.fields
            else None
        )

        return mapped_spec

    def where(self, field: str, value: Any) -> Query[T]:
        self.query_spec.filter.where(field, value)
        return self

    def where_not(self, field: str, value: Any) -> Query[T]:
        self.query_spec.filter.where_not(field, value)
        return self

    def where_gt(self, field: str, value: Any) -> Query[T]:
        self.query_spec.filter.where_gt(field, value)
        return self

    def where_gte(self, field: str, value: Any) -> Query[T]:
        self.query_spec.filter.where_gte(field, value)
        return self

    def where_lt(self, field: str, value: Any) -> Query[T]:
        self.query_spec.filter.where_lt(field, value)
        return self

    def where_lte(self, field: str, value: Any) -> Query[T]:
        self.query_spec.filter.where_lte(field, value)
        return self

    def where_in(self, field: str, values: list[Any]) -> Query[T]:
        self.query_spec.filter.where_in(field, values)
        return self

    def where_not_in(self, field: str, values: list[Any]) -> Query[T]:
        self.query_spec.filter.where_not_in(field, values)
        return self

    def where_like(self, field: str, pattern: str) -> Query[T]:
        self.query_spec.filter.where_like(field, pattern)
        return self

    def where_null(self, field: str) -> Query[T]:
        self.query_spec.filter.where_null(field)
        return self

    def where_not_null(self, field: str) -> Query[T]:
        self.query_spec.filter.where_not_null(field)
        return self

    def order_by(self, field: str) -> Query[T]:
        self.query_spec.order_by(field)
        return self

    def order_by_desc(self, field: str) -> Query[T]:
        self.query_spec.order_by_desc(field)
        return self

    def limit(self, count: int) -> Query[T]:
        self.query_spec.take(count)
        return self

    def offset(self, count: int) -> Query[T]:
        self.query_spec.skip(count)
        return self

    def select(self, *fields: str) -> Query[T]:
        self.query_spec.select(*fields)
        return self

    async def all(self) -> list[T]:
        self._apply_specifications()
        mapped_spec = self._map_query_spec(self.query_spec)
        raw_results = await self.database_adapter.execute_query(
            self._entity_name,
            mapped_spec,
        )
        return [self.model_adapter.deserialize(row) for row in raw_results]

    async def first(self) -> T | None:
        original_limit = self.query_spec.limit
        self.query_spec.limit = 1
        try:
            results = await self.all()
            return results[0] if results else None
        finally:
            self.query_spec.limit = original_limit

    async def count(self) -> int:
        self._apply_specifications()
        mapped_spec = self._map_query_spec(self.query_spec)
        return await self.database_adapter.execute_count(self._entity_name, mapped_spec)

    async def exists(self) -> bool:
        count = await self.count()
        return count > 0

    async def update(self, data: dict[str, Any]) -> Any:
        validated_data = self.model_adapter.validate_data(self.model_class, data)
        mapped_spec = self._map_query_spec(self.query_spec)
        return await self.database_adapter.execute_update(
            self._entity_name,
            mapped_spec,
            validated_data,
        )

    async def delete(self) -> Any:
        mapped_spec = self._map_query_spec(self.query_spec)
        return await self.database_adapter.execute_delete(
            self._entity_name,
            mapped_spec,
        )

    async def create(self, data: dict[str, Any] | list[dict[str, Any]]) -> Any:
        if isinstance(data, list):
            validated_data = [
                self.model_adapter.validate_data(self.model_class, item)
                for item in data
            ]
        else:
            validated_data = self.model_adapter.validate_data(self.model_class, data)

        return await self.database_adapter.execute_create(
            self._entity_name,
            validated_data,
        )

    async def aggregate(self, pipeline: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return await self.database_adapter.execute_aggregate(
            self._entity_name,
            pipeline,
        )

    def with_specification(self, spec: Specification[T]) -> Query[T]:
        self._specifications.append(spec)
        return self

    def with_spec(self, spec: Specification[T]) -> Query[T]:
        return self.with_specification(spec)

    def _apply_specifications(self) -> None:
        if not self._specifications:
            return
        combined_spec = self._specifications[0]
        for spec in self._specifications[1:]:
            combined_spec = combined_spec.and_(spec)
        spec_query_spec = combined_spec.to_query_spec()
        self.query_spec.filter.conditions.extend(spec_query_spec.filter.conditions)
        if spec_query_spec.filter.logical_operator:
            self.query_spec.filter.logical_operator = (
                spec_query_spec.filter.logical_operator
            )
        self.query_spec.sorts.extend(spec_query_spec.sorts)
        if spec_query_spec.limit is not None:
            if self.query_spec.limit is None:
                self.query_spec.limit = spec_query_spec.limit
            else:
                self.query_spec.limit = min(
                    self.query_spec.limit,
                    spec_query_spec.limit,
                )
        if spec_query_spec.offset is not None:
            if self.query_spec.offset is None:
                self.query_spec.offset = spec_query_spec.offset
            else:
                self.query_spec.offset = max(
                    self.query_spec.offset,
                    spec_query_spec.offset,
                )

    def evaluate_specifications(self, candidates: list[T]) -> list[T]:
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


class QueryBuilder:
    def __init__(
        self,
        database_adapter: DatabaseAdapter,
        model_adapter: ModelAdapter[Any],
    ) -> None:
        self.database_adapter = database_adapter
        self.model_adapter = model_adapter

    def query(self, model_class: type[T]) -> Query[T]:
        return Query(model_class, self.database_adapter, self.model_adapter)

    async def create(
        self,
        model_class: type[T],
        data: dict[str, Any] | list[dict[str, Any]],
    ) -> Any:
        query = self.query(model_class)
        return await query.create(data)

    async def find_by_id(self, model_class: type[T], id_value: Any) -> T | None:
        query = self.query(model_class)
        return await query.where("id", id_value).first()

    @asynccontextmanager
    async def transaction(self) -> AsyncGenerator[Any]:
        async with self.database_adapter.transaction() as txn:
            yield txn


class Registry:
    def __init__(self) -> None:
        self._database_adapters: dict[str, DatabaseAdapter] = {}
        self._model_adapters: dict[str, ModelAdapter[Any]] = {}
        self._default_database: str | None = None
        self._default_model: str | None = None

    def register_database_adapter(
        self,
        name: str,
        adapter: DatabaseAdapter,
        is_default: bool = False,
    ) -> None:
        self._database_adapters[name] = adapter
        if is_default or self._default_database is None:
            self._default_database = name

    def register_model_adapter(
        self,
        name: str,
        adapter: ModelAdapter[Any],
        is_default: bool = False,
    ) -> None:
        self._model_adapters[name] = adapter
        if is_default or self._default_model is None:
            self._default_model = name

    def get_database_adapter(self, name: str | None = None) -> DatabaseAdapter:
        adapter_name = name or self._default_database
        if adapter_name not in self._database_adapters:
            msg = f"Database adapter '{adapter_name}' not found"
            raise ValueError(msg)
        return self._database_adapters[adapter_name]

    def get_model_adapter(self, name: str | None = None) -> ModelAdapter[Any]:
        adapter_name = name or self._default_model
        if adapter_name not in self._model_adapters:
            msg = f"Model adapter '{adapter_name}' not found"
            raise ValueError(msg)
        return self._model_adapters[adapter_name]

    def create_query_builder(
        self,
        database_name: str | None = None,
        model_name: str | None = None,
    ) -> QueryBuilder:
        db_adapter = self.get_database_adapter(database_name)
        model_adapter = self.get_model_adapter(model_name)
        return QueryBuilder(db_adapter, model_adapter)


registry = Registry()
