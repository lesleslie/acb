"""Query Specification Pattern Implementation.

Provides composable query specifications for complex database queries:
- Specification pattern for query building
- Logical operators (AND, OR, NOT)
- Field-based specifications
- Range and comparison specifications
- Integration with repository query methods
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date, datetime
from enum import Enum
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
    field_mappings: dict[str, str] = (
        None  # Map logical field names to actual field names
    )
    table_alias: str = None
    join_conditions: list[str] = None

    def __post_init__(self) -> None:
        if self.field_mappings is None:
            self.field_mappings = {}
        if self.join_conditions is None:
            self.join_conditions = []

    def get_field_name(self, logical_name: str) -> str:
        """Get actual field name from logical name."""
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
        """Convert to SQL WHERE clause."""
        field_name = context.get_field_name(self.field)
        table_prefix = f"{context.table_alias}." if context.table_alias else ""
        full_field = f"{table_prefix}{field_name}"

        param_key = (
            f"param_{abs(hash(f'{self.field}_{self.operator.value}_{self.value}'))}"
        )

        if self.operator == ComparisonOperator.EQUALS:
            return f"{full_field} = :{param_key}", {param_key: self.value}
        if self.operator == ComparisonOperator.NOT_EQUALS:
            return f"{full_field} != :{param_key}", {param_key: self.value}
        if self.operator == ComparisonOperator.GREATER_THAN:
            return f"{full_field} > :{param_key}", {param_key: self.value}
        if self.operator == ComparisonOperator.GREATER_THAN_OR_EQUAL:
            return f"{full_field} >= :{param_key}", {param_key: self.value}
        if self.operator == ComparisonOperator.LESS_THAN:
            return f"{full_field} < :{param_key}", {param_key: self.value}
        if self.operator == ComparisonOperator.LESS_THAN_OR_EQUAL:
            return f"{full_field} <= :{param_key}", {param_key: self.value}
        if self.operator == ComparisonOperator.IN:
            if isinstance(self.value, list | tuple):
                placeholders = ",".join(
                    f":{param_key}_{i}" for i in range(len(self.value))
                )
                params = {f"{param_key}_{i}": v for i, v in enumerate(self.value)}
                return f"{full_field} IN ({placeholders})", params
            return f"{full_field} IN (:{param_key})", {param_key: self.value}
        if self.operator == ComparisonOperator.NOT_IN:
            if isinstance(self.value, list | tuple):
                placeholders = ",".join(
                    f":{param_key}_{i}" for i in range(len(self.value))
                )
                params = {f"{param_key}_{i}": v for i, v in enumerate(self.value)}
                return f"{full_field} NOT IN ({placeholders})", params
            return f"{full_field} NOT IN (:{param_key})", {param_key: self.value}
        if self.operator == ComparisonOperator.LIKE:
            return f"{full_field} LIKE :{param_key}", {param_key: self.value}
        if self.operator == ComparisonOperator.ILIKE:
            return f"UPPER({full_field}) LIKE UPPER(:{param_key})", {
                param_key: self.value,
            }
        if self.operator == ComparisonOperator.CONTAINS:
            return f"{full_field} LIKE :{param_key}", {param_key: f"%{self.value}%"}
        if self.operator == ComparisonOperator.STARTS_WITH:
            return f"{full_field} LIKE :{param_key}", {param_key: f"{self.value}%"}
        if self.operator == ComparisonOperator.ENDS_WITH:
            return f"{full_field} LIKE :{param_key}", {param_key: f"%{self.value}"}
        if self.operator == ComparisonOperator.IS_NULL:
            return f"{full_field} IS NULL", {}
        if self.operator == ComparisonOperator.IS_NOT_NULL:
            return f"{full_field} IS NOT NULL", {}
        if self.operator == ComparisonOperator.BETWEEN:
            if isinstance(self.value, list | tuple) and len(self.value) == 2:
                return (
                    f"{full_field} BETWEEN :{param_key}_start AND :{param_key}_end",
                    {
                        f"{param_key}_start": self.value[0],
                        f"{param_key}_end": self.value[1],
                    },
                )
            msg = "BETWEEN operator requires a list/tuple of 2 values"
            raise ValueError(msg)
        msg = f"Unsupported operator: {self.operator}"
        raise ValueError(msg)

    def to_nosql_filter(self, context: SpecificationContext) -> dict[str, Any]:  # noqa: C901
        """Convert to NoSQL filter."""
        field_name = context.get_field_name(self.field)

        if self.operator == ComparisonOperator.EQUALS:
            return {field_name: self.value}
        if self.operator == ComparisonOperator.NOT_EQUALS:
            return {field_name: {"$ne": self.value}}
        if self.operator == ComparisonOperator.GREATER_THAN:
            return {field_name: {"$gt": self.value}}
        if self.operator == ComparisonOperator.GREATER_THAN_OR_EQUAL:
            return {field_name: {"$gte": self.value}}
        if self.operator == ComparisonOperator.LESS_THAN:
            return {field_name: {"$lt": self.value}}
        if self.operator == ComparisonOperator.LESS_THAN_OR_EQUAL:
            return {field_name: {"$lte": self.value}}
        if self.operator == ComparisonOperator.IN:
            return {field_name: {"$in": self.value}}
        if self.operator == ComparisonOperator.NOT_IN:
            return {field_name: {"$nin": self.value}}
        if self.operator == ComparisonOperator.LIKE:
            # Convert SQL LIKE to regex
            pattern = self.value.replace("%", ".*").replace("_", ".")
            return {field_name: {"$regex": pattern}}
        if self.operator == ComparisonOperator.ILIKE:
            pattern = self.value.replace("%", ".*").replace("_", ".")
            return {field_name: {"$regex": pattern, "$options": "i"}}
        if self.operator == ComparisonOperator.CONTAINS:
            return {field_name: {"$regex": f".*{self.value}.*"}}
        if self.operator == ComparisonOperator.STARTS_WITH:
            return {field_name: {"$regex": f"^{self.value}"}}
        if self.operator == ComparisonOperator.ENDS_WITH:
            return {field_name: {"$regex": f"{self.value}$"}}
        if self.operator == ComparisonOperator.IS_NULL:
            return {field_name: {"$exists": False}}
        if self.operator == ComparisonOperator.IS_NOT_NULL:
            return {field_name: {"$exists": True}}
        if self.operator == ComparisonOperator.BETWEEN:
            if isinstance(self.value, list | tuple) and len(self.value) == 2:
                return {field_name: {"$gte": self.value[0], "$lte": self.value[1]}}
            msg = "BETWEEN operator requires a list/tuple of 2 values"
            raise ValueError(msg)
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
