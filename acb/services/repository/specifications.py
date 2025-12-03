"""Query Specification Pattern Implementation.

Provides composable query specifications for complex database queries:
- Specification pattern for query building
- Logical operators (AND, OR, NOT)
- Field-based specifications
- Range and comparison specifications
- Integration with repository query methods
"""

from abc import ABC, abstractmethod
from enum import Enum

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any


class ComparisonOperator(Enum):
    """Comparison operators for specifications."""

    EQUALS = "eq"
    NOT_EQUALS = "ne"
    GREATER_THAN = "gt"
    GREATER_THAN_OR_EQUAL = "gte"
    LESS_THAN = "lt"
    LESS_THAN_OR_EQUAL = "lte"
    IN = "in"
    NOT_IN = "not_in"
    LIKE = "like"
    ILIKE = "ilike"  # Case-insensitive like
    CONTAINS = "contains"
    STARTS_WITH = "starts_with"
    ENDS_WITH = "ends_with"
    IS_NULL = "is_null"
    IS_NOT_NULL = "is_not_null"
    BETWEEN = "between"


@dataclass
class SpecificationContext:
    """Context for specification evaluation."""

    entity_type: type
    field_mappings: dict[str, str] | None = (
        None  # Map logical field names to actual field names
    )
    table_alias: str | None = None
    join_conditions: list[str] | None = None

    def __post_init__(self) -> None:
        if self.field_mappings is None:
            self.field_mappings = {}
        if self.join_conditions is None:
            self.join_conditions = []

    def get_field_name(self, logical_name: str) -> str:
        """Get actual field name from logical name."""
        if self.field_mappings is None:
            return logical_name
        return self.field_mappings.get(logical_name, logical_name)


class Specification(ABC):
    """Abstract base class for query specifications.

    Specifications represent query criteria that can be combined
    using logical operators to build complex queries.
    """

    @abstractmethod
    def to_sql_where(self, context: SpecificationContext) -> tuple[str, dict[str, Any]]:
        """Convert specification to SQL WHERE clause.

        Args:
            context: Specification context with entity information

        Returns:
            Tuple of (where_clause, parameters)
        """

    @abstractmethod
    def to_nosql_filter(self, context: SpecificationContext) -> dict[str, Any]:
        """Convert specification to NoSQL filter.

        Args:
            context: Specification context with entity information

        Returns:
            NoSQL filter dictionary
        """

    @abstractmethod
    def to_dict(self) -> dict[str, Any]:
        """Convert specification to dictionary representation.

        Returns:
            Dictionary representation of the specification
        """

    def __and__(self, other: "Specification") -> "AndSpecification":
        """Combine specifications with AND operator."""
        return AndSpecification([self, other])

    def __or__(self, other: "Specification") -> "OrSpecification":
        """Combine specifications with OR operator."""
        return OrSpecification([self, other])

    def __invert__(self) -> "NotSpecification":
        """Negate specification with NOT operator."""
        return NotSpecification(self)


