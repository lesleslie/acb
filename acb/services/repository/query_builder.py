"""Query Builder Implementation.

Provides fluent query building interface:
- Fluent query API
- Dynamic query construction
- SQL and NoSQL query generation
- Performance optimization hints
"""

from enum import Enum

from dataclasses import dataclass
from datetime import datetime
from typing import Any, TypeVar

from ._base import PaginationInfo, RepositoryBase, SortCriteria, SortDirection
from .specifications import ComparisonOperator, FieldSpecification, Specification

EntityType = TypeVar("EntityType")


class QueryType(Enum):
    """Query type enumeration."""

    SELECT = "select"
    COUNT = "count"
    EXISTS = "exists"
    AGGREGATE = "aggregate"


class AggregateFunction(Enum):
    """Aggregate function enumeration."""

    SUM = "sum"
    AVG = "avg"
    MIN = "min"
    MAX = "max"
    COUNT = "count"
    COUNT_DISTINCT = "count_distinct"


@dataclass
class QueryResult:
    """Query execution result."""

    data: Any
    total_count: int | None = None
    execution_time: float | None = None
    query_type: QueryType = QueryType.SELECT
    cache_hit: bool = False
    metadata: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        if self.metadata is None:
            self.metadata = {}


@dataclass
class AggregateSpec:
    """Aggregate specification."""

    function: AggregateFunction
    field: str
    alias: str | None = None

    @property
    def name(self) -> str:
        """Get aggregate name."""
        return self.alias or f"{self.function.value}_{self.field}"


