"""NoSQL Database Adapter for Universal Query Interface.

This module implements the DatabaseAdapter protocol for NoSQL databases,
allowing the universal query interface to work with any NoSQL database.
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

from acb.adapters.models._query import (
    DatabaseAdapter,
    QueryOperator,
    QuerySpec,
    SortDirection,
)
from acb.adapters.nosql._base import NosqlBase


class NoSqlDatabaseAdapter(DatabaseAdapter):
    def __init__(self, nosql_adapter: NosqlBase) -> None:
        self.nosql_adapter = nosql_adapter

    async def execute_query(
        self,
        entity: str,
        query_spec: QuerySpec,
    ) -> list[dict[str, Any]]:
        filter_dict = self._build_filter(query_spec)
        options = self._build_options(query_spec)

        results = await self.nosql_adapter.find(entity, filter_dict, **options)
        return [self._normalize_document(doc) for doc in results]

    async def execute_count(self, entity: str, query_spec: QuerySpec) -> int:
        filter_dict = self._build_filter(query_spec)
        return await self.nosql_adapter.count(entity, filter_dict)

    async def execute_create(
        self,
        entity: str,
        data: dict[str, Any] | list[dict[str, Any]],
    ) -> Any:
        if isinstance(data, list):
            return await self.nosql_adapter.insert_many(entity, data)
        return await self.nosql_adapter.insert_one(entity, data)

    async def execute_update(
        self,
        entity: str,
        query_spec: QuerySpec,
        data: dict[str, Any],
    ) -> Any:
        filter_dict = self._build_filter(query_spec)
        update_doc = {"$set": data}

        return await self.nosql_adapter.update_many(entity, filter_dict, update_doc)

    async def execute_delete(self, entity: str, query_spec: QuerySpec) -> Any:
        filter_dict = self._build_filter(query_spec)

        return await self.nosql_adapter.delete_many(entity, filter_dict)

    async def execute_aggregate(
        self,
        entity: str,
        pipeline: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        results = await self.nosql_adapter.aggregate(entity, pipeline)
        return [self._normalize_document(doc) for doc in results]

    @asynccontextmanager
    async def transaction(self) -> AsyncGenerator[Any]:
        if hasattr(self.nosql_adapter, "transaction"):
            async with self.nosql_adapter.transaction() as txn:
                yield txn
        else:
            yield None

    def _build_filter(self, query_spec: QuerySpec) -> dict[str, Any]:
        if not query_spec.filter.conditions:
            return {}
        if (
            query_spec.filter.logical_operator == "OR"
            and len(query_spec.filter.conditions) > 1
        ):
            return self._build_or_filter(query_spec.filter.conditions)

        return self._build_and_filter(query_spec.filter.conditions)

    def _build_and_filter(self, conditions: list[Any]) -> dict[str, Any]:
        filter_dict = {}
        for condition in conditions:
            field_filter = self._build_condition_filter(condition)
            filter_dict.update(field_filter)

        return filter_dict

    def _build_or_filter(self, conditions: list[Any]) -> dict[str, Any]:
        or_conditions = []
        for condition in conditions:
            condition_dict = self._build_condition_filter(condition)
            or_conditions.append(condition_dict)

        return {"$or": or_conditions}

    def _build_condition_filter(self, condition: Any) -> dict[str, Any]:
        field = condition.field
        operator = condition.operator
        value = condition.value
        if operator == QueryOperator.EQ:
            return self._build_equality_filter(field, value)
        if operator == QueryOperator.NE:
            return self._build_inequality_filter(field, value)
        if operator in (
            QueryOperator.GT,
            QueryOperator.GTE,
            QueryOperator.LT,
            QueryOperator.LTE,
        ):
            return self._build_comparison_filter(field, operator, value)
        if operator in (QueryOperator.IN, QueryOperator.NOT_IN):
            return self._build_membership_filter(field, operator, value)
        if operator in (QueryOperator.LIKE, QueryOperator.ILIKE):
            return self._build_like_filter(field, operator, value)
        if operator in (
            QueryOperator.IS_NULL,
            QueryOperator.IS_NOT_NULL,
            QueryOperator.EXISTS,
        ):
            return self._build_existence_filter(field, operator)
        if operator == QueryOperator.BETWEEN:
            return self._build_between_filter(field, value)
        if operator == QueryOperator.REGEX:
            return self._build_regex_filter(field, value)
        msg = f"Unsupported operator: {operator}"
        raise ValueError(msg)

    def _build_equality_filter(self, field: str, value: Any) -> dict[str, Any]:
        return {field: value}

    def _build_inequality_filter(self, field: str, value: Any) -> dict[str, Any]:
        return {field: {"$ne": value}}

    def _build_comparison_filter(
        self,
        field: str,
        operator: QueryOperator,
        value: Any,
    ) -> dict[str, Any]:
        operator_map = {
            QueryOperator.GT: "$gt",
            QueryOperator.GTE: "$gte",
            QueryOperator.LT: "$lt",
            QueryOperator.LTE: "$lte",
        }
        return {field: {operator_map[operator]: value}}

    def _build_membership_filter(
        self,
        field: str,
        operator: QueryOperator,
        value: Any,
    ) -> dict[str, Any]:
        if operator == QueryOperator.IN:
            return {field: {"$in": value}}
        return {field: {"$nin": value}}

    def _build_like_filter(
        self,
        field: str,
        operator: QueryOperator,
        value: Any,
    ) -> dict[str, Any]:
        regex_pattern = value.replace("%", ".*").replace("_", ".")
        return {field: {"$regex": regex_pattern, "$options": "i"}}

    def _build_existence_filter(
        self,
        field: str,
        operator: QueryOperator,
    ) -> dict[str, Any]:
        if operator == QueryOperator.IS_NULL:
            return {field: {"$exists": False}}
        return {field: {"$exists": True}}

    def _build_between_filter(self, field: str, value: Any) -> dict[str, Any]:
        if isinstance(value, list | tuple) and len(value) == 2:
            return {field: {"$gte": value[0], "$lte": value[1]}}
        return {}

    def _build_regex_filter(self, field: str, value: Any) -> dict[str, Any]:
        return {field: {"$regex": value}}

    def _build_options(self, query_spec: QuerySpec) -> dict[str, Any]:
        options = {}
        if query_spec.fields:
            options["projection"] = dict.fromkeys(query_spec.fields, 1)
        if query_spec.sorts:
            sort_spec = []
            for sort in query_spec.sorts:
                direction = 1 if sort.direction == SortDirection.ASC else -1
                sort_spec.append((sort.field, direction))
            options["sort"] = sort_spec
        if query_spec.limit is not None:
            options["limit"] = query_spec.limit
        if query_spec.offset is not None:
            options["skip"] = query_spec.offset

        return options

    def _normalize_document(self, doc: dict[str, Any]) -> dict[str, Any]:
        normalized = doc.copy()
        if "_id" in normalized:
            id_value = normalized["_id"]
            if hasattr(id_value, "__str__"):
                normalized["_id"] = str(id_value)
        for key, value in normalized.items():
            if hasattr(value, "__str__") and not isinstance(
                value,
                str | int | float | bool | list | dict,
            ):
                normalized[key] = str(value)

        return normalized