class FieldSpecification(Specification):
    """Specification for field-based queries."""

    def __init__(self, field: str, operator: ComparisonOperator, value: Any) -> None:
        self.field = field
        self.operator = operator
        self.value = value

    def to_sql_where(self, context: SpecificationContext) -> tuple[str, dict[str, Any]]:  # noqa: C901
        """Convert to SQL WHERE clause using match statement for operator dispatch.

        Note: Complexity from match statement is acceptable - each case is simple and focused.
        """
        field_name = self._get_full_field_name(context)
        param_key = self._generate_param_key()

        match self.operator:
            case ComparisonOperator.EQUALS:
                return self._sql_equals(field_name, param_key)
            case ComparisonOperator.NOT_EQUALS:
                return self._sql_not_equals(field_name, param_key)
            case ComparisonOperator.GREATER_THAN:
                return self._sql_greater_than(field_name, param_key)
            case ComparisonOperator.GREATER_THAN_OR_EQUAL:
                return self._sql_greater_than_or_equal(field_name, param_key)
            case ComparisonOperator.LESS_THAN:
                return self._sql_less_than(field_name, param_key)
            case ComparisonOperator.LESS_THAN_OR_EQUAL:
                return self._sql_less_than_or_equal(field_name, param_key)
            case ComparisonOperator.IN:
                return self._sql_in(field_name, param_key)
            case ComparisonOperator.NOT_IN:
                return self._sql_not_in(field_name, param_key)
            case ComparisonOperator.LIKE:
                return self._sql_like(field_name, param_key)
            case ComparisonOperator.ILIKE:
                return self._sql_ilike(field_name, param_key)
            case ComparisonOperator.CONTAINS:
                return self._sql_contains(field_name, param_key)
            case ComparisonOperator.STARTS_WITH:
                return self._sql_starts_with(field_name, param_key)
            case ComparisonOperator.ENDS_WITH:
                return self._sql_ends_with(field_name, param_key)
            case ComparisonOperator.IS_NULL:
                return self._sql_is_null(field_name)
            case ComparisonOperator.IS_NOT_NULL:
                return self._sql_is_not_null(field_name)
            case ComparisonOperator.BETWEEN:
                return self._sql_between(field_name, param_key)

        msg = f"Unsupported operator: {self.operator}"
        raise ValueError(msg)

    def to_nosql_filter(self, context: SpecificationContext) -> dict[str, Any]:  # noqa: C901
        """Convert to NoSQL filter using match statement for operator dispatch.

        Note: Complexity from match statement is acceptable - each case is simple and focused.
        """
        field_name = context.get_field_name(self.field)

        match self.operator:
            case ComparisonOperator.EQUALS:
                return {field_name: self.value}
            case ComparisonOperator.NOT_EQUALS:
                return {field_name: {"$ne": self.value}}
            case ComparisonOperator.GREATER_THAN:
                return {field_name: {"$gt": self.value}}
            case ComparisonOperator.GREATER_THAN_OR_EQUAL:
                return {field_name: {"$gte": self.value}}
            case ComparisonOperator.LESS_THAN:
                return {field_name: {"$lt": self.value}}
            case ComparisonOperator.LESS_THAN_OR_EQUAL:
                return {field_name: {"$lte": self.value}}
            case ComparisonOperator.IN:
                return {field_name: {"$in": self.value}}
            case ComparisonOperator.NOT_IN:
                return {field_name: {"$nin": self.value}}
            case ComparisonOperator.LIKE:
                return self._nosql_like(field_name)
            case ComparisonOperator.ILIKE:
                return self._nosql_ilike(field_name)
            case ComparisonOperator.CONTAINS:
                return {field_name: {"$regex": f".*{self.value}.*"}}
            case ComparisonOperator.STARTS_WITH:
                return {field_name: {"$regex": f"^{self.value}"}}
            case ComparisonOperator.ENDS_WITH:
                return {field_name: {"$regex": f"{self.value}$"}}
            case ComparisonOperator.IS_NULL:
                return {field_name: {"$exists": False}}
            case ComparisonOperator.IS_NOT_NULL:
                return {field_name: {"$exists": True}}
            case ComparisonOperator.BETWEEN:
                return self._nosql_between(field_name)

        msg = f"Unsupported operator for NoSQL: {self.operator}"
        raise ValueError(msg)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "type": "field",
            "field": self.field,
            "operator": self.operator.value,
            "value": self.value,
        }

    # Helper methods for field name and parameter generation
    def _get_full_field_name(self, context: SpecificationContext) -> str:
        """Get full field name with table alias if present."""
        field_name = context.get_field_name(self.field)
        table_prefix = f"{context.table_alias}." if context.table_alias else ""
        return f"{table_prefix}{field_name}"

    def _generate_param_key(self) -> str:
        """Generate unique parameter key for SQL binding."""
        return f"param_{abs(hash(f'{self.field}_{self.operator.value}_{self.value}'))}"

    # SQL operator handlers
    def _sql_equals(
        self,
        field_name: str,
        param_key: str,
    ) -> tuple[str, dict[str, Any]]:
        return f"{field_name} = :{param_key}", {param_key: self.value}

    def _sql_not_equals(
        self,
        field_name: str,
        param_key: str,
    ) -> tuple[str, dict[str, Any]]:
        return f"{field_name} != :{param_key}", {param_key: self.value}

    def _sql_greater_than(
        self,
        field_name: str,
        param_key: str,
    ) -> tuple[str, dict[str, Any]]:
        return f"{field_name} > :{param_key}", {param_key: self.value}

    def _sql_greater_than_or_equal(
        self,
        field_name: str,
        param_key: str,
    ) -> tuple[str, dict[str, Any]]:
        return f"{field_name} >= :{param_key}", {param_key: self.value}

    def _sql_less_than(
        self,
        field_name: str,
        param_key: str,
    ) -> tuple[str, dict[str, Any]]:
        return f"{field_name} < :{param_key}", {param_key: self.value}

    def _sql_less_than_or_equal(
        self,
        field_name: str,
        param_key: str,
    ) -> tuple[str, dict[str, Any]]:
        return f"{field_name} <= :{param_key}", {param_key: self.value}

    def _sql_in(self, field_name: str, param_key: str) -> tuple[str, dict[str, Any]]:
        if isinstance(self.value, list | tuple):
            placeholders = ",".join(f":{param_key}_{i}" for i in range(len(self.value)))
            params = {f"{param_key}_{i}": v for i, v in enumerate(self.value)}
            return f"{field_name} IN ({placeholders})", params
        return f"{field_name} IN (:{param_key})", {param_key: self.value}

    def _sql_not_in(
        self,
        field_name: str,
        param_key: str,
    ) -> tuple[str, dict[str, Any]]:
        if isinstance(self.value, list | tuple):
            placeholders = ",".join(f":{param_key}_{i}" for i in range(len(self.value)))
            params = {f"{param_key}_{i}": v for i, v in enumerate(self.value)}
            return f"{field_name} NOT IN ({placeholders})", params
        return f"{field_name} NOT IN (:{param_key})", {param_key: self.value}

    def _sql_like(self, field_name: str, param_key: str) -> tuple[str, dict[str, Any]]:
        return f"{field_name} LIKE :{param_key}", {param_key: self.value}

    def _sql_ilike(self, field_name: str, param_key: str) -> tuple[str, dict[str, Any]]:
        return f"UPPER({field_name}) LIKE UPPER(:{param_key})", {param_key: self.value}

    def _sql_contains(
        self,
        field_name: str,
        param_key: str,
    ) -> tuple[str, dict[str, Any]]:
        return f"{field_name} LIKE :{param_key}", {param_key: f"%{self.value}%"}

    def _sql_starts_with(
        self,
        field_name: str,
        param_key: str,
    ) -> tuple[str, dict[str, Any]]:
        return f"{field_name} LIKE :{param_key}", {param_key: f"{self.value}%"}

    def _sql_ends_with(
        self,
        field_name: str,
        param_key: str,
    ) -> tuple[str, dict[str, Any]]:
        return f"{field_name} LIKE :{param_key}", {param_key: f"%{self.value}"}

    def _sql_is_null(self, field_name: str) -> tuple[str, dict[str, Any]]:
        return f"{field_name} IS NULL", {}

    def _sql_is_not_null(self, field_name: str) -> tuple[str, dict[str, Any]]:
        return f"{field_name} IS NOT NULL", {}

    def _sql_between(
        self,
        field_name: str,
        param_key: str,
    ) -> tuple[str, dict[str, Any]]:
        if not isinstance(self.value, list | tuple) or len(self.value) != 2:
            msg = "BETWEEN operator requires a list/tuple of 2 values"
            raise ValueError(msg)

        return (
            f"{field_name} BETWEEN :{param_key}_start AND :{param_key}_end",
            {f"{param_key}_start": self.value[0], f"{param_key}_end": self.value[1]},
        )

    # NoSQL operator handlers
    def _nosql_like(self, field_name: str) -> dict[str, Any]:
        """Convert SQL LIKE to regex pattern."""
        pattern = self.value.replace("%", ".*").replace("_", ".")
        return {field_name: {"$regex": pattern}}

    def _nosql_ilike(self, field_name: str) -> dict[str, Any]:
        """Convert SQL ILIKE to case-insensitive regex."""
        pattern = self.value.replace("%", ".*").replace("_", ".")
        return {field_name: {"$regex": pattern, "$options": "i"}}

    def _nosql_between(self, field_name: str) -> dict[str, Any]:
        """Convert BETWEEN to NoSQL range query."""
        if not isinstance(self.value, list | tuple) or len(self.value) != 2:
            msg = "BETWEEN operator requires a list/tuple of 2 values"
            raise ValueError(msg)

        return {field_name: {"$gte": self.value[0], "$lte": self.value[1]}}