class QueryBuilder:
    """Fluent query builder for repositories.

    Provides a fluent interface for building complex queries with
    support for filtering, sorting, pagination, and aggregation.
    """

    def __init__(self, repository: RepositoryBase[EntityType, Any]) -> None:
        self.repository = repository
        self._specifications: list[Specification] = []
        self._sort_criteria: list[SortCriteria] = []
        self._pagination: PaginationInfo | None = None
        self._selected_fields: list[str] = []
        self._group_by_fields: list[str] = []
        self._having_specs: list[Specification] = []
        self._aggregates: list[AggregateSpec] = []
        self._distinct = False
        self._limit: int | None = None
        self._offset: int | None = None
        self._query_hints: dict[str, Any] = {}

    def where(self, specification: Specification) -> "QueryBuilder":
        """Add WHERE clause specification.

        Args:
            specification: Query specification

        Returns:
            Query builder for chaining
        """
        self._specifications.append(specification)
        return self

    def where_field(
        self,
        field: str,
        operator: ComparisonOperator,
        value: Any,
    ) -> "QueryBuilder":
        """Add field-based WHERE clause.

        Args:
            field: Field name
            operator: Comparison operator
            value: Comparison value

        Returns:
            Query builder for chaining
        """
        spec = FieldSpecification(field, operator, value)
        return self.where(spec)

    def where_equals(self, field: str, value: Any) -> "QueryBuilder":
        """Add equals WHERE clause.

        Args:
            field: Field name
            value: Expected value

        Returns:
            Query builder for chaining
        """
        return self.where_field(field, ComparisonOperator.EQUALS, value)

    def where_in(self, field: str, values: list[Any]) -> "QueryBuilder":
        """Add IN WHERE clause.

        Args:
            field: Field name
            values: List of values

        Returns:
            Query builder for chaining
        """
        return self.where_field(field, ComparisonOperator.IN, values)

    def where_like(self, field: str, pattern: str) -> "QueryBuilder":
        """Add LIKE WHERE clause.

        Args:
            field: Field name
            pattern: LIKE pattern

        Returns:
            Query builder for chaining
        """
        return self.where_field(field, ComparisonOperator.LIKE, pattern)

    def where_between(self, field: str, start: Any, end: Any) -> "QueryBuilder":
        """Add BETWEEN WHERE clause.

        Args:
            field: Field name
            start: Start value
            end: End value

        Returns:
            Query builder for chaining
        """
        return self.where_field(field, ComparisonOperator.BETWEEN, [start, end])

    def where_null(self, field: str) -> "QueryBuilder":
        """Add IS NULL WHERE clause.

        Args:
            field: Field name

        Returns:
            Query builder for chaining
        """
        return self.where_field(field, ComparisonOperator.IS_NULL, None)

    def where_not_null(self, field: str) -> "QueryBuilder":
        """Add IS NOT NULL WHERE clause.

        Args:
            field: Field name

        Returns:
            Query builder for chaining
        """
        return self.where_field(field, ComparisonOperator.IS_NOT_NULL, None)

    def order_by(
        self,
        field: str,
        direction: SortDirection = SortDirection.ASC,
    ) -> "QueryBuilder":
        """Add ORDER BY clause.

        Args:
            field: Field name to sort by
            direction: Sort direction

        Returns:
            Query builder for chaining
        """
        self._sort_criteria.append(SortCriteria(field, direction))
        return self

    def order_by_asc(self, field: str) -> "QueryBuilder":
        """Add ascending ORDER BY clause.

        Args:
            field: Field name to sort by

        Returns:
            Query builder for chaining
        """
        return self.order_by(field, SortDirection.ASC)

    def order_by_desc(self, field: str) -> "QueryBuilder":
        """Add descending ORDER BY clause.

        Args:
            field: Field name to sort by

        Returns:
            Query builder for chaining
        """
        return self.order_by(field, SortDirection.DESC)

    def page(self, page: int, page_size: int = 50) -> "QueryBuilder":
        """Add pagination.

        Args:
            page: Page number (1-based)
            page_size: Items per page

        Returns:
            Query builder for chaining
        """
        self._pagination = PaginationInfo(page=page, page_size=page_size)
        return self

    def limit(self, limit: int) -> "QueryBuilder":
        """Add LIMIT clause.

        Args:
            limit: Maximum number of results

        Returns:
            Query builder for chaining
        """
        self._limit = limit
        return self

    def offset(self, offset: int) -> "QueryBuilder":
        """Add OFFSET clause.

        Args:
            offset: Number of results to skip

        Returns:
            Query builder for chaining
        """
        self._offset = offset
        return self

    def select(self, *fields: str) -> "QueryBuilder":
        """Select specific fields.

        Args:
            fields: Field names to select

        Returns:
            Query builder for chaining
        """
        self._selected_fields.extend(fields)
        return self

    def distinct(self) -> "QueryBuilder":
        """Add DISTINCT clause.

        Returns:
            Query builder for chaining
        """
        self._distinct = True
        return self

    def group_by(self, *fields: str) -> "QueryBuilder":
        """Add GROUP BY clause.

        Args:
            fields: Field names to group by

        Returns:
            Query builder for chaining
        """
        self._group_by_fields.extend(fields)
        return self

    def having(self, specification: Specification) -> "QueryBuilder":
        """Add HAVING clause specification.

        Args:
            specification: HAVING specification

        Returns:
            Query builder for chaining
        """
        self._having_specs.append(specification)
        return self

    def aggregate(
        self,
        function: AggregateFunction,
        field: str,
        alias: str | None = None,
    ) -> "QueryBuilder":
        """Add aggregate function.

        Args:
            function: Aggregate function
            field: Field to aggregate
            alias: Optional alias for result

        Returns:
            Query builder for chaining
        """
        self._aggregates.append(AggregateSpec(function, field, alias))
        return self

    def sum(self, field: str, alias: str | None = None) -> "QueryBuilder":
        """Add SUM aggregate.

        Args:
            field: Field to sum
            alias: Optional alias

        Returns:
            Query builder for chaining
        """
        return self.aggregate(AggregateFunction.SUM, field, alias)

    def avg(self, field: str, alias: str | None = None) -> "QueryBuilder":
        """Add AVG aggregate.

        Args:
            field: Field to average
            alias: Optional alias

        Returns:
            Query builder for chaining
        """
        return self.aggregate(AggregateFunction.AVG, field, alias)

    def min(self, field: str, alias: str | None = None) -> "QueryBuilder":
        """Add MIN aggregate.

        Args:
            field: Field to find minimum
            alias: Optional alias

        Returns:
            Query builder for chaining
        """
        return self.aggregate(AggregateFunction.MIN, field, alias)

    def max(self, field: str, alias: str | None = None) -> "QueryBuilder":
        """Add MAX aggregate.

        Args:
            field: Field to find maximum
            alias: Optional alias

        Returns:
            Query builder for chaining
        """
        return self.aggregate(AggregateFunction.MAX, field, alias)

    def count(self, field: str = "*", alias: str | None = None) -> "QueryBuilder":
        """Add COUNT aggregate.

        Args:
            field: Field to count (default: *)
            alias: Optional alias

        Returns:
            Query builder for chaining
        """
        return self.aggregate(AggregateFunction.COUNT, field, alias)

    def count_distinct(self, field: str, alias: str | None = None) -> "QueryBuilder":
        """Add COUNT DISTINCT aggregate.

        Args:
            field: Field to count distinct values
            alias: Optional alias

        Returns:
            Query builder for chaining
        """
        return self.aggregate(AggregateFunction.COUNT_DISTINCT, field, alias)

    def hint(self, key: str, value: Any) -> "QueryBuilder":
        """Add query hint.

        Args:
            key: Hint key
            value: Hint value

        Returns:
            Query builder for chaining
        """
        self._query_hints[key] = value
        return self

    def use_index(self, index_name: str) -> "QueryBuilder":
        """Add index hint.

        Args:
            index_name: Index to use

        Returns:
            Query builder for chaining
        """
        return self.hint("use_index", index_name)

    def parallel(self, degree: int = 4) -> "QueryBuilder":
        """Enable parallel query execution.

        Args:
            degree: Degree of parallelism

        Returns:
            Query builder for chaining
        """
        return self.hint("parallel", degree)

    async def execute(self) -> QueryResult:
        """Execute the query.

        Returns:
            Query result
        """
        start_time = datetime.now()

        try:
            # Determine query type
            result_data: Any
            if self._aggregates:
                query_type = QueryType.AGGREGATE
                result_data = await self._execute_aggregate()
            else:
                query_type = QueryType.SELECT
                result_data = await self._execute_select()

            execution_time = (datetime.now() - start_time).total_seconds()

            return QueryResult(
                data=result_data,
                execution_time=execution_time,
                query_type=query_type,
                metadata=self._query_hints.copy(),
            )

        except Exception as e:
            execution_time = (datetime.now() - start_time).total_seconds()
            msg = f"Query execution failed after {execution_time:.3f}s: {e}"
            raise RuntimeError(
                msg,
            ) from e

    async def first(self) -> EntityType | None:
        """Execute query and return first result.

        Returns:
            First entity or None if not found
        """
        # Set limit to 1 for efficiency
        original_limit = self._limit
        self._limit = 1

        try:
            result = await self.execute()
            if isinstance(result.data, list) and result.data:
                return result.data[0]
            return None
        finally:
            self._limit = original_limit

    async def count_only(self) -> int:
        """Execute count query only.

        Returns:
            Total count of matching records
        """
        # Convert specifications to filters for count
        filters = self._build_filters()
        return await self.repository.count(filters)

    async def exists_any(self) -> bool:
        """Check if any records match the query.

        Returns:
            True if any records match, False otherwise
        """
        count = await self.count_only()
        return count > 0

    async def to_list(self) -> list[EntityType]:
        """Execute query and return list of entities.

        Returns:
            List of matching entities
        """
        result = await self.execute()
        if isinstance(result.data, list):
            return result.data
        return [result.data] if result.data else []

    async def _execute_select(self) -> list[EntityType]:
        """Execute SELECT query."""
        filters = self._build_filters()
        sort_criteria = self._sort_criteria or None
        pagination = self._pagination

        # Handle limit/offset if no pagination
        if not pagination and (self._limit or self._offset):
            page = (
                (self._offset // self._limit) + 1 if self._limit and self._offset else 1
            )
            page_size = self._limit or 50
            pagination = PaginationInfo(page=page, page_size=page_size)

        return await self.repository.list(filters, sort_criteria, pagination)  # type: ignore[return-value]

    async def _execute_aggregate(self) -> dict[str, Any]:
        """Execute aggregate query."""
        # For now, implement basic aggregates using repository methods
        # In a full implementation, this would generate appropriate SQL/NoSQL queries
        filters = self._build_filters()

        results: dict[str, int | None] = {}

        # Get count for COUNT aggregates
        count_aggregates = [
            agg for agg in self._aggregates if agg.function == AggregateFunction.COUNT
        ]
        if count_aggregates:
            total_count = await self.repository.count(filters)
            for agg in count_aggregates:
                results[agg.name] = total_count

        # For other aggregates, we'd need to execute custom queries
        # This is a simplified implementation
        for agg in self._aggregates:
            if agg.function != AggregateFunction.COUNT:
                results[agg.name] = None  # Would implement actual aggregation

        return results

    def _build_filters(self) -> dict[str, Any] | None:
        """Build filters dictionary from specifications."""
        if not self._specifications:
            return None

        # This is a simplified implementation
        # In a full implementation, we'd convert specifications to filters
        filters = {}

        for spec in self._specifications:
            if isinstance(spec, FieldSpecification):
                if spec.operator == ComparisonOperator.EQUALS:
                    filters[spec.field] = spec.value
                # Add more operators as needed

        return filters or None

    def clone(self) -> "QueryBuilder":
        """Create a copy of this query builder.

        Returns:
            New query builder with same configuration
        """
        new_builder = QueryBuilder(self.repository)
        new_builder._specifications = self._specifications.copy()
        new_builder._sort_criteria = self._sort_criteria.copy()
        new_builder._pagination = self._pagination
        new_builder._selected_fields = self._selected_fields.copy()
        new_builder._group_by_fields = self._group_by_fields.copy()
        new_builder._having_specs = self._having_specs.copy()
        new_builder._aggregates = self._aggregates.copy()
        new_builder._distinct = self._distinct
        new_builder._limit = self._limit
        new_builder._offset = self._offset
        new_builder._query_hints = self._query_hints.copy()
        return new_builder

    def reset(self) -> "QueryBuilder":
        """Reset query builder to initial state.

        Returns:
            Query builder for chaining
        """
        self._specifications.clear()
        self._sort_criteria.clear()
        self._pagination = None
        self._selected_fields.clear()
        self._group_by_fields.clear()
        self._having_specs.clear()
        self._aggregates.clear()
        self._distinct = False
        self._limit = None
        self._offset = None
        self._query_hints.clear()
        return self
