"""SQL Database Adapter for Universal Query Interface.

This module implements the DatabaseAdapter protocol for SQL databases,
allowing the universal query interface to work with any SQL database.
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

from sqlalchemy import text
from acb.adapters.models._query import (
    DatabaseAdapter,
    QueryOperator,
    QuerySpec,
    SortDirection,
)
from acb.adapters.sql._base import SqlBase


class SqlDatabaseAdapter(DatabaseAdapter):
    def __init__(self, sql_adapter: SqlBase) -> None:
        self.sql_adapter = sql_adapter

    async def execute_query(
        self,
        entity: str,
        query_spec: QuerySpec,
    ) -> list[dict[str, Any]]:
        query = self._build_select_query(entity, query_spec)
        params = self._build_params(query_spec)

        async with self.sql_adapter.get_session() as session:
            result = await session.execute(text(query), params)  # type: ignore[misc]
            rows = result.fetchall()
            if hasattr(rows, "__await__"):
                rows = await rows  # type: ignore[misc]
            return [dict(row._mapping) for row in rows]

    async def execute_count(self, entity: str, query_spec: QuerySpec) -> int:
        query = self._build_count_query(entity, query_spec)
        params = self._build_params(query_spec)
        async with self.sql_adapter.get_session() as session:
            result = await session.execute(text(query), params)  # type: ignore[misc]
            return result.scalar() or 0

    async def execute_create(
        self,
        entity: str,
        data: dict[str, Any] | list[dict[str, Any]],
    ) -> Any:
        if isinstance(data, list):
            return await self._insert_many(entity, data)
        return await self._insert_one(entity, data)

    async def _insert_one(self, entity: str, data: dict[str, Any]) -> Any:
        columns = ", ".join(data.keys())
        placeholders = ", ".join(f":{key}" for key in data)
        query = f"INSERT INTO {entity} ({columns}) VALUES ({placeholders}) RETURNING *"  # nosec B608
        async with self.sql_adapter.get_session() as session:
            try:
                result = await session.execute(text(query), data)  # type: ignore[misc]
                await session.commit()
                return dict(result.fetchone()._mapping)
            except Exception:
                await session.rollback()
                raise

    async def _insert_many(self, entity: str, data: list[dict[str, Any]]) -> Any:
        if not data:
            return []
        columns = ", ".join(data[0].keys())
        placeholders = ", ".join(f":{key}" for key in data[0])
        query = f"INSERT INTO {entity} ({columns}) VALUES ({placeholders}) RETURNING *"  # nosec B608
        async with self.sql_adapter.get_session() as session:
            try:
                results = []
                for record in data:
                    result = await session.execute(text(query), record)  # type: ignore[misc]
                    results.append(dict(result.fetchone()._mapping))
                await session.commit()
                return results
            except Exception:
                await session.rollback()
                raise

    async def execute_update(
        self,
        entity: str,
        query_spec: QuerySpec,
        data: dict[str, Any],
    ) -> Any:
        query = self._build_update_query(entity, query_spec, data)
        params = self._build_params(query_spec)
        params.update({f"set_{k}": v for k, v in data.items()})

        async with self.sql_adapter.get_session() as session:
            try:
                result = await session.execute(text(query), params)  # type: ignore[misc]
                await session.commit()
                return result.rowcount  # type: ignore[misc]
            except Exception:
                await session.rollback()
                raise

    async def execute_delete(self, entity: str, query_spec: QuerySpec) -> Any:
        query = self._build_delete_query(entity, query_spec)
        params = self._build_params(query_spec)
        async with self.sql_adapter.get_session() as session:
            try:
                result = await session.execute(text(query), params)  # type: ignore[misc]
                await session.commit()
                return result.rowcount  # type: ignore[misc]
            except Exception:
                await session.rollback()
                raise

    async def execute_aggregate(
        self,
        entity: str,
        pipeline: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        query = self._build_aggregation_query(entity, pipeline)

        async with self.sql_adapter.get_session() as session:
            result = await session.execute(text(query))  # type: ignore[misc]
            rows = result.fetchall()
            return [dict(row._mapping) for row in rows]

    @asynccontextmanager
    async def transaction(self) -> AsyncGenerator[Any]:
        async with self.sql_adapter.get_session() as session, session.begin():
            yield session

    def _build_select_query(self, entity: str, query_spec: QuerySpec) -> str:
        if query_spec.fields:
            select_clause = f"SELECT {', '.join(query_spec.fields)}"
        else:
            select_clause = "SELECT *"
        from_clause = f"FROM {entity}"
        where_clause = self._build_where_clause(query_spec)
        order_clause = self._build_order_clause(query_spec)
        limit_clause = ""
        if query_spec.limit is not None:
            limit_clause = f"LIMIT {query_spec.limit}"
        offset_clause = ""
        if query_spec.offset is not None:
            offset_clause = f"OFFSET {query_spec.offset}"
        query_parts = [select_clause, from_clause]
        if where_clause:
            query_parts.append(where_clause)
        if order_clause:
            query_parts.append(order_clause)
        if limit_clause:
            query_parts.append(limit_clause)
        if offset_clause:
            query_parts.append(offset_clause)

        return " ".join(query_parts)

    def _build_count_query(self, entity: str, query_spec: QuerySpec) -> str:
        query_parts = [f"SELECT COUNT(*) FROM {entity}"]  # nosec B608
        where_clause = self._build_where_clause(query_spec)
        if where_clause:
            query_parts.append(where_clause)

        return " ".join(query_parts)

    def _build_update_query(
        self,
        entity: str,
        query_spec: QuerySpec,
        data: dict[str, Any],
    ) -> str:
        set_clauses = [f"{key} = :set_{key}" for key in data]
        set_clause = f"SET {', '.join(set_clauses)}"

        where_clause = self._build_where_clause(query_spec)

        query_parts = [f"UPDATE {entity}", set_clause]  # nosec B608
        if where_clause:
            query_parts.append(where_clause)

        return " ".join(query_parts)

    def _build_delete_query(self, entity: str, query_spec: QuerySpec) -> str:
        query_parts = [f"DELETE FROM {entity}"]  # nosec B608
        where_clause = self._build_where_clause(query_spec)
        if where_clause:
            query_parts.append(where_clause)

        return " ".join(query_parts)

    def _build_where_clause(self, query_spec: QuerySpec) -> str:
        if not query_spec.filter.conditions:
            return ""
        conditions = []
        for condition in query_spec.filter.conditions:
            sql_condition = self._build_condition(condition)
            conditions.append(sql_condition)
        if not conditions:
            return ""
        operator = " AND " if query_spec.filter.logical_operator == "AND" else " OR "
        return f"WHERE {operator.join(conditions)}"

    def _build_condition(self, condition: Any) -> str:
        field = condition.field
        operator = condition.operator
        if operator == QueryOperator.EQ:
            return self._build_equality_condition(field)
        if operator == QueryOperator.NE:
            return self._build_inequality_condition(field)
        if operator in (
            QueryOperator.GT,
            QueryOperator.GTE,
            QueryOperator.LT,
            QueryOperator.LTE,
        ):
            return self._build_comparison_condition(field, operator)
        if operator in (QueryOperator.IN, QueryOperator.NOT_IN):
            return self._build_membership_condition(field, operator)
        if operator in (QueryOperator.LIKE, QueryOperator.ILIKE):
            return self._build_like_condition(field, operator)
        if operator in (QueryOperator.IS_NULL, QueryOperator.IS_NOT_NULL):
            return self._build_null_condition(field, operator)
        if operator == QueryOperator.BETWEEN:
            return self._build_between_condition(field)
        if operator == QueryOperator.REGEX:
            return self._build_regex_condition(field)
        msg = f"Unsupported operator: {operator}"
        raise ValueError(msg)

    def _build_equality_condition(self, field: str) -> str:
        return f"{field} = :{field}"

    def _build_inequality_condition(self, field: str) -> str:
        return f"{field} != :{field}"

    def _build_comparison_condition(self, field: str, operator: QueryOperator) -> str:
        operator_map = {
            QueryOperator.GT: ">",
            QueryOperator.GTE: ">=",
            QueryOperator.LT: "<",
            QueryOperator.LTE: "<=",
        }
        return f"{field} {operator_map[operator]} :{field}"

    def _build_membership_condition(self, field: str, operator: QueryOperator) -> str:
        if operator == QueryOperator.IN:
            return f"{field} = ANY(:{field})"
        return f"{field} != ALL(:{field})"

    def _build_like_condition(self, field: str, operator: QueryOperator) -> str:
        if operator == QueryOperator.LIKE:
            return f"{field} LIKE :{field}"
        return f"{field} ILIKE :{field}"

    def _build_null_condition(self, field: str, operator: QueryOperator) -> str:
        if operator == QueryOperator.IS_NULL:
            return f"{field} IS NULL"
        return f"{field} IS NOT NULL"

    def _build_between_condition(self, field: str) -> str:
        return f"{field} BETWEEN :{field}_start AND :{field}_end"

    def _build_regex_condition(self, field: str) -> str:
        return f"{field} ~ :{field}"

    def _build_order_clause(self, query_spec: QuerySpec) -> str:
        if not query_spec.sorts:
            return ""
        order_parts = []
        for sort in query_spec.sorts:
            direction = "ASC" if sort.direction == SortDirection.ASC else "DESC"
            order_parts.append(f"{sort.field} {direction}")

        return f"ORDER BY {', '.join(order_parts)}"

    def _build_params(self, query_spec: QuerySpec) -> dict[str, Any]:
        params = {}
        for condition in query_spec.filter.conditions:
            if condition.value is not None:
                if condition.operator == QueryOperator.BETWEEN:
                    if (
                        isinstance(condition.value, list | tuple)
                        and len(condition.value) == 2
                    ):
                        params[f"{condition.field}_start"] = condition.value[0]
                        params[f"{condition.field}_end"] = condition.value[1]
                else:
                    params[condition.field] = condition.value

        return params

    def _build_aggregation_query(
        self,
        entity: str,
        pipeline: list[dict[str, Any]],
    ) -> str:
        base_query = f"SELECT * FROM {entity}"  # nosec B608

        for stage in pipeline:
            if "$match" in stage:
                base_query = self._apply_match_stage(base_query, stage["$match"])
            elif "$group" in stage:
                base_query = self._apply_group_stage(entity, stage["$group"])
            elif "$sort" in stage:
                base_query = self._apply_sort_stage(base_query, stage["$sort"])
            elif "$limit" in stage:
                base_query = self._apply_limit_stage(base_query, stage["$limit"])

        return base_query

    def _apply_match_stage(
        self,
        base_query: str,
        match_conditions: dict[str, Any],
    ) -> str:
        conditions = [f"{key} = '{value}'" for key, value in match_conditions.items()]
        if conditions:
            return base_query + f" WHERE {' AND '.join(conditions)}"  # nosec B608
        return base_query

    def _apply_group_stage(self, entity: str, group_stage: dict[str, Any]) -> str:
        group_by = group_stage.get("_id", "")
        if not group_by:
            return f"SELECT * FROM {entity}"  # nosec B608
        select_parts = [group_by]
        for key, value in group_stage.items():
            if key != "_id" and isinstance(value, dict):
                aggregation_part = self._build_aggregation_part(key, value)
                if aggregation_part:
                    select_parts.append(aggregation_part)

        return f"SELECT {', '.join(select_parts)} FROM {entity} GROUP BY {group_by}"  # nosec B608

    def _build_aggregation_part(self, key: str, value: dict[str, Any]) -> str | None:
        for agg_op, field in value.items():
            if agg_op == "$sum":
                return f"SUM({field}) as {key}"
            if agg_op == "$avg":
                return f"AVG({field}) as {key}"
            if agg_op == "$count":
                return f"COUNT(*) as {key}"
        return None

    def _apply_sort_stage(self, base_query: str, sort_stage: dict[str, Any]) -> str:
        order_clauses = [
            f"{key} {'ASC' if direction == 1 else 'DESC'}"
            for key, direction in sort_stage.items()
        ]
        if order_clauses:
            return base_query + f" ORDER BY {', '.join(order_clauses)}"  # nosec B608
        return base_query

    def _apply_limit_stage(self, base_query: str, limit: int) -> str:
        return base_query + f" LIMIT {limit}"  # nosec B608