class AndSpecification(Specification):
    """Specification for AND operations."""

    def __init__(self, specifications: list[Specification]) -> None:
        self.specifications = specifications

    def to_sql_where(self, context: SpecificationContext) -> tuple[str, dict[str, Any]]:
        """Convert to SQL WHERE clause."""
        clauses = []
        all_params = {}

        for spec in self.specifications:
            clause, params = spec.to_sql_where(context)
            clauses.append(f"({clause})")
            all_params.update(params)

        return " AND ".join(clauses), all_params

    def to_nosql_filter(self, context: SpecificationContext) -> dict[str, Any]:
        """Convert to NoSQL filter."""
        filters = [spec.to_nosql_filter(context) for spec in self.specifications]
        return {"$and": filters}

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "type": "and",
            "specifications": [spec.to_dict() for spec in self.specifications],
        }


class OrSpecification(Specification):
    """Specification for OR operations."""

    def __init__(self, specifications: list[Specification]) -> None:
        self.specifications = specifications

    def to_sql_where(self, context: SpecificationContext) -> tuple[str, dict[str, Any]]:
        """Convert to SQL WHERE clause."""
        clauses = []
        all_params = {}

        for spec in self.specifications:
            clause, params = spec.to_sql_where(context)
            clauses.append(f"({clause})")
            all_params.update(params)

        return " OR ".join(clauses), all_params

    def to_nosql_filter(self, context: SpecificationContext) -> dict[str, Any]:
        """Convert to NoSQL filter."""
        filters = [spec.to_nosql_filter(context) for spec in self.specifications]
        return {"$or": filters}

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "type": "or",
            "specifications": [spec.to_dict() for spec in self.specifications],
        }


