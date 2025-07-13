"""Specification Pattern for Composable Business Rules.

This module implements the Specification Pattern, allowing business rules to be
expressed as composable, reusable objects that can be combined and tested independently.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from typing import Any, TypeVar

from acb.adapters.models._query import QueryCondition, QueryOperator, QuerySpec

T = TypeVar("T")


class LogicalOperator(Enum):
    AND = "and"
    OR = "or"
    NOT = "not"


@dataclass
class SpecificationResult:
    satisfied: bool
    reason: str | None = None
    context: dict[str, Any] | None = None


class Specification[T](ABC):
    @abstractmethod
    def is_satisfied_by(self, candidate: T) -> bool:
        pass

    @abstractmethod
    def to_query_spec(self) -> QuerySpec:
        pass

    def evaluate(self, candidate: T) -> SpecificationResult:
        try:
            satisfied = self.is_satisfied_by(candidate)
            return SpecificationResult(
                satisfied=satisfied,
                reason=f"Specification {self.__class__.__name__} {'satisfied' if satisfied else 'not satisfied'}",
                context={"specification": self.__class__.__name__},
            )
        except Exception as e:
            return SpecificationResult(
                satisfied=False,
                reason=f"Error evaluating specification: {e!s}",
                context={"error": str(e)},
            )

    def and_(self, other: Specification[T]) -> CompositeSpecification[T]:
        return CompositeSpecification(self, other, LogicalOperator.AND)

    def or_(self, other: Specification[T]) -> CompositeSpecification[T]:
        return CompositeSpecification(self, other, LogicalOperator.OR)

    def not_(self) -> NotSpecification[T]:
        return NotSpecification(self)

    def __and__(self, other: Specification[T]) -> CompositeSpecification[T]:
        return self.and_(other)

    def __or__(self, other: Specification[T]) -> CompositeSpecification[T]:
        return self.or_(other)

    def __invert__(self) -> NotSpecification[T]:
        return self.not_()


class CompositeSpecification(Specification[T]):
    def __init__(
        self,
        left: Specification[T],
        right: Specification[T],
        operator: LogicalOperator,
    ) -> None:
        self.left = left
        self.right = right
        self.operator = operator

    def is_satisfied_by(self, candidate: T) -> bool:
        left_result = self.left.is_satisfied_by(candidate)
        right_result = self.right.is_satisfied_by(candidate)
        if self.operator == LogicalOperator.AND:
            return left_result and right_result
        if self.operator == LogicalOperator.OR:
            return left_result or right_result
        msg = f"Unsupported logical operator: {self.operator}"
        raise ValueError(msg)

    def to_query_spec(self) -> QuerySpec:
        left_spec = self.left.to_query_spec()
        right_spec = self.right.to_query_spec()
        combined_spec = QuerySpec()
        combined_spec.filter.conditions.extend(left_spec.filter.conditions)
        combined_spec.filter.conditions.extend(right_spec.filter.conditions)
        if self.operator == LogicalOperator.AND:
            combined_spec.filter.logical_operator = "AND"
        elif self.operator == LogicalOperator.OR:
            combined_spec.filter.logical_operator = "OR"
        combined_spec.sorts.extend(left_spec.sorts)
        combined_spec.sorts.extend(right_spec.sorts)
        if left_spec.limit is not None and right_spec.limit is not None:
            combined_spec.limit = min(left_spec.limit, right_spec.limit)
        elif left_spec.limit is not None:
            combined_spec.limit = left_spec.limit
        elif right_spec.limit is not None:
            combined_spec.limit = right_spec.limit
        if left_spec.offset is not None and right_spec.offset is not None:
            combined_spec.offset = max(left_spec.offset, right_spec.offset)
        elif left_spec.offset is not None:
            combined_spec.offset = left_spec.offset
        elif right_spec.offset is not None:
            combined_spec.offset = right_spec.offset

        return combined_spec

    def evaluate(self, candidate: T) -> SpecificationResult:
        left_result = self.left.evaluate(candidate)
        right_result = self.right.evaluate(candidate)
        if self.operator == LogicalOperator.AND:
            satisfied = left_result.satisfied and right_result.satisfied
            reason = f"({left_result.reason}) AND ({right_result.reason})"
        elif self.operator == LogicalOperator.OR:
            satisfied = left_result.satisfied or right_result.satisfied
            reason = f"({left_result.reason}) OR ({right_result.reason})"
        else:
            satisfied = False
            reason = f"Unknown operator: {self.operator}"

        return SpecificationResult(
            satisfied=satisfied,
            reason=reason,
            context={
                "left": left_result.context,
                "right": right_result.context,
                "operator": self.operator.value,
            },
        )


class NotSpecification(Specification[T]):
    def __init__(self, specification: Specification[T]) -> None:
        self.specification = specification

    def is_satisfied_by(self, candidate: T) -> bool:
        return not self.specification.is_satisfied_by(candidate)

    def to_query_spec(self) -> QuerySpec:
        inner_spec = self.specification.to_query_spec()
        inverted_spec = QuerySpec()
        for condition in inner_spec.filter.conditions:
            inverted_condition = self._invert_condition(condition)
            inverted_spec.filter.conditions.append(inverted_condition)
        if inner_spec.filter.logical_operator == "AND":
            inverted_spec.filter.logical_operator = "OR"
        else:
            inverted_spec.filter.logical_operator = "AND"

        return inverted_spec

    def _invert_condition(self, condition: QueryCondition) -> QueryCondition:
        operator_inversions = {
            QueryOperator.EQ: QueryOperator.NE,
            QueryOperator.NE: QueryOperator.EQ,
            QueryOperator.GT: QueryOperator.LTE,
            QueryOperator.GTE: QueryOperator.LT,
            QueryOperator.LT: QueryOperator.GTE,
            QueryOperator.LTE: QueryOperator.GT,
            QueryOperator.IN: QueryOperator.NOT_IN,
            QueryOperator.NOT_IN: QueryOperator.IN,
            QueryOperator.IS_NULL: QueryOperator.IS_NOT_NULL,
            QueryOperator.IS_NOT_NULL: QueryOperator.IS_NULL,
            QueryOperator.LIKE: QueryOperator.NOT_IN,
            QueryOperator.ILIKE: QueryOperator.NOT_IN,
        }
        return QueryCondition(
            condition.field,
            operator_inversions.get(condition.operator, condition.operator),
            condition.value,
        )

    def evaluate(self, candidate: T) -> SpecificationResult:
        inner_result = self.specification.evaluate(candidate)

        return SpecificationResult(
            satisfied=not inner_result.satisfied,
            reason=f"NOT ({inner_result.reason})",
            context={"inner": inner_result.context, "operator": "NOT"},
        )


class FieldSpecification(Specification[T]):
    def __init__(self, field: str, operator: QueryOperator, value: Any) -> None:
        self.field = field
        self.operator = operator
        self.value = value

    def is_satisfied_by(self, candidate: T) -> bool:
        if not hasattr(candidate, self.field):
            return False
        field_value = getattr(candidate, self.field)
        return self._evaluate_condition(field_value)

    def _evaluate_condition(self, field_value: Any) -> bool:
        if self.operator == QueryOperator.EQ:
            return field_value == self.value
        if self.operator == QueryOperator.NE:
            return field_value != self.value
        if self.operator in (
            QueryOperator.GT,
            QueryOperator.GTE,
            QueryOperator.LT,
            QueryOperator.LTE,
        ):
            return self._evaluate_comparison(field_value)
        if self.operator in (QueryOperator.IN, QueryOperator.NOT_IN):
            return self._evaluate_membership(field_value)
        if self.operator in (QueryOperator.IS_NULL, QueryOperator.IS_NOT_NULL):
            return self._evaluate_null_check(field_value)
        if self.operator == QueryOperator.LIKE:
            return self._evaluate_like_pattern(field_value)
        if self.operator == QueryOperator.BETWEEN:
            return self._evaluate_between_range(field_value)
        return False

    def _evaluate_comparison(self, field_value: Any) -> bool:
        if self.operator == QueryOperator.GT:
            return field_value > self.value
        if self.operator == QueryOperator.GTE:
            return field_value >= self.value
        if self.operator == QueryOperator.LT:
            return field_value < self.value
        if self.operator == QueryOperator.LTE:
            return field_value <= self.value
        return False

    def _evaluate_membership(self, field_value: Any) -> bool:
        if self.operator == QueryOperator.IN:
            return field_value in self.value
        if self.operator == QueryOperator.NOT_IN:
            return field_value not in self.value
        return False

    def _evaluate_null_check(self, field_value: Any) -> bool:
        if self.operator == QueryOperator.IS_NULL:
            return field_value is None
        if self.operator == QueryOperator.IS_NOT_NULL:
            return field_value is not None
        return False

    def _evaluate_like_pattern(self, field_value: Any) -> bool:
        pattern = str(self.value).replace("%", "").replace("_", "")
        return pattern in str(field_value)

    def _evaluate_between_range(self, field_value: Any) -> bool:
        if isinstance(self.value, list | tuple) and len(self.value) == 2:
            return self.value[0] <= field_value <= self.value[1]
        return False

    def to_query_spec(self) -> QuerySpec:
        spec = QuerySpec()
        condition = QueryCondition(self.field, self.operator, self.value)
        spec.filter.conditions.append(condition)
        return spec


class RangeSpecification(Specification[T]):
    def __init__(
        self,
        field: str,
        min_value: Any,
        max_value: Any,
        inclusive: bool = True,
    ) -> None:
        self.field = field
        self.min_value = min_value
        self.max_value = max_value
        self.inclusive = inclusive

    def is_satisfied_by(self, candidate: T) -> bool:
        if not hasattr(candidate, self.field):
            return False
        field_value = getattr(candidate, self.field)
        if self.inclusive:
            return self.min_value <= field_value <= self.max_value
        return self.min_value < field_value < self.max_value

    def to_query_spec(self) -> QuerySpec:
        spec = QuerySpec()
        if self.inclusive:
            min_condition = QueryCondition(
                self.field,
                QueryOperator.GTE,
                self.min_value,
            )
            max_condition = QueryCondition(
                self.field,
                QueryOperator.LTE,
                self.max_value,
            )
        else:
            min_condition = QueryCondition(self.field, QueryOperator.GT, self.min_value)
            max_condition = QueryCondition(self.field, QueryOperator.LT, self.max_value)
        spec.filter.conditions.extend((min_condition, max_condition))
        spec.filter.logical_operator = "AND"

        return spec


class ListSpecification(Specification[T]):
    def __init__(self, field: str, values: list[Any], include: bool = True) -> None:
        self.field = field
        self.values = values
        self.include = include

    def is_satisfied_by(self, candidate: T) -> bool:
        if not hasattr(candidate, self.field):
            return False
        field_value = getattr(candidate, self.field)
        in_list = field_value in self.values

        return in_list if self.include else not in_list

    def to_query_spec(self) -> QuerySpec:
        spec = QuerySpec()
        operator = QueryOperator.IN if self.include else QueryOperator.NOT_IN
        condition = QueryCondition(self.field, operator, self.values)
        spec.filter.conditions.append(condition)
        return spec


class CustomSpecification(Specification[T]):
    def __init__(
        self,
        predicate: Callable[..., Any],
        query_spec: QuerySpec,
        name: str = "CustomSpecification",
    ) -> None:
        self.predicate = predicate
        self.query_spec = query_spec
        self.name = name

    def is_satisfied_by(self, candidate: T) -> bool:
        try:
            return self.predicate(candidate)
        except Exception:
            return False

    def to_query_spec(self) -> QuerySpec:
        return self.query_spec

    def evaluate(self, candidate: T) -> SpecificationResult:
        try:
            satisfied = self.predicate(candidate)
            return SpecificationResult(
                satisfied=satisfied,
                reason=f"Custom specification '{self.name}' {'satisfied' if satisfied else 'not satisfied'}",
                context={"specification": self.name},
            )
        except Exception as e:
            return SpecificationResult(
                satisfied=False,
                reason=f"Error in custom specification '{self.name}': {e!s}",
                context={"error": str(e), "specification": self.name},
            )


class SpecificationBuilder:
    @staticmethod
    def field(field: str) -> FieldSpecificationBuilder:
        return FieldSpecificationBuilder(field)

    @staticmethod
    def range(
        field: str,
        min_value: Any,
        max_value: Any,
        inclusive: bool = True,
    ) -> RangeSpecification[Any]:
        return RangeSpecification(field, min_value, max_value, inclusive)

    @staticmethod
    def list(
        field: str, values: list[Any], include: bool = True
    ) -> ListSpecification[Any]:
        return ListSpecification(field, values, include)

    @staticmethod
    def custom(
        predicate: Callable[..., Any],
        query_spec: QuerySpec,
        name: str = "CustomSpecification",
    ) -> CustomSpecification[Any]:
        return CustomSpecification(predicate, query_spec, name)


class FieldSpecificationBuilder:
    def __init__(self, field: str) -> None:
        self.field = field

    def equals(self, value: Any) -> FieldSpecification[Any]:
        return FieldSpecification(self.field, QueryOperator.EQ, value)

    def not_equals(self, value: Any) -> FieldSpecification[Any]:
        return FieldSpecification(self.field, QueryOperator.NE, value)

    def greater_than(self, value: Any) -> FieldSpecification[Any]:
        return FieldSpecification(self.field, QueryOperator.GT, value)

    def greater_than_or_equal(self, value: Any) -> FieldSpecification[Any]:
        return FieldSpecification(self.field, QueryOperator.GTE, value)

    def less_than(self, value: Any) -> FieldSpecification[Any]:
        return FieldSpecification(self.field, QueryOperator.LT, value)

    def less_than_or_equal(self, value: Any) -> FieldSpecification[Any]:
        return FieldSpecification(self.field, QueryOperator.LTE, value)

    def in_list(self, values: list[Any]) -> FieldSpecification[Any]:
        return FieldSpecification(self.field, QueryOperator.IN, values)

    def not_in_list(self, values: list[Any]) -> FieldSpecification[Any]:
        return FieldSpecification(self.field, QueryOperator.NOT_IN, values)

    def is_null(self) -> FieldSpecification[Any]:
        return FieldSpecification(self.field, QueryOperator.IS_NULL, None)

    def is_not_null(self) -> FieldSpecification[Any]:
        return FieldSpecification(self.field, QueryOperator.IS_NOT_NULL, None)

    def like(self, pattern: str) -> FieldSpecification[Any]:
        return FieldSpecification(self.field, QueryOperator.LIKE, pattern)

    def between(self, min_value: Any, max_value: Any) -> FieldSpecification[Any]:
        return FieldSpecification(
            self.field,
            QueryOperator.BETWEEN,
            [min_value, max_value],
        )


def field(field_name: str) -> FieldSpecificationBuilder:
    return SpecificationBuilder.field(field_name)


def range_spec(
    field: str,
    min_value: Any,
    max_value: Any,
    inclusive: bool = True,
) -> RangeSpecification[Any]:
    return SpecificationBuilder.range(field, min_value, max_value, inclusive)


def list_spec(
    field: str, values: list[Any], include: bool = True
) -> ListSpecification[Any]:
    return SpecificationBuilder.list(field, values, include)


def custom_spec(
    predicate: Callable[..., Any],
    query_spec: QuerySpec,
    name: str = "CustomSpecification",
) -> CustomSpecification[Any]:
    return SpecificationBuilder.custom(predicate, query_spec, name)