class NotSpecification(Specification):
    """Specification for NOT operations."""

    def __init__(self, specification: Specification) -> None:
        self.specification = specification

    def to_sql_where(self, context: SpecificationContext) -> tuple[str, dict[str, Any]]:
        """Convert to SQL WHERE clause."""
        clause, params = self.specification.to_sql_where(context)
        return f"NOT ({clause})", params

    def to_nosql_filter(self, context: SpecificationContext) -> dict[str, Any]:
        """Convert to NoSQL filter."""
        filter_dict = self.specification.to_nosql_filter(context)
        return {"$not": filter_dict}

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation."""
        return {"type": "not", "specification": self.specification.to_dict()}


# Convenience functions for creating specifications
def equals(field: str, value: Any) -> FieldSpecification:
    """Create equals specification."""
    return FieldSpecification(field, ComparisonOperator.EQUALS, value)


def not_equals(field: str, value: Any) -> FieldSpecification:
    """Create not equals specification."""
    return FieldSpecification(field, ComparisonOperator.NOT_EQUALS, value)


def greater_than(field: str, value: Any) -> FieldSpecification:
    """Create greater than specification."""
    return FieldSpecification(field, ComparisonOperator.GREATER_THAN, value)


def greater_than_or_equal(field: str, value: Any) -> FieldSpecification:
    """Create greater than or equal specification."""
    return FieldSpecification(field, ComparisonOperator.GREATER_THAN_OR_EQUAL, value)


def less_than(field: str, value: Any) -> FieldSpecification:
    """Create less than specification."""
    return FieldSpecification(field, ComparisonOperator.LESS_THAN, value)


def less_than_or_equal(field: str, value: Any) -> FieldSpecification:
    """Create less than or equal specification."""
    return FieldSpecification(field, ComparisonOperator.LESS_THAN_OR_EQUAL, value)


def in_values(field: str, values: list[Any]) -> FieldSpecification:
    """Create IN specification."""
    return FieldSpecification(field, ComparisonOperator.IN, values)


def not_in_values(field: str, values: list[Any]) -> FieldSpecification:
    """Create NOT IN specification."""
    return FieldSpecification(field, ComparisonOperator.NOT_IN, values)


def like(field: str, pattern: str) -> FieldSpecification:
    """Create LIKE specification."""
    return FieldSpecification(field, ComparisonOperator.LIKE, pattern)


def ilike(field: str, pattern: str) -> FieldSpecification:
    """Create case-insensitive LIKE specification."""
    return FieldSpecification(field, ComparisonOperator.ILIKE, pattern)


def contains(field: str, value: str) -> FieldSpecification:
    """Create contains specification."""
    return FieldSpecification(field, ComparisonOperator.CONTAINS, value)


def starts_with(field: str, value: str) -> FieldSpecification:
    """Create starts with specification."""
    return FieldSpecification(field, ComparisonOperator.STARTS_WITH, value)


def ends_with(field: str, value: str) -> FieldSpecification:
    """Create ends with specification."""
    return FieldSpecification(field, ComparisonOperator.ENDS_WITH, value)


def is_null(field: str) -> FieldSpecification:
    """Create IS NULL specification."""
    return FieldSpecification(field, ComparisonOperator.IS_NULL, None)


def is_not_null(field: str) -> FieldSpecification:
    """Create IS NOT NULL specification."""
    return FieldSpecification(field, ComparisonOperator.IS_NOT_NULL, None)


def between(field: str, start: Any, end: Any) -> FieldSpecification:
    """Create BETWEEN specification."""
    return FieldSpecification(field, ComparisonOperator.BETWEEN, [start, end])


def date_range(field: str, start_date: date, end_date: date) -> FieldSpecification:
    """Create date range specification."""
    return between(field, start_date, end_date)


def datetime_range(
    field: str,
    start_datetime: datetime,
    end_datetime: datetime,
) -> FieldSpecification:
    """Create datetime range specification."""
    return between(field, start_datetime, end_datetime)


def and_specs(*specifications: Specification) -> AndSpecification:
    """Create AND specification from multiple specifications."""
    return AndSpecification(list(specifications))


def or_specs(*specifications: Specification) -> OrSpecification:
    """Create OR specification from multiple specifications."""
    return OrSpecification(list(specifications))


def not_spec(specification: Specification) -> NotSpecification:
    """Create NOT specification."""
    return NotSpecification(specification)
